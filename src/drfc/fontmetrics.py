"""Metriche dei font senza dipendenze: parser minimale TrueType/OpenType (anche .ttc).

Serve al motore di layout per misurare la larghezza delle righe (auto-adattamento,
avvisi di uscita dalla safe area, colonne) e l'interlinea naturale del font, cosi' le
posizioni calcolate coincidono con il rendering di Text+ in Fusion.

Se un font non viene trovato si usa una stima (0.5 em per carattere): il layout resta
valido e il validatore segnala il font mancante.
"""

import json
import os
import struct
import sys

FALLBACK_ADVANCE = 0.5      # em medio per carattere quando il font non e' disponibile
FALLBACK_LINE_HEIGHT = 1.2  # (ascender - descender + lineGap) / unitsPerEm tipico


class FontInfo(object):
    def __init__(self, path, index=0):
        self.path = path
        self.index = index
        self.family = ""
        self.subfamily = ""
        self.typo_family = ""
        self.typo_subfamily = ""
        self.full_name = ""
        self.units_per_em = 1000
        self.ascender = 800
        self.descender = -200
        self.line_gap = 0
        self.advances = []
        self.cmap = {}
        self._loaded = False

    # ---------------------------------------------------------------- parsing
    def _tables(self, data):
        base = 0
        if data[:4] == b"ttcf":
            n = struct.unpack(">I", data[8:12])[0]
            if self.index >= n:
                raise ValueError("indice TTC fuori range")
            base = struct.unpack(">I", data[12 + 4 * self.index:16 + 4 * self.index])[0]
        num = struct.unpack(">H", data[base + 4:base + 6])[0]
        tables = {}
        for i in range(num):
            off = base + 12 + 16 * i
            tag = data[off:off + 4].decode("latin-1")
            t_off, t_len = struct.unpack(">II", data[off + 8:off + 16])
            tables[tag] = (t_off, t_len)
        return tables

    def read_names(self, data=None):
        if data is None:
            with open(self.path, "rb") as f:
                data = f.read()
        tables = self._tables(data)
        if "name" not in tables:
            return
        off, _ = tables["name"]
        _fmt, count, str_off = struct.unpack(">HHH", data[off:off + 6])
        found = {}
        for i in range(count):
            rec = off + 6 + 12 * i
            pid, eid, lid, nid, length, noff = struct.unpack(">HHHHHH", data[rec:rec + 12])
            if nid not in (1, 2, 4, 16, 17):
                continue
            raw = data[off + str_off + noff:off + str_off + noff + length]
            if pid == 3 or pid == 0:
                try:
                    s = raw.decode("utf-16-be")
                except UnicodeDecodeError:
                    continue
                english = (pid == 0) or (lid in (0x0409, 0x0809))
            elif pid == 1:
                s = raw.decode("mac_roman", "replace")
                english = lid == 0
            else:
                continue
            prev = found.get(nid)
            if prev is None or (english and not prev[1]):
                found[nid] = (s, english)
        self.family = found.get(1, ("", 0))[0]
        self.subfamily = found.get(2, ("", 0))[0]
        self.full_name = found.get(4, ("", 0))[0]
        self.typo_family = found.get(16, (self.family, 0))[0]
        self.typo_subfamily = found.get(17, (self.subfamily, 0))[0]

    def load(self):
        if self._loaded:
            return self
        with open(self.path, "rb") as f:
            data = f.read()
        tables = self._tables(data)
        self.read_names(data)
        off, _ = tables["head"]
        self.units_per_em = struct.unpack(">H", data[off + 18:off + 20])[0] or 1000
        off, _ = tables["hhea"]
        self.ascender, self.descender, self.line_gap = struct.unpack(">hhh", data[off + 4:off + 10])
        n_hmetrics = struct.unpack(">H", data[off + 34:off + 36])[0]
        off, _ = tables["hmtx"]
        self.advances = [struct.unpack(">H", data[off + 4 * i:off + 4 * i + 2])[0] for i in range(n_hmetrics)]
        self.cmap = self._parse_cmap(data, tables["cmap"][0])
        self.cap_height = None
        if "OS/2" in tables:
            off, length = tables["OS/2"]
            version = struct.unpack(">H", data[off:off + 2])[0]
            if version >= 2 and length >= 90:
                self.cap_height = struct.unpack(">h", data[off + 88:off + 90])[0]
        self._loaded = True
        return self

    @staticmethod
    def _parse_cmap(data, off):
        num = struct.unpack(">H", data[off + 2:off + 4])[0]
        best = None
        for i in range(num):
            pid, eid, sub = struct.unpack(">HHI", data[off + 4 + 8 * i:off + 12 + 8 * i])
            fmt = struct.unpack(">H", data[off + sub:off + sub + 2])[0]
            score = {12: 3, 4: 2}.get(fmt, 0) if (pid == 3 or pid == 0) else 0
            if score and (best is None or score > best[0]):
                best = (score, off + sub, fmt)
        cmap = {}
        if best is None:
            return cmap
        _, so, fmt = best
        if fmt == 4:
            seg_x2 = struct.unpack(">H", data[so + 6:so + 8])[0]
            segs = seg_x2 // 2
            ends = struct.unpack(">%dH" % segs, data[so + 14:so + 14 + seg_x2])
            starts_off = so + 16 + seg_x2
            starts = struct.unpack(">%dH" % segs, data[starts_off:starts_off + seg_x2])
            deltas = struct.unpack(">%dh" % segs, data[starts_off + seg_x2:starts_off + 2 * seg_x2])
            ro_off = starts_off + 2 * seg_x2
            ranges = struct.unpack(">%dH" % segs, data[ro_off:ro_off + seg_x2])
            for s in range(segs):
                start, end, delta, ro = starts[s], ends[s], deltas[s], ranges[s]
                if start == 0xFFFF:
                    continue
                for c in range(start, end + 1):
                    if ro == 0:
                        g = (c + delta) & 0xFFFF
                    else:
                        gi = ro_off + 2 * s + ro + 2 * (c - start)
                        g = struct.unpack(">H", data[gi:gi + 2])[0]
                        if g:
                            g = (g + delta) & 0xFFFF
                    if g:
                        cmap[c] = g
        elif fmt == 12:
            n_groups = struct.unpack(">I", data[so + 12:so + 16])[0]
            for gidx in range(n_groups):
                g_off = so + 16 + 12 * gidx
                start, end, glyph = struct.unpack(">III", data[g_off:g_off + 12])
                if end - start > 0x30000:
                    continue
                for c in range(start, end + 1):
                    cmap[c] = glyph + (c - start)
        return cmap

    # ---------------------------------------------------------------- misure
    def advance_em(self, ch):
        g = self.cmap.get(ord(ch), 0)
        if not self.advances:
            return FALLBACK_ADVANCE
        a = self.advances[g] if g < len(self.advances) else self.advances[-1]
        return a / float(self.units_per_em)

    def line_height_em(self):
        return (self.ascender - self.descender + self.line_gap) / float(self.units_per_em)

    def text_width_em(self, text):
        return sum(self.advance_em(c) for c in text)


# --------------------------------------------------------------------- indice
def font_dirs(extra=None):
    dirs = list(extra or [])
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs += [os.path.join(windir, "Fonts"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    elif sys.platform == "darwin":
        dirs += ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                 os.path.join(home, "Library", "Fonts")]
    else:
        dirs += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.join(home, ".fonts"),
                 os.path.join(home, ".local", "share", "fonts")]
    return [d for d in dirs if d and os.path.isdir(d)]


def _norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


_STYLE_ALIASES = {"regular": ("regular", "book", "roman", "normal", ""), "italic": ("italic", "oblique")}


class FontIndex(object):
    """Indice famiglia/stile -> file. Viene salvato in cache per non rileggere i font."""

    def __init__(self, extra_dirs=None, cache_path=None):
        self.extra_dirs = extra_dirs or []
        self.cache_path = cache_path
        self.entries = None
        self._fonts = {}

    def _scan(self):
        cache = {}
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    cache = json.load(f)
            except (ValueError, IOError, OSError):
                cache = {}
        entries, new_cache = [], {}
        for d in font_dirs(self.extra_dirs):
            for root, _dirs, files in os.walk(d):
                for fn in files:
                    if not fn.lower().endswith((".ttf", ".otf", ".ttc")):
                        continue
                    path = os.path.join(root, fn)
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    hit = cache.get(path)
                    if hit and hit.get("mtime") == mtime:
                        recs = hit["recs"]
                    else:
                        recs = self._read_records(path)
                    new_cache[path] = {"mtime": mtime, "recs": recs}
                    entries.extend(recs)
        if self.cache_path:
            try:
                d = os.path.dirname(self.cache_path)
                if d and not os.path.isdir(d):
                    os.makedirs(d)
                with open(self.cache_path, "w", encoding="utf-8") as f:
                    json.dump(new_cache, f)
            except (IOError, OSError):
                pass
        self.entries = entries

    @staticmethod
    def _read_records(path):
        recs = []
        try:
            with open(path, "rb") as f:
                head = f.read(12)
            count = struct.unpack(">I", head[8:12])[0] if head[:4] == b"ttcf" else 1
            for i in range(min(count, 32)):
                fi = FontInfo(path, i)
                fi.read_names()
                recs.append({"path": path, "index": i, "family": fi.family, "sub": fi.subfamily,
                             "tfamily": fi.typo_family, "tsub": fi.typo_subfamily, "full": fi.full_name})
        except Exception:  # font corrotto o formato non supportato: ignorato
            pass
        return recs

    def find(self, family, style="Regular"):
        """Cerca il file migliore per (famiglia, stile) come li mostra Text+."""
        if self.entries is None:
            self._scan()
        fam, sty = _norm(family), _norm(style)
        best, best_score = None, 0
        for e in self.entries:
            for f_name, s_name in ((e["tfamily"], e["tsub"]), (e["family"], e["sub"])):
                if _norm(f_name) != fam:
                    continue
                s = _norm(s_name)
                if s == sty:
                    score = 3
                elif sty in _STYLE_ALIASES.get("regular", ()) and s in _STYLE_ALIASES["regular"]:
                    score = 2
                else:
                    score = 1
                if score > best_score:
                    best, best_score = e, score
            if best_score < 3 and _norm(e["full"]) == fam + sty:
                best, best_score = e, 3
        return best, best_score

    def font(self, family, style="Regular"):
        key = (family, style)
        if key not in self._fonts:
            rec, score = self.find(family, style)
            fi = None
            if rec:
                try:
                    fi = FontInfo(rec["path"], rec["index"]).load()
                except Exception:
                    fi = None
            self._fonts[key] = (fi, score)
        return self._fonts[key]


def default_cache_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", base)
    return os.path.join(base, "DR-FilmCredits", "fontindex.json")


class Measurer(object):
    """Misura testi in pixel per uno stile risolto (family, style, size_px, tracking)."""

    def __init__(self, index=None):
        self.index = index if index is not None else FontIndex(cache_path=default_cache_path())
        self.missing = set()

    def _font(self, st):
        fi, _score = self.index.font(st["family"], st.get("style", "Regular"))
        if fi is None:
            self.missing.add("%s %s" % (st["family"], st.get("style", "")))
        return fi

    def width(self, text, st):
        fi = self._font(st)
        em = st["size_px"]
        base = fi.text_width_em(text) if fi else FALLBACK_ADVANCE * len(text)
        extra = (st.get("tracking", 1.0) - 1.0) * max(len(text) - 1, 0)
        return (base + extra) * em

    def natural_line_height(self, st):
        """Interlinea naturale del font (LineSpacing = 1.0 in Text+)."""
        fi = self._font(st)
        ratio = fi.line_height_em() if fi else FALLBACK_LINE_HEIGHT
        return ratio * st["size_px"]

    def line_height(self, st):
        return self.natural_line_height(st) * st.get("line_spacing", 1.0)

    def vmetrics(self, st):
        """(ascender, descender) in pixel; descender negativo."""
        fi = self._font(st)
        if fi is None:
            return 0.8 * st["size_px"], -0.2 * st["size_px"]
        upm = float(fi.units_per_em)
        return fi.ascender / upm * st["size_px"], fi.descender / upm * st["size_px"]
