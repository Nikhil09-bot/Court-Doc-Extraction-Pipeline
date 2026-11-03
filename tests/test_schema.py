import pytest

from src.schema import Confidence, DocumentType, ExtractionRecord, FieldConfidence


def test_extraction_record_rejects_unknown_document_type():
    with pytest.raises(ValueError):
        ExtractionRecord(
            document_type="LETTER",
            field_confidence=FieldConfidence(**{field: Confidence.HIGH for field in FieldConfidence.model_fields}),
            overall_confidence=Confidence.HIGH,
        )


def test_extraction_record_accepts_document_type():
    record = ExtractionRecord(
        document_type=DocumentType.MOTION,
        field_confidence=FieldConfidence(**{field: Confidence.HIGH for field in FieldConfidence.model_fields}),
        overall_confidence=Confidence.HIGH,
    )
    assert record.document_type is DocumentType.MOTION