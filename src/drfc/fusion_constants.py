"""Costanti di conversione verso Fusion Text+, sovrascrivibili con la calibrazione.

Text+ esprime la dimensione del font ("Size") in unita' relative alla larghezza del
fotogramma. Misure empiriche della community indicano em_px ~= Size * Width / 1.08; il
valore esatto puo' essere misurato con lo script "DR-FilmCredits Calibrate" che salva
calibration.json nella cartella utente (vedi docs/CALIBRAZIONE.md).
"""

import json
import os
import sys

DEFAULTS = {
    # em in pixel = Size * Width * EM_PER_SIZE_WIDTH
    "em_per_size_width": 1.0 / 1.08,
    # Ancoraggio orizzontale Text+ (HorizontalLeftCenterRight)
    "anchor_h": {"left": -1, "center": 0, "right": 1},
    # Giustificazione multiriga (HorizontalJustificationNew). Usata solo in render_mode=block
    # per colonne non centrate; in modalita' auto/line le colonne laterali sono una riga per Text+.
    "justify_h": {"left": 0, "center": 3, "right": 1},
    # spostamento verticale aggiuntivo (frazione di em) per allineare la baseline di Text+
    "baseline_fix_em": 0.0,
}


def user_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "DR-FilmCredits")


def calibration_path():
    return os.path.join(user_dir(), "calibration.json")


def saved():
    """Contenuto grezzo di calibration.json ({} se assente o illeggibile)."""
    try:
        with open(calibration_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (IOError, OSError, ValueError):
        return {}


def save(update):
    d = os.path.dirname(calibration_path())
    os.makedirs(d, exist_ok=True)
    cur = saved()
    cur.update(update)
    with open(calibration_path(), "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2)
    return cur


def load():
    c = json.loads(json.dumps(DEFAULTS))
    try:
        with open(calibration_path(), encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k].update(v)
            elif k in c:
                c[k] = v
    except (IOError, OSError, ValueError):
        pass
    return c
