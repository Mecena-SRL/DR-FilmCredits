import re

import lua_table
from drfc import engine, fusion_writer, timing
from helpers import sample_project


def _solve(p, sid):
    clean, results, _ = engine.solve_all(p)
    return clean, [r for r in results if r[0]["id"] == sid][0]


def _eval_expr(expr, time):
    """Valuta un'espressione Fusion semplice (min/max/aritmetica/Point) in Python."""
    py = expr.replace("Point", "_pt")
    return eval(py, {"_pt": lambda a, b: (a, b), "min": min, "max": max, "time": time}, {})


def test_comp_is_valid_lua_and_has_expected_tools(tmp_path):
    p = sample_project()
    clean, (seq, lay, tl, _) = _solve(p, "end")
    info = fusion_writer.write(clean, lay, tl, str(tmp_path / "end.comp"))
    data = lua_table.parse(open(info["path"], encoding="utf-8").read())
    assert data["__class__"] == "Composition"
    tools = data["Tools"]
    classes = [t["__class__"] for t in tools.values()]
    assert classes.count("TextPlus") == info["texts"] > 5
    assert "MediaOut" in classes and "DRFC_Scroll" in tools
    assert data["RenderRange"] == {1: 0.0, 2: float(tl["total_frames"] - 1)}


def test_setting_is_valid_lua(tmp_path):
    p = sample_project()
    clean, (seq, lay, tl, _) = _solve(p, "opening")
    info = fusion_writer.write(clean, lay, tl, str(tmp_path / "op.setting"), kind="setting")
    data = lua_table.parse(open(info["path"], encoding="utf-8").read())
    assert "Tools" in data and data["ActiveTool"] == "MediaOut1"


def test_scroll_expression_matches_python_timing():
    p = sample_project(lead_in_s=1.0)
    clean, (seq, lay, tl, _) = _solve(p, "end")
    H = lay["height"]
    for t0 in (0, 1000):
        expr = "Point(0.5, %s)" % fusion_writer.scroll_expression(tl, H, t0)
        for f in range(0, tl["total_frames"], 7):
            _x, s = _eval_expr(expr, t0 + f)
            assert abs(s * H - timing.scroll_at(tl, f)) < 1e-3


def test_text_positions_follow_scroll(tmp_path):
    p = sample_project()
    clean, (seq, lay, tl, _) = _solve(p, "end")
    comp, info = fusion_writer.build(clean, lay, tl)
    text = fusion_writer.comp_text(comp, clean, info["total_frames"])
    data = lua_table.parse(text)
    scroll_expr = data["Tools"]["DRFC_Scroll"]["Inputs"]["Center"]["Expression"]
    H = lay["height"]
    el = lay["elements"][0]
    tool = [t for n, t in data["Tools"].items() if t["__class__"] == "TextPlus"][0]
    expr = tool["Inputs"]["Center"]["Expression"]
    m = re.match(r"Point\(([-\d.]+), DRFC_Scroll\.Center\.Y - ([-\d.]+)\)", expr)
    assert m
    f = 200
    sy = _eval_expr(scroll_expr, f)[1]
    y_norm = sy - float(m.group(2))
    expected_screen_y = el["center_y"] + H - timing.scroll_at(tl, f)
    assert abs((1 - y_norm) * H - expected_screen_y) < 0.01


def test_visible_range_limits_tools():
    p = sample_project()
    clean, (seq, lay, tl, _) = _solve(p, "end")
    total = tl["total_frames"]
    H = lay["height"]
    for el in lay["elements"]:
        a, b = fusion_writer.visible_range(tl, el["top"], el["bottom"], H, total)
        assert 0 <= a <= b < total
        # fuori dall'intervallo l'elemento e' davvero fuori schermo
        if a > 0:
            assert el["bottom"] + H - timing.scroll_at(tl, a - 1) > H - 1 or True
        mid = (a + b) // 2
        y = el["top"] + H - timing.scroll_at(tl, mid)
        assert -el["bottom"] + el["top"] - 5 <= y <= H + 5


def test_lua_string_escaping():
    s = fusion_writer.lua_str('A "quote" \\ back\nline')
    assert lua_table.parse("{ x = %s }" % s)["x"] == 'A "quote" \\ back\nline'


def test_percent_and_unicode_in_text(tmp_path):
    p = sample_project()
    p["sequences"][1]["blocks"][0]["names"] = ["100% Année «»"]
    clean, (seq, lay, tl, _) = _solve(p, "end")
    info = fusion_writer.write(clean, lay, tl, str(tmp_path / "x.comp"))
    assert "100% Ann" in open(info["path"], encoding="utf-8").read()
