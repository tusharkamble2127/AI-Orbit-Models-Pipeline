from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_canonical_enriched.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_final_normalized.json"


FINAL_FIELDS = [
    "model_id",
    "model_name",
    "model_family",
    "company_provider",
    "official_website",
    "release_date",
    "last_updated",
    "model_type_task",
    "description",
    "modalities",
    "context_window",
    "maximum_output",
    "reasoning",
    "function_tool_calling",
    "structured_output",
    "vision",
    "audio",
    "multimodal",
    "embeddings",
    "api_platforms",
    "open_source_weights",
    "license",
    "huggingface",
    "github",
    "documentation",
    "pricing",
    "benchmarks",
    "adoption_downloads",
    "quality_score",
    "quality_band",
    "last_verified",
    "source_urls",
    "identity_verification",
    "curation_status",
    "variant_review",
]


OFFICIAL_PROVIDER_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "ai.google.dev",
    "google.com",
    "deepseek.com",
    "x.ai",
    "mistral.ai",
    "moonshot.ai",
    "z.ai",
    "qwen.ai",
    "ai.meta.com",
    "meta.ai",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(
        ("http://", "https://")
    )


def get_domain(url: str) -> str:
    try:
        return (
            urlparse(url).netloc.lower().removeprefix("www.")
        )
    except Exception:
        return ""


def extract_urls(value: Any) -> list[str]:
    urls = []
    seen = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, str):
            if is_http_url(obj) and obj not in seen:
                seen.add(obj)
                urls.append(obj)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

        elif isinstance(obj, dict):
            for item in obj.values():
                walk(item)

    walk(value)
    return urls


def unique(values: list[Any]) -> list[Any]:
    result = []
    seen = set()

    for value in values:
        if value in (None, "", [], {}):
            continue

        key = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


def get_enrichment_urls(enrichment: dict) -> list[str]:
    urls = []

    selected = enrichment.get("selected_official_source")
    if isinstance(selected, dict):
        selected_url = selected.get("url")
        if is_http_url(selected_url):
            urls.append(selected_url)

    inspected = enrichment.get("inspected_sources")
    if isinstance(inspected, list):
        for source in inspected:
            if not isinstance(source, dict):
                continue

            for key in ("url", "final_url"):
                value = source.get(key)
                if is_http_url(value):
                    urls.append(value)

    return unique(urls)


def get_selected_source(enrichment: dict) -> dict | None:
    selected = enrichment.get("selected_official_source")

    if isinstance(selected, dict):
        url = selected.get("url")
        if is_http_url(url):
            return selected

    return None


def get_huggingface_urls(
    record: dict,
    enrichment: dict,
) -> list[str]:
    urls = []

    # Existing weights / source data.
    urls.extend(extract_urls(record.get("weights")))

    # Official enrichment.
    urls.extend(get_enrichment_urls(enrichment))

    return unique([
        url
        for url in urls
        if "huggingface.co" in get_domain(url)
    ])


def get_github_urls(
    record: dict,
    enrichment: dict,
) -> list[str]:
    urls = []

    urls.extend(extract_urls(record.get("source")))
    urls.extend(extract_urls(record.get("providers")))
    urls.extend(extract_urls(record.get("provider_docs")))
    urls.extend(extract_urls(record.get("provider_apis")))
    urls.extend(get_enrichment_urls(enrichment))

    return unique([
        url
        for url in urls
        if "github.com" in get_domain(url)
    ])


def get_documentation_urls(
    record: dict,
    enrichment: dict,
) -> list[str]:
    urls = []

    urls.extend(extract_urls(record.get("provider_docs")))

    inspected = enrichment.get("inspected_sources")

    if isinstance(inspected, list):
        for source in inspected:
            if not isinstance(source, dict):
                continue

            url = source.get("final_url") or source.get("url")

            if not is_http_url(url):
                continue

            domain = get_domain(url)

            if (
                domain.startswith("docs.")
                or domain.startswith("developer.")
                or domain.startswith("developers.")
                or "/docs" in url.lower()
            ):
                urls.append(url)

    return unique(urls)


def get_api_urls(record: dict) -> list[str]:
    return unique(extract_urls(record.get("provider_apis")))


def get_official_website(
    record: dict,
    enrichment: dict,
) -> str | None:
    selected = get_selected_source(enrichment)

    if selected:
        url = selected.get("url")
        domain = selected.get("domain") or get_domain(url)

        # Important:
        # HF/GitHub/aggregators are supporting sources,
        # NOT automatically the official website.
        if domain in OFFICIAL_PROVIDER_DOMAINS:
            return url

    # Check source URLs only when they clearly belong to provider domain.
    candidate_urls = (
        extract_urls(record.get("source"))
        + get_enrichment_urls(enrichment)
    )

    for url in candidate_urls:
        domain = get_domain(url)

        if domain in OFFICIAL_PROVIDER_DOMAINS:
            return url

    return None


def model_type_task(record: dict) -> list[str]:
    values = []

    if record.get("model_family"):
        values.append(record["model_family"])

    modalities = record.get("modalities")

    if isinstance(modalities, list):
        values.extend(
            str(x)
            for x in modalities
            if x not in (None, "")
        )

    if record.get("reasoning") is True:
        values.append("reasoning")

    if record.get("tool_calling") is True:
        values.append("tool calling")

    return unique(values)


def normalize_record(record: dict) -> dict:
    enrichment = record.get("official_enrichment") or {}

    if not isinstance(enrichment, dict):
        enrichment = {}

    source_urls = unique(
        extract_urls(record.get("source"))
        + extract_urls(record.get("weights"))
        + extract_urls(record.get("providers"))
        + extract_urls(record.get("provider_docs"))
        + extract_urls(record.get("provider_apis"))
        + get_enrichment_urls(enrichment)
    )

    modalities = record.get("modalities")

    if not isinstance(modalities, list):
        modalities = (
            []
            if modalities is None
            else [modalities]
        )

    modalities = unique(
        [
            str(x)
            for x in modalities
            if x not in (None, "")
        ]
    )

    modality_set = {
        str(x).lower()
        for x in modalities
    }

    identity = record.get("identity_verification") or {}
    verification = record.get("verification") or {}

    quality_score = record.get("quality_score")

    try:
        quality_score = float(quality_score)
    except (TypeError, ValueError):
        quality_score = None

    return {
        "model_id": record.get("model_id"),

        "model_name": record.get("model_name"),

        "model_family": record.get("model_family"),

        "company_provider": (
            str(record.get("model_id")).split("/", 1)[0]
            if "/" in str(record.get("model_id") or "")
            else None
        ),

        "official_website": get_official_website(
            record,
            enrichment,
        ),

        "release_date": record.get("release_date"),

        "last_updated": record.get("last_updated"),

        "model_type_task": model_type_task(record),

        "description": record.get("description"),

        "modalities": modalities,

        "context_window": record.get("context_window"),

        "maximum_output": record.get("maximum_output"),

        "reasoning": (
            record.get("reasoning")
            if isinstance(record.get("reasoning"), bool)
            else None
        ),

        "function_tool_calling": (
            record.get("tool_calling")
            if isinstance(record.get("tool_calling"), bool)
            else None
        ),

        "structured_output": (
            record.get("structured_output")
            if isinstance(record.get("structured_output"), bool)
            else None
        ),

        "vision": (
            "vision" in modality_set
        ),

        "audio": (
            "audio" in modality_set
        ),

        "multimodal": (
            len(modality_set) > 1
            if modality_set
            else None
        ),

        # Do not infer embedding support.
        "embeddings": None,

        "api_platforms": get_api_urls(record),

        "open_source_weights": (
            record.get("open_weights")
            if isinstance(record.get("open_weights"), bool)
            else None
        ),

        # Do not infer license.
        "license": None,

        "huggingface": get_huggingface_urls(
            record,
            enrichment,
        ),

        "github": get_github_urls(
            record,
            enrichment,
        ),

        "documentation": get_documentation_urls(
            record,
            enrichment,
        ),

        # Do not infer pricing.
        "pricing": None,

        "benchmarks": (
            record.get("benchmarks")
            if record.get("benchmarks")
            else None
        ),

        # Do not infer adoption/downloads.
        "adoption_downloads": None,

        "quality_score": quality_score,

        "quality_band": record.get("quality_band"),

        "last_verified": (
            verification.get("checked_at")
            or identity.get("checked_at")
            or enrichment.get("verified_at")
        ),

        "source_urls": source_urls,

        "identity_verification": {
            "status": identity.get("status"),
            "strong_matches": identity.get(
                "strong_matches"
            ),
            "probable_matches": identity.get(
                "probable_matches"
            ),
            "requires_manual_review": verification.get(
                "requires_manual_review"
            ),
        },

        "curation_status": record.get(
            "curation_status"
        ),

        "variant_review": record.get(
            "variant_resolution"
        ) or {},
    }


def validate(records: list[dict]) -> dict:
    expected = set(FINAL_FIELDS)

    schema_errors = []

    for index, record in enumerate(records):
        keys = set(record.keys())

        if keys != expected:
            schema_errors.append(
                {
                    "index": index,
                    "missing": sorted(
                        expected - keys
                    ),
                    "extra": sorted(
                        keys - expected
                    ),
                }
            )

    model_ids = [
        record.get("model_id")
        for record in records
    ]

    duplicate_ids = sorted(
        {
            model_id
            for model_id in model_ids
            if model_id
            and model_ids.count(model_id) > 1
        }
    )

    return {
        "valid": (
            not schema_errors
            and not duplicate_ids
        ),
        "schema_errors": schema_errors,
        "duplicate_model_ids": duplicate_ids,
    }


def main() -> None:
    ensure_directories()

    payload = load_json(INPUT_FILE)

    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            "Expected 'records' list in "
            "models_canonical_enriched.json"
        )

    normalized_records = [
        normalize_record(record)
        for record in records
    ]

    validation = validate(
        normalized_records
    )

    output = {
        "metadata": {
            "dataset_name": (
                "AIOrbit Models Final Normalized "
                "Candidate Dataset"
            ),
            "schema_version": "1.2",
            "record_count": len(
                normalized_records
            ),
            "field_count": len(FINAL_FIELDS),
            "fields": FINAL_FIELDS,
            "source_file": INPUT_FILE.name,
            "official_enrichment_used": True,
            "validation": validation,
        },
        "records": normalized_records,
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

    print(
        f"Input records: "
        f"{len(records)}"
    )

    print(
        f"Output records: "
        f"{len(normalized_records)}"
    )

    print(
        f"Fields per record: "
        f"{len(FINAL_FIELDS)}"
    )

    print(
        f"Schema valid: "
        f"{validation['valid']}"
    )

    print(
        "Duplicate model IDs: "
        f"{len(validation['duplicate_model_ids'])}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()