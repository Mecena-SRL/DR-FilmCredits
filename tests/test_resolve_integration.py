import os

import fakes
from drfc import resolve_bridge, ui_wizard
from helpers import sample_project


def test_insert_with_still_holder(tmp_path):
    r = fakes.FakeResolve(still_ok=True)
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    res = sess.insert(p, "end", str(tmp_path), where="playhead")
    assert res["ok"] and res["method"] == "clip"
    item = res["item"]
    assert item.dur == res["frames"]
    assert item.start == sess.tc_to_frames("01:00:10:00", 25)
    assert r.tl.names[item.track] == resolve_bridge.TRACK_NAME
    assert p["format"]["width"] == 3840 and p["format"]["fps"] == 25.0
    assert item.names == ["DRFC_Prova_end"]
    assert os.path.exists(res["path"])


def test_insert_falls_back_to_image_sequence(tmp_path):
    r = fakes.FakeResolve(still_ok=False)
    sess = resolve_bridge.ResolveSession(r)
    res = sess.insert(sample_project(), "end", str(tmp_path))
    assert res["ok"] and res["item"].dur == res["frames"]
    seq_dir = [d for d in os.listdir(str(tmp_path)) if d.endswith("_holder_seq")][0]
    assert len(os.listdir(str(tmp_path / seq_dir))) == res["frames"]


def test_comp_offset_is_realigned(tmp_path):
    r = fakes.FakeResolve()
    fakes.FakeItem.comp_start = 1000
    try:
        sess = resolve_bridge.ResolveSession(r)
        res = sess.insert(sample_project(), "end", str(tmp_path))
        text = open(res["path"], encoding="utf-8").read()
        assert "RenderRange = { 1000," in text
        assert len(res["item"].names) == 1
    finally:
        fakes.FakeItem.comp_start = 0


def test_regenerate_replaces_previous(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    first = sess.insert(p, "end", str(tmp_path))
    second = sess.insert(p, "end", str(tmp_path), where="replace")
    assert first["item"] in r.tl.deleted
    assert second["item"].start == first["item"].start
    assert sum(len(t) for t in r.tl.tracks.values()) == 1


def test_drop_frame_timecode():
    f = resolve_bridge.ResolveSession.tc_to_frames
    assert f("00:01:00;02", 29.97, True) == 1800
    assert f("00:10:00;00", 29.97, True) == 17982


def test_transparent_png(tmp_path):
    from drfc import imageinfo
    path = resolve_bridge.write_transparent_png(str(tmp_path / "h.png"), 3840, 2160)
    assert imageinfo.image_size(path) == (3840, 2160)
    assert os.path.getsize(path) < 200000


def _wizard(tmp_path, request=None):
    fu = fakes.FakeFusion(request=request)
    w = ui_wizard.Wizard(fu, fakes.FakeBmd(), fakes.FakeResolve())
    w.build()
    return w


def test_wizard_end_to_end(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(ui_wizard.webbrowser, "open", lambda u: opened.append(u))
    w = _wizard(tmp_path)
    win = w.win
    it = w.it
    assert it["Blocks"].top, "elenco blocchi popolato"
    it["Title"].Text = "Il film"
    it["Owner"].Text = "Acme"
    for i in range(5):
        win.fire("Step%d" % i, "Clicked")
    # seleziona la sequenza 'end' e modifica il primo blocco
    w.it["Seq"].CurrentIndex = 1
    win.fire("Seq", "CurrentIndexChanged")
    row = it["Blocks"].top[0]
    win.fire("Blocks", "ItemClicked", item=row)
    it["BlockText"].PlainText = "director: Giulia Ferri"
    win.fire("Apply", "Clicked")
    assert w.seq()["blocks"][0]["names"] == ["Giulia Ferri"]
    # aggiunge un blocco 'cast' e lo compila
    it["AddType"].CurrentIndex = list(ui_wizard.BLOCK_TYPES).index("cast")
    win.fire("Add", "Clicked")
    it["BlockText"].PlainText = "Marta Lodi = Elena"
    win.fire("Apply", "Clicked")
    assert w.block()["rows"] == [{"actor": "Marta Lodi", "character": "Elena"}]
    win.fire("Up", "Clicked")
    win.fire("Dup", "Clicked")
    win.fire("Del", "Clicked")
    win.fire("Toggle", "Clicked")
    win.fire("InsertRole", "Clicked")
    # stile e tempi
    win.fire("SApply", "Clicked")
    it["Fit"].CurrentIndex = 1
    it["Target"].Value = 40
    win.fire("Calc", "Clicked")
    assert "px/frame" in it["TimingOut"].PlainText
    # verifica, anteprima, inserimento
    win.fire("Check", "Clicked")
    assert "errori" in it["Results"].PlainText
    monkeypatch.setattr(ui_wizard.resolve_bridge, "default_work_dir", lambda p=None: str(tmp_path / "work"))
    win.fire("Preview", "Clicked")
    assert opened and opened[0].endswith(".html")
    win.fire("Insert", "Clicked")
    assert "✔" in it["Results"].PlainText, it["Results"].PlainText + it["Status"].Text


def test_wizard_save_and_reopen(tmp_path):
    path = str(tmp_path / "p.drfc.json")
    w = _wizard(tmp_path, request=path)
    w.it["Title"].Text = "Salvato"
    w.win.fire("Save", "Clicked")
    assert os.path.exists(path)
    w2 = _wizard(tmp_path)
    assert w2.project["meta"]["title"] == "Salvato"
