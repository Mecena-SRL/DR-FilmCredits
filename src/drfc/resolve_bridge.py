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

import hashlib
import json
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
    # ------------------------------------------------------------------ sezioni
    def insert(self, project, seq_id, work_dir, where="playhead", track="dr", replace=True, progress=None,
               card_mode="per_card"):
        """Genera (o rigenera) una sequenza. Compatibilita': aggiorna sempre le sue sezioni."""
        res = self.sync(project, work_dir, only=[seq_id], where=where, track=track, only_changed=False,
                        progress=progress, card_mode=card_mode, replace=replace)
        if not res["sections"]:
            raise RuntimeError("La sequenza '%s' e' vuota." % seq_id)
        first = res["sections"][0]
        out = dict(first)
        out.update({"issues": res["issues"], "notes": res["notes"], "message": "\n".join(r["message"] for r in res["sections"]),
                    "ok": all(r["ok"] for r in res["sections"])})
        return out

    def sync(self, project, work_dir, only=None, where="playhead", track="dr", only_changed=True,
             progress=None, card_mode="per_card", replace=True):
        """Allinea la timeline al progetto, sezione per sezione, senza distruggere il lavoro fatto:
        - sezione invariata (stesso hash) -> non toccata
        - modificata, stessa durata -> nuovo comp sullo stesso clip; nodi aggiunti a mano conservati,
          versione precedente tenuta come '<nome>_prev'
        - modificata, durata diversa -> nuovo clip nella stessa posizione/traccia con le stesse proprieta'
        - bloccata -> mai rigenerata
        - nuova -> inserita alla posizione scelta (i cartelli mantengono la loro distanza)."""
        say = progress or (lambda m: None)
        fmt = self.apply_timeline_format(project)
        secs, issues, notes = plan_sections(project, only=only, card_mode=card_mode)
        if not os.path.isdir(work_dir):
            os.makedirs(work_dir)
        state = project.setdefault("render_state", {})
        base_rec = None
        out = []
        for sec in secs:
            sid, stem = sec["id"], sec["stem"]
            st = state.get(sid, {})
            existing = self.find_existing(stem) if replace else []
            if st.get("locked") and existing:
                out.append(_res(sec, True, "locked", "Bloccata: '%s' non modificata." % sec["label"]))
                continue
            if existing and only_changed and st.get("hash") == sec["hash"]:
                out.append(_res(sec, True, "unchanged", "Invariata: %s." % sec["label"]))
                continue
            comp_path = os.path.join(work_dir, stem + ".comp")
            if existing:
                item, track_idx = existing[0]
                for extra, _t in existing[1:]:
                    self.timeline.DeleteClips([extra], False)
                if self._duration(item) == sec["frames"]:
                    say("Aggiorno '%s' nello stesso clip..." % sec["label"])
                    self._update_in_place(item, sec, comp_path)
                    r = _res(sec, True, "updated", "Aggiornata: %s (stesso clip, nodi manuali conservati)." % sec["label"])
                else:
                    say("Aggiorno '%s' (nuova durata %d frame)..." % (sec["label"], sec["frames"]))
                    new_item = self._replace_item(item, track_idx, sec, work_dir, fmt, comp_path)
                    r = _res(sec, new_item is not None, "replaced",
                             "Aggiornata: %s, nuova durata %d frame (posizione e proprieta' conservate)." % (sec["label"], sec["frames"]))
                    item = new_item
            else:
                if base_rec is None:
                    base_rec = self.record_frame(where if where != "replace" else "playhead")
                track_idx = self._track_for(track)
                say("Inserisco '%s' (%d frame)..." % (sec["label"], sec["frames"]))
                self.mp.SetCurrentFolder(self._folder())
                item = self._append_holder(stem, work_dir, fmt, sec["frames"], track_idx, base_rec + sec["offset"])
                if item is None:
                    path = os.path.join(work_dir, stem + ".setting")
                    fusion_writer.write(sec["project"], sec["layout"], sec["timeline"], path, kind="setting")
                    out.append(_res(sec, False, "setting",
                                    "Inserimento automatico non riuscito: incollare %s nella pagina Fusion." % path, path=path))
                    continue
                self._import_comp(item, sec, comp_path)
                r = _res(sec, True, "inserted", "Inserita: %s, %d frame (%.2fs) su V%d." % (
                    sec["label"], sec["frames"], sec["frames"] / fmt["fps"], track_idx))
            r.update({"item": item, "path": comp_path})
            out.append(r)
            if r["ok"]:
                state[sid] = {"hash": sec["hash"], "frames": sec["frames"], "stem": stem, "locked": st.get("locked", False)}
        return {"sections": out, "issues": issues, "notes": notes}

    def _import_comp(self, item, sec, comp_path):
        info = fusion_writer.write(sec["project"], sec["layout"], sec["timeline"], comp_path, t0=0)
        comp = item.ImportFusionComp(comp_path)
        if comp is None:
            raise RuntimeError("ImportFusionComp non riuscito (%s)." % comp_path)
        start = self._comp_start(comp)
        if start:
            first = list(item.GetFusionCompNameList() or [])
            info = fusion_writer.write(sec["project"], sec["layout"], sec["timeline"], comp_path, t0=start)
            comp = item.ImportFusionComp(comp_path) or comp
            for n in first:
                try:
                    item.DeleteFusionCompByName(n)
                except Exception:
                    pass
        self._rename_active(item, sec["stem"])
        self._fix_loaders(comp, info, start)
        return comp, info

    def _current_comp(self, item, stem):
        try:
            c = item.GetFusionCompByName(stem)
            if c:
                return c
        except Exception:
            pass
        try:
            n = item.GetFusionCompCount()
            return item.GetFusionCompByIndex(n) if n else None
        except Exception:
            return None

    def _update_in_place(self, item, sec, comp_path):
        stem = sec["stem"]
        old = self._current_comp(item, stem)
        user = collect_user_nodes(old) if old else None
        start = self._comp_start(old) if old else 0
        info = fusion_writer.write(sec["project"], sec["layout"], sec["timeline"], comp_path, t0=start)
        names_before = list(item.GetFusionCompNameList() or [])
        comp = item.ImportFusionComp(comp_path)
        if comp is None:
            raise RuntimeError("ImportFusionComp non riuscito (%s)." % comp_path)
        if self._comp_start(comp) != start:
            info = fusion_writer.write(sec["project"], sec["layout"], sec["timeline"], comp_path, t0=self._comp_start(comp))
            item.DeleteFusionCompByName((item.GetFusionCompNameList() or [None])[-1])
            comp = item.ImportFusionComp(comp_path)
        # la versione precedente resta disponibile come <stem>_prev
        try:
            if stem + "_prev" in names_before:
                item.DeleteFusionCompByName(stem + "_prev")
            if stem in names_before:
                item.RenameFusionCompByName(stem, stem + "_prev")
        except Exception:
            pass
        self._rename_active(item, stem)
        self._fix_loaders(comp, info, self._comp_start(comp))
        if user:
            restore_user_nodes(comp, user, info["last_merge"], self.log)
        return comp

    def _replace_item(self, old_item, track_idx, sec, work_dir, fmt, comp_path):
        rec = old_item.GetStart()
        old_comp = self._current_comp(old_item, sec["stem"])
        user = collect_user_nodes(old_comp) if old_comp else None
        props = copy_item_properties(old_item)
        self.timeline.DeleteClips([old_item], False)
        self.mp.SetCurrentFolder(self._folder())
        item = self._append_holder(sec["stem"], work_dir, fmt, sec["frames"], track_idx, rec)
        if item is None:
            return None
        comp, info = self._import_comp(item, sec, comp_path)
        paste_item_properties(item, props)
        if user:
            restore_user_nodes(comp, user, info["last_merge"], self.log)
        return item

    def set_locked(self, project, section_id, locked=True):
        project.setdefault("render_state", {}).setdefault(section_id, {})["locked"] = bool(locked)

    def section_status(self, project, only=None, card_mode="per_card"):
        """[(id, etichetta, stato)] con stato: nuova | modificata | invariata | bloccata."""
        secs, _i, _n = plan_sections(project, only=only, card_mode=card_mode)
        state = project.get("render_state") or {}
        out = []
        for sec in secs:
            st = state.get(sec["id"], {})
            on_tl = bool(self.find_existing(sec["stem"]))
            if st.get("locked") and on_tl:
                s = "locked"
            elif not on_tl:
                s = "new"
            elif st.get("hash") == sec["hash"]:
                s = "unchanged"
            else:
                s = "changed"
            out.append((sec["id"], sec["label"], s))
        return out

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
                        h = attrs.get("TOOLIT_Clip_Height")
                        if isinstance(h, dict):
                            h = list(h.values())[0]
                        if w and ld.get("cover") and h:
                            size = max(float(ld["w"]) / float(w), float(ld["h"]) / float(h))
                            comp.FindTool(ld["merge"]).SetInput("Size", size)
                        elif w:
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


# ---------------------------------------------------------------------- sezioni (logica pura)
def _res(sec, ok, action, message, path=None):
    return {"ok": ok, "id": sec["id"], "label": sec["label"], "action": action, "message": message,
            "frames": sec["frames"], "path": path, "method": "clip" if ok else action}


def _section_hash(lay_part, tl_part):
    def clean(o):
        if isinstance(o, float):
            return round(o, 3)
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if k not in ("block",)}
        if isinstance(o, list):
            return [clean(x) for x in o]
        return o
    blob = json.dumps({"lay": clean(lay_part), "tl": clean(tl_part)}, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def plan_sections(project, only=None, card_mode="per_card"):
    """Divide il progetto in sezioni da mettere in timeline: un clip per rullo e, per i
    cartelli, un clip per cartello (spostabili liberamente) oppure uno per sequenza.
    Ogni sezione ha id stabile, hash del contenuto, durata, offset e dati per il writer."""
    clean, results, issues = engine.solve_all(project, only=only)
    slug = engine.model_slug(project)
    secs, notes = [], []
    for seq, lay, tl, n in results:
        notes += n
        if tl["kind"] == "crawl" or card_mode == "per_sequence":
            secs.append({"id": seq["id"], "label": seq.get("name", seq["id"]), "stem": "%s%s_%s" % (COMP_PREFIX, slug, seq["id"]),
                         "project": clean, "layout": lay, "timeline": tl, "frames": int(tl["total_frames"]), "offset": 0,
                         "hash": _section_hash(lay.get("elements") or lay.get("cards"), tl)})
            continue
        seen = {}
        for card, ctl in zip(lay["cards"], tl["cards"]):
            bid = card["blocks"][0] if card.get("blocks") else "card"
            seen[bid] = seen.get(bid, 0) + 1
            sid = "%s_%s" % (seq["id"], bid) + ("_p%d" % seen[bid] if seen[bid] > 1 else "")
            sub_lay = dict(lay, cards=[card])
            sub_tl = dict(tl, cards=[dict(ctl, start=0)], total_frames=int(ctl["frames"]), lead_in=0, lead_out=0)
            label = " / ".join(" ".join(e["lines"]) for e in card["elements"] if e["kind"] == "text")[:48] or sid
            secs.append({"id": sid, "label": "%s: %s" % (seq.get("name", seq["id"]), label),
                         "stem": "%s%s_%s" % (COMP_PREFIX, slug, sid), "project": clean, "layout": sub_lay,
                         "timeline": sub_tl, "frames": int(ctl["frames"]), "offset": int(ctl["start"]),
                         "hash": _section_hash(card["elements"], sub_tl["cards"])})
    return secs, issues, notes


ITEM_PROPERTIES = ("Pan", "Tilt", "ZoomX", "ZoomY", "ZoomGang", "RotationAngle", "AnchorPointX", "AnchorPointY",
                   "Pitch", "Yaw", "FlipX", "FlipY", "CropLeft", "CropRight", "CropTop", "CropBottom",
                   "CropSoftness", "CropRetain", "CompositeMode", "Opacity", "Distortion", "Scaling",
                   "ResizeFilter")


def copy_item_properties(item):
    props = {}
    for k in ITEM_PROPERTIES:
        try:
            v = item.GetProperty(k)
            if v is not None:
                props[k] = v
        except Exception:
            pass
    try:
        props["__color"] = item.GetClipColor()
    except Exception:
        pass
    return props


def paste_item_properties(item, props):
    for k, v in props.items():
        try:
            if k == "__color":
                if v:
                    item.SetClipColor(v)
            else:
                item.SetProperty(k, v)
        except Exception:
            pass


def _tool_name(t):
    try:
        return t.Name
    except Exception:
        return (t.GetAttrs() or {}).get("TOOLS_Name", "")


def _tool_id(t):
    try:
        return (t.GetAttrs() or {}).get("TOOLS_RegID", "")
    except Exception:
        return ""


def collect_user_nodes(comp):
    """Nodi aggiunti a mano (nome non 'DRFC_'): impostazioni + punto di aggancio alla catena."""
    try:
        tools = comp.GetToolList(False) or {}
    except Exception:
        return None
    tools = list(tools.values()) if isinstance(tools, dict) else list(tools)
    user = [t for t in tools if not _tool_name(t).startswith(COMP_PREFIX)
            and _tool_id(t) not in ("MediaOut", "MediaIn") and not _tool_name(t).startswith(("MediaOut", "MediaIn"))]
    if not user:
        return None
    names = {_tool_name(t) for t in user}
    try:
        settings = comp.CopySettings(user)
    except Exception:
        settings = None
    head = tail = None
    for t in user:
        try:
            for inp in (t.GetInputList() or {}).values():
                out = inp.GetConnectedOutput()
                if out is not None and _tool_name(out.GetTool()).startswith(COMP_PREFIX):
                    head = (_tool_name(t), (inp.GetAttrs() or {}).get("INPS_ID", "Input"))
        except Exception:
            continue
    try:
        mo = comp.FindTool("MediaOut1")
        src = mo.Input.GetConnectedOutput() if mo else None
        if src is not None and _tool_name(src.GetTool()) in names:
            tail = _tool_name(src.GetTool())
    except Exception:
        pass
    return {"settings": settings, "names": sorted(names), "head": head, "tail": tail}


def restore_user_nodes(comp, user, last_merge, log=None):
    """Incolla i nodi utente nel nuovo comp e li ricollega tra l'ultimo Merge e MediaOut."""
    try:
        if user.get("settings") is not None:
            comp.Paste(user["settings"])
        if user.get("head"):
            tool, inp = user["head"]
            comp.FindTool(tool).ConnectInput(inp, comp.FindTool(last_merge))
        if user.get("tail"):
            comp.FindTool("MediaOut1").ConnectInput("Input", comp.FindTool(user["tail"]))
        return True
    except Exception as e:
        if log is not None:
            log.append("Nodi manuali non ricollegati: %s" % e)
        return False


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
