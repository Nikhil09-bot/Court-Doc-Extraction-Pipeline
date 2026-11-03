from eval.evaluate import evaluate, normalize


def test_normalize_removes_honorifics_and_punctuation():
    assert normalize("Hon. Smith, John A.") == "smithjohna"


def test_evaluate_scores_normalized_list_items():
    truth = {"1": {"document_id": "1", "parties": [{"name": "John A. Smith"}]}}
    predictions = {"1": {"document_id": "1", "parties": [{"name": "John A Smith"}]}}
    assert evaluate(predictions, truth)["parties"]["f1"] == 1.0