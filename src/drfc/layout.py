"""Motore di impaginazione.

Trasforma una sequenza (crawl o cartelli) in una lista di elementi posizionati in
pixel: testi (una o piu' righe con stile risolto) e immagini/video. Le coordinate sono
nel sistema "contenuto": x da sinistra del fotogramma, y dall'alto del contenuto del
crawl (per i cartelli: dall'alto del fotogramma).

Principi tipografici applicati:
- due colonne su asse centrale: ruolo allineato a destra, nomi a sinistra, gutter fisso;
- tutte le righe di una riga-credito condividono la stessa linea di base;
- interlinea uniforme per blocco (le colonne restano allineate in Text+);
- testo mai fuori dalla title-safe: le righe troppo lunghe vanno a capo e generano avviso;
- loghi bilanciati per area ottica (non per larghezza), cosi' marchi larghi e quadrati
  hanno lo stesso peso visivo.
"""

import copy
import json
import math
import os

from . import DATA_DIR, i18n, imageinfo, phrases
from .fontmetrics import Measurer
from .model import resolve_path

REF_H = 1080.0

_themes = None


def themes():
    global _themes
    if _themes is None:
        with open(os.path.join(DATA_DIR, "themes.json"), encoding="utf-8") as f:
            _themes = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    return _themes


def apply_case(text, case):
    if case == "upper":
        return text.upper()
    if case == "lower":
        return text.lower()
    if case == "title":
        return " ".join(w[:1].upper() + w[1:] for w in text.split(" "))
    return text


class Ctx(object):
    def __init__(self, project, sequence, measurer=None, gap_scale=1.0):
        self.project = project
        self.seq = sequence
        self.lang = project["meta"].get("language", "it")
        fmt = project["format"]
        self.W, self.H = float(fmt["width"]), float(fmt["height"])
        self.scale = self.H / REF_H
        self.m = measurer or Measurer()
        self.cards = sequence.get("kind") == "cards"
        theme_name = project["style"].get("theme", "classic")
        self.theme = themes().get(theme_name) or themes()["classic"]
        self.metrics = dict(self.theme["metrics"])
        self.metrics.update(project["style"].get("metrics", {}))
        self.gap_scale = gap_scale
        self.warnings = []
        safe = float(fmt.get("safe_title", 0.9))
        mx, my = self.W * (1 - safe) / 2, self.H * (1 - safe) / 2
        self.safe = (mx, my, self.W - mx, self.H - my)
        lay = project["layout"]
        split = lay.get("split", "none")
        sl, _, sr, _ = self.safe
        sw = sr - sl
        if split in ("media_left", "media_right") and not self.cards:
            tw = sw * float(lay.get("text_lane", 0.5))
            if split == "media_left":
                self.lane = (sr - tw, sr)
                self.side_lane = (sl, sr - tw)
            else:
                self.lane = (sl, sl + tw)
                self.side_lane = (sl + tw, sr)
            self.axis = (self.lane[0] + self.lane[1]) / 2
        else:
            self.lane = (sl, sr)
            self.side_lane = None
            self.axis = self.W * float(lay.get("axis", 0.5))
        mode = lay.get("render_mode", "auto")
        self.line_mode = mode == "line"
        self.auto_mode = mode == "auto"

    # ------------------------------------------------------------ stili
    def px(self, v):
        return v * self.scale

    def style(self, key, block=None):
        if self.cards and key in ("role", "name"):
            key = "card_" + key
        base = copy.deepcopy(self.theme["styles"].get(key) or self.theme["styles"]["name"])
        base.update(self.project["style"].get("overrides", {}).get(key, {}))
        if block:
            base.update(block.get("style", {}).get(key, {}))
        base["size_px"] = self.px(float(base["size"]))
        base["key"] = key
        return base

    def name_advance(self, block=None):
        return self.m.line_height(self.style("name", block))

    def warn(self, block, msg):
        self.warnings.append({"block": block.get("id") if block else None, "message": msg})

    # ------------------------------------------------------------ misure/a capo
    def width(self, text, st):
        return self.m.width(apply_case(text, st.get("case")), st)

    def wrap(self, text, st, max_w):
        out = []
        for para in text.split("\n"):
            words = para.split(" ")
            line = ""
            for w in words:
                cand = (line + " " + w) if line else w
                if line and self.width(cand, st) > max_w:
                    out.append(line)
                    line = w
                else:
                    line = cand
            out.append(line)
        return out

    # ------------------------------------------------------------ elementi
    def text_el(self, lines, st, x, anchor, baseline, advance, block):
        lines = [apply_case(l, st.get("case")) for l in lines]
        asc, desc = self.m.vmetrics(st)
        n = len(lines)
        nat = self.m.natural_line_height(st)
        return {
            "kind": "text", "lines": lines, "style": st, "x": x, "anchor": anchor,
            "baseline": baseline, "advance": advance,
            "line_spacing": advance / nat if nat else 1.0,
            "ascender": asc, "descender": desc,
            "top": baseline - asc, "bottom": baseline + (n - 1) * advance - desc,
            "center_y": baseline + ((n - 1) * advance - asc - desc) / 2.0,
            "width": max([self.m.width(l, st) for l in lines] or [0]),
            "block": block.get("id"),
        }

    def emit_column(self, lines, st, x, anchor, y_top, advance, ref_st, block):
        """Colonna di righe con interlinea `advance`; righe vuote = spazio.
        In modalita' blocco: un elemento per colonna; in modalita' riga: uno per riga."""
        asc_r, desc_r = self.m.vmetrics(ref_st)
        base0 = y_top + advance / 2.0 + (asc_r + desc_r) / 2.0
        els = []
        if not any(l.strip() for l in lines):
            return els
        # auto: colonne centrate = un Text+ multiriga; colonne allineate a sx/dx = un Text+
        # per riga ancorato al bordo (allineamento indipendente dalla giustificazione Text+)
        if self.line_mode or (self.auto_mode and anchor != "center"):
            for i, l in enumerate(lines):
                if l.strip():
                    els.append(self.text_el([l], st, x, anchor, base0 + i * advance, advance, block))
        else:
            first = next(i for i, l in enumerate(lines) if l.strip())
            last = max(i for i, l in enumerate(lines) if l.strip())
            els.append(self.text_el(lines[first:last + 1], st, x, anchor, base0 + first * advance, advance, block))
        return els


# ======================================================================= builders
def _stack(ctx, block, y, groups, align="center", x=None):
    """Pila verticale di gruppi (righe, style_key) o ('gap', px)."""
    els, cur = [], y
    if x is None:
        x = {"center": ctx.axis, "left": ctx.lane[0], "right": ctx.lane[1]}[align]
    max_w = (ctx.lane[1] - ctx.lane[0]) * float(ctx.project["layout"].get("max_text_width", 0.8)) \
        if align == "center" else (ctx.lane[1] - ctx.lane[0])
    for g in groups:
        if g[0] == "gap":
            cur += g[1]
            continue
        lines, skey = g
        st = ctx.style(skey, block)
        wrapped = []
        for l in lines:
            if ctx.width(l, st) > max_w:
                wrapped.extend(ctx.wrap(l, st, max_w))
            else:
                wrapped.append(l)
        adv = ctx.m.line_height(st)
        els.extend(ctx.emit_column(wrapped, st, x, align, cur, adv, st, block))
        cur += adv * len(wrapped)
    return els, cur - y


def _heading_groups(ctx, block):
    h = phrases.heading_text(block.get("heading", ""), ctx.lang)
    if not h:
        return []
    gap = ctx.metrics["heading_gap"] * ctx.name_advance(block) * ctx.gap_scale
    return [([h], "heading"), ("gap", gap)]


def _role_text(ctx, role):
    return phrases.role_text(role, ctx.lang)


def _two_column(ctx, block, y, rows):
    """rows: lista di (righe_sinistra, style_sx, righe_destra, style_dx)."""
    g = ctx.px(ctx.metrics["gutter"])
    left_x, right_x = ctx.axis - g, ctx.axis + g
    left_max, right_max = left_x - ctx.lane[0], ctx.lane[1] - right_x
    if not rows:
        return [], 0.0
    l_st = ctx.style(rows[0][1], block)
    r_st = ctx.style(rows[0][3], block)
    adv = max(ctx.m.line_height(l_st), ctx.m.line_height(r_st))
    row_gap = ctx.metrics.get("row_gap", 0.0)
    per_line = ctx.line_mode or ctx.auto_mode
    gap_lines = 0 if per_line else int(round(row_gap))
    left_lines, right_lines, extra = [], [], 0.0
    gap_px_line_mode = row_gap * adv if per_line else 0.0
    els = []
    cur = y
    for ri, (ll, _ls, rl, _rs) in enumerate(rows):
        lw = []
        for t in ll:
            lw.extend(ctx.wrap(t, l_st, left_max) if ctx.width(t, l_st) > left_max else [t])
        rw = []
        for t in rl:
            rw.extend(ctx.wrap(t, r_st, right_max) if ctx.width(t, r_st) > right_max else [t])
        if len(lw) > len(ll) or len(rw) > len(rl):
            ctx.warn(block, "Riga troppo lunga mandata a capo: %s" % " / ".join(ll + rl)[:80])
        n = max(len(lw), len(rw), 1)
        lw += [""] * (n - len(lw))
        rw += [""] * (n - len(rw))
        if per_line:
            els += ctx.emit_column(lw, l_st, left_x, "right", cur, adv, r_st, block)
            els += ctx.emit_column(rw, r_st, right_x, "left", cur, adv, r_st, block)
            cur += n * adv + (gap_px_line_mode if ri < len(rows) - 1 else 0)
        else:
            left_lines += lw
            right_lines += rw
            if ri < len(rows) - 1:
                left_lines += [""] * gap_lines
                right_lines += [""] * gap_lines
    if not per_line:
        els += ctx.emit_column(left_lines, l_st, left_x, "right", y, adv, r_st, block)
        els += ctx.emit_column(right_lines, r_st, right_x, "left", y, adv, r_st, block)
        cur = y + len(left_lines) * adv
    return els, cur - y + extra


def _grid(ctx, block, y, names, skey="name", columns="auto"):
    st = ctx.style(skey, block)
    if not names:
        return [], 0.0
    lane_w = ctx.lane[1] - ctx.lane[0]
    col_gap = max(ctx.px(ctx.metrics["gutter"]) * 3, ctx.W * 0.03)
    widest = max(ctx.width(n, st) for n in names)
    if columns == "auto":
        fit = int((lane_w * 0.9 + col_gap) // (widest + col_gap)) or 1
        n_cols = max(1, min(fit, 4, len(names)))
        if len(names) <= 3:
            n_cols = 1 if len(names) < 3 else min(n_cols, 3)
    else:
        n_cols = max(1, int(columns))
    rows = int(math.ceil(len(names) / float(n_cols)))
    col_w = min(widest, (lane_w - col_gap * (n_cols - 1)) / n_cols)
    if widest > col_w:
        ctx.warn(block, "Nomi troppo lunghi per %d colonne" % n_cols)
    pitch = col_w + col_gap
    x0 = ctx.axis - (n_cols - 1) * pitch / 2.0
    adv = ctx.m.line_height(st)
    # riempimento per righe (ordine di lettura); ultima riga incompleta centrata
    full, rem = divmod(len(names), n_cols)
    els = []
    for c in range(n_cols):
        col = [names[r * n_cols + c] for r in range(full)]
        if col:
            els += ctx.emit_column(col, st, x0 + c * pitch, "center", y, adv, st, block)
    if rem:
        last = names[full * n_cols:]
        xl = ctx.axis - (rem - 1) * pitch / 2.0
        for i, n in enumerate(last):
            els += ctx.emit_column([n], st, xl + i * pitch, "center", y + full * adv, adv, st, block)
    return els, rows * adv


def _image_rows(ctx, block, y, items, target_h, mode="logo"):
    """Righe di immagini centrate; mode logo = bilanciamento per area ottica."""
    gap = ctx.px(ctx.metrics.get("logo_gap", 60))
    lane_w = ctx.lane[1] - ctx.lane[0]
    sized = []
    for it in items:
        path = resolve_path(ctx.project, it.get("path", ""))
        kind = it.get("kind") or imageinfo.media_kind(path)
        size = imageinfo.image_size(path) if kind == "image" else None
        if size is None:
            aspect = float(it.get("aspect") or (16 / 9.0 if kind == "video" else 2.0))
            if kind == "image" and not os.path.exists(path or ""):
                ctx.warn(block, "File non trovato: %s" % it.get("path"))
        else:
            aspect = size[0] / float(size[1] or 1)
        if mode == "logo":
            area = target_h * target_h * 2.0
            h = math.sqrt(area / aspect)
            h = min(h, target_h * 1.6)
            w = h * aspect
            if w > target_h * 4.2:
                w = target_h * 4.2
                h = w / aspect
        else:
            h = target_h
            w = h * aspect
        s = float(it.get("scale", 1.0))
        w, h = w * s, h * s
        if w > lane_w:
            w, h = lane_w, lane_w / aspect
        sized.append((it, path, kind, w, h))
    per_row = block.get("per_row", "auto")
    rows, row = [], []
    row_w = 0.0
    for entry in sized:
        w = entry[3]
        limit_hit = per_row != "auto" and len(row) >= int(per_row)
        if row and (limit_hit or row_w + gap + w > lane_w):
            rows.append(row)
            row, row_w = [], 0.0
        row.append(entry)
        row_w += (gap if len(row) > 1 else 0) + w
    if row:
        rows.append(row)
    els, cur = [], y
    for ri, r in enumerate(rows):
        rw = sum(e[3] for e in r) + gap * (len(r) - 1)
        rh = max(e[4] for e in r)
        x = ctx.axis - rw / 2
        for it, path, kind, w, h in r:
            els.append({"kind": kind, "path": path, "x": x + w / 2, "y": cur + (rh - h) / 2, "w": w, "h": h,
                        "top": cur + (rh - h) / 2, "bottom": cur + (rh + h) / 2,
                        "loop": bool(it.get("loop", True)), "name": it.get("name", ""),
                        "block": block.get("id")})
            x += w + gap
        cur += rh + (gap * 0.6 if ri < len(rows) - 1 else 0)
    return els, cur - y


# --------------------------------------------------------------------- per tipo
def b_title(ctx, block, y):
    return _stack(ctx, block, y, [(block.get("text", "").split("\n"), "title")])


def b_card(ctx, block, y):
    groups = []
    if block.get("lines"):
        for ln in block["lines"]:
            groups.append(([ln.get("text", "")], ln.get("style", "name")))
    else:
        role = _role_text(ctx, block.get("role", ""))
        if role:
            groups += [([role], "role"), ("gap", ctx.name_advance(block) * 0.15)]
        names = block.get("names") or []
        if names:
            groups.append((names, "name"))
    align = {"lower_third": "left", "upper_third": "left", "left": "left", "right": "right"}.get(
        block.get("position", "center"), "center")
    return _stack(ctx, block, y, groups, align=align)


def b_credit(ctx, block, y):
    role = _role_text(ctx, block.get("role", ""))
    names = block.get("names") or []
    if block.get("team") and len(names) > 1:
        names = [i18n.join_names(names, ctx.lang, team=True)]
    if block.get("layout") == "two_column":
        return _two_column(ctx, block, y, [([role], "role", names, "name")])
    groups = []
    if role:
        groups += [([role], "role"), ("gap", ctx.name_advance(block) * 0.1)]
    groups.append((names, "name"))
    return _stack(ctx, block, y, groups)


def b_list(ctx, block, y, rows=None):
    rows = block.get("rows", []) if rows is None else rows
    head_els, head_h = _stack(ctx, block, y, _heading_groups(ctx, block)) if block.get("heading") else ([], 0)
    y2 = y + head_h
    if block.get("layout") == "stacked":
        groups = []
        for i, r in enumerate(rows):
            role = _role_text(ctx, r.get("role", ""))
            if role:
                groups += [([role], "role")]
            groups.append((list(r.get("names") or []), "name"))
            if i < len(rows) - 1:
                groups.append(("gap", ctx.name_advance(block) * 0.6))
        els, h = _stack(ctx, block, y2, groups)
    else:
        els, h = _two_column(ctx, block, y2, [([_role_text(ctx, r.get("role", ""))], "role",
                                               list(r.get("names") or []), "name") for r in rows])
    return head_els + els, head_h + h


def b_names(ctx, block, y, names=None):
    names = block.get("names", []) if names is None else names
    head_els, head_h = _stack(ctx, block, y, _heading_groups(ctx, block)) if block.get("heading") else ([], 0)
    els, h = _grid(ctx, block, y + head_h, names, "name", block.get("columns", "auto"))
    return head_els + els, head_h + h


def b_cast(ctx, block, y, rows=None):
    rows = block.get("rows", []) if rows is None else rows
    head_els, head_h = _stack(ctx, block, y, _heading_groups(ctx, block)) if block.get("heading") else ([], 0)
    data = []
    for r in rows:
        actor, char = r.get("actor", ""), r.get("character", "")
        if block.get("order") == "character_actor":
            data.append(([char], "character", [actor], "name"))
        else:
            data.append(([actor], "name", [char], "character"))
    els, h = _two_column(ctx, block, y + head_h, data)
    return head_els + els, head_h + h


def b_music(ctx, block, y, cues=None):
    cues = block.get("cues", []) if cues is None else cues
    groups = list(_heading_groups(ctx, block))
    for i, cue in enumerate(cues):
        lines = phrases.music_cue_lines(cue, ctx.lang)
        # raggruppa righe consecutive con lo stesso stile
        cur_style, cur = None, []
        for text, skey in lines:
            if skey != cur_style and cur:
                groups.append((cur, cur_style))
                cur = []
            cur_style = skey
            cur.append(text)
        if cur:
            groups.append((cur, cur_style))
        if i < len(cues) - 1:
            groups.append(("gap", ctx.name_advance(block) * 0.9 * ctx.gap_scale))
    return _stack(ctx, block, y, groups)


def b_agreements(ctx, block, y, entries=None):
    entries = block.get("entries", []) if entries is None else entries
    kind = block.get("kind", "location")
    heading = block.get("heading") or {"location": "h:locations", "rental": "h:rentals", "archive": "h:archive",
                                       "product": "h:products", "artwork": ""}.get(kind, "")
    b = dict(block, heading=heading)
    lines = [phrases.agreement_line(kind, e, ctx.lang) for e in entries]
    if int(block.get("columns", 1) or 1) > 1:
        return b_names(ctx, b, y, names=lines)
    groups = list(_heading_groups(ctx, b))
    simple = all(phrases.agreement_line(kind, e, ctx.lang) == e.get("name") for e in entries)
    groups.append((lines, "name" if simple else "small"))
    return _stack(ctx, b, y, groups)


def b_logos(ctx, block, y):
    cap = block.get("caption", "")
    cap = phrases.heading_text(cap, ctx.lang) if cap else ""
    els, h = [], 0.0
    if cap:
        els, h = _stack(ctx, block, y, [([cap], "role")])
        h += ctx.name_advance(block) * 0.6
    th = ctx.px(float(block.get("height") or ctx.metrics.get("logo_height", 90)))
    iels, ih = _image_rows(ctx, block, y + h, block.get("items", []), th, mode="logo")
    return els + iels, h + ih


def b_legal(ctx, block, y):
    groups = []
    texts = []
    if block.get("text"):
        texts.append(block["text"])
    for it in block.get("items", []):
        texts.append(phrases.legal_text(it, ctx.lang, ctx.project["meta"]))
    for i, t in enumerate(texts):
        groups.append(([t], "legal"))
        if i < len(texts) - 1:
            groups.append(("gap", ctx.name_advance(block) * 0.6))
    return _stack(ctx, block, y, groups)


def b_media(ctx, block, y):
    if block.get("lane") == "side" and ctx.side_lane:
        return [], 0.0  # posizionati dopo, nella corsia laterale
    th = ctx.px(float(block.get("height") or ctx.metrics.get("media_height", 300)))
    els, h = _image_rows(ctx, block, y, block.get("items", []), th, mode="media")
    caps = [it.get("caption") for it in block.get("items", []) if it.get("caption")]
    if caps:
        cels, ch = _stack(ctx, block, y + h + ctx.name_advance(block) * 0.3, [(caps, "small")])
        els += cels
        h += ch + ctx.name_advance(block) * 0.3
    return els, h


def b_text(ctx, block, y):
    return _stack(ctx, block, y, [(block.get("text", "").split("\n"), block.get("style_key", "small"))],
                  align=block.get("align", "center"))


def b_spacer(ctx, block, y):
    return [], float(block.get("lines", 2.0)) * ctx.name_advance(block) * ctx.gap_scale


BUILDERS = {
    "title": b_title, "card": b_card, "credit": b_credit, "list": b_list, "names": b_names,
    "cast": b_cast, "music": b_music, "agreements": b_agreements, "logos": b_logos,
    "legal": b_legal, "media": b_media, "text": b_text, "spacer": b_spacer,
}

# blocchi i cui elementi possono essere divisi su piu' cartelli: (campo, builder)
PAGINABLE = {"list": ("rows", b_list), "cast": ("rows", b_cast), "names": ("names", b_names),
             "music": ("cues", b_music), "agreements": ("entries", b_agreements)}


def _shift(els, dy):
    for e in els:
        for k in ("baseline", "top", "bottom", "center_y", "y"):
            if k in e:
                e[k] += dy
    return els


# ======================================================================= crawl
def layout_crawl(project, sequence, measurer=None, gap_scale=1.0):
    ctx = Ctx(project, sequence, measurer, gap_scale)
    els, holds, y = [], [], 0.0
    side_items = []
    blocks = [b for b in sequence["blocks"] if b.get("enabled", True)]
    na = ctx.name_advance()
    gaps_total = 0.0
    block_spans = []
    for i, b in enumerate(blocks):
        if i > 0:
            before = b.get("spacing_before")
            prev_after = blocks[i - 1].get("spacing_after")
            gap_lines = before if before is not None else (
                prev_after if prev_after is not None else ctx.metrics["block_gap"])
            gap = float(gap_lines) * na * gap_scale
            y += gap
            gaps_total += gap
        if b["type"] == "media" and b.get("lane") == "side" and ctx.side_lane:
            side_items.extend(b.get("items", []))
            continue
        bels, h = BUILDERS[b["type"]](ctx, b, y)
        els.extend(bels)
        block_spans.append((b.get("id"), y, y + h, b["type"]))
        if float(b.get("hold_s") or 0) > 0:
            holds.append({"y": y + h / 2.0, "seconds": float(b["hold_s"]), "block": b.get("id")})
        y += h
    content_h = y
    if side_items:
        els.extend(_place_side(ctx, side_items, content_h))
    _check_bounds(ctx, els)
    return {"kind": "crawl", "width": ctx.W, "height": ctx.H, "elements": els, "content_height": content_h,
            "holds": holds, "gaps_total": gaps_total, "blocks": block_spans, "warnings": ctx.warnings,
            "missing_fonts": sorted(ctx.m.missing), "safe": ctx.safe}


def _place_side(ctx, items, content_h):
    lane_w = ctx.side_lane[1] - ctx.side_lane[0]
    cx = (ctx.side_lane[0] + ctx.side_lane[1]) / 2.0
    n = len(items)
    slot = max(content_h, ctx.H) / n
    out = []
    for i, it in enumerate(items):
        path = resolve_path(ctx.project, it.get("path", ""))
        kind = it.get("kind") or imageinfo.media_kind(path)
        size = imageinfo.image_size(path) if kind == "image" else None
        aspect = (size[0] / float(size[1])) if size else float(it.get("aspect") or 16 / 9.0)
        w = lane_w * 0.88 * float(it.get("scale", 1.0))
        h = w / aspect
        if h > min(slot * 0.85, ctx.H * 0.6):
            h = min(slot * 0.85, ctx.H * 0.6)
            w = h * aspect
        top = (i + 0.5) * slot - h / 2
        out.append({"kind": kind, "path": path, "x": cx, "y": top, "w": w, "h": h, "top": top, "bottom": top + h,
                    "loop": bool(it.get("loop", True)), "name": it.get("name", ""), "block": "side_media"})
    return out


def _check_bounds(ctx, els):
    sl, _st, sr, _sb = ctx.safe
    for e in els:
        if e["kind"] != "text":
            continue
        if e["anchor"] == "center":
            l, r = e["x"] - e["width"] / 2, e["x"] + e["width"] / 2
        elif e["anchor"] == "left":
            l, r = e["x"], e["x"] + e["width"]
        else:
            l, r = e["x"] - e["width"], e["x"]
        if l < sl - 0.5 or r > sr + 0.5:
            ctx.warnings.append({"block": e["block"], "message": "Testo fuori dalla title-safe: %s" % e["lines"][0][:60]})


# ======================================================================= cards
def layout_cards(project, sequence, measurer=None):
    """Ogni blocco diventa uno o piu' cartelli (paginazione automatica se non entra)."""
    ctx = Ctx(project, sequence, measurer)
    sl, st, sr, sb = ctx.safe
    max_h = (sb - st) * 0.92
    cards = []
    for b in sequence["blocks"]:
        if not b.get("enabled", True) or b["type"] == "spacer":
            continue
        pages = _paginate(ctx, b, max_h)
        for els, h, ids in pages:
            pos = b.get("position", "center")
            if pos == "lower_third":
                top = sb - h - (sb - st) * 0.04
            elif pos == "upper_third":
                top = st + (sb - st) * 0.04
            else:
                top = st + ((sb - st) - h) / 2.0
            _shift(els, top)
            if cards and not b.get("page_break") and b.get("merge_with_previous"):
                cards[-1]["elements"].extend(els)
                cards[-1]["blocks"].append(b.get("id"))
                continue
            cards.append({"elements": els, "height": h, "blocks": ids, "hold_s": float(b.get("hold_s") or 0),
                          "duration_s": b.get("duration_s")})
    for c in cards:
        _check_bounds(ctx, c["elements"])
    return {"kind": "cards", "width": ctx.W, "height": ctx.H, "cards": cards, "warnings": ctx.warnings,
            "missing_fonts": sorted(ctx.m.missing), "safe": ctx.safe}


def _paginate(ctx, block, max_h):
    builder = BUILDERS[block["type"]]
    els, h = builder(ctx, block, 0.0)
    if h <= max_h or block["type"] not in PAGINABLE:
        if h > max_h:
            ctx.warn(block, "Il cartello supera l'altezza utile e non e' divisibile")
        return [(els, h, [block.get("id")])]
    field, fn = PAGINABLE[block["type"]]
    items = list(block.get(field, []))
    pages, start = [], 0
    while start < len(items):
        end = start + 1
        best = fn(ctx, block, 0.0, items[start:end])
        while end < len(items):
            trial = fn(ctx, block, 0.0, items[start:end + 1])
            if trial[1] > max_h:
                break
            best, end = trial, end + 1
        pages.append((best[0], best[1], [block.get("id")]))
        start = end
    return pages


def layout_sequence(project, sequence, measurer=None, gap_scale=1.0):
    if sequence.get("kind") == "cards":
        return layout_cards(project, sequence, measurer)
    return layout_crawl(project, sequence, measurer, gap_scale)
