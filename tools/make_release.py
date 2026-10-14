"""Crea dist/DR-FilmCredits-v<versione>.zip pronto da scaricare e installare.

    python tools/make_release.py
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from drfc import __version__  # noqa: E402

INCLUDE = ["src", "scripts", "install", "templates", "fonts", "examples", "docs", "README.md", "LICENSE"]
SKIP = ("__pycache__", ".pyc", ".pytest_cache", "drfc_render", "preview")


def main():
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    name = "DR-FilmCredits-v%s" % __version__
    path = os.path.join(out_dir, name + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUDE:
            full = os.path.join(ROOT, item)
            if os.path.isfile(full):
                z.write(full, os.path.join(name, item))
                continue
            for root, _dirs, files in os.walk(full):
                if any(s in root for s in SKIP):
                    continue
                for fn in files:
                    if fn.endswith(SKIP):
                        continue
                    fp = os.path.join(root, fn)
                    info = zipfile.ZipInfo.from_file(fp, os.path.join(name, os.path.relpath(fp, ROOT)))
                    if fn.endswith((".command", ".sh")):
                        info.external_attr = 0o755 << 16
                    with open(fp, "rb") as f:
                        z.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
    print(path)


if __name__ == "__main__":
    main()
