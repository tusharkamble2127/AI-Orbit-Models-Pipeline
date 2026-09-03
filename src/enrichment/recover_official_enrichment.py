from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories

ENRICHED_FILE = FINAL_DATA_DIR / "models_official_enriched.json"
CANONICAL_FILE = FINAL_DATA_DIR / "models_canonical.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_canonical_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "official_enrichment_recovery_report.txt"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def records_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return payload["records"]
    raise ValueError("Could not find a records list in input JSON")


def model_id(record: dict) -> str:
    return str(record.get("model_id") or "").strip()


def main() -> None:
    ensure_directories()

    enriched_payload = load_json(ENRICHED_FILE)
    canonical_payload = load_json(CANONICAL_FILE)

    enriched_records = records_from_payload(enriched_payload)
    canonical_records = records_from_payload(canonical_payload)

    enriched_by_id = {
        model_id(r): r
        for r in enriched_records
        if model_id(r)
    }

    matched = 0
    missing = []
    nonempty = 0

    output_records = []

    for record in canonical_records:
        item = dict(record)
        mid = model_id(record)
        source = enriched_by_id.get(mid)

        if source is None:
            missing.append(mid or record.get("model_name"))
            output_records.append(item)
            continue

        enrichment = source.get("official_enrichment")

        # Preserve the full enrichment object exactly as produced by the
        # enrichment stage. Do not rewrite or fabricate its contents.
        item["official_enrichment"] = enrichment

        if enrichment not in (None, "", [], {}):
            nonempty += 1

        matched += 1
        output_records.append(item)

    if isinstance(canonical_payload, dict):
        output_payload = dict(canonical_payload)
        output_payload["records"] = output_records
    else:
        output_payload = {
            "metadata": {
                "dataset_name": "AIOrbit Models Canonical Candidate Dataset",
                "recovered_from": ENRICHED_FILE.name,
            },
            "records": output_records,
        }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Official Enrichment Recovery",
        f"Enriched source records: {len(enriched_records)}",
        f"Canonical records: {len(canonical_records)}",
        f"Model-ID matches: {matched}",
        f"Non-empty enrichment recovered: {nonempty}",
        f"Canonical records without enrichment source match: {len(missing)}",
        "",
        "UNMATCHED RECORDS",
        "=" * 90,
    ]

    if missing:
        lines.extend(str(x) for x in missing)
    else:
        lines.append("None")

    lines.extend([
        "",
        "OUTPUT",
        "=" * 90,
        str(OUTPUT_FILE),
        "",
        "IMPORTANT",
        "This step only carries forward previously collected enrichment.",
        "It does not scrape new sources or invent missing values.",
    ])

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")

    print(f"Enriched source records: {len(enriched_records)}")
    print(f"Canonical records: {len(canonical_records)}")
    print(f"Model-ID matches: {matched}")
    print(f"Non-empty enrichment recovered: {nonempty}")
    print(f"Unmatched canonical records: {len(missing)}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
