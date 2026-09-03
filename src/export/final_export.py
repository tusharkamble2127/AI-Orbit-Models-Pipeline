from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_validated.json"

CSV_OUTPUT = FINAL_DATA_DIR / "models_final.csv"
JSON_OUTPUT = FINAL_DATA_DIR / "models_final_public.json"
REPORT_OUTPUT = FINAL_DATA_DIR / "final_export_report.txt"


PUBLIC_FIELDS = [
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
]


FIELD_LABELS = {
    "model_name": "Model Name",
    "model_family": "Model Family",
    "company_provider": "Company / Provider",
    "official_website": "Official Website",
    "release_date": "Release Date",
    "last_updated": "Last Updated",
    "model_type_task": "Model Type / Task",
    "description": "Description",
    "modalities": "Modalities",
    "context_window": "Context Window",
    "maximum_output": "Maximum Output",
    "reasoning": "Reasoning",
    "function_tool_calling": "Function / Tool Calling",
    "structured_output": "Structured Output",
    "vision": "Vision",
    "audio": "Audio",
    "multimodal": "Multimodal",
    "embeddings": "Embeddings",
    "api_platforms": "API / Platforms",
    "open_source_weights": "Open Source / Weights",
    "license": "License",
    "huggingface": "Hugging Face",
    "github": "GitHub",
    "documentation": "Documentation",
    "pricing": "Pricing",
    "benchmarks": "Benchmarks",
    "adoption_downloads": "Adoption / Downloads",
    "quality_score": "Quality Score",
    "quality_band": "Quality Band",
    "last_verified": "Last Verified",
    "source_urls": "Source URLs",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def serialize_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, list):
        return "; ".join(
            serialize_value(item)
            for item in value
            if item not in (None, "", [], {})
        )

    if isinstance(value, dict):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ": "),
        )

    return str(value)


def build_public_record(record: dict) -> dict:
    public = {}

    for field in PUBLIC_FIELDS:
        public[FIELD_LABELS[field]] = serialize_value(
            record.get(field)
        )

    return public


def validate_public_records(records: list[dict]) -> dict:
    expected = {
        FIELD_LABELS[field]
        for field in PUBLIC_FIELDS
    }

    errors = []

    for index, record in enumerate(records):
        keys = set(record.keys())

        missing = sorted(expected - keys)
        extra = sorted(keys - expected)

        if missing or extra:
            errors.append(
                {
                    "index": index,
                    "missing": missing,
                    "extra": extra,
                }
            )

    model_names = [
        record.get("Model Name")
        for record in records
    ]

    duplicate_names = sorted(
        {
            name
            for name in model_names
            if name
            and model_names.count(name) > 1
        }
    )

    return {
        "record_count": len(records),
        "column_count": len(expected),
        "schema_errors": errors,
        "duplicate_model_names": duplicate_names,
        "valid": (
            not errors
            and not duplicate_names
        ),
    }


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)

    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_validated.json"
        )

    public_records = [
        build_public_record(record)
        for record in records
    ]

    validation = validate_public_records(
        public_records
    )

    # ---------------------------------------------------------
    # CSV
    # ---------------------------------------------------------

    csv_fields = [
        FIELD_LABELS[field]
        for field in PUBLIC_FIELDS
    ]

    with CSV_OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=csv_fields,
            extrasaction="ignore",
        )

        writer.writeheader()

        for record in public_records:
            writer.writerow(record)

    # ---------------------------------------------------------
    # Public JSON
    # ---------------------------------------------------------

    public_payload = {
        "metadata": {
            "dataset_name":
                "AIOrbit Models Public Dataset",
            "record_count": len(public_records),
            "column_count": len(csv_fields),
            "source_file": INPUT_FILE.name,
            "internal_audit_fields_removed": True,
            "validation": validation,
        },
        "records": public_records,
    }

    with JSON_OUTPUT.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            public_payload,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    report_lines = [
        "AIOrbit Models - Final Export Report",
        f"Input records: {len(records)}",
        f"CSV records: {len(public_records)}",
        f"CSV columns: {len(csv_fields)}",
        f"Duplicate public model names: "
        f"{len(validation['duplicate_model_names'])}",
        f"Schema valid: {validation['valid']}",
        "",
        "OUTPUT FILES",
        "=" * 90,
        str(CSV_OUTPUT),
        str(JSON_OUTPUT),
        "",
        "PUBLIC COLUMNS",
        "=" * 90,
    ]

    report_lines.extend(
        csv_fields
    )

    REPORT_OUTPUT.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(
        f"Input records: {len(records)}"
    )

    print(
        f"CSV records: {len(public_records)}"
    )

    print(
        f"CSV columns: {len(csv_fields)}"
    )

    print(
        f"Schema valid: {validation['valid']}"
    )

    print(
        f"CSV output: {CSV_OUTPUT}"
    )

    print(
        f"Public JSON output: {JSON_OUTPUT}"
    )

    print(
        f"Report: {REPORT_OUTPUT}"
    )


if __name__ == "__main__":
    main()