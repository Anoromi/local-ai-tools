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
    speed = params.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ProtocolError("speed must be a positive number")
    target = params.get("target_wpm")
    if target is not None and (not isinstance(target, (int, float)) or target <= 0):
        raise ProtocolError("target_wpm must be a positive number")


def success(request_id: str, result: dict[str, Any]) -> str:
    return json.dumps({"id": request_id, "ok": True, "result": result}, separators=(",", ":")) + "\n"


def failure(request_id: str, stage: str, message: str, detail: str = "") -> str:
    return json.dumps(
        {"id": request_id, "ok": False, "error": {"stage": stage, "message": message, "detail": detail[-4000:]}},
        separators=(",", ":"),
    ) + "\n"


def request_line(request_id: str, method: str, params: dict[str, Any]) -> bytes:
    return (json.dumps({"id": request_id, "method": method, "params": params}, separators=(",", ":")) + "\n").encode("utf-8")
