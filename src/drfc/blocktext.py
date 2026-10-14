"""Formato testuale rapido per compilare i blocchi dal wizard (o da qualsiasi editor).

Ogni tipo di blocco ha una sintassi minima, pensata per incollare elenchi da mail,
fogli di calcolo e call sheet:

  credit / list   ruolo: Nome Uno, Nome Due          (ruolo = chiave es. 'cinematographer' o testo)
  card            ruolo: Nomi        oppure   [stile] testo   (una riga per riga del cartello)
  cast            Attore = Personaggio
  names           un nome per riga
  music           un brano per paragrafo (righe 'campo: valore', paragrafi separati da riga vuota)
                    titolo / title, autori / writers, musica / music, testo / lyrics, interpreti / performers,
                    edizioni / publisher, accordo / agreement, licenziante / licensor, agente / agent,
                    cc, team (si/no), extra
  agreements      nome | fornitore | accordo
  logos           percorso | tag | scala | nome
  media           percorso | didascalia | scala
  legal           @chiave campo=valore ...   oppure testo libero
  title / text    testo libero
"""

MUSIC_KEYS = {
    "titolo": "title", "title": "title", "titre": "title", "titel": "title", "titulo": "title",
    "autori": "writers", "writers": "writers", "written by": "writers", "auteurs": "writers", "autoren": "writers", "autores": "writers",
    "musica": "composers", "music": "composers", "composers": "composers",
    "testo": "lyricists", "lyrics": "lyricists", "lyricists": "lyricists",
    "arrangiamento": "arrangers", "arrangers": "arrangers",
    "interpreti": "performers", "performers": "performers", "performed by": "performers", "interpretes": "performers",
    "edizioni": "publisher", "publisher": "publisher", "editore": "publisher", "verlag": "publisher",
    "accordo": "agreement", "agreement": "agreement",
    "licenziante": "licensor", "licensor": "licensor", "courtesy of": "licensor",
    "agente": "agent", "agent": "agent", "cc": "cc_license", "cc_license": "cc_license",
    "team": "writers_team", "extra": "extra",
}
LIST_FIELDS = ("writers", "composers", "lyricists", "arrangers", "performers")
MUSIC_OUT = [("title", "titolo"), ("writers", "autori"), ("composers", "musica"), ("lyricists", "testo"),
             ("arrangers", "arrangiamento"), ("performers", "interpreti"), ("publisher", "edizioni"),
             ("agreement", "accordo"), ("licensor", "licenziante"), ("agent", "agente"), ("cc_license", "cc"),
             ("writers_team", "team")]


def split_names(s):
    s = s.strip()
    if not s:
        return []
    sep = ";" if ";" in s else ","
    return [n.strip() for n in s.split(sep) if n.strip()]


def _lines(text):
    return [l.rstrip() for l in (text or "").replace("\r", "").split("\n")]


def _role_names(line):
    if ":" in line:
        role, names = line.split(":", 1)
        return role.strip(), split_names(names)
    return "", split_names(line)


def _pipe(line, n):
    parts = [p.strip() for p in line.split("|")]
    return parts + [""] * (n - len(parts))


def parse(block, text):
    """Aggiorna `block` (dict) dal testo. Ritorna il blocco."""
    t = block["type"]
    lines = _lines(text)
    nonempty = [l.strip() for l in lines if l.strip()]
    if t == "credit":
        role, names = _role_names(nonempty[0]) if nonempty else ("", [])
        for extra in nonempty[1:]:
            names += split_names(extra)
        block["role"], block["names"] = role or block.get("role", ""), names
    elif t == "card":
        if nonempty and not nonempty[0].startswith("[") and ":" in nonempty[0] and len(nonempty) == 1:
            block["role"], block["names"] = _role_names(nonempty[0])
            block["lines"] = []
        else:
            out = []
            for l in nonempty:
                style = "card_name"
                if l.startswith("[") and "]" in l:
                    style, l = l[1:l.index("]")].strip(), l[l.index("]") + 1:].strip()
                out.append({"text": l, "style": style})
            block["lines"], block["role"], block["names"] = out, "", []
    elif t == "list":
        rows = []
        for l in nonempty:
            role, names = _role_names(l)
            if not role and rows:
                rows[-1]["names"] += names  # riga di continuazione
            else:
                rows.append({"role": role, "names": names})
        block["rows"] = rows
    elif t == "cast":
        rows = []
        for l in nonempty:
            if "=" in l:
                a, c = l.split("=", 1)
            else:
                a, c = l, ""
            rows.append({"actor": a.strip(), "character": c.strip()})
        block["rows"] = rows
    elif t == "names":
        block["names"] = nonempty
    elif t == "music":
        cues, cur = [], {}
        for l in lines + [""]:
            if not l.strip():
                if cur:
                    cues.append(cur)
                    cur = {}
                continue
            if ":" not in l:
                cur.setdefault("title", l.strip())
                continue
            k, v = l.split(":", 1)
            key = MUSIC_KEYS.get(k.strip().lower())
            v = v.strip()
            if not key:
                cur.setdefault("extra", []).append(l.strip())
            elif key in LIST_FIELDS:
                cur[key] = split_names(v)
            elif key == "writers_team":
                cur[key] = v.lower() in ("si", "sì", "yes", "true", "1", "oui", "ja")
            elif key == "extra":
                cur.setdefault("extra", []).append(v)
            else:
                cur[key] = v
        block["cues"] = cues
    elif t == "agreements":
        entries = []
        for l in nonempty:
            name, provider, ag = _pipe(l, 3)
            e = {"name": name}
            if provider:
                e["provider"] = provider
            if ag:
                e["agreement"] = ag
            entries.append(e)
        block["entries"] = entries
    elif t == "logos":
        items = []
        for l in nonempty:
            path, tag, scale, name = _pipe(l, 4)
            it = {"path": path}
            if tag:
                it["tag"] = tag
            if scale:
                it["scale"] = float(scale.replace(",", "."))
            if name:
                it["name"] = name
            items.append(it)
        block["items"] = items
    elif t == "media":
        items = []
        for l in nonempty:
            path, cap, scale = _pipe(l, 3)
            it = {"path": path}
            if cap:
                it["caption"] = cap
            if scale:
                it["scale"] = float(scale.replace(",", "."))
            items.append(it)
        block["items"] = items
    elif t == "legal":
        items, free = [], []
        for l in nonempty:
            if l.startswith("@"):
                parts = l[1:].split(" ", 1)
                item = {"key": parts[0].strip()}
                if len(parts) > 1:
                    vals = {}
                    for kv in _kv_split(parts[1]):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            vals[k.strip()] = v.strip()
                    if vals:
                        item["values"] = vals
                items.append(item)
            else:
                free.append(l)
        block["items"], block["text"] = items, "\n".join(free)
    elif t in ("title", "text"):
        block["text"] = "\n".join(lines).strip("\n")
    elif t == "spacer":
        try:
            block["lines"] = float(nonempty[0].replace(",", ".")) if nonempty else 2.0
        except ValueError:
            pass
    return block


def _kv_split(s):
    """'uses=montaggio, colore year=2026' -> ['uses=montaggio, colore', 'year=2026']"""
    out, cur = [], ""
    for tok in s.split(" "):
        if "=" in tok and cur:
            out.append(cur.strip())
            cur = tok
        else:
            cur = (cur + " " + tok) if cur else tok
    if cur:
        out.append(cur.strip())
    return out


def render(block):
    """Testo modificabile che rappresenta il blocco (inverso di parse)."""
    t = block["type"]
    if t == "credit":
        return "%s: %s" % (block.get("role", ""), ", ".join(block.get("names", [])))
    if t == "card":
        if block.get("lines"):
            return "\n".join("[%s] %s" % (l.get("style", "card_name"), l.get("text", "")) for l in block["lines"])
        return "%s: %s" % (block.get("role", ""), ", ".join(block.get("names", [])))
    if t == "list":
        return "\n".join("%s: %s" % (r.get("role", ""), ", ".join(r.get("names", []))) for r in block.get("rows", []))
    if t == "cast":
        return "\n".join("%s = %s" % (r.get("actor", ""), r.get("character", "")) for r in block.get("rows", []))
    if t == "names":
        return "\n".join(block.get("names", []))
    if t == "music":
        paras = []
        for c in block.get("cues", []):
            ls = []
            for k, label in MUSIC_OUT:
                v = c.get(k)
                if v in (None, "", [], False):
                    continue
                if isinstance(v, list):
                    v = ", ".join(v)
                if v is True:
                    v = "si"
                ls.append("%s: %s" % (label, v))
            for e in c.get("extra", []) or []:
                ls.append("extra: %s" % e)
            paras.append("\n".join(ls))
        return "\n\n".join(paras)
    if t == "agreements":
        return "\n".join(" | ".join([e.get("name", ""), e.get("provider", ""), e.get("agreement", "")]).rstrip(" |")
                         for e in block.get("entries", []))
    if t == "logos":
        return "\n".join(" | ".join([i.get("path", ""), i.get("tag", ""), str(i.get("scale", "")) if i.get("scale") else "",
                                     i.get("name", "")]).rstrip(" |") for i in block.get("items", []))
    if t == "media":
        return "\n".join(" | ".join([i.get("path", ""), i.get("caption", ""),
                                     str(i.get("scale", "")) if i.get("scale") else ""]).rstrip(" |")
                         for i in block.get("items", []))
    if t == "legal":
        ls = []
        for it in block.get("items", []):
            vals = " ".join("%s=%s" % (k, v if isinstance(v, str) else ", ".join(v)) for k, v in it.get("values", {}).items())
            ls.append(("@%s %s" % (it["key"], vals)).strip())
        if block.get("text"):
            ls.append(block["text"])
        return "\n".join(ls)
    if t in ("title", "text"):
        return block.get("text", "")
    if t == "spacer":
        return str(block.get("lines", 2.0))
    return ""


def summary(block, lang="it"):
    """Etichetta breve per l'elenco blocchi del wizard."""
    from . import phrases
    t = block["type"]
    if block.get("heading"):
        label = phrases.heading_text(block["heading"], lang)
    elif block.get("role"):
        label = phrases.role_text(block["role"], lang)
    elif t == "agreements":
        label = block.get("kind", "")
    elif t in ("title", "text"):
        label = (block.get("text") or "").split("\n")[0][:40]
    elif t == "card" and block.get("lines"):
        label = (block["lines"][0].get("text") or block.get("note", ""))[:40]
    elif t == "logos":
        label = phrases.heading_text(block.get("caption", ""), lang)
    else:
        label = block.get("note", "")[:40]
    n = len(block.get("names") or block.get("rows") or block.get("cues") or block.get("entries")
            or block.get("items") or [])
    return label or block.get("note", "")[:40], n
