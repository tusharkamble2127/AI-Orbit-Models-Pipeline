from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories

INPUT_FILE = FINAL_DATA_DIR / "models_final_normalized.json"
REPORT_FILE = FINAL_DATA_DIR / "enrichment_schema_inspection.txt"
JSON_FILE = FINAL_DATA_DIR / "enrichment_schema_inspection.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def compact(value: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = repr(value)

    if len(text) > limit:
        return text[:limit] + "..."
    return text


def describe(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": type(value).__name__,
        "empty": value in (None, "", [], {}),
    }

    if isinstance(value, dict):
        result["keys"] = list(value.keys())
    elif isinstance(value, list):
        result["length"] = len(value)
        if value:
            result["first_item_type"] = type(value[0]).__name__

    return result


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected 'records' list in models_final_normalized.json")

    lines = [
        "AIOrbit Models - Official Enrichment Schema Inspection",
        f"Records: {len(records)}",
        "",
    ]

    enrichment_shape_counts: dict[str, int] = {}
    selected_url_records = []
    populated_enrichment_records = []

    for record in records:
        model = record.get("model_name") or record.get("model_id")
        enrichment = record.get("official_enrichment")

        shape = describe(enrichment)
        shape_key = json.dumps(shape, sort_keys=True, ensure_ascii=False)
        enrichment_shape_counts[shape_key] = enrichment_shape_counts.get(shape_key, 0) + 1

        if enrichment not in (None, "", [], {}):
            populated_enrichment_records.append({
                "model_name": model,
                "shape": shape,
                "preview": compact(enrichment),
            })

        if isinstance(enrichment, dict):
            selected = (
                enrichment.get("selected_official_url")
                or enrichment.get("selected_official")
                or enrichment.get("official_url")
                or enrichment.get("official_website")
            )

            if selected:
                selected_url_records.append({
                    "model_name": model,
                    "selected_url": selected,
                    "keys": list(enrichment.keys()),
                    "preview": compact(enrichment),
                })

    lines.extend([
        "TOP-LEVEL ENRICHMENT SHAPE COUNTS",
        "=" * 90,
    ])

    for shape, count in sorted(
        enrichment_shape_counts.items(),
        key=lambda x: (-x[1], x[0]),
    ):
        lines.append(f"{count:>3} records | {shape}")

    lines.extend([
        "",
        f"Records with non-empty official_enrichment: {len(populated_enrichment_records)}",
        f"Records with obvious selected official URL field: {len(selected_url_records)}",
        "",
        "SELECTED OFFICIAL URL CANDIDATES",
        "=" * 90,
    ])

    if selected_url_records:
        for item in selected_url_records:
            lines.append(
                f"{item['model_name']} | URL={item['selected_url']} | "
                f"keys={', '.join(item['keys'])}"
            )
            lines.append(f"  {item['preview']}")
    else:
        lines.append("No obvious selected official URL was found using known field names.")

    lines.extend([
        "",
        "NON-EMPTY ENRICHMENT RECORDS",
        "=" * 90,
    ])

    for item in populated_enrichment_records:
        lines.append(
            f"{item['model_name']} | {json.dumps(item['shape'], ensure_ascii=False)}"
        )
        lines.append(f"  {item['preview']}")

    report = {
        "record_count": len(records),
        "enrichment_shape_counts": enrichment_shape_counts,
        "non_empty_records": populated_enrichment_records,
        "selected_official_url_candidates": selected_url_records,
    }

    with REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with JSON_FILE.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"Records inspected: {len(records)}")
    print(f"Non-empty enrichment records: {len(populated_enrichment_records)}")
    print(f"Selected official URL candidates: {len(selected_url_records)}")
    print(f"Text report: {REPORT_FILE}")
    print(f"JSON report: {JSON_FILE}")


if __name__ == "__main__":
    main()
