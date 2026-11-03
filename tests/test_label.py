import json

import pytest

import eval.label as label


def test_collect_rejects_blank_document_type(tmp_path, monkeypatch):
	monkeypatch.setattr(label, "LABELING_DIR", tmp_path / "labeling")
	monkeypatch.setattr(label, "GROUND_TRUTH_PATH", tmp_path / "ground_truth.jsonl")
	label.LABELING_DIR.mkdir()
	label.GROUND_TRUTH_PATH.write_text("", encoding="utf-8")
	(label.LABELING_DIR / "1.json").write_text(json.dumps(label._blank_label("1")), encoding="utf-8")
	with pytest.raises(ValueError, match="document_type"):
		label.collect("1")