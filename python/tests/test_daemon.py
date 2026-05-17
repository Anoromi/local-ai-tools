from local_ai_tools.daemon import LocalAiDaemon


def test_select_does_not_load_kokoro(monkeypatch, tmp_path):
    class Selector:
        model_id = "fake"

        def select(self, **_kwargs):
            return {"results": []}

    monkeypatch.setattr("local_ai_tools.daemon.ZillizSelector", Selector)
    daemon = LocalAiDaemon(tmp_path / "s.sock")
    result = daemon._select({"text": "Hello.", "items": [{"question": "What?"}]})
    assert result == {"results": []}
    assert daemon.kokoro is None
    assert daemon.selector is not None


def test_classify_does_not_load_other_tools(monkeypatch, tmp_path):
    class Classifier:
        model_id = "fake"

        def classify(self, **_kwargs):
            return {"results": []}

    monkeypatch.setattr("local_ai_tools.daemon.ModernBertClassifier", Classifier)
    daemon = LocalAiDaemon(tmp_path / "s.sock")
    result = daemon._classify({"sentences": ["Hello."], "labels": ["issue"]})
    assert result == {"results": []}
    assert daemon.kokoro is None
    assert daemon.selector is None
    assert daemon.classifier is not None


def test_health_reports_tools(tmp_path):
    result = LocalAiDaemon(tmp_path / "s.sock")._health()
    assert result["tools"]["tts"]["loaded"] is False
    assert result["tools"]["selection"]["loaded"] is False
    assert result["tools"]["classification"]["loaded"] is False
    assert result["tools"]["classification"]["requires_rocm"] is True
