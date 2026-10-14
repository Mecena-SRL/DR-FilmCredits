"""Scarica i font liberi (SIL OFL / Apache) usati dai set predefiniti in fonts/.

    python tools/fetch_fonts.py

Si usano solo file *statici* (Regular, Medium, Italic...): i font variabili non sono
affidabili in Fusion Text+. Le licenze vengono salvate accanto ai font.
"""
import os
import shutil
import sys
import urllib.request

RAW = "https://raw.githubusercontent.com/"
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

SOURCES = {
    "EB Garamond": ("octaviopardo/EBGaramond12/master/", "fonts/ttf/EBGaramond-%s.ttf",
                    ["Regular", "Medium", "SemiBold", "Italic"], "OFL.txt"),
    "Cormorant Garamond": ("CatharsisFonts/Cormorant/master/", "fonts/ttf/CormorantGaramond-%s.ttf",
                           ["Regular", "Medium", "SemiBold", "Italic"], "OFL.txt"),
    "Montserrat": ("JulietaUla/Montserrat/master/", "fonts/ttf/Montserrat-%s.ttf",
                   ["Light", "Regular", "Medium", "SemiBold", "Bold"], "OFL.txt"),
    "IBM Plex Sans": ("IBM/plex/master/", "packages/plex-sans/fonts/complete/ttf/IBMPlexSans-%s.ttf",
                      ["Light", "Regular", "Medium"], "LICENSE.txt"),
    "IBM Plex Serif": ("IBM/plex/master/", "packages/plex-serif/fonts/complete/ttf/IBMPlexSerif-%s.ttf",
                       ["Regular", "Medium"], "LICENSE.txt"),
    "Lato": ("google/fonts/main/", "ofl/lato/Lato-%s.ttf", ["Light", "Regular", "Italic", "Bold"], "ofl/lato/OFL.txt"),
    "Bebas Neue": ("google/fonts/main/", "ofl/bebasneue/BebasNeue-%s.ttf", ["Regular"], "ofl/bebasneue/OFL.txt"),
    "DM Serif Display": ("google/fonts/main/", "ofl/dmserifdisplay/DMSerifDisplay-%s.ttf", ["Regular", "Italic"],
                         "ofl/dmserifdisplay/OFL.txt"),
    "Roboto": ("googlefonts/roboto/main/", "src/hinted/Roboto-%s.ttf", ["Regular", "Medium", "Bold"], "LICENSE"),
}
# Inter: file statici dal pacchetto di sistema se presenti, altrimenti dal repository rsms/inter
INTER_LOCAL = "/usr/share/fonts/opentype/inter"


def fetch(url, dst):
    with urllib.request.urlopen(url, timeout=60) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f)


def main():
    ok, fail = 0, []
    for family, (repo, pattern, styles, lic) in SOURCES.items():
        d = os.path.join(ROOT, family.replace(" ", ""))
        os.makedirs(d, exist_ok=True)
        for st in styles:
            url = RAW + repo + pattern % st
            dst = os.path.join(d, os.path.basename(pattern % st))
            try:
                fetch(url, dst)
                ok += 1
            except Exception as e:  # rete o file spostato
                fail.append("%s %s: %s" % (family, st, e))
        try:
            fetch(RAW + repo + lic, os.path.join(d, "LICENSE.txt"))
        except Exception as e:
            fail.append("%s licenza: %s" % (family, e))
    d = os.path.join(ROOT, "Inter")
    os.makedirs(d, exist_ok=True)
    for st in ["Regular", "Medium", "SemiBold", "Light", "Italic"]:
        src = os.path.join(INTER_LOCAL, "Inter-%s.otf" % st)
        if os.path.exists(src):
            shutil.copy2(src, d)
            ok += 1
        else:
            fail.append("Inter %s: non trovato in %s" % (st, INTER_LOCAL))
    print("Scaricati %d file" % ok)
    for f in fail:
        print("  ! " + f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
