"""Preset per tipologia/territorio: struttura guidata dei titoli + controlli obbligatori."""

import copy
import json
import os

from . import DATA_DIR, model

PRESET_DIR = os.path.join(DATA_DIR, "presets")


def list_presets():
    out = []
    for fn in sorted(os.listdir(PRESET_DIR)):
        if fn.endswith(".json"):
            out.append(load_preset(fn[:-5]))
    return out


def load_preset(preset_id):
    with open(os.path.join(PRESET_DIR, preset_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def preset_label(preset, lang):
    lab = preset.get("label", {})
    return lab.get(lang) or lab.get("en") or preset["id"]


def project_from_preset(preset_id, language=None, **meta):
    """Nuovo progetto con la struttura del preset (blocchi vuoti da compilare)."""
    pr = load_preset(preset_id)
    p = model.new_project(preset=preset_id, language=language or pr.get("language", "it"), **meta)
    p["style"]["theme"] = pr.get("theme", "classic")
    if pr.get("fontset"):
        p["style"]["fontset"] = pr["fontset"]
    p["format"].update(pr.get("format", {}))
    p["timing"].update(pr.get("timing", {}))
    if pr.get("destination"):
        from . import design
        design.apply_destination(p, pr["destination"])
        p["timing"].update({k: v for k, v in pr.get("timing", {}).items() if k == "speed"})
    p["meta"].setdefault("funding", [])
    p["sequences"] = copy.deepcopy(pr["sequences"])
    return model.normalize(p)
