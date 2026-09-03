from __future__ import annotations

import json
from pathlib import Path

from src.config import FINAL_DATA_DIR, ensure_directories


BASE_FILE = FINAL_DATA_DIR / "models_final_hf_verified.json"
PATCH_FILE = FINAL_DATA_DIR / "models_provider_patched.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_final_provider_verified.json"
REPORT_FILE = FINAL_DATA_DIR / "merge_provider_patch_report.txt"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_empty(value):
    return value in (None, "", [], {})


def main():
    ensure_directories()

    base_payload = load_json(BASE_FILE)
    patch_payload = load_json(PATCH_FILE)

    base_records = base_payload.get("records")
    patch_records = patch_payload.get("records")

    if not isinstance(base_records, list):
        raise ValueError("Base dataset must contain 'records'")

    if not isinstance(patch_records, list):
        raise ValueError("Patch dataset must contain 'records'")

    patch_by_id = {
        record.get("model_id"): record
        for record in patch_records
        if record.get("model_id")
    }

    merged_records = []

    matched_models = 0
    fields_added = 0

    for base_record in base_records:

        model_id = base_record.get("model_id")
        patch_record = patch_by_id.get(model_id)

        merged = dict(base_record)

        if patch_record is not None:
            matched_models += 1

            for field, value in patch_record.items():

                if field == "model_id":
                    continue

                if is_empty(value):
                    continue

                # Never overwrite existing verified evidence.
                if is_empty(merged.get(field)):
                    merged[field] = value
                    fields_added += 1

        merged_records.append(merged)

    output = {
        "metadata": {
            **(base_payload.get("metadata") or {}),
            "dataset_name": (
                "AIOrbit Models Final Provider Verified Dataset"
            ),
            "source_files": [
                BASE_FILE.name,
                PATCH_FILE.name,
            ],
            "merge_stats": {
                "base_records": len(base_records),
                "patch_records": len(patch_records),
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

    report = [
        "AIOrbit Models - Provider Patch Merge",
        f"Base records: {len(base_records)}",
        f"Patch records: {len(patch_records)}",
        f"Matched models: {matched_models}",
        f"Fields added: {fields_added}",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print(f"Base records: {len(base_records)}")
    print(f"Patch records: {len(patch_records)}")
    print(f"Matched models: {matched_models}")
    print(f"Fields added: {fields_added}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()