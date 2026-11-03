"""Centralized environment configuration for the extraction pipeline."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
OCR_DATA_DIR = DATA_DIR / "ocr"
PROMPTS_DIR = PROJECT_ROOT / "src" / "prompts"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str
    google_cloud_location: str
    gcs_bucket: str
    bq_dataset: str
    gemini_model: str
    docai_location: str
    docai_processor_id: str
    courtlistener_token: str
    max_workers: int
    default_doc_limit: int
    gemini_input_cost_per_million_tokens: float | None
    gemini_output_cost_per_million_tokens: float | None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        return cls(
            google_cloud_project=_required("GOOGLE_CLOUD_PROJECT"),
            google_cloud_location=_required("GOOGLE_CLOUD_LOCATION"),
            gcs_bucket=_required("GCS_BUCKET"),
            bq_dataset=_required("BQ_DATASET"),
            gemini_model=_required("GEMINI_MODEL"),
            docai_location=_required("DOCAI_LOCATION"),
            docai_processor_id=_required("DOCAI_PROCESSOR_ID"),
            courtlistener_token=os.getenv("COURTLISTENER_TOKEN", "").strip(),
            max_workers=int(_required("MAX_WORKERS")),
            default_doc_limit=int(_required("DEFAULT_DOC_LIMIT")),
            gemini_input_cost_per_million_tokens=_optional_float("GEMINI_INPUT_COST_PER_MILLION_TOKENS"),
            gemini_output_cost_per_million_tokens=_optional_float("GEMINI_OUTPUT_COST_PER_MILLION_TOKENS"),
        )


def _optional_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None