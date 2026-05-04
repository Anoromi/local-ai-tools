import json

import pytest

from kokoro_rocm.protocol import ProtocolError, parse_request, request_line, validate_synthesize


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
