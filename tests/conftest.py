import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_user_dirs(tmp_path, monkeypatch):
    """Cache font, calibrazione e impostazioni in una cartella temporanea."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    yield


@pytest.fixture
def examples_dir():
    return os.path.join(ROOT, "examples")
