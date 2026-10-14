"""Modello dati del progetto titoli (.drfc.json).

Il progetto e' un semplice dizionario JSON, cosi' resta leggibile, versionabile e
modificabile a mano. Questo modulo definisce i default, i tipi di blocco e le funzioni
per caricare/salvare/normalizzare.

Struttura:
    project
      meta      titolo, anno, lingua, preset, titolare copyright...
      format    width, height, fps, safe_title, background
      style     theme + override per stile (title, heading, role, name, ...)
      timing    velocita'/durata (vedi timing.py)
      layout    split media laterale, larghezza colonne
      sequences [ {id, kind: crawl|cards, name, blocks: [...]} ]
"""

import copy
import json
import os

SCHEMA = "drfc/1"

DEFAULT_PROJECT = {
    "schema": SCHEMA,
    "meta": {
        "title": "",
        "original_title": "",
        "year": 2026,
        "language": "it",
        "preset": "it_cinema",
        "copyright_owner": "",
        "country": "",
    },
    "format": {
        "width": 1920,
        "height": 1080,
        "fps": 24.0,
        "safe_title": 0.9,
        "background": "transparent",
    },
    "style": {"theme": "classic", "overrides": {}},
    "timing": {
        "speed": "normal",          # slow | normal | fast | custom
        "px_per_frame": None,       # usato se speed == custom (intero consigliato)
        "fit": "none",              # none | speed | spacing
        "target_seconds": None,     # durata desiderata del crawl (fit != none)
        "lead_in_s": 0.0,           # nero/attesa prima dell'ingresso
        "lead_out_s": 0.0,
        "end_mode": "scroll_out",   # scroll_out | hold_last
        "hold_last_s": 4.0,
        "card_pace": "normal",      # slow | normal | fast
        "card_fade_s": 0.5,
        "card_gap_s": 0.25,
        "allow_fractional_speed": False,
    },
    "layout": {
        "split": "none",            # none | media_left | media_right
        "axis": 0.5,                # asse centrale del testo (0..1 sulla larghezza)
        "text_lane": 0.5,           # in split: frazione di larghezza per il testo
        "max_text_width": 0.8,      # frazione della safe area
        "render_mode": "auto",      # auto | block (un Text+ per colonna) | line (un Text+ per riga)
    },
    "sequences": [],
}

# Tipi di blocco: campi, default e descrizione (usati da wizard, import e validazione).
BLOCK_TYPES = {
    "title":      {"fields": {"text": ""}, "style": "title"},
    "card":       {"fields": {"role": "", "names": [], "lines": [], "position": "center"}},
    "credit":     {"fields": {"role": "", "names": [], "layout": "stacked", "team": False}},
    "list":       {"fields": {"heading": "", "rows": [], "layout": "two_column"}},
    "names":      {"fields": {"heading": "", "names": [], "columns": "auto"}},
    "cast":       {"fields": {"heading": "", "rows": [], "order": "actor_character"}},
    "music":      {"fields": {"heading": "", "cues": []}},
    "agreements": {"fields": {"heading": "", "kind": "location", "entries": [], "columns": 1}},
    "logos":      {"fields": {"caption": "", "items": [], "height": None, "per_row": "auto"}},
    "legal":      {"fields": {"items": [], "text": ""}},
    "media":      {"fields": {"items": [], "arrangement": "row", "height": None, "lane": "main"}},
    "text":       {"fields": {"text": "", "style_key": "small", "align": "center"}},
    "spacer":     {"fields": {"lines": 2.0}},
}

COMMON_BLOCK_FIELDS = {
    "id": None,
    "enabled": True,
    "spacing_before": None,   # in "righe nome"; None = default del tema
    "spacing_after": None,
    "hold_s": 0.0,            # pausa dello scorrimento quando il blocco e' al centro
    "page_break": False,      # cards: forza un nuovo cartello
    "style": {},              # override locali degli stili {style_key: {...}}
    "note": "",
}

MUSIC_AGREEMENTS = ("original", "licensed", "licensed_under", "courtesy", "artist_owned",
                    "library", "public_domain", "creative_commons")
AGREEMENT_KINDS = {
    "location": ("paid", "free", "public", "thanks"),
    "rental": ("paid", "free", "discount", "sponsor"),
    "archive": ("licensed", "free", "public_domain"),
    "product": ("placement", "free"),
    "artwork": ("licensed", "free"),
}

SPEEDS = ("slow", "normal", "fast", "custom")
SEQUENCE_KINDS = ("crawl", "cards")


def new_project(**meta):
    p = copy.deepcopy(DEFAULT_PROJECT)
    p["meta"].update(meta)
    return p


def new_block(btype, **fields):
    if btype not in BLOCK_TYPES:
        raise ValueError("Tipo di blocco sconosciuto: %s" % btype)
    b = {"type": btype}
    b.update(copy.deepcopy(COMMON_BLOCK_FIELDS))
    b.update(copy.deepcopy(BLOCK_TYPES[btype]["fields"]))
    b.update(fields)
    return b


def new_sequence(seq_id, kind="crawl", name="", blocks=None):
    if kind not in SEQUENCE_KINDS:
        raise ValueError("Tipo di sequenza sconosciuto: %s" % kind)
    return {"id": seq_id, "kind": kind, "name": name or seq_id, "blocks": blocks or []}


def _merge_defaults(target, defaults):
    for k, v in defaults.items():
        if k not in target:
            target[k] = copy.deepcopy(v)
        elif isinstance(v, dict) and isinstance(target[k], dict) and k not in ("overrides", "style"):
            _merge_defaults(target[k], v)


def normalize(project):
    """Completa un progetto (anche parziale o scritto a mano) con tutti i default."""
    p = copy.deepcopy(project)
    _merge_defaults(p, DEFAULT_PROJECT)
    for si, seq in enumerate(p["sequences"]):
        seq.setdefault("id", "seq%d" % (si + 1))
        seq.setdefault("kind", "crawl")
        seq.setdefault("name", seq["id"])
        seq.setdefault("blocks", [])
        for bi, b in enumerate(seq["blocks"]):
            bt = b.get("type")
            if bt not in BLOCK_TYPES:
                raise ValueError("Blocco %d di '%s': tipo sconosciuto %r" % (bi + 1, seq["id"], bt))
            for k, v in COMMON_BLOCK_FIELDS.items():
                b.setdefault(k, copy.deepcopy(v))
            for k, v in BLOCK_TYPES[bt]["fields"].items():
                b.setdefault(k, copy.deepcopy(v))
            if not b.get("id"):
                b["id"] = "%s_%s_%d" % (seq["id"], bt, bi + 1)
            if isinstance(b.get("names"), str):
                b["names"] = [n.strip() for n in b["names"].split(",") if n.strip()]
    return p


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("Schema non supportato: %s" % data.get("schema"))
    p = normalize(data)
    p["_base_dir"] = os.path.dirname(os.path.abspath(path))
    return p


def save(project, path):
    data = {k: v for k, v in project.items() if not k.startswith("_")}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def resolve_path(project, path):
    """Percorsi relativi di loghi/media sono relativi al file di progetto."""
    if not path:
        return path
    path = os.path.expanduser(path)
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(project.get("_base_dir", os.getcwd()), path))


def get_sequence(project, seq_id):
    for s in project["sequences"]:
        if s["id"] == seq_id:
            return s
    raise KeyError("Sequenza non trovata: %s" % seq_id)


def move_block(seq, index, delta):
    """Sposta un blocco su/giu' (usato dal wizard)."""
    j = index + delta
    blocks = seq["blocks"]
    if 0 <= index < len(blocks) and 0 <= j < len(blocks):
        blocks[index], blocks[j] = blocks[j], blocks[index]
        return j
    return index
