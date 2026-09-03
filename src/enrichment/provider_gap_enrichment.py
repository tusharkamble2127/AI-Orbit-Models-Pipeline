from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_hf_verified.json"
OUTPUT_FILE = FINAL_DATA_DIR / "provider_gap_queue.json"
REPORT_FILE = FINAL_DATA_DIR / "provider_gap_queue.txt"


TARGET_FIELDS = [
    "official_website",
    "pricing",
    "license",
    "embeddings",
    "structured_output",
    "github",
    "benchmarks",
]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_missing(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0

    return False


def normalize_provider(record: dict) -> str:
    provider = record.get("company_provider")

    if provider:
        return str(provider).strip().lower()

    model_id = str(record.get("model_id") or "")

    if "/" in model_id:
        return model_id.split("/", 1)[0].lower()

    return "unknown"


def provider_display_name(provider: str) -> str:
    names = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "deepseek": "DeepSeek",
        "xai": "xAI",
        "moonshotai": "Moonshot AI",
        "tencent": "Tencent",
        "xiaomi": "Xiaomi",
        "arcee-ai": "Arcee AI",
        "thinkingmachines": "Thinking Machines",
    }

    return names.get(provider, provider.title())


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_hf_verified.json"
        )

    provider_groups = defaultdict(list)

    for record in records:
        provider = normalize_provider(record)

        missing_fields = [
            field
            for field in TARGET_FIELDS
            if is_missing(record.get(field))
        ]

        # Keep only models that actually have unresolved provider gaps.
        if missing_fields:
            provider_groups[provider].append(
                {
                    "model_id": record.get("model_id"),
                    "model_name": record.get("model_name"),
                    "missing_fields": missing_fields,
                    "missing_count": len(missing_fields),
                    "quality_score": record.get("quality_score"),
                    "official_website": record.get("official_website"),
                    "pricing": record.get("pricing"),
                    "license": record.get("license"),
                    "embeddings": record.get("embeddings"),
                    "structured_output": record.get(
                        "structured_output"
                    ),
                    "github": record.get("github"),
                    "benchmarks": record.get("benchmarks"),
                }
            )

    # Sort providers by number of unresolved records.
    provider_groups = dict(
        sorted(
            provider_groups.items(),
            key=lambda item: (
                -len(item[1]),
                item[0],
            ),
        )
    )

    provider_summary = {}

    for provider, models in provider_groups.items():
        field_counts = {
            field: 0
            for field in TARGET_FIELDS
        }

        for model in models:
            for field in model["missing_fields"]:
                field_counts[field] += 1

        provider_summary[provider] = {
            "display_name": provider_display_name(provider),
            "model_count": len(models),
            "field_gap_counts": field_counts,
            "models": models,
        }

    field_totals = {
        field: sum(
            field_counts[field]
            for field_counts in (
                provider["field_gap_counts"]
                for provider in provider_summary.values()
            )
        )
        for field in TARGET_FIELDS
    }

    output = {
        "dataset": INPUT_FILE.name,
        "record_count": len(records),
        "provider_count": len(provider_summary),
        "target_fields": TARGET_FIELDS,
        "field_gap_totals": field_totals,
        "providers": provider_summary,
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
        "AIOrbit Models - Provider Gap Enrichment Queue",
        f"Records: {len(records)}",
        f"Providers with gaps: {len(provider_summary)}",
        "",
        "GLOBAL FIELD GAPS",
        "=" * 100,
    ]

    for field, count in sorted(
        field_totals.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(
            f"{field:<25} {count}"
        )

    lines.extend(
        [
            "",
            "PROVIDER QUEUE",
            "=" * 100,
        ]
    )

    for provider, summary in provider_summary.items():

        lines.append(
            f"{summary['display_name']} "
            f"({provider}) | "
            f"models={summary['model_count']}"
        )

        nonzero = [
            f"{field}={count}"
            for field, count in summary["field_gap_counts"].items()
            if count
        ]

        lines.append(
            "  Gaps: "
            + ", ".join(nonzero)
        )

        for model in sorted(
            summary["models"],
            key=lambda item: (
                -item["missing_count"],
                item["model_name"] or "",
            ),
        ):
            lines.append(
                f"  - {model['model_name']} | "
                f"{model['model_id']} | "
                f"missing={model['missing_count']} | "
                f"{', '.join(model['missing_fields'])}"
            )

        lines.append("")

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"Records: {len(records)}"
    )

    print(
        f"Providers with gaps: "
        f"{len(provider_summary)}"
    )

    print(
        f"JSON: {OUTPUT_FILE}"
    )

    print(
        f"Text: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()