from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from src.config import INTERMEDIATE_DATA_DIR, FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_review_resolved.json"
OUTPUT_FILE = FINAL_DATA_DIR / "models_official_enriched.json"
REPORT_FILE = FINAL_DATA_DIR / "official_enrichment_report.json"
CACHE_FILE = INTERMEDIATE_DATA_DIR / "official_enrichment_cache.json"

MAX_WORKERS = 10
REQUEST_TIMEOUT = 20
MAX_HTML_BYTES = 1_500_000

USER_AGENT = (
    "AIOrbit-Models-Pipeline/1.0 "
    "(official-source-enrichment; research/verification)"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

_thread_local = threading.local()


def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
            }
        )
        _thread_local.session = session

    return _thread_local.session


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"File not found: {path}")

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

    if isinstance(value, list):
        return " ".join(
            str(item)
            for item in value
            if item is not None
        )

    return str(value).strip()


def normalize(value: Any) -> str:
    """Normalize free text for matching while preserving underscore-style statuses."""
    value = text(value).lower().strip()
    value = re.sub(r"[^a-z0-9_\s-]+", " ", value)
    value = re.sub(r"[\s-]+", "_", value)
    return value.strip("_")


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
    try:
        return int(float(record.get("quality_score", 0)))
    except (TypeError, ValueError):
        return 0


def get_identity_status(record: dict[str, Any]) -> str:
    # The authoritative field for this stage is the resolved identity
    # status produced by review_resolution.py.
    resolution = record.get("review_resolution")
    if isinstance(resolution, dict):
        value = resolution.get("resolved_identity_status")
        if value:
            return normalize(value)

    # Fallback for records that have not passed review resolution.
    identity = record.get("identity_verification")
    if isinstance(identity, dict):
        value = identity.get("status")
        if value:
            return normalize(value)

    return ""


def provider_domain_from_url(url: str) -> str:
    if not url:
        return ""

    try:
        hostname = urlparse(url).hostname or ""
    except ValueError:
        return ""

    hostname = hostname.lower().strip()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def root_domain(url: str) -> str:
    hostname = provider_domain_from_url(url)

    if not hostname:
        return ""

    parts = hostname.split(".")

    if len(parts) < 2:
        return hostname

    return ".".join(parts[-2:])


def is_huggingface(url: str) -> bool:
    return root_domain(url) == "huggingface.co"


def is_github(url: str) -> bool:
    return root_domain(url) == "github.com"


def collect_urls(record: dict[str, Any]) -> list[dict[str, str]]:
    """
    Collect source URLs already present in the pipeline.

    Priority:
    1. provider docs
    2. provider APIs
    3. weight/HF sources
    4. previous verification sources
    5. previous identity sources
    """

    results: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: Any, source_type: str) -> None:
        url = text(url)

        if not url:
            return

        if url in seen:
            return

        seen.add(url)

        results.append(
            {
                "url": url,
                "source_type": source_type,
            }
        )

    for url in record.get("provider_docs") or []:
        add(url, "provider_documentation")

    for url in record.get("provider_apis") or []:
        add(url, "provider_api")

    for item in record.get("weights") or []:
        if isinstance(item, dict):
            add(
                item.get("url"),
                "weight_or_huggingface",
            )

    verification = record.get("verification") or {}

    if isinstance(verification, dict):
        for item in verification.get("sources_checked") or []:
            if isinstance(item, dict):
                add(
                    item.get("final_url") or item.get("url"),
                    item.get("source_type")
                    or "verified_source",
                )

    identity = record.get("identity_verification") or {}

    if isinstance(identity, dict):
        for item in identity.get("sources") or []:
            if isinstance(item, dict):
                add(
                    item.get("final_url") or item.get("url"),
                    item.get("source_type")
                    or "identity_source",
                )

    return results


def cache_key(url: str) -> str:
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def load_cache() -> dict[str, Any]:
    cache = load_json(
        CACHE_FILE,
        default={},
    )

    if not isinstance(cache, dict):
        return {}

    return cache


def save_cache(cache: dict[str, Any]) -> None:
    save_json(
        CACHE_FILE,
        cache,
    )


def extract_page_metadata(
    html: str,
) -> dict[str, Any]:
    soup = BeautifulSoup(
        html,
        "lxml",
    )

    title = ""

    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True,
        )

    description = ""

    meta_description = soup.find(
        "meta",
        attrs={"name": "description"},
    )

    if meta_description:
        description = text(
            meta_description.get("content")
        )

    og_title = ""

    og_title_tag = soup.find(
        "meta",
        attrs={"property": "og:title"},
    )

    if og_title_tag:
        og_title = text(
            og_title_tag.get("content")
        )

    og_description = ""

    og_description_tag = soup.find(
        "meta",
        attrs={"property": "og:description"},
    )

    if og_description_tag:
        og_description = text(
            og_description_tag.get("content")
        )

    text_content = soup.get_text(
        " ",
        strip=True,
    )

    text_content = re.sub(
        r"\s+",
        " ",
        text_content,
    )

    # Avoid storing huge page bodies.
    text_content = text_content[:25_000]

    return {
        "title": title,
        "meta_description": description,
        "og_title": og_title,
        "og_description": og_description,
        "visible_text_sample": text_content,
    }


def fetch_url(url: str) -> dict[str, Any]:
    key = cache_key(url)

    try:
        session = get_session()

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )

        content_type = text(
            response.headers.get(
                "Content-Type"
            )
        )

        final_url = response.url

        chunks: list[bytes] = []
        total_bytes = 0

        try:
            for chunk in response.iter_content(
                chunk_size=16_384
            ):
                if not chunk:
                    continue

                remaining = (
                    MAX_HTML_BYTES - total_bytes
                )

                if remaining <= 0:
                    break

                chunk = chunk[:remaining]
                chunks.append(chunk)
                total_bytes += len(chunk)

                if total_bytes >= MAX_HTML_BYTES:
                    break
        finally:
            response.close()

        raw = b"".join(chunks)

        is_html = (
            "html" in content_type.lower()
            or not content_type
        )

        metadata: dict[str, Any] = {}

        if is_html and raw:
            encoding = (
                response.encoding
                or "utf-8"
            )

            html = raw.decode(
                encoding,
                errors="replace",
            )

            metadata = extract_page_metadata(
                html
            )

        return {
            "cache_key": key,
            "url": url,
            "final_url": final_url,
            "domain": provider_domain_from_url(
                final_url
            ),
            "root_domain": root_domain(
                final_url
            ),
            "status_code": response.status_code,
            "content_type": content_type,
            "reachable": (
                200 <= response.status_code < 400
            ),
            "redirected": (
                final_url.rstrip("/")
                != url.rstrip("/")
            ),
            "error": None,
            "metadata": metadata,
        }

    except requests.RequestException as exc:
        return {
            "cache_key": key,
            "url": url,
            "final_url": "",
            "domain": provider_domain_from_url(
                url
            ),
            "root_domain": root_domain(url),
            "status_code": None,
            "content_type": "",
            "reachable": False,
            "redirected": False,
            "error": str(exc),
            "metadata": {},
        }

    except Exception as exc:
        return {
            "cache_key": key,
            "url": url,
            "final_url": "",
            "domain": provider_domain_from_url(
                url
            ),
            "root_domain": root_domain(url),
            "status_code": None,
            "content_type": "",
            "reachable": False,
            "redirected": False,
            "error": str(exc),
            "metadata": {},
        }


def score_source_identity(
    model_name: str,
    model_id: str,
    source: dict[str, Any],
) -> dict[str, Any]:

    normalized_name = normalize(
        model_name
    )

    normalized_id = normalize(
        model_id
    )

    final_url = normalize(
        source.get("final_url")
        or source.get("url")
    )

    metadata = source.get(
        "metadata"
    ) or {}

    title = normalize(
        metadata.get("title")
    )

    og_title = normalize(
        metadata.get("og_title")
    )

    description = normalize(
        metadata.get("meta_description")
        or metadata.get("og_description")
    )

    visible_text = normalize(
        metadata.get("visible_text_sample")
    )

    evidence: list[str] = []
    score = 0

    title_matches_name = (
        normalized_name
        and normalized_name in title
    )

    title_matches_og = (
        normalized_name
        and normalized_name in og_title
    )

    id_in_url = (
        normalized_id
        and normalized_id in final_url
    )

    name_in_text = (
        normalized_name
        and normalized_name in visible_text
    )

    name_in_description = (
        normalized_name
        and normalized_name in description
    )

    if title_matches_name:
        score += 40
        evidence.append(
            "Model name appears in page title."
        )

    elif title_matches_og:
        score += 35
        evidence.append(
            "Model name appears in OpenGraph title."
        )

    if id_in_url:
        score += 25
        evidence.append(
            "Model ID appears in verified final URL."
        )

    if name_in_text:
        score += 20
        evidence.append(
            "Model name appears in visible page text."
        )

    if name_in_description:
        score += 10
        evidence.append(
            "Model name appears in page description."
        )

    source_domain = root_domain(
        source.get("final_url")
        or source.get("url")
    )

    if source_domain not in {
        "huggingface.co",
        "github.com",
    } and source_domain:
        score += 5
        evidence.append(
            "Source belongs to a non-HuggingFace/GitHub domain "
            "that can represent a provider/official site."
        )

    if score >= 70:
        status = "strong_match"

    elif score >= 45:
        status = "probable_match"

    elif score >= 20:
        status = "weak_match"

    else:
        status = "unverified"

    return {
        "status": status,
        "score": min(score, 100),
        "evidence": evidence,
    }


def choose_official_source(
    model_name: str,
    model_id: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any] | None:

    ranked: list[tuple[int, dict[str, Any]]] = []

    for source in sources:
        if not source.get("reachable"):
            continue

        identity = score_source_identity(
            model_name,
            model_id,
            source,
        )

        score = identity["score"]

        domain = root_domain(
            source.get("final_url")
            or source.get("url")
        )

        source_type = text(
            source.get("source_type")
        ).lower()

        # Prefer official provider documentation over
        # third-party/community sources.
        source_bonus = 0

        if source_type in {
            "provider_documentation",
            "provider_model_page",
            "official",
        }:
            source_bonus += 30

        if domain in {
            "huggingface.co",
            "github.com",
        }:
            source_bonus -= 10

        ranked.append(
            (
                score + source_bonus,
                {
                    "source": source,
                    "identity": identity,
                },
            )
        )

    if not ranked:
        return None

    ranked.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best = ranked[0]

    if best["identity"]["score"] < 45:
        return None

    return {
        "selection_score": best_score,
        "url": (
            best["source"].get("final_url")
            or best["source"].get("url")
        ),
        "domain": root_domain(
            best["source"].get("final_url")
            or best["source"].get("url")
        ),
        "source_type": best["source"].get(
            "source_type"
        ),
        "identity": best["identity"],
    }


def process_url(
    url_info: dict[str, str],
    cache: dict[str, Any],
) -> dict[str, Any]:

    url = url_info["url"]
    key = cache_key(url)

    if key in cache:
        cached = dict(
            cache[key]
        )

        cached["from_cache"] = True
        cached["source_type"] = (
            url_info.get("source_type")
            or cached.get("source_type")
        )

        return cached

    result = fetch_url(url)

    result["source_type"] = (
        url_info.get("source_type")
        or "unknown"
    )

    result["from_cache"] = False

    cache[key] = result

    return result


def main() -> None:
    ensure_directories()

    records = load_json(
        INPUT_FILE
    )

    if not isinstance(records, list):
        raise ValueError(
            "Input file must contain a JSON list."
        )

    # ---------------------------------------------------------------
    # Select strong first-batch candidates:
    # probable identity + quality >= 70
    # ---------------------------------------------------------------

    candidates = []

    for record in records:
        resolution = record.get("review_resolution") or {}
        identity_status = ""

        if isinstance(resolution, dict):
            identity_status = normalize(
                resolution.get("resolved_identity_status")
            )

        if not identity_status:
            identity_status = get_identity_status(record)

        quality_score = get_quality_score(record)

        if (
            identity_status.replace("-", "_").replace(" ", "_")
            == "probable_identity"
            and quality_score >= 70
        ):
            candidates.append(record)

    candidates.sort(
        key=lambda record: (
            get_quality_score(record),
            get_model_name(record).lower(),
        ),
        reverse=True,
    )

    logging.info(
        "Total records: %d",
        len(records),
    )

    logging.info(
        "Selected strong candidates: %d",
        len(candidates),
    )

    if not candidates:
        raise RuntimeError(
            "No strong candidates found."
        )

    # ---------------------------------------------------------------
    # Collect unique source URLs across selected records.
    # ---------------------------------------------------------------

    url_to_records: dict[str, list[str]] = {}

    for record in candidates:
        model_id = get_model_id(record)

        for item in collect_urls(record):
            url = item["url"]

            url_to_records.setdefault(
                url,
                [],
            ).append(model_id)

    logging.info(
        "Unique source URLs: %d",
        len(url_to_records),
    )

    cache = load_cache()
    cached_urls_before_run = len(cache)

    logging.info(
        "Cached URLs available: %d",
        cached_urls_before_run,
    )

    # ---------------------------------------------------------------
    # Fetch unique URLs concurrently.
    # ---------------------------------------------------------------

    url_results: dict[str, dict[str, Any]] = {}

    jobs = []

    for record in candidates:
        for item in collect_urls(record):
            jobs.append(item)

    unique_jobs: dict[str, dict[str, str]] = {}

    for item in jobs:
        unique_jobs.setdefault(
            item["url"],
            item,
        )

    logging.info(
        "URLs requiring inspection: %d",
        len(unique_jobs),
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        future_to_url = {
            executor.submit(
                process_url,
                item,
                cache,
            ): url
            for url, item in unique_jobs.items()
        }

        completed = 0
        total = len(future_to_url)

        for future in as_completed(
            future_to_url
        ):
            url = future_to_url[future]

            try:
                result = future.result()

            except Exception as exc:
                result = {
                    "url": url,
                    "final_url": "",
                    "domain": root_domain(url),
                    "root_domain": root_domain(url),
                    "status_code": None,
                    "content_type": "",
                    "reachable": False,
                    "redirected": False,
                    "error": str(exc),
                    "metadata": {},
                    "source_type": unique_jobs[
                        url
                    ].get(
                        "source_type"
                    ),
                    "from_cache": False,
                }

            url_results[url] = result

            completed += 1

            logging.info(
                "[%d/%d] Checked %s -> %s",
                completed,
                total,
                url,
                (
                    result.get("status_code")
                    or result.get("error")
                    or "unknown"
                ),
            )

    save_cache(cache)

    # ---------------------------------------------------------------
    # Build enriched output.
    # ---------------------------------------------------------------

    enriched_records: list[dict[str, Any]] = []

    reachable_sources_total = 0
    official_sources_total = 0
    identity_strong_total = 0
    identity_probable_total = 0

    for index, record in enumerate(
        candidates,
        start=1,
    ):
        model_id = get_model_id(record)
        model_name = get_model_name(record)

        source_entries = collect_urls(
            record
        )

        inspected_sources: list[dict[str, Any]] = []

        for item in source_entries:
            url = item["url"]

            result = url_results.get(
                url
            )

            if not result:
                result = cache.get(
                    cache_key(url)
                )

            if not result:
                continue

            result_copy = dict(result)

            identity = score_source_identity(
                model_name,
                model_id,
                result_copy,
            )

            result_copy["identity"] = identity

            inspected_sources.append(
                result_copy
            )

            if result_copy.get("reachable"):
                reachable_sources_total += 1

            if identity["status"] == "strong_match":
                identity_strong_total += 1

            elif identity["status"] == "probable_match":
                identity_probable_total += 1

        official_source = None

        ranked_sources: list[
            tuple[int, dict[str, Any]]
        ] = []

        for source in inspected_sources:
            identity = source.get(
                "identity"
            ) or {}

            rank = int(
                identity.get(
                    "score",
                    0,
                )
            )

            source_type = text(
                source.get(
                    "source_type"
                )
            ).lower()

            domain = root_domain(
                source.get(
                    "final_url"
                )
                or source.get(
                    "url"
                )
            )

            if source_type in {
                "provider_documentation",
                "provider_model_page",
                "official",
            }:
                rank += 30

            if domain in {
                "huggingface.co",
                "github.com",
            }:
                rank -= 10

            if (
                source.get(
                    "reachable"
                )
                is not True
            ):
                rank -= 50

            ranked_sources.append(
                (
                    rank,
                    source,
                )
            )

        ranked_sources.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        if ranked_sources:
            rank, best = ranked_sources[0]

            best_identity = best.get(
                "identity"
            ) or {}

            if (
                best.get("reachable")
                and best_identity.get(
                    "score",
                    0,
                ) >= 45
            ):
                official_source = {
                    "url": (
                        best.get("final_url")
                        or best.get("url")
                    ),
                    "domain": root_domain(
                        best.get("final_url")
                        or best.get("url")
                    ),
                    "source_type": best.get(
                        "source_type"
                    ),
                    "selection_score": rank,
                    "identity_score": best_identity.get(
                        "score"
                    ),
                    "identity_status": best_identity.get(
                        "status"
                    ),
                }

                official_sources_total += 1

        enriched = dict(record)

        enriched["official_enrichment"] = {
            "status": (
                "enriched"
                if official_source
                else "partial"
            ),
            "selected_official_source": official_source,
            "inspected_sources": inspected_sources,
            "source_count": len(
                inspected_sources
            ),
            "reachable_source_count": sum(
                1
                for source in inspected_sources
                if source.get(
                    "reachable"
                )
            ),
            "verified_at": (
                __import__(
                    "datetime"
                )
                .datetime.now(
                    __import__(
                        "datetime"
                    ).timezone.utc
                ).isoformat()
            ),
        }

        enriched_records.append(
            enriched
        )

        logging.info(
            "[%d/%d] Enriched %s | official=%s",
            index,
            len(candidates),
            model_name,
            (
                official_source.get(
                    "domain"
                )
                if official_source
                else "none"
            ),
        )

    report = {
        "pipeline": (
            "AIOrbit Models Official Source Enrichment"
        ),
        "input_records": len(records),
        "selected_candidates": len(
            candidates
        ),
        "unique_urls": len(
            unique_jobs
        ),
        "cached_urls_before_run": cached_urls_before_run,
        "reachable_sources": (
            reachable_sources_total
        ),
        "selected_official_sources": (
            official_sources_total
        ),
        "strong_identity_source_matches": (
            identity_strong_total
        ),
        "probable_identity_source_matches": (
            identity_probable_total
        ),
        "methodology": {
            "selection": (
                "probable_identity + quality_score >= 70"
            ),
            "official_source_preference": (
                "provider documentation/model page"
            ),
            "secondary_sources": (
                "Hugging Face/GitHub/provider APIs"
            ),
            "no_inference": True,
            "cache_enabled": True,
            "max_workers": MAX_WORKERS,
        },
    }

    save_json(
        OUTPUT_FILE,
        enriched_records,
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
        "OFFICIAL SOURCE ENRICHMENT COMPLETED"
    )
    logging.info(
        "=============================================="
    )
    logging.info(
        "Selected candidates: %d",
        len(candidates),
    )
    logging.info(
        "Unique URLs inspected: %d",
        len(unique_jobs),
    )
    logging.info(
        "Reachable sources: %d",
        reachable_sources_total,
    )
    logging.info(
        "Records with selected official source: %d",
        official_sources_total,
    )
    logging.info(
        "Strong source identity matches: %d",
        identity_strong_total,
    )
    logging.info(
        "Probable source identity matches: %d",
        identity_probable_total,
    )
    logging.info(
        "Output: %s",
        OUTPUT_FILE,
    )
    logging.info(
        "Report: %s",
        REPORT_FILE,
    )


if __name__ == "__main__":
    main()