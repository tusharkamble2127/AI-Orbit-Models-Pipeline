from __future__ import annotations

import json
from pathlib import Path

from src.config import FINAL_DATA_DIR, ensure_directories


BASE_FILE = FINAL_DATA_DIR / "models_final_normalized.json"
TARGET_FILE = FINAL_DATA_DIR / "models_target_enriched.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_final_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "models_final_enriched_report.txt"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_empty(value):
    return value in (None, "", [], {})


def main():
    ensure_directories()

    base_payload = load_json(BASE_FILE)
    target_payload = load_json(TARGET_FILE)

    base_records = base_payload.get("records")
    target_records = target_payload.get("records")

    if not isinstance(base_records, list):
        raise ValueError("Base dataset must contain 'records' list")

    if not isinstance(target_records, list):
        raise ValueError("Target dataset must contain 'records' list")

    target_by_id = {
        record.get("model_id"): record
        for record in target_records
        if record.get("model_id")
    }

    merged_records = []
    matched_models = 0
    fields_added = 0

    for base_record in base_records:
        model_id = base_record.get("model_id")
        target_record = target_by_id.get(model_id)

        merged = dict(base_record)

        if target_record is not None:
            matched_models += 1

            for field, value in target_record.items():
                if field == "model_id":
                    continue

                if is_empty(value):
                    continue

                if is_empty(merged.get(field)):
                    merged[field] = value
                    fields_added += 1

        merged_records.append(merged)

    output = {
        "metadata": {
            **(base_payload.get("metadata") or {}),
            "dataset_name": (
                "AIOrbit Models Final Enriched Candidate Dataset"
            ),
            "source_files": [
                BASE_FILE.name,
                TARGET_FILE.name,
            ],
            "merge_stats": {
                "base_records": len(base_records),
                "target_records": len(target_records),
                "matched_models": matched_models,
                "fields_added": fields_added,
            },
        },
        "records": merged_records,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        "AIOrbit Models - Final Enrichment Merge",
        f"Base records: {len(base_records)}",
        f"Target records: {len(target_records)}",
        f"Matched models: {matched_models}",
        f"Fields added: {fields_added}",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(f"Base records: {len(base_records)}")
    print(f"Target records: {len(target_records)}")
    print(f"Matched models: {matched_models}")
    print(f"Fields added: {fields_added}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()