from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_hf_verified.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_provider_patched.json"
REPORT_FILE = FINAL_DATA_DIR / "provider_official_patch_report.txt"


PATCHES: dict[str, dict[str, Any]] = {

    # =========================================================
    # OPENAI
    # =========================================================

    "openai/gpt-5.4-mini": {
        "official_website":
            "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.75,
            "output_per_1m_tokens": 4.50,
        },
        "structured_output": True,
    },

    "openai/gpt-5.6-sol": {
        "official_website":
            "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 4.00,
            "output_per_1m_tokens": 20.00,
        },
        "structured_output": True,
    },

    # =========================================================
    # GOOGLE GEMINI
    # =========================================================

    "google/gemini-3.5-flash": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 1.50,
            "output_per_1m_tokens": 9.00,
        },
        "structured_output": True,
    },

    "google/gemini-3.5-flash-lite": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.30,
            "output_per_1m_tokens": 2.50,
        },
        "structured_output": True,
    },

    "google/gemini-3.6-flash": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.75,
            "output_per_1m_tokens": 3.75,
        },
        "structured_output": True,
    },

    "google/gemini-3.1-pro-preview": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens_le_200k": 2.00,
            "output_per_1m_tokens_le_200k": 12.00,
            "input_per_1m_tokens_gt_200k": 4.00,
            "output_per_1m_tokens_gt_200k": 18.00,
        },
        "structured_output": True,
    },

    "google/gemini-2.5-flash-lite": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "pricing": {
            "currency": "USD",
            "input_per_1m_tokens": 0.10,
        },
        "structured_output": True,
    },

    "google/gemini-2.5-pro": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "structured_output": True,
    },

    "google/gemini-3-flash-preview": {
        "official_website":
            "https://ai.google.dev/gemini-api/docs/models",
        "structured_output": True,
    },

    # =========================================================
    # ANTHROPIC
    # =========================================================

    "anthropic/claude-opus-4-6": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-opus-4-7": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-opus-4-8": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-opus-5": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-sonnet-4-6": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-sonnet-5": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    "anthropic/claude-fable-5": {
        "official_website":
            "https://platform.claude.com/docs/en/about-claude/models",
        "structured_output": True,
    },

    # =========================================================
    # TENCENT HY3
    # =========================================================

    "tencent/hy3-preview": {
        "github": [
            "https://github.com/Tencent-Hunyuan/Hy3-preview"
        ],
        "license": {
            "name": "Tencent Hy Community License",
            "source":
                "https://github.com/Tencent-Hunyuan/Hy3-preview/blob/main/LICENSE",
        },
        "benchmarks": {
            "source":
                "https://github.com/Tencent-Hunyuan/Hy3-preview",
            "available": True,
        },
    },

    # =========================================================
    # DEEPSEEK V4 FLASH 0731
    # =========================================================

    "deepseek/deepseek-v4-flash-0731": {
        "official_website":
            "https://api-docs.deepseek.com/quick_start/pricing/",
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

        # Never overwrite an existing verified value.
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
            "Expected 'records' list in models_final_hf_verified.json"
        )

    matched = 0
    fields_written = 0

    updated_records = []

    for record in records:

        model_id = str(
            record.get("model_id") or ""
        )

        patch = PATCHES.get(model_id)

        item = dict(record)

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
                "AIOrbit Models Provider Official Patched Dataset",
            "patch_policy":
                "First-party source evidence only; "
                "existing values preserved.",
            "matched_models": matched,
            "fields_written": fields_written,
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
        "AIOrbit Models - Provider Official Patch",
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