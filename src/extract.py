"""Gemini extraction with constrained JSON output and Pydantic validation."""

from pathlib import Path

from google import genai
from google.genai import types

from config import PROMPTS_DIR, Settings
from src.schema import ExtractionRecord


def load_prompt(version: str) -> str:
	prompt_path = PROMPTS_DIR / f"{version}.txt"
	if not prompt_path.is_file():
		raise ValueError(f"Unknown prompt version: {version}")
	return prompt_path.read_text(encoding="utf-8")


def extract_document(text: str, prompt_version: str = "v1") -> tuple[ExtractionRecord, dict[str, int]]:
	"""Extract one record. Low temperature reduces variability for a single-answer task."""
	settings = Settings.from_env()
	client = genai.Client(
		vertexai=True,
		project=settings.google_cloud_project,
		location=settings.google_cloud_location,
	)
	response = client.models.generate_content(
		model=settings.gemini_model,
		contents=f"{load_prompt(prompt_version)}\n\nDOCUMENT TEXT:\n{text}",
		config=types.GenerateContentConfig(
			temperature=0.0,
			response_mime_type="application/json",
			response_schema=ExtractionRecord,
		),
	)
	record = ExtractionRecord.model_validate_json(response.text)
	usage = response.usage_metadata
	return record, {
		"input_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
		"output_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
	}