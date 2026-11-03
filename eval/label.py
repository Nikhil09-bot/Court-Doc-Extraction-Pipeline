"""Prepare and collect human-authored ground-truth labels for evaluation."""

import argparse
import json
from pathlib import Path

from config import DATA_DIR, OCR_DATA_DIR


LABELING_DIR = DATA_DIR / "labeling"
GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.jsonl"


def _blank_label(document_id: str) -> dict:
	return {
		"document_id": document_id,
		"case_name": "",
		"docket_number": "",
		"court_name": "",
		"filing_date": "",
		"document_type": "",
		"parties": [],
		"attorneys": [],
		"judge_name": "",
		"filed_by": "",
		"relief_sought": "",
		"redaction_present": False,
	}


def prepare(document_id: str) -> tuple[Path, Path]:
	"""Create an empty label JSON and a text copy for a person to annotate."""
	ocr_path = OCR_DATA_DIR / f"{document_id}.json"
	if not ocr_path.exists():
		raise FileNotFoundError(f"OCR cache not found for document {document_id}")
	LABELING_DIR.mkdir(parents=True, exist_ok=True)
	text_path = LABELING_DIR / f"{document_id}.txt"
	label_path = LABELING_DIR / f"{document_id}.json"
	text_path.write_text(json.loads(ocr_path.read_text(encoding="utf-8"))["text"], encoding="utf-8")
	if not label_path.exists():
		label_path.write_text(json.dumps(_blank_label(document_id), indent=2) + "\n", encoding="utf-8")
	return text_path, label_path


def collect(document_id: str) -> None:
	"""Append one completed label once; duplicate document IDs are rejected."""
	label_path = LABELING_DIR / f"{document_id}.json"
	label = json.loads(label_path.read_text(encoding="utf-8"))
	if str(label.get("document_id")) != str(document_id):
		raise ValueError("document_id in the label file does not match the requested document")
	if not label.get("document_type"):
		raise ValueError("document_type must be labeled before collection")
	existing = {
		str(json.loads(line)["document_id"])
		for line in GROUND_TRUTH_PATH.read_text(encoding="utf-8").splitlines()
		if line.strip()
	}
	if str(document_id) in existing:
		raise ValueError(f"Ground truth already contains document {document_id}")
	with GROUND_TRUTH_PATH.open("a", encoding="utf-8") as output:
		output.write(json.dumps(label) + "\n")


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=("prepare", "collect"))
	parser.add_argument("document_id")
	arguments = parser.parse_args()
	if arguments.command == "prepare":
		text, label = prepare(arguments.document_id)
		print(f"Edit label: {label}\nRead OCR text: {text}")
	else:
		collect(arguments.document_id)
		print(f"Collected human label for document {arguments.document_id}")