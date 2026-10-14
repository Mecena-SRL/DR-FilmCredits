"""Collegamento con DaVinci Resolve Studio (API di scripting).

Strategia di inserimento (durata esatta, comp nativo e modificabile):
  1. si crea un "supporto" trasparente della durata esatta (PNG alla risoluzione della
     timeline aggiunto con startFrame/endFrame; se Resolve non accetta la durata del
     fermo immagine, sequenza di immagini di N fotogrammi collegati con hardlink);
  2. il supporto va su una traccia video dedicata, alla posizione scelta;
  3. sul clip si importa la composizione Fusion generata (ImportFusionComp) e la si rende
     attiva; il frame iniziale del comp viene letto e, se diverso da 0, il comp viene
     rigenerato con l'offset corretto (lo scorrimento resta allineato al frame);
  4. i Loader di loghi/foto/video vengono rifiniti via API (percorso, durata, scala).
Fallback: Fusion Composition standard (da allungare a mano) e, in ultima istanza, file
.setting da incollare nella pagina Fusion.
"""

import os
import struct
import sys
import tempfile
import zlib

from . import engine, fusion_writer

MEDIA_FOLDER = "DR-FilmCredits"
TRACK_NAME = "DR-FilmCredits"
COMP_PREFIX = "DRFC_"


# ---------------------------------------------------------------------- connessione
def get_resolve(resolve=None):
    if resolve is not None:
        return resolve
    try:
        import DaVinciResolveScript as dvr  # noqa
    except ImportError:
        paths = {
            "win32": os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                                  "Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting", "Modules"),
            "darwin": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        }
        sys.path.append(paths.get(sys.platform, "/opt/resolve/Developer/Scripting/Modules"))
        try:
            import DaVinciResolveScript as dvr  # noqa
        except ImportError:
            return None
    return dvr.scriptapp("Resolve")


class ResolveSession(object):
    def __init__(self, resolve=None):
        self.resolve = get_resolve(resolve)
        if not self.resolve:
            raise RuntimeError("DaVinci Resolve non raggiungibile. Avviare lo script da Workspace > Scripts.")
        self.pm = self.resolve.GetProjectManager()
        self.project = self.pm.GetCurrentProject()
        if not self.project:
            raise RuntimeError("Nessun progetto Resolve aperto.")
        self.timeline = self.project.GetCurrentTimeline()
        if not self.timeline:
            raise RuntimeError("Nessuna timeline attiva: aprirne una nella pagina Edit.")
        self.mp = self.project.GetMediaPool()
        self.log = []

    # ------------------------------------------------------------------ formato
    def timeline_format(self):
        tl = self.timeline

        def g(key):
            v = tl.GetSetting(key) or self.project.GetSetting(key)
            return v
        w, h = int(g("timelineResolutionWidth") or 1920), int(g("timelineResolutionHeight") or 1080)
        fps_s = str(g("timelineFrameRate") or "24")
        drop = "DF" in fps_s
        fps = float(fps_s.replace("DF", "").strip() or 24)
        return {"width": w, "height": h, "fps": fps, "drop_frame": drop}

    def apply_timeline_format(self, project):
        f = self.timeline_format()
        project["format"].update({"width": f["width"], "height": f["height"], "fps": f["fps"]})
        return f

    # ------------------------------------------------------------------ tempo
    @staticmethod
    def tc_to_frames(tc, fps, drop=False):
        sep = ";" if ";" in tc else ":"
        parts = [int(x) for x in tc.replace(";", ":").split(":")]
        h, m, s, f = parts
        nominal = int(round(fps))
        total = ((h * 60 + m) * 60 + s) * nominal + f
        if drop or sep == ";":
            dropn = 2 if nominal == 30 else 4 if nominal == 60 else 0
            minutes = h * 60 + m
            total -= dropn * (minutes - minutes // 10)
        return total

    def record_frame(self, where):
        tl = self.timeline
        if where == "start":
            return tl.GetStartFrame()
        if where == "end":
            return tl.GetEndFrame() + 1
        fmt = self.timeline_format()
        return self.tc_to_frames(tl.GetCurrentTimecode(), fmt["fps"], fmt["drop_frame"])

    # ------------------------------------------------------------------ media pool
    def _folder(self):
        root = self.mp.GetRootFolder()
        for f in root.GetSubFolderList() or []:
            if f.GetName() == MEDIA_FOLDER:
                return f
        return self.mp.AddSubFolder(root, MEDIA_FOLDER)

    def _new_track(self):
        self.timeline.AddTrack("video")
        idx = self.timeline.GetTrackCount("video")
        try:
            self.timeline.SetTrackName("video", idx, TRACK_NAME)
        except Exception:
            pass
        return idx

    def _track_for(self, where_track):
        if where_track == "new":
            return self._new_track()
        n = self.timeline.GetTrackCount("video")
        for i in range(1, n + 1):
            if self.timeline.GetTrackName("video", i) == TRACK_NAME:
                return i
        return self._new_track()

    # ------------------------------------------------------------------ inserimento
    def insert(self, project, seq_id, work_dir, where="playhead", track="dr", replace=True, progress=None):
        """Genera e inserisce una sequenza. Ritorna dict con esito e messaggi."""
        say = progress or (lambda m: None)
        fmt = self.apply_timeline_format(project)
        clean, results, issues = engine.solve_all(project, only=[seq_id])
        if not results:
            raise RuntimeError("La sequenza '%s' e' vuota." % seq_id)
        seq, lay, tl, notes = results[0]
        total = int(tl["total_frames"])
        stem = "%s%s_%s" % (COMP_PREFIX, engine.model_slug(project), seq_id)
        if not os.path.isdir(work_dir):
            os.makedirs(work_dir)

        old = self.find_existing(stem) if replace else []
        rec = self.record_frame(where)
        track_idx = None
        if old:
            item0, track_idx = old[0]
            if where == "replace":
                rec = item0.GetStart()
            self.timeline.DeleteClips([o[0] for o in old], False)
            say("Rimossa la versione precedente.")
        if track_idx is None:
            track_idx = self._track_for(track)

        say("Creo il supporto (%d frame)..." % total)
        self.mp.SetCurrentFolder(self._folder())
        item = self._append_holder(stem, work_dir, fmt, total, track_idx, rec)
        method = "clip"
        if item is None:
            say("Supporto non disponibile: uso una Fusion Composition.")
            item = self.timeline.InsertFusionCompositionIntoTimeline()
            method = "fusion_composition"
            if item is None:
                path = os.path.join(work_dir, stem + ".setting")
                fusion_writer.write(clean, lay, tl, path, kind="setting")
                return {"ok": False, "method": "setting", "path": path, "issues": issues, "notes": notes,
                        "message": "Inserimento automatico non riuscito: incollare %s nella pagina Fusion." % path}

        say("Importo la composizione Fusion...")
        comp_path = os.path.join(work_dir, stem + ".comp")
        info = fusion_writer.write(clean, lay, tl, comp_path, t0=0)
        comp = item.ImportFusionComp(comp_path)
        if comp is None:
            raise RuntimeError("ImportFusionComp non riuscito (%s)." % comp_path)
        start = self._comp_start(comp)
        if start:
            say("Allineo il comp al frame %d..." % start)
            first = list(item.GetFusionCompNameList() or [])
            info = fusion_writer.write(clean, lay, tl, comp_path, t0=start)
            comp = item.ImportFusionComp(comp_path) or comp
            for n in first:
                try:
                    item.DeleteFusionCompByName(n)
                except Exception:
                    pass
        self._rename_active(item, stem)
        self._fix_loaders(comp, info, start)
        dur = self._duration(item)
        msg = "Inserito '%s': %d frame (%.2fs) sulla traccia V%d." % (seq.get("name", seq_id), total, total / fmt["fps"], track_idx)
        if method == "fusion_composition" or (dur and dur != total):
            msg += " ATTENZIONE: allungare il clip a %d frame (durata attuale %s)." % (total, dur)
        return {"ok": True, "method": method, "item": item, "path": comp_path, "issues": issues, "notes": notes,
                "message": msg, "frames": total}

    def _append_holder(self, stem, work_dir, fmt, total, track_idx, rec):
        png = os.path.join(work_dir, stem + "_holder.png")
        write_transparent_png(png, fmt["width"], fmt["height"])
        items = self.mp.ImportMedia([png]) or []
        if items:
            res = self.mp.AppendToTimeline([{"mediaPoolItem": items[0], "startFrame": 0, "endFrame": total - 1,
                                             "trackIndex": track_idx, "recordFrame": rec}]) or []
            if res and self._duration(res[0]) == total:
                return res[0]
            if res:
                self.timeline.DeleteClips(res, False)
        # fallback: sequenza di immagini di esattamente `total` fotogrammi (hardlink, zero spazio)
        seq_dir = os.path.join(work_dir, stem + "_holder_seq")
        if not os.path.isdir(seq_dir):
            os.makedirs(seq_dir)
        for fn in os.listdir(seq_dir):
            os.remove(os.path.join(seq_dir, fn))
        for i in range(total):
            dst = os.path.join(seq_dir, "%s.%06d.png" % (stem, i))
            try:
                os.link(png, dst)
            except (OSError, AttributeError):
                with open(png, "rb") as s, open(dst, "wb") as d:
                    d.write(s.read())
        items = self.mp.ImportMedia([{"FilePath": os.path.join(seq_dir, stem + ".%06d.png"),
                                      "StartIndex": 0, "EndIndex": total - 1}]) or []
        if not items:
            return None
        res = self.mp.AppendToTimeline([{"mediaPoolItem": items[0], "startFrame": 0, "endFrame": total - 1,
                                         "trackIndex": track_idx, "recordFrame": rec}]) or []
        return res[0] if res else None

    @staticmethod
    def _duration(item):
        try:
            return int(item.GetDuration())
        except Exception:
            return None

    @staticmethod
    def _comp_start(comp):
        try:
            attrs = comp.GetAttrs() or {}
            return int(attrs.get("COMPN_RenderStart", attrs.get("COMPN_GlobalStart", 0)) or 0)
        except Exception:
            return 0

    @staticmethod
    def _rename_active(item, stem):
        try:
            names = item.GetFusionCompNameList() or []
            if names:
                item.RenameFusionCompByName(names[-1], stem)
                item.LoadFusionCompByName(stem)
        except Exception:
            pass

    def _fix_loaders(self, comp, info, t0):
        """Percorso, durata e scala dei Loader impostati via API (piu' robusto del file)."""
        if not info.get("loaders"):
            return
        total = info["total_frames"]
        comp.Lock()
        try:
            for ld in info["loaders"]:
                tool = comp.FindTool(ld["loader"])
                if tool is None:
                    continue
                try:
                    tool.SetInput("Clip", ld["path"].replace("\\", "/"))
                    tool.SetInput("GlobalOut", t0 + total - 1)
                    tool.SetInput("GlobalIn", t0)
                    if ld["kind"] == "video":
                        tool.SetInput("Loop", 1)
                    else:
                        tool.SetInput("HoldLastFrame", total)
                except Exception:
                    pass
                if not ld["scaled"]:
                    try:
                        attrs = tool.GetAttrs() or {}
                        w = attrs.get("TOOLIT_Clip_Width")
                        if isinstance(w, dict):
                            w = list(w.values())[0]
                        if w:
                            comp.FindTool(ld["merge"]).SetInput("Size", float(ld["w"]) / float(w))
                    except Exception:
                        self.log.append("Scala non impostata per %s" % ld["path"])
        finally:
            comp.Unlock()

    def find_existing(self, stem):
        """Clip gia' generati per questa sequenza (per sostituirli all'aggiornamento)."""
        out = []
        n = self.timeline.GetTrackCount("video")
        for i in range(1, n + 1):
            for it in self.timeline.GetItemListInTrack("video", i) or []:
                try:
                    mpi = it.GetMediaPoolItem()
                    name = mpi.GetName() if mpi else ""
                except Exception:
                    name = ""
                if name.startswith(stem + "_holder"):
                    out.append((it, i))
        return out


# ---------------------------------------------------------------------- PNG
def write_transparent_png(path, width, height):
    """PNG RGBA completamente trasparente, compresso in streaming (pochi KB anche in 4K)."""
    if os.path.exists(path):
        return path
    row = b"\x00" + b"\x00\x00\x00\x00" * width
    comp = zlib.compressobj(9)
    data = b"".join(comp.compress(row) for _ in range(height)) + comp.flush()

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
        f.write(chunk(b"IDAT", data))
        f.write(chunk(b"IEND", b""))
    return path


def default_work_dir(project_path=None):
    if project_path:
        return os.path.join(os.path.dirname(os.path.abspath(project_path)), "drfc_render")
    return os.path.join(tempfile.gettempdir(), "DR-FilmCredits")
