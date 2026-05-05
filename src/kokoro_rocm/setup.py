from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from . import env
from .health import build_report

MODEL_URL = "https://github.com/remsky/Kokoro-FastAPI/releases/download/v1.4/kokoro-v1_0.pth"
CONFIG_URL = "https://github.com/remsky/Kokoro-FastAPI/releases/download/v1.4/config.json"
VOICE_URL_TEMPLATE = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/{voice}.pt"

TORCH_INDEXES = {
    "rocm6.4": "https://download.pytorch.org/whl/rocm6.4",
    "rocm6.3": "https://download.pytorch.org/whl/rocm6.3",
    "cpu": "https://download.pytorch.org/whl/cpu",
}


def run_setup(args) -> int:
    try:
        result = setup(args)
    except Exception as exc:
        print(f"kokoro-rocm setup failed: {exc}", file=sys.stderr)
        return 6
    print(f"wrote {result['env_file']}")
    print(f"wrote {result['probe_file']}")
    if result["status"] == "ok":
        print("setup ok")
        print('next: printf "Hello" | kokoro-rocm -o /tmp/hello.wav')
        return 0
    print("setup completed but health probe failed", file=sys.stderr)
    return 6


def setup(args) -> dict:
    data_dir = Path(args.data_dir).expanduser().resolve() if args.data_dir else env.default_data_dir()
    venv = data_dir / ".venv"
    model_dir = data_dir / "models" / "v1_0"
    voices_dir = data_dir / "voices" / "v1_0"
    model = model_dir / "kokoro-v1_0.pth"
    config = model_dir / "config.json"
    voice = voices_dir / f"{args.voice}.pt"
    for path in [model_dir, voices_dir]:
        path.mkdir(parents=True, exist_ok=True)

    if args.torch == "existing":
        if not args.python_path:
            raise ValueError("--torch existing requires --python-path")
        python = Path(args.python_path).expanduser().absolute()
        if not python.exists():
            raise FileNotFoundError(python)
    else:
        python = venv / "bin" / "python"
        if args.force and venv.exists():
            shutil.rmtree(venv)
        run(["uv", "venv", str(venv), "--python", args.python])
        run(["uv", "pip", "install", "--python", str(python), "torch", "torchvision", "torchaudio", "--index-url", TORCH_INDEXES[args.torch]])
        run(["uv", "pip", "install", "--python", str(python), "kokoro==0.9.4", "soundfile", "numpy"])

    stage_from_existing(model, config, voice)
    if not args.no_download:
        download(args.model_url or MODEL_URL, model)
        download(args.config_url or CONFIG_URL, config)
        download(args.voice_url or VOICE_URL_TEMPLATE.format(voice=args.voice), voice)

    validate_assets(python, model, config, voices_dir, voice)
    env_file = env.user_env_file(data_dir)
    write_env(env_file, python, model, config, voices_dir, args.voice)
    os.environ["KOKORO_ROCM_PYTHON"] = str(python)
    os.environ["KOKORO_ROCM_MODEL"] = str(model)
    os.environ["KOKORO_ROCM_CONFIG"] = str(config)
    os.environ["KOKORO_ROCM_VOICES_DIR"] = str(voices_dir)
    os.environ["KOKORO_ROCM_DEFAULT_VOICE"] = args.voice
    probe_file = data_dir / "setup-probe.json"
    health_args = type("HealthArgs", (), {"socket": None, "probe_synthesis": True, "keep_probe_output": False})()
    report = build_report(health_args)
    probe_file.write_text(json.dumps(report, indent=2))
    return {"status": report["status"], "env_file": str(env_file), "probe_file": str(probe_file)}


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")


def stage_from_existing(model: Path, config: Path, voice: Path) -> None:
    sources = [
        (Path(env.DEFAULT_MODEL), model),
        (Path(env.DEFAULT_CONFIG), config),
        (Path(env.DEFAULT_VOICES_DIR) / voice.name, voice),
    ]
    for src, dest in sources:
        if dest.exists() or not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)


def write_env(env_file: Path, python: Path, model: Path, config: Path, voices_dir: Path, voice: str) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(
        "\n".join(
            [
                f"KOKORO_ROCM_PYTHON={python}",
                f"KOKORO_ROCM_MODEL={model}",
                f"KOKORO_ROCM_CONFIG={config}",
                f"KOKORO_ROCM_VOICES_DIR={voices_dir}",
                f"KOKORO_ROCM_DEFAULT_VOICE={voice}",
                "",
            ]
        )
    )
    env_file.chmod(0o644)


def validate_assets(python: Path, model: Path, config: Path, voices_dir: Path, voice: Path) -> None:
    if not python.exists():
        raise FileNotFoundError(python)
    if not model.exists() or model.stat().st_size < 100 * 1024 * 1024:
        raise RuntimeError(f"model missing or too small: {model}")
    if not config.exists():
        raise FileNotFoundError(config)
    json.loads(config.read_text())
    if not voices_dir.exists():
        raise FileNotFoundError(voices_dir)
    if not voice.exists() or voice.stat().st_size < 10 * 1024:
        raise RuntimeError(f"voice missing or too small: {voice}")
