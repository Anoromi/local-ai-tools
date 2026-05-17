from local_ai_tools import env


def test_rocm_env_enables_aotriton_by_default(monkeypatch):
    monkeypatch.delenv("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", raising=False)
    assert env.rocm_env()["TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL"] == "1"


def test_rocm_env_allows_aotriton_override(monkeypatch):
    monkeypatch.setenv("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "0")
    assert env.rocm_env()["TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL"] == "0"
