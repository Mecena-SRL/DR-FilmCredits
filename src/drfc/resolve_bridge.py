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
import uuid
import re
import json
import os
import struct
import sys
import tempfile
import zlib

from . import calibration, engine, fusion_writer, log, workspace

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
        self._cal_done = False
        try:
            self.version = str(self.resolve.GetVersionString() or "")
        except Exception:
            self.version = ""

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
        if not re.fullmatch(r"\d{2,}:\d{2}:\d{2}[:;]\d{2}", str(tc)):
            raise ValueError("Timecode non valido: %s (HH:MM:SS:FF)." % tc)
        sep = ";" if ";" in tc else ":"
        parts = [int(x) for x in tc.replace(";", ":").split(":")]
        h, m, s, f = parts
        nominal = int(round(fps))
        if m >= 60 or s >= 60 or f >= nominal:
            raise ValueError("Timecode fuori intervallo: %s." % tc)
        total = ((h * 60 + m) * 60 + s) * nominal + f
        if drop or sep == ";":
            dropn = 2 if nominal == 30 else 4 if nominal == 60 else 0
            if not dropn or (m % 10 and s == 0 and f < dropn):
                raise ValueError("Timecode drop-frame non valido: %s." % tc)
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

    @staticmethod
    def _uid(obj):
        try:
            return str(obj.GetUniqueId() or "")
        except Exception:
            return ""

    def _state(self, project):
        """Bind render state to the actual Resolve project and timeline, not their names."""
        project.setdefault("project_id", uuid.uuid4().hex)
        key = self._uid(self.project) + ":" + self._uid(self.timeline)
        if key == ":":
            return project.setdefault("render_state", {})
        states = project.setdefault("timeline_states", {})
        previous = project.get("active_timeline")
        if previous and previous != key:
            states[previous] = project.get("render_state", {})
        if key not in states:
            states[key] = project.get("render_state", {}) if not previous else {}
        project["active_timeline"] = key
        project["render_state"] = states[key]
        return states[key]

    def _linked(self, sec, state):
        st = state.get(sec["id"], {})
        stem = st.get("stem", sec["stem"])
        all_items = [(it, i) for i in range(1, self.timeline.GetTrackCount("video") + 1)
                     for it in self.timeline.GetItemListInTrack("video", i) or []]
        uid = st.get("clip_uid")
        if uid:
            # A copied clip is independent. Never silently adopt or delete it.
            return [(it, i) for it, i in all_items if self._uid(it) == uid]
        # Legacy projects: only an unambiguous name can be adopted.
        return self.find_existing(stem) if st else []

    def review(self, project, only=None, card_mode="per_card", section_ids=None, zones=None):
        state = self._state(project)
        secs, issues, notes = plan_sections(project, only=only, card_mode=card_mode)
        selected = [s for s in secs if (not section_ids or s["id"] in section_ids)
                    and (not zones or s["zone"] in zones)]
        rows = []
        for sec in selected:
            st = state.get(sec["id"], {})
            linked = self._linked(sec, state)
            item = linked[0][0] if len(linked) == 1 else None
            if len(linked) > 1:
                status = "ambiguous"
            elif not item:
                status = "missing" if st.get("hash") else "new"
            elif st.get("locked"):
                status = "locked"
            elif self._duration(item) != st.get("clip_frames", st.get("frames")):
                status = "trimmed"
            elif st.get("hash") == sec["hash"]:
                status = "unchanged"
            else:
                status = "changed"
            rows.append(dict(sec, status=status, existing=linked,
                             current_frames=self._duration(item) if item else None,
                             current_start=int(item.GetStart()) if item else None))
        # Deletion is a tombstone: never infer that the timeline clip should be deleted.
        live = {s["id"] for s in secs}
        for sid, st in state.items():
            if sid in live or not st.get("hash"):
                continue
            if only and st.get("seq_id") not in only:
                continue
            if section_ids and sid not in section_ids:
                continue
            if zones and st.get("zone", "crawl") not in zones:
                continue
            rows.append({"id": sid, "label": st.get("label", sid), "zone": st.get("zone", "crawl"),
                         "status": "removed", "frames": st.get("frames", 0),
                         "existing": self._linked({"id": sid, "stem": st.get("stem", "")}, state)})
        return rows, issues, notes

    def _track_busy(self, track, start, frames, exclude=None):
        end = start + frames
        return any(it is not exclude and start < int(it.GetStart()) + int(it.GetDuration())
                   and int(it.GetStart()) < end
                   for it in self.timeline.GetItemListInTrack("video", track) or [])

    def sync(self, project, work_dir, only=None, where="playhead", track="dr", only_changed=True,
             progress=None, card_mode="per_card", replace=True, operation="sync", anchors=None,
             section_ids=None, zones=None, duration_policy="calculated", protected_until=None,
             film_start=None, before_film=False):
        """Generate and update are distinct. No ripple, no implicit duplicate cleanup.

        UI updates preserve manual duration by default; 'calculated' is an explicit
        replacement on a fresh upper track, staged before the old clip is deleted.
        """
        if operation not in ("sync", "generate", "update"):
            raise ValueError("Operazione sconosciuta")
        if duration_policy not in ("preserve", "calculated"):
            raise ValueError("Gestione durata sconosciuta")
        say = progress or (lambda m: None)
        fmt = self.apply_timeline_format(project)
        state = self._state(project)
        rows, issues, notes = self.review(project, only, card_mode, section_ids, zones)
        os.makedirs(work_dir, exist_ok=True)
        tracks, out = {}, []
        base = self.record_frame(where if where != "replace" else "playhead")
        zone_offsets, placements = {}, {}
        for sec in rows:
            if sec["status"] != "new":
                continue
            zone = sec["zone"]
            # Every zone has its own anchor; legacy callers pack sequences consecutively.
            if anchors is not None:
                start = int(anchors.get(zone, base)) + zone_offsets.get(zone, 0)
                zone_offsets[zone] = zone_offsets.get(zone, 0) + sec["frames"]
            else:
                start = base
                base += sec["frames"]
            placements[sec["id"]] = start
        # Validate every insertion before mutating Resolve.
        for sec in rows:
            if sec["status"] != "new" or operation == "update":
                continue
            start = placements[sec["id"]]
            if start < self.timeline.GetStartFrame():
                raise ValueError("Il titolo precede l'inizio della timeline.")
            if protected_until is not None and start < int(protected_until):
                raise ValueError("Il titolo entra nell'intervallo protetto del frameleader.")
            if before_film and sec["zone"] in ("opening", "head") and film_start is not None:
                if start + sec["frames"] > int(film_start):
                    raise ValueError("Spazio insufficiente prima del film: predisporre spazio manualmente, "
                                     "senza spostare il frameleader.")
        for sec in rows:
            sid, status = sec["id"], sec["status"]
            if status == "removed":
                out.append(_res(sec, False, "removed", "Da gestire: %s (clip conservata)." % sec["label"]))
                continue
            if status in ("missing", "ambiguous"):
                out.append(_res(sec, False, status, "Collegamento da verificare: %s. Nessuna modifica." % sec["label"]))
                continue
            if status == "locked":
                out.append(_res(sec, True, "locked", "Bloccata: '%s' non modificata." % sec["label"]))
                continue
            if (operation == "generate" and status != "new") or (operation == "update" and status == "new"):
                continue
            if status == "unchanged" and only_changed:
                out.append(_res(sec, True, "unchanged", "Invariata: %s." % sec["label"]))
                continue
            st = state.get(sid, {})
            stem = st.get("stem", sec["stem"])
            sec = dict(sec, stem=stem)
            comp_path = os.path.join(work_dir, stem + ".comp")
            item = None
            try:
                if sec["existing"]:
                    item, track_idx = sec["existing"][0]
                    if duration_policy == "preserve" or self._duration(item) == sec["frames"]:
                        say("Aggiorno '%s' mantenendo posizione e durata..." % sec["label"])
                        self._ensure_calibration(item, fmt["width"])
                        self._update_in_place(item, sec, comp_path)
                        if self._duration(item) != sec["frames"]:
                            notes.append("%s: durata manuale conservata; verificare ingresso/uscita del testo "
                                         "(calcolata %d frame, clip %d)." %
                                         (sec["label"], sec["frames"], self._duration(item)))
                        r = _res(sec, True, "updated", "Aggiornata: %s (posizione e durata conservate)." % sec["label"])
                    else:
                        if self._track_busy(track_idx, int(item.GetStart()), sec["frames"], item):
                            out.append(_res(sec, False, "collision", "Durata in conflitto: %s. "
                                            "Liberare spazio o mantenere la durata manuale." % sec["label"]))
                            continue
                        new_item = self._replace_item(item, track_idx, sec, work_dir, fmt, comp_path)
                        r = _res(sec, new_item is not None, "replaced", "Nuova durata: %s, %d frame "
                                 "(stessa posizione, nuova traccia superiore)." % (sec["label"], sec["frames"]))
                        item = new_item
                else:
                    zone = sec["zone"]
                    if zone not in tracks:
                        if operation == "generate":
                            tracks[zone] = self._new_track()
                            self.timeline.SetTrackName("video", tracks[zone], "DRFC · " +
                                                       workspace.ZONE_LABELS["it"][workspace.ZONES.index(zone)])
                        else:
                            tracks[zone] = self._track_for(track)
                    track_idx = tracks[zone]
                    rec = placements[sid]
                    if self._track_busy(track_idx, rec, sec["frames"]):
                        tracks[zone] = track_idx = self._new_track()
                    self.mp.SetCurrentFolder(self._folder())
                    item = self._append_holder(stem, work_dir, fmt, sec["frames"], track_idx, rec)
                    if item is None:
                        out.append(_res(sec, False, "failed", "Inserimento non riuscito: %s." % sec["label"]))
                        continue
                    self._ensure_calibration(item, fmt["width"])
                    self._import_comp(item, sec, comp_path)
                    item.SetClipColor("Purple")
                    r = _res(sec, True, "inserted", "Inserita: %s su V%d, frame %d." % (sec["label"], track_idx, rec))
                r.update({"item": item, "path": comp_path})
                out.append(r)
                if r["ok"] and item is not None:
                    state[sid] = {"hash": sec["hash"], "frames": sec["frames"], "stem": stem,
                                  "locked": st.get("locked", False), "clip_uid": self._uid(item),
                                  "clip_frames": self._duration(item), "label": sec["label"],
                                  "zone": sec["zone"], "seq_id": sec.get("seq_id")}
            except Exception as e:
                if status == "new" and item is not None:
                    self.timeline.DeleteClips([item], False)
                out.append(_res(sec, False, "failed", "%s: %s" % (sec["label"], e)))
        return {"sections": out, "issues": issues, "notes": notes}

    def resolve_removed(self, project, section_id, delete=False):
        rows, _i, _n = self.review(project)
        row = next((r for r in rows if r["id"] == section_id and r["status"] == "removed"), None)
        if not row:
            raise ValueError("Nessun elemento rimosso selezionato.")
        st = project["render_state"].get(section_id, {})
        if delete:
            if st.get("locked"):
                raise ValueError("La clip è bloccata: sbloccarla prima di rimuoverla.")
            if len(row["existing"]) != 1:
                raise ValueError("Collegamento mancante o ambiguo: nessuna clip rimossa.")
            if not self.timeline.DeleteClips([row["existing"][0][0]], False):
                raise RuntimeError("Resolve non ha rimosso la clip.")
        project["render_state"].pop(section_id, None)

    def _ensure_calibration(self, item, width):
        """Calibra Text+ da soli, una volta per versione di Resolve, su un comp temporaneo del
        clip (poi eliminato). Qualsiasi problema = si resta sui valori di default."""
        if self._cal_done:
            return
        self._cal_done = True
        if calibration.is_current(self.version):
            return
        probe = None
        try:
            before = list(item.GetFusionCompNameList() or [])
            probe = item.AddFusionComp()
            names = list(item.GetFusionCompNameList() or [])
            probe_name = next((n for n in names if n not in before), None)
            if probe is not None:
                calibration.ensure(probe, width, self.version)
            if probe_name:
                item.DeleteFusionCompByName(probe_name)
        except Exception:
            log.exception("calibrazione automatica")

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
        if user and not restore_user_nodes(comp, user, info["last_merge"], self.log):
            try:
                item.LoadFusionCompByName(stem + "_prev")
            finally:
                raise RuntimeError("Ripristino nodi manuali non riuscito: composizione precedente riattivata.")
        return comp

    def _replace_item(self, old_item, track_idx, sec, work_dir, fmt, comp_path):
        # Stage a complete replacement on a fresh upper track. Never delete first.
        rec = int(old_item.GetStart())
        old_comp = self._current_comp(old_item, sec["stem"])
        user = collect_user_nodes(old_comp) if old_comp else None
        props = copy_item_properties(old_item)
        new_track = self._new_track()
        self.timeline.SetTrackName("video", new_track, "DRFC · Aggiornamento durata")
        self.mp.SetCurrentFolder(self._folder())
        item = self._append_holder(sec["stem"], work_dir, fmt, sec["frames"], new_track, rec)
        if item is None:
            return None
        try:
            self._ensure_calibration(item, fmt["width"])
            comp, info = self._import_comp(item, sec, comp_path)
            paste_item_properties(item, props)
            if user and not restore_user_nodes(comp, user, info["last_merge"], self.log):
                raise RuntimeError("Nodi manuali non ripristinati: originale conservato.")
            if not self.timeline.DeleteClips([old_item], False):
                raise RuntimeError("Originale non rimosso: aggiornamento annullato.")
        except Exception:
            self.timeline.DeleteClips([item], False)
            raise
        return item

    def set_locked(self, project, section_id, locked=True):
        project.setdefault("render_state", {}).setdefault(section_id, {})["locked"] = bool(locked)

    def section_status(self, project, only=None, card_mode="per_card"):
        rows, _i, _n = self.review(project, only=only, card_mode=card_mode)
        return [(r["id"], r["label"], r["status"]) for r in rows]

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
    slug = engine.model_slug(project) + ("_" + project["project_id"][:8] if project.get("project_id") else "")
    secs, notes = [], []
    for seq, lay, tl, n in results:
        notes += n
        if tl["kind"] == "crawl" or card_mode == "per_sequence":
            secs.append({"id": seq["id"], "label": seq.get("name", seq["id"]), "stem": "%s%s_%s" % (COMP_PREFIX, slug, seq["id"]),
                         "project": clean, "layout": lay, "timeline": tl, "frames": int(tl["total_frames"]), "offset": 0,
                         "seq_id": seq["id"], "zone": workspace.zone_of(seq, seq["blocks"][0]) if seq["blocks"] else "crawl",
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
                         "seq_id": seq["id"], "zone": workspace.zone_of(seq, next((b for b in seq["blocks"] if b["id"] == bid), {})),
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

