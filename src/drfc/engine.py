"""Orchestrazione: progetto -> (layout, tempi) per sequenza -> validazione -> file Fusion."""

import os

from . import fusion_writer, model, preview, timing, validate
from .fontmetrics import FontIndex, Measurer, default_cache_path


def font_dirs_extra():
    """Font inclusi nel pacchetto (cartella fonts/ del repository o della libreria installata)."""
    from . import PKG_DIR, fusion_constants
    cands = [os.path.join(PKG_DIR, "..", "..", "fonts"), os.path.join(PKG_DIR, "..", "fonts"),
             os.path.join(fusion_constants.user_dir(), "fonts")]
    return [os.path.normpath(c) for c in cands if os.path.isdir(c)]


def make_measurer(project=None):
    extra = font_dirs_extra()
    if project and project.get("_base_dir"):
        fonts = os.path.join(project["_base_dir"], "fonts")
        if os.path.isdir(fonts):
            extra.append(fonts)
    return Measurer(FontIndex(extra_dirs=extra, cache_path=default_cache_path()))


def solve_all(project, measurer=None, only=None):
    """Ritorna (progetto_pulito, [(sequence, layout, timeline, notes)], issues)."""
    project = model.normalize(project) if "sequences" in project else project
    m = measurer or make_measurer(project)
    clean = validate.strip_empty(project)
    clean["_base_dir"] = project.get("_base_dir")
    results = []
    for seq in clean["sequences"]:
        if only and seq["id"] not in only:
            continue
        if not seq["blocks"]:
            continue
        lay, tl, notes = timing.solve(clean, seq, m)
        results.append((seq, lay, tl, notes))
    issues = validate.check_project(project, {s["id"]: (l, t, n) for s, l, t, n in results})
    return clean, results, issues


def export(project, out_dir, kinds=("comp", "setting"), t0=0, measurer=None, html=True):
    """Scrive per ogni sequenza: <id>.comp, <id>.setting e l'anteprima HTML."""
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    clean, results, issues = solve_all(project, measurer)
    files = []
    stem = model_slug(project)
    for seq, lay, tl, notes in results:
        for k in kinds:
            path = os.path.join(out_dir, "%s_%s.%s" % (stem, seq["id"], k))
            info = fusion_writer.write(clean, lay, tl, path, t0=t0, kind=k)
            files.append(info)
    if html and results:
        files.append({"path": preview.build_html(clean, results, os.path.join(out_dir, "%s_preview.html" % stem))})
    return files, results, issues


def model_slug(project):
    t = project["meta"].get("title") or "credits"
    s = "".join(c if c.isalnum() else "_" for c in t).strip("_")
    return s[:40] or "credits"
