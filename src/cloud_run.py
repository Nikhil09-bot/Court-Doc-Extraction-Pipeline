"""Cloud Run Job entrypoint: stage GCS PDFs, run extraction, and load BigQuery."""

import json
from pathlib import Path

from google.cloud import storage

from config import DATA_DIR, RAW_DATA_DIR, Settings
from src.bq import ensure_tables, insert_records
from src.pipeline import RESULTS_PATH, RUN_LOG_PATH, run


def stage_gcs_pdfs(prefix: str = "raw/") -> int:
    settings = Settings.from_env()
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = storage.Client(project=settings.google_cloud_project)
    staged = 0
    for blob in client.list_blobs(settings.gcs_bucket, prefix=prefix):
        if not blob.name.lower().endswith(".pdf"):
            continue
        destination = RAW_DATA_DIR / Path(blob.name).name
        if not destination.exists():
            blob.download_to_filename(destination)
            staged += 1
    manifest_path = RAW_DATA_DIR / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for pdf_path in RAW_DATA_DIR.glob("*.pdf"):
            manifest.write(json.dumps({"id": pdf_path.stem, "local_path": str(pdf_path)}) + "\n")
    return staged


def _jsonl_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    settings = Settings.from_env()
    print(f"Staged {stage_gcs_pdfs()} PDFs from Cloud Storage")
    run(settings.default_doc_limit)
    ensure_tables()
    extractions = [record for record in _jsonl_records(RESULTS_PATH) if "error" not in record]
    for record in extractions:
        record["processing_date"] = __import__("datetime").date.today().isoformat()
    insert_records("extractions", extractions)
    insert_records("run_logs", _jsonl_records(RUN_LOG_PATH))
    print(f"Loaded {len(extractions)} extraction records into BigQuery")


if __name__ == "__main__":
    main()