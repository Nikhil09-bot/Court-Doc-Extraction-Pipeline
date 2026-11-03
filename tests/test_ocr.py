from src.ocr import choose_path


def test_text_layer_beats_paid_ocr():
    assert choose_path({"embedded_text_chars": 100, "effective_dpi": 72, "laplacian_variance": 1}) == "embedded_text"


def test_clean_scan_uses_vision():
    assert choose_path({"embedded_text_chars": 0, "effective_dpi": 300, "laplacian_variance": 500}) == "vision"


def test_low_resolution_scan_uses_document_ai():
    assert choose_path({"embedded_text_chars": 0, "effective_dpi": 100, "laplacian_variance": 500}) == "document_ai"