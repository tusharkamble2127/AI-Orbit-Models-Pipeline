from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_applicability_enriched.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_verified_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "verified_field_enrichment_report.txt"


# Conservative first-party evidence patches.
# Only facts supported by current official provider documentation are added.
PATCHES: dict[str, dict[str, Any]] = {

    # -------------------------
    # OPENAI
    # -------------------------

    "openai/gpt-oss-20b": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-oss-20b",
        "license": "Apache 2.0",
        "embeddings": False,
    },

    "openai/gpt-oss-120b": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-oss-120b",
        "license": "Apache 2.0",
        "embeddings": False,
    },

    "openai/gpt-5": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5",
        "embeddings": False,
    },

    "openai/gpt-5.4": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.4",
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.50,
            "output_per_1m_tokens": 15.00,
        },
        "structured_output": True,
    },

    "openai/gpt-5.4-pro": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.4-pro",
        "embeddings": False,
    },

    "openai/gpt-5.5": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.5",
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.00,
            "output_per_1m_tokens": 30.00,
        },
        "structured_output": True,
    },

    "openai/gpt-5.5-pro": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.5-pro",
        "embeddings": False,
    },

    "openai/gpt-5.3-codex": {
        "official_website": "https://developers.openai.com/api/docs/models/gpt-5.3-codex",
        "embeddings": False,
    },

    "openai/o4-mini": {
        "official_website": "https://developers.openai.com/api/docs/models/o4-mini",
        "embeddings": False,
    },

    # -------------------------
    # ANTHROPIC
    # -------------------------

    "anthropic/claude-fable-5": {
        "official_website": (
            "https://platform.claude.com/docs/en/models/"
            "fable-5/introducing-claude-fable-5-and-claude-mythos-5"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 10.00,
            "output_per_1m_tokens": 50.00,
        },
    },

    "anthropic/claude-opus-5": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.00,
            "output_per_1m_tokens": 25.00,
        },
    },

    "anthropic/claude-opus-4-8": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.00,
            "output_per_1m_tokens": 25.00,
        },
    },

    "anthropic/claude-opus-4-7": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.00,
            "output_per_1m_tokens": 25.00,
        },
    },

    "anthropic/claude-opus-4-6": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 5.00,
            "output_per_1m_tokens": 25.00,
        },
    },

    "anthropic/claude-sonnet-5": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.00,
            "output_per_1m_tokens": 10.00,
        },
    },

    "anthropic/claude-sonnet-4-6": {
        "official_website": (
            "https://platform.claude.com/docs/en/"
            "about-claude/pricing"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 3.00,
            "output_per_1m_tokens": 15.00,
        },
    },

    # -------------------------
    # GOOGLE GEMINI
    # -------------------------

    "google/gemini-3.6-flash": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-3.5-flash": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-3.5-flash-lite": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-3.1-pro-preview": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-3-flash-preview": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-2.5-pro": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    "google/gemini-2.5-flash-lite": {
        "official_website": (
            "https://ai.google.dev/gemini-api/docs/models"
        ),
        "embeddings": False,
        "structured_output": True,
    },

    # -------------------------
    # XAI
    # -------------------------

    "xai/grok-4.5": {
        "official_website": (
            "https://docs.x.ai/developers/models/grok-4.5"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 2.00,
            "output_per_1m_tokens": 6.00,
        },
        "structured_output": True,
    },

    "xai/grok-4.3": {
        "official_website": (
            "https://docs.x.ai/developers/models/grok-4.3"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.25,
            "output_per_1m_tokens": 2.50,
        },
        "structured_output": True,
    },

    # -------------------------
    # DEEPSEEK
    # -------------------------

    "deepseek/deepseek-v4-flash": {
        "official_website": (
            "https://api-docs.deepseek.com/quick_start/pricing/"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_cache_hit_offpeak_per_1m_tokens": 0.007,
            "input_cache_hit_peak_per_1m_tokens": 0.014,
            "input_cache_miss_offpeak_per_1m_tokens": 0.22,
            "input_cache_miss_peak_per_1m_tokens": 0.44,
            "output_offpeak_per_1m_tokens": 0.66,
            "output_peak_per_1m_tokens": 1.32,
        },
        "structured_output": True,
    },

    "deepseek/deepseek-v4-pro": {
        "official_website": (
            "https://api-docs.deepseek.com/quick_start/pricing/"
        ),
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "input_cache_hit_offpeak_per_1m_tokens": 0.022,
            "input_cache_hit_peak_per_1m_tokens": 0.044,
            "input_cache_miss_offpeak_per_1m_tokens": 0.66,
            "input_cache_miss_peak_per_1m_tokens": 1.32,
            "output_offpeak_per_1m_tokens": 1.98,
            "output_peak_per_1m_tokens": 3.96,
        },
        "structured_output": True,
    },
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def merge_patch(record: dict, patch: dict) -> int:
    fields_written = 0

    for field, value in patch.items():

        if is_empty(value):
            continue

        # Never overwrite existing verified information.
        if is_empty(record.get(field)):
            record[field] = value
            fields_written += 1

    # Always preserve official URL as a source.
    official = patch.get("official_website")

    if (
        isinstance(official, str)
        and official
    ):
        sources = record.setdefault(
            "source_urls",
            [],
        )

        if isinstance(sources, list) and official not in sources:
            sources.append(official)

    return fields_written


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in "
            "models_applicability_enriched.json"
        )

    matched = 0
    fields_written = 0

    for record in records:

        model_id = str(
            record.get("model_id") or ""
        )

        patch = PATCHES.get(model_id)

        if patch is None:
            continue

        matched += 1

        fields_written += merge_patch(
            record,
            patch,
        )

    output = {
        "metadata": {
            **(
                payload.get("metadata")
                or {}
            ),
            "dataset_name": (
                "AIOrbit Models Verified "
                "Field Enriched Dataset"
            ),
            "verified_patch_models": matched,
            "verified_fields_written": (
                fields_written
            ),
            "source_policy": (
                "First-party provider documentation "
                "only. Existing values are not overwritten."
            ),
        },
        "records": records,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            indent=2,
            ensure_ascii=False,
        )

    lines = [
        "AIOrbit Models - Verified Field Enrichment",
        f"Input records: {len(records)}",
        f"Matched verified models: {matched}",
        f"Fields written: {fields_written}",
        "",
        "MODELS UPDATED",
        "=" * 90,
    ]

    for model_id in PATCHES:

        if any(
            r.get("model_id") == model_id
            for r in records
        ):
            lines.append(model_id)

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"Input records: {len(records)}"
    )

    print(
        f"Matched verified models: {matched}"
    )

    print(
        f"Fields written: {fields_written}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Report: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()