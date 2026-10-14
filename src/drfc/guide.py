"""Percorso guidato: tipo di opera + territorio + destinazione + "cosa hai?" -> progetto
con SOLO le sezioni necessarie; riordino secondo lo standard; suggerimenti.

Logica pura (testabile); il wizard la richiama.
"""

import copy

from . import design, i18n, model, presets

WORK_TYPES = ["corto", "lungo", "documentario", "videoclip", "serie", "spot", "social"]
WORK_LABELS = {
    "it": {"corto": "Cortometraggio", "lungo": "Lungometraggio", "documentario": "Documentario",
           "videoclip": "Videoclip", "serie": "Serie / TV", "spot": "Spot / corporate", "social": "Social verticale"},
    "en": {"corto": "Short film", "lungo": "Feature film", "documentario": "Documentary",
           "videoclip": "Music video", "serie": "Series / TV", "spot": "Commercial / corporate", "social": "Social vertical"},
}
TERRITORIES = ["it", "eu", "us", "int"]
TERRITORY_LABELS = {"it": {"it": "Italia", "eu": "Coproduzione europea", "us": "USA (WGA/DGA)", "int": "Internazionale"},
                    "en": {"it": "Italy", "eu": "European co-production", "us": "USA (WGA/DGA)", "int": "International"}}

# (tipo, territorio) -> preset
PRESET_FOR = {
    ("lungo", "it"): "it_cinema", ("lungo", "eu"): "eu_coproduction", ("lungo", "us"): "us_theatrical",
    ("lungo", "int"): "eu_coproduction", ("corto", None): "short_festival", ("documentario", None): "documentary",
    ("videoclip", None): "music_video", ("serie", "it"): "it_tv", ("serie", "eu"): "it_tv",
    ("serie", "us"): "us_tv_streaming", ("serie", "int"): "us_tv_streaming", ("spot", None): "spot_corporate",
    ("social", None): "social_vertical",
}

ELEMENTS = ["key_crew", "cast", "crew", "music", "locations", "rentals", "archive", "products", "funders",
            "thanks", "backstage", "festival", "copyright"]
ELEMENT_LABELS = {
    "it": {"key_crew": "Crediti principali (regia, sceneggiatura, produzione)", "cast": "Cast / interpreti",
           "crew": "Troupe completa per reparti", "music": "Brani musicali", "locations": "Location",
           "rentals": "Noleggi / mezzi tecnici", "archive": "Materiali di repertorio", "products": "Prodotti / marchi",
           "funders": "Finanziatori e loghi", "thanks": "Ringraziamenti", "backstage": "Foto/video di backstage",
           "festival": "Festival e premi (allori)", "copyright": "Copyright e diciture legali"},
    "en": {"key_crew": "Key credits (director, writers, producers)", "cast": "Cast", "crew": "Full crew by department",
           "music": "Songs", "locations": "Locations", "rentals": "Equipment / facilities", "archive": "Archive footage",
           "products": "Products / brands", "funders": "Funders and logos", "thanks": "Special thanks",
           "backstage": "Behind-the-scenes media", "festival": "Festivals and awards (laurels)",
           "copyright": "Copyright and legal notices"},
}
DEFAULT_ELEMENTS = {
    "corto": ["key_crew", "cast", "crew", "music", "thanks", "copyright"],
    "lungo": ["key_crew", "cast", "crew", "music", "locations", "rentals", "funders", "thanks", "copyright"],
    "documentario": ["key_crew", "crew", "archive", "music", "locations", "thanks", "copyright"],
    "videoclip": ["key_crew", "crew", "copyright"],
    "serie": ["key_crew", "cast", "crew", "music", "copyright"],
    "spot": ["key_crew", "crew", "copyright"],
    "social": ["key_crew", "copyright"],
}
KEY_ROLES = {"director", "film_by", "written_by", "screenplay", "story", "based_on", "producer", "executive_producer",
             "coproducer", "created_by", "showrunner", "cinematographer", "editor", "production_designer",
             "costume_designer", "composer", "casting", "artist", "production_company", "client", "agency"}


def preset_for(work_type, territory):
    return PRESET_FOR.get((work_type, territory)) or PRESET_FOR.get((work_type, None)) or "short_festival"


def element_of(block):
    """A quale voce della checklist appartiene un blocco (None = sempre presente)."""
    t = block["type"]
    if t in ("title",):
        return None
    if t == "card":
        return None if not block.get("role") or block.get("role") in KEY_ROLES else "key_crew"
    if t == "cast" or (t == "names" and block.get("heading") in ("h:cast",)):
        return "cast"
    if t == "music":
        return "music"
    if t == "agreements":
        return {"location": "locations", "rental": "rentals", "archive": "archive", "product": "products",
                "artwork": "archive"}.get(block.get("kind"), "locations")
    if t == "names" and block.get("heading") == "h:thanks":
        return "thanks"
    if t == "media":
        return "backstage"
    if t == "laurels":
        return "festival"
    if t == "logos":
        return "funders"
    if t == "legal":
        keys = {i.get("key") for i in block.get("items", [])}
        if keys & {"mic_tax_credit", "creative_europe", "eurimages", "italian_tax_credit_foreign", "cultural_interest"}:
            return "funders"
        return "copyright"
    if t == "credit":
        return "key_crew" if block.get("role") in KEY_ROLES else "crew"
    if t == "list":
        roles = {r.get("role") for r in block.get("rows", [])}
        return "key_crew" if roles and roles <= KEY_ROLES else "crew"
    if t == "names":
        return "cast" if "cast" in (block.get("heading") or "") else "thanks"
    return None


def new_project(work_type, territory="it", elements=None, destination=None, language=None, **meta):
    """Progetto con solo le sezioni scelte."""
    pid = preset_for(work_type, territory)
    p = presets.project_from_preset(pid, language=language, **meta)
    p["meta"]["work_type"] = work_type
    p["meta"]["territory"] = territory
    if destination:
        design.apply_destination(p, destination)
    chosen = set(elements if elements is not None else DEFAULT_ELEMENTS.get(work_type, ELEMENTS))
    for s in p["sequences"]:
        s["blocks"] = [b for b in s["blocks"] if element_of(b) is None or element_of(b) in chosen]
    if "festival" in chosen:
        _ensure_festival_block(p)
    if "backstage" in chosen:
        for s in p["sequences"]:
            for b in s["blocks"]:
                if b["type"] == "media":
                    b["enabled"] = True
    p["sequences"] = [s for s in p["sequences"] if s["blocks"]]
    return model.normalize(p)


def _ensure_festival_block(p):
    cards = next((s for s in p["sequences"] if s["kind"] == "cards"), None)
    if cards is None:
        cards = model.new_sequence("opening", "cards", "Titoli di testa")
        p["sequences"].insert(0, cards)
    if not any(b["type"] == "laurels" for b in cards["blocks"]):
        idx = next((i for i, b in enumerate(cards["blocks"]) if b["type"] == "title"), len(cards["blocks"]))
        cards["blocks"].insert(idx, model.new_block("laurels"))


GENERIC = {
    "key_crew": lambda: [model.new_block("credit", role="director"), model.new_block("credit", role="screenplay"),
                         model.new_block("credit", role="producer")],
    "cast": lambda: [model.new_block("cast", heading="h:cast")],
    "crew": lambda: [model.new_block("list", heading="dept:" + d, rows=[{"role": r, "names": []} for r in rs])
                     for d, rs in (("camera", ["cinematographer", "first_ac"]), ("sound", ["sound_mixer"]),
                                   ("editing", ["editor"]))],
    "music": lambda: [model.new_block("music", heading="h:songs")],
    "locations": lambda: [model.new_block("agreements", kind="location")],
    "rentals": lambda: [model.new_block("agreements", kind="rental")],
    "archive": lambda: [model.new_block("agreements", kind="archive")],
    "products": lambda: [model.new_block("agreements", kind="product")],
    "funders": lambda: [model.new_block("logos", caption="h:with_support")],
    "thanks": lambda: [model.new_block("names", heading="h:thanks")],
    "backstage": lambda: [model.new_block("media")],
    "copyright": lambda: [model.new_block("legal", items=[{"key": "copyright"}])],
}


def add_element(project, element):
    """Aggiunge le sezioni di una voce della checklist prese dal preset del progetto."""
    pr = presets.load_preset(project["meta"].get("preset", "short_festival"))
    added = 0
    for ps in pr["sequences"]:
        seq = next((s for s in project["sequences"] if s["id"] == ps["id"]), None)
        if seq is None:
            seq = model.new_sequence(ps["id"], ps["kind"], ps.get("name", ps["id"]))
            project["sequences"].append(seq)
        for b in ps["blocks"]:
            if element_of(b) == element and not _has_equivalent(seq, b):
                seq["blocks"].append(copy.deepcopy(b))
                added += 1
    if element == "festival":
        _ensure_festival_block(project)
        added += 1
    if not added and element in GENERIC:
        seq = next((s for s in project["sequences"] if s["kind"] == "crawl"), None)
        if seq is None:
            seq = model.new_sequence("end", "crawl", "Titoli di coda")
            project["sequences"].append(seq)
        for b in GENERIC[element]():
            if not _has_equivalent(seq, b):
                seq["blocks"].append(b)
                added += 1
    normalized = model.normalize(project)
    project["sequences"] = normalized["sequences"]
    reorder_project(project)
    return added


def _has_equivalent(seq, b):
    for x in seq["blocks"]:
        if x["type"] != b["type"]:
            continue
        if b["type"] in ("credit", "card") and x.get("role") == b.get("role") and (b.get("role") or x.get("lines") == b.get("lines")):
            return True
        if b["type"] == "list" and x.get("heading") == b.get("heading"):
            return True
        if b["type"] == "agreements" and x.get("kind") == b.get("kind"):
            return True
        if b["type"] in ("cast", "music", "logos", "laurels", "media") or (
                b["type"] == "names" and x.get("heading") == b.get("heading")):
            return True
        if b["type"] == "legal" and {i.get("key") for i in x.get("items", [])} == {i.get("key") for i in b.get("items", [])}:
            return True
    return False


# ------------------------------------------------------------------ riordino
DEPT_ORDER = list(i18n.roles()["departments"].keys())

OPENING_ORDER = {
    # ordine dei cartelli di testa (dopo presenta/produzione); la regia sempre ultima
    "it": ["film_by", "@cast", "@laurels", "@title", "casting", "composer", "costume_designer", "editor",
           "production_designer", "cinematographer", "general_manager", "story", "screenplay", "written_by",
           "executive_producer", "producer", "director"],
    "us": ["film_by", "@cast", "@laurels", "@title", "casting", "composer", "costume_designer", "editor",
           "production_designer", "cinematographer", "executive_producer", "producer", "based_on", "story",
           "screenplay", "written_by", "director"],
}
END_HEAD = ["director", "film_by", "created_by", "written_by", "screenplay", "story", "based_on", "producer",
            "executive_producer", "coproducer", "artist", "production_company"]


def _role_rank(role, order):
    return order.index(role) if role in order else len(order)


def _block_role(b):
    if b.get("role"):
        return b["role"]
    rows = b.get("rows") or []
    return rows[0].get("role") if rows else None


def _end_rank(b):
    t = b["type"]
    if t in ("credit", "card"):
        r = _block_role(b)
        if r in END_HEAD:
            return (0, END_HEAD.index(r), 0)
        if t == "card" and not r:
            return (0, -1, 0)
        dept = i18n.role_department(r) if r else None
        return (2, DEPT_ORDER.index(dept) if dept in DEPT_ORDER else 99, 0)
    if t == "cast" or (t == "names" and b.get("heading") == "h:cast"):
        return (1, 0, 0)
    if t == "list":
        h = b.get("heading") or ""
        if h.startswith("dept:") and h[5:] in DEPT_ORDER:
            return (2, DEPT_ORDER.index(h[5:]), 0)
        r = _block_role(b)
        if r in END_HEAD:
            return (0, len(END_HEAD), 0)
        dept = i18n.role_department(r) if r else None
        return (2, DEPT_ORDER.index(dept) if dept in DEPT_ORDER else 98, 0)
    order = {"music": 3, "agreements": 4, "names": 5, "media": 6, "laurels": 7, "text": 8, "spacer": 8,
             "logos": 9, "legal": 10, "title": 0}
    sub = {"location": 0, "rental": 1, "archive": 2, "product": 3, "artwork": 4}.get(b.get("kind"), 0)
    if t == "legal":
        keys = [i.get("key") for i in b.get("items", [])]
        sub = 2 if "copyright" in keys or "video_copyright" in keys or "phonographic" in keys else (
            0 if any(k in ("mic_tax_credit", "creative_europe", "eurimages", "ai_disclosure") for k in keys) else 1)
    return (order.get(t, 8), sub, 0)


def _opening_rank(b, territory):
    order = OPENING_ORDER.get("us" if territory == "us" else "it")
    t = b["type"]
    if t == "card" and not b.get("role"):
        return (0, 0)  # presenta / produzione: restano in testa nell'ordine dato
    if t == "logos":
        return (0, 1)
    if t == "laurels":
        return (1, order.index("@laurels"))
    if t == "title":
        return (1, order.index("@title"))
    if t == "card" and b.get("names") and not b.get("role"):
        return (1, order.index("@cast"))
    r = _block_role(b)
    return (1, _role_rank(r, order) if r else order.index("@cast"))


def reorder(sequence, territory="it"):
    """Riordina i blocchi secondo lo standard (ordinamento stabile: a parita' resta l'ordine dato)."""
    idx = {id(b): i for i, b in enumerate(sequence["blocks"])}
    if sequence.get("kind") == "cards":
        key = lambda b: (_opening_rank(b, territory), idx[id(b)])
    else:
        key = lambda b: (_end_rank(b), idx[id(b)])
    sequence["blocks"] = sorted(sequence["blocks"], key=key)
    return sequence


def reorder_project(project):
    ter = project["meta"].get("territory") or presets.load_preset(project["meta"].get("preset", "it_cinema")).get("territory", "it")
    for s in project["sequences"]:
        reorder(s, ter)
    return project


# ------------------------------------------------------------------ suggerimenti
def suggestions(project):
    """Elementi consigliati/obbligatori non ancora presenti: [(element, motivo)]."""
    present = set()
    for s in project["sequences"]:
        for b in s["blocks"]:
            e = element_of(b)
            if e and b.get("enabled", True):
                present.add(e)
    out = []
    meta = project["meta"]
    if "copyright" not in present:
        out.append(("copyright", "Il copyright chiude sempre i titoli di coda."))
    if meta.get("funding") and "funders" not in present:
        out.append(("funders", "Hai indicato dei finanziamenti: servono loghi e diciture."))
    if meta.get("ai_used"):
        out.append(("copyright", "Uso di IA: la dichiarazione va nei titoli (tax credit italiano)."))
    wt = meta.get("work_type")
    for e in DEFAULT_ELEMENTS.get(wt, []):
        if e not in present and e not in [x[0] for x in out]:
            out.append((e, "Tipico per questo tipo di opera."))
    return out
