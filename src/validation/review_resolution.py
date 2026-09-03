from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.config import INTERMEDIATE_DATA_DIR, FINAL_DATA_DIR, ensure_directories


IDENTITY_FILE = INTERMEDIATE_DATA_DIR / "models_identity_verified.json"
SCORED_FILE = INTERMEDIATE_DATA_DIR / "models_scored.json"
CURATION_FILE = FINAL_DATA_DIR / "models_curated.json"

OUTPUT_FILE = FINAL_DATA_DIR / "models_review_resolved.json"
REPORT_FILE = FINAL_DATA_DIR / "review_resolution_report.json"

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


def normalize_status(value: Any) -> str:
    return (
        text(value)
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def get_quality_score(record: dict[str, Any]) -> int:
    try:
        return int(float(record.get("quality_score", 0)))
    except (TypeError, ValueError):
        return 0


def get_identity_data(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("identity_verification")

    if isinstance(value, dict):
        return value

    return {}


def get_verification_data(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("verification")

    if isinstance(value, dict):
        return value

    return {}


def extract_source_identity_evidence(
    identity_data: dict[str, Any],
) -> dict[str, Any]:

    sources = identity_data.get("sources") or []

    if not isinstance(sources, list):
        sources = []

    strong_count = 0
    probable_count = 0
    reachable_count = 0
    scores: list[int] = []
    evidence_items: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue

        if source.get("reachable") is True:
            reachable_count += 1

        nested = source.get("identity") or {}

        if not isinstance(nested, dict):
            continue

        status = normalize_status(
            nested.get("status")
        )

        if status in {
            "strong_match",
            "verified_identity",
            "verified",
        }:
            strong_count += 1

        elif status in {
            "probable_match",
            "probable_identity",
        }:
            probable_count += 1

        score = nested.get("score")

        if score is not None:
            try:
                scores.append(int(float(score)))
            except (TypeError, ValueError):
                pass

        evidence = nested.get("evidence") or []

        if isinstance(evidence, list):
            for item in evidence:
                item = text(item)

                if item and item not in evidence_items:
                    evidence_items.append(item)

    return {
        "strong_count": strong_count,
        "probable_count": probable_count,
        "reachable_count": reachable_count,
        "max_source_score": max(scores) if scores else 0,
        "evidence": evidence_items,
    }


def existing_identity_strength(
    record: dict[str, Any],
) -> dict[str, Any]:

    identity = get_identity_data(record)
    verification = get_verification_data(record)

    overall_status = normalize_status(
        identity.get("status")
    )

    strong_matches = int(
        identity.get("strong_matches") or 0
    )

    probable_matches = int(
        identity.get("probable_matches") or 0
    )

    source_evidence = extract_source_identity_evidence(
        identity
    )

    provider_verified = (
        verification.get("provider_source_verified")
        is True
    )

    secondary_verified = (
        verification.get("secondary_source_verified")
        is True
    )

    return {
        "overall_status": overall_status,
        "strong_matches": strong_matches,
        "probable_matches": probable_matches,
        "source_strong_count": source_evidence["strong_count"],
        "source_probable_count": source_evidence["probable_count"],
        "reachable_source_count": source_evidence["reachable_count"],
        "max_source_score": source_evidence["max_source_score"],
        "provider_source_verified": provider_verified,
        "secondary_source_verified": secondary_verified,
        "evidence": source_evidence["evidence"],
    }


def resolve_identity(
    record: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:

    evidence = existing_identity_strength(record)

    status = evidence["overall_status"]

    # ---------------------------------------------------------------
    # 1. Existing strong/probable result is authoritative.
    # ---------------------------------------------------------------

    if status == "verified_identity":
        return (
            "verified_identity",
            "Identity verifier already established verified identity.",
            evidence,
        )

    if status == "probable_identity":
        return (
            "probable_identity",
            "Identity verifier already established probable identity.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 2. Explicit strong matches.
    # ---------------------------------------------------------------

    if (
        evidence["strong_matches"] > 0
        or evidence["source_strong_count"] > 0
    ):
        return (
            "probable_identity",
            "At least one strong model-to-source identity match exists.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 3. Multiple probable matches are stronger than one.
    # ---------------------------------------------------------------

    probable_total = (
        evidence["probable_matches"]
        + evidence["source_probable_count"]
    )

    if probable_total >= 2:
        return (
            "probable_identity",
            "Multiple independent probable identity matches exist.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 4. Provider source verification is useful, but not sufficient
    #    by itself. Keep this as REVIEW unless identity matching
    #    evidence also exists.
    # ---------------------------------------------------------------

    if evidence["provider_source_verified"]:
        if evidence["max_source_score"] >= 60:
            return (
                "probable_identity",
                "Official provider source is verified and identity score provides supporting evidence.",
                evidence,
            )

        return (
            "needs_review",
            "Provider source is reachable/verified but identity matching is insufficient.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 5. Secondary verification alone is also not enough.
    # ---------------------------------------------------------------

    if evidence["secondary_source_verified"]:
        if evidence["max_source_score"] >= 70:
            return (
                "probable_identity",
                "Secondary source verification is supported by a strong identity score.",
                evidence,
            )

        return (
            "needs_review",
            "Secondary source exists but does not establish sufficient identity confidence.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 6. One weak probable match remains review.
    # ---------------------------------------------------------------

    if probable_total == 1:
        return (
            "needs_review",
            "Only one probable identity signal is available.",
            evidence,
        )

    # ---------------------------------------------------------------
    # 7. No evidence.
    # ---------------------------------------------------------------

    return (
        "no_identity_evidence",
        "No strong or sufficiently corroborated identity evidence exists.",
        evidence,
    )


def final_decision(
    record: dict[str, Any],
    resolved_identity: str,
) -> tuple[str, str]:

    score = get_quality_score(record)

    # Identity is insufficient.
    if resolved_identity == "no_identity_evidence":
        return (
            "REJECT",
            "Identity evidence is insufficient for the trusted final dataset.",
        )

    # Identity still ambiguous.
    if resolved_identity == "needs_review":
        return (
            "REVIEW",
            "Identity requires manual verification.",
        )

    # Verified/probable identity + high quality.
    if score >= 80:
        return (
            "ACCEPT",
            "Identity sufficiently established and quality score is 80+.",
        )

    # Mid-quality records remain review.
    if score >= 70:
        return (
            "REVIEW",
            "Identity sufficiently established but quality score is 70-79.",
        )

    # Low quality.
    return (
        "REJECT",
        "Identity is supported but quality score is below 70.",
    )


def main() -> None:
    ensure_directories()

    identity_records = load_json(IDENTITY_FILE)
    scored_records = load_json(SCORED_FILE)
    curated_records = load_json(CURATION_FILE)

    if not isinstance(identity_records, list):
        raise ValueError(
            "models_identity_verified.json must contain a list."
        )

    if not isinstance(scored_records, list):
        raise ValueError(
            "models_scored.json must contain a list."
        )

    if not isinstance(curated_records, list):
        raise ValueError(
            "models_curated.json must contain a list."
        )

    logging.info(
        "Identity records: %d",
        len(identity_records),
    )

    logging.info(
        "Scored records: %d",
        len(scored_records),
    )

    logging.info(
        "Curated records: %d",
        len(curated_records),
    )

    identity_by_id = {
        get_model_id(record): record
        for record in identity_records
        if get_model_id(record)
    }

    scored_by_id = {
        get_model_id(record): record
        for record in scored_records
        if get_model_id(record)
    }

    resolved_records: list[dict[str, Any]] = []

    identity_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}

    for index, curated in enumerate(
        curated_records,
        start=1,
    ):
        model_id = get_model_id(curated)
        model_name = get_model_name(curated)

        logging.info(
            "[%d/%d] Resolving %s",
            index,
            len(curated_records),
            model_name,
        )

        merged = dict(curated)

        # Use scored source as canonical scoring data.
        if model_id in scored_by_id:
            score_record = scored_by_id[model_id]

            for key, value in score_record.items():
                if key != "curation":
                    merged[key] = value

        # Use actual identity verification output.
        if model_id in identity_by_id:
            identity_record = identity_by_id[model_id]

            if "identity_verification" in identity_record:
                merged["identity_verification"] = (
                    identity_record["identity_verification"]
                )

            if "verification" in identity_record:
                merged["verification"] = (
                    identity_record["verification"]
                )

        resolved_identity, identity_reason, evidence = (
            resolve_identity(merged)
        )

        decision, decision_reason = final_decision(
            merged,
            resolved_identity,
        )

        identity_counts[resolved_identity] = (
            identity_counts.get(
                resolved_identity,
                0,
            ) + 1
        )

        decision_counts[decision] = (
            decision_counts.get(
                decision,
                0,
            ) + 1
        )

        merged["review_resolution"] = {
            "previous_identity_status": (
                evidence["overall_status"]
            ),
            "resolved_identity_status": (
                resolved_identity
            ),
            "identity_reason": identity_reason,
            "identity_evidence": evidence,
            "decision": decision,
            "decision_reason": decision_reason,
            "quality_score": get_quality_score(merged),
        }

        resolved_records.append(merged)

    report = {
        "pipeline": "AIOrbit Models Review Resolution v2.1",
        "input_records": len(curated_records),
        "resolved_records": len(resolved_records),
        "identity_resolution": identity_counts,
        "final_decisions": decision_counts,
        "methodology": {
            "existing_probable_or_verified_identity": "preserved",
            "strong_match": "probable_identity",
            "multiple_probable_matches": "probable_identity",
            "single_probable_match": "manual_review",
            "provider_reachability_only": "manual_review",
            "no_identity_evidence": "reject",
            "quality_accept_threshold": 80,
            "quality_review_threshold": 70,
        },
    }

    save_json(
        OUTPUT_FILE,
        resolved_records,
    )

    save_json(
        REPORT_FILE,
        report,
    )

    logging.info("")
    logging.info(
        "=============================================="
    )
    logging.info(
        "REVIEW RESOLUTION V2.1 COMPLETED"
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
    logging.info("Resolved identity:")

    for key, value in sorted(
        identity_counts.items()
    ):
        logging.info(
            "  %s: %d",
            key,
            value,
        )

    logging.info("")
    logging.info("Final decisions:")

    for key, value in sorted(
        decision_counts.items()
    ):
        logging.info(
            "  %s: %d",
            key,
            value,
        )


if __name__ == "__main__":
    main()