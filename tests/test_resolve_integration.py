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


def _items(r):
    return [it for t in r.tl.tracks.values() for it in t]


def test_unchanged_section_is_not_touched(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    sess.sync(p, str(tmp_path))
    before = {id(i): len(i.comps) for i in _items(r)}
    res = sess.sync(p, str(tmp_path))
    assert all(x["action"] == "unchanged" for x in res["sections"])
    assert {id(i): len(i.comps) for i in _items(r)} == before


def test_changed_text_updates_in_place_and_keeps_user_nodes(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    sess.sync(p, str(tmp_path), only=["end"])
    item = [i for i in _items(r) if "_end_holder" in i.mpi.path][0]
    item.props["Opacity"] = 80
    comp = item.comps[-1]
    # l'utente aggiunge un Glow tra l'ultimo merge e MediaOut
    last = comp.tools["MediaOut1"].links["Input"]
    glow = fakes.FakeTool("MyGlow", "SoftGlow")
    glow.links["Input"] = last
    comp.tools["MyGlow"] = glow
    comp.tools["MediaOut1"].links["Input"] = glow
    p["sequences"][1]["blocks"][0]["names"] = ["Giulia Ferri Rossi"]  # stessa durata
    res = sess.sync(p, str(tmp_path), only=["end"])
    assert res["sections"][0]["action"] == "updated"
    assert res["sections"][0]["item"] is item
    new = item.comps[-1]
    assert new.pasted and new.pasted[0]["tools"] == ["MyGlow"]
    assert new.tools["MediaOut1"].links["Input"].Name == "MyGlow"
    assert new.tools["MyGlow"].links["Input"].Name.startswith("DRFC_")
    assert "DRFC_Prova_end_prev" in item.names and "DRFC_Prova_end" in item.names
    assert item.props["Opacity"] == 80


def test_duration_change_replaces_clip_keeping_position_and_properties(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    sess.sync(p, str(tmp_path), only=["end"])
    old = _items(r)[0]
    old.start = 95000
    old.props.update({"ZoomX": 0.9, "Opacity": 70})
    old.color = "Orange"
    p["sequences"][1]["blocks"][3]["names"] += ["Altra Persona %d" % i for i in range(30)]
    res = sess.sync(p, str(tmp_path), only=["end"])
    sec = res["sections"][0]
    assert sec["action"] == "replaced"
    new = sec["item"]
    assert new is not old and old in r.tl.deleted
    assert new.start == 95000 and new.track == old.track
    assert new.props["ZoomX"] == 0.9 and new.props["Opacity"] == 70 and new.color == "Orange"
    assert new.dur == sec["frames"]


def test_locked_section_is_never_regenerated(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    sess.sync(p, str(tmp_path), only=["end"])
    sess.set_locked(p, "end")
    p["sequences"][1]["blocks"][0]["names"] = ["Cambiato"]
    res = sess.sync(p, str(tmp_path), only=["end"])
    assert res["sections"][0]["action"] == "locked"
    assert [s for _i, _l, s in sess.section_status(p, only=["end"])] == ["locked"]


def test_cards_are_separate_clips_and_keep_user_position(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    p = sample_project()
    res = sess.sync(p, str(tmp_path), only=["opening"])
    assert len(res["sections"]) == 3
    starts = [x["item"].start for x in res["sections"]]
    assert starts == sorted(starts) and len(set(starts)) == 3
    moved = res["sections"][2]["item"]
    moved.start = 123456  # l'utente sposta il cartello sopra un'altra inquadratura
    p["sequences"][0]["blocks"][2]["names"] = ["Giulia F."]
    res2 = sess.sync(p, str(tmp_path), only=["opening"])
    actions = [x["action"] for x in res2["sections"]]
    assert actions[:2] == ["unchanged", "unchanged"]
    assert res2["sections"][2]["item"].start == 123456
    status = dict((i, s) for i, _l, s in sess.section_status(p, only=["opening"]))
    assert set(status.values()) == {"unchanged"}


def test_per_sequence_mode_for_cards(tmp_path):
    r = fakes.FakeResolve()
    sess = resolve_bridge.ResolveSession(r)
    res = sess.sync(sample_project(), str(tmp_path), only=["opening"], card_mode="per_sequence")
    assert len(res["sections"]) == 1


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


def _click_row(w, kind, pred=lambda r: True):
    i = next(i for i, r in enumerate(w.rows) if r["kind"] == kind and pred(r))
    w.win.fire("Outline", "ItemClicked", item=w.items[i])
    return i


def test_wizard_three_steps_flow(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(ui_wizard.webbrowser, "open", lambda u: opened.append(u))
    monkeypatch.setattr(ui_wizard.resolve_bridge, "default_work_dir", lambda p=None: str(tmp_path / "work"))
    w = _wizard(tmp_path)
    win, it = w.win, w.it
    assert it["Stack"].CurrentIndex == 0  # progetto nuovo: parte dal passo 1
    # passo 1: crea tutto con i segnaposto
    it["Work"].CurrentIndex = ui_wizard.guide.WORK_TYPES.index("corto")
    win.fire("Work", "CurrentIndexChanged")
    it["Title"].Text = "Il corto"
    it["Placeholders"].Checked = True
    win.fire("Create", "Clicked")
    assert it["Stack"].CurrentIndex == 1
    assert ui_wizard.placeholders.count(w.project) > 0
    assert w.rows and any(r["kind"] == "entry" for r in w.rows)
    # passo 2: sostituisco il nome di una voce
    i = _click_row(w, "entry")
    row = w.rows[i]
    it["RNames"].Text = "Luca Marini"
    win.fire("RSave", "Clicked")
    _r, names = ui_wizard.outline.entry_values(w.project, row)
    assert names == ["Luca Marini"]
    # elimina i segnaposto rimasti
    win.fire("Unfilled", "Clicked")
    assert ui_wizard.placeholders.count(w.project) == 0
    # passo 3: timeline
    win.fire("Next1", "Clicked")
    win.fire("Next2", "Clicked") if "Next2" in it else win.fire("Step2", "Clicked")
    win.fire("Preview", "Clicked")
    assert opened and opened[0].endswith(".html")
    win.fire("SyncChanged", "Clicked")
    assert "\u2714" in it["Results"].PlainText
    win.fire("SyncChanged", "Clicked")
    assert "Invariata" in it["Results"].PlainText


def test_wizard_second_sync_after_edit_updates_only_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_wizard.resolve_bridge, "default_work_dir", lambda p=None: str(tmp_path / "work"))
    w = _wizard(tmp_path)
    w.win.fire("Create", "Clicked")
    w.win.fire("Step2", "Clicked")
    w.win.fire("SyncChanged", "Clicked")
    w.win.fire("Step1", "Clicked")
    _click_row(w, "entry")
    w.it["RNames"].Text = "Nome Nuovo"
    w.win.fire("RSave", "Clicked")
    w.win.fire("Step2", "Clicked")
    w.win.fire("SyncChanged", "Clicked")
    txt = w.it["Results"].PlainText
    assert "\u2714" in txt and "Invariata" not in txt.split("\n")[0]


def test_wizard_placeholders_can_be_off(tmp_path):
    w = _wizard(tmp_path)
    w.it["Placeholders"].Checked = False
    w.win.fire("Create", "Clicked")
    assert ui_wizard.placeholders.count(w.project) == 0


def test_wizard_move_and_delete_section(tmp_path):
    w = _wizard(tmp_path)
    w.win.fire("Create", "Clicked")
    i = _click_row(w, "section")
    r = w.rows[i]
    blocks = w.project["sequences"][r["seq"]]["blocks"]
    first, n = blocks[r["block"]], len(blocks)
    w.win.fire("Down", "Clicked")
    assert blocks[r["block"] + 1] is first
    w.win.fire("DelSec", "Clicked")
    assert len(w.project["sequences"][r["seq"]]["blocks"]) == n - 1


def test_wizard_save_and_reopen(tmp_path):
    path = str(tmp_path / "p.drfc.json")
    w = _wizard(tmp_path, request=path)
    w.it["Title"].Text = "Salvato"
    w.win.fire("Create", "Clicked")
    w.win.fire("Save", "Clicked")
    assert os.path.exists(path)
    w2 = _wizard(tmp_path)
    assert w2.project["meta"]["title"] == "Salvato"


def test_startup_events_in_queue_do_not_close_or_change_anything(tmp_path):
    """Regressione 'flash': in UIManager gli eventi dei menu riempiti dal codice arrivano
    dopo la build; non devono chiudere la finestra ne' toccare il progetto."""
    import copy
    fu = fakes.FakeFusion()
    w = ui_wizard.Wizard(fu, fakes.QueuedBmd(), fakes.FakeResolve())
    w.build()
    before = copy.deepcopy(w.project)
    lang = w.lang
    w.disp.RunLoop()
    assert w.disp.exited == 0 and not w.restart
    assert w.lang == lang
    assert w.project == before


def test_run_does_not_loop_on_startup(tmp_path):
    fu = fakes.FakeFusion()
    bmd = fakes.QueuedBmd()
    w = ui_wizard.Wizard(fu, bmd, fakes.FakeResolve())
    w.run()
    assert w.disp.loops == 1


def test_real_language_change_restarts_once(tmp_path):
    fu = fakes.FakeFusion()
    w = ui_wizard.Wizard(fu, fakes.QueuedBmd(), fakes.FakeResolve())
    w.build()
    w.disp.RunLoop()
    other = (list(ui_wizard.i18n.LANGUAGES).index(w.lang) + 1) % 5
    w.it["UiLang"].CurrentIndex = other
    w.disp.RunLoop()
    assert w.restart and w.disp.exited == 1


# ------------------------------------------------------------------ calibrazione automatica
def _sync_one(tmp_path, k_true=None, readable=True):
    from drfc import fusion_constants
    r = fakes.FakeResolve()
    if k_true is not None:
        fakes.ProbeTool.k_true = k_true
    fakes.ProbeTool.comp_width = 3840.0
    if not readable:
        fakes.ProbeTool.render = lambda self: None
    sess = resolve_bridge.ResolveSession(r)
    res = sess.sync(sample_project(), str(tmp_path), only=["end"])
    return r, sess, res, fusion_constants


def _restore_probe():
    import importlib
    importlib.reload(fakes)


def test_auto_calibration_measures_and_regenerates_with_true_scale(tmp_path):
    try:
        r, sess, res, fc = _sync_one(tmp_path, k_true=1.0 / 1.35)
        saved = fc.saved()
        assert saved["measured"] and saved["resolve_version"] == "20.0.0.1"
        assert abs(saved["em_per_size_width"] - 1.0 / 1.35) < 0.002  # le side-bearing non falsano la misura
        item = res["sections"][0]["item"]
        # il clip ha un solo comp reale (la sonda temporanea e' stata eliminata) e usa la scala misurata
        assert item.names == ["DRFC_Prova_end"]
        text = open(res["sections"][0]["path"], encoding="utf-8").read()
        import re
        size = float(re.search(r"Size = Input \{ Value = ([0-9.]+)", text).group(1))
        assert size * 3840 * (1.0 / 1.35) > 15  # px/em plausibili con la scala vera
        # seconda generazione: non misura di nuovo
        sess2 = resolve_bridge.ResolveSession(r)
        sess2.sync(sample_project(), str(tmp_path), only=["end"])
        assert sess2._cal_done and fc.saved()["measured"]
    finally:
        _restore_probe()


def test_auto_calibration_falls_back_silently_when_unreadable(tmp_path):
    try:
        r, sess, res, fc = _sync_one(tmp_path, readable=False)
        assert res["sections"][0]["ok"]
        saved = fc.saved()
        assert saved.get("unmeasurable") == "20.0.0.1" and "em_per_size_width" not in saved
        assert fc.load()["em_per_size_width"] == fc.DEFAULTS["em_per_size_width"]
        assert res["sections"][0]["item"].names == ["DRFC_Prova_end"]
    finally:
        _restore_probe()


def test_recalibrate_clears_saved_values(tmp_path):
    from drfc import calibration, fusion_constants
    fusion_constants.save({"em_per_size_width": 0.9, "resolve_version": "x"})
    assert calibration.reset() and fusion_constants.saved() == {}


def test_main_shows_error_window_and_logs_instead_of_vanishing(tmp_path, monkeypatch):
    from drfc import log

    def boom(self):
        raise RuntimeError("build rotta")
    monkeypatch.setattr(ui_wizard.Wizard, "build", boom)
    fu = fakes.FakeFusion()
    bmd = fakes.FakeBmd()
    ui_wizard.main(fu, bmd, None)  # non deve sollevare
    text = open(log.path(), encoding="utf-8").read()
    assert "build rotta" in text and "Traceback" in text


def test_log_rotates(tmp_path):
    from drfc import log
    for _ in range(3000):
        log.write("x" * 200)
    import os
    assert os.path.exists(log.path() + ".1") and os.path.getsize(log.path()) < log.MAX_BYTES + 1000
