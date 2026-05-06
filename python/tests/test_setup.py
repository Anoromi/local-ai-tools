import json
from pathlib import Path

import pytest

from kokoro_rocm import setup


def test_torch_indexes():
    assert setup.TORCH_INDEXES["rocm6.4"] == "https://download.pytorch.org/whl/rocm6.4"
    assert setup.TORCH_INDEXES["rocm6.3"] == "https://download.pytorch.org/whl/rocm6.3"
    assert setup.TORCH_INDEXES["cpu"] == "https://download.pytorch.org/whl/cpu"


def test_existing_requires_python_path(tmp_path):
    args = type("Args", (), {"torch": "existing", "python_path": None, "data_dir": str(tmp_path), "voice": "af_sarah"})()
    with pytest.raises(ValueError):
        setup.setup(args)


def test_write_env(tmp_path):
    env_file = tmp_path / "env"
    setup.write_env(env_file, Path("/venv/bin/python"), Path("/m.pth"), Path("/config.json"), Path("/voices"), "af_sarah")
    values = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if line)
    assert values["KOKORO_ROCM_PYTHON"] == "/venv/bin/python"
    assert values["KOKORO_ROCM_DEFAULT_VOICE"] == "af_sarah"


def test_validate_assets_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup.validate_assets(tmp_path / "python", tmp_path / "model.pth", tmp_path / "config.json", tmp_path / "voices", tmp_path / "voice.pt")


def test_validate_assets_rejects_small_model(tmp_path):
    python = tmp_path / "python"
    python.write_text("")
    model = tmp_path / "model.pth"
    model.write_bytes(b"x")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({}))
    voices = tmp_path / "voices"
    voices.mkdir()
    voice = voices / "af_sarah.pt"
    voice.write_bytes(b"x" * 20000)
    with pytest.raises(RuntimeError):
        setup.validate_assets(python, model, config, voices, voice)
