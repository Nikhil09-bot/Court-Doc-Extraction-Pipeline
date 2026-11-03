"""Build and resolve a local queue for low-confidence extraction records."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from config import DATA_DIR, OCR_DATA_DIR


REVIEW_QUEUE_PATH = DATA_DIR / "review_queue.jsonl"
REVIEWED_RECORDS_PATH = DATA_DIR / "reviewed_records.jsonl"


def review_reasons(record: dict) -> list[str]:
	reasons = []
	if record.get("overall_confidence") == "LOW":
		reasons.append("overall_confidence is LOW")
	for field, confidence in record.get("field_confidence", {}).items():
		if confidence == "LOW":
			reasons.append(f"{field} confidence is LOW")
	return reasons


def queue_for_review(records: list[dict]) -> int:
	queued = 0
	with REVIEW_QUEUE_PATH.open("a", encoding="utf-8") as queue:
		for record in records:
			reasons = review_reasons(record)
			if reasons:
				queue.write(json.dumps({"record": record, "reasons": reasons, "status": "pending"}) + "\n")
				queued += 1
	return queued


def rebuild_review_queue(records: list[dict]) -> int:
	"""Replace the queue from checkpoints so resumed runs cannot create duplicate items."""
	REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
	REVIEW_QUEUE_PATH.write_text("", encoding="utf-8")
	return queue_for_review(records)


def mark_reviewed(record: dict, reviewer: str) -> dict:
	return {
		**record,
		"reviewed_by_human": True,
		"reviewed_by": reviewer,
		"reviewed_at": datetime.now(UTC).isoformat(),
	}


def review_cli(reviewer: str) -> None:
	"""Present queued OCR text and extraction fields for a human accept/correct decision."""
	if not REVIEW_QUEUE_PATH.exists():
		print("No review queue exists.")
		return
	queue = [json.loads(line) for line in REVIEW_QUEUE_PATH.read_text(encoding="utf-8").splitlines() if line]
	with REVIEWED_RECORDS_PATH.open("a", encoding="utf-8") as output:
		for item in queue:
			record = item["record"]
			document_id = record["document_id"]
			ocr_path = OCR_DATA_DIR / f"{document_id}.json"
			ocr_text = json.loads(ocr_path.read_text(encoding="utf-8"))["text"] if ocr_path.exists() else "OCR cache unavailable"
			print(f"\nDocument {document_id}\nReasons: {'; '.join(item['reasons'])}")
			print(f"\nOCR text\n{'-' * 40}\n{ocr_text[:4000]}")
			print(f"\nExtraction\n{'-' * 40}\n{json.dumps(record, indent=2)}")
			action = input("[a]ccept, [e]dit one field, or [s]kip: ").strip().lower()
			if action == "s":
				continue
			if action == "e":
				field = input("Field to correct: ").strip()
				if field not in record:
					print(f"Unknown field: {field}; skipped.")
					continue
				record[field] = input(f"New value for {field}: ").strip()
			elif action != "a":
				print("Unknown action; skipped.")
				continue
			output.write(json.dumps(mark_reviewed(record, reviewer)) + "\n")
			print("Saved reviewed record.")


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--reviewer", required=True)
	arguments = parser.parse_args()
	review_cli(arguments.reviewer)