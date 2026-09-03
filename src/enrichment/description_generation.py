from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final_candidate.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_with_descriptions.json"
REPORT_FILE = FINAL_DATA_DIR / "description_generation_report.txt"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def clean(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return ", ".join(
            str(x).strip()
            for x in value
            if x not in (None, "")
        )

    if isinstance(value, dict):
        return ", ".join(
            f"{k}: {v}"
            for k, v in value.items()
            if v not in (None, "", [], {})
        )

    return str(value)


def format_number(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,}"

    return str(value)


def get_capability_sentence(record: dict) -> str:
    parts = []

    modalities = clean(record.get("modalities"))
    if modalities:
        parts.append(f"It supports {modalities} modalities")

    if record.get("reasoning") is True:
        parts.append("supports reasoning-oriented workloads")

    if record.get("function_tool_calling") is True:
        parts.append("supports function/tool calling")

    if record.get("structured_output") is True:
        parts.append("supports structured output")

    if record.get("vision") is True:
        parts.append("supports vision")

    if record.get("audio") is True:
        parts.append("supports audio")

    if not parts:
        return ""

    if len(parts) == 1:
        return parts[0] + "."

    return "; ".join(parts[:-1]) + ", and " + parts[-1] + "."


def get_context_sentence(record: dict) -> str:
    context = record.get("context_window")
    maximum_output = record.get("maximum_output")

    pieces = []

    if context is not None:
        pieces.append(
            f"a context window of {format_number(context)} tokens"
        )

    if maximum_output is not None:
        pieces.append(
            f"up to {format_number(maximum_output)} output tokens"
        )

    if not pieces:
        return ""

    if len(pieces) == 1:
        return f"It provides {pieces[0]}."

    return f"It provides {pieces[0]} and {pieces[1]}."


def get_access_sentence(record: dict) -> str:
    parts = []

    if record.get("open_source_weights") is True:
        parts.append("open weights")

    provider = clean(record.get("company_provider"))
    if provider:
        parts.append(f"provided by {provider}")

    if not parts:
        return ""

    return "The model is " + " and ".join(parts) + "."


def get_benchmark_sentence(record: dict) -> str:
    benchmarks = record.get("benchmarks")

    if benchmarks in (None, "", [], {}):
        return ""

    if isinstance(benchmarks, dict):
        source = benchmarks.get("source")

        if source:
            return (
                "Benchmark evidence is available in the verified "
                "source record."
            )

        return "Benchmark evidence is available in the verified model data."

    return "Benchmark information is available in the verified model data."


def get_quality_sentence(record: dict) -> str:
    score = record.get("quality_score")
    band = clean(record.get("quality_band"))

    if score is None and not band:
        return ""

    if score is not None and band:
        return (
            f"The curated quality assessment is {score:.0f}/100 "
            f"({band})."
        )

    if score is not None:
        return f"The curated quality assessment is {score:.0f}/100."

    return f"The curated quality assessment is {band}."


def build_description(record: dict) -> str:
    name = clean(record.get("model_name"))
    family = clean(record.get("model_family"))
    provider = clean(record.get("company_provider"))

    if not name:
        name = "This model"

    opening_parts = []

    if family:
        opening_parts.append(
            f"{name} is a {family} model"
        )
    else:
        opening_parts.append(
            f"{name} is an AI model"
        )

    if provider:
        opening_parts.append(
            f"from {provider}"
        )

    opening = " ".join(opening_parts) + "."

    description = [opening]

    capabilities = get_capability_sentence(record)
    if capabilities:
        description.append(capabilities)

    context = get_context_sentence(record)
    if context:
        description.append(context)

    access = get_access_sentence(record)
    if access:
        description.append(access)

    benchmark = get_benchmark_sentence(record)
    if benchmark:
        description.append(benchmark)

    quality = get_quality_sentence(record)
    if quality:
        description.append(quality)

    task = clean(record.get("model_type_task"))

    if task:
        description.append(
            f"It is intended for {task}-oriented applications."
        )

    return " ".join(
        sentence.strip()
        for sentence in description
        if sentence.strip()
    )


def validate_description(text: str) -> list[str]:
    problems = []

    if not text.strip():
        problems.append("empty")

    words = text.split()

    if len(words) < 30:
        problems.append("too_short")

    if len(words) > 130:
        problems.append("too_long")

    if "\n" in text:
        problems.append("multiple_lines")

    banned_phrases = [
        "revolutionary",
        "game-changing",
        "world-class",
        "best model",
        "according to the source",
        "according to the data",
    ]

    lower = text.lower()

    for phrase in banned_phrases:
        if phrase in lower:
            problems.append(
                f"banned_phrase:{phrase}"
            )

    if "http://" in lower or "https://" in lower:
        problems.append("contains_url")

    return problems


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)
    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in models_final_candidate.json"
        )

    generated = 0
    validation_failures = 0

    output_records = []

    for index, record in enumerate(records, start=1):

        item = dict(record)

        description = build_description(item)

        problems = validate_description(description)

        if problems:
            validation_failures += 1

        item["description"] = description

        item["description_metadata"] = {
            "generated": True,
            "method": "local_evidence_based_generator",
            "source": "verified_dataset_fields",
            "validation": {
                "valid": len(problems) == 0,
                "problems": problems,
                "word_count": len(description.split()),
            },
        }

        output_records.append(item)
        generated += 1

        print(
            f"[{index}/{len(records)}] "
            f"Generated: {item.get('model_name')}"
        )

    output = {
        "metadata": {
            **(
                payload.get("metadata")
                or {}
            ),
            "dataset_name":
                "AIOrbit Models Dataset With Descriptions",
            "description_generation": {
                "method": "local_evidence_based_generator",
                "records_total": len(records),
                "generated": generated,
                "validation_failures": validation_failures,
            },
        },
        "records": output_records,
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    report_lines = [
        "AIOrbit Models - Description Generation Report",
        f"Input records: {len(records)}",
        f"Descriptions generated: {generated}",
        f"Validation failures: {validation_failures}",
        "Generation method: local evidence-based generator",
        "",
        f"Output: {OUTPUT_FILE}",
    ]

    REPORT_FILE.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print("")
    print(f"Input records: {len(records)}")
    print(f"Descriptions generated: {generated}")
    print(
        f"Description validation failures: "
        f"{validation_failures}"
    )
    print(f"Output: {OUTPUT_FILE}")
    print(f"Report: {REPORT_FILE}")


if __name__ == "__main__":
    main()