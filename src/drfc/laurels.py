"""Allori dei festival.

- generate(): disegna corone d'alloro (PNG con trasparenza, bianche e nere, piu' stili)
  con un piccolo rasterizzatore puro Python (supersampling 3x3): nessuna dipendenza.
- laurel_lines(): testo standard dell'alloro (stato, festival, sezione, anno) da
  data/festivals.json, nella lingua del festival.
- Se il festival fornisce l'alloro ufficiale (item["path"]) si usa quello, senza testo.

    python -m drfc.laurels      rigenera i PNG in data/laurels/
"""

import json
import math
import os
import struct
import zlib

from . import DATA_DIR

LAUREL_DIR = os.path.join(DATA_DIR, "laurels")
CANVAS = (1000, 800)  # proporzioni dell'alloro (unita' di disegno)
CENTER = (500.0, 410.0)
STYLES = {
    "classic": {"leaves": 11, "leaf_a": 50.0, "leaf_b": 17.0, "radius": 330.0, "stem": 6.0, "spread": 36.0},
    "slim": {"leaves": 15, "leaf_a": 40.0, "leaf_b": 11.0, "radius": 335.0, "stem": 4.5, "spread": 30.0},
    "bold": {"leaves": 9, "leaf_a": 62.0, "leaf_b": 23.0, "radius": 320.0, "stem": 8.0, "spread": 40.0},
}


# ------------------------------------------------------------------ rasterizzazione
class Mask(object):
    def __init__(self, w, h, ss=3):
        self.w, self.h, self.ss = w, h, ss
        self.W, self.H = w * ss, h * ss
        self.bits = bytearray(self.W * self.H)

    def ellipse(self, cx, cy, a, b, angle):
        """Ellisse ruotata (coordinate in pixel di uscita)."""
        ss = self.ss
        cx, cy, a, b = cx * ss, cy * ss, a * ss, b * ss
        ca, sa = math.cos(angle), math.sin(angle)
        r = max(a, b)
        x0, x1 = max(0, int(cx - r)), min(self.W - 1, int(cx + r) + 1)
        y0, y1 = max(0, int(cy - r)), min(self.H - 1, int(cy + r) + 1)
        ia2, ib2 = 1.0 / (a * a), 1.0 / (b * b)
        bits, W = self.bits, self.W
        for y in range(y0, y1 + 1):
            dy = y + 0.5 - cy
            row = y * W
            for x in range(x0, x1 + 1):
                dx = x + 0.5 - cx
                u = dx * ca + dy * sa
                v = -dx * sa + dy * ca
                if u * u * ia2 + v * v * ib2 <= 1.0:
                    bits[row + x] = 1

    def disc(self, cx, cy, r):
        self.ellipse(cx, cy, r, r, 0.0)

    def alpha(self):
        ss, W = self.ss, self.W
        n = float(ss * ss)
        out = bytearray(self.w * self.h)
        bits = self.bits
        for y in range(self.h):
            rows = [bits[(y * ss + k) * W:(y * ss + k + 1) * W] for k in range(ss)]
            for x in range(self.w):
                c = 0
                xs = x * ss
                for r in rows:
                    c += sum(r[xs:xs + ss])
                out[y * self.w + x] = int(round(c / n * 255))
        return out


def write_png(path, w, h, alpha, rgb):
    raw = bytearray()
    r, g, b = rgb
    for y in range(h):
        raw.append(0)
        row = alpha[y * w:(y + 1) * w]
        for a in row:
            raw += bytes((r, g, b, a))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def draw(style="classic", width=750):
    """Alpha della corona: due rami che salgono dal basso e si aprono in alto."""
    p = STYLES[style]
    k = width / float(CANVAS[0])
    w, h = width, int(round(CANVAS[1] * k))
    m = Mask(w, h)
    cx, cy = CENTER[0] * k, CENTER[1] * k
    R = p["radius"] * k
    for side in (-1, 1):
        # angolo misurato dal basso: 0 = punto piu' basso, cresce salendo sul lato
        start, end = math.radians(14), math.radians(150)
        steps = 160
        for i in range(steps + 1):
            t = start + (end - start) * i / steps
            x = cx + side * R * math.sin(t)
            y = cy + R * math.cos(t)
            m.disc(x, y, p["stem"] * k * (1.0 - 0.45 * i / steps))
        n = p["leaves"]
        for j in range(n):
            f = j / float(n - 1)
            t = start + (end - start) * (0.04 + 0.96 * f)
            x = cx + side * R * math.sin(t)
            y = cy + R * math.cos(t)
            # tangente nella direzione di crescita (verso l'alto)
            tx, ty = side * math.cos(t), -math.sin(t)
            tang = math.atan2(ty, tx)
            scale = 1.0 - 0.38 * f
            a, b = p["leaf_a"] * k * scale, p["leaf_b"] * k * scale
            for out in (1, -1):
                ang = tang + out * side * math.radians(p["spread"])
                lx = x + math.cos(ang) * a * 0.92
                ly = y + math.sin(ang) * a * 0.92
                m.ellipse(lx, ly, a, b, ang)
        # foglia apicale
        t = end
        x, y = cx + side * R * math.sin(t), cy + R * math.cos(t)
        tang = math.atan2(-math.sin(t), side * math.cos(t))
        a = p["leaf_a"] * k * 0.6
        m.ellipse(x + math.cos(tang) * a * 0.9, y + math.sin(tang) * a * 0.9, a, p["leaf_b"] * k * 0.55, tang)
    return w, h, m.alpha()


def laurel_path(style="classic", light_bg=False):
    color = "black" if light_bg else "white"
    return os.path.join(LAUREL_DIR, "laurel_%s_%s.png" % (style, color))


def generate(out_dir=LAUREL_DIR, width=750):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for style in STYLES:
        w, h, a = draw(style, width)
        for name, rgb in (("white", (255, 255, 255)), ("black", (17, 17, 17))):
            p = os.path.join(out_dir, "laurel_%s_%s.png" % (style, name))
            write_png(p, w, h, a, rgb)
            paths.append(p)
    return paths


# ------------------------------------------------------------------ testi
_fest = None


def festivals():
    global _fest
    if _fest is None:
        with open(os.path.join(DATA_DIR, "festivals.json"), encoding="utf-8") as f:
            _fest = json.load(f)
    return _fest


def laurel_lines(item, default_lang="en"):
    """Righe di testo dell'alloro: [(testo, ruolo)] con ruolo in status/festival/section/year."""
    if item.get("lines"):
        return [(l, "festival" if i == 1 else "status" if i == 0 else "section") for i, l in enumerate(item["lines"])]
    data = festivals()
    fest = data["festivals"].get(item.get("festival", ""))
    lang = item.get("lang") or (fest["laurel_lang"] if fest else default_lang)
    out = []
    if item.get("award"):
        out.append((item["award"], "status"))
    else:
        st = data["status"].get(item.get("status", "official_selection"), {})
        out.append((st.get(lang) or st.get("en") or item.get("status", ""), "status"))
    out.append(((fest["short"] if fest else item.get("festival_name", item.get("festival", ""))), "festival"))
    sec = item.get("section")
    if sec:
        text = (fest or {}).get("sections", {}).get(sec, sec)
        year = item.get("year")
        edition = item.get("edition")
        if edition is None and year and item.get("festival") == "venezia":
            edition = int(year) - 1943  # 82a Mostra = 2025
        out.append((text.replace("{edition}", str(edition or "")).strip(" –"), "section"))
    if item.get("year"):
        out.append((str(item["year"]), "year"))
    return out


if __name__ == "__main__":
    for p in generate():
        print(p)
