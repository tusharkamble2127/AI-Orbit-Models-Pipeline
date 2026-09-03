from __future__ import annotations

import json
from pathlib import Path

from src.config import FINAL_DATA_DIR, ensure_directories

INPUT_FILE = FINAL_DATA_DIR / "models_variant_resolution.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_canonical.json"

MANUAL_RELATIONSHIP_DECISIONS = {
    frozenset({"openai/gpt-oss-20b", "openai/gpt-oss-120b"}): "KEEP_SEPARATE",
    frozenset({"google/gemini-3.5-flash-lite", "google/gemini-2.5-flash-lite"}): "KEEP_SEPARATE",
    frozenset({"google/gemini-3.5-flash", "google/gemini-3.6-flash"}): "KEEP_SEPARATE",
    frozenset({"anthropic/claude-opus-4-8", "anthropic/claude-opus-4-6"}): "KEEP_SEPARATE",
    frozenset({"anthropic/claude-opus-4-8", "anthropic/claude-opus-4-7"}): "KEEP_SEPARATE",
    frozenset({"anthropic/claude-opus-4-6", "anthropic/claude-opus-4-7"}): "KEEP_SEPARATE",
    frozenset({"openai/gpt-5.4-pro", "openai/gpt-5.5-pro"}): "KEEP_SEPARATE",
    frozenset({"deepseek/deepseek-v4-flash-0731", "deepseek/deepseek-v4-flash"}): "KEEP_SEPARATE_REVIEW",
    frozenset({"openai/gpt-5.4", "openai/gpt-5.5"}): "KEEP_SEPARATE",
    frozenset({"openai/gpt-5.4", "openai/gpt-5"}): "KEEP_SEPARATE",
    frozenset({"openai/gpt-5.5", "openai/gpt-5"}): "KEEP_SEPARATE",
}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_model_id(record: dict) -> str:
    return str(record.get("model_id") or "")


def main() -> None:
    ensure_directories()

    records = load_json(INPUT_FILE)
    if not isinstance(records, list):
        raise ValueError("Expected a JSON list in models_variant_resolution.json")

    canonical = []

    for record in records:
        item = dict(record)

        model_id = get_model_id(record)
        vr = dict(item.get("variant_resolution") or {})

        # The current 41-record set has no confirmed exact duplicates.
        # Therefore every candidate remains one canonical record.
        vr["canonical_status"] = "CANONICAL_CANDIDATE"
        vr["canonical_action"] = "KEEP_RECORD"

        item["variant_resolution"] = vr

        # Preserve a clear audit field explaining that relationships were reviewed.
        item["canonical_audit"] = {
            "reviewed_variant_relationships": True,
            "automatic_duplicate_merges": 0,
            "manual_relationship_decisions": "KEEP_SEPARATE",
            "deepseek_v4_flash_0731_pair": (
                "KEEP_SEPARATE_REVIEW"
                if model_id == "deepseek/deepseek-v4-flash-0731"
                else None
            ),
        }

        canonical.append(item)

    dataset_meta = {
        "dataset_name": "AIOrbit Models Canonical Candidate Dataset",
        "schema_version": "1.0",
        "record_count": len(canonical),
        "automatic_duplicate_merges": 0,
        "manual_relationship_decision_count": len(MANUAL_RELATIONSHIP_DECISIONS),
        "manual_relationship_decisions": [
            {
                "model_ids": sorted(list(pair)),
                "decision": decision,
            }
            for pair, decision in sorted(
                MANUAL_RELATIONSHIP_DECISIONS.items(),
                key=lambda x: sorted(x[0]),
            )
        ],
        "note": (
            "Canonical candidate layer created after conservative variant review. "
            "No flagged relationship was merged automatically. "
            "DeepSeek V4 Flash 0731 remains a separate candidate pending stronger "
            "identity evidence."
        ),
    }

    output = {
        "metadata": dataset_meta,
        "records": canonical,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Input records: {len(records)}")
    print(f"Canonical records: {len(canonical)}")
    print("Automatic duplicate merges: 0")
    print(f"Manual relationships reviewed: {len(MANUAL_RELATIONSHIP_DECISIONS)}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
