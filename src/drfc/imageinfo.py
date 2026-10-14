"""Dimensioni di immagini (PNG, JPEG, GIF, BMP, TIFF) senza dipendenze."""

import os
import struct

VIDEO_EXT = (".mov", ".mp4", ".mxf", ".avi", ".mkv", ".m4v", ".webm", ".braw", ".r3d")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".dpx", ".bmp", ".gif", ".tga", ".psd")


def media_kind(path):
    ext = os.path.splitext(path or "")[1].lower()
    if ext in VIDEO_EXT:
        return "video"
    return "image"


def image_size(path):
    """(width, height) oppure None se non determinabile."""
    try:
        with open(path, "rb") as f:
            head = f.read(64 * 1024)
    except (IOError, OSError):
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if head[:2] == b"BM":
        w, h = struct.unpack("<ii", head[18:26])
        return abs(w), abs(h)
    if head[:2] == b"\xff\xd8":
        i = 2
        while i < len(head) - 9:
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", head[i + 2:i + 4])[0]
            i += 2 + seg
        return None
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        endian = "<" if head[:2] == b"II" else ">"
        ifd = struct.unpack(endian + "I", head[4:8])[0]
        if ifd + 2 > len(head):
            return None
        n = struct.unpack(endian + "H", head[ifd:ifd + 2])[0]
        w = h = None
        for k in range(n):
            e = ifd + 2 + 12 * k
            tag, typ = struct.unpack(endian + "HH", head[e:e + 4])
            val = struct.unpack(endian + ("H" if typ == 3 else "I"), head[e + 8:e + (10 if typ == 3 else 12)])[0]
            if tag == 256:
                w = val
            elif tag == 257:
                h = val
        return (w, h) if w and h else None
    return None
