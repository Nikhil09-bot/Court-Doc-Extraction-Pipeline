"""Acquire publicly available RECAP filings and inventory local PDFs."""

import argparse
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError

import fitz

from config import RAW_DATA_DIR, Settings


RECAP_DOCUMENTS_URL = "https://www.courtlistener.com/api/rest/v4/recap-documents/"
MANIFEST_PATH = RAW_DATA_DIR / "manifest.jsonl"


def _request_json(url: str, token: str) -> dict:
	request = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
	for attempt in range(3):
		try:
			with urllib.request.urlopen(request, timeout=30) as response:
				return json.load(response)
		except HTTPError as error:
			if error.code not in {429, 503} or attempt == 2:
				raise
			# Spacing retries prevents a rate-limited client from immediately causing another limit.
			time.sleep(5 * (2**attempt))
	raise RuntimeError("Unreachable retry state")


def _download(url: str, destination: Path, token: str) -> None:
	request = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
	with urllib.request.urlopen(request, timeout=60) as response:
		destination.write_bytes(response.read())


def _download_url(document: dict) -> str | None:
	path = document.get("filepath_local")
	if not path:
		return None
	if path.startswith("http"):
		return path
	return urllib.parse.urljoin("https://storage.courtlistener.com/", path.lstrip("/"))


def _read_completed_ids(manifest_path: Path) -> set[int]:
	if not manifest_path.exists():
		return set()
	return {
		int(json.loads(line)["id"])
		for line in manifest_path.read_text(encoding="utf-8").splitlines()
		if line.strip()
	}


def acquire(limit: int, delay_seconds: float = 1.0) -> int:
	"""Download up to ``limit`` new, publicly available PDFs and append metadata."""
	settings = Settings.from_env()
	if not settings.courtlistener_token:
		raise ValueError("COURTLISTENER_TOKEN is required to acquire documents")
	RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
	completed_ids = _read_completed_ids(MANIFEST_PATH)
	downloaded = 0
	next_url = f"{RECAP_DOCUMENTS_URL}?page_size=100"

	while next_url and downloaded < limit:
		payload = _request_json(next_url, settings.courtlistener_token)
		for document in payload["results"]:
			if downloaded >= limit:
				break
			document_id = document["id"]
			url = _download_url(document)
			if document_id in completed_ids or not document.get("is_available") or not url:
				continue

			destination = RAW_DATA_DIR / f"{document_id}.pdf"
			try:
				_download(url, destination, settings.courtlistener_token)
				with MANIFEST_PATH.open("a", encoding="utf-8") as manifest:
					manifest.write(json.dumps({**document, "local_path": str(destination)}) + "\n")
				completed_ids.add(document_id)
				downloaded += 1
				print(f"Downloaded {downloaded}/{limit}: {destination.name}")
			except Exception as error:
				destination.unlink(missing_ok=True)
				print(f"Skipped document {document_id}: {type(error).__name__}: {error}")
			time.sleep(delay_seconds)
		next_url = payload.get("next")
	return downloaded


def inventory() -> dict:
	"""Measure text-layer, page-count, and file-size distributions for local PDFs."""
	documents = []
	for pdf_path in sorted(RAW_DATA_DIR.glob("*.pdf")):
		with fitz.open(pdf_path) as pdf:
			text = "".join(page.get_text() for page in pdf)
			documents.append(
				{
					"file": pdf_path.name,
					"has_substantive_text": len(text.strip()) >= 100,
					"pages": len(pdf),
					"size_bytes": pdf_path.stat().st_size,
				}
			)
	total = len(documents)
	report = {
		"documents": total,
		"text_layer_documents": sum(item["has_substantive_text"] for item in documents),
		"image_only_documents": sum(not item["has_substantive_text"] for item in documents),
		"page_counts": [item["pages"] for item in documents],
		"file_sizes_bytes": [item["size_bytes"] for item in documents],
	}
	print(json.dumps(report, indent=2))
	return report


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("command", choices=("acquire", "inventory"))
	parser.add_argument("--limit", type=int, default=Settings.from_env().default_doc_limit)
	args = parser.parse_args()
	acquire(args.limit) if args.command == "acquire" else inventory()