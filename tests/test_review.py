from src.review import mark_reviewed, review_reasons


def test_low_field_confidence_routes_to_review():
	reasons = review_reasons({"overall_confidence": "HIGH", "field_confidence": {"parties": "LOW"}})
	assert reasons == ["parties confidence is LOW"]


def test_reviewed_record_has_audit_fields():
	reviewed = mark_reviewed({"document_id": "1"}, "reviewer@example.com")
	assert reviewed["reviewed_by_human"] is True
	assert reviewed["reviewed_by"] == "reviewer@example.com"
	assert reviewed["reviewed_at"]