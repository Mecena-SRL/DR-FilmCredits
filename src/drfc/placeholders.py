"""Segnaposto: crea subito tutto il progetto con testi tipo NOME COGNOME, da sostituire dopo.

- fill(project): riempie ogni sezione senza contenuto (un nome per ruolo, cast, brani d'esempio
  con accordi diversi, location, loghi grigi, allori...). Cosi' il progetto non e' mai vuoto
  e si vede subito il risultato.
- count(project): quanti segnaposto restano da sostituire.
- remove_unfilled(project): toglie righe e sezioni ancora fatte solo di segnaposto.

I segnaposto si riconoscono per uguaglianza di testo nella lingua delle diciture del progetto.
"""

import os

from . import DATA_DIR, i18n
from .model import AGREEMENT_KINDS

PLACEHOLDER_DIR = os.path.join(DATA_DIR, "placeholders")
LOGO_PREFIX = "placeholder_"
LOGO_IDS = ("placeholder_wide", "placeholder_square", "placeholder_mid")
# tipi di blocco che si riempiono (legal, text, media e spacer restano come sono)
FILLABLE = ("title", "card", "credit", "list", "names", "cast", "music", "agreements", "logos", "laurels")


def texts(lang):
    """Dizionario dei segnaposto nella lingua (fallback inglese)."""
    out = dict(i18n.phrases(i18n.FALLBACK).get("placeholders", {}))
    out.update(i18n.phrases(lang).get("placeholders", {}) if lang in i18n.LANGUAGES else {})
    return out


def all_texts(lang):
    return set(texts(lang).values())


def is_placeholder(text, lang):
    return text in all_texts(lang)


def logo_file(logo_id):
    """File PNG di un logo segnaposto (generato se manca)."""
    name = "logo_%s.png" % logo_id[len(LOGO_PREFIX):]
    path = os.path.join(PLACEHOLDER_DIR, name)
    if not os.path.exists(path):
        generate_logos()
    return path


def is_placeholder_logo(logo_id):
    return bool(logo_id) and logo_id.startswith(LOGO_PREFIX)


# ------------------------------------------------------------------ riempimento
def _lang(project):
    return project["meta"].get("language", "it")


def _music_cues(T):
    return [
        {"title": T["song"], "writers": [T["writers"]], "performers": [T["performers"]],
         "agreement": "courtesy", "licensor": T["company"]},
        {"title": T["song"], "writers": [T["writers"]], "performers": [T["performers"]],
         "agreement": "licensed", "licensor": T["company"]},
    ]


def _agreement_entries(kind, T):
    out = []
    for ag in AGREEMENT_KINDS.get(kind, ("paid",))[:3]:
        out.append({"name": T["location"], "provider": T["provider"], "agreement": ag})
    return out


def fill(project):
    """Riempie con segnaposto tutto cio' che e' vuoto. Ritorna quante cose ha aggiunto."""
    lang = _lang(project)
    T = texts(lang)
    meta = project["meta"]
    added = 0
    for seq in project["sequences"]:
        for b in seq["blocks"]:
            t = b["type"]
            if t not in FILLABLE:
                continue
            before = added
            if t == "title":
                if not b.get("text"):
                    b["text"] = meta.get("title") or T["film_title"]
                    added += 1
            elif t == "card":
                if b.get("lines"):
                    for ln in b["lines"]:
                        if not ln.get("text"):
                            ln["text"] = T["production"]
                            added += 1
                elif not b.get("names"):
                    b["names"] = [T["name"]]
                    added += 1
            elif t == "credit":
                if not b.get("names"):
                    b["names"] = [T["name"]]
                    added += 1
            elif t == "list":
                for r in b.get("rows", []):
                    if not r.get("break") and not r.get("names"):
                        r["names"] = [T["name"]]
                        added += 1
            elif t == "names":
                if not b.get("names"):
                    n = 8 if b.get("heading") == "h:thanks" else 6
                    b["names"] = [T["name"]] * n
                    added += n
            elif t == "cast":
                if not b.get("rows"):
                    b["rows"] = [{"actor": T["actor"], "character": T["character"]} for _ in range(4)]
                    added += 4
            elif t == "music":
                if not b.get("cues"):
                    b["cues"] = _music_cues(T)
                    added += 2
            elif t == "agreements":
                if not b.get("entries"):
                    b["entries"] = _agreement_entries(b.get("kind", "location"), T)
                    added += 3
            elif t == "logos":
                if not b.get("items"):
                    b["items"] = [{"logo": i} for i in LOGO_IDS]
                    added += 3
            elif t == "laurels":
                if not b.get("items"):
                    y = int(meta.get("year") or 2026)
                    b["items"] = [
                        {"status": "official_selection", "festival_name": T["festival"], "section": T["section"],
                         "year": y, "placeholder": True},
                        {"status": "winner", "festival_name": T["festival"], "award": T["award"], "year": y,
                         "placeholder": True}]
                    added += 2
            if added > before:
                b["enabled"] = True
    return added


# ------------------------------------------------------------------ conteggio / pulizia
def _names(b, key="names"):
    return b.get(key) or []


def _scan(project, remove):
    """Conta i segnaposto; con remove=True li toglie e scarta le sezioni rimaste vuote."""
    lang = _lang(project)
    T = all_texts(lang)
    total = 0
    for seq in project["sequences"]:
        keep = []
        for b in seq["blocks"]:
            n, touched = _scan_block(b, T, remove)
            total += n
            if remove and touched and not _has_content(b):
                continue  # sezione fatta solo di segnaposto: via
            keep.append(b)
        if remove:
            seq["blocks"] = keep
    return total


def _scan_block(b, T, remove):
    t = b["type"]
    n = 0
    if t == "title":
        hit = b.get("text") in T
        if remove and hit:
            b["text"] = ""
        return (1 if hit else 0), hit
    if t == "credit" or (t == "card" and not b.get("lines")) or t == "names":
        names = _names(b)
        n = sum(1 for x in names if x in T)
        if remove and n:
            b["names"] = [x for x in names if x not in T]
        return n, bool(n)
    if t == "card":
        lines = b.get("lines", [])
        n = sum(1 for l in lines if l.get("text") in T)
        if remove and n:
            b["lines"] = [l for l in lines if l.get("text") not in T]
        return n, bool(n)
    if t == "list":
        for r in b.get("rows", []):
            c = sum(1 for x in _names(r) if x in T)
            n += c
            if remove and c:
                r["names"] = [x for x in r["names"] if x not in T]
        if remove and n:
            b["rows"] = [r for r in b["rows"] if r.get("break") or r.get("names")]
        return n, bool(n)
    if t == "cast":
        rows = b.get("rows", [])
        n = sum((r.get("actor") in T) + (r.get("character") in T) for r in rows)
        if remove and n:
            kept = []
            for r in rows:
                if r.get("actor") in T:
                    continue
                if r.get("character") in T:
                    r = dict(r, character="")
                kept.append(r)
            b["rows"] = kept
        return n, bool(n)
    if t == "music":
        cues = b.get("cues", [])
        n = sum(1 for c in cues if c.get("title") in T)
        if remove and n:
            b["cues"] = [c for c in cues if c.get("title") not in T]
        return n, bool(n)
    if t == "agreements":
        entries = b.get("entries", [])
        n = sum(1 for e in entries if e.get("name") in T)
        if remove and n:
            b["entries"] = [e for e in entries if e.get("name") not in T]
        return n, bool(n)
    if t == "logos":
        items = b.get("items", [])
        n = sum(1 for i in items if is_placeholder_logo(i.get("logo")))
        if remove and n:
            b["items"] = [i for i in items if not is_placeholder_logo(i.get("logo"))]
        return n, bool(n)
    if t == "laurels":
        items = b.get("items", [])
        n = sum(1 for i in items if i.get("placeholder"))
        if remove and n:
            b["items"] = [i for i in items if not i.get("placeholder")]
        return n, bool(n)
    return 0, False


def _has_content(b):
    t = b["type"]
    if t == "title":
        return bool(b.get("text"))
    if t == "list":
        return any(r.get("names") for r in b.get("rows", []))
    if t in ("credit", "names"):
        return bool(b.get("names"))
    if t == "card":
        return bool(b.get("lines")) or bool(b.get("names"))
    key = {"cast": "rows", "music": "cues", "agreements": "entries", "logos": "items", "laurels": "items"}.get(t)
    return bool(b.get(key)) if key else True


def count(project):
    return _scan(project, remove=False)


def remove_unfilled(project):
    """Toglie i segnaposto rimasti (e le sezioni che restano vuote). Ritorna quanti ne ha tolti."""
    return _scan(project, remove=True)


# ------------------------------------------------------------------ PNG dei loghi segnaposto
def _rounded_png(path, w, h, radius, body=(150, 150, 150), mark=(205, 205, 205)):
    import struct
    import zlib
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            dx = max(radius - x, 0, x - (w - 1 - radius))
            dy = max(radius - y, 0, y - (h - 1 - radius))
            if dx * dx + dy * dy > radius * radius:
                row += b"\x00\x00\x00\x00"
                continue
            # un cerchio e due barre chiare: ricorda un logo senza esserlo
            cx, cy, r = h * 0.5, h * 0.5, h * 0.22
            in_circle = (x - cx) ** 2 + (y - cy) ** 2 <= r * r
            in_bar1 = h * 0.82 <= x <= w * 0.9 and h * 0.34 <= y <= h * 0.46
            in_bar2 = h * 0.82 <= x <= w * 0.72 and h * 0.56 <= y <= h * 0.66
            c = mark if (in_circle or in_bar1 or in_bar2) else body
            row += bytes((c[0], c[1], c[2], 255))
        rows.append(bytes(row))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(b"".join(rows), 9)))
        f.write(chunk(b"IEND", b""))


def generate_logos(out_dir=PLACEHOLDER_DIR):
    specs = {"logo_wide.png": (600, 180), "logo_square.png": (300, 300), "logo_mid.png": (400, 200)}
    paths = []
    for name, (w, h) in specs.items():
        p = os.path.join(out_dir, name)
        _rounded_png(p, w, h, radius=max(10, h // 8))
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in generate_logos():
        print(p)
