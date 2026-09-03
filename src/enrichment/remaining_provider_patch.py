from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_provider_verified.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_remaining_provider_patched.json"
REPORT_FILE = FINAL_DATA_DIR / "remaining_provider_patch_report.txt"


PATCHES: dict[str, dict[str, Any]] = {

    # =========================================================
    # MOONSHOT / KIMI
    # =========================================================

    "moonshotai/kimi-k2.5": {
        "official_website": "https://platform.kimi.com/docs/models",
        "pricing": {
            "currency": "CNY",
            "input_cache_hit_per_1m_tokens": 0.70,
            "input_cache_miss_per_1m_tokens": 4.00,
            "output_per_1m_tokens": 21.00,
            "source": "Kimi API",
        },
        "license": {
            "name": "Modified MIT",
            "source": "https://huggingface.co/moonshotai/Kimi-K2.5",
        },
        "huggingface": [
            "https://huggingface.co/moonshotai/Kimi-K2.5"
        ],
        "embeddings": False,
        "benchmarks": {
            "source": "https://www.kimi.com/en/blog/kimi-k2-5",
            "available": True,
        },
    },

    "moonshotai/kimi-k2.6": {
        "official_website": "https://platform.kimi.com/",
        "pricing": {
            "currency": "CNY",
            "input_cache_hit_per_1m_tokens": 1.10,
            "input_cache_miss_per_1m_tokens": 6.50,
            "output_per_1m_tokens": 27.00,
            "source": "Kimi API",
        },
        "license": {
            "name": "Modified MIT",
            "source": "https://huggingface.co/moonshotai/Kimi-K2.6",
        },
        "huggingface": [
            "https://huggingface.co/moonshotai/Kimi-K2.6"
        ],
        "embeddings": False,
    },

    "moonshotai/kimi-k2.7-code": {
        "official_website": "https://platform.kimi.com/",
        "pricing": {
            "currency": "CNY",
            "input_cache_hit_per_1m_tokens": 1.30,
            "input_cache_miss_per_1m_tokens": 6.50,
            "output_per_1m_tokens": 27.00,
            "source": "Kimi API",
        },
        "license": {
            "name": "Modified MIT",
            "source": "https://huggingface.co/moonshotai/Kimi-K2.7-Code/blob/main/LICENSE",
        },
        "huggingface": [
            "https://huggingface.co/moonshotai/Kimi-K2.7-Code"
        ],
        "embeddings": False,
    },

    "moonshotai/kimi-k3": {
        "official_website": "https://platform.kimi.com/",
        "pricing": {
            "currency": "CNY",
            "input_cache_hit_per_1m_tokens": 2.00,
            "input_per_1m_tokens": 20.00,
            "output_per_1m_tokens": 100.00,
            "source": "Kimi API",
        },
        "license": {
            "name": "Kimi K3 License",
            "source": "https://huggingface.co/moonshotai/Kimi-K3",
        },
        "huggingface": [
            "https://huggingface.co/moonshotai/Kimi-K3"
        ],
        "embeddings": False,
    },

    "moonshotai/kimi-k2-thinking": {
        "official_website": "https://www.kimi.com/en/blog/",
        "embeddings": False,
    },

    # =========================================================
    # THINKING MACHINES
    # =========================================================

    "thinkingmachines/inkling": {
        "official_website": "https://thinkingmachines.ai/model-card/inkling/",
        "license": {
            "name": "Apache 2.0",
            "source": "https://thinkingmachines.ai/model-card/inkling/",
        },
        "huggingface": [
            "https://huggingface.co/collections/ThinkingMachinesLab/inkling"
        ],
        "embeddings": False,
        "benchmarks": {
            "source": "https://thinkingmachines.ai/news/introducing-inkling/",
            "available": True,
        },
    },

    "thinkingmachines/inkling-small": {
        "official_website": "https://thinkingmachines.ai/inkling/",
        "license": {
            "name": "Apache 2.0",
            "source": "https://thinkingmachines.ai/model-card/inkling/",
        },
        "huggingface": [
            "https://huggingface.co/collections/ThinkingMachinesLab/inkling"
        ],
        "embeddings": False,
        "pricing": {
            "currency": "USD",
            "source": "Tinker",
            "note": "Pricing varies by context length and service mode.",
        },
        "benchmarks": {
            "source": "https://thinkingmachines.ai/inkling/",
            "available": True,
        },
    },

    # =========================================================
    # ARCEE
    # =========================================================

    "arcee-ai/trinity-large-thinking": {
        "official_website": "https://www.arcee.ai/blog/trinity-large-thinking",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.25,
            "output_per_1m_tokens": 0.80,
            "source": "Arcee AI Open Models API",
        },
        "license": {
            "name": "Apache 2.0",
            "source": "https://www.arcee.ai/blog/trinity-large-thinking",
        },
        "embeddings": False,
        "benchmarks": {
            "source": "https://www.arcee.ai/blog/trinity-large-thinking",
            "available": True,
        },
    },

    # =========================================================
    # XIAOMI
    # =========================================================

    "xiaomi/mimo-v2.5": {
        "official_website": "https://mimo.mi.com/models/en-US/mimo-v2.5",
        "pricing": {
            "currency": "USD",
            "input_cache_hit_per_1m_tokens": 0.0028,
            "input_cache_miss_per_1m_tokens": 0.14,
            "output_per_1m_tokens": 0.28,
            "source": "Xiaomi MiMo API",
        },
        "license": {
            "name": "MIT",
            "source": "https://mimo.mi.com/docs/en-US/news/latest/v2.5-open-sourced",
        },
        "huggingface": [
            "https://huggingface.co/XiaomiMiMo/MiMo-V2.5"
        ],
        "embeddings": False,
        "structured_output": True,
        "benchmarks": {
            "source": "https://mimo.mi.com/models/en-US/mimo-v2.5",
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

        # Existing verified evidence wins.
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
            "Expected 'records' list in models_final_provider_verified.json"
        )

    matched = 0
    fields_written = 0

    updated_records = []

    for record in records:
        item = dict(record)

        model_id = str(item.get("model_id") or "")
        patch = PATCHES.get(model_id)

        if patch is not None:
            matched += 1
            fields_written += merge_patch(item, patch)

        updated_records.append(item)

    output = {
        "metadata": {
            **(payload.get("metadata") or {}),
            "dataset_name":
                "AIOrbit Models Remaining Provider Patched Dataset",
            "matched_models": matched,
            "fields_written": fields_written,
            "source_policy":
                "First-party provider/Hugging Face evidence only.",
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
        "AIOrbit Models - Remaining Provider Patch",
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

    print(f"Input records: {len(records)}")
    print(f"Matched models: {matched}")
    print(f"Fields written: {fields_written}")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()