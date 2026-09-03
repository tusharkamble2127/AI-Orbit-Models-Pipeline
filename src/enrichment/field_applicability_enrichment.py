from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_enriched.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_applicability_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "field_applicability_report.txt"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0

    return False


def is_open_weight_model(record: dict) -> bool:
    return record.get("open_source_weights") is True


def has_huggingface(record: dict) -> bool:
    return bool(record.get("huggingface"))


def has_benchmarks(record: dict) -> bool:
    return not is_missing(record.get("benchmarks"))


def has_official_website(record: dict) -> bool:
    return not is_missing(record.get("official_website"))


def has_pricing(record: dict) -> bool:
    return not is_missing(record.get("pricing"))


def has_license(record: dict) -> bool:
    return not is_missing(record.get("license"))


def classify_field(record: dict, field: str) -> str:
    """
    Decide the status of a field without inventing values.

    VERIFIED:
        Existing value is already present.

    NOT_APPLICABLE:
        We can safely determine that the field does not apply.

    NEEDS_VERIFICATION:
        The field may apply, but there is currently insufficient evidence.
    """

    value = record.get(field)

    if not is_missing(value):
        return "verified"

    # Embeddings:
    # We do NOT assume generative models support embeddings.
    # Missing value therefore requires verification.
    if field == "embeddings":
        return "needs_verification"

    # License:
    # Open-weight models should have a license identified.
    # Closed/API models may be proprietary, but we don't infer
    # a legal license without source evidence.
    if field == "license":
        if is_open_weight_model(record):
            return "needs_verification"
        return "needs_verification"

    # Pricing:
    # Pricing is meaningful for API/access models, but absence
    # does not prove free/no-cost.
    if field == "pricing":
        return "needs_verification"

    # Official website:
    if field == "official_website":
        return "needs_verification"

    # Adoption/downloads:
    # This field is not universally applicable.
    if field == "adoption_downloads":
        if has_huggingface(record):
            return "needs_verification"

        # For models without public download infrastructure,
        # there may be no public download metric.
        # We still avoid converting that assumption into a value.
        return "needs_verification"

    # Hugging Face:
    if field == "huggingface":
        return "needs_verification"

    # GitHub:
    if field == "github":
        return "needs_verification"

    # Structured output:
    if field == "structured_output":
        return "needs_verification"

    # Benchmarks:
    if field == "benchmarks":
        return "needs_verification"

    return "needs_verification"


def build_applicability(record: dict) -> dict:
    tracked_fields = [
        "official_website",
        "pricing",
        "license",
        "embeddings",
        "huggingface",
        "github",
        "structured_output",
        "benchmarks",
        "adoption_downloads",
    ]

    applicability = {}

    for field in tracked_fields:
        applicability[field] = {
            "status": classify_field(record, field),
            "current_value_present": not is_missing(
                record.get(field)
            ),
        }

    # Extra model-level indicators useful for later enrichment.
    applicability["model_characteristics"] = {
        "open_weight": is_open_weight_model(record),
        "has_huggingface": has_huggingface(record),
        "has_benchmarks": has_benchmarks(record),
        "has_official_website": has_official_website(record),
        "has_pricing": has_pricing(record),
        "has_license": has_license(record),
    }

    return applicability


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_enriched.json"
        )

    output_records = []

    status_counts = {}

    for record in records:
        item = dict(record)

        applicability = build_applicability(record)

        item["field_applicability"] = applicability

        for field_info in applicability.values():
            if not isinstance(field_info, dict):
                continue

            status = field_info.get("status")

            if status:
                status_counts[status] = (
                    status_counts.get(status, 0) + 1
                )

        output_records.append(item)

    output = {
        "metadata": {
            **(payload.get("metadata") or {}),
            "dataset_name": (
                "AIOrbit Models Applicability Enriched Dataset"
            ),
            "applicability_stage": "field-level triage",
            "notes": [
                "No unsupported values are invented.",
                "Existing verified values are preserved.",
                "Missing fields are classified for targeted verification.",
            ],
        },
        "records": output_records,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        "AIOrbit Models - Field Applicability Enrichment",
        f"Records: {len(records)}",
        "",
        "STATUS COUNTS",
        "=" * 90,
    ]

    for status, count in sorted(
        status_counts.items()
    ):
        lines.append(
            f"{status:<25} {count}"
        )

    lines.extend(
        [
            "",
            "FIELD-LEVEL TARGETS",
            "=" * 90,
        ]
    )

    tracked_fields = [
        "official_website",
        "pricing",
        "license",
        "embeddings",
        "huggingface",
        "github",
        "structured_output",
        "benchmarks",
        "adoption_downloads",
    ]

    for field in tracked_fields:

        counts = {
            "verified": 0,
            "needs_verification": 0,
            "not_applicable": 0,
        }

        for record in output_records:
            status = (
                record["field_applicability"]
                [field]["status"]
            )

            counts[status] = (
                counts.get(status, 0) + 1
            )

        lines.append(
            f"{field:<25} "
            f"verified={counts['verified']:<3} "
            f"needs_verification={counts['needs_verification']:<3} "
            f"not_applicable={counts['not_applicable']:<3}"
        )

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"Input records: {len(records)}"
    )

    print(
        f"Output records: {len(output_records)}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Report: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()