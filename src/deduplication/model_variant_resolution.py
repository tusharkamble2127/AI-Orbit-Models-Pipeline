from __future__ import annotations

import json
import logging
import re
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rapidfuzz.fuzz import ratio, token_set_ratio

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_official_enriched.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_variant_resolution.json"
REPORT_FILE = FINAL_DATA_DIR / "model_variant_resolution_report.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def normalize(value: Any) -> str:
    value = text(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", text(value).lower())


def model_id(record: dict[str, Any]) -> str:
    return text(record.get("model_id") or record.get("id") or record.get("model_name"))


def model_name(record: dict[str, Any]) -> str:
    return text(record.get("model_name") or record.get("name") or record.get("model_id"))


def family(record: dict[str, Any]) -> str:
    return text(record.get("model_family"))


def quality(record: dict[str, Any]) -> int:
    try:
        return int(float(record.get("quality_score", 0)))
    except (TypeError, ValueError):
        return 0


def normalize_url(url: str) -> str:
    url = text(url)
    if not url:
        return ""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def source_urls(record: dict[str, Any]) -> set[str]:
    urls: set[str] = set()

    for item in record.get("weights") or []:
        if isinstance(item, dict):
            u = normalize_url(item.get("url"))
            if u:
                urls.add(u)

    enrichment = record.get("official_enrichment") or {}
    if isinstance(enrichment, dict):
        selected = enrichment.get("selected_official_source") or {}
        if isinstance(selected, dict):
            u = normalize_url(selected.get("url"))
            if u:
                urls.add(u)

    for item in (record.get("verification") or {}).get("sources_checked", []) or []:
        if isinstance(item, dict):
            u = normalize_url(item.get("final_url") or item.get("url"))
            if u:
                urls.add(u)

    return urls


def github_repos(record: dict[str, Any]) -> set[str]:
    repos: set[str] = set()
    for url in source_urls(record):
        if url.startswith("github.com/"):
            parts = url.split("/")
            if len(parts) >= 3:
                repos.add("/".join(parts[:3]))
    return repos


def name_stem(name: str) -> str:
    """
    Remove common non-identity qualifiers while retaining the core model name.
    This is only used as a similarity signal, never as an automatic duplicate rule.
    """
    value = normalize(name)
    value = re.sub(
        r"\b(latest|preview|beta|alpha|experimental|turbo|highspeed|"
        r"fast|lite|mini|nano|pro|plus|instant|chat|reasoning|"
        r"instruct|thinking|flash|air|vision|tts|live)\b",
        " ",
        value,
    )
    return re.sub(r"\s+", " ", value).strip()


def score_pair(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    a_id = model_id(a)
    b_id = model_id(b)
    a_name = model_name(a)
    b_name = model_name(b)
    a_family = normalize(family(a))
    b_family = normalize(family(b))

    signals: list[str] = []
    strong_signals = 0
    moderate_signals = 0

    # Hard identity signals.
    if a_id and b_id and compact(a_id) == compact(b_id):
        strong_signals += 5
        signals.append("same_model_id")

    a_urls = source_urls(a)
    b_urls = source_urls(b)

    shared_urls = a_urls & b_urls
    if shared_urls:
        strong_signals += 4
        signals.append("shared_source_url")

    shared_repos = github_repos(a) & github_repos(b)
    if shared_repos:
        strong_signals += 3
        signals.append("shared_github_repo")

    # Family is evidence, not identity.
    family_same = bool(a_family and b_family and a_family == b_family)
    if family_same:
        moderate_signals += 2
        signals.append("same_model_family")

    # Name similarity.
    name_ratio = ratio(normalize(a_name), normalize(b_name))
    name_token = token_set_ratio(normalize(a_name), normalize(b_name))
    stem_ratio = token_set_ratio(name_stem(a_name), name_stem(b_name))

    if name_ratio >= 96:
        moderate_signals += 2
        signals.append("very_high_name_similarity")
    elif name_ratio >= 90:
        moderate_signals += 1
        signals.append("high_name_similarity")

    if stem_ratio >= 95:
        moderate_signals += 2
        signals.append("same_name_stem")
    elif stem_ratio >= 85:
        moderate_signals += 1
        signals.append("similar_name_stem")

    # Strong contradiction signals: explicit generation/size/task qualifiers.
    a_norm = normalize(a_name)
    b_norm = normalize(b_name)

    version_pattern = re.compile(r"\b(?:\d+(?:\.\d+){0,2}|v\d+(?:\.\d+)*)\b")
    a_versions = set(version_pattern.findall(a_norm))
    b_versions = set(version_pattern.findall(b_norm))

    if a_versions and b_versions and a_versions != b_versions:
        signals.append("different_explicit_version_markers")

    size_pattern = re.compile(r"\b\d+(?:b|m|k)\b")
    a_sizes = set(size_pattern.findall(a_norm))
    b_sizes = set(size_pattern.findall(b_norm))

    if a_sizes and b_sizes and a_sizes != b_sizes:
        signals.append("different_size_markers")

    task_terms = {
        "vision", "tts", "speech", "audio", "embedding", "rerank",
        "ocr", "image", "video", "code", "coder", "translate",
        "safety", "guard", "robotics",
    }
    a_tasks = task_terms & set(a_norm.split())
    b_tasks = task_terms & set(b_norm.split())

    if a_tasks and b_tasks and a_tasks != b_tasks:
        signals.append("different_task_markers")

    score = min(
        100,
        strong_signals * 15
        + moderate_signals * 8
        + int(name_ratio * 0.12)
        + int(name_token * 0.05),
    )

    # Conservative classification.
    if a_id and b_id and compact(a_id) == compact(b_id):
        classification = "EXACT_DUPLICATE"

    elif shared_urls and family_same and name_ratio >= 90:
        classification = "LIKELY_VARIANT"

    elif shared_repos and family_same and name_ratio >= 90:
        classification = "LIKELY_VARIANT"

    elif (
        family_same
        and name_ratio >= 94
        and "different_explicit_version_markers" not in signals
        and "different_size_markers" not in signals
        and "different_task_markers" not in signals
    ):
        classification = "POSSIBLE_VARIANT"

    elif (
        family_same
        and stem_ratio >= 95
        and name_ratio >= 82
        and "different_task_markers" not in signals
    ):
        classification = "POSSIBLE_VARIANT"

    elif (
        name_ratio >= 96
        and "different_explicit_version_markers" not in signals
        and "different_size_markers" not in signals
        and "different_task_markers" not in signals
    ):
        classification = "POSSIBLE_SIMILARITY"

    else:
        classification = "DISTINCT"

    return {
        "model_id_a": a_id,
        "model_name_a": a_name,
        "model_id_b": b_id,
        "model_name_b": b_name,
        "classification": classification,
        "score": score,
        "name_ratio": round(name_ratio, 2),
        "name_token_ratio": round(name_token, 2),
        "name_stem_ratio": round(stem_ratio, 2),
        "same_family": family_same,
        "shared_source_urls": sorted(shared_urls),
        "shared_github_repos": sorted(shared_repos),
        "signals": signals,
    }


def main() -> None:
    ensure_directories()

    records = load_json(INPUT_FILE)
    if not isinstance(records, list):
        raise ValueError("Input file must contain a JSON list.")

    logging.info("Input records: %d", len(records))

    comparisons: list[dict[str, Any]] = []
    flagged_by_record: dict[str, list[dict[str, Any]]] = {
        model_id(r): [] for r in records
    }

    classification_counts: dict[str, int] = {}

    for a, b in combinations(records, 2):
        result = score_pair(a, b)
        classification = result["classification"]

        if classification != "DISTINCT":
            comparisons.append(result)
            classification_counts[classification] = (
                classification_counts.get(classification, 0) + 1
            )

            flagged_by_record[result["model_id_a"]].append(result)
            flagged_by_record[result["model_id_b"]].append(result)

    enriched_records: list[dict[str, Any]] = []

    for record in records:
        rid = model_id(record)
        flags = flagged_by_record.get(rid, [])

        exact = [x for x in flags if x["classification"] == "EXACT_DUPLICATE"]
        likely = [x for x in flags if x["classification"] == "LIKELY_VARIANT"]
        possible = [
            x for x in flags
            if x["classification"] in {"POSSIBLE_VARIANT", "POSSIBLE_SIMILARITY"}
        ]

        if exact:
            overall = "DUPLICATE_REVIEW"
        elif likely:
            overall = "VARIANT_REVIEW"
        elif possible:
            overall = "SIMILARITY_REVIEW"
        else:
            overall = "UNIQUE_CANDIDATE"

        enriched = dict(record)
        enriched["variant_resolution"] = {
            "overall_status": overall,
            "flag_count": len(flags),
            "exact_duplicate_count": len(exact),
            "likely_variant_count": len(likely),
            "possible_similarity_count": len(possible),
            "review_required": overall != "UNIQUE_CANDIDATE",
        }
        enriched_records.append(enriched)

    report = {
        "pipeline": "AIOrbit Models Conservative Variant Resolution v2",
        "input_records": len(records),
        "total_pairwise_comparisons": len(records) * (len(records) - 1) // 2,
        "flagged_comparisons": len(comparisons),
        "classification_summary": classification_counts,
        "record_status_summary": {
            status: sum(
                1
                for r in enriched_records
                if r["variant_resolution"]["overall_status"] == status
            )
            for status in [
                "DUPLICATE_REVIEW",
                "VARIANT_REVIEW",
                "SIMILARITY_REVIEW",
                "UNIQUE_CANDIDATE",
            ]
        },
        "methodology": {
            "automatic_duplicate_rule": "same canonical model_id only",
            "variant_rule": "shared canonical source/repository plus strong identity/name evidence",
            "similarity_rule": "name/family similarity without enough identity evidence",
            "name_similarity_alone": "never treated as duplicate",
            "manual_review_required": True,
        },
    }

    save_json(OUTPUT_FILE, enriched_records)
    save_json(
        REPORT_FILE,
        {
            **report,
            "flagged_comparisons": comparisons,
        },
    )

    logging.info("Variant resolution v2 completed.")
    logging.info(
        "Pairwise comparisons: %d",
        report["total_pairwise_comparisons"],
    )
    logging.info(
        "Flagged comparisons: %d",
        report["flagged_comparisons"],
    )
    logging.info("Classification summary:")

    for key, value in sorted(classification_counts.items()):
        logging.info("  %s: %d", key, value)

    logging.info("Record status summary:")

    for key, value in report["record_status_summary"].items():
        logging.info("  %s: %d", key, value)

    logging.info("Output: %s", OUTPUT_FILE)
    logging.info("Report: %s", REPORT_FILE)


if __name__ == "__main__":
    main()
