from __future__ import annotations

import os
import subprocess
from pathlib import Path

DEFAULT_MODEL = "/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/kokoro-v1_0.pth"
DEFAULT_CONFIG = "/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/models/v1_0/config.json"
DEFAULT_VOICES_DIR = "/tmp/kokoro-bench/api-test/Kokoro-FastAPI/api/src/voices/v1_0"
DEFAULT_PYTHON = "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python"


def default_data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "kokoro-rocm"


def config_env_file() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kokoro-rocm" / "env"


def user_env_file(data_dir: Path | None = None) -> Path:
    return (data_dir or default_data_dir()) / "env"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def discovered_env() -> tuple[Path | None, dict[str, str]]:
    for path in [config_env_file(), user_env_file()]:
        values = load_env_file(path)
        if values:
            return path, values
    return None, {}


def configured_value(name: str, fallback: str) -> str:
    if os.environ.get(name) and os.environ[name] != fallback:
        return os.environ[name]
    _path, values = discovered_env()
    return values.get(name, fallback)


def effective_config() -> dict[str, str]:
    env_file, values = discovered_env()
    keys = {
        "KOKORO_ROCM_PYTHON": DEFAULT_PYTHON,
        "KOKORO_ROCM_MODEL": DEFAULT_MODEL,
        "KOKORO_ROCM_CONFIG": DEFAULT_CONFIG,
        "KOKORO_ROCM_VOICES_DIR": DEFAULT_VOICES_DIR,
        "KOKORO_ROCM_DEFAULT_VOICE": "af_sarah",
    }
    result = {key: os.environ.get(key) or values.get(key) or fallback for key, fallback in keys.items()}
    result["KOKORO_ROCM_ENV_FILE"] = str(env_file) if env_file else ""
    return result


def backend_python() -> Path:
    return Path(configured_value("KOKORO_ROCM_PYTHON", DEFAULT_PYTHON))


def model_path() -> Path:
    return Path(configured_value("KOKORO_ROCM_MODEL", DEFAULT_MODEL))


def config_path() -> Path:
    return Path(configured_value("KOKORO_ROCM_CONFIG", DEFAULT_CONFIG))


def voices_dir() -> Path:
    return Path(configured_value("KOKORO_ROCM_VOICES_DIR", DEFAULT_VOICES_DIR))


def default_voice() -> str:
    return configured_value("KOKORO_ROCM_DEFAULT_VOICE", "af_sarah")


def voice_path(voice: str) -> Path:
    candidate = Path(voice)
    if candidate.exists():
        return candidate
    return voices_dir() / f"{voice}.pt"


def rocm_env() -> dict[str, str]:
    env = os.environ.copy()
    _path, values = discovered_env()
    for key, value in values.items():
        env.setdefault(key, value)
    env.setdefault("HIP_VISIBLE_DEVICES", "0")
    env.setdefault("ROCR_VISIBLE_DEVICES", "0")
    env.setdefault("PYTORCH_ROCM_ARCH", "gfx1151")
    env.setdefault("HSA_OVERRIDE_GFX_VERSION", "11.5.1")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    return _compiler_include_env(env)


def _compiler_include_env(env: dict[str, str]) -> dict[str, str]:
    try:
        gcc_include = subprocess.check_output(["gcc", "-print-file-name=include"], text=True).strip()
        gcc_version = subprocess.check_output(["gcc", "-dumpversion"], text=True).strip()
        gcc_prefix = Path(gcc_include).parents[3]
        rocm_site = backend_python().parents[1] / "lib" / "python3.12" / "site-packages"
        rocm_llvm = rocm_site / "_rocm_sdk_core" / "lib" / "llvm"
        rocm_libcxx = rocm_llvm / "include" / "c++" / "v1"
        rocm_clang_root = rocm_llvm / "lib" / "clang"
        rocm_clang = next(rocm_clang_root.glob("*/include"), None) if rocm_clang_root.exists() else None
        cxx_include = gcc_prefix / "include" / "c++" / gcc_version
        target_cxx_include = cxx_include / "x86_64-unknown-linux-gnu"
        parts = [
            str(p)
            for p in [rocm_libcxx, rocm_clang, cxx_include, target_cxx_include, Path(gcc_include)]
            if p and Path(p).exists()
        ]
        if parts:
            env["CPATH"] = ":".join(parts + ([env["CPATH"]] if env.get("CPATH") else []))
            env["CPLUS_INCLUDE_PATH"] = ":".join(parts + ([env["CPLUS_INCLUDE_PATH"]] if env.get("CPLUS_INCLUDE_PATH") else []))
            env["C_INCLUDE_PATH"] = ":".join([gcc_include] + ([env["C_INCLUDE_PATH"]] if env.get("C_INCLUDE_PATH") else []))
    except Exception:
        pass
    return env
