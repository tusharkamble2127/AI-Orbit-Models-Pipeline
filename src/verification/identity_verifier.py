from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from rapidfuzz.fuzz import ratio

from src.config import (
    INTERMEDIATE_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)


INPUT_PATH = (
    INTERMEDIATE_DATA_DIR / "models_verified.json"
)

OUTPUT_PATH = (
    INTERMEDIATE_DATA_DIR / "models_identity_verified.json"
)


logger = logging.getLogger(__name__)


class IdentityVerifier:
    """
    Verify whether reachable source pages actually correspond
    to the expected model.

    This is still an evidence layer. It does not make destructive
    deduplication decisions.
    """

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
    def normalize_text(value: str | None) -> str:
        """Normalize text for comparison."""
        if not value:
            return ""

        value = value.lower().strip()

        # Keep alphanumeric characters and spaces.
        value = re.sub(r"[^a-z0-9]+", " ", value)

        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def extract_domain(url: str | None) -> str | None:
        """Extract a normalized hostname."""
        if not url:
            return None

        try:
            hostname = urlparse(url).hostname
        except ValueError:
            return None

        if not hostname:
            return None

        return hostname.lower()

    @staticmethod
    def get_page_text(
        response: requests.Response,
    ) -> tuple[str, str | None]:
        """
        Extract page title and visible text.

        We intentionally cap visible text to avoid storing
        enormous HTML pages.
        """
        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "html" not in content_type:
            return "", None

        soup = BeautifulSoup(
            response.text,
            "lxml",
        )

        title = None

        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        for element in soup(
            ["script", "style", "noscript"]
        ):
            element.decompose()

        text = soup.get_text(
            separator=" ",
            strip=True,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        # Keep enough context for matching while avoiding
        # huge payloads.
        text = text[:10000]

        return text, title

    def fetch_page(
        self,
        url: str,
    ) -> dict[str, Any]:
        """Fetch a page and extract lightweight evidence."""
        result: dict[str, Any] = {
            "url": url,
            "final_url": None,
            "domain": self.extract_domain(url),
            "status_code": None,
            "reachable": False,
            "page_title": None,
            "page_text": "",
            "error": None,
        }

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
            )

            result["final_url"] = response.url
            result["status_code"] = (
                response.status_code
            )

            result["reachable"] = (
                200 <= response.status_code < 400
            )

            if not result["reachable"]:
                return result

            page_text, title = self.get_page_text(
                response
            )

            result["page_title"] = title
            result["page_text"] = page_text

        except requests.Timeout:
            result["error"] = "timeout"

        except requests.RequestException as exc:
            result["error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        return result

    def calculate_identity_score(
        self,
        record: dict[str, Any],
        page: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Calculate deterministic identity evidence.

        This is a heuristic score for triage, not a truth oracle.
        """

        expected_name = self.normalize_text(
            record.get("model_name")
        )

        expected_id = self.normalize_text(
            record.get("model_id")
        )

        title = self.normalize_text(
            page.get("page_title")
        )

        page_text = self.normalize_text(
            page.get("page_text")
        )

        final_url = self.normalize_text(
            page.get("final_url")
        )

        evidence: list[str] = []
        score = 0

        # --------------------------------------------------
        # Model name
        # --------------------------------------------------
        name_similarity = 0.0

        if expected_name and title:
            name_similarity = ratio(
                expected_name,
                title,
            )

            if name_similarity >= 90:
                score += 40
                evidence.append(
                    "model_name_strongly_matches_title"
                )
            elif name_similarity >= 75:
                score += 20
                evidence.append(
                    "model_name_partially_matches_title"
                )

        # --------------------------------------------------
        # Exact model name in page text
        # --------------------------------------------------
        if (
            expected_name
            and len(expected_name) >= 4
            and expected_name in page_text
        ):
            score += 25
            evidence.append(
                "model_name_found_in_page_text"
            )

        # --------------------------------------------------
        # Model ID in page text / URL
        # --------------------------------------------------
        if (
            expected_id
            and len(expected_id) >= 5
            and (
                expected_id in page_text
                or expected_id in final_url
            )
        ):
            score += 25
            evidence.append(
                "model_id_found_in_page_or_url"
            )

        # --------------------------------------------------
        # Repository / slug overlap
        # --------------------------------------------------
        raw_id = record.get("model_id")

        if isinstance(raw_id, str):
            id_parts = [
                self.normalize_text(part)
                for part in raw_id.split("/")
                if part
            ]

            id_parts = [
                part
                for part in id_parts
                if len(part) >= 3
            ]

            matched_parts = sum(
                1
                for part in id_parts
                if part in page_text
                or part in final_url
            )

            if matched_parts:
                score += min(
                    10,
                    matched_parts * 5,
                )

                evidence.append(
                    "model_id_components_found"
                )

        # --------------------------------------------------
        # Determine status
        # --------------------------------------------------
        if score >= 70:
            identity_status = "strong_match"
        elif score >= 45:
            identity_status = "probable_match"
        elif score >= 20:
            identity_status = "weak_match"
        else:
            identity_status = "unverified"

        return {
            "score": score,
            "status": identity_status,
            "name_similarity": round(
                name_similarity,
                2,
            ),
            "evidence": evidence,
        }

    def verify_source(
        self,
        record: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify one previously discovered source."""
        url = source.get("url")

        if not url:
            return {
                **source,
                "identity": {
                    "status": "unverified",
                    "score": 0,
                    "evidence": ["missing_url"],
                },
            }

        page = self.fetch_page(url)

        if not page["reachable"]:
            return {
                **source,
                "identity": {
                    "status": "source_unreachable",
                    "score": 0,
                    "evidence": [
                        page.get("error")
                        or f"http_{page.get('status_code')}"
                    ],
                },
            }

        identity = self.calculate_identity_score(
            record,
            page,
        )

        # Don't store full page text in final intermediate data.
        clean_source = {
            **source,
            "identity": identity,
            "page_title": page.get(
                "page_title"
            ),
            "final_url": page.get(
                "final_url"
            ),
            "domain": page.get(
                "domain"
            ),
        }

        return clean_source

    def verify_record(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify all reachable sources for one model."""

        verification = record.get(
            "verification",
            {},
        )

        sources = verification.get(
            "sources_checked",
            [],
        )

        if not isinstance(sources, list):
            sources = []

        verified_sources: list[dict[str, Any]] = []

        for source in sources:
            if not isinstance(source, dict):
                continue

            verified_sources.append(
                self.verify_source(
                    record,
                    source,
                )
            )

        strong_matches = [
            source
            for source in verified_sources
            if source.get("identity", {}).get(
                "status"
            )
            == "strong_match"
        ]

        probable_matches = [
            source
            for source in verified_sources
            if source.get("identity", {}).get(
                "status"
            )
            == "probable_match"
        ]

        if strong_matches:
            identity_status = "verified_identity"

        elif probable_matches:
            identity_status = (
                "probable_identity"
            )

        elif verified_sources:
            identity_status = "needs_review"

        else:
            identity_status = "no_identity_evidence"

        verified_record = dict(record)

        verified_record["identity_verification"] = {
            "checked_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "status": identity_status,
            "strong_matches": len(
                strong_matches
            ),
            "probable_matches": len(
                probable_matches
            ),
            "sources": verified_sources,
        }

        return verified_record

    def run(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Run identity verification for all records."""

        output: list[dict[str, Any]] = []

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
                "[%d/%d] Identity checking %s",
                index,
                total,
                model_name,
            )

            output.append(
                self.verify_record(
                    record
                )
            )

        return output


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
            "Expected verified model data to be a list."
        )

    verifier = IdentityVerifier()

    results = verifier.run(records)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )

    summary: dict[str, int] = {}

    for record in results:
        status = record[
            "identity_verification"
        ]["status"]

        summary[status] = (
            summary.get(status, 0) + 1
        )

    print()
    print(
        "Identity verification completed."
    )
    print(
        f"Input records: {len(records)}"
    )
    print(
        f"Output: {OUTPUT_PATH}"
    )

    print("\nIdentity summary:")

    for status, count in sorted(
        summary.items()
    ):
        print(f"{status}: {count}")


if __name__ == "__main__":
    main()