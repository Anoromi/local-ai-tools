from __future__ import annotations

import os
from pathlib import Path


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        root = Path(base) / "kokoro-rocm"
    else:
        root = Path("/tmp") / f"kokoro-rocm-{os.getuid()}"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


def socket_path(explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("KOKORO_ROCM_SOCKET")
    return Path(value) if value else runtime_dir() / "kokoro.sock"


def pid_path() -> Path:
    return runtime_dir() / "kokoro.pid"


def log_path() -> Path:
    return runtime_dir() / "daemon.log"


def sidecar_path(output_path: Path) -> Path:
    return output_path.with_suffix(".json")


def stale_pid() -> int | None:
    path = pid_path()
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip())
    except Exception:
        return None
