"""Two-window film map rendered with Qt's supported rich-text tables.

The discontinuous scale never changes source positions. Blocks keep exact bounds;
labels are shortened to fit, with full names in the element list and tooltips.
"""

import html
from urllib.parse import quote
from . import workspace


def timecode(frame, fps, drop=False):
    n = int(round(fps))
    frame = max(0, int(frame))
    if drop:
        d = 2 if n == 30 else 4 if n == 60 else 0
        if not d:
            raise ValueError("Drop-frame requires 29.97 or 59.94 fps")
        per_minute, per_ten = n * 60 - d, n * 600 - d * 9
        tens, rem = divmod(frame, per_ten)
        frame += d * 9 * tens + d * max(0, (rem - d) // per_minute)
    h, rem = divmod(frame, n * 3600)
    m, rem = divmod(rem, n * 60)
    s, f = divmod(rem, n)
    return "%02d:%02d:%02d%s%02d" % (h, m, s, ";" if drop else ":", f)


def windows(start, film_start, film_end, blocks, fps, full=False):
    end = max(film_end + int(15 * fps), max((b["end"] for b in blocks), default=film_end))
    start = min(start, min((b["start"] for b in blocks), default=start))
    if full:
        return [(start, max(start + 1, end))]
    left = [b for b in blocks if b.get("zone") in ("opening", "head")]
    right = [b for b in blocks if b.get("zone") in ("closing", "crawl")]
    left_end = max(film_start + int(30 * fps), max((b["end"] + int(3 * fps) for b in left), default=film_start))
    right_start = min(film_end - int(30 * fps), min((b["start"] - int(3 * fps) for b in right), default=film_end))
    if left_end >= right_start:
        return [(start, max(start + 1, end))]
    return [(start, left_end), (right_start, end)]


def _cells(a, b, blocks, film_start, film_end, film=False):
    boundaries = {a, b}
    if film:
        boundaries.update(x for x in (film_start, film_end) if a < x < b)
    else:
        for block in blocks:
            boundaries.update(x for x in (block["start"], block["end"]) if a < x < b)
    points = sorted(boundaries)
    cells = []
    for x, y in zip(points, points[1:]):
        percent = 100.0 * (y - x) / (b - a)
        color, text = "#20252e", "&nbsp;"
        if film:
            if x < film_start:
                color, text = "#493d2a", "LEADER" if percent > 10 else "&nbsp;"
            elif x < film_end:
                color, text = "#34516a", "FILM" if percent > 8 else "&nbsp;"
        else:
            active = [block for block in blocks if block["start"] < y and block["end"] > x]
            if active:
                block = active[0]
                _label, color = workspace.status_label(block.get("status", "new"))
                label = block.get("label", "Titolo")
                if len(active) > 1:
                    label = "%d titoli" % len(active)
                available = max(1, int(percent * 0.55))
                short = label if len(label) <= available else label[:max(1, available - 1)] + "…"
                href = "drfc:section:" + quote(block["id"], safe="")
                text = '<a href="%s" title="%s" style="color:#101319;text-decoration:none;">%s</a>' % (
                    html.escape(href, quote=True), html.escape(label, quote=True), html.escape(short))
        cells.append('<td width="%.3f%%" bgcolor="%s" align="center" style="font-size:10px;color:#d8e1ec;">%s</td>' % (percent, color, text))
    return '<table width="100%" cellspacing="2" cellpadding="5"><tr>' + "".join(cells) + "</tr></table>"


def render(start, film_start, film_end, blocks, fps, full=False, drop=False, indicative=False):
    ranges = windows(start, film_start, film_end, blocks, fps, full)
    columns = []
    for a, b in ranges:
        ruler = '<table width="100%%"><tr><td style="color:#94a3b7;font-size:10px;">%s</td><td align="right" style="color:#94a3b7;font-size:10px;">%s</td></tr></table>' % (timecode(a, fps, drop), timecode(b, fps, drop))
        section = ruler + _cells(a, b, blocks, film_start, film_end) + _cells(a, b, [], film_start, film_end, film=True)
        columns.append('<td width="%s" valign="top">%s</td>' % ("48%" if len(ranges) == 2 else "100%", section))
    if len(columns) == 2:
        omitted = timecode(ranges[0][1], fps, drop) + " → " + timecode(ranges[1][0], fps, drop)
        columns.insert(1, '<td width="4%%" align="center" valign="middle"><a href="drfc:full" title="%s" style="color:#c6d2e4;text-decoration:none;font-size:20px;">//</a></td>' % html.escape(omitted))
    note = "BOZZA · POSIZIONI INDICATIVE" if indicative else "POSIZIONI DELLA TIMELINE"
    return '<html><body><table width="100%" cellspacing="0" cellpadding="0"><tr><td width="45" valign="middle" style="color:#94a3b7;font-size:10px;">TC<br><br>V2<br><br>V1</td>' + "".join(columns) + '</tr></table><p style="color:#7f8da1;font-size:9px;margin:0;">%s · <a href="drfc:full" style="color:#a7b8d0;">%s</a></p></body></html>' % (note, "Compatta apertura e coda" if full else "Mostra tutto il film")
