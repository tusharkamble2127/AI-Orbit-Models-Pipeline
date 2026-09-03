from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_normalized.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_target_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "targeted_enrichment_report.txt"


# First-party sources verified during the current enrichment pass.
# Only facts directly supported by those sources are populated.
PATCH: dict[str, dict[str, Any]] = {
    "openai/gpt-oss-20b": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-oss-20b",
        "license": "Apache 2.0",
    },
    "openai/gpt-oss-120b": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-oss-120b",
        "license": "Apache 2.0",
    },
    "openai/gpt-5": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.25,
            "output_per_1m_tokens": 10.0,
        },
        "embeddings": False,
    },
    "openai/gpt-5.4": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.4",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.50,
            "output_per_1m_tokens": 15.0,
        },
        "embeddings": False,
    },
    "openai/gpt-5.4-pro": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.4-pro",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 30.0,
            "output_per_1m_tokens": 180.0,
        },
        "embeddings": False,
    },
    "openai/gpt-5.5": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.5",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.0,
            "output_per_1m_tokens": 30.0,
        },
        "embeddings": False,
    },
    "openai/gpt-5.5-pro": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.5-pro",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 30.0,
            "output_per_1m_tokens": 180.0,
        },
        "embeddings": False,
    },
    "openai/gpt-5.3-codex": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.3-codex",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.75,
            "output_per_1m_tokens": 14.0,
        },
        "embeddings": False,
    },
    "openai/o4-mini": {
        "official_website": "https://developers.openai.com/api/docs/models/o4-mini",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.10,
            "output_per_1m_tokens": 4.40,
        },
        "embeddings": False,
    },
    "anthropic/claude-fable-5": {
        "official_website": "https://platform.claude.com/docs/en/models/fable-5/introducing-claude-fable-5-and-claude-mythos-5",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 10.0,
            "output_per_1m_tokens": 50.0,
        },
        "embeddings": False,
    },
    "anthropic/claude-opus-5": {
        "official_website": "https://platform.claude.com/docs/en/about-claude/pricing",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.0,
            "output_per_1m_tokens": 25.0,
        },
        "embeddings": False,
    },
    "anthropic/claude-sonnet-5": {
        "official_website": "https://www.anthropic.com/news/claude-sonnet-5",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.0,
            "output_per_1m_tokens": 10.0,
        },
        "embeddings": False,
    },
    "anthropic/claude-sonnet-4-6": {
        "official_website": "https://platform.claude.com/docs/en/models/sonnet-4-6/overview",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 3.0,
            "output_per_1m_tokens": 15.0,
        },
        "embeddings": False,
    },
    "xai/grok-4.5": {
        "official_website": "https://docs.x.ai/developers/models/grok-4.5",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.0,
            "output_per_1m_tokens": 6.0,
        },
        "embeddings": False,
    },
    "xai/grok-4.3": {
        "official_website": "https://docs.x.ai/developers/models/grok-4.3",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.25,
            "output_per_1m_tokens": 2.50,
        },
        "embeddings": False,
    },
    "thinkingmachines/inkling-small": {
        "official_website": "https://thinkingmachines.ai/model-card/inkling-small/",
        "license": "Apache 2.0",
        "embeddings": False,
    },
    "tencent/hy3-preview": {
        "official_website": "https://www.tencent.com/index.php/en-us/articles/2202320.html",
        "embeddings": False,
    },
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError("Expected 'records' list")

    matched = 0
    updated = 0

    for record in records:
        model_id = str(record.get("model_id") or "")
        patch = PATCH.get(model_id)

        if patch is None:
            continue

        matched += 1

        for field, value in patch.items():
            if value in (None, "", [], {}):
                continue

            # Keep existing evidence when the field is already populated.
            if record.get(field) in (None, "", [], {}):
                record[field] = value
                updated += 1

        sources = record.setdefault("source_urls", [])
        if isinstance(sources, list):
            official = patch.get("official_website")
            if (
                isinstance(official, str)
                and official
                and official not in sources
            ):
                sources.append(official)

    output = {
        "metadata": dict(payload.get("metadata") or {}),
        "records": records,
        "targeted_enrichment": {
            "patched_models": matched,
            "fields_written": updated,
            "source_policy": "first-party sources only; no unsupported inference",
        },
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    lines = [
        "AIOrbit Models - Targeted Official Enrichment",
        f"Input records: {len(records)}",
        f"Models matched by verified patch: {matched}",
        f"Fields written: {updated}",
        "",
        "PATCHED MODEL IDS",
        "=" * 90,
    ]

    for model_id in PATCH:
        if any(r.get("model_id") == model_id for r in records):
            lines.append(model_id)

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")

    print(f"Input records: {len(records)}")
    print(f"Models matched: {matched}")
    print(f"Fields written: {updated}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
