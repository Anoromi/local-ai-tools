import json

import pytest

import json

from local_ai_tools.protocol import ProtocolError, parse_request, request_line, stream_event, validate_select, validate_synthesize


def test_parse_request():
    req = parse_request(request_line("1", "health", {}))
    assert req.id == "1"
    assert req.method == "health"
    assert req.params == {}


def test_unknown_shape_fails():
    with pytest.raises(ProtocolError):
        parse_request(json.dumps([]))


def test_validate_synthesize_requires_text():
    with pytest.raises(ProtocolError):
        validate_synthesize({"output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json"})


def test_validate_synthesize_requires_output():
    with pytest.raises(ProtocolError):
        validate_synthesize({"text": "hello", "timings_path": "/tmp/a.json"})


def test_validate_synthesize_accepts_target_wpm():
    validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "target_wpm": 500})


def test_validate_synthesize_accepts_fp16():
    validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "precision": "fp16"})


def test_validate_synthesize_accepts_profile_path():
    validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json"})
    validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "profile_path": None})
    validate_synthesize(
        {"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "profile_path": "/tmp/a.profile.json"}
    )


def test_validate_synthesize_rejects_invalid_profile_path():
    with pytest.raises(ProtocolError):
        validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "profile_path": ""})
    with pytest.raises(ProtocolError):
        validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "profile_path": 123})


def test_validate_synthesize_rejects_invalid_precision():
    with pytest.raises(ProtocolError):
        validate_synthesize({"text": "hello", "output_path": "/tmp/a.wav", "timings_path": "/tmp/a.json", "precision": "bf16"})


def test_validate_select_requires_text():
    with pytest.raises(ProtocolError):
        validate_select({"items": [{"question": "What failed?"}]})


def test_validate_select_requires_items():
    with pytest.raises(ProtocolError):
        validate_select({"text": "hello"})


def test_validate_select_requires_question():
    with pytest.raises(ProtocolError):
        validate_select({"text": "hello", "items": [{"question": ""}]})


def test_validate_select_accepts_defaults():
    validate_select({"text": "hello", "items": [{"question": "What happened?"}]})


def test_stream_event_shape():
    payload = json.loads(stream_event("1", "chunk", {"chunk": {"index": 0}}))
    assert payload == {"id": "1", "ok": True, "event": "chunk", "data": {"chunk": {"index": 0}}}
