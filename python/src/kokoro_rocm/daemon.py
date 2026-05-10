from __future__ import annotations

import asyncio
import json
import os
import signal
import traceback
from pathlib import Path

from .engine import KokoroEngine
from .paths import log_path, pid_path, socket_path
from .protocol import failure, parse_request, stream_event, success, validate_synthesize


class KokoroDaemon:
    def __init__(self, socket: Path) -> None:
        self.socket = socket
        self.engine: KokoroEngine | None = None
        self.lock = asyncio.Lock()
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.socket.parent.mkdir(parents=True, exist_ok=True)
        if self.socket.exists():
            self.socket.unlink()
        self.engine = await asyncio.to_thread(KokoroEngine)
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
                writer.write(success(request.id, {"status": "ok", "pid": os.getpid(), "model_loaded": self.engine is not None}).encode())
            elif request.method == "shutdown":
                writer.write(success(request.id, {"status": "shutting_down"}).encode())
                await writer.drain()
                asyncio.get_running_loop().call_soon(asyncio.get_running_loop().stop)
                return
            elif request.method == "synthesize":
                validate_synthesize(request.params)
                async with self.lock:
                    result = await asyncio.to_thread(self._synthesize, request.params)
                writer.write(success(request.id, result).encode())
            elif request.method == "synthesize_stream":
                validate_synthesize(request.params)
                writer.write(stream_event(request.id, "started", {}).encode())
                await writer.drain()
                loop = asyncio.get_running_loop()

                def emit(data: dict) -> None:
                    loop.call_soon_threadsafe(writer.write, stream_event(request.id, data.get("event", "chunk"), data).encode())

                async with self.lock:
                    result = await asyncio.to_thread(self._synthesize, request.params, emit)
                await writer.drain()
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
        if self.engine is None:
            raise RuntimeError("engine is not loaded")
        return self.engine.synthesize(
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
    daemon = KokoroDaemon(sock)
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
