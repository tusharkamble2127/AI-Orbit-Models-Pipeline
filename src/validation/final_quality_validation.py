from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_with_descriptions.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_final_validated.json"
REPORT_FILE = FINAL_DATA_DIR / "final_quality_validation_report.txt"


CRITICAL_FIELDS = [
    "model_id",
    "model_name",
    "model_family",
    "company_provider",
    "description",
    "model_type_task",
    "modalities",
    "context_window",
    "reasoning",
    "function_tool_calling",
    "quality_score",
    "quality_band",
    "source_urls",
    "identity_verification",
    "curation_status",
    "variant_review",
]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_missing(value):
    return value is None or value == "" or value == [] or value == {}


def valid_url(url):
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def validate_description(record):
    description = str(record.get("description") or "").strip()

    problems = []

    if not description:
        problems.append("missing")

    word_count = len(description.split())

    if word_count < 30:
        problems.append("too_short")

    if word_count > 130:
        problems.append("too_long")

    if "\n" in description:
        problems.append("multiple_lines")

    lower = description.lower()

    for phrase in [
        "revolutionary",
        "game-changing",
        "world-class",
        "best model",
        "according to the source",
    ]:
        if phrase in lower:
            problems.append("marketing_or_meta_phrase")

    if "http://" in lower or "https://" in lower:
        problems.append("contains_url")

    return problems


def validate_record(record):
    errors = []

    for field in CRITICAL_FIELDS:
        if is_missing(record.get(field)):
            errors.append(f"missing:{field}")

    # Quality score
    score = record.get("quality_score")

    if not isinstance(score, (int, float)):
        errors.append("invalid_quality_score")
    elif not 0 <= float(score) <= 100:
        errors.append("quality_score_out_of_range")

    # Quality band
    valid_bands = {
        "excellent",
        "good",
        "borderline",
        "reject_candidate",
        "quality_candidate",
        "manual_identity_review",
        "identity_review_recommended",
        "low_quality_candidate",
        "borderline_candidate",
    }

    band = record.get("quality_band")

    if band is not None and band not in valid_bands:
        errors.append("unknown_quality_band")

    # Source URLs
    urls = record.get("source_urls")

    if not isinstance(urls, list) or not urls:
        errors.append("missing_source_urls")
    else:
        invalid_urls = [
            url for url in urls
            if not valid_url(url)
        ]

        if invalid_urls:
            errors.append(
                f"invalid_source_urls:{len(invalid_urls)}"
            )

    # Description
    errors.extend(
        f"description:{error}"
        for error in validate_description(record)
    )

    return errors


def main():
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected records list in models_with_descriptions.json"
        )

    ids = [
        record.get("model_id")
        for record in records
    ]

    duplicate_ids = sorted(
        {
            model_id
            for model_id in ids
            if model_id
            and ids.count(model_id) > 1
        }
    )

    record_errors = {}

    for record in records:
        errors = validate_record(record)

        if errors:
            record_errors[
                record.get("model_id")
            ] = errors

    # Description statistics
    word_counts = [
        len(str(record.get("description") or "").split())
        for record in records
    ]

    validation = {
        "record_count": len(records),
        "duplicate_model_ids": duplicate_ids,
        "records_with_errors": len(record_errors),
        "record_errors": record_errors,
        "description_statistics": {
            "min_words": min(word_counts) if word_counts else 0,
            "max_words": max(word_counts) if word_counts else 0,
            "average_words": (
                round(
                    sum(word_counts) / len(word_counts),
                    2,
                )
                if word_counts
                else 0
            ),
        },
        "valid": (
            len(duplicate_ids) == 0
            and len(record_errors) == 0
        ),
    }

    output = {
        "metadata": {
            **(payload.get("metadata") or {}),
            "dataset_name":
                "AIOrbit Models Final Validated Dataset",
            "validation": validation,
        },
        "records": records,
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
        "AIOrbit Models - Final Quality Validation",
        f"Records: {len(records)}",
        f"Duplicate model IDs: {len(duplicate_ids)}",
        f"Records with errors: {len(record_errors)}",
        "",
        "DESCRIPTION STATISTICS",
        "=" * 90,
        f"Minimum words: {validation['description_statistics']['min_words']}",
        f"Maximum words: {validation['description_statistics']['max_words']}",
        f"Average words: {validation['description_statistics']['average_words']}",
        "",
        f"DATASET VALID: {validation['valid']}",
        "",
        "RECORD ERRORS",
        "=" * 90,
    ]

    if record_errors:
        for model_id, errors in record_errors.items():
            lines.append(
                f"{model_id}: {', '.join(errors)}"
            )
    else:
        lines.append("None")

    lines.extend([
        "",
        f"Output: {OUTPUT_FILE}",
    ])

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(f"Records: {len(records)}")
    print(
        f"Duplicate model IDs: "
        f"{len(duplicate_ids)}"
    )
    print(
        f"Records with errors: "
        f"{len(record_errors)}"
    )
    print(
        f"Dataset valid: "
        f"{validation['valid']}"
    )
    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()