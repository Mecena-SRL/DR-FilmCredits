"""Installer di DR-FilmCredits per DaVinci Resolve (Windows, macOS, Linux).

    python install/install.py            installa / aggiorna
    python install/install.py --remove   disinstalla

Copia:
  - la libreria (src/drfc)            -> <cartella utente>/DR-FilmCredits/lib/drfc
  - lo script di avvio                -> .../Fusion/Scripts/Utility/DR-FilmCredits.py
  - i Title Fusion manuali (templates)-> .../Fusion/Templates/Edit/Titles/DR-FilmCredits/
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_base():
    if sys.platform.startswith("win"):
        return os.environ.get("APPDATA", os.path.expanduser("~"))
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


def resolve_fusion_dir():
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", ""), "Blackmagic Design", "DaVinci Resolve", "Support", "Fusion")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "Blackmagic Design", "DaVinci Resolve", "Fusion")
    return os.path.join(home, ".local", "share", "DaVinciResolve", "Fusion")


def targets():
    fusion = resolve_fusion_dir()
    return {
        "lib": os.path.join(user_base(), "DR-FilmCredits", "lib", "drfc"),
        "script": os.path.join(fusion, "Scripts", "Utility", "DR-FilmCredits.py"),
        "templates": os.path.join(fusion, "Templates", "Edit", "Titles", "DR-FilmCredits"),
    }


def install():
    t = targets()
    if os.path.isdir(t["lib"]):
        shutil.rmtree(t["lib"])
    shutil.copytree(os.path.join(ROOT, "src", "drfc"), t["lib"],
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.dirname(t["script"]), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "scripts", "DR-FilmCredits.py"), t["script"])
    src_tpl = os.path.join(ROOT, "templates")
    os.makedirs(t["templates"], exist_ok=True)
    for fn in os.listdir(src_tpl):
        if fn.endswith(".setting"):
            shutil.copy2(os.path.join(src_tpl, fn), os.path.join(t["templates"], fn))
    for k, v in t.items():
        print("  %-9s %s" % (k, v))
    print("Installato. Riavviare Resolve: Workspace > Scripts > Utility > DR-FilmCredits")


def remove():
    t = targets()
    for k in ("lib", "templates"):
        if os.path.isdir(t[k]):
            shutil.rmtree(t[k])
    if os.path.exists(t["script"]):
        os.remove(t["script"])
    print("Rimosso.")


if __name__ == "__main__":
    remove() if "--remove" in sys.argv else install()
