from local_ai_tools.classification import (
    ClassificationLabel,
    ClassificationSentence,
    ModernBertClassifier,
    classification_labels,
    classification_sentences,
)


def test_classification_normalizes_string_shorthand():
    assert classification_sentences(["Hello."]) == [ClassificationSentence(id=None, text="Hello.")]
    assert classification_labels(["issue"]) == [ClassificationLabel(id="issue", label="issue", threshold=None)]


def test_classifier_maps_scores_and_thresholds_with_fake_pipeline():
    class Pipeline:
        def __call__(self, sentences, **kwargs):
            assert sentences == ["The deploy passed.", "The parser failed."]
            assert kwargs["candidate_labels"] == ["success", "issue"]
            assert kwargs["batch_size"] == 32
            return [
                {"labels": ["success", "issue"], "scores": [0.91, 0.11]},
                {"labels": ["issue", "success"], "scores": [0.88, 0.21]},
            ]

    classifier = object.__new__(ModernBertClassifier)
    classifier.model_id = "fake"
    classifier.classifier = Pipeline()
    classifier.batch_size = 32
    result = classifier.classify(
        sentences=[
            ClassificationSentence(id="s1", text="The deploy passed."),
            ClassificationSentence(id="s2", text="The parser failed."),
        ],
        labels=[ClassificationLabel(id="success", label="success"), ClassificationLabel(id="issue", label="issue")],
        threshold=0.5,
        include_all_scores=True,
    )
    assert result["sentence_count"] == 2
    assert result["label_count"] == 2
    assert result["results"][0]["matches"] == [{"id": "success", "label": "success", "score": 0.91}]
    assert result["results"][1]["matches"] == [{"id": "issue", "label": "issue", "score": 0.88}]
    assert result["results"][0]["top_label"] == "success"
    assert "all_scores" in result["results"][0]


def test_classifier_uses_per_label_threshold():
    class Pipeline:
        def __call__(self, *_args, **_kwargs):
            return {"labels": ["success", "issue"], "scores": [0.6, 0.6]}

    classifier = object.__new__(ModernBertClassifier)
    classifier.model_id = "fake"
    classifier.classifier = Pipeline()
    classifier.batch_size = 32
    result = classifier.classify(
        sentences=[ClassificationSentence(id=None, text="Mixed.")],
        labels=[
            ClassificationLabel(id="success", label="success", threshold=0.7),
            ClassificationLabel(id="issue", label="issue", threshold=0.5),
        ],
        threshold=0.5,
    )
    assert result["results"][0]["matches"] == [{"id": "issue", "label": "issue", "score": 0.6}]
    assert "all_scores" not in result["results"][0]
