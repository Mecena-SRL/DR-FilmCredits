import copy
import pytest
import fakes
from helpers import sample_project
from drfc import resolve_bridge, ui_wizard, workspace


def session():
    r = fakes.FakeResolve()
    return r, resolve_bridge.ResolveSession(r)


def end_item(r):
    return next(it for track in r.tl.tracks.values() for it in track if "_end_holder" in it.mpi.path)


def test_generate_never_overwrites_existing_or_deletes_copies(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"], operation="generate")
    original = end_item(r)
    duplicate = fakes.FakeItem(original.mpi, original.start + 5000, original.dur, original.track)
    r.tl.tracks[original.track].append(duplicate)
    p["sequences"][1]["blocks"][0]["names"] = ["Cambiato"]
    generated = s.sync(p, str(tmp_path), only=["end"], operation="generate")
    assert generated["sections"] == []
    updated = s.sync(p, str(tmp_path), only=["end"], operation="update", duration_policy="preserve")
    assert updated["sections"][0]["item"] is original
    assert duplicate in r.tl.tracks[duplicate.track] and not r.tl.deleted


def test_manual_move_trim_rename_and_title_change_keep_link(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"], operation="generate")
    item = end_item(r)
    item.start += 700
    item.dur -= 25
    duration, start = item.dur, item.start
    item.mpi.path = "renamed_media.png"
    p["meta"]["title"] = "Titolo nuovo"
    p["sequences"][1]["blocks"][0]["names"] = ["Nome modificato"]
    assert s.section_status(p, only=["end"])[0][2] == "trimmed"
    out = s.sync(p, str(tmp_path), only=["end"], operation="update", duration_policy="preserve")
    assert out["sections"][0]["item"] is item
    assert (item.start, item.dur) == (start, duration)
    assert s.section_status(p, only=["end"])[0][2] == "unchanged"


def test_missing_clip_is_not_implicitly_recreated(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    item = end_item(r)
    r.tl.tracks[item.track].remove(item)
    assert s.section_status(p, only=["end"])[0][2] == "missing"
    out = s.sync(p, str(tmp_path), only=["end"], operation="generate")
    assert out["sections"][0]["action"] == "missing"
    assert not any(r.tl.tracks.values())


def test_legacy_ambiguous_copies_are_not_deleted(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    original = end_item(r)
    p["render_state"]["end"].pop("clip_uid")
    r.tl.tracks[original.track].append(fakes.FakeItem(original.mpi, 100000, original.dur, original.track))
    p["sequences"][1]["blocks"][0]["names"] = ["Modificato"]
    out = s.sync(p, str(tmp_path), only=["end"])
    assert out["sections"][0]["action"] == "ambiguous" and not r.tl.deleted


def test_deleted_element_requires_separate_action(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["opening"])
    removed_id = s.section_status(p, only=["opening"])[-1][0]
    p["sequences"][0]["blocks"].pop()
    assert dict((sid, st) for sid, _, st in s.section_status(p))[removed_id] == "removed"
    s.sync(p, str(tmp_path), operation="update")
    assert not r.tl.deleted
    s.resolve_removed(p, removed_id, delete=False)
    assert removed_id not in p["render_state"] and not r.tl.deleted


def test_removed_locked_clip_cannot_be_deleted(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    s.set_locked(p, "end")
    p["sequences"].pop()
    with pytest.raises(ValueError, match="bloccata"):
        s.resolve_removed(p, "end", delete=True)
    assert not r.tl.deleted


def test_timeline_states_do_not_leak_and_restore_on_return(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    first = r.project.tl
    second = fakes.FakeTimeline()
    r.project.tl = second
    other = resolve_bridge.ResolveSession(r)
    assert other.section_status(p, only=["end"])[0][2] == "new"
    r.project.tl = first
    assert resolve_bridge.ResolveSession(r).section_status(p, only=["end"])[0][2] == "unchanged"


def test_frameleader_and_before_film_checked_before_any_mutation(tmp_path):
    r, s = session()
    p = sample_project()
    with pytest.raises(ValueError, match="frameleader"):
        s.sync(p, str(tmp_path), operation="generate", protected_until=90050,
               anchors={z: 90000 for z in workspace.ZONES})
    assert r.tl.GetTrackCount("video") == 2 and not any(r.tl.tracks.values())
    with pytest.raises(ValueError, match="Spazio insufficiente"):
        s.sync(p, str(tmp_path), operation="generate", protected_until=90050, film_start=90060,
               before_film=True, anchors={z: 90050 for z in workspace.ZONES})
    assert r.tl.GetTrackCount("video") == 2


def test_generation_creates_upper_tracks_colored_clips_and_keeps_edit(tmp_path):
    r, s = session()
    edit = fakes.FakeItem(fakes.FakeMPI("film.mov"), 90050, 2000, 2)
    r.tl.tracks[2].append(edit)
    p = sample_project()
    out = s.sync(p, str(tmp_path), operation="generate", protected_until=90050,
                 anchors={"opening": 90050, "head": 90400, "closing": 92050, "crawl": 92200})
    assert all(x["ok"] for x in out["sections"])
    assert all(x["item"].track > 2 and x["item"].color == "Purple" for x in out["sections"])
    assert edit.start == 90050 and edit.dur == 2000 and not r.tl.deleted


def test_failed_duration_replacement_preserves_original(tmp_path, monkeypatch):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    original = end_item(r)
    p["sequences"][1]["blocks"][3]["names"] += ["Persona %s" % i for i in range(30)]
    monkeypatch.setattr(s, "_append_holder", lambda *a: None)
    out = s.sync(p, str(tmp_path), only=["end"])
    assert not out["sections"][0]["ok"]
    assert original in r.tl.tracks[original.track] and original not in r.tl.deleted


def test_duration_collision_leaves_both_clips_untouched(tmp_path):
    r, s = session()
    p = sample_project()
    s.sync(p, str(tmp_path), only=["end"])
    original = end_item(r)
    neighbor = fakes.FakeItem(fakes.FakeMPI("other.mov"), original.start + original.dur, 100, original.track)
    r.tl.tracks[original.track].append(neighbor)
    p["sequences"][1]["blocks"][3]["names"] += ["Persona %s" % i for i in range(30)]
    out = s.sync(p, str(tmp_path), only=["end"])
    assert out["sections"][0]["action"] == "collision" and not r.tl.deleted


def test_project_namespace_distinguishes_same_title(tmp_path):
    r, s = session()
    one, two = sample_project(), sample_project()
    s.sync(one, str(tmp_path), only=["end"])
    s.sync(two, str(tmp_path), only=["end"])
    assert one["render_state"]["end"]["clip_uid"] != two["render_state"]["end"]["clip_uid"]
    assert not r.tl.deleted


def wizard(tmp_path, monkeypatch):
    monkeypatch.setattr(resolve_bridge, "default_work_dir", lambda p=None: str(tmp_path / "render"))
    w = ui_wizard.Wizard(fakes.FakeFusion(request=str(tmp_path / "p.drfc.json")), fakes.FakeBmd(), fakes.FakeResolve())
    w.build()
    w.win.fire("Create", "Clicked")
    return w


def test_save_commits_pending_editor_and_does_not_advance(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    idx = next(i for i, r in enumerate(w.rows) if r["kind"] == "entry")
    w.select(idx)
    w.it["RNames"].Text = "Nome senza salva intermedio"
    w.win.fire("Save", "Clicked")
    assert w.sel == idx
    assert w.block()["names"] == ["Nome senza salva intermedio"]
    assert "Salvato" in w.it["SaveState"].Text
    w.it["RNames"].Text = ""
    w.win.fire("RSave", "Clicked")
    assert w.sel == idx and w.block()["names"] == []


def test_zone_navigation_filters_without_mutating_project(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    before = copy.deepcopy(w.project)
    w.win.fire("Zone_crawl", "Clicked")
    assert w.zone == "crawl" and w.rows
    assert all(workspace.zone_of(w.project["sequences"][r["seq"]], w.project["sequences"][r["seq"]]["blocks"][r["block"]]) == "crawl" for r in w.rows)
    assert w.project == before


def test_review_is_invalidated_by_timeline_change(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    w.prepare_operation("generate")
    w.prepare_operation("generate", setup_done=True)
    assert w.pending_operation
    w.resolve.project.tl = fakes.FakeTimeline()
    with pytest.raises(ValueError, match="timeline cambiati"):
        w.apply_operation(None)
    assert not w.pending_operation


def test_review_is_invalidated_by_pending_text_edit(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    idx = next(i for i, r in enumerate(w.rows) if r["kind"] == "entry")
    w.select(idx)
    w.prepare_operation("generate")
    w.prepare_operation("generate", setup_done=True)
    w.it["RNames"].Text = "Modificato dopo riepilogo"
    with pytest.raises(ValueError, match="cambiati"):
        w.apply_operation(None)
    assert not any(w.resolve.tl.tracks.values())


@pytest.mark.parametrize("tc", ["01:00", "01:99:00:00", "01:00:00:25", "00:01:00;00"])
def test_invalid_timecode_rejected(tc):
    with pytest.raises(ValueError):
        resolve_bridge.ResolveSession.tc_to_frames(tc, 29.97 if ";" in tc else 25)


def test_content_proof_escapes_text():
    assert "&lt;script&gt;" in workspace.content_html({"type": "title", "text": "<script>"})
