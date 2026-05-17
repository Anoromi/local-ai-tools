from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class ProtocolError(ValueError):
    pass


@dataclass
class Request:
    id: str
    method: str
    params: dict[str, Any]


def parse_request(line: str | bytes) -> Request:
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProtocolError("request must be an object")
    request_id = raw.get("id")
    method = raw.get("method")
    params = raw.get("params", {})
    if not isinstance(request_id, str) or not request_id:
        raise ProtocolError("request id is required")
    if not isinstance(method, str) or not method:
        raise ProtocolError("method is required")
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object")
    return Request(request_id, method, params)


def validate_synthesize(params: dict[str, Any]) -> None:
    text = params.get("text")
    output_path = params.get("output_path")
    timings_path = params.get("timings_path")
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError("text is required")
    if not isinstance(output_path, str) or not output_path:
        raise ProtocolError("output_path is required")
    if not isinstance(timings_path, str) or not timings_path:
        raise ProtocolError("timings_path is required")
    profile_path = params.get("profile_path")
    if profile_path is not None and (not isinstance(profile_path, str) or not profile_path):
        raise ProtocolError("profile_path must be a non-empty string")
    speed = params.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ProtocolError("speed must be a positive number")
    target = params.get("target_wpm")
    if target is not None and (not isinstance(target, (int, float)) or target <= 0):
        raise ProtocolError("target_wpm must be a positive number")
    precision = params.get("precision", "fp32")
    if precision not in ("fp32", "fp16"):
        raise ProtocolError("precision must be fp32 or fp16")


def validate_select(params: dict[str, Any]) -> None:
    text = params.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ProtocolError("text is required")
    items = params.get("items")
    if not isinstance(items, list) or not items:
        raise ProtocolError("items must be a non-empty list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ProtocolError(f"items[{index}] must be an object")
        item_id = item.get("id")
        if item_id is not None and not isinstance(item_id, str):
            raise ProtocolError(f"items[{index}].id must be a string")
        question = item.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ProtocolError(f"items[{index}].question is required")
        threshold = item.get("threshold", 0.5)
        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            raise ProtocolError(f"items[{index}].threshold must be between 0 and 1")
    language = params.get("language", "auto")
    if language not in ("auto", "en", "zh"):
        raise ProtocolError("language must be auto, en, or zh")
    include_all_scores = params.get("include_all_scores", False)
    if not isinstance(include_all_scores, bool):
        raise ProtocolError("include_all_scores must be a boolean")


def validate_classify(params: dict[str, Any]) -> None:
    sentences = params.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        raise ProtocolError("sentences must be a non-empty list")
    for index, sentence in enumerate(sentences):
        if isinstance(sentence, str):
            if not sentence.strip():
                raise ProtocolError(f"sentences[{index}] must be non-empty")
            continue
        if not isinstance(sentence, dict):
            raise ProtocolError(f"sentences[{index}] must be a string or object")
        sentence_id = sentence.get("id")
        if sentence_id is not None and not isinstance(sentence_id, str):
            raise ProtocolError(f"sentences[{index}].id must be a string")
        text = sentence.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError(f"sentences[{index}].text is required")

    labels = params.get("labels")
    if not isinstance(labels, list) or not labels:
        raise ProtocolError("labels must be a non-empty list")
    for index, label in enumerate(labels):
        if isinstance(label, str):
            if not label.strip():
                raise ProtocolError(f"labels[{index}] must be non-empty")
            continue
        if not isinstance(label, dict):
            raise ProtocolError(f"labels[{index}] must be a string or object")
        label_id = label.get("id")
        if label_id is not None and not isinstance(label_id, str):
            raise ProtocolError(f"labels[{index}].id must be a string")
        label_text = label.get("label")
        if not isinstance(label_text, str) or not label_text.strip():
            raise ProtocolError(f"labels[{index}].label is required")
        label_threshold = label.get("threshold")
        if label_threshold is not None and (not isinstance(label_threshold, (int, float)) or label_threshold < 0 or label_threshold > 1):
            raise ProtocolError(f"labels[{index}].threshold must be between 0 and 1")

    threshold = params.get("threshold", 0.5)
    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        raise ProtocolError("threshold must be between 0 and 1")
    hypothesis_template = params.get("hypothesis_template", "This sentence indicates {}.")
    if not isinstance(hypothesis_template, str) or not hypothesis_template.strip():
        raise ProtocolError("hypothesis_template must be a non-empty string")
    include_all_scores = params.get("include_all_scores", False)
    if not isinstance(include_all_scores, bool):
        raise ProtocolError("include_all_scores must be a boolean")


def success(request_id: str, result: dict[str, Any]) -> str:
    return json.dumps({"id": request_id, "ok": True, "result": result}, separators=(",", ":")) + "\n"


def failure(request_id: str, stage: str, message: str, detail: str = "") -> str:
    return json.dumps(
        {"id": request_id, "ok": False, "error": {"stage": stage, "message": message, "detail": detail[-4000:]}},
        separators=(",", ":"),
    ) + "\n"


def stream_event(request_id: str, event: str, data: dict[str, Any]) -> str:
    return json.dumps({"id": request_id, "ok": True, "event": event, "data": data}, separators=(",", ":")) + "\n"


def request_line(request_id: str, method: str, params: dict[str, Any]) -> bytes:
    return (json.dumps({"id": request_id, "method": method, "params": params}, separators=(",", ":")) + "\n").encode("utf-8")
