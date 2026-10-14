import copy
from drfc import filmstrip, resolve_bridge
from test_workspace_sync import wizard


def blocks():
    return [
        {"id": "intro", "label": "Produzione", "zone": "opening", "status": "unchanged", "start": 90050, "end": 90200},
        {"id": "end", "label": "Titoli di coda", "zone": "crawl", "status": "changed", "start": 135000, "end": 137000},
    ]


def test_split_ranges_preserve_true_bounds_and_frames():
    data = blocks()
    before = copy.deepcopy(data)
    ranges = filmstrip.windows(90000, 90050, 135000, data, 25)
    assert len(ranges) == 2 and ranges[0][1] < ranges[1][0]
    assert ranges[0][0] == 90000 and ranges[1][1] >= 137000
    assert data == before


def test_short_film_uses_continuous_scale():
    assert len(filmstrip.windows(90000, 90050, 90500, [], 25)) == 1


def test_full_view_keeps_middle_credits_accessible():
    data = blocks() + [{"id": "middle", "label": "Credito centrale", "zone": "head", "status": "new", "start": 110000, "end": 110200}]
    page = filmstrip.render(90000, 90050, 135000, data, 25, full=True)
    assert "drfc:section:middle" in page and "//" not in page


def test_render_has_ruler_two_tracks_click_targets_and_gap():
    page = filmstrip.render(90000, 90050, 135000, blocks(), 25)
    assert "01:00:00:00" in page and "V1" in page and "V2" in page and "//" in page
    assert "drfc:section:intro" in page and "drfc:section:end" in page
    assert "100%%" not in page and "4%%" not in page


def test_timecode_drop_frame_round_trip():
    for fps in (29.97, 59.94):
        for frame in (0, 1800, 17982, 107892, 200000):
            tc = filmstrip.timecode(frame, fps, drop=True)
            assert resolve_bridge.ResolveSession.tc_to_frames(tc, fps, drop=True) == frame


def test_html_escapes_and_encodes_identifiers():
    data = [{"id": "x\"<&", "label": "<script>", "zone": "opening", "status": "new", "start": 90050, "end": 90200}]
    page = filmstrip.render(90000, 90050, 135000, data, 25)
    assert "<script>" not in page and "%22%3C%26" in page


def test_native_stack_negative_getter_does_not_break_company_save(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    w.on_add_company()
    w.it["EdStack"].CurrentIndex = -1  # observed on the real Resolve 21.1 UIStack
    w.it["CompanyName"].Text = "Mécena"
    w.it["CompanyContract"].Checked = False
    w.win.fire("CompanySave", "Clicked")
    assert w.block()["company"]["name"] == "Mécena"
    assert any(line["text"] == "Mécena" for line in w.block()["lines"])


def test_view_navigation_shows_one_window(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    w._view_shown = True
    w.win.Show()
    w.win.fire("Step2", "Clicked")
    assert w.windows[2].shown and not any(win.shown for i, win in enumerate(w.windows) if i != 2)
    w.win.fire("Step1", "Clicked")
    assert w.windows[1].shown and not w.windows[2].shown


def test_clicking_credit_navigates_to_its_editor(tmp_path, monkeypatch):
    w = wizard(tmp_path, monkeypatch)
    row = next(row for row in w._strip_rows if row["zone"] == "head")
    w.on_strip_link({"URL": "drfc:section:" + row["id"]})
    assert w.zone == "head" and w.sel >= 0
    w.on_strip_link({"URL": "drfc:full"})
    assert w._strip_full
