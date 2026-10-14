import io
import json
import os
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from drfc import design, engine, guide, laurels, logos, model
from helpers import sample_project


def _end(p):
    _c, results, _ = engine.solve_all(p)
    return [r for r in results if r[0]["id"] == "end"][0][1]


def _pairs_project(arr, dest=None):
    p = sample_project()
    if dest:
        design.apply_destination(p, dest)
    rows = [{"role": r, "names": ["Nome %d" % i]} for i, r in enumerate(
        ["gaffer", "electrician", "key_grip", "grip", "sound_mixer", "boom_operator"])]
    p["sequences"][1]["blocks"].insert(1, model.new_block("list", heading="", rows=rows, arrangement=arr, id="mixed"))
    return p


def test_pairs_3_side_by_side_groups_share_baselines():
    lay = _end(_pairs_project("pairs_3"))
    els = [e for e in lay["elements"] if e["block"] == "mixed"]
    roles = [e for e in els if e["anchor"] == "right"]
    xs = sorted({round(e["x"]) for e in roles})
    assert len(xs) == 3  # tre assi: sinistra, centro, destra
    first_baselines = sorted({round(e["baseline"], 2) for e in roles})
    assert len(first_baselines) == 2  # due righe per gruppo, allineate fra i gruppi
    sl, _st, sr, _sb = lay["safe"]
    for e in els:
        left = e["x"] - e["width"] if e["anchor"] == "right" else e["x"]
        assert sl - 1 <= left and left + e["width"] <= sr + 1


def test_pairs_degrade_on_vertical():
    lay = _end(_pairs_project("pairs_3", dest="social_9x16"))
    assert any("ridotti" in w["message"] or "uno sopra" in w["message"] for w in lay["warnings"])
    sl, _st, sr, _sb = lay["safe"]
    for e in lay["elements"]:
        if e["kind"] == "text":
            left = {"left": e["x"], "center": e["x"] - e["width"] / 2, "right": e["x"] - e["width"]}[e["anchor"]]
            assert left >= sl - 1 and left + e["width"] <= sr + 1


def test_manual_column_breaks():
    p = sample_project()
    rows = [{"role": "gaffer", "names": ["A"]}, {"role": "grip", "names": ["B"]}, {"break": True},
            {"role": "sound_mixer", "names": ["C"]}]
    p["sequences"][1]["blocks"].insert(1, model.new_block("list", rows=rows, arrangement="pairs_2", id="mixed"))
    els = [e for e in _end(p)["elements"] if e["block"] == "mixed" and e["anchor"] == "left"]
    left_group = [e for e in els if e["x"] < 960]
    assert sorted(e["lines"][0] for e in left_group) == ["A", "B"]


def test_stacked_grid():
    lay = _end(_pairs_project("stacked_3"))
    els = [e for e in lay["elements"] if e["block"] == "mixed"]
    assert len({round(e["x"]) for e in els}) == 3


def test_vertical_safe_area_is_asymmetric():
    p = sample_project()
    design.apply_destination(p, "social_9x16")
    lay = _end(p)
    sl, st, sr, sb = lay["safe"]
    assert (sl, st) == pytest.approx((1080 * 0.065, 1920 * 0.14))
    assert sr == pytest.approx(1080 * (1 - 0.17)) and sb == pytest.approx(1920 * 0.65)
    # testo proporzionato al lato corto
    name = [e for e in lay["elements"] if e["kind"] == "text"][0]
    assert name["style"]["size_px"] < 60


def test_white_background_inverts_palette():
    p = sample_project()
    p["format"]["background"] = "white"
    lay = _end(p)
    colors = {e["style"]["color"] for e in lay["elements"] if e["kind"] == "text"}
    assert all(design._lum(c) < 0.5 for c in colors)


def test_density_changes_spacing():
    a, b = sample_project(), sample_project()
    a["style"]["density"], b["style"]["density"] = "compact", "airy"
    assert _end(a)["content_height"] < _end(b)["content_height"]


def test_fontset_applies():
    p = sample_project()
    p["style"]["fontset"] = "videoclip"
    fams = {e["style"]["family"] for e in _end(p)["elements"] if e["kind"] == "text"}
    assert "Bebas Neue" in fams


@pytest.mark.parametrize("bg", ["black", "white", {"mode": "gradient", "colors": ["#101010", "#303050"]},
                                {"mode": "dim", "opacity": 0.4}, {"mode": "panel", "color": "#000000", "opacity": 0.8},
                                {"mode": "media", "path": "/tmp/x.mov", "dim": 0.5, "blur": 8}])
def test_backgrounds_write_valid_comp(tmp_path, bg):
    import lua_table
    from drfc import fusion_writer
    p = sample_project()
    p["format"]["background"] = bg
    clean, results, _ = engine.solve_all(p)
    seq, lay, tl, _ = [r for r in results if r[0]["id"] == "end"][0]
    info = fusion_writer.write(clean, lay, tl, str(tmp_path / "x.comp"))
    data = lua_table.parse(open(info["path"], encoding="utf-8").read())
    assert "MediaOut1" in data["Tools"]
    assert all(n.startswith("DRFC_") or n == "MediaOut1" for n in data["Tools"])


def test_laurels_generated_and_texts():
    p = os.path.join(laurels.LAUREL_DIR, "laurel_classic_white.png")
    from drfc import imageinfo
    assert imageinfo.image_size(p) == (750, 600)
    lines = laurels.laurel_lines({"festival": "venezia", "status": "official_selection", "section": "concorso", "year": 2025})
    assert lines[0][0] == "Selezione Ufficiale" and "Venezia 82" in lines[2][0]
    cannes = laurels.laurel_lines({"festival": "cannes", "status": "official_selection"})
    assert cannes[0][0] == "Sélection Officielle"
    assert laurels.laurel_lines({"festival": "locarno", "award": "Pardo d'oro"})[0][0] == "Pardo d'oro"


def test_laurels_block_layout():
    p = sample_project()
    p["sequences"][0]["blocks"].insert(0, model.new_block("laurels", items=[
        {"festival": "venezia", "status": "official_selection", "section": "orizzonti", "year": 2026},
        {"festival": "berlinale", "status": "in_competition", "year": 2026}]))
    _c, results, issues = engine.solve_all(p)
    lay = [r for r in results if r[0]["id"] == "opening"][0][1]
    els = lay["cards"][0]["elements"]
    assert sum(1 for e in els if e["kind"] == "image") == 2
    assert any("ORIZZONTI" in e["lines"] for e in els if e["kind"] == "text")


# ------------------------------------------------------------------ loghi
class _Handler(BaseHTTPRequestHandler):
    calls = []

    def do_GET(self):
        _Handler.calls.append(self.path)
        if self.headers.get("If-None-Match") == '"v1"':
            self.send_response(304)
            self.end_headers()
            return
        if self.path.endswith(".zip"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("kit/logo_white.png", _png_bytes())
                z.writestr("kit/logo_black.png", _png_bytes())
                z.writestr("kit/logo.svg", "<svg/>")
            body = buf.getvalue()
        else:
            body = json.dumps({"version": 99, "logos": [{"id": "x", "tag": "x", "name": "X"}]}).encode()
        self.send_response(200)
        self.send_header("ETag", '"v1"')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _png_bytes(w=40, h=20):
    import struct
    import zlib
    raw = b"".join(b"\x00" + b"\xff\xff\xff\xff" * w for _ in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + \
        ch(b"IDAT", zlib.compress(raw)) + ch(b"IEND", b"")


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:%d" % srv.server_port
    srv.shutdown()


def test_registry_is_complete():
    reg = logos.registry()
    ids = [e["id"] for e in reg["logos"]]
    assert len(ids) == len(set(ids)) >= 40
    tags = {e["tag"] for e in reg["logos"]}
    for t in ("mic", "film_commission", "creative_europe", "eurimages", "cnc", "ffa", "dfff", "icaa"):
        assert t in tags
    assert sum(1 for e in reg["logos"] if e["category"] == "film_commission_it") >= 21


def test_logo_update_zip_etag_and_variants(server, monkeypatch):
    import copy
    reg = copy.deepcopy(logos.registry())
    reg["logos"] = [dict(reg["logos"][0], id="test_logo", download=[server + "/kit.zip"])]
    monkeypatch.setattr(logos, "registry", lambda: reg)
    res = logos.update(log=lambda m: None)
    assert res["test_logo"] == "updated"
    names = sorted(os.path.basename(f) for f in logos.files("test_logo"))
    assert names == ["logo.svg", "logo_black.png", "logo_white.png"]
    assert logos.status("test_logo") == "ready"
    assert logos.resolve("test_logo", light_bg=False).endswith("logo_white.png")
    assert logos.resolve("test_logo", light_bg=True).endswith("logo_black.png")
    res2 = logos.update(log=lambda m: None)
    assert res2["test_logo"] == "unchanged"


def test_logo_import_custom_and_status(tmp_path):
    png = tmp_path / "mio.png"
    png.write_bytes(_png_bytes())
    assert logos.status("fc_puglia") == "request"
    logos.import_file("fc_puglia", str(png))
    assert logos.status("fc_puglia") == "ready"
    logos.import_file("mio_sponsor", str(png), tag="sponsor", name="Sponsor")
    assert logos.entry("mio_sponsor")["tag"] == "sponsor"


def test_update_registry(server):
    n = logos.update_registry(server + "/registry.json")
    assert n == 1 and logos.registry()["version"] == 99


def test_logo_by_registry_id_in_project(tmp_path):
    png = tmp_path / "mic_white.png"
    png.write_bytes(_png_bytes())
    logos.import_file("mic_dgca", str(png))
    p = sample_project()
    p["meta"]["funding"] = ["mic_tax_credit"]
    p["sequences"][1]["blocks"].append(model.new_block("logos", items=[{"logo": "mic_dgca"}]))
    p["sequences"][1]["blocks"].append(model.new_block("legal", items=[{"key": "mic_tax_credit"}]))
    _c, results, issues = engine.solve_all(p)
    assert not [i for i in issues if i["code"] in ("funding_logo", "logo_kit", "funding_legal")]
    lay = [r for r in results if r[0]["id"] == "end"][0][1]
    assert any(e["kind"] == "image" and e["path"].endswith("mic_white.png") for e in lay["elements"])


# ------------------------------------------------------------------ guida
@pytest.mark.parametrize("wt", guide.WORK_TYPES)
def test_guided_project_builds(wt):
    p = guide.new_project(wt, "it", title="T", copyright_owner="O")
    _c, results, _issues = engine.solve_all(p)
    assert p["sequences"]


def test_reorder_puts_director_last_in_opening_and_legal_last_in_end():
    p = guide.new_project("lungo", "it", title="T")
    opening = p["sequences"][0]
    opening["blocks"].reverse()
    guide.reorder(opening, "it")
    roles = [b.get("role") for b in opening["blocks"] if b.get("role")]
    assert roles[-1] == "director"
    end = p["sequences"][1]
    end["blocks"].reverse()
    guide.reorder(end, "it")
    assert end["blocks"][-1]["type"] == "legal"
    assert end["blocks"][0].get("role") == "director"
    cast_idx = [i for i, b in enumerate(end["blocks"]) if b["type"] == "cast"][0]
    cam_idx = [i for i, b in enumerate(end["blocks"]) if b.get("heading") == "dept:camera"][0]
    assert cast_idx < cam_idx


def test_music_video_preset_has_p_and_c_lines():
    p = guide.new_project("videoclip", "int", title="Brano", copyright_owner="Prod srl")
    keys = [i["key"] for s in p["sequences"] for b in s["blocks"] if b["type"] == "legal" for i in b["items"]]
    assert "phonographic" in keys and "video_copyright" in keys
