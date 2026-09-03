from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_provider_complete.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_final_evidence_patched.json"
REPORT_FILE = FINAL_DATA_DIR / "final_evidence_patch_report.txt"


PATCHES: dict[str, dict[str, Any]] = {

    # ---------------------------------------------------------
    # GOOGLE GEMMA 4
    # ---------------------------------------------------------

    "google/gemma-4-31b-it": {
        "official_website": "https://ai.google.dev/gemma/docs/core/model_card_4",
        "license": {
            "name": "Apache 2.0",
            "source": "https://ai.google.dev/gemma/docs/core/model_card_4",
        },
        "embeddings": False,
        "structured_output": True,
        "benchmarks": {
            "source": "https://ai.google.dev/gemma/docs/core/model_card_4",
            "available": True,
        },
        "huggingface": [
            "https://huggingface.co/google/gemma-4-31B-it"
        ],
    },

    # ---------------------------------------------------------
    # GEMINI PRICING
    # ---------------------------------------------------------

    "google/gemini-2.5-pro": {
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens_le_200k": 1.25,
            "input_per_1m_tokens_gt_200k": 2.50,
            "output_per_1m_tokens_le_200k": 10.00,
            "output_per_1m_tokens_gt_200k": 15.00,
            "source": "Google Gemini API pricing",
        },
    },

    "google/gemini-3-flash-preview": {
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.50,
            "output_per_1m_tokens": 3.00,
            "source": "Google Gemini API pricing",
        },
    },

    # ---------------------------------------------------------
    # GPT-OSS
    # ---------------------------------------------------------

    "openai/gpt-oss-20b": {
        "pricing": {
            "status": "No OpenAI API pricing",
            "source": "OpenAI gpt-oss release",
        },
        "benchmarks": {
            "source": "https://openai.com/index/introducing-gpt-oss/",
            "available": True,
        },
        "license": {
            "name": "Apache 2.0",
            "source": "https://openai.com/index/introducing-gpt-oss/",
        },
    },

    "openai/gpt-oss-120b": {
        "pricing": {
            "status": "No OpenAI API pricing",
            "source": "OpenAI gpt-oss release",
        },
        "benchmarks": {
            "source": "https://openai.com/index/introducing-gpt-oss/",
            "available": True,
        },
        "license": {
            "name": "Apache 2.0",
            "source": "https://openai.com/index/introducing-gpt-oss/",
        },
    },

    # ---------------------------------------------------------
    # DEEPSEEK V4 FLASH 0731
    # ---------------------------------------------------------

    "deepseek/deepseek-v4-flash-0731": {
        "pricing": {
            "currency": "USD",
            "input_cache_hit_offpeak_per_1m_tokens": 0.007,
            "input_cache_hit_peak_per_1m_tokens": 0.014,
            "input_cache_miss_offpeak_per_1m_tokens": 0.22,
            "input_cache_miss_peak_per_1m_tokens": 0.44,
            "output_offpeak_per_1m_tokens": 0.66,
            "output_peak_per_1m_tokens": 1.32,
            "source": "DeepSeek API pricing",
        },
        "embeddings": False,
        "official_website": "https://api-docs.deepseek.com/quick_start/pricing/",
    },

    # ---------------------------------------------------------
    # KIMI K2 THINKING
    # ---------------------------------------------------------

    "moonshotai/kimi-k2-thinking": {
        "official_website": "https://platform.kimi.com/blog/posts/k2-think",
        "pricing": {
            "status": "See current Kimi API pricing",
            "source": "https://platform.kimi.com/",
        },
        "structured_output": True,
        "embeddings": False,
    },

    # ---------------------------------------------------------
    # THINKING MACHINES
    # ---------------------------------------------------------

    "thinkingmachines/inkling": {
        "pricing": {
            "currency": "USD",
            "input_prefill_per_1m_tokens": 1.00,
            "cached_input_per_1m_tokens": 0.17,
            "output_per_1m_tokens": 4.05,
            "source": "Tinker",
        },
        "structured_output": True,
        "benchmarks": {
            "source": "https://thinkingmachines.ai/news/introducing-inkling-small/",
            "available": True,
        },
    },

    "thinkingmachines/inkling-small": {
        "pricing": {
            "currency": "USD",
            "input_prefill_per_1m_tokens": 0.30,
            "cached_input_per_1m_tokens": 0.06,
            "output_per_1m_tokens": 1.20,
            "source": "Tinker",
        },
        "structured_output": True,
        "benchmarks": {
            "source": "https://thinkingmachines.ai/news/inkling-small/",
            "available": True,
        },
    },
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


def merge_patch(record: dict, patch: dict) -> int:
    written = 0

    for field, value in patch.items():

        if is_empty(value):
            continue

        if is_empty(record.get(field)):
            record[field] = value
            written += 1

    official = patch.get("official_website")

    if isinstance(official, str):

        sources = record.get("source_urls")

        if not isinstance(sources, list):
            sources = []

        if official not in sources:
            sources.append(official)

        record["source_urls"] = sources

    return written


def main() -> None:

    ensure_directories()

    payload = load_json(INPUT_FILE)

    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_provider_complete.json"
        )

    updated_records = []

    matched = 0
    fields_written = 0

    for record in records:

        item = dict(record)

        model_id = str(
            item.get("model_id") or ""
        )

        patch = PATCHES.get(model_id)

        if patch is not None:

            matched += 1

            fields_written += merge_patch(
                item,
                patch,
            )

        updated_records.append(item)

    output = {
        "metadata": {
            **(
                payload.get("metadata")
                or {}
            ),
            "dataset_name":
                "AIOrbit Models Final Evidence Patched Dataset",
            "matched_models": matched,
            "fields_written": fields_written,
            "source_policy":
                "First-party evidence only; existing values preserved.",
        },
        "records": updated_records,
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
        "AIOrbit Models - Final Evidence Patch",
        f"Input records: {len(records)}",
        f"Matched models: {matched}",
        f"Fields written: {fields_written}",
        "",
        "UPDATED MODELS",
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
        f"Matched models: {matched}"
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