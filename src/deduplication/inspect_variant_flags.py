from __future__ import annotations

import json
from pathlib import Path
from itertools import combinations

from src.config import FINAL_DATA_DIR, ensure_directories
from src.deduplication.model_variant_resolution import score_pair, model_id


INPUT_FILE = FINAL_DATA_DIR / "models_variant_resolution.json"
OUTPUT_FILE = FINAL_DATA_DIR / "variant_flagged_pairs.json"
TEXT_REPORT = FINAL_DATA_DIR / "variant_flagged_pairs.txt"

PRIORITY = {
    "EXACT_DUPLICATE": 0,
    "LIKELY_VARIANT": 1,
    "POSSIBLE_VARIANT": 2,
    "POSSIBLE_SIMILARITY": 3,
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def score(r: dict) -> float:
    try:
        return float(r.get("quality_score", 0))
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    ensure_directories()

    records = load_json(INPUT_FILE)
    if not isinstance(records, list):
        raise ValueError("Expected a JSON list in models_variant_resolution.json")

    flagged = []

    for a, b in combinations(records, 2):
        result = score_pair(a, b)

        if result["classification"] == "DISTINCT":
            continue

        result["quality_score_a"] = score(a)
        result["quality_score_b"] = score(b)

        result["hf_urls_a"] = [
            x.get("url")
            for x in (a.get("weights") or [])
            if isinstance(x, dict)
            and x.get("url")
            and "huggingface.co" in str(x.get("url")).lower()
        ]

        result["hf_urls_b"] = [
            x.get("url")
            for x in (b.get("weights") or [])
            if isinstance(x, dict)
            and x.get("url")
            and "huggingface.co" in str(x.get("url")).lower()
        ]

        flagged.append(result)

    flagged.sort(
        key=lambda x: (
            PRIORITY.get(x["classification"], 99),
            -x["name_ratio"],
            -int(x["same_family"]),
        )
    )

    summary = {
        "input_records": len(records),
        "flagged_pairs": len(flagged),
        "flagged_records": len(
            {x for p in flagged for x in (p["model_id_a"], p["model_id_b"])}
        ),
        "classification_counts": {},
        "note": "Audit report only. No merge/delete decision is made automatically.",
        "pairs": flagged,
    }

    for pair in flagged:
        c = pair["classification"]
        summary["classification_counts"][c] = (
            summary["classification_counts"].get(c, 0) + 1
        )

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Variant Flag Inspection",
        f"Input records: {len(records)}",
        f"Flagged pairs: {len(flagged)}",
        f"Flagged records: {summary['flagged_records']}",
        "",
    ]

    for i, p in enumerate(flagged, 1):
        lines.append(f"[{i}] {p['classification']}")
        lines.append(
            f"A: {p['model_name_a']} | id={p['model_id_a']} | "
            f"family={next((r.get('model_family') for r in records if model_id(r) == p['model_id_a']), '-') or '-'} | "
            f"quality={p['quality_score_a']:.0f}"
        )
        lines.append(
            f"B: {p['model_name_b']} | id={p['model_id_b']} | "
            f"family={next((r.get('model_family') for r in records if model_id(r) == p['model_id_b']), '-') or '-'} | "
            f"quality={p['quality_score_b']:.0f}"
        )
        lines.append(
            f"Similarity: name={p['name_ratio']:.1f}, "
            f"token={p['name_token_ratio']:.1f}, "
            f"stem={p['name_stem_ratio']:.1f}, "
            f"same_family={p['same_family']}"
        )
        lines.append(f"Signals: {', '.join(p['signals']) or '-'}")
        lines.append(
            f"Shared source URLs: {', '.join(p['shared_source_urls']) or '-'}"
        )
        lines.append(
            f"Shared GitHub repos: {', '.join(p['shared_github_repos']) or '-'}"
        )
        lines.append(f"HF A: {', '.join(p['hf_urls_a']) or '-'}")
        lines.append(f"HF B: {', '.join(p['hf_urls_b']) or '-'}")
        lines.append("-" * 100)

    TEXT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"Input records: {len(records)}")
    print(f"Flagged pairs: {len(flagged)}")
    print(f"Flagged records: {summary['flagged_records']}")
    print(f"Classification counts: {summary['classification_counts']}")
    print(f"JSON report: {OUTPUT_FILE}")
    print(f"Text report: {TEXT_REPORT}")


if __name__ == "__main__":
    main()
