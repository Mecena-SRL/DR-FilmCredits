"""Calibrazione di Text+ dentro Resolve: misura la scala reale di "Size" e il verso
dell'ancoraggio orizzontale, poi salva calibration.json (letto da fusion_constants).

Procedura (automatica, ~1 secondo): aggiunge un Text+ temporaneo al comp Fusion
corrente, ne legge il riquadro dei pixel (DataWindow) e lo rimuove.
"""

import json
import os

from . import fusion_constants
from .fontmetrics import FontIndex, default_cache_path

PROBE_FONT = ("Arial", "Regular")
PROBE_SIZE = 0.1


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


def run(fusion, font=None):
    comp = fusion.GetCurrentComp()
    if comp is None:
        raise RuntimeError("Aprire la pagina Fusion su un clip qualsiasi e rilanciare la calibrazione.")
    family, style = font or PROBE_FONT
    attrs = comp.GetAttrs() or {}
    prefs = comp.GetPrefs("Comp.FrameFormat") or {}
    W = float(prefs.get("Width") or attrs.get("COMPI_Width") or 1920)
    result = {}
    comp.Lock()
    tool = comp.AddTool("TextPlus", -32768, -32768)
    try:
        tool.SetInput("StyledText", "HHHHHHHHHH")
        tool.SetInput("Font", family)
        tool.SetInput("Style", style)
        tool.SetInput("Size", PROBE_SIZE)
        tool.SetInput("Center", {1: 0.5, 2: 0.5})
        box = _render_box(tool, comp)
        if not box:
            raise RuntimeError("Impossibile leggere l'immagine di Text+ da script.")
        ink_h = box[3] - box[1]
        fi, _ = FontIndex(cache_path=default_cache_path()).font(family, style)
        cap = (fi.cap_height / float(fi.units_per_em)) if fi and fi.cap_height else 0.716
        em = ink_h / cap
        result["em_per_size_width"] = em / (PROBE_SIZE * W)
        tool.SetInput("HorizontalLeftCenterRight", -1)
        box_l = _render_box(tool, comp)
        if box_l:
            left_edge_at_center = abs(box_l[0] - W / 2) < abs(box_l[2] - W / 2)
            result["anchor_h"] = {"left": -1, "center": 0, "right": 1} if left_edge_at_center \
                else {"left": 1, "center": 0, "right": -1}
    finally:
        tool.Delete()
        comp.Unlock()
    path = fusion_constants.calibration_path()
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    current = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                current = json.load(f)
        except ValueError:
            current = {}
    current.update(result)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return result, path
