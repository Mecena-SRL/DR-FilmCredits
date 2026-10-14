"""Composizione automatica delle diciture in base al tipo di accordo e alla lingua.

Esempio: una canzone concessa gratuitamente produce "Per gentile concessione di X"
(it) / "Used by kind permission of X" (en); una con licenza a pagamento produce
"Su licenza di X" / "Courtesy of X". Ogni riga resta sovrascrivibile a mano con il
campo `override` (lista di righe) sull'elemento.
"""

from . import i18n


def _names(value, lang, team=False):
    if isinstance(value, str):
        return value
    return i18n.join_names(list(value or []), lang, team=team)


def music_cue_lines(cue, lang):
    """Righe di un brano. Ritorna lista di (testo, style_key).

    Campi del cue: title, writers, composers, lyricists, arrangers, performers,
    publisher, agreement (vedi model.MUSIC_AGREEMENTS), licensor, agent,
    cc_license, writers_team (bool), extra (righe libere), override (righe).
    """
    if cue.get("override"):
        lines = cue["override"]
        return [(lines[0], "name")] + [(l, "small") for l in lines[1:]]
    out = []
    title = cue.get("title", "").strip()
    if title:
        out.append((i18n.quote(title, lang), "name"))
    writers = _names(cue.get("writers"), lang, team=cue.get("writers_team", False))
    if writers:
        out.append((i18n.phrase(lang, "music.written_by", names=writers), "small"))
    for field, key in (("composers", "music.music_by"), ("lyricists", "music.lyrics_by"),
                       ("arrangers", "music.arranged_by"), ("performers", "music.performed_by"),
                       ("publisher", "music.publisher")):
        v = _names(cue.get(field), lang)
        if v:
            out.append((i18n.phrase(lang, key, names=v), "small"))
    agreement = cue.get("agreement", "")
    if agreement:
        if agreement in ("licensed", "licensed_under", "courtesy", "library", "creative_commons") \
                and not cue.get("licensor"):
            text = None  # segnalato dal validatore
        else:
            text = i18n.phrase(lang, "music.agreement." + agreement,
                               licensor=cue.get("licensor", ""), cc_license=cue.get("cc_license", ""))
        if text:
            out.append((text, "small"))
    if cue.get("agent"):
        out.append((i18n.phrase(lang, "music.agreement.by_arrangement", agent=cue["agent"]), "small"))
    for extra in cue.get("extra", []) or []:
        out.append((extra, "small"))
    return out


def agreement_line(kind, entry, lang):
    """Riga per location / noleggi / repertorio / prodotti / opere d'arte."""
    if entry.get("override"):
        return entry["override"]
    agreement = entry.get("agreement") or {"location": "paid", "rental": "paid", "archive": "licensed",
                                           "product": "placement", "artwork": "licensed"}[kind]
    if agreement in ("free", "public") and not entry.get("provider"):
        agreement = "paid" if kind == "location" else agreement
    return i18n.phrase(lang, "agreement.%s.%s" % (kind, agreement),
                       name=entry.get("name", ""), provider=entry.get("provider", entry.get("name", "")))


def legal_text(item, lang, meta):
    """item = {"key": "copyright", "values": {...}} oppure {"text": "..."}"""
    if item.get("text"):
        return item["text"]
    values = {"year": meta.get("year", ""), "owner": meta.get("copyright_owner", ""),
              "country": meta.get("country", "")}
    values.update(item.get("values", {}))
    if "uses" in values and not isinstance(values["uses"], str):
        values["uses"] = ", ".join(values["uses"])
    return i18n.phrase(item.get("lang", lang), "legal." + item["key"], **values)


def presenting_text(key, name, lang):
    return i18n.phrase(lang, "presenting." + key, name=name)


def header_text(key, lang, **values):
    return i18n.phrase(lang, "headers." + key, **values)


def role_text(role, lang):
    """Ruolo: chiave del dizionario (es. 'cinematographer') o testo libero."""
    return i18n.role_label(role, lang) if role else ""


def heading_text(heading, lang):
    """Intestazione: chiave reparto ('dept:camera'), chiave header ('h:thanks') o testo."""
    if not heading:
        return ""
    if heading.startswith("dept:"):
        return i18n.department_label(heading[5:], lang)
    if heading.startswith("h:"):
        return header_text(heading[2:], lang)
    if heading.startswith("role:"):
        return i18n.role_label(heading[5:], lang)
    return heading
