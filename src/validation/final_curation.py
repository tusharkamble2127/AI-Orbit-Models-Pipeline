from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.config import INTERMEDIATE_DATA_DIR, FINAL_DATA_DIR, ensure_directories


IDENTITY_FILE = INTERMEDIATE_DATA_DIR / "models_identity_verified.json"
SCORED_FILE = INTERMEDIATE_DATA_DIR / "models_scored.json"
DEDUP_FILE = INTERMEDIATE_DATA_DIR / "entity_resolution_report.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_curated.json"
REPORT_FILE = FINAL_DATA_DIR / "curation_report.json"

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
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def get_model_id(record: dict[str, Any]) -> str:
    return text(
        record.get("model_id")
        or record.get("id")
        or record.get("model_name")
    )


def get_model_name(record: dict[str, Any]) -> str:
    return text(
        record.get("model_name")
        or record.get("name")
        or record.get("model_id")
        or "Unknown"
    )


def get_quality_score(record: dict[str, Any]) -> int:
    value = record.get("quality_score", 0)

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def get_identity_status(record: dict[str, Any]) -> str:
    identity = record.get("identity_verification")

    if isinstance(identity, dict):
        value = identity.get("status")
        if value:
            return text(value).lower()

    value = (
        record.get("identity_status")
        or record.get("verification_status")
        or ""
    )

    return text(value).lower()


def identity_result(status: str) -> tuple[str, str]:
    normalized = (
        status.replace("-", "_")
        .replace(" ", "_")
        .lower()
        .strip()
    )

    if normalized in {
        "verified_identity",
        "probable_identity",
    }:
        return (
            "PASS",
            "Identity evidence is sufficient for automated curation.",
        )

    if normalized in {
        "needs_review",
        "review_required",
    }:
        return (
            "REVIEW",
            "Identity evidence requires manual verification.",
        )

    if normalized in {
        "no_identity_evidence",
        "unverified",
        "",
        "unknown",
    }:
        return (
            "FAIL",
            "No adequate identity evidence was established.",
        )

    return (
        "REVIEW",
        f"Unrecognized identity status: {status}",
    )


def extract_dedup_pairs(report: Any) -> list[dict[str, Any]]:
    if isinstance(report, list):
        return [
            item for item in report
            if isinstance(item, dict)
        ]

    if not isinstance(report, dict):
        return []

    for key in (
        "comparisons",
        "flagged_comparisons",
        "results",
        "matches",
        "pairs",
    ):
        value = report.get(key)

        if isinstance(value, list):
            return [
                item for item in value
                if isinstance(item, dict)
            ]

    return []


def get_pair_ids(pair: dict[str, Any]) -> tuple[str, str]:
    left = text(
        pair.get("left_model_id")
        or pair.get("model_id_1")
        or pair.get("model_a")
        or pair.get("record_a")
        or pair.get("left_id")
    )

    right = text(
        pair.get("right_model_id")
        or pair.get("model_id_2")
        or pair.get("model_b")
        or pair.get("record_b")
        or pair.get("right_id")
    )

    return left, right


def get_pair_classification(pair: dict[str, Any]) -> str:
    return text(
        pair.get("classification")
        or pair.get("match_type")
        or pair.get("decision")
        or pair.get("status")
    ).lower()


def build_dedup_index(report: Any) -> dict[str, list[dict[str, Any]]]:
    pairs = extract_dedup_pairs(report)

    index: dict[str, list[dict[str, Any]]] = {}

    for pair in pairs:
        left, right = get_pair_ids(pair)

        if not left or not right:
            continue

        index.setdefault(left, []).append(pair)
        index.setdefault(right, []).append(pair)

    return index


def get_dedup_status(
    model_id: str,
    dedup_index: dict[str, list[dict[str, Any]]],
) -> tuple[str, list[dict[str, Any]]]:
    pairs = dedup_index.get(model_id, [])

    if not pairs:
        return "no_flag", []

    classifications = [
        get_pair_classification(pair)
        for pair in pairs
    ]

    if any(
        value in {
            "duplicate",
            "strong_duplicate",
            "confirmed_duplicate",
        }
        for value in classifications
    ):
        return "confirmed_duplicate", pairs

    if any(
        value in {
            "review_required",
            "possible_similarity",
            "similar",
        }
        for value in classifications
    ):
        return "similarity_flag", pairs

    return "no_flag", pairs


def dedup_reason(
    status: str,
    pairs: list[dict[str, Any]],
) -> str:
    if status == "confirmed_duplicate":
        return "Entity-resolution stage identified a confirmed duplicate."

    if status == "similarity_flag":
        classifications = sorted(
            {
                get_pair_classification(pair)
                for pair in pairs
                if get_pair_classification(pair)
            }
        )

        return (
            "Entity-resolution found similarity evidence "
            f"({', '.join(classifications)}); flag retained for audit."
        )

    return "No entity-resolution duplicate flag."


def decide(
    score: int,
    identity_status: str,
    dedup_status: str,
) -> tuple[str, str]:
    identity_state, identity_reason = identity_result(
        identity_status
    )

    # 1. Confirmed duplicate always rejected.
    if dedup_status == "confirmed_duplicate":
        return (
            "REJECT",
            "Confirmed duplicate detected.",
        )

    # 2. Identity failure means the record is not trusted enough
    #    for the final dataset.
    if identity_state == "FAIL":
        return (
            "REJECT",
            identity_reason,
        )

    # 3. Identity ambiguity still requires human review.
    if identity_state == "REVIEW":
        return (
            "REVIEW",
            identity_reason,
        )

    # 4. Verified + strong quality.
    if score >= 80:
        if dedup_status == "similarity_flag":
            return (
                "ACCEPT",
                "Verified identity and high quality score; "
                "similarity flag retained for audit but is not a "
                "decision blocker.",
            )

        return (
            "ACCEPT",
            "Verified identity and high quality score.",
        )

    # 5. Verified + medium quality.
    if score >= 70:
        return (
            "REVIEW",
            "Verified identity but quality score is below "
            "the preferred 80-point acceptance threshold.",
        )

    # 6. Verified + insufficient quality.
    return (
        "REJECT",
        "Quality score is below the preferred minimum threshold.",
    )


def enrich_record(
    record: dict[str, Any],
    dedup_index: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    model_id = get_model_id(record)
    model_name = get_model_name(record)

    score = get_quality_score(record)
    identity_status = get_identity_status(record)

    dedup_status, dedup_pairs = get_dedup_status(
        model_id,
        dedup_index,
    )

    decision, reason = decide(
        score=score,
        identity_status=identity_status,
        dedup_status=dedup_status,
    )

    enriched = dict(record)

    enriched["curation"] = {
        "decision": decision,
        "reason": reason,
        "model_id": model_id,
        "model_name": model_name,
        "quality_score": score,
        "identity_status": identity_status,
        "dedup_status": dedup_status,

        # Similarity remains an audit flag rather than a blocker.
        "dedup_review_flag": dedup_status == "similarity_flag",

        # Human review is needed only where the actual decision
        # remains uncertain.
        "review_required": decision == "REVIEW",

        "dedup_evidence_count": len(dedup_pairs),
    }

    return enriched


def create_summary(
    records: list[dict[str, Any]],
) -> dict[str, Any]:

    decisions: dict[str, int] = {
        "ACCEPT": 0,
        "REVIEW": 0,
        "REJECT": 0,
    }

    dedup_statuses: dict[str, int] = {}
    identity_statuses: dict[str, int] = {}
    score_bands: dict[str, int] = {}

    accepted_scores: list[int] = []

    for record in records:
        curation = record.get("curation", {})

        decision = text(
            curation.get("decision")
        ) or "UNKNOWN"

        decisions[decision] = (
            decisions.get(decision, 0) + 1
        )

        dedup = text(
            curation.get("dedup_status")
        ) or "unknown"

        dedup_statuses[dedup] = (
            dedup_statuses.get(dedup, 0) + 1
        )

        identity = text(
            curation.get("identity_status")
        ) or "unknown"

        identity_statuses[identity] = (
            identity_statuses.get(identity, 0) + 1
        )

        score = get_quality_score(record)

        if score >= 90:
            band = "exceptional"
        elif score >= 80:
            band = "excellent"
        elif score >= 70:
            band = "good"
        elif score >= 60:
            band = "borderline"
        else:
            band = "reject_candidate"

        score_bands[band] = (
            score_bands.get(band, 0) + 1
        )

        if decision == "ACCEPT":
            accepted_scores.append(score)

    return {
        "input_records": len(records),
        "decisions": decisions,
        "identity_statuses": identity_statuses,
        "dedup_statuses": dedup_statuses,
        "quality_distribution": score_bands,
        "accepted_records": decisions.get("ACCEPT", 0),
        "review_records": decisions.get("REVIEW", 0),
        "rejected_records": decisions.get("REJECT", 0),
        "accepted_score_min": (
            min(accepted_scores)
            if accepted_scores
            else None
        ),
        "accepted_score_max": (
            max(accepted_scores)
            if accepted_scores
            else None
        ),
    }


def main() -> None:
    ensure_directories()

    identity_records = load_json(IDENTITY_FILE)
    scored_records = load_json(SCORED_FILE)
    dedup_report = load_json(DEDUP_FILE)

    if not isinstance(identity_records, list):
        raise ValueError(
            "Identity file must contain a JSON list."
        )

    if not isinstance(scored_records, list):
        raise ValueError(
            "Scored file must contain a JSON list."
        )

    logging.info(
        "Identity records: %d",
        len(identity_records),
    )

    logging.info(
        "Scored records: %d",
        len(scored_records),
    )

    identity_by_id: dict[str, dict[str, Any]] = {}

    for record in identity_records:
        model_id = get_model_id(record)

        if model_id:
            identity_by_id[model_id] = record

    dedup_index = build_dedup_index(
        dedup_report
    )

    logging.info(
        "Deduplication index entries: %d",
        len(dedup_index),
    )

    curated: list[dict[str, Any]] = []

    for index, scored in enumerate(
        scored_records,
        start=1,
    ):
        model_id = get_model_id(scored)
        model_name = get_model_name(scored)

        logging.info(
            "[%d/%d] Curating %s",
            index,
            len(scored_records),
            model_name,
        )

        merged = dict(scored)

        identity_record = identity_by_id.get(
            model_id
        )

        if identity_record:
            if "identity_verification" in identity_record:
                merged["identity_verification"] = (
                    identity_record["identity_verification"]
                )

            if "verification" in identity_record:
                merged["verification"] = (
                    identity_record["verification"]
                )

        curated.append(
            enrich_record(
                merged,
                dedup_index,
            )
        )

    summary = create_summary(curated)

    save_json(
        OUTPUT_FILE,
        curated,
    )

    report = {
        "pipeline": "AIOrbit Models Final Curation v2",
        "methodology": {
            "accept_threshold": 80,
            "review_threshold": 70,
            "confirmed_duplicate": "reject",
            "similarity_flag": "audit_only",
            "identity_requirement": (
                "probable_identity_or_verified_identity"
            ),
        },
        "input_files": {
            "identity": str(IDENTITY_FILE),
            "scored": str(SCORED_FILE),
            "deduplication": str(DEDUP_FILE),
        },
        "output_file": str(OUTPUT_FILE),
        "summary": summary,
    }

    save_json(
        REPORT_FILE,
        report,
    )

    logging.info("")
    logging.info(
        "=============================================="
    )
    logging.info(
        "FINAL CURATION V2 COMPLETED"
    )
    logging.info(
        "=============================================="
    )
    logging.info(
        "Output: %s",
        OUTPUT_FILE,
    )
    logging.info(
        "Report: %s",
        REPORT_FILE,
    )
    logging.info("")
    logging.info(
        "Input records: %d",
        summary["input_records"],
    )
    logging.info(
        "ACCEPT: %d",
        summary["accepted_records"],
    )
    logging.info(
        "REVIEW: %d",
        summary["review_records"],
    )
    logging.info(
        "REJECT: %d",
        summary["rejected_records"],
    )
    logging.info("")

    logging.info("Quality distribution:")

    for key, value in sorted(
        summary["quality_distribution"].items()
    ):
        logging.info(
            "  %s: %d",
            key,
            value,
        )

    logging.info("")

    logging.info("Deduplication status:")

    for key, value in sorted(
        summary["dedup_statuses"].items()
    ):
        logging.info(
            "  %s: %d",
            key,
            value,
        )

    logging.info("")

    logging.info("Identity status:")

    for key, value in sorted(
        summary["identity_statuses"].items()
    ):
        logging.info(
            "  %s: %d",
            key,
            value,
        )


if __name__ == "__main__":
    main()