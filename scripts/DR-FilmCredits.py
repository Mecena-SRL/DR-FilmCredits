"""DR-FilmCredits - avvio dal menu di DaVinci Resolve (Workspace > Scripts > DR-FilmCredits).

Questo file viene copiato dall'installer nella cartella Scripts/Utility di Resolve.
La libreria vera e propria sta nella cartella utente (vedi install/install.py), cosi'
il menu Scripts mostra una sola voce.
"""
import os
import sys


def _lib_dirs():
    dirs = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        dirs += [os.path.join(here, "..", "..", "src"), os.path.join(here, "src")]
    except NameError:
        pass
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    dirs.append(os.path.join(base, "DR-FilmCredits", "lib"))
    return dirs


for _d in _lib_dirs():
    if os.path.isdir(os.path.join(_d, "drfc")) and _d not in sys.path:
        sys.path.insert(0, _d)
        break

from drfc import ui_wizard  # noqa: E402

_g = globals()
_resolve = _g.get("resolve")
_bmd = _g.get("bmd")
if _resolve is None and _bmd is not None:
    _resolve = _bmd.scriptapp("Resolve")
_fusion = _g.get("fusion") or _g.get("fu") or (_resolve.Fusion() if _resolve else None)
if _bmd is None:
    import DaVinciResolveScript as _bmd  # noqa

ui_wizard.main(_fusion, _bmd, _resolve)
