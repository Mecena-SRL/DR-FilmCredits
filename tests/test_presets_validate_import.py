import os

import pytest

from drfc import engine, i18n, io_import, model, presets, validate
from helpers import sample_project


@pytest.mark.parametrize("pid", [p["id"] for p in presets.list_presets()])
def test_presets_are_consistent(pid):
    pr = presets.load_preset(pid)
    roles, depts = i18n.roles()["roles"], i18n.roles()["departments"]
    headers = i18n.phrases("en")["headers"]
    for s in pr["sequences"]:
        for b in s["blocks"]:
            assert b["type"] in model.BLOCK_TYPES
            if b.get("role"):
                assert b["role"] in roles, (pid, b["role"])
            for r in b.get("rows", []):
                if r.get("role"):
                    assert r["role"] in roles, (pid, r["role"])
            h = b.get("heading") or b.get("caption") or ""
            if h.startswith("dept:"):
                assert h[5:] in depts
            if h.startswith("h:"):
                assert h[2:] in headers, (pid, h)
            for it in b.get("items", []):
                if it.get("key"):
                    assert it["key"] in i18n.phrases("en")["legal"], (pid, it["key"])
    for c in pr.get("checks", []):
        if c.get("legal"):
            assert c["legal"] in i18n.phrases("en")["legal"]


@pytest.mark.parametrize("pid", [p["id"] for p in presets.list_presets()])
def test_preset_project_solves_when_filled(pid):
    p = presets.project_from_preset(pid, title="T", copyright_owner="O")
    for s in p["sequences"]:
        for b in s["blocks"]:
            if b["type"] in ("credit", "card") and not b.get("lines"):
                b["names"] = ["Nome Cognome"]
            for r in b.get("rows", []):
                if "role" in r:
                    r["names"] = ["Nome Cognome"]
            if b["type"] == "cast":
                b["rows"] = [{"actor": "Attore", "character": "Personaggio"}]
            if b["type"] == "title":
                b["text"] = "T"
    _c, results, issues = engine.solve_all(p)
    assert results
    for seq, lay, tl, notes in results:
        assert tl["total_frames"] > 0


def test_funding_requires_logo_and_wording():
    p = sample_project()
    p["meta"]["funding"] = ["mic_tax_credit"]
    issues = validate.check_project(p)
    codes = {i["code"] for i in issues}
    assert "funding_logo" in codes and "funding_legal" in codes


def test_ai_disclosure_required():
    p = sample_project()
    p["meta"]["ai_used"] = True
    assert any(i["code"] == "ai" for i in validate.check_project(p))


def test_music_licensor_required():
    p = sample_project()
    p["sequences"][1]["blocks"][4]["cues"].append({"title": "Y", "writers": ["Z"], "agreement": "licensed"})
    assert any(i["code"] == "music_licensor" for i in validate.check_project(p))


def test_strip_empty_removes_unfilled_blocks():
    p = presets.project_from_preset("it_cinema", title="Titolo")
    clean = validate.strip_empty(p)
    end = [s for s in clean["sequences"] if s["id"] == "end"][0]
    assert all(b["type"] in ("legal", "title") for b in end["blocks"])


def test_csv_import_semicolon(tmp_path):
    path = tmp_path / "c.csv"
    io_import.write_template(str(path))
    p = presets.project_from_preset("it_cinema", title="T")
    n = io_import.import_file(p, str(path))
    assert n == 9
    end = [s for s in p["sequences"] if s["id"] == "end"][0]
    cam = [b for b in end["blocks"] if b.get("heading") == "dept:camera"][0]
    names = {r["role"]: r["names"] for r in cam["rows"]}
    assert names["first_ac"] == ["Nome Cognome"]
    music = [b for b in end["blocks"] if b["type"] == "music"][0]
    assert music["cues"][0]["writers"] == ["Autore 1", "Autore 2"]
    loc = [b for b in end["blocks"] if b["type"] == "agreements" and b["kind"] == "location"][0]
    assert loc["entries"][0]["agreement"] == "free"
    # l'import rispetta l'ordine: loghi e diciture restano in fondo
    assert end["blocks"][-1]["type"] == "legal"


def test_save_load_roundtrip(tmp_path):
    p = sample_project()
    path = str(tmp_path / "x.drfc.json")
    model.save(p, path)
    q = model.load(path)
    assert q["sequences"] == p["sequences"]


def test_examples_build(examples_dir, tmp_path):
    for fn in os.listdir(examples_dir):
        if fn.endswith(".drfc.json"):
            p = model.load(os.path.join(examples_dir, fn))
            files, results, issues = engine.export(p, str(tmp_path / fn))
            assert files and not [i for i in issues if i["level"] == "error"], issues
