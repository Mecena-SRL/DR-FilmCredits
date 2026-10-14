"""Elenco unico del progetto (logica pura, senza interfaccia).

Il pannello mostra tutto il progetto come un elenco piatto di righe:

    ■ Titoli di coda                              (kind "seq")
    ▌ Reparto fotografia                          (kind "section")
        Direttore della fotografia | NOME COGNOME (kind "entry": ruolo + nomi, modificabile)
        Operatore di macchina      | NOME COGNOME
    ▌ Interpreti                                  (kind "section")
        ATTORE = PERSONAGGIO                      (kind "item": si modifica come testo)

Ogni riga sa a quale sequenza/sezione/voce del progetto appartiene (`seq`, `block`, `row`),
cosi' il pannello puo' modificare, aggiungere, eliminare e spostare senza altra logica.
"""

from . import blocktext, i18n, phrases

# tipi di sezione le cui righe (ruolo + nomi) si modificano una per una
ROW_TYPES = ("list", "credit", "card")


def _names(names):
    return ", ".join(n for n in (names or []) if n)


def _seq_title(seq):
    return seq.get("name") or seq.get("id", "")


def _section_label(b, lang):
    label, _n = blocktext.summary(b, lang)
    return label or b["type"]


def build(project, lang=None):
    """Righe dell'elenco: dict con kind, seq, block, row, label, value."""
    lang = lang or project["meta"].get("language", "it")
    rows = []
    for si, seq in enumerate(project["sequences"]):
        rows.append({"kind": "seq", "seq": si, "block": None, "row": None, "label": "■ " + _seq_title(seq),
                     "value": ""})
        for bi, b in enumerate(seq["blocks"]):
            t = b["type"]
            off = "" if b.get("enabled", True) else "  (disattivata)"
            if t == "credit" or (t == "card" and not b.get("lines")):
                rows.append({"kind": "entry", "seq": si, "block": bi, "row": 0,
                             "label": "▌ " + phrases.role_text(b.get("role", ""), lang) + off,
                             "value": _names(b.get("names"))})
                continue
            rows.append({"kind": "section", "seq": si, "block": bi, "row": None,
                         "label": "▌ " + _section_label(b, lang) + off, "value": ""})
            if t == "list":
                for ri, r in enumerate(b.get("rows", [])):
                    if r.get("break"):
                        rows.append({"kind": "break", "seq": si, "block": bi, "row": ri,
                                     "label": "      ── nuova colonna ──", "value": ""})
                    else:
                        rows.append({"kind": "entry", "seq": si, "block": bi, "row": ri,
                                     "label": "      " + phrases.role_text(r.get("role", ""), lang),
                                     "value": _names(r.get("names"))})
            else:
                for ri, (label, value) in enumerate(_items(b, lang)):
                    rows.append({"kind": "item", "seq": si, "block": bi, "row": ri,
                                 "label": "      " + label, "value": value})
    return rows


def _items(b, lang):
    """Righe di sola lettura (si modificano come testo) per le sezioni non a ruolo+nomi."""
    t = b["type"]
    if t == "cast":
        return [(r.get("actor", ""), r.get("character", "")) for r in b.get("rows", [])]
    if t == "names":
        names = b.get("names", [])
        return [("%d" % len(names), _names(names[:4]) + ("…" if len(names) > 4 else ""))] if names else []
    if t == "music":
        return [(c.get("title", ""), _names(c.get("writers"))) for c in b.get("cues", [])]
    if t == "agreements":
        return [(e.get("name", ""), e.get("provider", "")) for e in b.get("entries", [])]
    if t == "logos":
        return [(i.get("logo") or i.get("path", ""), i.get("tag", "")) for i in b.get("items", [])]
    if t == "laurels":
        return [(i.get("festival_name") or i.get("festival", ""), i.get("section") or i.get("award", ""))
                for i in b.get("items", [])]
    if t == "card":
        return [(l.get("text", ""), "") for l in b.get("lines", [])]
    if t in ("title", "text"):
        return [((b.get("text") or "").split("\n")[0][:60], "")]
    if t == "legal":
        return [(i.get("key", ""), "") for i in b.get("items", [])] + ([(b["text"][:60], "")] if b.get("text") else [])
    if t == "media":
        return [(i.get("path", ""), i.get("caption", "")) for i in b.get("items", [])]
    return []


def block_of(project, row):
    if row is None or row.get("block") is None:
        return None
    return project["sequences"][row["seq"]]["blocks"][row["block"]]


def entry_values(project, row):
    """(ruolo, nomi) della voce selezionata."""
    b = block_of(project, row)
    if b["type"] == "list":
        r = b["rows"][row["row"]]
        return r.get("role", ""), list(r.get("names") or [])
    return b.get("role", ""), list(b.get("names") or [])


def set_entry(project, row, role, names):
    b = block_of(project, row)
    if b["type"] == "list":
        r = b["rows"][row["row"]]
        r["role"], r["names"] = role, names
    else:
        b["role"], b["names"] = role, names


def add_entry_after(project, row, role, names):
    """Aggiunge una voce sotto la selezionata (solo nei reparti). Ritorna False se non possibile."""
    b = block_of(project, row)
    if b is None or b["type"] != "list":
        return False
    at = row["row"] + 1 if row.get("row") is not None else len(b["rows"])
    b["rows"].insert(at, {"role": role, "names": names})
    return True


def delete_entry(project, row):
    """Elimina la voce; in un credito singolo elimina la sezione. Ritorna cosa e' stato eliminato."""
    b = block_of(project, row)
    seq = project["sequences"][row["seq"]]
    if b["type"] == "list" and row.get("row") is not None:
        del b["rows"][row["row"]]
        return "entry"
    del seq["blocks"][row["block"]]
    return "section"


def delete_section(project, row):
    if row.get("block") is None:
        return False
    del project["sequences"][row["seq"]]["blocks"][row["block"]]
    return True


def move_section(project, row, delta):
    """Sposta la sezione su (-1) o giu' (+1). Ritorna il nuovo indice del blocco."""
    if row.get("block") is None:
        return None
    blocks = project["sequences"][row["seq"]]["blocks"]
    i, j = row["block"], row["block"] + delta
    if 0 <= j < len(blocks):
        blocks[i], blocks[j] = blocks[j], blocks[i]
        return j
    return i


def find(rows, seq, block, row=None):
    """Indice della riga dell'elenco che corrisponde a (seq, block, row); cade sulla sezione."""
    best = None
    for i, r in enumerate(rows):
        if r["seq"] == seq and r["block"] == block:
            if r["row"] == row and r["kind"] != "section":
                return i
            if r["kind"] in ("section", "entry") and best is None:
                best = i
    return best if best is not None else 0


def role_choices(lang, dept=None):
    """[(chiave, etichetta)] dei ruoli, filtrati per reparto, in ordine alfabetico."""
    items = [(k, r.get(lang) or r.get("en") or k) for k, r in i18n.roles()["roles"].items()
             if dept is None or r["dept"] == dept]
    return sorted(items, key=lambda kv: kv[1].lower())
