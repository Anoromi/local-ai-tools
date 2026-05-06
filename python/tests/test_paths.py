from pathlib import Path

from kokoro_rocm.paths import sidecar_path


def test_sidecar_path():
    assert sidecar_path(Path("/tmp/foo.wav")) == Path("/tmp/foo.json")
