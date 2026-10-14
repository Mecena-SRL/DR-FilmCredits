"""Riga di comando (funziona senza Resolve).

    python -m drfc presets                         elenca i preset
    python -m drfc new it_cinema progetto.drfc.json --title "Il film" [--lang it]
    python -m drfc import progetto.drfc.json crediti.csv
    python -m drfc template crediti.csv            CSV vuoto da compilare
    python -m drfc check progetto.drfc.json        validazione + tempi
    python -m drfc build progetto.drfc.json out/   .comp + .setting + anteprima HTML
    python -m drfc preview progetto.drfc.json      solo anteprima HTML (e apre il browser)
"""

import argparse
import os
import sys
import webbrowser

from . import engine, io_import, model, presets


def _print_issues(issues):
    icons = {"error": "[ERRORE]", "warning": "[AVVISO]", "info": "[info]  "}
    for i in issues:
        where = " (%s)" % i["block"] if i.get("block") else ""
        print("%s %s%s" % (icons.get(i["level"], "-"), i["message"], where))


def _summary(results):
    for seq, lay, tl, notes in results:
        secs = tl["total_frames"] / float(tl["fps"])
        if tl["kind"] == "crawl":
            print("- %s: rullo %.2fs, %d px/frame, %d elementi, %d pause" % (
                seq["id"], secs, tl["speed_px"], len(lay["elements"]), len(tl["holds"])))
        else:
            print("- %s: %d cartelli, %.2fs" % (seq["id"], len(tl["cards"]), secs))
        for n in notes:
            print("    %s" % n)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="drfc", description="DR-FilmCredits")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("presets")
    p_new = sub.add_parser("new")
    p_new.add_argument("preset")
    p_new.add_argument("path")
    p_new.add_argument("--title", default="")
    p_new.add_argument("--lang", default=None)
    p_imp = sub.add_parser("import")
    p_imp.add_argument("project")
    p_imp.add_argument("csv")
    p_tpl = sub.add_parser("template")
    p_tpl.add_argument("path")
    p_chk = sub.add_parser("check")
    p_chk.add_argument("project")
    p_b = sub.add_parser("build")
    p_b.add_argument("project")
    p_b.add_argument("out_dir")
    p_pv = sub.add_parser("preview")
    p_pv.add_argument("project")
    p_pv.add_argument("--no-open", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "presets":
        for pr in presets.list_presets():
            print("%-18s %s" % (pr["id"], presets.preset_label(pr, "it")))
    elif a.cmd == "new":
        p = presets.project_from_preset(a.preset, language=a.lang, title=a.title)
        model.save(p, a.path)
        print("Creato %s" % a.path)
    elif a.cmd == "import":
        p = model.load(a.project)
        n = io_import.import_file(p, a.csv)
        model.save(p, a.project)
        print("Importate %d voci in %s" % (n, a.project))
    elif a.cmd == "template":
        io_import.write_template(a.path)
        print("Modello CSV: %s" % a.path)
    elif a.cmd == "check":
        p = model.load(a.project)
        _clean, results, issues = engine.solve_all(p)
        _summary(results)
        _print_issues(issues)
        return 1 if any(i["level"] == "error" for i in issues) else 0
    elif a.cmd == "build":
        p = model.load(a.project)
        files, results, issues = engine.export(p, a.out_dir)
        _summary(results)
        _print_issues(issues)
        for f in files:
            print("  -> %s" % f["path"])
    elif a.cmd == "preview":
        p = model.load(a.project)
        out = os.path.join(os.path.dirname(os.path.abspath(a.project)), "preview")
        files, results, issues = engine.export(p, out, kinds=())
        _summary(results)
        _print_issues(issues)
        html = files[-1]["path"]
        print("Anteprima: %s" % html)
        if not a.no_open:
            webbrowser.open("file://" + os.path.abspath(html))
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
