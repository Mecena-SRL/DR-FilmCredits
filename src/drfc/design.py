"""Scelte di design trasversali: destinazioni, sfondi, palette chiaro/scuro, set di font,
densita' e interlinea. Tutto puro Python, usato da layout, writer, anteprima e wizard."""

import json
import os

from . import DATA_DIR

_cache = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            _cache[name] = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    return _cache[name]


def destinations():
    return _load("destinations.json")


def fontsets():
    return _load("fontsets.json")


def label(entry, lang):
    lab = entry.get("label", {})
    return lab.get(lang) or lab.get("en") or ""


# ---------------------------------------------------------------- destinazione
def apply_destination(project, dest_id, keep_fps=False):
    """Imposta risoluzione, fps, safe area, scala e velocita' dal profilo."""
    d = destinations()[dest_id]
    f = project["format"]
    f["destination"] = dest_id
    f["width"], f["height"] = d["width"], d["height"]
    if not keep_fps:
        f["fps"] = float(d["fps"])
    f["safe"] = dict(d["safe"])
    f["type_scale"] = float(d.get("type_scale", 1.0))
    project["timing"]["speed"] = d.get("speed", project["timing"].get("speed", "normal"))
    return d


def guess_destination(width, height):
    """Profilo piu' vicino a una risoluzione (es. quella della timeline)."""
    best, score = None, None
    for k, d in destinations().items():
        s = abs(d["width"] - width) + abs(d["height"] - height)
        if score is None or s < score:
            best, score = k, s
    return best


def safe_box(fmt):
    """(left, top, right, bottom) in pixel; supporta safe asimmetrica o safe_title."""
    W, H = float(fmt["width"]), float(fmt["height"])
    s = fmt.get("safe")
    if isinstance(s, dict):
        return (W * s.get("left", 0.05), H * s.get("top", 0.05),
                W * (1 - s.get("right", 0.05)), H * (1 - s.get("bottom", 0.05)))
    t = float(fmt.get("safe_title", 0.9))
    mx, my = W * (1 - t) / 2, H * (1 - t) / 2
    return (mx, my, W - mx, H - my)


def text_scale(fmt):
    """Scala del testo: lato corto / 1080 x scala del profilo (in verticale i caratteri
    restano proporzionati alla larghezza)."""
    short = min(float(fmt["width"]), float(fmt["height"]))
    return short / 1080.0 * float(fmt.get("type_scale", 1.0))


# ---------------------------------------------------------------- sfondi
BACKGROUND_MODES = ("transparent", "black", "white", "color", "gradient", "media", "dim", "panel")


def background(fmt):
    """Normalizza format.background in un dict {mode, ...}."""
    b = fmt.get("background", "transparent")
    if isinstance(b, dict):
        out = dict(b)
        out.setdefault("mode", "color")
        return out
    if b in (None, "", "transparent"):
        return {"mode": "transparent"}
    if b == "black":
        return {"mode": "color", "color": "#000000"}
    if b == "white":
        return {"mode": "color", "color": "#FFFFFF"}
    if isinstance(b, str) and b.startswith("#"):
        return {"mode": "color", "color": b}
    return {"mode": "transparent"}


def _lum(hexcol):
    h = (hexcol or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def is_light(fmt):
    b = background(fmt)
    if b["mode"] == "color":
        return _lum(b.get("color")) > 0.55
    if b["mode"] == "gradient":
        cols = b.get("colors") or ["#000000", "#000000"]
        return sum(_lum(c) for c in cols) / len(cols) > 0.55
    if b["mode"] == "panel":
        return _lum(b.get("color", "#000000")) > 0.55 and float(b.get("opacity", 1.0)) > 0.6
    return False


def invert_color(hexcol):
    h = (hexcol or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [255 - int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02X%02X%02X" % (r, g, b)


# ---------------------------------------------------------------- font
FONTSET_ROLE = {"title": "title", "heading": "heading", "role": "role", "character": "role",
                "card_role": "role", "name": "name", "card_name": "name", "small": "small", "legal": "small"}


def fontset_style(fontset_id, style_key):
    fs = fontsets().get(fontset_id)
    if not fs:
        return {}
    fam = fs.get(FONTSET_ROLE.get(style_key, "name"))
    if not fam:
        return {}
    return {"family": fam[0], "style": fam[1]}


# ---------------------------------------------------------------- densita'
DENSITY = {
    "compact": {"block_gap": 0.7, "row_gap": 0.5, "heading_gap": 0.8},
    "normal": {"block_gap": 1.0, "row_gap": 1.0, "heading_gap": 1.0},
    "airy": {"block_gap": 1.4, "row_gap": 1.6, "heading_gap": 1.2},
}
LEADING = {"tight": 0.9, "normal": 1.0, "wide": 1.2}


def density_factors(style):
    d = style.get("density", "normal")
    if isinstance(d, dict):
        out = dict(DENSITY["normal"])
        out.update(d)
        return out
    return DENSITY.get(d, DENSITY["normal"])


def leading_factor(style):
    v = style.get("leading", "normal")
    if isinstance(v, (int, float)):
        return float(v)
    return LEADING.get(v, 1.0)
