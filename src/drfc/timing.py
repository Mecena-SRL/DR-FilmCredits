"""Velocita', durata e tempi dei titoli.

Crawl (rullo):
  - la velocita' e' sempre un numero INTERO di pixel per fotogramma: ogni riga si sposta
    della stessa quantita' a ogni frame, niente judder/strobing sui bordi sottili;
  - i preset lento/normale/veloce sono definiti come "secondi per attraversare lo schermo"
    e quindi si adattano a risoluzione e frame rate;
  - "Adatta a durata" (fit=speed): sceglie la velocita' intera piu' bassa che sta nella
    durata richiesta e recupera i frame residui nella pausa finale (durata esatta);
  - "Adatta spaziatura" (fit=spacing): mantiene la velocita' del preset e allarga/stringe
    gli spazi tra i blocchi finche' la durata coincide (gli elementi si spostano).
  - pause (hold) su blocchi specifici: il rullo si ferma quando il blocco e' al centro.

Cartelli: durata dal numero di parole/righe (velocita' di lettura) * ritmo scelto.
"""

import math
import re

from . import layout as layout_mod

# secondi impiegati da una riga per attraversare l'intera altezza dello schermo
SPEED_SCREEN_SECONDS = {"slow": 15.0, "normal": 11.0, "fast": 8.0}
CARD_PACE = {"slow": 1.3, "normal": 1.0, "fast": 0.75}
CARD_MIN_S, CARD_MAX_S = 2.5, 8.0
GAP_SCALE_LIMITS = (0.5, 2.0)


def preset_speed(height, fps, speed):
    secs = SPEED_SCREEN_SECONDS.get(speed, SPEED_SCREEN_SECONDS["normal"])
    return max(1, int(round(height / (secs * fps))))


def _end_travel(lay, end_mode):
    H = lay["height"]
    if end_mode == "hold_last" and lay["blocks"]:
        # si ferma centrando l'ultimo blocco, o il gruppo finale loghi + diciture se sta nello schermo
        spans = lay["blocks"]
        top, bottom = spans[-1][1], spans[-1][2]
        for sp in reversed(spans[-3:]):
            if sp[3] == "logos" and bottom - sp[1] <= H * 0.8:
                top = sp[1]
                break
        return (top + bottom) / 2.0 + H / 2.0
    return lay["content_height"] + H


def _hold_marks(lay, v, fps):
    """Converte le pause in (frame di movimento in cui inizia, durata in frame)."""
    marks = []
    H = lay["height"]
    for h in sorted(lay["holds"], key=lambda x: x["y"]):
        s = h["y"] + H / 2.0
        marks.append((int(round(s / float(v))), int(round(h["seconds"] * fps)), h["block"]))
    return marks


def crawl_timeline(project, lay, v, pad_end_frames=0):
    t = project["timing"]
    fps = float(project["format"]["fps"])
    lead_in = int(round(float(t.get("lead_in_s") or 0) * fps))
    lead_out = int(round(float(t.get("lead_out_s") or 0) * fps))
    end_mode = t.get("end_mode", "scroll_out")
    travel = _end_travel(lay, end_mode)
    move_frames = int(math.ceil(travel / float(v)))
    marks = _hold_marks(lay, v, fps)
    holds, acc = [], 0
    for m, frames, bid in marks:
        if m >= move_frames:
            continue
        holds.append({"start": lead_in + m + acc, "frames": frames, "block": bid, "move_frame": m})
        acc += frames
    end_hold = int(round(float(t.get("hold_last_s") or 0) * fps)) if end_mode == "hold_last" else 0
    end_hold += pad_end_frames
    total = lead_in + move_frames + acc + end_hold + lead_out
    return {"kind": "crawl", "fps": fps, "speed_px": v, "lead_in": lead_in, "lead_out": lead_out,
            "move_frames": move_frames, "travel_px": travel, "holds": holds, "end_hold": end_hold,
            "total_frames": total, "end_mode": end_mode}


def scroll_at(tl, frame):
    """Spostamento in pixel del rullo al frame `frame` (0 = primo frame del clip)."""
    x = frame - tl["lead_in"]
    if x <= 0:
        return 0.0
    m = float(x)
    for h in tl["holds"]:
        a = h["start"] - tl["lead_in"]
        m -= min(max(x - a, 0), h["frames"])
    return min(m * tl["speed_px"], tl["travel_px"])


def solve_crawl(project, sequence, measurer=None):
    """Calcola layout + timeline del crawl applicando velocita' e modalita' di adattamento.
    Ritorna (layout, timeline, note)."""
    t = project["timing"]
    fps = float(project["format"]["fps"])
    H = float(project["format"]["height"])
    notes = []
    if t.get("speed") == "custom" and t.get("px_per_frame"):
        v = float(t["px_per_frame"])
        if not t.get("allow_fractional_speed"):
            v = max(1, int(round(v)))
    else:
        v = preset_speed(H, fps, t.get("speed", "normal"))
    fit = t.get("fit", "none")
    target = t.get("target_seconds")
    lay = layout_mod.layout_crawl(project, sequence, measurer, 1.0)
    if fit == "none" or not target:
        return lay, crawl_timeline(project, lay, v), notes

    target_frames = int(round(float(target) * fps))
    probe = crawl_timeline(project, lay, v)
    fixed = probe["total_frames"] - probe["move_frames"]  # lead, pause, attese

    if fit == "spacing":
        lay2 = layout_mod.layout_crawl(project, sequence, measurer, 2.0)
        tr1, tr2 = _end_travel(lay, probe["end_mode"]), _end_travel(lay2, probe["end_mode"])
        slope = tr2 - tr1
        wanted = (target_frames - fixed) * v
        if slope > 0:
            g = 1.0 + (wanted - tr1) / slope
            gc = min(max(g, GAP_SCALE_LIMITS[0]), GAP_SCALE_LIMITS[1])
            if abs(gc - g) > 1e-6:
                notes.append("Spaziatura al limite (%.2fx): adeguo anche la velocita'." % gc)
            lay = layout_mod.layout_crawl(project, sequence, measurer, gc)
            notes.append("Spaziatura blocchi x%.2f" % gc)
        fit = "speed"  # rifinitura: velocita' intera + recupero frame residui

    if fit == "speed":
        for _ in range(3):  # le pause dipendono dalla velocita': piccola iterazione
            tl = crawl_timeline(project, lay, v)
            fixed = tl["total_frames"] - tl["move_frames"]
            avail = target_frames - fixed
            if avail <= 0:
                notes.append("Durata richiesta troppo corta per pause e attese impostate.")
                avail = 1
            exact = tl["travel_px"] / float(avail)
            v = exact if t.get("allow_fractional_speed") else max(1, int(math.ceil(exact - 1e-9)))
        tl = crawl_timeline(project, lay, v)
        pad = target_frames - tl["total_frames"]
        if pad > 0:
            tl = crawl_timeline(project, lay, v, pad_end_frames=pad)
        elif pad < 0:
            notes.append("Durata minima ottenibile: %.2fs" % (tl["total_frames"] / fps))
        readable = reading_check(tl, H, fps)
        if readable:
            notes.append(readable)
        return lay, tl, notes
    return lay, crawl_timeline(project, lay, v), notes


def reading_check(tl, H, fps):
    secs = H / (tl["speed_px"] * fps)
    if secs < 6.0:
        return "Attenzione: rullo molto veloce (una riga resta a schermo %.1fs). Consigliato >= 7s." % secs
    return None


# ======================================================================= cards
_word = re.compile(r"\w+", re.UNICODE)


def card_auto_seconds(card, pace):
    words, lines = 0, 0
    for e in card["elements"]:
        if e["kind"] == "text":
            for l in e["lines"]:
                if l.strip():
                    lines += 1
                    words += len(_word.findall(l))
        else:
            words += 2
    secs = 1.2 + 0.32 * words + 0.25 * lines
    return min(max(secs, CARD_MIN_S), CARD_MAX_S) * CARD_PACE.get(pace, 1.0)


def cards_timeline(project, lay):
    t = project["timing"]
    fps = float(project["format"]["fps"])
    pace = t.get("card_pace", "normal")
    fade = int(round(float(t.get("card_fade_s", 0.5)) * fps))
    gap = int(round(float(t.get("card_gap_s", 0.25)) * fps))
    lead_in = int(round(float(t.get("lead_in_s") or 0) * fps))
    lead_out = int(round(float(t.get("lead_out_s") or 0) * fps))
    durs = []
    for c in lay["cards"]:
        secs = float(c["duration_s"]) if c.get("duration_s") else card_auto_seconds(c, pace)
        durs.append(secs + c.get("hold_s", 0.0))
    target = t.get("target_seconds")
    notes = []
    if t.get("fit", "none") != "none" and target and durs:
        fixed = (lead_in + lead_out + gap * (len(durs) - 1)) / fps
        avail = float(target) - fixed
        if avail > 0:
            k = avail / sum(durs)
            durs = [d * k for d in durs]
            notes.append("Durata cartelli scalata x%.2f" % k)
    cards, cur = [], lead_in
    for d in durs:
        frames = max(int(round(d * fps)), 2 * fade + 1)
        cards.append({"start": cur, "frames": frames, "fade_in": fade, "fade_out": fade})
        cur += frames + gap
    total = (cur - gap if cards else cur) + lead_out
    if target and t.get("fit", "none") != "none":
        diff = int(round(float(target) * fps)) - total
        if cards and diff != 0:
            cards[-1]["frames"] = max(cards[-1]["frames"] + diff, 2 * fade + 1)
            total = cards[-1]["start"] + cards[-1]["frames"] + lead_out
    return {"kind": "cards", "fps": fps, "cards": cards, "total_frames": total, "lead_in": lead_in,
            "lead_out": lead_out}, notes


def card_opacity(card_tl, frame):
    s, n = card_tl["start"], card_tl["frames"]
    fi, fo = max(card_tl["fade_in"], 1), max(card_tl["fade_out"], 1)
    return max(0.0, min(1.0, (frame - s) / float(fi), (s + n - frame) / float(fo)))


def effective_project(project, sequence):
    """Tempi effettivi della sequenza: quelli del progetto + override della sequenza.
    Durata obiettivo e adattamento valgono per sequenza (testa e coda hanno durate diverse):
    a livello di progetto si applicano solo ai rulli."""
    t = dict(project["timing"])
    if sequence.get("kind") == "cards":
        t["fit"], t["target_seconds"] = "none", None
    t.update(sequence.get("timing") or {})
    if t == project["timing"]:
        return project
    p = dict(project)
    p["timing"] = t
    return p


def solve(project, sequence, measurer=None):
    """Punto d'ingresso unico: (layout, timeline, note) per crawl o cartelli."""
    project = effective_project(project, sequence)
    if sequence.get("kind") == "cards":
        lay = layout_mod.layout_cards(project, sequence, measurer)
        tl, notes = cards_timeline(project, lay)
        return lay, tl, notes
    return solve_crawl(project, sequence, measurer)
