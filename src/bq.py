"""Create and load the three BigQuery tables used by the pipeline."""

import argparse
from datetime import date
import json
from pathlib import Path

from google.cloud import bigquery

from config import DATA_DIR, Settings


def ensure_tables() -> None:
	settings = Settings.from_env()
	client = bigquery.Client(project=settings.google_cloud_project)
	dataset = f"{settings.google_cloud_project}.{settings.bq_dataset}"
	extraction_schema = [
		bigquery.SchemaField("document_id", "STRING", mode="REQUIRED"),
		bigquery.SchemaField("processing_date", "DATE", mode="REQUIRED"),
		bigquery.SchemaField("prompt_version", "STRING"),
		bigquery.SchemaField("case_name", "STRING"),
		bigquery.SchemaField("docket_number", "STRING"),
		bigquery.SchemaField("court_name", "STRING"),
		bigquery.SchemaField("filing_date", "DATE"),
		bigquery.SchemaField("document_type", "STRING"),
		bigquery.SchemaField("judge_name", "STRING"),
		bigquery.SchemaField("filed_by", "STRING"),
		bigquery.SchemaField("relief_sought", "STRING"),
		bigquery.SchemaField("redaction_present", "BOOLEAN"),
		bigquery.SchemaField("overall_confidence", "STRING"),
		bigquery.SchemaField("extraction_notes", "STRING"),
		bigquery.SchemaField("field_confidence", "RECORD", fields=[
			bigquery.SchemaField("case_name", "STRING"),
			bigquery.SchemaField("docket_number", "STRING"),
			bigquery.SchemaField("court_name", "STRING"),
			bigquery.SchemaField("filing_date", "STRING"),
			bigquery.SchemaField("document_type", "STRING"),
			bigquery.SchemaField("parties", "STRING"),
			bigquery.SchemaField("attorneys", "STRING"),
			bigquery.SchemaField("judge_name", "STRING"),
			bigquery.SchemaField("filed_by", "STRING"),
			bigquery.SchemaField("relief_sought", "STRING"),
		]),
		bigquery.SchemaField("parties", "RECORD", mode="REPEATED", fields=[bigquery.SchemaField("name", "STRING"), bigquery.SchemaField("role", "STRING"), bigquery.SchemaField("party_type", "STRING")]),
		bigquery.SchemaField("attorneys", "RECORD", mode="REPEATED", fields=[bigquery.SchemaField("name", "STRING"), bigquery.SchemaField("firm", "STRING"), bigquery.SchemaField("represents_party", "STRING")]),
	]
	tables = {
		"extractions": extraction_schema,
		"run_logs": [bigquery.SchemaField("document_id", "STRING"), bigquery.SchemaField("status", "STRING"), bigquery.SchemaField("input_tokens", "INTEGER"), bigquery.SchemaField("output_tokens", "INTEGER"), bigquery.SchemaField("estimated_cost_usd", "FLOAT"), bigquery.SchemaField("latency_seconds", "FLOAT"), bigquery.SchemaField("ocr_path", "STRING"), bigquery.SchemaField("retry_count", "INTEGER")],
		"review_queue": [bigquery.SchemaField("document_id", "STRING"), bigquery.SchemaField("status", "STRING"), bigquery.SchemaField("reasons", "STRING", mode="REPEATED"), bigquery.SchemaField("reviewed_by_human", "BOOLEAN"), bigquery.SchemaField("reviewed_at", "TIMESTAMP")],
	}
	for name, schema in tables.items():
		table = bigquery.Table(f"{dataset}.{name}", schema=schema)
		if name == "extractions":
			table.time_partitioning = bigquery.TimePartitioning(field="processing_date")
		try:
			client.create_table(table)
		except Exception as error:
			if "Already Exists" not in str(error):
				raise
			existing = client.get_table(table.reference)
			existing_names = {field.name for field in existing.schema}
			missing = [field for field in schema if field.name not in existing_names]
			if missing:
				existing.schema = [*existing.schema, *missing]
				client.update_table(existing, ["schema"])


def insert_records(table_name: str, records: list[dict]) -> None:
	"""Insert small batches with explicit errors rather than silently dropping rows."""
	if not records:
		return
	settings = Settings.from_env()
	client = bigquery.Client(project=settings.google_cloud_project)
	table_id = f"{settings.google_cloud_project}.{settings.bq_dataset}.{table_name}"
	errors = client.insert_rows_json(table_id, records)
	if errors:
		raise RuntimeError(f"BigQuery insert failed: {errors}")


def _checkpoint_records(path: Path) -> list[dict]:
	if not path.exists():
		return []
	return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _replace_records(table_name: str, records: list[dict]) -> None:
	if not records:
		return
	settings = Settings.from_env()
	client = bigquery.Client(project=settings.google_cloud_project)
	table_id = f"{settings.google_cloud_project}.{settings.bq_dataset}.{table_name}"
	document_ids = list({record["document_id"] for record in records})
	query = f"DELETE FROM `{table_id}` WHERE document_id IN UNNEST(@document_ids)"
	job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("document_ids", "STRING", document_ids)])
	client.query(query, job_config=job_config).result()
	insert_records(table_name, records)


def load_local_outputs() -> None:
	"""Idempotently load local checkpoints so rerunning a batch cannot duplicate rows."""
	extractions = [record for record in _checkpoint_records(DATA_DIR / "extractions.jsonl") if "error" not in record]
	for record in extractions:
		record["processing_date"] = date.today().isoformat()
		record["filing_date"] = record.get("filing_date") or None
	logs = _checkpoint_records(DATA_DIR / "run_logs.jsonl")
	queue = _checkpoint_records(DATA_DIR / "review_queue.jsonl")
	review_rows = [
		{
			"document_id": item["record"]["document_id"],
			"status": item["status"],
			"reasons": item["reasons"],
			"reviewed_by_human": False,
			"reviewed_at": None,
		}
		for item in queue
	]
	_replace_records("extractions", extractions)
	_replace_records("run_logs", logs)
	_replace_records("review_queue", review_rows)
	print(f"Loaded {len(extractions)} extractions, {len(logs)} logs, and {len(review_rows)} review items.")


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=("init", "load"))
	arguments = parser.parse_args()
	if arguments.command == "init":
		ensure_tables()
		print("BigQuery tables are ready.")
	if arguments.command == "load":
		load_local_outputs()