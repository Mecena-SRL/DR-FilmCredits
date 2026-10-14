"""Presentation helpers for the film map; no Resolve or UI dependency."""

import html
from . import blocktext, phrases

ZONES = ("opening", "head", "closing", "crawl")
ZONE_LABELS = {
    "it": ("Apertura", "Titoli di testa", "Chiusura", "Titoli di coda"),
    "en": ("Opening panels", "Opening credits", "Closing panels", "End crawl"),
}
STATUS = {
    "new": ("#65a9ef", "+", "Nuovo", "New"),
    "changed": ("#e0b04a", "↻", "Da aggiornare", "Changed"),
    "unchanged": ("#73c999", "✓", "Sincronizzato", "Synced"),
    "removed": ("#ed7979", "−", "Da gestire", "Removed"),
    "missing": ("#ed7979", "!", "Clip non trovata", "Missing clip"),
    "ambiguous": ("#ed7979", "!", "Collegamento ambiguo", "Ambiguous link"),
    "trimmed": ("#e0b04a", "↔", "Durata manuale", "Manual duration"),
    "locked": ("#a0a0aa", "🔒", "Bloccato", "Locked"),
}


def zone_of(seq, block):
    explicit = block.get("zone") or seq.get("zone")
    if explicit in ZONES:
        return explicit
    if seq.get("kind") == "crawl":
        return "crawl"
    if seq.get("id") in ("end", "closing", "final"):
        return "closing"
    if block.get("type") in ("logos", "laurels", "legal") or (
            block.get("type") == "card" and not block.get("role") and not block.get("names")):
        return "opening"
    return "head"


def status_label(status, lang="it"):
    color, icon, it, en = STATUS.get(status, STATUS["missing"])
    return "%s %s" % (icon, it if lang == "it" else en), color


def preview_text(block, lang="it"):
    """Readable content proof, deliberately not a pixel-accurate Fusion preview."""
    if not block:
        return ""
    t = block["type"]
    if t in ("credit", "card") and not block.get("lines"):
        return "\n".join([phrases.role_text(block.get("role", ""), lang)] + block.get("names", []))
    if t == "card":
        return "\n".join(line.get("text", "") for line in block.get("lines", []))
    if t == "list":
        return "\n\n".join("\n".join([phrases.role_text(r.get("role", ""), lang)] + r.get("names", []))
                            for r in block.get("rows", []) if not r.get("break"))
    return blocktext.render(block)


def content_html(block, lang="it"):
    lines = preview_text(block, lang).splitlines()
    return "<html><body>" + "".join(
        '<p align="center" style="color:#eeeeee;font-size:16px;">%s</p>' % html.escape(line)
        for line in lines) + "</body></html>"
