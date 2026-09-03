from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.config import RAW_DATA_DIR, INTERMEDIATE_DATA_DIR, ensure_directories


logger = logging.getLogger(__name__)


class ModelExtractor:
    """
    Convert the raw Models.dev datasets into a normalized,
    provider-aware candidate model dataset.

    Important:
    - models.json is treated as the model-level source of truth.
    - api.json is used to enrich provider/deployment metadata.
    - We do NOT make one record per provider listing.
    """

    def __init__(
        self,
        models_path: Path | None = None,
        api_path: Path | None = None,
    ) -> None:
        self.models_path = (
            models_path
            if models_path is not None
            else RAW_DATA_DIR / "models_dev_models.json"
        )

        self.api_path = (
            api_path
            if api_path is not None
            else RAW_DATA_DIR / "models_dev_api.json"
        )

    @staticmethod
    def _load_json(path: Path) -> Any:
        """Load a JSON file safely."""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _normalize_string(value: Any) -> str | None:
        """Normalize a string while preserving meaningful content."""
        if value is None:
            return None

        if not isinstance(value, str):
            value = str(value)

        value = value.strip()

        return value or None

    @staticmethod
    def _unique_strings(values: list[str | None]) -> list[str]:
        """Return unique non-empty strings while preserving order."""
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not value:
                continue

            normalized = value.strip()

            if not normalized:
                continue

            key = normalized.casefold()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result

    def _build_provider_index(
        self,
        api_data: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Build:

            model_id -> [
                {
                    provider_id,
                    provider_name,
                    provider_doc,
                    provider_api,
                    provider_model
                },
                ...
            ]

        A model may be served by multiple providers.
        We preserve those relationships rather than duplicating the model.
        """
        provider_index: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for provider_id, provider in api_data.items():
            if not isinstance(provider, dict):
                continue

            provider_name = self._normalize_string(provider.get("name"))
            provider_doc = self._normalize_string(provider.get("doc"))
            provider_api = self._normalize_string(provider.get("api"))

            models = provider.get("models", {})

            if not isinstance(models, dict):
                continue

            for model_id, provider_model in models.items():
                if not isinstance(provider_model, dict):
                    continue

                normalized_model_id = self._normalize_string(
                    provider_model.get("id") or model_id
                )

                if not normalized_model_id:
                    continue

                provider_index[normalized_model_id].append(
                    {
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "provider_doc": provider_doc,
                        "provider_api": provider_api,
                        "model": provider_model,
                    }
                )

        return provider_index

    def _normalize_model(
        self,
        model_id: str,
        model: dict[str, Any],
        provider_records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert one raw model object into our canonical model structure."""

        providers = self._unique_strings(
            [
                record.get("provider_name")
                for record in provider_records
            ]
        )

        provider_ids = self._unique_strings(
            [
                record.get("provider_id")
                for record in provider_records
            ]
        )

        provider_docs = self._unique_strings(
            [
                record.get("provider_doc")
                for record in provider_records
            ]
        )

        provider_apis = self._unique_strings(
            [
                record.get("provider_api")
                for record in provider_records
            ]
        )

        modalities = model.get("modalities")

        if not isinstance(modalities, dict):
            modalities = {}

        limits = model.get("limit")

        if not isinstance(limits, dict):
            limits = {}

        weights = model.get("weights")

        if not isinstance(weights, list):
            weights = []

        benchmarks = model.get("benchmarks")

        if not isinstance(benchmarks, list):
            benchmarks = []

        record = {
            "model_id": self._normalize_string(
                model.get("id") or model_id
            ),
            "model_name": self._normalize_string(
                model.get("name")
            ),
            "model_family": self._normalize_string(
                model.get("family")
            ),
            "description": self._normalize_string(
                model.get("description")
            ),

            "release_date": self._normalize_string(
                model.get("release_date")
            ),
            "last_updated": self._normalize_string(
                model.get("last_updated")
            ),

            "reasoning": model.get("reasoning"),
            "tool_calling": model.get("tool_call"),
            "structured_output": model.get("structured_output"),

            "modalities": modalities,
            "open_weights": model.get("open_weights"),

            "context_window": limits.get("context"),
            "maximum_output": limits.get("output"),

            "weights": weights,
            "benchmarks": benchmarks,

            "providers": providers,
            "provider_ids": provider_ids,

            "provider_docs": provider_docs,
            "provider_apis": provider_apis,

            "source": {
                "primary": "Models.dev",
                "models_dev_model": (
                    "https://models.dev/"
                ),
                "models_dev_api": (
                    "https://models.dev/"
                ),
            },

            "processing": {
                "discovery_status": "candidate",
                "verification_status": "pending",
                "deduplication_status": "pending",
                "quality_score": None,
            },
        }

        return record

    def extract(self) -> list[dict[str, Any]]:
        """Load raw files and produce normalized model candidates."""
        models_data = self._load_json(self.models_path)
        api_data = self._load_json(self.api_path)

        if not isinstance(models_data, dict):
            raise TypeError(
                "Expected models_dev_models.json to contain a JSON object."
            )

        if not isinstance(api_data, dict):
            raise TypeError(
                "Expected models_dev_api.json to contain a JSON object."
            )

        provider_index = self._build_provider_index(api_data)

        logger.info("Raw Models.dev models: %d", len(models_data))
        logger.info("Raw Models.dev providers: %d", len(api_data))
        logger.info(
            "Provider/model relationships indexed: %d",
            len(provider_index),
        )

        records: list[dict[str, Any]] = []

        for model_id, model in models_data.items():
            if not isinstance(model, dict):
                logger.warning(
                    "Skipping malformed model record: %s",
                    model_id,
                )
                continue

            providers = provider_index.get(model_id, [])

            record = self._normalize_model(
                model_id=model_id,
                model=model,
                provider_records=providers,
            )

            records.append(record)

        records.sort(
            key=lambda item: (
                item.get("model_name") or "",
                item.get("model_id") or "",
            )
        )

        return records

    def save(self, records: list[dict[str, Any]]) -> Path:
        """Save normalized candidates to intermediate storage."""
        ensure_directories()

        output_path = (
            INTERMEDIATE_DATA_DIR / "models_dev_normalized.json"
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                records,
                file,
                ensure_ascii=False,
                indent=2,
            )

        return output_path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    extractor = ModelExtractor()

    try:
        records = extractor.extract()
        output_path = extractor.save(records)

        print()
        print("Models.dev normalization completed successfully.")
        print(f"Normalized records: {len(records)}")
        print(f"Output: {output_path}")

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        logger.error("Extraction failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()