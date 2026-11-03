"""Extract PDF text through embedded text, Vision, or Document AI with caching."""

from dataclasses import dataclass
from pathlib import Path
import json
import time

import cv2
import fitz
import numpy as np
from google.cloud import documentai, vision

from config import OCR_DATA_DIR, Settings


@dataclass(frozen=True)
class OcrResult:
	document_id: str
	text: str
	path: str
	quality: dict[str, float]


def _embedded_text(pdf: fitz.Document) -> str:
	return "\n".join(page.get_text() for page in pdf).strip()


def scan_quality(pdf_path: Path) -> dict[str, float]:
	"""Estimate image-only scan quality from the first page for routing decisions."""
	with fitz.open(pdf_path) as pdf:
		text = _embedded_text(pdf)
		page = pdf[0]
		pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY)
		image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)
		laplacian_variance = float(cv2.Laplacian(image, cv2.CV_64F).var())
		_, thresholded = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
		points = np.column_stack(np.where(thresholded > 0))
		angle = float(cv2.minAreaRect(points.astype(np.float32))[2]) if len(points) else 0.0
		skew_degrees = angle - 90 if angle > 45 else angle
		return {
			"embedded_text_chars": float(len(text)),
			"effective_dpi": float(pixmap.xres),
			"laplacian_variance": laplacian_variance,
			"skew_degrees": skew_degrees,
			"page_count": float(len(pdf)),
		}


def choose_path(quality: dict[str, float]) -> str:
	if quality["embedded_text_chars"] >= 100:
		return "embedded_text"
	# Low edge variance is a cheap blur signal; blurry scans benefit most from Document AI.
	if quality["effective_dpi"] < 150 or quality["laplacian_variance"] < 100 or abs(quality.get("skew_degrees", 0)) > 3:
		return "document_ai"
	return "vision"


def _vision_text(pdf_path: Path) -> str:
	client = vision.ImageAnnotatorClient()
	parts = []
	with fitz.open(pdf_path) as pdf:
		for page in pdf:
			pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
			response = client.document_text_detection(image=vision.Image(content=pixmap.tobytes("png")))
			if response.error.message:
				raise RuntimeError(response.error.message)
			parts.append(response.full_text_annotation.text)
	return "\n".join(parts).strip()


def _document_ai_text(pdf_path: Path, settings: Settings) -> str:
	client = documentai.DocumentProcessorServiceClient(
		client_options={"api_endpoint": f"{settings.docai_location}-documentai.googleapis.com"}
	)
	name = client.processor_path(settings.google_cloud_project, settings.docai_location, settings.docai_processor_id)
	result = client.process_document(
		request={
			"name": name,
			"raw_document": {"content": pdf_path.read_bytes(), "mime_type": "application/pdf"},
		}
	)
	return result.document.text.strip()


def extract_text(pdf_path: Path, document_id: str) -> OcrResult:
	"""Extract text once and cache it locally because paid OCR should never be repeated."""
	OCR_DATA_DIR.mkdir(parents=True, exist_ok=True)
	cache_path = OCR_DATA_DIR / f"{document_id}.json"
	if cache_path.exists():
		cached = json.loads(cache_path.read_text(encoding="utf-8"))
		return OcrResult(**cached)

	quality = scan_quality(pdf_path)
	path = choose_path(quality)
	if path == "embedded_text":
		with fitz.open(pdf_path) as pdf:
			text = _embedded_text(pdf)
	elif path == "vision":
		text = _vision_text(pdf_path)
	else:
		text = _document_ai_text(pdf_path, Settings.from_env())
	result = OcrResult(document_id=document_id, text=text, path=path, quality=quality)
	cache_path.write_text(json.dumps(result.__dict__), encoding="utf-8")
	return result


def compare_paid_backends(pdf_path: Path, document_id: str) -> list[dict]:
	"""Run Vision and Document AI on one image-only PDF for measured Phase 2 comparison."""
	settings = Settings.from_env()
	results = []
	for backend, extractor in (("vision", lambda: _vision_text(pdf_path)), ("document_ai", lambda: _document_ai_text(pdf_path, settings))):
		started = time.monotonic()
		text = extractor()
		results.append({
			"document_id": document_id,
			"backend": backend,
			"text": text,
			"latency_seconds": round(time.monotonic() - started, 3),
		})
	return results