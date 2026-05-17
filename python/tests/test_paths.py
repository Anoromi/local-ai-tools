from pathlib import Path

from local_ai_tools.paths import sidecar_path


def test_sidecar_path():
    assert sidecar_path(Path("/tmp/foo.wav")) == Path("/tmp/foo.json")
