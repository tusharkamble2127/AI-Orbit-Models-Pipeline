from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories

INPUT_FILE = FINAL_DATA_DIR / "models_final_verified.json"
JSON_OUTPUT = FINAL_DATA_DIR / "final_enrichment_queue.json"
TEXT_OUTPUT = FINAL_DATA_DIR / "final_enrichment_queue.txt"

TARGET_FIELDS = [
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


def main() -> None:
    ensure_directories()
    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected 'records' list")

    field_stats = {}
    queue = []

    for field in TARGET_FIELDS:
        missing = []
        for record in records:
            if is_missing(record.get(field)):
                missing.append({
                    "model_id": record.get("model_id"),
                    "model_name": record.get("model_name"),
                    "provider": record.get("company_provider"),
                })

        present = len(records) - len(missing)
        field_stats[field] = {
            "present": present,
            "missing": len(missing),
            "coverage_percent": round(
                present / len(records) * 100, 2
            ),
            "missing_models": missing,
        }

    for record in records:
        missing_fields = [
            field
            for field in TARGET_FIELDS
            if is_missing(record.get(field))
        ]

        if missing_fields:
            queue.append({
                "model_id": record.get("model_id"),
                "model_name": record.get("model_name"),
                "provider": record.get("company_provider"),
                "missing_fields": missing_fields,
                "priority_count": len(missing_fields),
            })

    queue.sort(
        key=lambda x: (
            -x["priority_count"],
            x["provider"] or "",
            x["model_name"] or "",
        )
    )

    output = {
        "dataset": INPUT_FILE.name,
        "record_count": len(records),
        "target_fields": TARGET_FIELDS,
        "field_statistics": field_stats,
        "record_queue": queue,
    }

    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Final Enrichment Queue",
        f"Records: {len(records)}",
        "",
        "FIELD COVERAGE",
        "=" * 100,
    ]

    for field, stats in sorted(
        field_stats.items(),
        key=lambda item: (item[1]["coverage_percent"], item[0]),
    ):
        lines.append(
            f"{field:<25} "
            f"{stats['present']:>2}/{len(records):<2} "
            f"{stats['coverage_percent']:>6.2f}% "
            f"missing={stats['missing']}"
        )

    lines += [
        "",
        "RECORD QUEUE",
        "=" * 100,
    ]

    for item in queue:
        lines.append(
            f"{item['model_name']} | {item['model_id']} | "
            f"missing={item['priority_count']} | "
            f"{', '.join(item['missing_fields'])}"
        )

    TEXT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Records: {len(records)}")
    print(f"Queued records: {len(queue)}")
    print(f"JSON: {JSON_OUTPUT}")
    print(f"Text: {TEXT_OUTPUT}")


if __name__ == "__main__":
    main()
