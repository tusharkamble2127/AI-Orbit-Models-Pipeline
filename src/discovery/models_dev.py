from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import requests

from src.config import (
    MODELS_DEV_API_URL,
    MODELS_DEV_MODELS_URL,
    RAW_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    ensure_directories,
)


logger = logging.getLogger(__name__)


class ModelsDevClient:
    """Client for downloading model metadata from models.dev."""

    def __init__(
        self,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
        user_agent: str = USER_AGENT,
    ) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )

    def _get_json(self, url: str) -> Any:
        """Fetch JSON from a URL with basic error handling."""
        logger.info("Fetching %s", url)

        response = self.session.get(
            url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    @staticmethod
    def _save_json(path: Path, data: Any) -> None:
        """Save JSON with UTF-8 encoding."""
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def fetch_models(self) -> Any:
        """Fetch provider-agnostic model metadata."""
        return self._get_json(MODELS_DEV_MODELS_URL)

    def fetch_api_catalog(self) -> Any:
        """Fetch provider/model serving metadata."""
        return self._get_json(MODELS_DEV_API_URL)

    def download_raw_data(self) -> tuple[Path, Path]:
        """
        Download models.dev datasets and save raw responses locally.

        Returns:
            Tuple containing paths to models.json and api.json.
        """
        ensure_directories()

        models_data = self.fetch_models()
        api_data = self.fetch_api_catalog()

        models_path = RAW_DATA_DIR / "models_dev_models.json"
        api_path = RAW_DATA_DIR / "models_dev_api.json"

        self._save_json(models_path, models_data)
        self._save_json(api_path, api_data)

        logger.info("Saved model metadata: %s", models_path)
        logger.info("Saved API metadata: %s", api_path)

        return models_path, api_path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    client = ModelsDevClient()

    try:
        models_path, api_path = client.download_raw_data()

        print()
        print("Models.dev collection completed successfully.")
        print(f"Models metadata: {models_path}")
        print(f"API metadata:    {api_path}")

    except requests.RequestException as exc:
        logger.error("Models.dev request failed: %s", exc)
        raise SystemExit(1) from exc

    except (OSError, ValueError, TypeError) as exc:
        logger.error("Failed to save/parse Models.dev data: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()