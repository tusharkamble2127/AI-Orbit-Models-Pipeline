from __future__ import annotations

import json
from pathlib import Path

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_evidence_patched.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_final_candidate.json"
REPORT_FILE = FINAL_DATA_DIR / "final_dataset_merge_report.txt"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ensure_directories()

    payload = load_json(INPUT_FILE)

    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_evidence_patched.json"
        )

    # Preserve the complete enriched record structure.
    final_records = []

    for record in records:
        item = dict(record)

        # Mark this as the frozen candidate layer.
        item["dataset_status"] = "final_candidate"

        final_records.append(item)

    # ---------------------------------------------------------
    # Basic validation
    # ---------------------------------------------------------

    model_ids = [
        r.get("model_id")
        for r in final_records
    ]

    duplicate_ids = sorted(
        {
            model_id
            for model_id in model_ids
            if model_id
            and model_ids.count(model_id) > 1
        }
    )

    empty_model_names = [
        r.get("model_id")
        for r in final_records
        if not r.get("model_name")
    ]

    empty_descriptions = [
        r.get("model_id")
        for r in final_records
        if not r.get("description")
    ]

    empty_quality_scores = [
        r.get("model_id")
        for r in final_records
        if r.get("quality_score") is None
    ]

    validation = {
        "record_count": len(final_records),
        "duplicate_model_ids": duplicate_ids,
        "empty_model_names": empty_model_names,
        "empty_descriptions": empty_descriptions,
        "empty_quality_scores": empty_quality_scores,
        "valid": (
            len(duplicate_ids) == 0
            and len(empty_model_names) == 0
            and len(empty_descriptions) == 0
            and len(empty_quality_scores) == 0
        ),
    }

    output = {
        "metadata": {
            **(
                payload.get("metadata")
                or {}
            ),
            "dataset_name":
                "AIOrbit Models Final Candidate Dataset",
            "dataset_stage":
                "frozen_before_description_generation",
            "validation":
                validation,
        },
        "records": final_records,
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
        "AIOrbit Models - Final Candidate Dataset",
        f"Records: {len(final_records)}",
        f"Duplicate model IDs: {len(duplicate_ids)}",
        f"Missing model names: {len(empty_model_names)}",
        f"Missing descriptions: {len(empty_descriptions)}",
        f"Missing quality scores: {len(empty_quality_scores)}",
        f"Dataset valid: {validation['valid']}",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(
        f"Records: {len(final_records)}"
    )

    print(
        f"Duplicate model IDs: "
        f"{len(duplicate_ids)}"
    )

    print(
        f"Missing model names: "
        f"{len(empty_model_names)}"
    )

    print(
        f"Missing descriptions: "
        f"{len(empty_descriptions)}"
    )

    print(
        f"Missing quality scores: "
        f"{len(empty_quality_scores)}"
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