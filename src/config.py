from pathlib import Path


# Project root:
# .../AI-Orbit-Models-Pipeline/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERMEDIATE_DATA_DIR = DATA_DIR / "intermediate"
FINAL_DATA_DIR = DATA_DIR / "final"

MODELS_DEV_MODELS_URL = "https://models.dev/models.json"
MODELS_DEV_API_URL = "https://models.dev/api.json"
MODELS_DEV_CATALOG_URL = "https://models.dev/catalog.json"

REQUEST_TIMEOUT_SECONDS = 30

USER_AGENT = (
    "AIOrbit-Models-Pipeline/1.0 "
    "(data-engineering-internship; research/verification use)"
)


def ensure_directories() -> None:
    """Create required project directories if they do not exist."""
    for directory in (
        RAW_DATA_DIR,
        INTERMEDIATE_DATA_DIR,
        FINAL_DATA_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)