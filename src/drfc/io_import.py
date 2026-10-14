"""Import da foglio di calcolo (CSV/TSV, anche con ';' di Excel italiano) e da XLSX
(se openpyxl e' installato). Un rigo = una voce; le colonne mancanti si ignorano.

Colonne riconosciute (intestazioni in italiano o inglese):
  sezione/section   camera, sound, ... (chiave reparto) | cast | music | thanks |
                    locations | rentals | archive | products | logos | media | credit | legal
  sequenza/sequence opening | end (default: end)
  ruolo/role        chiave ruolo (es. cinematographer) o testo libero
  nome/name         nome della persona / location / azienda
  personaggio/character
  titolo/title      titolo del brano
  autori/writers    separati da ';' o '|'
  interpreti/performers, editore/publisher, accordo/agreement, licenziante/licensor,
  agente/agent, licenza_cc/cc_license, fornitore/provider, file/path, tag, didascalia/caption, nota/note
"""

import csv
import io
import os

from . import i18n
from .model import new_block

ALIASES = {
    "sezione": "section", "reparto": "section", "sequenza": "sequence", "ruolo": "role", "nome": "name",
    "personaggio": "character", "titolo": "title", "autori": "writers", "interpreti": "performers",
    "editore": "publisher", "edizioni": "publisher", "accordo": "agreement", "licenziante": "licensor",
    "agente": "agent", "licenza_cc": "cc_license", "fornitore": "provider", "file": "path",
    "didascalia": "caption", "nota": "note", "attore": "name", "actor": "name",
}

AGREEMENT_SECTIONS = {"locations": "location", "location": "location", "rentals": "rental", "noleggi": "rental",
                      "archive": "archive", "repertorio": "archive", "products": "product", "prodotti": "product",
                      "artwork": "artwork", "opere": "artwork"}
SECTION_ALIASES = {"interpreti": "cast", "musiche": "music", "brani": "music", "ringraziamenti": "thanks",
                   "loghi": "logos", "backstage": "media", "crediti": "credit"}


def _split(v):
    if not v:
        return []
    for sep in ("|", ";"):
        if sep in v:
            return [x.strip() for x in v.split(sep) if x.strip()]
    return [v.strip()]


def read_rows(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl  # opzionale
        except ImportError:
            raise RuntimeError("Per i file .xlsx installare openpyxl, oppure salvare come CSV.")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip() for h in next(it)]
        rows = [dict(zip(header, ["" if v is None else str(v) for v in r])) for r in it]
    else:
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(f, dialect=dialect))
    out = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            if k is None:
                continue
            key = k.strip().lower().replace(" ", "_")
            nr[ALIASES.get(key, key)] = (v or "").strip()
        if any(nr.values()):
            out.append(nr)
    return out


def _find_block(seq, pred):
    for b in seq["blocks"]:
        if pred(b):
            return b
    return None


def _insert_before_tail(seq, block):
    """Inserisce prima di loghi/legal finali per rispettare l'ordine standard."""
    idx = len(seq["blocks"])
    for i in range(len(seq["blocks"]) - 1, -1, -1):
        if seq["blocks"][i]["type"] in ("logos", "legal"):
            idx = i
        else:
            break
    seq["blocks"].insert(idx, block)
    return block


def import_rows(project, rows):
    """Unisce le righe nel progetto. Ritorna il numero di voci importate."""
    seqs = {s["id"]: s for s in project["sequences"]}
    count = 0
    for r in rows:
        seq_id = r.get("sequence") or "end"
        if seq_id not in seqs:
            from .model import new_sequence
            s = new_sequence(seq_id, "cards" if seq_id == "opening" else "crawl")
            project["sequences"].append(s)
            seqs[seq_id] = s
        seq = seqs[seq_id]
        section = (r.get("section") or "").strip().lower()
        section = SECTION_ALIASES.get(section, section)
        if not section:
            section = i18n.role_department(r.get("role", "")) or "credit"
        count += 1
        if section == "cast":
            b = _find_block(seq, lambda b: b["type"] == "cast") or _insert_before_tail(seq, new_block("cast", heading="h:cast"))
            b["rows"].append({"actor": r.get("name", ""), "character": r.get("character", "")})
        elif section == "music":
            b = _find_block(seq, lambda b: b["type"] == "music") or _insert_before_tail(seq, new_block("music", heading="h:songs"))
            cue = {"title": r.get("title", ""), "writers": _split(r.get("writers")),
                   "performers": _split(r.get("performers")), "publisher": r.get("publisher", ""),
                   "agreement": r.get("agreement", ""), "licensor": r.get("licensor", ""),
                   "agent": r.get("agent", ""), "cc_license": r.get("cc_license", "")}
            b["cues"].append({k: v for k, v in cue.items() if v})
        elif section in AGREEMENT_SECTIONS:
            kind = AGREEMENT_SECTIONS[section]
            b = _find_block(seq, lambda b: b["type"] == "agreements" and b.get("kind") == kind) or \
                _insert_before_tail(seq, new_block("agreements", kind=kind))
            b["enabled"] = True
            b["entries"].append({k: v for k, v in {"name": r.get("name", ""), "provider": r.get("provider", ""),
                                                    "agreement": r.get("agreement", "")}.items() if v})
        elif section == "thanks":
            b = _find_block(seq, lambda b: b["type"] == "names" and b.get("heading") == "h:thanks") or \
                _insert_before_tail(seq, new_block("names", heading="h:thanks"))
            b["names"].append(r.get("name", ""))
        elif section in ("logos", "media"):
            b = _find_block(seq, lambda b: b["type"] == section) or _insert_before_tail(seq, new_block(section))
            b["enabled"] = True
            item = {k: v for k, v in {"path": r.get("path", ""), "name": r.get("name", ""), "tag": r.get("tag", ""),
                                      "caption": r.get("caption", "")}.items() if v}
            b["items"].append(item)
        elif section == "legal":
            b = _find_block(seq, lambda b: b["type"] == "legal" and not b.get("items")) or \
                _insert_before_tail(seq, new_block("legal"))
            b["text"] = (b.get("text", "") + "\n" + r.get("name", "")).strip()
        elif section == "credit":
            role = r.get("role", "")
            b = _find_block(seq, lambda b: b["type"] in ("credit", "card") and b.get("role") == role)
            if b is None:
                b = new_block("credit" if seq.get("kind") != "cards" else "card", role=role)
                seq["blocks"].insert(0 if not seq["blocks"] else len([x for x in seq["blocks"] if x["type"] in ("credit", "card")]), b)
            b["names"].extend(_split(r.get("name")))
        else:
            # reparto: elenco a due colonne, nomi con lo stesso ruolo raggruppati
            heading = "dept:" + section if section in i18n.roles()["departments"] else section
            role = r.get("role", "")
            b = _find_block(seq, lambda b: b["type"] == "list" and b.get("heading") == heading)
            if b is None:
                b = _insert_before_tail(seq, new_block("list", heading=heading))
            row = next((x for x in b["rows"] if x.get("role") == role), None)
            if row is None:
                row = {"role": role, "names": []}
                b["rows"].append(row)
            row["names"].extend(_split(r.get("name")))
    return count


def import_file(project, path):
    return import_rows(project, read_rows(path))


TEMPLATE_HEADER = ["sezione", "sequenza", "ruolo", "nome", "personaggio", "titolo", "autori", "interpreti",
                   "editore", "accordo", "licenziante", "fornitore", "file", "tag", "nota"]


def write_template(path):
    """Crea un CSV vuoto con intestazioni ed esempi, da compilare in Excel/Numbers/Sheets."""
    ex = [
        ["credit", "end", "director", "Nome Cognome", "", "", "", "", "", "", "", "", "", "", "regista"],
        ["camera", "end", "cinematographer", "Nome Cognome", "", "", "", "", "", "", "", "", "", "", ""],
        ["camera", "end", "first_ac", "Nome Cognome", "", "", "", "", "", "", "", "", "", "", "piu' nomi: A; B"],
        ["cast", "end", "", "Attore", "Personaggio", "", "", "", "", "", "", "", "", "", ""],
        ["music", "end", "", "", "", "Titolo brano", "Autore 1; Autore 2", "Interprete", "Edizioni",
         "courtesy", "Etichetta", "", "", "", "courtesy = concessione gratuita"],
        ["locations", "end", "", "Villa Rossi", "", "", "", "", "", "free", "", "Famiglia Rossi", "", "", ""],
        ["rentals", "end", "", "", "", "", "", "", "", "paid", "", "Noleggio Camere srl", "", "", ""],
        ["thanks", "end", "", "Nome Cognome", "", "", "", "", "", "", "", "", "", "", ""],
        ["logos", "end", "", "Ministero della Cultura", "", "", "", "", "", "", "", "", "loghi/mic.png", "mic", ""],
    ]
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(TEMPLATE_HEADER)
        w.writerows(ex)
    return path
