"""Run extraction concurrently with retry, checkpointing, and cost-aware logs."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time

from config import DATA_DIR, RAW_DATA_DIR, Settings
from src.extract import extract_document
from src.ocr import extract_text
from src.review import rebuild_review_queue


RESULTS_PATH = DATA_DIR / "extractions.jsonl"
RUN_LOG_PATH = DATA_DIR / "run_logs.jsonl"


def _estimated_cost(usage: dict[str, int], settings: Settings) -> float | None:
	if settings.gemini_input_cost_per_million_tokens is None or settings.gemini_output_cost_per_million_tokens is None:
		return None
	return round(
		usage["input_tokens"] * settings.gemini_input_cost_per_million_tokens / 1_000_000
		+ usage["output_tokens"] * settings.gemini_output_cost_per_million_tokens / 1_000_000,
		8,
	)


def _completed_ids(path: Path) -> set[str]:
	if not path.exists():
		return set()
	return {str(json.loads(line)["document_id"]) for line in path.read_text(encoding="utf-8").splitlines() if line}


def _is_retryable(error: Exception) -> bool:
	status = getattr(error, "code", None) or getattr(error, "status_code", None)
	return status in {429, 500, 502, 503, 504} or "RESOURCE_EXHAUSTED" in str(error)


def _append(path: Path, record: dict) -> None:
	with path.open("a", encoding="utf-8") as output:
		output.write(json.dumps(record) + "\n")


def process_document(source: dict, prompt_version: str) -> tuple[dict, dict]:
	document_id = str(source["id"])
	pdf_path = Path(source["local_path"])
	started = time.monotonic()
	retries = 0
	for attempt in range(3):
		try:
			ocr = extract_text(pdf_path, document_id)
			extraction, usage = extract_document(ocr.text, prompt_version)
			result = {"document_id": document_id, "prompt_version": prompt_version, **extraction.model_dump(mode="json")}
			log = {
				"document_id": document_id,
				"status": "success",
				"ocr_path": ocr.path,
				"retry_count": retries,
				"latency_seconds": round(time.monotonic() - started, 3),
				"estimated_cost_usd": _estimated_cost(usage, Settings.from_env()),
				**usage,
			}
			return result, log
		except Exception as error:
			if not _is_retryable(error) or attempt == 2:
				return ({"document_id": document_id, "error": f"{type(error).__name__}: {error}"}, {
					"document_id": document_id,
					"status": "error",
					"retry_count": retries,
					"latency_seconds": round(time.monotonic() - started, 3),
				})
			retries += 1
			# Backoff avoids synchronized constant-rate retries that prolong an API limit.
			time.sleep(5 * (2**attempt))
	raise RuntimeError("Unreachable retry state")


def run(limit: int, prompt_version: str = "v1") -> None:
	settings = Settings.from_env()
	manifest_path = RAW_DATA_DIR / "manifest.jsonl"
	sources = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
	pending = [source for source in sources if str(source["id"]) not in _completed_ids(RESULTS_PATH)][:limit]
	print(f"Processing {len(pending)} documents with {settings.max_workers} workers")
	completed = failed = 0
	with ThreadPoolExecutor(max_workers=settings.max_workers) as executor:
		futures = {executor.submit(process_document, source, prompt_version): source for source in pending}
		for future in as_completed(futures):
			result, log = future.result()
			_append(RESULTS_PATH, result)
			_append(RUN_LOG_PATH, log)
			completed += log["status"] == "success"
			failed += log["status"] != "success"
			print(f"Complete {completed + failed}/{len(pending)}: {completed} succeeded, {failed} failed")
	all_results = [json.loads(line) for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines() if line]
	successful_results = [result for result in all_results if "error" not in result]
	print(f"Queued {rebuild_review_queue(successful_results)} records for human review")


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--limit", type=int, default=Settings.from_env().default_doc_limit)
	parser.add_argument("--prompt-version", choices=("v1", "v2"), default="v1")
	arguments = parser.parse_args()
	run(arguments.limit, arguments.prompt_version)