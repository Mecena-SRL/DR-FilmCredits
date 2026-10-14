"""DR-FilmCredits: generatore guidato di titoli di testa e di coda per DaVinci Resolve.

Il pacchetto e' scritto in Python puro (>= 3.6, nessuna dipendenza) cosi' gira sia
dentro Resolve (Workspace > Scripts) sia da riga di comando per test e anteprime.
"""

__version__ = "0.3.0"

import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PKG_DIR, "data")
