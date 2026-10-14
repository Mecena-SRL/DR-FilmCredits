"""Controlli prima della generazione: obblighi da preset/finanziamenti + qualita'.

Ogni problema e' un dict {level: error|warning|info, code, message, block}.
Gli 'error' non bloccano la generazione ma vengono mostrati in rosso nel wizard.
"""

import os

from . import imageinfo, placeholders, presets, timing
from .model import MUSIC_AGREEMENTS, resolve_path

FUNDING_LABELS = {
    "mic_tax_credit": "Tax credit MiC", "mic_selective": "Contributi selettivi MiC",
    "cultural_interest": "Interesse culturale MiC", "film_commission": "Film Commission",
    "creative_europe": "Creative Europe MEDIA", "eurimages": "Eurimages", "rai_cinema": "Rai Cinema",
    "italian_tax_credit_foreign": "Italian Tax Credit (opere straniere)", "cnc": "CNC", "ffa": "FFA",
    "dfff": "DFFF", "icaa": "ICAA",
}


def _issue(level, code, message, block=None):
    return {"level": level, "code": code, "message": message, "block": block}


def _blocks(project, seq_ids=None):
    for s in project["sequences"]:
        if seq_ids and s["id"] not in seq_ids:
            continue
        for b in s["blocks"]:
            if b.get("enabled", True):
                yield s, b


def _has_role(project, role):
    for _s, b in _blocks(project):
        if b.get("role") == role and b.get("names"):
            return True
        for r in b.get("rows", []) or []:
            if r.get("role") == role and r.get("names"):
                return True
    return False


def _has_legal(project, key):
    return any(b["type"] == "legal" and any(i.get("key") == key for i in b.get("items", []))
               for _s, b in _blocks(project))


def _has_logo_tag(project, tag, opening_only=False):
    seqs = None
    if opening_only:
        seqs = [s["id"] for s in project["sequences"] if s.get("kind") == "cards"]
    from . import logos

    def item_tag(i):
        if i.get("tag"):
            return i["tag"]
        e = logos.entry(i["logo"]) if i.get("logo") else None
        return e.get("tag") if e else None
    return any(b["type"] == "logos" and any(item_tag(i) == tag for i in b.get("items", []))
               for _s, b in _blocks(project, seqs))


def check_project(project, layouts=None):
    issues = []
    meta = project["meta"]
    funding = set(meta.get("funding", []) or [])
    try:
        preset = presets.load_preset(meta.get("preset", ""))
    except (IOError, OSError, ValueError):
        preset = {"checks": []}

    for c in preset.get("checks", []):
        kind = c["check"]
        if kind == "title_present":
            if not meta.get("title") and not any(b["type"] == "title" and b.get("text") for _s, b in _blocks(project)):
                issues.append(_issue("error", "title", "Manca il titolo dell'opera."))
        elif kind == "role_present":
            if not _has_role(project, c["role"]):
                issues.append(_issue("error", "role", "Manca il credito obbligatorio: %s" % c["role"]))
        elif kind == "legal_present":
            if not _has_legal(project, c["key"]):
                issues.append(_issue("error", "legal", "Manca la dicitura legale: %s" % c["key"]))
            if c["key"] == "copyright" and not meta.get("copyright_owner"):
                issues.append(_issue("error", "copyright_owner", "Indicare il titolare dei diritti (copyright)."))
        elif kind == "funding" and c["flag"] in funding:
            label = FUNDING_LABELS.get(c["flag"], c["flag"])
            if c.get("legal") and not _has_legal(project, c["legal"]):
                issues.append(_issue("error", "funding_legal", "%s: manca la dicitura obbligatoria." % label))
            if c.get("logo_tag") and not _has_logo_tag(project, c["logo_tag"], c.get("opening", False)):
                where = " nei titoli di testa" if c.get("opening") else ""
                from . import logos
                sugg = ", ".join(e["id"] for e in logos.by_tag(c["logo_tag"]))[:120]
                issues.append(_issue("error", "funding_logo",
                                     "%s: manca il logo%s (tag '%s'; dal kit: %s)." % (label, where, c["logo_tag"], sugg)))
        elif kind == "ai_disclosure":
            if meta.get("ai_used") and not _has_legal(project, "ai_disclosure"):
                issues.append(_issue("error", "ai", "Uso di IA dichiarato: aggiungere la dicitura nei titoli "
                                                    "(obbligatoria per il tax credit italiano)."))
        elif kind == "director_form":
            # DGA: nei titoli di testa il credito di regia e' l'ultimo prima dell'immagine
            for s in project["sequences"]:
                if s.get("kind") != "cards":
                    continue
                filled = [b for b in s["blocks"] if b.get("enabled", True) and (b.get("names") or b.get("text"))]
                if filled and filled[-1].get("role") != "director" and any(b.get("role") == "director" for b in filled):
                    issues.append(_issue("warning", "dga", "DGA: il credito 'Directed by' dovrebbe essere l'ultimo "
                                                           "dei titoli di testa.", filled[-1]["id"]))
        elif kind == "wga_team_hint":
            for _s, b in _blocks(project):
                if b.get("role") in ("written_by", "screenplay", "story") and len(b.get("names", [])) > 1 \
                        and not b.get("team"):
                    issues.append(_issue("info", "wga", "WGA: piu' autori uniti con 'and' (lavoro separato). "
                                                        "Attivare 'team' per '&' se hanno scritto insieme.", b["id"]))

    # ------------------------------------------------------- controlli generali
    for s, b in _blocks(project):
        bid = b["id"]
        t = b["type"]
        if t == "music":
            for cue in b.get("cues", []):
                ag = cue.get("agreement")
                name = cue.get("title", "?")
                if not ag:
                    issues.append(_issue("warning", "music_agreement", "Brano %s: tipo di accordo non indicato." % name, bid))
                elif ag not in MUSIC_AGREEMENTS:
                    issues.append(_issue("error", "music_agreement", "Brano %s: accordo sconosciuto '%s'." % (name, ag), bid))
                elif ag in ("licensed", "licensed_under", "courtesy", "library", "creative_commons") and not cue.get("licensor"):
                    issues.append(_issue("error", "music_licensor", "Brano %s: indicare il licenziante/titolare." % name, bid))
                if ag == "creative_commons" and not cue.get("cc_license"):
                    issues.append(_issue("error", "music_cc", "Brano %s: indicare la licenza CC (es. CC BY 4.0)." % name, bid))
                if not cue.get("writers") and ag not in ("public_domain",):
                    issues.append(_issue("warning", "music_writers", "Brano %s: autori mancanti." % name, bid))
        if t in ("logos", "media"):
            for it in b.get("items", []):
                if it.get("logo") and not it.get("path"):
                    from . import logos
                    st = logos.status(it["logo"])
                    if st != "ready":
                        e = logos.entry(it["logo"]) or {}
                        issues.append(_issue("error", "logo_kit", "Logo '%s' %s. %s" % (
                            e.get("name", it["logo"]), logos.STATUS_LABEL["it"].get(st, st),
                            ("Contatto: " + e["request_contact"]) if e.get("request_contact") else
                            "Pagina: %s" % e.get("official_page", "")), bid))
                    continue
                p = resolve_path(project, it.get("path", ""))
                if not p or not os.path.exists(p):
                    issues.append(_issue("error", "file", "File mancante: %s" % it.get("path"), bid))
                elif t == "logos" and p.lower().endswith(".svg"):
                    issues.append(_issue("error", "svg", "Fusion non legge SVG: esportare il logo in PNG trasparente.", bid))
                elif t == "logos" and imageinfo.image_size(p) and p.lower().endswith((".jpg", ".jpeg")):
                    issues.append(_issue("info", "logo_alpha", "Logo JPEG senza trasparenza: meglio PNG con alpha.", bid))

    n_ph = placeholders.count(project)
    if n_ph:
        issues.append(_issue("warning", "placeholder", "Ci sono ancora %d segnaposto da sostituire "
                                                       "(es. %s)." % (n_ph, placeholders.texts(project["meta"].get("language", "it"))["name"])))
    empty = sum(len(s["blocks"]) for s in project["sequences"]) - \
        sum(len(s["blocks"]) for s in strip_empty(project)["sequences"])
    if empty:
        issues.append(_issue("info", "empty", "%d blocchi vuoti o disattivati non verranno generati." % empty))

    # ------------------------------------------------------- durata / leggibilita'
    fonts_missing = set()
    if layouts:
        for seq_id, (lay, tl, _notes) in layouts.items():
            for w in lay.get("warnings", []):
                issues.append(_issue("warning", "layout", w["message"], w.get("block")))
            fonts_missing.update(lay.get("missing_fonts", []))
            if tl["kind"] == "crawl":
                msg = timing.reading_check(tl, project["format"]["height"], project["format"]["fps"])
                if msg:
                    issues.append(_issue("warning", "speed", msg))
            mx = preset.get("max_crawl_seconds")
            for c in preset.get("checks", []):
                if c["check"] == "max_duration":
                    mx = c["seconds"]
            secs = tl["total_frames"] / float(tl["fps"])
            if mx and tl["kind"] == "crawl" and secs > mx:
                issues.append(_issue("warning", "duration", "%s dura %.0fs: oltre il massimo consigliato (%ds)." % (seq_id, secs, mx)))
    if fonts_missing:
        issues.append(_issue("warning", "font", "Font non trovati sul sistema (misure stimate, installarli anche "
                                                "per Resolve): %s" % ", ".join(sorted(fonts_missing))))
    return issues


def strip_empty(project):
    """Copia del progetto senza blocchi vuoti (non generano nodi inutili)."""
    import copy
    p = copy.deepcopy(project)
    for s in p["sequences"]:
        keep = []
        for b in s["blocks"]:
            if not b.get("enabled", True):
                continue
            t = b["type"]
            empty = (
                (t in ("credit",) and not b.get("names")) or
                (t == "card" and not b.get("names") and not any(l.get("text") for l in b.get("lines", []))) or
                (t == "title" and not b.get("text")) or
                (t in ("list",) and not any(r.get("names") for r in b.get("rows", []))) or
                (t == "cast" and not b.get("rows")) or
                (t == "names" and not b.get("names")) or
                (t == "music" and not b.get("cues")) or
                (t == "agreements" and not b.get("entries")) or
                (t in ("logos", "media", "laurels") and not b.get("items")) or
                (t == "legal" and not b.get("items") and not b.get("text")) or
                (t == "text" and not b.get("text"))
            )
            if t == "list" and not empty:
                b["rows"] = [r for r in b["rows"] if r.get("names") or r.get("break")]
            if t == "title" and not b.get("text") and p["meta"].get("title"):
                b["text"] = p["meta"]["title"]
                empty = False
            if not empty:
                keep.append(b)
        s["blocks"] = keep
    return p
