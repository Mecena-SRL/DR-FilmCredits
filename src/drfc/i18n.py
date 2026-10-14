"""Accesso ai dati multilingua: ruoli, reparti, diciture e testi dell'interfaccia."""

import json
import os

from . import DATA_DIR

LANGUAGES = ("it", "en", "fr", "de", "es")
FALLBACK = "en"

_cache = {}


def _load(rel):
    if rel not in _cache:
        with open(os.path.join(DATA_DIR, rel), encoding="utf-8") as f:
            _cache[rel] = json.load(f)
    return _cache[rel]


def _dig(data, dotted):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def phrases(lang):
    return _load(os.path.join("phrases", "%s.json" % lang))


def phrase(lang, key, **values):
    """Restituisce la dicitura `key` (es. 'legal.copyright') nella lingua richiesta,
    con fallback all'inglese, e sostituisce i segnaposto {nome}."""
    text = _dig(phrases(lang), key) if lang in LANGUAGES else None
    if text is None:
        text = _dig(phrases(FALLBACK), key)
    if text is None:
        raise KeyError("Dicitura sconosciuta: %s" % key)
    if isinstance(text, str) and values:
        text = _format(text, values)
    return text


class _Missing(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _format(template, values):
    return template.format_map(_Missing(values))


def roles():
    return _load("roles.json")


def role_label(role_key, lang):
    """Etichetta localizzata di un ruolo; se la chiave non esiste la usa come testo libero."""
    r = roles()["roles"].get(role_key)
    if not r:
        return role_key
    return r.get(lang) or r.get(FALLBACK) or role_key


def department_label(dept_key, lang):
    d = roles()["departments"].get(dept_key)
    if not d:
        return dept_key
    return d.get(lang) or d.get(FALLBACK) or dept_key


def role_department(role_key):
    r = roles()["roles"].get(role_key)
    return r["dept"] if r else None


def join_names(names, lang, team=False):
    """Unisce una lista di nomi secondo la lingua ('A, B e C'). Con team=True usa '&'
    (convenzione WGA: '&' = squadra di scrittura, 'and' = contributi separati)."""
    names = [n for n in names if n]
    if not names:
        return ""
    p = phrases(lang)
    if team:
        return p.get("team_sep", " & ").join(names)
    if len(names) == 1:
        return names[0]
    return p["list_sep"].join(names[:-1]) + p["list_last"] + names[-1]


def quote(text, lang):
    q = phrases(lang).get("quote", ["“", "”"])
    return q[0] + text + q[1]


def ui(lang):
    try:
        return _load(os.path.join("ui", "%s.json" % lang))
    except (IOError, OSError):
        return _load(os.path.join("ui", "%s.json" % FALLBACK))


def ui_text(lang, key, **values):
    text = _dig(ui(lang), key)
    if text is None:
        text = _dig(ui(FALLBACK), key) or key
    return _format(text, values) if values else text
