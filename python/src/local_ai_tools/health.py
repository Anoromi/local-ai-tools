from __future__ import annotations

import glob
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__, env
from .cli import call
from .paths import socket_path

CRITICAL = ["wrapper", "setup_env", "assets", "gpu_devices", "pytorch_rocm", "kokoro_python"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_health(args) -> int:
    report = build_report(args)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(json.dumps(report, indent=2))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0 if report["status"] == "ok" else 7


def build_report(args) -> dict[str, Any]:
    checks = {
        "wrapper": check_wrapper(),
        "setup_env": check_setup_env(),
        "assets": check_assets(),
        "gpu_devices": check_gpu_devices(),
        "pytorch_rocm": check_pytorch_rocm(),
        "kokoro_python": check_kokoro_python(),
        "daemon": check_daemon(args.socket),
    }
    if args.probe_synthesis:
        checks["synthesis_probe"] = check_synthesis_probe(args.keep_probe_output)
    else:
        checks["synthesis_probe"] = {"ok": True, "skipped": True}

    critical = list(CRITICAL)
    if args.probe_synthesis:
        critical.append("synthesis_probe")
    status = "ok" if all(checks[name].get("ok") for name in critical) else "failed"
    return {
        "status": status,
        "created_at": now_iso(),
        "checks": checks,
        "recommendations": recommendations(checks),
    }


def check_wrapper() -> dict[str, Any]:
    tools = {name: shutil.which(name) for name in ["uv", "ffmpeg", "soxi", "gcc"]}
    return {"ok": all(tools.values()), "version": __version__, "tools": tools}


def check_setup_env() -> dict[str, Any]:
    cfg = env.effective_config()
    return {
        "ok": bool(cfg["LOCAL_AI_TOOLS_PYTHON"] and cfg["LOCAL_AI_TOOLS_MODEL"] and cfg["LOCAL_AI_TOOLS_CONFIG"] and cfg["LOCAL_AI_TOOLS_VOICES_DIR"]),
        "env_file": cfg.get("LOCAL_AI_TOOLS_ENV_FILE") or None,
        "python": cfg["LOCAL_AI_TOOLS_PYTHON"],
        "model": cfg["LOCAL_AI_TOOLS_MODEL"],
        "config": cfg["LOCAL_AI_TOOLS_CONFIG"],
        "voices_dir": cfg["LOCAL_AI_TOOLS_VOICES_DIR"],
        "default_voice": cfg["LOCAL_AI_TOOLS_DEFAULT_VOICE"],
    }


def check_assets() -> dict[str, Any]:
    python = env.backend_python()
    model = env.model_path()
    config = env.config_path()
    voices = env.voices_dir()
    voice = env.voice_path(env.default_voice())
    config_valid = False
    if config.exists():
        try:
            json.loads(config.read_text())
            config_valid = True
        except Exception:
            config_valid = False
    model_size = model.stat().st_size if model.exists() else 0
    voice_size = voice.stat().st_size if voice.exists() else 0
    payload = {
        "python_exists": python.exists(),
        "python_executable": python.exists() and os.access(python, os.X_OK),
        "model_exists": model.exists(),
        "model_size_bytes": model_size,
        "config_exists": config.exists(),
        "config_valid_json": config_valid,
        "voices_dir_exists": voices.exists() and voices.is_dir(),
        "voice": str(voice),
        "voice_exists": voice.exists(),
        "voice_size_bytes": voice_size,
    }
    payload["ok"] = (
        payload["python_executable"]
        and payload["model_exists"]
        and model_size > 100 * 1024 * 1024
        and payload["config_valid_json"]
        and payload["voices_dir_exists"]
        and payload["voice_exists"]
        and voice_size > 10 * 1024
    )
    return payload


def access_info(path: str) -> dict[str, Any]:
    p = Path(path)
    return {
        "path": path,
        "exists": p.exists(),
        "readable": p.exists() and os.access(p, os.R_OK),
        "writable": p.exists() and os.access(p, os.W_OK),
    }


def check_gpu_devices() -> dict[str, Any]:
    render_nodes = [access_info(path) for path in sorted(glob.glob("/dev/dri/renderD*"))]
    groups = [g.gr_name for g in os.getgrouplist(os.getlogin() if hasattr(os, "getlogin") else "", os.getgid())] if False else []
    try:
        import grp

        groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
    except Exception:
        groups = []
    dev_kfd = access_info("/dev/kfd")
    ok = dev_kfd["exists"] and dev_kfd["readable"] and dev_kfd["writable"] and any(n["readable"] and n["writable"] for n in render_nodes)
    return {"ok": ok, "dev_kfd": dev_kfd, "render_nodes": render_nodes, "groups": groups}


def run_backend_probe(code: str, timeout: int = 60) -> dict[str, Any]:
    python = env.backend_python()
    if not python.exists():
        return {"ok": False, "error": f"backend Python missing: {python}"}
    proc = subprocess.run([str(python), "-c", code], env=env.rocm_env(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout).strip()[-4000:]}
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "error": f"invalid JSON from probe: {exc}", "stdout": proc.stdout[-2000:]}
    payload["ok"] = bool(payload.get("ok", True))
    return payload


def check_pytorch_rocm() -> dict[str, Any]:
    code = """
import json, torch
payload = {
  "torch_version": torch.__version__,
  "hip_version": getattr(torch.version, "hip", None),
  "cuda_available": torch.cuda.is_available(),
  "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
}
if torch.cuda.is_available():
  payload["device_name"] = torch.cuda.get_device_name(0)
payload["ok"] = bool(payload["cuda_available"] and payload["device_count"] >= 1)
print(json.dumps(payload))
"""
    return run_backend_probe(code)


def check_kokoro_python() -> dict[str, Any]:
    code = """
import json
import kokoro, soundfile, numpy
from kokoro import KModel, KPipeline
print(json.dumps({"ok": True, "kokoro_import": True, "soundfile_import": True, "numpy_import": True}))
"""
    return run_backend_probe(code)


def check_daemon(sock: str | None) -> dict[str, Any]:
    path = socket_path(sock)
    try:
        response = call(str(path), "health", {}, timeout=2)
    except Exception:
        return {"ok": False, "socket": str(path), "running": False, "message": "daemon is not running; this is fine before first synthesis"}
    result = response.get("result", {})
    return {"ok": bool(response.get("ok")), "socket": str(path), "running": bool(response.get("ok")), **result}


def check_synthesis_probe(keep_output: bool) -> dict[str, Any]:
    tmp = tempfile.TemporaryDirectory(prefix="local-ai-tools-health-")
    tmpdir = Path(tmp.name)
    code = f"""
import json, time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from kokoro import KModel, KPipeline
torch.backends.cudnn.enabled = False
sample_rate = 24000
started = time.perf_counter()
model = KModel(config={str(env.config_path())!r}, model={str(env.model_path())!r}).eval().cuda()
torch.cuda.synchronize()
pipeline = KPipeline(lang_code="a", model=model, device="cuda")
chunks = []
words = 0
with torch.inference_mode():
    for result in pipeline("Setup probe.", voice={str(env.voice_path(env.default_voice()))!r}, speed=1.0, model=model):
        if result.audio is not None:
            chunks.append(result.audio.detach().cpu().numpy().astype(np.float32))
        for token in result.tokens or []:
            if getattr(token, "text", "").strip() and getattr(token, "start_ts", None) is not None:
                words += 1
torch.cuda.synchronize()
audio = np.concatenate(chunks)
out = Path({str(tmpdir / "probe.wav")!r})
sf.write(str(out), audio, sample_rate)
print(json.dumps({{"ok": True, "generation_seconds": time.perf_counter() - started, "audio_seconds": len(audio) / sample_rate, "words": words, "output_file": str(out)}}))
"""
    payload = run_backend_probe(code, timeout=180)
    if keep_output:
        payload["kept_output_dir"] = str(tmpdir)
    else:
        tmp.cleanup()
    return payload


def recommendations(checks: dict[str, dict[str, Any]]) -> list[str]:
    recs: list[str] = []
    if not checks.get("gpu_devices", {}).get("ok"):
        recs.append("Verify /dev/kfd exists and your user can access /dev/dri/renderD*.")
        recs.append("Verify your user is in render/video groups where required.")
    if not checks.get("pytorch_rocm", {}).get("ok"):
        recs.append("Verify the machine has a ROCm-supported AMD GPU and a compatible PyTorch ROCm wheel.")
        recs.append("Try local-ai-tools setup --torch rocm6.3 if rocm6.4 wheels fail.")
    if not checks.get("assets", {}).get("ok"):
        recs.append("Run local-ai-tools setup to create the venv and stage Kokoro model assets.")
    return recs


def print_human(report: dict[str, Any]) -> None:
    print("local-ai-tools health\n")
    labels = [
        ("wrapper", "wrapper"),
        ("setup_env", "setup env"),
        ("assets", "assets"),
        ("gpu_devices", "gpu devices"),
        ("pytorch_rocm", "pytorch rocm"),
        ("kokoro_python", "kokoro python"),
        ("daemon", "daemon"),
        ("synthesis_probe", "synthesis probe"),
    ]
    for key, label in labels:
        item = report["checks"][key]
        if item.get("skipped"):
            state = "skipped"
        elif item.get("ok"):
            state = "ok"
        elif key == "daemon" and not item.get("running"):
            state = "not running"
        else:
            state = "failed"
        detail = item.get("env_file") or item.get("device_name") or item.get("message") or item.get("error") or ""
        print(f"{label:<16} {state:<12} {detail}")
    print(f"\noverall          {report['status']}")
    for rec in report["recommendations"]:
        print(f"- {rec}")
