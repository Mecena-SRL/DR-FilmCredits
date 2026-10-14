from drfc import engine, layout, model
from helpers import sample_project


def _lay(p, sid="end"):
    _c, results, _ = engine.solve_all(p)
    return [r for r in results if r[0]["id"] == sid][0][1]


def test_two_column_alignment_and_baselines():
    lay = _lay(sample_project())
    cam = [e for e in lay["elements"] if e["block"].startswith("end_list")]
    roles = [e for e in cam if e["anchor"] == "right"]
    names = [e for e in cam if e["anchor"] == "left"]
    assert roles and names
    axis = lay["width"] / 2
    assert all(e["x"] < axis for e in roles) and all(e["x"] > axis for e in names)
    # ogni ruolo condivide la baseline con il primo nome della sua riga
    name_baselines = {round(e["baseline"], 3) for e in names}
    for r in roles:
        assert round(r["baseline"], 3) in name_baselines


def test_text_inside_title_safe():
    lay = _lay(sample_project())
    sl, st, sr, sb = lay["safe"]
    for e in lay["elements"]:
        if e["kind"] != "text":
            continue
        left = {"left": e["x"], "center": e["x"] - e["width"] / 2, "right": e["x"] - e["width"]}[e["anchor"]]
        assert left >= sl - 1 and left + e["width"] <= sr + 1


def test_long_role_wraps_with_warning():
    p = sample_project()
    p["sequences"][1]["blocks"][1]["rows"][0]["role"] = "Una qualifica lunghissima " * 6
    lay = _lay(p)
    assert any("a capo" in w["message"] for w in lay["warnings"])


def test_names_grid_uses_columns():
    lay = _lay(sample_project())
    grid = [e for e in lay["elements"] if e["block"].startswith("end_names") and len(e["lines"]) > 1]
    assert len(grid) >= 2
    xs = sorted(e["x"] for e in grid)
    assert xs[0] < xs[-1]


def test_logos_balanced_by_area(tmp_path):
    import struct
    import zlib

    def png(path, w, h):
        raw = b"".join(b"\x00" + b"\xff\xff\xff\xff" * w for _ in range(h))
        ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                               + ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b""))
    png(str(tmp_path / "wide.png"), 800, 100)
    png(str(tmp_path / "square.png"), 200, 200)
    p = sample_project()
    p["_base_dir"] = str(tmp_path)
    p["sequences"][1]["blocks"].append(model.new_block("logos", items=[{"path": "wide.png"}, {"path": "square.png"}]))
    lay = _lay(p)
    imgs = [e for e in lay["elements"] if e["kind"] == "image"]
    assert len(imgs) == 2
    areas = [e["w"] * e["h"] for e in imgs]
    assert max(areas) / min(areas) < 1.6  # pesi ottici simili
    assert imgs[0]["h"] < imgs[1]["h"]      # il logo largo e' piu' basso


def test_cards_paginate_long_lists():
    p = sample_project()
    p["sequences"][0]["blocks"].append(model.new_block("list", rows=[{"role": "grip", "names": ["N%d" % i]} for i in range(60)]))
    lay = _lay(p, "opening")
    assert len(lay["cards"]) > 4
    sl, st, sr, sb = lay["safe"]
    for c in lay["cards"]:
        assert c["height"] <= (sb - st) + 1


def test_render_modes_change_node_granularity():
    p = sample_project()
    p["layout"]["render_mode"] = "block"
    block = len(_lay(p)["elements"])
    p["layout"]["render_mode"] = "line"
    line = len(_lay(p)["elements"])
    assert line > block


def test_split_lane_places_side_media(tmp_path):
    p = sample_project()
    p["_base_dir"] = str(tmp_path)
    p["layout"]["split"] = "media_right"
    p["sequences"][1]["blocks"].append(model.new_block("media", lane="side", items=[{"path": "a.mov", "aspect": 1.78}] * 3))
    lay = _lay(p)
    side = [e for e in lay["elements"] if e["block"] == "side_media"]
    assert len(side) == 3 and all(e["x"] > lay["width"] / 2 for e in side)
    texts = [e for e in lay["elements"] if e["kind"] == "text"]
    assert all(e["x"] < lay["width"] * 0.55 for e in texts)


def test_all_themes_layout():
    for t in layout.themes():
        lay = _lay(sample_project(theme=t))
        assert lay["content_height"] > 0
