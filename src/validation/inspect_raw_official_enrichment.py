from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_official_enriched.json"
TEXT_OUTPUT = FINAL_DATA_DIR / "raw_official_enrichment_inspection.txt"
JSON_OUTPUT = FINAL_DATA_DIR / "raw_official_enrichment_inspection.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": list(value.keys()),
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first_item": shape(value[0]) if value else None,
        }

    if value is None:
        return {"type": "NoneType"}

    return {"type": type(value).__name__}


def preview(value: Any, limit: int = 1200) -> str:
    try:
        text = json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        text = repr(value)

    if len(text) > limit:
        return text[:limit] + "\n...TRUNCATED..."

    return text


def records_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        if isinstance(payload.get("records"), list):
            return payload["records"]

        if isinstance(payload.get("models"), list):
            return payload["models"]

    raise ValueError(
        "Could not locate records/models list in models_official_enriched.json"
    )


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = records_from_payload(payload)

    top_key_counter = Counter()
    enrichment_key_counter = Counter()

    nonempty_enrichment = 0
    sample_records = []

    for record in records:

        # Track all top-level record keys.
        top_key_counter.update(record.keys())

        enrichment = record.get("official_enrichment")

        if enrichment not in (None, "", [], {}):
            nonempty_enrichment += 1

        # Track keys inside official_enrichment.
        if isinstance(enrichment, dict):
            enrichment_key_counter.update(enrichment.keys())

        # Keep first 5 samples for inspection.
        if len(sample_records) < 5:
            sample_records.append(
                {
                    "model_id": record.get("model_id"),
                    "model_name": record.get("model_name"),
                    "record_keys": list(record.keys()),
                    "official_enrichment_shape": shape(enrichment),
                    "official_enrichment_preview": enrichment,
                }
            )

    report = {
        "record_count": len(records),
        "nonempty_official_enrichment": nonempty_enrichment,
        "top_level_key_frequency": dict(top_key_counter),
        "official_enrichment_key_frequency": dict(
            enrichment_key_counter
        ),
        "samples": sample_records,
    }

    # JSON report
    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # Text report
    lines = [
        "AIOrbit Models - RAW Official Enrichment Inspection",
        f"Records: {len(records)}",
        f"Non-empty official_enrichment field: {nonempty_enrichment}",
        "",
        "TOP-LEVEL RECORD KEYS",
        "=" * 100,
    ]

    for key, count in top_key_counter.most_common():
        lines.append(f"{count:>3} | {key}")

    lines.extend(
        [
            "",
            "OFFICIAL_ENRICHMENT KEYS",
            "=" * 100,
        ]
    )

    if enrichment_key_counter:
        for key, count in enrichment_key_counter.most_common():
            lines.append(f"{count:>3} | {key}")
    else:
        lines.append(
            "No dictionary keys found under official_enrichment."
        )

    lines.extend(
        [
            "",
            "FIRST 5 RECORD SAMPLES",
            "=" * 100,
        ]
    )

    for i, sample in enumerate(sample_records, 1):

        lines.append(
            f"[{i}] {sample['model_name']} | {sample['model_id']}"
        )

        lines.append(
            "official_enrichment shape: "
            + json.dumps(
                sample["official_enrichment_shape"],
                ensure_ascii=False,
            )
        )

        lines.append("official_enrichment preview:")

        # FIX:
        # Read the actual key that was stored above.
        lines.append(
            preview(sample["official_enrichment_preview"])
        )

        lines.append("-" * 100)

    TEXT_OUTPUT.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(f"Records: {len(records)}")
    print(
        f"Non-empty official_enrichment: "
        f"{nonempty_enrichment}"
    )
    print(f"Text report: {TEXT_OUTPUT}")
    print(f"JSON report: {JSON_OUTPUT}")


if __name__ == "__main__":
    main()