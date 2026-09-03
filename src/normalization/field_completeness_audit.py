from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories

INPUT_FILE = FINAL_DATA_DIR / "models_final_normalized.json"
JSON_OUTPUT = FINAL_DATA_DIR / "completeness_report.json"
TEXT_OUTPUT = FINAL_DATA_DIR / "completeness_report.txt"

TRACK_FIELDS = [
    "model_id", "model_name", "model_family", "company_provider",
    "official_website", "release_date", "last_updated", "model_type_task",
    "description", "modalities", "context_window", "maximum_output",
    "reasoning", "function_tool_calling", "structured_output", "vision",
    "audio", "multimodal", "embeddings", "api_platforms",
    "open_source_weights", "license", "huggingface", "github",
    "documentation", "pricing", "benchmarks", "adoption_downloads",
    "quality_score", "quality_band", "last_verified", "source_urls",
    "identity_verification", "curation_status", "variant_review",
]

PRIORITY_FIELDS = {
    "official_website", "company_provider", "license", "pricing",
    "benchmarks", "adoption_downloads", "huggingface", "github",
    "documentation", "api_platforms", "last_verified",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def quality_label(coverage: float) -> str:
    if coverage >= 95:
        return "excellent"
    if coverage >= 80:
        return "good"
    if coverage >= 60:
        return "partial"
    return "low"


def main() -> None:
    ensure_directories()
    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected 'records' list in models_final_normalized.json")

    total = len(records)
    field_statistics = []

    for field in TRACK_FIELDS:
        missing_models = [
            (r.get("model_name") or r.get("model_id"))
            for r in records
            if is_missing(r.get(field))
        ]
        present = total - len(missing_models)
        coverage = (present / total * 100) if total else 0.0

        field_statistics.append({
            "field": field,
            "present": present,
            "missing": len(missing_models),
            "coverage_percent": round(coverage, 2),
            "quality": quality_label(coverage),
            "missing_models": missing_models,
        })

    record_statistics = []
    for r in records:
        missing_fields = [f for f in TRACK_FIELDS if is_missing(r.get(f))]
        record_statistics.append({
            "model_id": r.get("model_id"),
            "model_name": r.get("model_name"),
            "missing_field_count": len(missing_fields),
            "missing_fields": missing_fields,
        })

    field_statistics.sort(key=lambda x: (x["coverage_percent"], x["field"]))
    record_statistics.sort(
        key=lambda x: (-x["missing_field_count"], x["model_name"] or "")
    )

    report = {
        "metadata": {
            "dataset": INPUT_FILE.name,
            "record_count": total,
            "tracked_field_count": len(TRACK_FIELDS),
            "thresholds": {
                "excellent": ">=95%",
                "good": "80-94.99%",
                "partial": "60-79.99%",
                "low": "<60%",
            },
        },
        "field_statistics": field_statistics,
        "record_statistics": record_statistics,
        "summary": {
            "fields_excellent": sum(
                x["quality"] == "excellent" for x in field_statistics
            ),
            "fields_good": sum(
                x["quality"] == "good" for x in field_statistics
            ),
            "fields_partial": sum(
                x["quality"] == "partial" for x in field_statistics
            ),
            "fields_low": sum(
                x["quality"] == "low" for x in field_statistics
            ),
            "priority_fields": [
                x for x in field_statistics if x["field"] in PRIORITY_FIELDS
            ],
        },
    }

    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Field Completeness Audit",
        f"Records: {total}",
        f"Tracked fields: {len(TRACK_FIELDS)}",
        "",
        "FIELD COVERAGE",
        "=" * 90,
    ]

    for x in field_statistics:
        lines.append(
            f"{x['field']:<25} {x['present']:>3}/{total:<3} "
            f"{x['coverage_percent']:>6.2f}%  {x['quality']}"
        )

    lines += ["", "MOST INCOMPLETE RECORDS", "=" * 90]
    for x in record_statistics[:15]:
        lines.append(
            f"{x['model_name']} | missing={x['missing_field_count']} | "
            f"{', '.join(x['missing_fields'])}"
        )

    lines += ["", "PRIORITY ENRICHMENT FIELDS", "=" * 90]
    for x in field_statistics:
        if x["field"] in PRIORITY_FIELDS:
            lines.append(
                f"{x['field']:<25} {x['present']:>3}/{total:<3} "
                f"{x['coverage_percent']:>6.2f}%  missing={x['missing']}"
            )

    TEXT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Records audited: {total}")
    print(f"Fields audited: {len(TRACK_FIELDS)}")
    print(f"JSON report: {JSON_OUTPUT}")
    print(f"Text report: {TEXT_OUTPUT}")


if __name__ == "__main__":
    main()
