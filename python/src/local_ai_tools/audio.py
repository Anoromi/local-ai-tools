from __future__ import annotations

import subprocess
import time
from pathlib import Path


def atempo_filter(factor: float) -> str:
    parts: list[float] = []
    f = float(factor)
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    parts.append(f)
    return ",".join(f"atempo={x:.10g}" for x in parts)


def duration_seconds(path: Path) -> float:
    proc = subprocess.run(["soxi", "-D", str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return float(proc.stdout.strip())


def retime_to_wpm(source: Path, dest: Path, native_wpm: float, target_wpm: float) -> dict:
    factor = target_wpm / native_wpm
    filt = atempo_filter(factor)
    started = time.perf_counter()
    proc = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source), "-filter:a", filt, str(dest)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return {"used": True, "engine": "ffmpeg_atempo", "factor": factor, "filter": filt, "seconds": elapsed}
