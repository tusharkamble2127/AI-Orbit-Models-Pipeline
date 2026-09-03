from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories

INPUT_FILE = FINAL_DATA_DIR / "models_final_enriched.json"
JSON_OUTPUT = FINAL_DATA_DIR / "final_enriched_completeness_report.json"
TEXT_OUTPUT = FINAL_DATA_DIR / "final_enriched_completeness_report.txt"

FIELDS = [
    "model_id",
    "model_name",
    "model_family",
    "company_provider",
    "official_website",
    "release_date",
    "last_updated",
    "model_type_task",
    "description",
    "modalities",
    "context_window",
    "maximum_output",
    "reasoning",
    "function_tool_calling",
    "structured_output",
    "vision",
    "audio",
    "multimodal",
    "embeddings",
    "api_platforms",
    "open_source_weights",
    "license",
    "huggingface",
    "github",
    "documentation",
    "pricing",
    "benchmarks",
    "adoption_downloads",
    "quality_score",
    "quality_band",
    "last_verified",
    "source_urls",
    "identity_verification",
    "curation_status",
    "variant_review",
]


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected 'records' list")

    total = len(records)
    stats = []

    for field in FIELDS:
        missing_models = [
            r.get("model_name") or r.get("model_id")
            for r in records
            if is_missing(r.get(field))
        ]
        present = total - len(missing_models)
        coverage = (present / total * 100) if total else 0

        stats.append({
            "field": field,
            "present": present,
            "missing": len(missing_models),
            "coverage_percent": round(coverage, 2),
            "missing_models": missing_models,
        })

    stats.sort(key=lambda x: (x["coverage_percent"], x["field"]))

    priority = {
        "official_website",
        "pricing",
        "license",
        "embeddings",
        "huggingface",
        "github",
        "benchmarks",
        "adoption_downloads",
    }

    report = {
        "dataset": INPUT_FILE.name,
        "record_count": total,
        "field_count": len(FIELDS),
        "field_statistics": stats,
        "priority_fields": [
            x for x in stats if x["field"] in priority
        ],
    }

    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Final Enriched Completeness Audit",
        f"Records: {total}",
        f"Fields: {len(FIELDS)}",
        "",
        "FIELD COVERAGE",
        "=" * 90,
    ]

    for x in stats:
        lines.append(
            f"{x['field']:<25} "
            f"{x['present']:>3}/{total:<3} "
            f"{x['coverage_percent']:>6.2f}% "
            f"missing={x['missing']}"
        )

    lines.extend([
        "",
        "PRIORITY FIELDS",
        "=" * 90,
    ])

    for x in stats:
        if x["field"] in priority:
            lines.append(
                f"{x['field']:<25} "
                f"{x['present']:>3}/{total:<3} "
                f"{x['coverage_percent']:>6.2f}% "
                f"missing={x['missing']}"
            )

    lines.extend([
        "",
        "FIELDS STILL NEEDING ENRICHMENT",
        "=" * 90,
    ])

    for x in stats:
        if x["missing"] > 0:
            lines.append(
                f"{x['field']}: {x['missing']} missing"
            )

    TEXT_OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Records: {total}")
    print(f"Fields: {len(FIELDS)}")
    print(f"JSON report: {JSON_OUTPUT}")
    print(f"Text report: {TEXT_OUTPUT}")


if __name__ == "__main__":
    main()
