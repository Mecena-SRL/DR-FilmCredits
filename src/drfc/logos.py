"""Kit loghi: registro degli enti + cartella locale aggiornabile.

- Il registro (data/logos/registry.json) elenca enti, tag, pagine ufficiali, URL diretti e
  regole d'uso. Si aggiorna da GitHub con update_registry().
- I file stanno nella cartella utente (DR-FilmCredits/logos/<id>/). update() scarica
  solo gli URL diretti e solo se cambiati (ETag/Last-Modified); per gli enti che concedono
  il logo su richiesta si apre la pagina ufficiale e si importa il file ricevuto.
- Fusion legge PNG/TIFF/JPG, non SVG/PDF: questi vengono segnalati da convertire.
- resolve() sceglie la variante adatta allo sfondo (chiara su scuro, scura su chiaro).
"""

import json
import os
import shutil
import urllib.error
import urllib.request
import webbrowser
import zipfile

from . import DATA_DIR, fusion_constants, imageinfo

REGISTRY_URL = "https://raw.githubusercontent.com/ivan-94m/DR-FilmCredits/main/src/drfc/data/logos/registry.json"
RASTER = (".png", ".tif", ".tiff", ".jpg", ".jpeg")
VECTOR = (".svg", ".pdf", ".eps", ".ai")
# parole nei nomi file che indicano la variante per sfondo scuro (logo chiaro)
LIGHT_HINTS = ("white", "bianco", "neg", "negativo", "reverse", "inverted", "inv", "light", "blanc", "weiss")
DARK_HINTS = ("black", "nero", "pos", "positivo", "dark", "noir", "schwarz", "color", "colour", "colore")


def kit_dir():
    return os.path.join(fusion_constants.user_dir(), "logos")


def _user_registry_path():
    return os.path.join(kit_dir(), "registry.json")


def registry():
    """Registro: versione utente aggiornata (se piu' recente) altrimenti quella inclusa."""
    with open(os.path.join(DATA_DIR, "logos", "registry.json"), encoding="utf-8") as f:
        base = json.load(f)
    up = _user_registry_path()
    if os.path.exists(up):
        try:
            with open(up, encoding="utf-8") as f:
                user = json.load(f)
            if user.get("version", 0) >= base.get("version", 0):
                base = user
        except ValueError:
            pass
    custom = _load_manifest().get("custom", [])
    base["logos"] = list(base["logos"]) + custom
    return base


def entry(logo_id):
    for e in registry()["logos"]:
        if e["id"] == logo_id:
            return e
    return None


def by_tag(tag):
    return [e for e in registry()["logos"] if e.get("tag") == tag]


# ------------------------------------------------------------------ manifest locale
def _manifest_path():
    return os.path.join(kit_dir(), "manifest.json")


def _load_manifest():
    try:
        with open(_manifest_path(), encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {"files": {}, "http": {}, "custom": []}


def _save_manifest(m):
    os.makedirs(kit_dir(), exist_ok=True)
    tmp = _manifest_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=1, ensure_ascii=False)
    os.replace(tmp, _manifest_path())


def files(logo_id):
    d = os.path.join(kit_dir(), logo_id)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if not f.startswith("."))


def status(logo_id):
    """ready | convert | request | download | page"""
    fs = files(logo_id)
    if any(f.lower().endswith(RASTER) for f in fs):
        return "ready"
    if any(f.lower().endswith(VECTOR) for f in fs):
        return "convert"
    e = entry(logo_id) or {}
    if e.get("request_required"):
        return "request"
    if e.get("download"):
        return "download"
    return "page"


STATUS_LABEL = {
    "it": {"ready": "pronto", "convert": "da convertire in PNG", "request": "da richiedere all'ente",
           "download": "da scaricare", "page": "da scaricare dalla pagina ufficiale"},
    "en": {"ready": "ready", "convert": "convert to PNG", "request": "request from the body",
           "download": "to download", "page": "download from official page"},
}


def list_status(lang="it"):
    labels = STATUS_LABEL.get(lang, STATUS_LABEL["en"])
    return [(e["id"], e["name"], e.get("tag", ""), labels[status(e["id"])]) for e in registry()["logos"]]


# ------------------------------------------------------------------ import / download
def _store(logo_id, src_path, name=None):
    d = os.path.join(kit_dir(), logo_id)
    os.makedirs(d, exist_ok=True)
    out = []
    if src_path.lower().endswith(".zip"):
        with zipfile.ZipFile(src_path) as z:
            for info in z.infolist():
                fn = os.path.basename(info.filename)
                if not fn or fn.startswith(".") or "__MACOSX" in info.filename:
                    continue
                if fn.lower().endswith(RASTER + VECTOR):
                    dst = os.path.join(d, fn)
                    with z.open(info) as s, open(dst, "wb") as f:
                        shutil.copyfileobj(s, f)
                    out.append(dst)
    else:
        dst = os.path.join(d, name or os.path.basename(src_path))
        if os.path.abspath(src_path) != os.path.abspath(dst):
            shutil.copy2(src_path, dst)
        out.append(dst)
    return out


def import_file(logo_id, path, tag=None, name=None):
    """Importa un PNG/ZIP ricevuto dall'ente (o un logo personale: id nuovo + tag)."""
    m = _load_manifest()
    if entry(logo_id) is None:
        m.setdefault("custom", []).append({
            "id": logo_id, "tag": tag or logo_id, "name": name or logo_id, "category": "custom",
            "official_page": "", "download": [], "request_required": False, "usage_notes": "Logo personale",
            "verified": False})
    stored = _store(logo_id, path)
    m.setdefault("files", {})[logo_id] = [os.path.basename(p) for p in files(logo_id)]
    _save_manifest(m)
    return stored


def update(ids=None, opener=None, log=print):
    """Scarica i loghi con URL diretto, solo se cambiati. Ritorna dict id -> esito."""
    opener = opener or urllib.request.urlopen
    m = _load_manifest()
    http = m.setdefault("http", {})
    out = {}
    for e in registry()["logos"]:
        if ids and e["id"] not in ids:
            continue
        if not e.get("download"):
            out[e["id"]] = status(e["id"])
            continue
        results = []
        for dl in e["download"]:
            url = dl if isinstance(dl, str) else dl.get("url")
            req = urllib.request.Request(url, headers={"User-Agent": "DR-FilmCredits"})
            meta = http.get(url, {})
            if meta.get("etag"):
                req.add_header("If-None-Match", meta["etag"])
            if meta.get("modified"):
                req.add_header("If-Modified-Since", meta["modified"])
            try:
                with opener(req, timeout=60) as r:
                    fn = os.path.basename(url.split("?")[0]) or (e["id"] + ".bin")
                    tmp_dir = os.path.join(kit_dir(), ".tmp")
                    os.makedirs(tmp_dir, exist_ok=True)
                    tmp = os.path.join(tmp_dir, fn)
                    with open(tmp, "wb") as f:
                        shutil.copyfileobj(r, f)
                    _store(e["id"], tmp)
                    os.remove(tmp)
                    http[url] = {"etag": r.headers.get("ETag"), "modified": r.headers.get("Last-Modified")}
                    results.append("updated")
            except urllib.error.HTTPError as err:
                results.append("unchanged" if err.code == 304 else "error %d" % err.code)
            except Exception as err:  # rete assente, timeout...
                results.append("error %s" % err)
        out[e["id"]] = ",".join(results)
        log("%-24s %s" % (e["id"], out[e["id"]]))
    m["files"] = {e["id"]: [os.path.basename(p) for p in files(e["id"])] for e in registry()["logos"] if files(e["id"])}
    _save_manifest(m)
    return out


def update_registry(url=REGISTRY_URL, opener=None):
    """Scarica l'ultima versione del registro enti dal repository."""
    opener = opener or urllib.request.urlopen
    with opener(urllib.request.Request(url, headers={"User-Agent": "DR-FilmCredits"}), timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "logos" not in data:
        raise ValueError("Registro non valido")
    os.makedirs(kit_dir(), exist_ok=True)
    with open(_user_registry_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return len(data["logos"])


def open_page(logo_id):
    e = entry(logo_id)
    if e and e.get("official_page"):
        webbrowser.open(e["official_page"])
        return e["official_page"]
    return None


# ------------------------------------------------------------------ scelta del file
def _variant_score(path, light_bg):
    n = os.path.basename(path).lower()
    is_light_logo = any(h in n for h in LIGHT_HINTS)
    is_dark_logo = any(h in n for h in DARK_HINTS)
    score = 0
    if light_bg:
        score += 2 if is_dark_logo else (-2 if is_light_logo else 0)
    else:
        score += 2 if is_light_logo else (-1 if is_dark_logo else 0)
    if n.endswith(".png"):
        score += 1  # trasparenza
    size = imageinfo.image_size(path)
    if size:
        score += min(size[0], 4000) / 4000.0  # preferisce la risoluzione maggiore
    return score


def resolve(logo_id, light_bg=False):
    """Percorso del file migliore per lo sfondo, o None se il logo non e' nel kit."""
    cands = [f for f in files(logo_id) if f.lower().endswith(RASTER)]
    if not cands:
        return None
    return max(cands, key=lambda p: _variant_score(p, light_bg))
