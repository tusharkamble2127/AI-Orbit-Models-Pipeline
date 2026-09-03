from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_verified.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_hf_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "huggingface_metadata_enrichment_report.txt"

HF_API = "https://huggingface.co/api/models/"
REQUEST_TIMEOUT = 20
USER_AGENT = "AIOrbit-Models-Pipeline/1.0"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def extract_hf_repo(record: dict) -> str | None:
    urls = record.get("huggingface") or []

    if isinstance(urls, str):
        urls = [urls]

    for url in urls:
        if not isinstance(url, str):
            continue

        match = re.search(
            r"huggingface\.co/([^/?#]+/[^/?#]+)",
            url,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    # Fall back to source URLs.
    urls = record.get("source_urls") or []

    if isinstance(urls, str):
        urls = [urls]

    for url in urls:
        if not isinstance(url, str):
            continue

        match = re.search(
            r"huggingface\.co/([^/?#]+/[^/?#]+)",
            url,
            flags=re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def extract_license(payload: dict) -> str | None:
    card_data = payload.get("cardData")

    if isinstance(card_data, dict):
        value = card_data.get("license")

        if isinstance(value, str) and value.strip():
            return value.strip()

    value = payload.get("license")

    if isinstance(value, str) and value.strip():
        return value.strip()

    tags = payload.get("tags")

    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, str):
                continue

            if tag.startswith("license:"):
                value = tag.split(":", 1)[1].strip()

                if value:
                    return value

    return None


def normalize_license(value: str | None) -> str | None:
    if not value:
        return None

    return value.strip()


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_verified.json"
        )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )

    repositories_found = 0
    api_success = 0
    api_failures = 0
    downloads_added = 0
    licenses_added = 0
    hf_urls_added = 0

    updated_records = []

    for record in records:

        item = dict(record)

        repo_id = extract_hf_repo(item)

        if not repo_id:
            updated_records.append(item)
            continue

        repositories_found += 1

        api_url = HF_API + repo_id

        try:
            response = session.get(
                api_url,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                api_failures += 1
                updated_records.append(item)
                continue

            data = response.json()

            if not isinstance(data, dict):
                api_failures += 1
                updated_records.append(item)
                continue

            api_success += 1

            hf_url = f"https://huggingface.co/{repo_id}"

            # -------------------------------------------------
            # Hugging Face URL
            # -------------------------------------------------

            hf_urls = item.get("huggingface")

            if not isinstance(hf_urls, list):
                hf_urls = []

            if hf_url not in hf_urls:
                hf_urls.append(hf_url)
                hf_urls_added += 1

            item["huggingface"] = hf_urls

            # -------------------------------------------------
            # Adoption / downloads
            # -------------------------------------------------

            downloads = data.get("downloads")

            if (
                downloads is not None
                and item.get("adoption_downloads")
                in (None, "", [], {})
            ):
                item["adoption_downloads"] = {
                    "source": "Hugging Face",
                    "metric": "downloads",
                    "value": downloads,
                    "repo_id": repo_id,
                    "url": hf_url,
                }

                downloads_added += 1

            # -------------------------------------------------
            # License
            # -------------------------------------------------

            license_value = normalize_license(
                extract_license(data)
            )

            if (
                license_value
                and item.get("license")
                in (None, "", [], {})
            ):
                item["license"] = {
                    "name": license_value,
                    "source": "Hugging Face model metadata",
                    "repo_id": repo_id,
                    "url": hf_url,
                }

                licenses_added += 1

            # -------------------------------------------------
            # Source URL
            # -------------------------------------------------

            source_urls = item.get("source_urls")

            if not isinstance(source_urls, list):
                source_urls = []

            if hf_url not in source_urls:
                source_urls.append(hf_url)

            item["source_urls"] = source_urls

        except requests.RequestException:
            api_failures += 1

        except (ValueError, TypeError, KeyError):
            api_failures += 1

        updated_records.append(item)

    output = {
        "metadata": {
            **(
                payload.get("metadata")
                or {}
            ),
            "dataset_name": (
                "AIOrbit Models Hugging Face "
                "Enriched Dataset"
            ),
            "huggingface_enrichment": {
                "repositories_found": repositories_found,
                "api_success": api_success,
                "api_failures": api_failures,
                "downloads_added": downloads_added,
                "licenses_added": licenses_added,
                "hf_urls_added": hf_urls_added,
                "source": "Hugging Face Hub API",
            },
        },
        "records": updated_records,
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    lines = [
        "AIOrbit Models - Hugging Face Metadata Enrichment",
        f"Input records: {len(records)}",
        f"HF repositories found: {repositories_found}",
        f"Successful API responses: {api_success}",
        f"API failures: {api_failures}",
        f"Downloads added: {downloads_added}",
        f"Licenses added: {licenses_added}",
        f"HF URLs added: {hf_urls_added}",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(f"Input records: {len(records)}")
    print(f"HF repositories found: {repositories_found}")
    print(f"Successful API responses: {api_success}")
    print(f"API failures: {api_failures}")
    print(f"Downloads added: {downloads_added}")
    print(f"Licenses added: {licenses_added}")
    print(f"HF URLs added: {hf_urls_added}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()