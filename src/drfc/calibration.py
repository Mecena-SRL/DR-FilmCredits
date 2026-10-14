"""Calibrazione di Text+ dentro Resolve: misura la scala reale di "Size" e il verso
dell'ancoraggio orizzontale, poi salva calibration.json (letto da fusion_constants).

E' AUTOMATICA: resolve_bridge la lancia da sola alla prima generazione (e a ogni nuova
versione di Resolve) su un comp temporaneo, che poi elimina. Se la misura non e' possibile
si restano sui valori di default, senza errori e senza chiedere nulla all'utente.

Metodo: si rende un Text+ con 1 e con 41 caratteri 'H' alla stessa Size. La differenza di
larghezza e' esattamente 40 avanzamenti del font (le side-bearing si cancellano), quindi
em_px = delta / (40 * avanzamento_em)  ->  em_per_size_width = em_px / (Size * Width).
"""

import os

from . import fusion_constants, log
from .fontmetrics import FontIndex, default_cache_path

PROBE_FONTS = (("Inter", "Regular"), ("Arial", "Regular"), ("Helvetica", "Regular"), ("DejaVu Sans", "Book"))
PROBE_FONT = PROBE_FONTS[1]
PROBE_SIZE = 0.02
N_CHARS = 41
SANE_RATIO = (0.4, 2.5)  # rispetto al valore di default: fuori da qui la misura e' scartata


def _render_box(tool, comp):
    t = comp.CurrentTime
    img = None
    try:
        img = tool.Output[t]
    except Exception:
        try:
            img = tool.Output.GetValue(t)
        except Exception:
            img = None
    if img is None:
        return None
    dw = getattr(img, "DataWindow", None)
    if dw is None:
        try:
            dw = img["DataWindow"]
        except Exception:
            return None
    if isinstance(dw, dict):
        vals = [dw[k] for k in sorted(dw.keys())]
    else:
        vals = list(dw)
    return [float(v) for v in vals[:4]]


def _width(tool, comp, text, size, W):
    tool.SetInput("StyledText", text)
    tool.SetInput("Size", size)
    tool.SetInput("Center", {1: 0.5, 2: 0.5})
    box = _render_box(tool, comp)
    if not box:
        return None
    return box[2] - box[0], box


def _pick_font():
    idx = FontIndex(cache_path=default_cache_path())
    for fam, sty in PROBE_FONTS:
        fi, score = idx.font(fam, sty)
        if fi is not None and score >= 2:
            return (fam, sty), fi
    return None, None


def is_current(version):
    cur = fusion_constants.saved()
    if not version:
        return "em_per_size_width" in cur
    return cur.get("resolve_version") == version and (
        "em_per_size_width" in cur or cur.get("unmeasurable") == version)


def measure(comp, W):
    """Misura su `comp` (qualsiasi comp, anche temporaneo). Ritorna dict o None se non misurabile."""
    font, fi = _pick_font()
    if font is None:
        log.write("calibrazione: nessun font di prova trovato")
        return None
    tool = comp.AddTool("TextPlus", -32768, -32768)
    try:
        tool.SetInput("Font", font[0])
        tool.SetInput("Style", font[1])
        one = _width(tool, comp, "H", PROBE_SIZE, W)
        many = _width(tool, comp, "H" * N_CHARS, PROBE_SIZE, W)
        if not one or not many:
            log.write("calibrazione: immagine di Text+ non leggibile da script")
            return None
        adv = fi.advance_em("H")
        em_px = (many[0] - one[0]) / ((N_CHARS - 1) * adv)
        k = em_px / (PROBE_SIZE * float(W))
        default = fusion_constants.DEFAULTS["em_per_size_width"]
        if not (SANE_RATIO[0] * default <= k <= SANE_RATIO[1] * default):
            log.write("calibrazione: misura scartata (k=%.4f)" % k)
            return None
        result = {"em_per_size_width": k}
        tool.SetInput("StyledText", "H" * 10)
        tool.SetInput("HorizontalLeftCenterRight", -1)
        box = _render_box(tool, comp)
        if box:
            left_edge_at_center = abs(box[0] - W / 2.0) < abs(box[2] - W / 2.0)
            result["anchor_h"] = {"left": -1, "center": 0, "right": 1} if left_edge_at_center \
                else {"left": 1, "center": 0, "right": -1}
        return result
    finally:
        try:
            tool.Delete()
        except Exception:
            pass


def ensure(comp, W, version=""):
    """Calibra se serve (nessuna calibrazione per questa versione di Resolve).
    Ritorna True se i valori salvati sono cambiati in modo sensibile (>1%)."""
    if is_current(version):
        return False
    before = fusion_constants.load()["em_per_size_width"]
    try:
        res = measure(comp, W)
    except Exception:
        log.exception("calibrazione")
        res = None
    if not res:
        fusion_constants.save({"resolve_version": version, "unmeasurable": version})
        return False
    res.update({"resolve_version": version, "measured": True})
    res.pop("unmeasurable", None)
    fusion_constants.save(res)
    log.write("calibrazione automatica: em_per_size_width %.5f (era %.5f)" % (res["em_per_size_width"], before))
    return abs(res["em_per_size_width"] - before) / before > 0.01


def reset():
    """Cancella la calibrazione: verra' rifatta da sola alla prossima generazione."""
    try:
        os.remove(fusion_constants.calibration_path())
        return True
    except OSError:
        return False
