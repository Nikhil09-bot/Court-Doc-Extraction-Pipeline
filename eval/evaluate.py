"""Score extraction JSONL against hand-labeled JSONL ground truth."""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> dict[str, dict]:
	return {str(record["document_id"]): record for record in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)}


def normalize(value: str) -> str:
	value = re.sub(r"\b(honorable|hon|esq)\.?\b", "", value.lower())
	return re.sub(r"[^a-z0-9]", "", value)


def _values(record: dict, field: str) -> set[str]:
	value = record.get(field, [])
	if isinstance(value, list):
		return {normalize(item["name"] if isinstance(item, dict) else item) for item in value}
	return {normalize(str(value))} if value not in (None, "") else set()


def _score_sets(actual: set[str], expected: set[str]) -> tuple[int, int, int]:
	return len(actual & expected), len(actual - expected), len(expected - actual)


def evaluate(predictions: dict[str, dict], truth: dict[str, dict]) -> dict:
	counts = defaultdict(lambda: [0, 0, 0])
	fields = ("case_name", "docket_number", "court_name", "filing_date", "document_type", "parties", "attorneys", "judge_name", "filed_by", "relief_sought", "redaction_present")
	for document_id, expected in truth.items():
		actual = predictions.get(document_id)
		if not actual:
			continue
		for field in fields:
			true_positive, false_positive, false_negative = _score_sets(_values(actual, field), _values(expected, field))
			counts[field][0] += true_positive
			counts[field][1] += false_positive
			counts[field][2] += false_negative
	report = {}
	for field, (true_positive, false_positive, false_negative) in counts.items():
		precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
		recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
		report[field] = {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
	return report


def calibration(predictions: dict[str, dict], truth: dict[str, dict]) -> dict:
	buckets = defaultdict(lambda: [0, 0])
	for document_id, expected in truth.items():
		actual = predictions.get(document_id, {})
		for field, confidence in actual.get("field_confidence", {}).items():
			buckets[confidence][0] += 1
			buckets[confidence][1] += _values(actual, field) == _values(expected, field)
	return {name: {"n": count, "accuracy": correct / count if count else 0.0} for name, (count, correct) in buckets.items()}


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("predictions", type=Path)
	parser.add_argument("ground_truth", type=Path)
	arguments = parser.parse_args()
	predicted = load_jsonl(arguments.predictions)
	expected = load_jsonl(arguments.ground_truth)
	print(json.dumps({"metrics": evaluate(predicted, expected), "calibration": calibration(predicted, expected)}, indent=2))