"""Genera composizioni Fusion native (.comp per Resolve, .setting per copia/incolla).

Struttura del comp generato (tutto resta modificabile a mano nella pagina Fusion):

    DRFC_Scroll (Transform, non collegato)   <- UNICA espressione di scorrimento
    DRFC_Bg (Background trasparente o colore)
    Bxx_..._T1 (Text+)  ->  Bxx_..._M1 (Merge)  -> ... -> MediaOut1
    Bxx_..._L1 (Loader logo/foto/video) -> Merge (Size/Center)

Ogni Text+ ha Center = Point(x, DRFC_Scroll.Center.Y - y_contenuto): cambiando
l'espressione di DRFC_Scroll (o la velocita') si muove tutto insieme, a passi interi di
pixel. Le pause (hold) sono termini min/max dell'espressione: niente keyframe.
Ogni strumento ha GlobalIn/GlobalOut limitati ai frame in cui e' visibile: Fusion non
calcola i titoli fuori schermo (rullo lunghi fluidi anche con centinaia di righe).
"""

import os
import re

from . import design, fusion_constants, imageinfo, timing

LOADER_FORMATS = {
    ".png": "PNGFormat", ".jpg": "JpegFormat", ".jpeg": "JpegFormat", ".tif": "TiffFormat",
    ".tiff": "TiffFormat", ".exr": "OpenEXRFormat", ".dpx": "DPXFormat", ".tga": "TargaFormat",
    ".bmp": "BMPFormat", ".psd": "PSDFormat", ".mov": "QuickTimeMovies", ".mp4": "QuickTimeMovies",
    ".m4v": "QuickTimeMovies", ".mxf": "MXFFormat", ".avi": "AVIFormat",
}


def lua_str(s):
    s = s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "")
    return "\"" + s + "\""


def num(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    r = "%.9f" % v
    r = r.rstrip("0").rstrip(".")
    return r if r not in ("-0", "") else "0"


def hex_rgba(h, opacity=1.0):
    h = (h or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    a = int(h[6:8], 16) / 255.0 if len(h) >= 8 else 1.0
    return r, g, b, a * opacity


def safe_name(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", s or "x")
    if not s or s[0].isdigit():
        s = "N" + s
    return s[:48]


class Comp(object):
    def __init__(self):
        self.tools = []   # (name, text)
        self.names = set()
        self.loaders = []  # metadati per la rifinitura via API (bridge)

    def unique(self, base):
        base = safe_name(base)
        name, i = base, 1
        while name in self.names:
            i += 1
            name = "%s_%d" % (base, i)
        self.names.add(name)
        return name

    def add(self, name, text):
        self.tools.append((name, text))


def _inp(name, value=None, expression=None, source=None):
    parts = []
    if source:
        parts.append("SourceOp = %s, Source = \"Output\"" % lua_str(source))
    if value is not None:
        parts.append("Value = %s" % value)
    if expression:
        parts.append("Expression = %s" % lua_str(expression))
    return "\t\t\t\t%s = Input { %s, }," % (name, ", ".join(parts))


def _tool(kind, inputs, pos, extra=""):
    body = "\n".join(i for i in inputs if i)
    return ("\t\t@@NAME@@ = %s {\n%s\t\t\tInputs = {\n%s\n\t\t\t},\n"
            "\t\t\tViewInfo = OperatorInfo { Pos = { %s, %s } },\n\t\t}," % (kind, extra, body, num(pos[0]), num(pos[1])))


# ---------------------------------------------------------------------- espressioni
def scroll_expression(tl, H, t0):
    """Espressione Fusion dello spostamento normalizzato S(time) (0..travel/H)."""
    x = "(time - %s)" % num(t0 + tl["lead_in"])
    terms = [x]
    for h in tl["holds"]:
        a = h["start"] - tl["lead_in"]
        terms.append("min(max(%s - %s, 0), %s)" % (x, num(a), num(h["frames"])))
    m = terms[0] if len(terms) == 1 else "(%s - %s)" % (terms[0], " - ".join(terms[1:]))
    v = tl["speed_px"] / float(H)
    return "min(max(%s, 0) * %s, %s)" % (m, num(v), num(tl["travel_px"] / float(H)))


def visible_range(tl, top, bottom, H, total):
    """Primo/ultimo frame in cui un elemento [top, bottom] (coord. contenuto) e' a schermo."""
    def first_frame(pred):
        lo, hi = 0, total - 1
        if not pred(hi):
            return None
        while lo < hi:
            mid = (lo + hi) // 2
            if pred(mid):
                hi = mid
            else:
                lo = mid + 1
        return lo
    a = first_frame(lambda f: timing.scroll_at(tl, f) > top - 2)
    if a is None:
        return None
    b = first_frame(lambda f: timing.scroll_at(tl, f) >= bottom + H + 2)
    b = total - 1 if b is None else b
    return max(0, a - 1), min(total - 1, b + 1)


# ---------------------------------------------------------------------- strumenti
def _text_tool(comp, cal, el, W, H, center_input, pos, rng, t0):
    st = el["style"]
    em = st["size_px"]
    size = em / (W * cal["em_per_size_width"])
    r, g, b, a = hex_rgba(st.get("color"), float(st.get("opacity", 1.0)))
    anchor = el["anchor"]
    ins = [
        _inp("GlobalIn", num(t0 + rng[0])) if rng else None,
        _inp("GlobalOut", num(t0 + rng[1])) if rng else None,
        _inp("Width", num(int(W))), _inp("Height", num(int(H))),
        _inp("UseFrameFormatSettings", "1"),
        center_input,
        _inp("StyledText", lua_str("\n".join(el["lines"]))),
        _inp("Font", lua_str(st["family"])),
        _inp("Style", lua_str(st.get("style", "Regular"))),
        _inp("Size", num(size)),
        _inp("CharacterSpacing", num(float(st.get("tracking", 1.0)))),
        _inp("LineSpacing", num(el["line_spacing"])),
        _inp("HorizontalLeftCenterRight", num(cal["anchor_h"][anchor])) if anchor != "center" else None,
        _inp("HorizontalJustificationNew", num(cal["justify_h"][anchor]))
        if anchor != "center" and len(el["lines"]) > 1 else None,
        _inp("Red1", num(r)), _inp("Green1", num(g)), _inp("Blue1", num(b)), _inp("Alpha1", num(a)),
    ]
    return _tool("TextPlus", ins, pos)


def _merge_tool(prev, fg, pos, blend_expr=None, center=None, size=None, rng=None, t0=0):
    ins = [
        _inp("Background", source=prev),
        _inp("Foreground", source=fg),
        center,
        _inp("Size", num(size)) if size is not None else None,
        _inp("Blend", "1", expression=blend_expr) if blend_expr else None,
        _inp("PerformDepthMerge", "0"),
    ]
    return _tool("Merge", ins, pos)


def _loader_tool(path, total, t0, pos):
    ext = os.path.splitext(path)[1].lower()
    fmt = LOADER_FORMATS.get(ext, "PNGFormat")
    is_video = imageinfo.media_kind(path) == "video"
    clip = ("\t\t\tClips = {\n\t\t\t\tClip {\n\t\t\t\t\tID = \"Clip1\",\n\t\t\t\t\tFilename = %s,\n"
            "\t\t\t\t\tFormatID = %s,\n\t\t\t\t\tStartFrame = -1,\n\t\t\t\t\tLengthSetManually = true,\n"
            "\t\t\t\t\tTrimIn = 0,\n\t\t\t\t\tTrimOut = 0,\n\t\t\t\t\tExtendFirst = 0,\n"
            "\t\t\t\t\tExtendLast = 0,\n\t\t\t\t\tLoop = %s,\n\t\t\t\t\tAspectMode = 0,\n\t\t\t\t\tDepth = 0,\n"
            "\t\t\t\t\tTimeCode = 0,\n\t\t\t\t\tGlobalStart = %s,\n\t\t\t\t\tGlobalEnd = %s\n\t\t\t\t}\n\t\t\t},\n"
            % (lua_str(path.replace("\\", "/")), lua_str(fmt), "1" if is_video else "0",
               num(t0), num(t0 + total - 1)))
    ins = [
        _inp("Loop", "1") if is_video else None,
        _inp("HoldLastFrame", num(total)) if not is_video else None,
        _inp("PostMultiplyByAlpha", "0"),
    ]
    return _tool("Loader", ins, pos, extra=clip)


def _bg_tool(W, H, rgba, rgba2=None, frame=True):
    r, g, b, a = rgba
    ins = [_inp("Width", num(int(W))), _inp("Height", num(int(H))),
           _inp("UseFrameFormatSettings", "1" if frame else "0"),
           _inp("TopLeftRed", num(r)), _inp("TopLeftGreen", num(g)), _inp("TopLeftBlue", num(b)),
           _inp("TopLeftAlpha", num(a))]
    if rgba2:
        # gradiente verticale: colore 1 in alto, colore 2 in basso
        r2, g2, b2, a2 = rgba2
        ins = [_inp("Type", "2")] + ins + [
            _inp("TopRightRed", num(r)), _inp("TopRightGreen", num(g)), _inp("TopRightBlue", num(b)), _inp("TopRightAlpha", num(a)),
            _inp("BottomLeftRed", num(r2)), _inp("BottomLeftGreen", num(g2)), _inp("BottomLeftBlue", num(b2)),
            _inp("BottomLeftAlpha", num(a2)),
            _inp("BottomRightRed", num(r2)), _inp("BottomRightGreen", num(g2)), _inp("BottomRightBlue", num(b2)),
            _inp("BottomRightAlpha", num(a2))]
    return ins


def _background(comp, project, lay, total, t0):
    """Sfondo: trasparente, colore, gradiente, immagine/video (oscurato e sfocato),
    oscuramento dell'immagine sottostante, pannello dietro la corsia del testo."""
    W, H = float(lay["width"]), float(lay["height"])
    bg = design.background(project["format"])
    mode = bg["mode"]
    name = comp.unique("DRFC_Bg")
    if mode == "color":
        comp.add(name, _tool("Background", _bg_tool(W, H, hex_rgba(bg.get("color", "#000000"))), (0, -110)))
        return name
    if mode == "gradient":
        cols = bg.get("colors") or ["#000000", "#202020"]
        comp.add(name, _tool("Background", _bg_tool(W, H, hex_rgba(cols[0]), hex_rgba(cols[-1])), (0, -110)))
        return name
    comp.add(name, _tool("Background", _bg_tool(W, H, (0, 0, 0, 0)), (0, -110)))
    prev = name
    if mode == "media" and bg.get("path"):
        path = bg["path"]
        ld = comp.unique("DRFC_BgMedia_L")
        comp.add(ld, _loader_tool(path, total, t0, (-110, -330)))
        src = ld
        if float(bg.get("blur", 0)) > 0:
            bl = comp.unique("DRFC_BgMedia_Blur")
            comp.add(bl, _tool("Blur", [_inp("Input", source=src), _inp("XBlurSize", num(float(bg["blur"])))], (0, -330)))
            src = bl
        size = imageinfo.image_size(path) if imageinfo.media_kind(path) == "image" else None
        scale = max(W / size[0], H / size[1]) if size else 1.0  # riempie il quadro
        m = comp.unique("DRFC_BgMedia_M")
        comp.add(m, _merge_tool(prev, src, (110, -330), size=scale))
        comp.loaders.append({"loader": ld, "merge": m, "path": path, "w": W, "h": H, "scaled": bool(size),
                             "kind": imageinfo.media_kind(path), "cover": True})
        prev = m
        dim = float(bg.get("dim", 0.5))
        if dim > 0:
            d = comp.unique("DRFC_BgDim")
            comp.add(d, _tool("Background", _bg_tool(W, H, (0, 0, 0, dim)), (220, -440)))
            md = comp.unique("DRFC_BgDim_M")
            comp.add(md, _merge_tool(prev, d, (220, -330)))
            prev = md
    elif mode == "dim":
        d = comp.unique("DRFC_BgDim")
        comp.add(d, _tool("Background", _bg_tool(W, H, (0, 0, 0, float(bg.get("opacity", 0.5)))), (0, -440)))
        md = comp.unique("DRFC_BgDim_M")
        comp.add(md, _merge_tool(prev, d, (110, -330)))
        prev = md
    elif mode == "panel":
        sl, _st, sr, _sb = design.safe_box(project["format"])
        split = project["layout"].get("split", "none")
        lane = float(project["layout"].get("text_lane", 0.5))
        sw = sr - sl
        if split == "media_left":
            x0, x1 = sr - sw * lane, W
        elif split == "media_right":
            x0, x1 = 0, sl + sw * lane
        else:
            x0, x1 = 0, W
        margin = W * 0.02
        x0, x1 = max(0, x0 - margin), min(W, x1 + margin)
        r, g, b, _a = hex_rgba(bg.get("color", "#000000"))
        pn = comp.unique("DRFC_Panel")
        comp.add(pn, _tool("Background", _bg_tool(x1 - x0, H, (r, g, b, float(bg.get("opacity", 0.85))), frame=False), (0, -440)))
        mp = comp.unique("DRFC_Panel_M")
        comp.add(mp, _merge_tool(prev, pn, (110, -330), center=_inp("Center", "{ %s, 0.5 }" % num((x0 + x1) / 2 / W))))
        prev = mp
    return prev


# ---------------------------------------------------------------------- build
def build(project, lay, tl, t0=0, name="DRFC"):
    """Ritorna (testo_comp, info). `t0` = primo frame del comp nel clip Resolve."""
    cal = fusion_constants.load()
    W, H = float(lay["width"]), float(lay["height"])
    total = int(tl["total_frames"])
    comp = Comp()
    cols = {"x": 0}

    def pos():
        cols["x"] += 1
        return (cols["x"] * 110, 0)

    prev = _background(comp, project, lay, total, t0)

    if lay["kind"] == "crawl":
        scroll = comp.unique("DRFC_Scroll")
        comp.add(scroll, _tool("Transform", [
            _inp("Center", "{ 0.5, 0 }", expression="Point(0.5, %s)" % scroll_expression(tl, H, t0)),
        ], (0, -220)))
        groups = [(None, lay["elements"])]
    else:
        scroll = None
        groups = list(zip(tl["cards"], [c["elements"] for c in lay["cards"]]))

    baseline_fix = cal.get("baseline_fix_em", 0.0)
    count = {"text": 0, "media": 0}
    for card_tl, elements in groups:
        blend = None
        rng_card = None
        if card_tl is not None:
            s, n = t0 + card_tl["start"], card_tl["frames"]
            fi, fo = max(card_tl["fade_in"], 1), max(card_tl["fade_out"], 1)
            blend = "max(0, min(1, min((time - %s) / %s, (%s - time) / %s)))" % (num(s), num(fi), num(s + n), num(fo))
            rng_card = (card_tl["start"], card_tl["start"] + n)
        for el in elements:
            prefix = safe_name("DRFC_%s" % (el.get("block") or "el"))
            if el["kind"] == "text":
                count["text"] += 1
                yc = el["center_y"] + baseline_fix * el["style"]["size_px"]
                xn = el["x"] / W
                if scroll:
                    center = _inp("Center", "{ %s, %s }" % (num(xn), num(-yc / H)),
                                  expression="Point(%s, %s.Center.Y - %s)" % (num(xn), scroll, num(yc / H)))
                    rng = visible_range(tl, el["top"], el["bottom"], H, total)
                    if rng is None:
                        continue
                else:
                    center = _inp("Center", "{ %s, %s }" % (num(xn), num(1 - yc / H)))
                    rng = rng_card
                tname = comp.unique(prefix + "_T")
                p = pos()
                comp.add(tname, _text_tool(comp, cal, el, W, H, center, p, rng, t0))
                mname = comp.unique(prefix + "_M")
                comp.add(mname, _merge_tool(prev, tname, (p[0], 110), blend_expr=blend))
                prev = mname
            else:
                count["media"] += 1
                lname = comp.unique(prefix + "_L")
                p = pos()
                comp.add(lname, _loader_tool(el["path"], total, t0, (p[0], -110)))
                cy = el["top"] + el["h"] / 2.0
                xn = el["x"] / W
                size = imageinfo.image_size(el["path"]) if el["kind"] == "image" else None
                scale = (el["w"] / float(size[0])) if size else None
                if scroll:
                    center = _inp("Center", "{ %s, %s }" % (num(xn), num(-cy / H)),
                                  expression="Point(%s, %s.Center.Y - %s)" % (num(xn), scroll, num(cy / H)))
                else:
                    center = _inp("Center", "{ %s, %s }" % (num(xn), num(1 - cy / H)))
                mname = comp.unique(prefix + "_M")
                comp.add(mname, _merge_tool(prev, lname, (p[0], 110), blend_expr=blend, center=center,
                                            size=scale if scale else 1.0))
                comp.loaders.append({"loader": lname, "merge": mname, "path": el["path"], "w": el["w"],
                                     "h": el["h"], "scaled": bool(scale), "kind": el["kind"]})
                prev = mname

    out = comp.unique("MediaOut1") if "MediaOut1" not in comp.names else "MediaOut1"
    comp.add(out, _tool("MediaOut", [_inp("Input", source=prev)], (cols["x"] * 110 + 110, 110)))
    info = {"tools": len(comp.tools), "texts": count["text"], "media": count["media"], "loaders": comp.loaders,
            "total_frames": total, "output": out, "last_merge": prev, "t0": t0}
    return comp, info


def comp_text(comp, project, total, t0=0):
    fmt = project["format"]
    tools = "\n".join(t.replace("@@NAME@@", name) for name, t in comp.tools)
    return (
        "Composition {\n"
        "\tCurrentTime = %(t0)s,\n"
        "\tRenderRange = { %(t0)s, %(end)s },\n"
        "\tGlobalRange = { %(t0)s, %(end)s },\n"
        "\tCurrentID = %(n)d,\n"
        "\tHiQ = true,\n"
        "\tPlaybackUpdateMode = 0,\n"
        "\tVersion = \"DR-FilmCredits\",\n"
        "\tSavedOutputs = 0,\n"
        "\tHeldTools = 0,\n"
        "\tDisabledTools = 0,\n"
        "\tLockedTools = 0,\n"
        "\tAudioOffset = 0,\n"
        "\tResumable = true,\n"
        "\tOutputClips = {\n\t},\n"
        "\tTools = ordered() {\n%(tools)s\n\t},\n"
        "\tPrefs = {\n\t\tComp = {\n\t\t\tFrameFormat = {\n"
        "\t\t\t\tRate = %(fps)s,\n\t\t\t\tWidth = %(w)d,\n\t\t\t\tHeight = %(h)d,\n"
        "\t\t\t\tGuideRatio = %(ratio)s,\n\t\t\t},\n\t\t},\n\t},\n"
        "}\n" % {"t0": num(t0), "end": num(t0 + total - 1), "n": len(comp.tools), "tools": tools,
                 "fps": num(float(fmt["fps"])), "w": int(fmt["width"]), "h": int(fmt["height"]),
                 "ratio": num(float(fmt["width"]) / float(fmt["height"]))}
    )


def setting_text(comp, active="MediaOut1"):
    """Formato appunti di Fusion: si puo' incollare (Ctrl+V) nella pagina Fusion."""
    tools = "\n".join(t.replace("@@NAME@@", name).replace("\n\t\t", "\n\t") for name, t in comp.tools)
    return "{\n\tTools = ordered() {\n%s\n\t},\n\tActiveTool = %s\n}\n" % (tools, lua_str(active))


def write(project, lay, tl, path, t0=0, kind="comp"):
    comp, info = build(project, lay, tl, t0)
    text = comp_text(comp, project, info["total_frames"], t0) if kind == "comp" else setting_text(comp, info["output"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    info["path"] = path
    return info
