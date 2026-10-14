"""Installer di DR-FilmCredits per DaVinci Resolve (Windows, macOS, Linux).

    python install/install.py            installa / aggiorna
    python install/install.py --remove   disinstalla

Copia:
  - la libreria (src/drfc)            -> <cartella utente>/DR-FilmCredits/lib/drfc
  - lo script di avvio                -> .../Fusion/Scripts/Utility/DR-FilmCredits.py
  - i Title Fusion manuali (templates)-> .../Fusion/Templates/Edit/Titles/DR-FilmCredits/
  - i font liberi dei set predefiniti   -> cartella font dell'utente (senza permessi admin)
    (opzione --no-fonts per saltarli)
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


def font_targets():
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Fonts")
    return os.path.join(home, ".local", "share", "fonts", "DR-FilmCredits")


def install_fonts():
    """Installa per l'utente corrente i font liberi dei set predefiniti (nessun permesso admin)."""
    src = os.path.join(ROOT, "fonts")
    if not os.path.isdir(src):
        return 0
    dst = font_targets()
    os.makedirs(dst, exist_ok=True)
    keep = os.path.join(user_base(), "DR-FilmCredits", "fonts")  # copia per le misure del motore
    os.makedirs(keep, exist_ok=True)
    n = 0
    reg = None
    if sys.platform.startswith("win"):
        try:
            import winreg
            reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts",
                                 0, winreg.KEY_SET_VALUE)
        except OSError:
            reg = None
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if not fn.lower().endswith((".ttf", ".otf")):
                continue
            path = os.path.join(root, fn)
            target = os.path.join(dst, fn)
            shutil.copy2(path, target)
            shutil.copy2(path, os.path.join(keep, fn))
            if reg is not None:
                import winreg
                kind = "TrueType" if fn.lower().endswith(".ttf") else "OpenType"
                winreg.SetValueEx(reg, "%s (%s)" % (os.path.splitext(fn)[0], kind), 0, winreg.REG_SZ, target)
            n += 1
    if sys.platform.startswith("linux"):
        os.system("fc-cache -f >/dev/null 2>&1")
    return n


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
    if "--no-fonts" not in sys.argv:
        print("  font      %d file in %s" % (install_fonts(), font_targets()))
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
