from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.config import INTERMEDIATE_DATA_DIR, ensure_directories


INPUT_FILE = INTERMEDIATE_DATA_DIR / "models_identity_verified.json"
OUTPUT_FILE = INTERMEDIATE_DATA_DIR / "models_scored.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def safe_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)

    if isinstance(value, dict):
        return " ".join(safe_text(v) for v in value.values())

    return str(value).strip()


def normalized_text(value: Any) -> str:
    text = safe_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def has_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, dict)):
        return len(value) > 0

    return True


def score_capability(model: dict[str, Any]) -> int:
    """
    Maximum: 30
    Evaluates whether the model has meaningful capability evidence.
    """

    score = 0

    description = safe_text(model.get("description"))
    modalities = model.get("modalities") or {}
    reasoning = model.get("reasoning")
    tool_calling = model.get("tool_calling")

    if description:
        score += 10

    if len(description) >= 100:
        score += 3

    input_modalities = modalities.get("input", [])
    output_modalities = modalities.get("output", [])

    if input_modalities:
        score += 3

    if output_modalities:
        score += 3

    if reasoning:
        score += 4

    if tool_calling:
        score += 4

    return min(score, 30)


def score_usefulness(model: dict[str, Any]) -> int:
    """
    Maximum: 20
    Uses description, modalities, and functional capabilities as proxies
    for practical usefulness.
    """

    score = 0

    description = normalized_text(model.get("description"))
    modalities = model.get("modalities") or {}
    context_window = model.get("context_window")
    maximum_output = model.get("maximum_output")

    useful_keywords = [
        "coding",
        "code",
        "reasoning",
        "agent",
        "research",
        "vision",
        "multimodal",
        "document",
        "translation",
        "embedding",
        "speech",
        "audio",
        "image",
        "video",
        "ocr",
        "instruction",
        "analysis",
        "generation",
    ]

    matched_keywords = sum(
        1 for keyword in useful_keywords if keyword in description
    )

    score += min(matched_keywords * 2, 10)

    if modalities.get("input") and modalities.get("output"):
        score += 3

    if context_window:
        try:
            if int(context_window) >= 32000:
                score += 3
            elif int(context_window) >= 8000:
                score += 2
            else:
                score += 1
        except (TypeError, ValueError):
            pass

    if maximum_output:
        score += 2

    return min(score, 20)


def score_adoption(model: dict[str, Any]) -> int:
    """
    Maximum: 15
    Evidence includes provider availability, Hugging Face/weight links,
    and provider ecosystem coverage.
    """

    score = 0

    providers = model.get("providers") or []
    weights = model.get("weights") or []

    if providers:
        provider_count = len(providers)

        if provider_count >= 10:
            score += 8
        elif provider_count >= 5:
            score += 6
        elif provider_count >= 2:
            score += 4
        else:
            score += 2

    if weights:
        score += 4

    if len(providers) >= 3 and weights:
        score += 3

    return min(score, 15)


def score_benchmarks(model: dict[str, Any]) -> int:
    """
    Maximum: 10
    Benchmark availability is evidence; it is not treated as proof of
    model superiority.
    """

    benchmarks = model.get("benchmarks") or []

    if not benchmarks:
        return 0

    benchmark_count = len(benchmarks)

    if benchmark_count >= 10:
        return 10

    if benchmark_count >= 5:
        return 8

    if benchmark_count >= 3:
        return 6

    if benchmark_count >= 1:
        return 4

    return 0


def score_activity(model: dict[str, Any]) -> int:
    """
    Maximum: 10
    Uses release/updated metadata and the presence of current source
    information.
    """

    score = 0

    release_date = safe_text(model.get("release_date"))
    last_updated = safe_text(model.get("last_updated"))

    if release_date:
        score += 3

    if last_updated:
        score += 4

    if release_date and last_updated:
        score += 1

    verification = model.get("verification") or {}

    if verification.get("status"):
        score += 1

    if model.get("identity_verification"):
        score += 1

    return min(score, 10)


def score_technical(model: dict[str, Any]) -> int:
    """
    Maximum: 5
    """

    score = 0

    if model.get("reasoning"):
        score += 1

    if model.get("tool_calling"):
        score += 1

    if model.get("structured_output"):
        score += 1

    if model.get("context_window"):
        score += 1

    if model.get("maximum_output"):
        score += 1

    return min(score, 5)


def score_docs_accessibility(model: dict[str, Any]) -> int:
    """
    Maximum: 5
    """

    score = 0

    provider_docs = model.get("provider_docs") or []
    weights = model.get("weights") or []
    providers = model.get("providers") or []

    if provider_docs:
        score += 2

    if weights:
        score += 1

    if providers:
        score += 1

    if provider_docs and weights:
        score += 1

    return min(score, 5)


def score_differentiation(model: dict[str, Any]) -> int:
    """
    Maximum: 5
    This is intentionally conservative because true differentiation
    often requires deeper comparative research.
    """

    score = 0

    family = safe_text(model.get("model_family"))
    description = normalized_text(model.get("description"))

    if family:
        score += 1

    differentiation_keywords = [
        "specialized",
        "specialized for",
        "reasoning",
        "multimodal",
        "vision",
        "coding",
        "agent",
        "safety",
        "embedding",
        "speech",
        "ocr",
        "long context",
        "real time",
    ]

    matched = sum(
        1 for keyword in differentiation_keywords
        if keyword in description
    )

    if matched >= 3:
        score += 4
    elif matched >= 2:
        score += 3
    elif matched >= 1:
        score += 2

    return min(score, 5)


def quality_band(score: int) -> str:
    if score >= 90:
        return "exceptional"

    if score >= 80:
        return "excellent"

    if score >= 70:
        return "good"

    if score >= 60:
        return "borderline"

    return "reject_candidate"


def identity_status(model: dict[str, Any]) -> str:
    identity = model.get("identity_verification") or {}

    return (
        identity.get("status")
        or model.get("verification_status")
        or "unknown"
    )


def calculate_quality_score(model: dict[str, Any]) -> dict[str, Any]:
    capability = score_capability(model)
    usefulness = score_usefulness(model)
    adoption = score_adoption(model)
    benchmarks = score_benchmarks(model)
    activity = score_activity(model)
    technical = score_technical(model)
    documentation = score_docs_accessibility(model)
    differentiation = score_differentiation(model)

    total = (
        capability
        + usefulness
        + adoption
        + benchmarks
        + activity
        + technical
        + documentation
        + differentiation
    )

    identity = identity_status(model)

    if identity in {"no_identity_evidence", "unverified"}:
        curation_status = "manual_identity_review"
    elif identity == "needs_review":
        curation_status = "identity_review_recommended"
    elif total < 60:
        curation_status = "low_quality_candidate"
    elif total < 70:
        curation_status = "borderline_candidate"
    else:
        curation_status = "quality_candidate"

    return {
        "total": total,
        "band": quality_band(total),
        "criteria": {
            "capability": capability,
            "real_world_usefulness": usefulness,
            "adoption": adoption,
            "benchmarks": benchmarks,
            "activity_current_relevance": activity,
            "technical_capabilities": technical,
            "documentation_accessibility": documentation,
            "differentiation": differentiation,
        },
        "curation_status": curation_status,
    }


def main() -> None:
    ensure_directories()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("Expected a JSON list of model records.")

    logging.info("Input records: %d", len(records))

    scored_records: list[dict[str, Any]] = []

    for index, model in enumerate(records, start=1):
        model_name = safe_text(
            model.get("model_name")
            or model.get("model_id")
            or "Unknown"
        )

        logging.info(
            "[%d/%d] Scoring %s",
            index,
            len(records),
            model_name,
        )

        scored = calculate_quality_score(model)

        enriched = dict(model)
        enriched["quality_score"] = scored["total"]
        enriched["quality_band"] = scored["band"]
        enriched["quality_breakdown"] = scored["criteria"]
        enriched["curation_status"] = scored["curation_status"]

        scored_records.append(enriched)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            scored_records,
            file,
            indent=2,
            ensure_ascii=False,
        )

    bands: dict[str, int] = {}
    statuses: dict[str, int] = {}

    for record in scored_records:
        band = record.get("quality_band", "unknown")
        status = record.get("curation_status", "unknown")

        bands[band] = bands.get(band, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1

    logging.info("")
    logging.info("Quality scoring completed.")
    logging.info("Output: %s", OUTPUT_FILE)
    logging.info("Quality bands:")

    for band, count in sorted(bands.items()):
        logging.info("  %s: %d", band, count)

    logging.info("Curation statuses:")

    for status, count in sorted(statuses.items()):
        logging.info("  %s: %d", status, count)


if __name__ == "__main__":
    main()