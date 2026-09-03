from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any

from rapidfuzz.fuzz import ratio


INPUT_PATH = Path(
    "data/intermediate/models_dev_normalized.json"
)

OUTPUT_PATH = Path(
    "data/intermediate/entity_resolution_report.json"
)


def normalize_text(value: str | None) -> str:
    """
    Normalize text only for comparison.

    Important:
    Semantic suffixes such as preview, turbo, highspeed,
    instruct, pro, mini, etc. are intentionally preserved.
    """
    if not value:
        return ""

    value = value.lower().strip()

    value = re.sub(r"[^a-z0-9]+", " ", value)

    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value: str | None) -> str:
    """Normalize a URL for comparison."""
    if not value:
        return ""

    value = value.strip().lower()

    return value.rstrip("/")


def extract_weight_urls(record: dict[str, Any]) -> list[str]:
    """Extract repository/weight URLs from a model record."""
    urls: list[str] = []

    weights = record.get("weights", [])

    if not isinstance(weights, list):
        return urls

    for weight in weights:
        if not isinstance(weight, dict):
            continue

        url = weight.get("url")

        if isinstance(url, str) and url.strip():
            urls.append(normalize_url(url))

    return urls


def compare_records(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare two model records and collect entity-resolution evidence.

    No automatic merge/delete decision is made here.
    """

    left_id = normalize_text(left.get("model_id"))
    right_id = normalize_text(right.get("model_id"))

    left_name = normalize_text(left.get("model_name"))
    right_name = normalize_text(right.get("model_name"))

    left_family = normalize_text(left.get("model_family"))
    right_family = normalize_text(right.get("model_family"))

    left_weights = set(extract_weight_urls(left))
    right_weights = set(extract_weight_urls(right))

    name_similarity = ratio(left_name, right_name)

    exact_id_match = (
        bool(left_id)
        and bool(right_id)
        and left_id == right_id
    )

    same_name = (
        bool(left_name)
        and bool(right_name)
        and left_name == right_name
    )

    same_family = (
        bool(left_family)
        and bool(right_family)
        and left_family == right_family
    )

    shared_weights = sorted(
        left_weights.intersection(right_weights)
    )

    score = 0
    reasons: list[str] = []

    # Strongest possible identity signal.
    if exact_id_match:
        score += 100
        reasons.append("exact_model_id")

    # Same normalized model name is useful but not enough
    # for automatic merging.
    if same_name:
        score += 40
        reasons.append("same_normalized_name")

    # Same family helps establish similarity but is not
    # proof of duplication.
    if same_family:
        score += 20
        reasons.append("same_model_family")

    # Shared HF/weight repository is only a REVIEW signal.
    if shared_weights:
        score += 20
        reasons.append("shared_weight_repository")

    if name_similarity >= 95:
        score += 20
        reasons.append(
            f"very_high_name_similarity:{name_similarity:.1f}"
        )
    elif name_similarity >= 85:
        score += 10
        reasons.append(
            f"high_name_similarity:{name_similarity:.1f}"
        )

    return {
        "left_model_id": left.get("model_id"),
        "right_model_id": right.get("model_id"),

        "left_model_name": left.get("model_name"),
        "right_model_name": right.get("model_name"),

        "left_family": left.get("model_family"),
        "right_family": right.get("model_family"),

        "name_similarity": round(
            name_similarity,
            2,
        ),

        "exact_model_id_match": exact_id_match,
        "same_normalized_name": same_name,
        "same_model_family": same_family,

        "shared_weight_urls": shared_weights,

        "score": score,
        "reasons": reasons,
    }


def classify_comparison(
    comparison: dict[str, Any],
) -> str:
    """
    Conservative classification.

    Rules:
    - Exact model ID -> automatic duplicate candidate.
    - Shared repository -> review only.
    - Same name/family -> review only.
    - High fuzzy similarity -> review only.
    """

    if comparison["exact_model_id_match"]:
        return "duplicate"

    if comparison["shared_weight_urls"]:
        return "review_required"

    if (
        comparison["same_normalized_name"]
        and comparison["same_model_family"]
    ):
        return "review_required"

    if comparison["name_similarity"] >= 95:
        return "review_required"

    if comparison["name_similarity"] >= 85:
        return "possible_similarity"

    return "distinct_or_low_similarity"


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_PATH}"
        )

    with INPUT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise TypeError(
            "Expected normalized dataset to be a list."
        )

    comparisons: list[dict[str, Any]] = []

    for left, right in combinations(records, 2):
        comparison = compare_records(
            left,
            right,
        )

        classification = classify_comparison(
            comparison
        )

        if classification != "distinct_or_low_similarity":
            comparison["classification"] = classification
            comparisons.append(comparison)

    summary: dict[str, int] = {}

    for comparison in comparisons:
        classification = comparison["classification"]

        summary[classification] = (
            summary.get(classification, 0) + 1
        )

    report = {
        "total_records": len(records),
        "comparisons_flagged": len(comparisons),
        "classification_summary": summary,
        "methodology": {
            "automatic_merge_rule": (
                "Exact model ID match only."
            ),
            "repository_rule": (
                "Shared repository is a review signal, "
                "not automatic proof of duplication."
            ),
            "fuzzy_rule": (
                "Fuzzy similarity generates review candidates "
                "but never deletes records automatically."
            ),
            "variant_rule": (
                "Preview, turbo, highspeed, instruct, "
                "version, size, and provider-specific variants "
                "require authoritative verification."
            ),
        },
        "comparisons": comparisons,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("Entity resolution analysis completed.")
    print(f"Input records: {len(records)}")
    print(f"Flagged comparisons: {len(comparisons)}")
    print(f"Report: {OUTPUT_PATH}")

    print("\nClassification summary:")

    for classification, count in sorted(
        summary.items()
    ):
        print(f"{classification}: {count}")


if __name__ == "__main__":
    main()