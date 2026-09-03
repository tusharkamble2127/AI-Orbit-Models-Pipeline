from __future__ import annotations

import json
from pathlib import Path

from src.config import FINAL_DATA_DIR, ensure_directories


BASE_FILE = FINAL_DATA_DIR / "models_final_enriched.json"
VERIFIED_FILE = FINAL_DATA_DIR / "models_verified_enriched.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_final_verified.json"
REPORT_FILE = FINAL_DATA_DIR / "merge_verified_enrichment_report.txt"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_empty(value):
    return value in (None, "", [], {})


def main() -> None:
    ensure_directories()

    base_payload = load_json(BASE_FILE)
    verified_payload = load_json(VERIFIED_FILE)

    base_records = base_payload.get("records")
    verified_records = verified_payload.get("records")

    if not isinstance(base_records, list):
        raise ValueError(
            "Base file must contain a 'records' list"
        )

    if not isinstance(verified_records, list):
        raise ValueError(
            "Verified file must contain a 'records' list"
        )

    verified_by_id = {
        record.get("model_id"): record
        for record in verified_records
        if record.get("model_id")
    }

    merged_records = []

    matched_models = 0
    fields_added = 0

    for base_record in base_records:

        model_id = base_record.get("model_id")
        verified_record = verified_by_id.get(model_id)

        merged = dict(base_record)

        if verified_record is not None:
            matched_models += 1

            for field, value in verified_record.items():

                if field == "model_id":
                    continue

                # Preserve existing verified/non-empty values.
                if is_empty(value):
                    continue

                if is_empty(merged.get(field)):
                    merged[field] = value
                    fields_added += 1

                # field_applicability is metadata from the
                # applicability stage and should also be preserved.
                if field == "field_applicability":
                    merged[field] = value

        merged_records.append(merged)

    output = {
        "metadata": {
            **(base_payload.get("metadata") or {}),
            "dataset_name": (
                "AIOrbit Models Final Verified Enriched Dataset"
            ),
            "source_files": [
                BASE_FILE.name,
                VERIFIED_FILE.name,
            ],
            "merge_stats": {
                "base_records": len(base_records),
                "verified_records": len(verified_records),
                "matched_models": matched_models,
                "fields_added": fields_added,
            },
        },
        "records": merged_records,
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

    report_lines = [
        "AIOrbit Models - Verified Enrichment Merge",
        f"Base records: {len(base_records)}",
        f"Verified records: {len(verified_records)}",
        f"Matched models: {matched_models}",
        f"Fields added: {fields_added}",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(
        f"Base records: {len(base_records)}"
    )

    print(
        f"Verified records: {len(verified_records)}"
    )

    print(
        f"Matched models: {matched_models}"
    )

    print(
        f"Fields added: {fields_added}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Report: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()