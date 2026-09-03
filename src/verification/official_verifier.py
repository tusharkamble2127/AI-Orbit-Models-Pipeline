from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests import Response

from src.config import (
    INTERMEDIATE_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    ensure_directories,
)


INPUT_PATH = (
    INTERMEDIATE_DATA_DIR / "models_dev_normalized.json"
)

OUTPUT_PATH = (
    INTERMEDIATE_DATA_DIR / "models_verified.json"
)


logger = logging.getLogger(__name__)


class OfficialVerifier:
    """Verify model source URLs without inventing missing information."""

    def __init__(
        self,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/json"
                ),
            }
        )

    @staticmethod
    def _normalize_url(url: str | None) -> str | None:
        """Normalize a URL for storage."""
        if not url:
            return None

        url = url.strip()

        if not url:
            return None

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        return url.rstrip("/")

    @staticmethod
    def _domain(url: str | None) -> str | None:
        """Extract hostname from a URL."""
        normalized = OfficialVerifier._normalize_url(url)

        if not normalized:
            return None

        try:
            hostname = urlparse(normalized).hostname
        except ValueError:
            return None

        return hostname.lower() if hostname else None

    @staticmethod
    def _get_weight_urls(
        record: dict[str, Any],
    ) -> list[str]:
        """Extract URLs from model weight records."""
        urls: list[str] = []

        weights = record.get("weights", [])

        if not isinstance(weights, list):
            return urls

        for weight in weights:
            if not isinstance(weight, dict):
                continue

            url = OfficialVerifier._normalize_url(
                weight.get("url")
            )

            if url:
                urls.append(url)

        return urls

    def _check_url(
        self,
        url: str,
    ) -> dict[str, Any]:
        """
        Check a URL with redirects enabled.

        We record the result instead of raising on normal
        HTTP/network failures.
        """
        normalized = self._normalize_url(url)

        result: dict[str, Any] = {
            "url": normalized,
            "final_url": None,
            "domain": self._domain(normalized),
            "status_code": None,
            "content_type": None,
            "reachable": False,
            "redirected": False,
            "error": None,
        }

        if not normalized:
            result["error"] = "invalid_url"
            return result

        try:
            response: Response = self.session.get(
                normalized,
                timeout=self.timeout,
                allow_redirects=True,
            )

            result["status_code"] = response.status_code
            result["final_url"] = response.url
            result["content_type"] = response.headers.get(
                "Content-Type"
            )

            result["reachable"] = (
                200 <= response.status_code < 400
            )

            result["redirected"] = (
                response.url.rstrip("/")
                != normalized.rstrip("/")
            )

        except requests.Timeout:
            result["error"] = "timeout"

        except requests.RequestException as exc:
            result["error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        return result

    def verify_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify source availability for one model.

        This does not yet make a final identity decision.
        It only records evidence.
        """
        checked_at = datetime.now(
            timezone.utc
        ).isoformat()

        provider_docs = record.get(
            "provider_docs",
            [],
        )

        if not isinstance(provider_docs, list):
            provider_docs = []

        weight_urls = self._get_weight_urls(record)

        sources: list[dict[str, Any]] = []

        for url in provider_docs:
            result = self._check_url(url)

            result["source_type"] = (
                "provider_documentation"
            )

            sources.append(result)

        for url in weight_urls:
            result = self._check_url(url)

            result["source_type"] = (
                "huggingface_or_weight_source"
            )

            sources.append(result)

        reachable_provider_docs = [
            item
            for item in sources
            if (
                item["source_type"]
                == "provider_documentation"
                and item["reachable"]
            )
        ]

        reachable_weights = [
            item
            for item in sources
            if (
                item["source_type"]
                == "huggingface_or_weight_source"
                and item["reachable"]
            )
        ]

        if reachable_provider_docs:
            verification_status = "verified_provider_source"

        elif reachable_weights:
            verification_status = (
                "verified_secondary_source"
            )

        elif sources:
            verification_status = "source_unreachable"

        else:
            verification_status = "needs_manual_review"

        verified_record = dict(record)

        verified_record["verification"] = {
            "checked_at": checked_at,
            "status": verification_status,
            "sources_checked": sources,
            "provider_source_verified": bool(
                reachable_provider_docs
            ),
            "secondary_source_verified": bool(
                reachable_weights
            ),
            "requires_manual_review": (
                verification_status
                in {
                    "source_unreachable",
                    "needs_manual_review",
                }
            ),
        }

        return verified_record

    def verify_all(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Verify all model records sequentially."""
        verified: list[dict[str, Any]] = []

        total = len(records)

        for index, record in enumerate(
            records,
            start=1,
        ):
            model_name = (
                record.get("model_name")
                or record.get("model_id")
                or "unknown"
            )

            logger.info(
                "[%d/%d] Verifying %s",
                index,
                total,
                model_name,
            )

            verified.append(
                self.verify_record(record)
            )

        return verified

    @staticmethod
    def save(
        records: list[dict[str, Any]],
    ) -> Path:
        """Save verified records."""
        ensure_directories()

        with OUTPUT_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return OUTPUT_PATH


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    with INPUT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise TypeError(
            "Expected normalized models to be a list."
        )

    verifier = OfficialVerifier()

    verified_records = verifier.verify_all(
        records
    )

    output_path = verifier.save(
        verified_records
    )

    summary: dict[str, int] = {}

    for record in verified_records:
        status = record["verification"]["status"]

        summary[status] = (
            summary.get(status, 0) + 1
        )

    print()
    print(
        "Official source verification completed."
    )
    print(
        f"Input records: {len(records)}"
    )
    print(
        f"Output: {output_path}"
    )

    print("\nVerification summary:")

    for status, count in sorted(
        summary.items()
    ):
        print(f"{status}: {count}")


if __name__ == "__main__":
    main()