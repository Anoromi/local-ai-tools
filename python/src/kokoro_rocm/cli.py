from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from . import env
from .paths import log_path, pid_path, sidecar_path, socket_path
from .protocol import request_line

EXIT_USAGE = 1
EXIT_DAEMON = 2
EXIT_SYNTHESIS = 3
EXIT_WRITE = 4
EXIT_PROTOCOL = 5
EXIT_SETUP = 6
EXIT_HEALTH = 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kokoro-rocm")
    sub = parser.add_subparsers(dest="command")

    say = sub.add_parser("say")
    add_say_args(say)

    serve = sub.add_parser("serve")
    serve.add_argument("--foreground", action="store_true")
    serve.add_argument("--socket")

    status = sub.add_parser("status")
    status.add_argument("--socket")

    stop = sub.add_parser("stop")
    stop.add_argument("--socket")

    setup = sub.add_parser("setup")
    setup.add_argument("--torch", choices=["rocm6.4", "rocm6.3", "cpu", "existing"], default="rocm6.4")
    setup.add_argument("--python", default="3.12")
    setup.add_argument("--python-path")
    setup.add_argument("--data-dir")
    setup.add_argument("--voice", default=env.default_voice())
    setup.add_argument("--force", action="store_true")
    setup.add_argument("--no-download", action="store_true")
    setup.add_argument("--model-url")
    setup.add_argument("--config-url")
    setup.add_argument("--voice-url")

    health = sub.add_parser("health")
    health.add_argument("--json", action="store_true")
    health.add_argument("--output")
    health.add_argument("--probe-synthesis", action="store_true")
    health.add_argument("--keep-probe-output", action="store_true")
    health.add_argument("--socket")

    add_say_args(parser)
    return parser


def add_say_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output")
    parser.add_argument("--voice", default=env.default_voice())
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--target-wpm", type=float)
    parser.add_argument("--socket")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "say"
    if command == "serve":
        from .daemon import run_server

        run_server(socket_path(args.socket), foreground=args.foreground)
        return 0
    if command == "status":
        return status(args.socket)
    if command == "stop":
        return stop(args.socket)
    if command == "setup":
        from .setup import run_setup

        return run_setup(args)
    if command == "health":
        from .health import run_health

        return run_health(args)
    if command == "say":
        return say(args)
    parser.print_help(sys.stderr)
    return EXIT_USAGE


def say(args) -> int:
    if not args.output:
        print("kokoro-rocm: -o/--output is required", file=sys.stderr)
        return EXIT_USAGE
    try:
        text = sys.stdin.read()
    except UnicodeDecodeError as exc:
        print(f"kokoro-rocm: failed to read UTF-8 stdin: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not text.strip():
        print("kokoro-rocm: stdin text is empty", file=sys.stderr)
        return EXIT_USAGE
    output = Path(args.output).expanduser().resolve()
    timings = sidecar_path(output)
    try:
        ensure_daemon(args.socket)
        response = call(
            args.socket,
            "synthesize",
            {
                "text": text.strip(),
                "output_path": str(output),
                "timings_path": str(timings),
                "voice": args.voice,
                "speed": args.speed,
                "target_wpm": args.target_wpm,
                "format": "wav",
            },
            timeout=3600,
        )
    except RuntimeError as exc:
        print(f"kokoro-rocm: {exc}", file=sys.stderr)
        return EXIT_DAEMON
    if not response.get("ok"):
        error = response.get("error", {})
        print(f"kokoro-rocm: {error.get('message', 'synthesis failed')}", file=sys.stderr)
        detail = error.get("detail")
        if detail:
            print(detail, file=sys.stderr)
        return EXIT_SYNTHESIS
    result = response["result"]
    print(f"wrote {result['output_path']} and {result['timings_path']} in {result['total_seconds']:.2f}s")
    return 0


def status(sock: str | None = None) -> int:
    try:
        response = call(sock, "health", {}, timeout=2)
    except RuntimeError as exc:
        print(f"not running: {exc}")
        return EXIT_DAEMON
    print(json.dumps(response.get("result", response), indent=2))
    return 0 if response.get("ok") else EXIT_PROTOCOL


def stop(sock: str | None = None) -> int:
    try:
        response = call(sock, "shutdown", {}, timeout=2)
    except RuntimeError as exc:
        print(f"not running: {exc}")
        return EXIT_DAEMON
    print(json.dumps(response.get("result", response), indent=2))
    return 0 if response.get("ok") else EXIT_PROTOCOL


def ensure_daemon(sock: str | None = None) -> None:
    try:
        response = call(sock, "health", {}, timeout=1)
        if response.get("ok"):
            return
    except RuntimeError:
        cleanup_stale_socket(sock)
    start_daemon(sock)
    deadline = time.monotonic() + 30
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = call(sock, "health", {}, timeout=1)
            if response.get("ok"):
                return
        except RuntimeError as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"daemon did not become ready within 30s: {last_error}; log: {log_path()}")


def cleanup_stale_socket(sock: str | None = None) -> None:
    path = socket_path(sock)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def start_daemon(sock: str | None = None) -> None:
    python = env.backend_python()
    if not python.exists():
        raise RuntimeError(f"backend Python is missing: {python}. Run: kokoro-rocm setup")
    pid_file = pid_path()
    log = log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    args = [str(python), "-m", "kokoro_rocm", "serve"]
    if sock:
        args += ["--socket", str(socket_path(sock))]
    env_map = env.rocm_env()
    source = str(Path(__file__).resolve().parents[1])
    env_map["PYTHONPATH"] = source + (":" + env_map["PYTHONPATH"] if env_map.get("PYTHONPATH") else "")
    with log.open("ab") as log_file:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file, env=env_map, start_new_session=True)
    pid_file.write_text(str(proc.pid))


def call(sock: str | None, method: str, params: dict, timeout: float) -> dict:
    import socket

    path = socket_path(sock)
    request_id = str(uuid.uuid4())
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(path))
        client.sendall(request_line(request_id, method, params))
        chunks = []
        while True:
            data = client.recv(65536)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        client.close()
    if not chunks:
        raise RuntimeError("empty daemon response")
    try:
        response = json.loads(b"".join(chunks).splitlines()[0].decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid daemon response: {exc}") from exc
    if response.get("id") != request_id:
        raise RuntimeError("daemon response id mismatch")
    return response
