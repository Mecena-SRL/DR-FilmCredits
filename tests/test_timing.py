import pytest

from drfc import engine, timing
from helpers import sample_project


def _end(p):
    _c, results, _i = engine.solve_all(p)
    return [r for r in results if r[0]["id"] == "end"][0]


def test_preset_speed_scales_with_resolution():
    hd = timing.preset_speed(1080, 24, "normal")
    uhd = timing.preset_speed(2160, 24, "normal")
    assert isinstance(hd, int) and hd >= 1
    assert abs(uhd - 2 * hd) <= 1
    assert timing.preset_speed(1080, 24, "slow") < hd < timing.preset_speed(1080, 24, "fast")


def test_integer_pixels_per_frame_and_monotonic_scroll():
    seq, lay, tl, _ = _end(sample_project())
    assert float(tl["speed_px"]).is_integer()
    prev = -1
    for f in range(tl["total_frames"]):
        s = timing.scroll_at(tl, f)
        assert s >= prev
        assert abs(s - round(s)) < 1e-9  # sempre pixel interi
        prev = s
    assert timing.scroll_at(tl, tl["total_frames"] - 1) == pytest.approx(tl["travel_px"], abs=tl["speed_px"])


def test_hold_stops_block_at_screen_centre():
    seq, lay, tl, _ = _end(sample_project())
    h = tl["holds"][0]
    s0 = timing.scroll_at(tl, h["start"])
    for f in range(h["start"], h["start"] + h["frames"] + 1):
        assert timing.scroll_at(tl, f) == s0
    legal = [b for b in lay["blocks"] if b[0] == h["block"]][0]
    centre_on_screen = (legal[1] + legal[2]) / 2 + lay["height"] - s0
    assert abs(centre_on_screen - lay["height"] / 2) <= tl["speed_px"]


@pytest.mark.parametrize("fit", ["speed", "spacing"])
def test_fit_to_duration_is_exact(fit):
    p = sample_project(fit=fit, target_seconds=50)
    seq, lay, tl, notes = _end(p)
    assert tl["total_frames"] == 50 * 24
    assert float(tl["speed_px"]).is_integer()


def test_fit_spacing_moves_blocks():
    base = _end(sample_project())[1]
    longer = _end(sample_project(fit="spacing", target_seconds=60))[1]
    assert longer["content_height"] > base["content_height"]


def test_hold_last_end_mode():
    p = sample_project(end_mode="hold_last", hold_last_s=3)
    seq, lay, tl, _ = _end(p)
    assert tl["end_hold"] == 72
    last = timing.scroll_at(tl, tl["total_frames"] - 1)
    assert last == pytest.approx(tl["travel_px"], abs=tl["speed_px"])


def test_cards_timing_and_opacity():
    p = sample_project()
    _c, results, _ = engine.solve_all(p)
    seq, lay, tl, _ = [r for r in results if r[0]["id"] == "opening"][0]
    assert len(tl["cards"]) == 3
    for c in tl["cards"]:
        assert c["frames"] >= timing.CARD_MIN_S * 24 - 1
        assert timing.card_opacity(c, c["start"]) == 0
        assert timing.card_opacity(c, c["start"] + c["frames"] // 2) == 1
    starts = [c["start"] for c in tl["cards"]]
    assert starts == sorted(starts)


def test_project_target_does_not_stretch_cards():
    p = sample_project(fit="speed", target_seconds=90)
    _c, results, _ = engine.solve_all(p)
    cards = [r for r in results if r[0]["id"] == "opening"][0][2]
    assert cards["total_frames"] < 30 * 24
