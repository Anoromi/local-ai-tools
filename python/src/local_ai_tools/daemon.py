from __future__ import annotations

import asyncio
import json
import os
import signal
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from .paths import log_path, pid_path, socket_path
from .classification import MODEL_ID as CLASSIFICATION_MODEL_ID
from .classification import ModernBertClassifier, classification_labels, classification_sentences
from .protocol import failure, parse_request, stream_event, success, validate_classify, validate_select, validate_synthesize
from .selection import MODEL_ID, ZillizSelector, selection_items

if TYPE_CHECKING:
    from .engine import KokoroEngine


class LocalAiDaemon:
    def __init__(self, socket: Path) -> None:
        self.socket = socket
        self.kokoro: KokoroEngine | None = None
        self.selector: ZillizSelector | None = None
        self.classifier: ModernBertClassifier | None = None
        self.kokoro_lock = asyncio.Lock()
        self.selector_lock = asyncio.Lock()
        self.classifier_lock = asyncio.Lock()
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.socket.parent.mkdir(parents=True, exist_ok=True)
        if self.socket.exists():
            self.socket.unlink()
        self.server = await asyncio.start_unix_server(self.handle_client, path=str(self.socket))
        self.socket.chmod(0o600)
        pid_path().write_text(str(os.getpid()))

    async def serve_forever(self) -> None:
        if self.server is None:
            raise RuntimeError("daemon server not started")
        async with self.server:
            await self.server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_id = "unknown"
        try:
            line = await reader.readline()
            request = parse_request(line)
            request_id = request.id
            if request.method == "health":
                writer.write(success(request.id, self._health()).encode())
            elif request.method == "shutdown":
                writer.write(success(request.id, {"status": "shutting_down"}).encode())
                await writer.drain()
                asyncio.get_running_loop().call_soon(asyncio.get_running_loop().stop)
                return
            elif request.method == "synthesize":
                validate_synthesize(request.params)
                async with self.kokoro_lock:
                    result = await asyncio.to_thread(self._synthesize, request.params)
                writer.write(success(request.id, result).encode())
            elif request.method == "synthesize_stream":
                validate_synthesize(request.params)
                writer.write(stream_event(request.id, "started", {}).encode())
                await writer.drain()
                loop = asyncio.get_running_loop()

                def emit(data: dict) -> None:
                    loop.call_soon_threadsafe(writer.write, stream_event(request.id, data.get("event", "chunk"), data).encode())

                async with self.kokoro_lock:
                    result = await asyncio.to_thread(self._synthesize, request.params, emit)
                await writer.drain()
                writer.write(success(request.id, result).encode())
            elif request.method == "select":
                validate_select(request.params)
                async with self.selector_lock:
                    result = await asyncio.to_thread(self._select, request.params)
                writer.write(success(request.id, result).encode())
            elif request.method == "select_stream":
                validate_select(request.params)
                writer.write(stream_event(request.id, "started", {}).encode())
                await writer.drain()
                async with self.selector_lock:
                    result = await asyncio.to_thread(self._select, request.params)
                writer.write(success(request.id, result).encode())
            elif request.method == "classify":
                validate_classify(request.params)
                async with self.classifier_lock:
                    result = await asyncio.to_thread(self._classify, request.params)
                writer.write(success(request.id, result).encode())
            elif request.method == "classify_stream":
                validate_classify(request.params)
                writer.write(stream_event(request.id, "started", {}).encode())
                await writer.drain()
                async with self.classifier_lock:
                    result = await asyncio.to_thread(self._classify, request.params)
                writer.write(success(request.id, result).encode())
            else:
                writer.write(failure(request.id, "protocol", f"unknown method: {request.method}").encode())
            await writer.drain()
        except Exception as exc:
            writer.write(failure(request_id, "daemon", str(exc), traceback.format_exc()).encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def _synthesize(self, params: dict, on_event=None) -> dict:
        if self.kokoro is None:
            from .engine import KokoroEngine

            self.kokoro = KokoroEngine()
        return self.kokoro.synthesize(
            text=params["text"],
            output_path=Path(params["output_path"]),
            timings_path=Path(params["timings_path"]),
            profile_path=None if params.get("profile_path") is None else Path(params["profile_path"]),
            voice=params.get("voice") or "af_sarah",
            speed=float(params.get("speed", 1.0)),
            target_wpm=None if params.get("target_wpm") is None else float(params["target_wpm"]),
            precision=params.get("precision") or "fp32",
            on_event=on_event,
        )

    def _select(self, params: dict) -> dict:
        if self.selector is None:
            self.selector = ZillizSelector()
        return self.selector.select(
            text=params["text"],
            items=selection_items(params["items"]),
            language=params.get("language") or "auto",
            include_all_scores=bool(params.get("include_all_scores", False)),
        )

    def _classify(self, params: dict) -> dict:
        if self.classifier is None:
            self.classifier = ModernBertClassifier()
        return self.classifier.classify(
            sentences=classification_sentences(params["sentences"]),
            labels=classification_labels(params["labels"]),
            threshold=float(params.get("threshold", 0.5)),
            hypothesis_template=(params.get("hypothesis_template") or "This sentence indicates {}.").strip(),
            include_all_scores=bool(params.get("include_all_scores", False)),
        )

    def _health(self) -> dict:
        return {
            "status": "ok",
            "pid": os.getpid(),
            "tools": {
                "tts": {"loaded": self.kokoro is not None},
                "selection": {"loaded": self.selector is not None, "model": self.selector.model_id if self.selector else MODEL_ID},
                "classification": {
                    "loaded": self.classifier is not None,
                    "model": self.classifier.model_id if self.classifier else CLASSIFICATION_MODEL_ID,
                    "requires_rocm": True,
                },
            },
        }


def _setup_logging() -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    os.dup2(fd, 1)
    os.dup2(fd, 2)


def run_server(socket: Path | None = None, foreground: bool = False) -> None:
    if not foreground:
        _setup_logging()
    sock = socket or socket_path()
    daemon = LocalAiDaemon(sock)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def stop(*_args):
        loop.stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        loop.run_until_complete(daemon.start())
        loop.run_until_complete(daemon.serve_forever())
    finally:
        if sock.exists():
            sock.unlink()
        if pid_path().exists():
            pid_path().unlink()
        loop.close()
