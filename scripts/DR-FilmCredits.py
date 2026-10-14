"""DR-FilmCredits - avvio dal menu di DaVinci Resolve (Workspace > Scripts > DR-FilmCredits).

Questo file viene copiato dall'installer nella cartella Scripts/Utility di Resolve.
La libreria vera e propria sta nella cartella utente (vedi install/install.py), cosi'
il menu Scripts mostra una sola voce. Se qualcosa va storto l'errore finisce in drfc.log
e in una finestra, invece di far sparire il pannello.
"""
import os
import sys
import time
import traceback


def _user_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "DR-FilmCredits")


def _log(msg):
    try:
        d = _user_dir()
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "drfc.log"), "a", encoding="utf-8") as f:
            f.write("%s [avvio] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _lib_dirs():
    dirs = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        dirs += [os.path.join(here, "..", "..", "src"), os.path.join(here, "src")]
    except NameError:
        pass
    dirs.append(os.path.join(_user_dir(), "lib"))
    return dirs


def _fail(text):
    _log("ERRORE\n" + text)
    print(text)
    try:
        g = globals()
        fusion = g.get("fusion") or g.get("fu")
        bmd = g.get("bmd")
        ui = fusion.UIManager
        disp = bmd.UIDispatcher(ui)
        win = disp.AddWindow({"ID": "DRFCErr0", "WindowTitle": "DR-FilmCredits – errore", "Geometry": [200, 200, 760, 420]},
                             ui.VGroup([ui.Label({"Text": "Il pannello non si e' avviato. Manda il file drfc.log a Ivan:\n%s" %
                                                  os.path.join(_user_dir(), "drfc.log"), "WordWrap": True, "Weight": 0}),
                                        ui.TextEdit({"PlainText": text, "ReadOnly": True}),
                                        ui.Button({"ID": "Ok", "Text": "OK", "Weight": 0})]))
        win.On.DRFCErr0.Close = lambda ev: disp.ExitLoop()
        win.On.Ok.Clicked = lambda ev: disp.ExitLoop()
        win.Show()
        disp.RunLoop()
        win.Hide()
    except Exception:
        pass


try:
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
except Exception:
    _fail(traceback.format_exc())
