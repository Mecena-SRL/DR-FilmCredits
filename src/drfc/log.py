"""Log su file (drfc.log nella cartella utente): errori e ciclo di vita del pannello.

Serve a capire cosa e' successo quando Resolve non mostra niente: l'utente puo' mandare il
file. Non solleva mai eccezioni e si ruota da solo (max ~256 KB + una copia precedente).
"""

import os
import time
import traceback

from . import __version__, fusion_constants

MAX_BYTES = 256 * 1024


def path():
    return os.path.join(fusion_constants.user_dir(), "drfc.log")


def write(msg):
    try:
        p = path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p) and os.path.getsize(p) > MAX_BYTES:
            os.replace(p, p + ".1")
        with open(p, "a", encoding="utf-8") as f:
            f.write("%s [v%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, msg))
    except Exception:
        pass


def exception(context=""):
    """Registra l'eccezione corrente con traceback; ritorna il testo."""
    text = traceback.format_exc()
    write("ERRORE %s\n%s" % (context, text))
    return text
