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


def test_health_reports_tools(tmp_path):
    result = LocalAiDaemon(tmp_path / "s.sock")._health()
    assert result["tools"]["tts"]["loaded"] is False
    assert result["tools"]["selection"]["loaded"] is False
