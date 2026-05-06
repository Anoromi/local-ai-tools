import json
from pathlib import Path

from kokoro_rocm import health


def test_recommendation_for_failed_pytorch():
    checks = {
        "gpu_devices": {"ok": True},
        "pytorch_rocm": {"ok": False},
        "assets": {"ok": True},
    }
    recs = health.recommendations(checks)
    assert any("ROCm-supported AMD GPU" in rec for rec in recs)


def test_daemon_missing_noncritical(monkeypatch, tmp_path):
    monkeypatch.setattr(health, "socket_path", lambda _sock=None: tmp_path / "missing.sock")
    result = health.check_daemon(None)
    assert result["ok"] is False
    assert result["running"] is False


def test_wrapper_reports_tools(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/bin/{name}")
    result = health.check_wrapper()
    assert result["ok"] is True
    assert result["tools"]["uv"] == "/bin/uv"


def test_backend_probe_parses_json(monkeypatch, tmp_path):
    python = tmp_path / "python"
    python.write_text("")
    monkeypatch.setattr(health.env, "backend_python", lambda: python)

    class Proc:
        returncode = 0
        stdout = json.dumps({"ok": True}) + "\n"
        stderr = ""

    monkeypatch.setattr(health.subprocess, "run", lambda *args, **kwargs: Proc())
    assert health.run_backend_probe("x")["ok"] is True


def test_probe_synthesis_critical(monkeypatch):
    args = type("Args", (), {"socket": None, "probe_synthesis": True, "keep_probe_output": False})()
    monkeypatch.setattr(health, "check_wrapper", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_setup_env", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_assets", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_gpu_devices", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_pytorch_rocm", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_kokoro_python", lambda: {"ok": True})
    monkeypatch.setattr(health, "check_daemon", lambda socket: {"ok": False})
    monkeypatch.setattr(health, "check_synthesis_probe", lambda keep: {"ok": False})
    assert health.build_report(args)["status"] == "failed"
