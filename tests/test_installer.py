import importlib.util
import os
import sys


def _load():
    spec = importlib.util.spec_from_file_location("drfc_install", os.path.join(os.path.dirname(__file__), "..", "install", "install.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _setup(m, tmp_path, monkeypatch):
    fusion = tmp_path / "Fusion"
    monkeypatch.setattr(m, "resolve_fusion_dir", lambda: str(fusion))
    monkeypatch.setattr(m, "user_base", lambda: str(tmp_path / "base"))
    monkeypatch.setattr(sys, "argv", ["install.py", "--no-fonts"])
    return fusion / "Templates" / "Edit" / "Titles" / "DR-FilmCredits"


def test_install_does_not_add_titles_and_removes_old_ones(tmp_path, monkeypatch):
    m = _load()
    titles = _setup(m, tmp_path, monkeypatch)
    titles.mkdir(parents=True)
    (titles / "old.setting").write_text("x")
    m.install()
    assert not titles.exists()
    assert (tmp_path / "Fusion" / "Scripts" / "Utility" / "DR-FilmCredits.py").exists()


def test_install_with_titles_option(tmp_path, monkeypatch):
    m = _load()
    titles = _setup(m, tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["install.py", "--no-fonts", "--with-titles"])
    m.install()
    assert titles.is_dir() and any(f.endswith(".setting") for f in os.listdir(titles))
