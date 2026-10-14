"""Pannello guidato (UIManager di Resolve/Fusion) a 3 passi.

  1 Cosa crei    titolo, tipo di opera, destinazione, cosa c'e' nel lavoro, segnaposto
  2 Compila      un unico elenco di tutto il progetto + editor a destra
  3 Timeline     un solo pulsante: crea o aggiorna le clip

  Aspetto e avanzate: look, stili, tempi, dati dell'opera, opzioni (tutto il resto).

Regole contro i bug visti in Resolve:
  - nessuna proprieta' dubbia (niente Hidden): i pannelli che cambiano sono Stack;
  - ogni handler e' idempotente (gli eventi dei menu riempiti dal codice arrivano a RunLoop
    avviato e non devono cambiare niente);
  - tutta la logica sta in moduli puri (outline, guide, placeholders, model...).
"""

import json
import uuid
import os
import traceback
import webbrowser

from . import (__version__, blocktext, design, engine, fusion_constants, guide, i18n, io_import, laurels,
               layout, log, logos, model, outline, placeholders, presets, resolve_bridge, workspace, validate, filmstrip)
from .model import BLOCK_TYPES

FUNDING = ["mic_tax_credit", "mic_selective", "cultural_interest", "film_commission", "creative_europe",
           "eurimages", "italian_tax_credit_foreign", "rai_cinema", "cnc", "ffa", "dfff", "icaa"]
SPEEDS = ["slow", "normal", "fast", "custom"]
FITS = ["none", "speed", "spacing"]
END_MODES = ["scroll_out", "hold_last"]
PACES = ["slow", "normal", "fast"]
LAYOUTS = ["stacked", "two_column"]
ARRANGEMENTS = ["pair", "single", "pairs_2", "pairs_3", "stacked_2", "stacked_3", "stacked_4", "names"]
POSITIONS = ["center", "lower_third", "upper_third", "left", "right"]
ORDERS = ["actor_character", "character_actor"]
KINDS = ["location", "rental", "archive", "product", "artwork"]
COLUMNS = ["auto", "1", "2", "3", "4"]
CASES = ["none", "upper", "lower", "title"]
STYLE_KEYS = ["title", "heading", "role", "name", "character", "small", "legal", "card_role", "card_name"]
WHERE = ["playhead", "end", "start"]
SPLITS = ["none", "media_left", "media_right"]
RENDER = ["auto", "block", "line"]
DENSITIES = ["compact", "normal", "airy"]
LEADINGS = ["tight", "normal", "wide"]
BACKGROUNDS = ["transparent", "black", "white", "color", "gradient", "media", "dim", "panel"]
CARD_MODES = ["per_card", "per_sequence"]
STATUS_KEYS = ["official_selection", "in_competition", "out_of_competition", "winner", "special_mention",
               "nominee", "world_premiere", "international_premiere", "opening_film"]
CUSTOM = "✎"

# le 9 spunte del passo 1 -> voci della checklist di guide.py (regia, crediti e copyright sono sempre inclusi)
UI_ELEMENTS = [
    ("cast", ["cast"]), ("crew", ["crew"]), ("music", ["music"]), ("places", ["locations", "rentals"]),
    ("archive", ["archive"]), ("funders", ["funders"]), ("festival", ["festival"]), ("thanks", ["thanks"]),
    ("backstage", ["backstage"]),
]
ALWAYS = ["key_crew", "copyright"]
# pagine dell'editor a destra (passo 2)
ED_HINT, ED_ENTRY, ED_TEXT, ED_LOGOS, ED_LAURELS, ED_COMPANY = 0, 1, 2, 3, 4, 5


def _settings_path():
    return os.path.join(fusion_constants.user_dir(), "settings.json")


def load_settings():
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return {}


def save_settings(s):
    d = os.path.dirname(_settings_path())
    if not os.path.isdir(d):
        os.makedirs(d)
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


UI_STYLESHEET = '\nQWidget { background-color:#17191f; color:#e7e9ed; font-size:12px; }\nQLabel { background:transparent; color:#b9bfca; }\nQPushButton { background:#252933; color:#e7e9ed; border:1px solid #353b48; border-radius:5px; padding:6px 12px; min-height:18px; }\nQPushButton:hover { background:#303744; border-color:#59677b; }\nQPushButton:checked { background:#394657; color:#ffffff; border-color:#8196b0; }\nQPushButton:disabled { color:#69717f; background:#1e222a; }\nQLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:#101319; color:#edf0f5; border:1px solid #343a46; border-radius:4px; padding:5px; min-height:18px; }\nQLineEdit:focus, QComboBox:focus, QTextEdit:focus { border:1px solid #8196b0; }\nQTextEdit, QTreeWidget { background:#101319; color:#e7e9ed; border:1px solid #303642; border-radius:6px; padding:7px; }\nQTreeWidget::item { padding:8px 4px; border-bottom:1px solid #1f2530; }\nQTreeWidget::item:selected { background:#31425a; color:#ffffff; }\nQHeaderView::section { background:#20252e; color:#abb4c2; border:0; padding:7px 5px; }\nQCheckBox { background:transparent; color:#c9d0dc; spacing:7px; }\nQCheckBox::indicator { width:15px; height:15px; }\nQScrollBar:vertical { background:#17191f; width:8px; }\nQScrollBar::handle:vertical { background:#4b5667; border-radius:4px; min-height:24px; }\n'


class _WorkspaceUI:
    """Track primitive widgets so inactive layouts do not impose their size hints.

    UIManager Stack reports surprising CurrentIndex values in Resolve 21.1 and
    keeps the minimum sizes of inactive layout pages. Explicit Visible on widgets
    is supported by UIWidget; no unsupported Hidden attributes are used.
    """
    def __init__(self, wizard):
        self.wizard = wizard

    def __getattr__(self, kind):
        factory = getattr(self.wizard.ui, kind)
        if kind in ("VGroup", "HGroup", "Stack", "VGap", "HGap"):
            return factory
        def make(props=None, *args):
            props = dict(props or {})
            props.setdefault("ID", "Auto_%d" % len(self.wizard._widget_visibility))
            props.setdefault("Visible", self.wizard._build_page is None or self.wizard._build_page == 0)
            self.wizard._widget_visibility[props["ID"]] = (
                self.wizard._build_page, self.wizard._build_editor, self.wizard._build_aspect)
            return factory(props, *args)
        return make


class Wizard(object):
    def __init__(self, fusion, bmd, resolve=None):
        self.fu, self.bmd, self.resolve = fusion, bmd, resolve
        self.ui = fusion.UIManager
        self.disp = bmd.UIDispatcher(self.ui)
        self.settings = load_settings()
        self.lang = self.settings.get("ui_lang", "it")
        self.path = self.settings.get("last_project")
        self.project = None
        self.fresh = True  # nessun progetto ancora creato o aperto
        if self.path and os.path.exists(self.path):
            try:
                self.project = model.load(self.path)
                self.fresh = False
            except Exception:
                self.project = None
        if self.project is None:
            self.path = None
            self.project = guide.new_project("corto", "it", use_placeholders=True)
        self.seq_idx = 0
        self.rows, self.items, self.sel = [], [], -1
        self.busy = False
        self.restart = False
        self.depts = list(i18n.roles()["departments"].keys())
        self.dests = list(design.destinations().keys())
        self.fontsets = list(design.fontsets().keys())
        self.festivals = list(laurels.festivals()["festivals"].keys())
        self.logo_ids = [e["id"] for e in logos.registry()["logos"]]
        self.zone = None
        self.pending_operation = None
        self._editor_page = ED_HINT
        self._more_tools_open = False
        self._current_page = 0
        self._insert_page = 0
        self._aspect = 0
        self._strip_full = False
        self.saved_snapshot = self._snapshot() if self.path else None
        self.role_keys = []
        self.section_keys = [""]

    def W(self, key):
        texts = {
            "add_company": ("+ Cartello società", "+ Company panel"),
            "company_panel": ("Cartello società", "Company panel"),
            "company_name": ("Società", "Company"),
            "company_relation": ("Funzione", "Relationship"),
            "company_contract": ("Usa una dicitura concordata", "Use agreed wording"),
            "company_statement": ("Dicitura esatta concordata", "Exact agreed wording"),
            "company_source": ("Riferimento contratto / approvazione", "Contract / approval reference"),
            "company_approved": ("Testo approvato", "Wording approved"),
            "company_note": ("Dicitura proposta modificabile. Verifica il contratto; i loghi hanno un blocco dedicato.", "Suggested wording is editable. Use the logo block for logos and properties for duration and positioning. Check contract requirements."),
            "content_proof": ("Contenuto del cartello", "Panel content"),
            "proof_note": ("Bozza del contenuto: posizione, loghi e animazione si verificano nell'anteprima completa.", "Content proof: check positioning, logos and animation in the full preview."),
            "animated_preview": ("Anteprima completa ↗", "Full preview ↗"),
            "timeline_help": ("Genera gli elementi nuovi; Aggiorna modifica solo quelli collegati. Il montaggio resta fermo.", "Generate new elements; Update only changes linked clips. The edit stays in place."),
            "generate": ("Genera in timeline", "Generate in timeline"),
            "update": ("Aggiorna in timeline", "Update in timeline"),
            "preserve_duration": ("Mantieni le durate modificate in timeline", "Keep durations edited in the timeline"),
            "remove_linked": ("Rimuovi clip eliminata…", "Remove deleted element's clip…"),
            "detach_linked": ("Conserva clip e scollega…", "Keep clip and detach…"),
            "review_hint": ("Le operazioni mostrano un riepilogo prima di scrivere in Resolve.", "Review each operation before writing to Resolve."),
            "film_end": ("Fine del film", "Film end"),
            "first_generation": ("Inserimento: punti di partenza delle quattro zone", "Insertion: starting points for the four zones"),
            "protect_leader": ("Proteggi l'intervallo del frameleader", "Protect the frameleader interval"),
            "leader_end": ("Fine frameleader (esclusiva)", "Frameleader end (exclusive)"),
            "film_start": ("Inizio del film", "Film start"),
            "before_film": ("Cartelli iniziali nello spazio prima del film", "Opening panels in the gap before the film"),
            "manual_shift": ("Per creare spazio, sposta manualmente il film mantenendo il frameleader. Poi indica il nuovo inizio. L'API non permette uno spostamento generale affidabile.", "To create a gap, move the film manually while keeping the frameleader. Then enter its new start. The API cannot reliably shift the whole edit."),
            "prepare_insert": ("Controlla inserimento →", "Review insertion →"),
            "confirm_removal": ("Confermo la rimozione della clip collegata", "Confirm removal of the linked clip"),
            "cancel": ("Annulla", "Cancel"),
            "apply_operation": ("Applica alla timeline", "Apply to timeline"),
            "zone": ("Zona del film", "Film zone"),
            "automatic": ("Automatica", "Automatic"),
            "all": ("Tutto", "All"),
            "film": ("FILM", "FILM"),
            "legend": ("verde: sincronizzato · giallo: modificato · blu: nuovo · rosso: da gestire", "green: synced · yellow: changed · blue: new · red: needs attention"),
            "scope_all": ("Intero progetto", "Whole project"),
            "scope_zone": ("Zona selezionata", "Selected zone"),
            "scope_selected": ("Elemento selezionato", "Selected element"),
        }
        return texts[key][0 if self.lang == "it" else 1]

    def _snapshot(self):
        return json.dumps(self.project, sort_keys=True, default=str) if self.project else ""

    @staticmethod
    def _rgba(color):
        return {"R": int(color[1:3], 16) / 255.0, "G": int(color[3:5], 16) / 255.0,
                "B": int(color[5:7], 16) / 255.0, "A": 1.0}

    def commit_editor(self):
        if not hasattr(self, "it") or self.busy or self.sel < 0:
            return
        row, b = self.row_sel(), self.block()
        if not b:
            return
        page = self._editor_page
        if page == ED_ENTRY and row["kind"] == "entry":
            role, names = self._row_from_ui()
            outline.set_entry(self.project, row, role, names)
        elif page == ED_COMPANY:
            values = {"name": self.it["CompanyName"].Text.strip(), "relation": self._idx("CompanyRelation"),
                      "contractual": bool(self.it["CompanyContract"].Checked), "statement": self.it["CompanyStatement"].PlainText.strip(),
                      "source": self.it["CompanySource"].Text.strip(), "approved": bool(self.it["CompanyApproved"].Checked)}
            if "company" not in b and not values["name"] and not values["source"] and not values["approved"] and values["contractual"] and values["statement"] == "\n".join(l.get("text", "") for l in b.get("lines", [])):
                return
            company = b.setdefault("company", {})
            company.update(name=self.it["CompanyName"].Text.strip(), relation=self._idx("CompanyRelation"),
                           contractual=bool(self.it["CompanyContract"].Checked),
                           statement=self.it["CompanyStatement"].PlainText.strip(),
                           source=self.it["CompanySource"].Text.strip(),
                           approved=bool(self.it["CompanyApproved"].Checked))
            if company["contractual"]:
                text = company["statement"]
            else:
                labels = ["presenta", "Una produzione", "In coproduzione con", "In collaborazione con", "Con il sostegno di"] if self.project["meta"].get("language") == "it" else ["presents", "A production by", "In coproduction with", "In collaboration with", "With the support of"]
                relation = company["relation"]
                text = (company["name"] + "\n" + labels[0]) if relation == 0 else (labels[relation] + "\n" + company["name"])
            b["lines"] = [{"text": line, "style": "card_name"} for line in text.splitlines() if line]
            b["role"], b["names"] = "", []
        elif page == ED_TEXT:
            blocktext.parse(b, self.it["BlockText"].PlainText)
            heading = self.it["HeadingText"].Text.strip() or self.headings[self._idx("Heading")]
            if "heading" in BLOCK_TYPES[b["type"]]["fields"]:
                b["heading"] = heading
            if b["type"] == "list":
                b["arrangement"] = ARRANGEMENTS[self._idx("Arr")]

    def close_views(self):
        for win in getattr(self, "windows", [self.win]):
            win.Hide()
        self.disp.ExitLoop()

    def update_visibility(self):
        if not hasattr(self, "it") or not hasattr(self, "_widget_visibility"):
            return
        more = {"Reorder", "Suggest", "Unfilled", "Import"}
        insert = {"ProtectLeader", "FilmStart", "LeaderEnd", "FilmEnd", "BeforeFilm", "PrepareInsert"} | {"Anchor_" + z for z in workspace.ZONES}
        review = {"OperationReview", "ConfirmRemoval", "CancelOperation", "ApplyOperation"}
        for cid, (page, editor, aspect) in self._widget_visibility.items():
            visible = page is None or page == self._current_page
            if editor is not None:
                visible = visible and editor == self._editor_page
            if aspect is not None:
                visible = visible and aspect == self._aspect
            if cid in insert:
                visible = visible and self._insert_page == 1
            if cid in review:
                visible = visible and self._insert_page == 2
            try:
                self.it[cid].Visible = visible
            except Exception:
                pass

    def toggle_more_tools(self):
        self.go(3)
        self.go_aspect(5)

    def on_add_company(self):
        self.ui_to_project()
        zone = self.zone if self.zone in ("opening", "head", "closing") else "opening"
        seq = next((s for s in self.project["sequences"] if s["kind"] == "cards" and (s.get("zone") == zone or (zone == "opening" and s["id"] == "opening"))), None)
        if seq is None:
            seq = model.new_sequence("zone_" + zone, "cards", workspace.ZONE_LABELS[self.L()][workspace.ZONES.index(zone)])
            seq["zone"] = zone
            self.project["sequences"].append(seq)
        block = model.new_block("card", id="company_" + uuid.uuid4().hex[:12], zone=zone,
                                company={"name": "", "relation": 1, "contractual": False, "statement": "", "source": "", "approved": False})
        seq["blocks"].append(block)
        self.zone, self.sel = zone, -1
        self.refresh_outline(select=(self.project["sequences"].index(seq), len(seq["blocks"]) - 1, 0))
        self.refresh_film_map()

    def on_pending_edit(self, ev):
        self.ui_to_project()
        self.it["ContentProof"].HTML = workspace.content_html(self.block(), self.project["meta"].get("language", "it"))
        self.refresh_film_map()

    def navigate_entry(self, direction):
        self.commit_editor()
        for i in range(self.sel + direction, len(self.rows) if direction > 0 else -1, direction):
            if self.rows[i]["kind"] == "entry":
                self.select(i, focus=True)
                return

    def select_zone(self, zone):
        self.ui_to_project()
        self.zone, self.sel = zone, -1
        self.go(1)
        self.refresh_film_map()

    def refresh_film_map(self):
        if not hasattr(self, "it"):
            return
        sess = self._session()
        try:
            if sess:
                rows, _i, _n = sess.review(self.project, card_mode=self._card_mode())
            else:
                secs, _i, _n = resolve_bridge.plan_sections(self.project, card_mode=self._card_mode())
                rows = [dict(s, status="new") for s in secs]
            priority = ("ambiguous", "missing", "removed", "changed", "trimmed", "new", "unchanged", "locked")
            for zi, zone in enumerate(workspace.ZONES):
                elements = [r for r in rows if r["zone"] == zone]
                statuses = [r["status"] for r in elements]
                st = next((p for p in priority if p in statuses), "new")
                label, color = workspace.status_label(st, self.lang)
                button = self.it["Zone_" + zone]
                button.Text = "%s · %d" % (workspace.ZONE_LABELS[self.L()][zi], len(elements))
                button.StyleSheet = "background:%s; color:%s; border:0; border-radius:4px; padding:3px 8px;" % ("#2d3543" if self.zone == zone else "#20252d", color)
            self.refresh_strip(rows, sess)
        except Exception as e:
            self.status(str(e))
        self.it["SaveState"].Text = ("✓ " + ("Salvato" if self.lang == "it" else "Saved")) if self.saved_snapshot == self._snapshot() else ("● " + ("Modifiche non salvate" if self.lang == "it" else "Unsaved changes"))

    def refresh_strip(self, rows, sess):
        fps = self.project["format"]["fps"]
        insertion = self.project.get("insertion") or {}
        drop = False
        if sess:
            fmt = sess.timeline_format()
            fps, drop = fmt["fps"], fmt["drop_frame"]
            start = sess.timeline.GetStartFrame()
            end = sess.timeline.GetEndFrame() + 1
        else:
            start = int(round(fps)) * 3600
            end = start + int(fps * 1800)
        convert = lambda tc: resolve_bridge.ResolveSession.tc_to_frames(tc, fps, drop)
        film_start = convert(insertion["film_start"]) if insertion.get("film_start") else start + int(2 * fps)
        film_end = convert(insertion["film_end"]) if insertion.get("film_end") else end
        cursors = {"opening": film_start, "head": film_start, "closing": film_end, "crawl": film_end}
        cursors.update({z: convert(tc) for z, tc in insertion.get("anchors_tc", {}).items()})
        blocks = []
        indicative = False
        for row in rows:
            a = row.get("current_start")
            duration = row.get("current_frames") or row["frames"]
            if a is None and row.get("existing"):
                item = row["existing"][0][0]
                a, duration = int(item.GetStart()), int(item.GetDuration())
            if a is None:
                indicative = True
                a = cursors[row["zone"]]
                cursors[row["zone"]] += duration
                if row["zone"] == "opening" and not insertion.get("anchors_tc", {}).get("head"):
                    cursors["head"] = max(cursors["head"], cursors["opening"])
                if row["zone"] == "closing" and not insertion.get("anchors_tc", {}).get("crawl"):
                    cursors["crawl"] = max(cursors["crawl"], cursors["closing"])
            blocks.append(dict(row, start=int(a), end=int(a + duration)))
        self._strip_rows = rows
        self.it["FilmStrip"].Text = filmstrip.render(start, film_start, film_end, blocks, fps,
                                                   self._strip_full, drop, indicative or not sess)

    def on_strip_link(self, ev):
        from urllib.parse import unquote
        link = ev.get("URL") or ev.get("Link") or ev.get("link") or ev.get("Text") or ev.get("text") or ""
        if link == "drfc:full":
            self._strip_full = not self._strip_full
            self.refresh_film_map()
            return
        if not link.startswith("drfc:section:"):
            return
        sid = unquote(link[len("drfc:section:"):])
        row = next((r for r in getattr(self, "_strip_rows", []) if r["id"] == sid), None)
        if not row:
            return
        if row["status"] == "removed":
            self.go(2)
            self.status("Elemento rimosso: selezionalo nell'elenco per conservarlo o rimuovere la clip.")
            return
        self.select_zone(row["zone"])
        secs, _i, _n = resolve_bridge.plan_sections(self.project, card_mode=self._card_mode())
        sec = next((s for s in secs if s["id"] == sid), None)
        if sec:
            seq_idx = next((i for i, seq in enumerate(self.project["sequences"]) if seq["id"] == sec["seq_id"]), None)
            # A crawl selects its first block; a card selects the original block ID.
            block_ids = sec["layout"]["cards"][0].get("blocks", []) if sec["layout"]["kind"] == "cards" else []
            idx = next((i for i, r in enumerate(self.rows) if r["seq"] == seq_idx and r.get("block") is not None
                        and (not block_ids or self.project["sequences"][seq_idx]["blocks"][r["block"]]["id"] in block_ids)), -1)
            if idx >= 0:
                self.select(idx, focus=True)

    def _scope(self):
        scope = self._idx("OperationScope")
        if scope == 1:
            if not self.zone:
                raise ValueError("Seleziona una zona dalla barra del film.")
            return {"zones": [self.zone]}
        if scope == 2:
            try:
                item = self.it["Sections"].CurrentItem()
                sid = item.Text[2]
            except Exception:
                raise ValueError("Seleziona un elemento nell'elenco della timeline.")
            return {"section_ids": [sid]}
        return {}

    def set_insert_page(self, page):
        self.it["InsertSetup"].MaximumSize = [16777215, (32, 340, 220)[page]]
        self._insert_page = page
        self.it["InsertSetup"].CurrentIndex = page
        self.update_visibility()

    def cancel_operation(self):
        self.pending_operation = None
        self.set_insert_page(0)

    def prepare_operation(self, operation, setup_done=False):
        self.ui_to_project()
        sess = self._session()
        if not sess:
            self.status(self.T("msg.no_resolve"))
            return
        scope = self._scope()
        self._maybe_timeline_format()
        rows, issues, notes = sess.review(self.project, card_mode=self._card_mode(), **scope)
        rows = [r for r in rows if r["status"] == "new"] if operation == "generate" else [r for r in rows if r["status"] in ("changed", "trimmed")]
        if not rows:
            self.status("Nessun elemento da generare." if operation == "generate" else "Nessun elemento da aggiornare. Verifica gli stati nell'elenco.")
            self.cancel_operation()
            self.refresh_sections()
            return
        if operation == "generate" and not setup_done:
            settings = self.project.get("insertion") or {}
            tc = sess.timeline.GetCurrentTimecode()
            end = self._frame_tc(sess.timeline.GetEndFrame() + 1, sess.timeline_format()["fps"], sess.timeline_format()["drop_frame"])
            for z in workspace.ZONES:
                self.it["Anchor_" + z].Text = settings.get("anchors_tc", {}).get(z, tc if z in ("opening", "head") else end)
            durations = {z: sum(r["frames"] for r in rows if r["zone"] == z) for z in workspace.ZONES}
            base = sess.record_frame("playhead")
            ending = sess.timeline.GetEndFrame() + 1
            for z, frame in (("head", base + durations["opening"]), ("crawl", ending + durations["closing"])):
                if z not in settings.get("anchors_tc", {}):
                    self.it["Anchor_" + z].Text = self._frame_tc(frame, sess.timeline_format()["fps"], sess.timeline_format()["drop_frame"])
            self.it["FilmEnd"].Text = settings.get("film_end", end)
            self.it["FilmStart"].Text = settings.get("film_start", "01:00:02:00")
            self.it["LeaderEnd"].Text = settings.get("leader_end", "01:00:02:00")
            self.set_insert_page(1)
            return
        options = {"operation": operation, "card_mode": self._card_mode(),
                   "duration_policy": "preserve" if self.it["PreserveDuration"].Checked else "calculated", **scope}
        lines = [self.W("generate") if operation == "generate" else self.W("update"),
                 "Nuove tracce sopra l'ultima; clip viola; nessuno spostamento del montaggio." if operation == "generate" else
                 "Posizioni conservate. Le nuove durate calcolate richiedono una clip su una nuova traccia superiore."]
        if operation == "generate":
            fmt = sess.timeline_format()
            anchors_tc = {z: self.it["Anchor_" + z].Text.strip() for z in workspace.ZONES}
            anchors = {z: sess.tc_to_frames(t, fmt["fps"], fmt["drop_frame"]) for z, t in anchors_tc.items()}
            film_tc = self.it["FilmStart"].Text.strip()
            film = sess.tc_to_frames(film_tc, fmt["fps"], fmt["drop_frame"])
            film_end_tc = self.it["FilmEnd"].Text.strip()
            film_end = sess.tc_to_frames(film_end_tc, fmt["fps"], fmt["drop_frame"])
            if film_end <= film:
                raise ValueError("La fine del film deve seguire il suo inizio.")
            before = self.it["BeforeFilm"].Checked
            protect = self.it["ProtectLeader"].Checked
            # Explicit leader endpoint: moving the film must not expand the protected interval.
            leader_tc = self.it["LeaderEnd"].Text.strip()
            leader = sess.tc_to_frames(leader_tc, fmt["fps"], fmt["drop_frame"]) if protect else None
            if leader is not None and leader > film:
                raise ValueError("La fine del frameleader deve precedere l'inizio del film.")
            offsets = {}
            for r in rows:
                z = r["zone"]
                start = anchors[z] + offsets.get(z, 0)
                offsets[z] = offsets.get(z, 0) + r["frames"]
                if start < sess.timeline.GetStartFrame() or (leader is not None and start < leader):
                    raise ValueError("Inserimento dentro il frameleader o prima della timeline: correggi i timecode.")
                if before and z in ("opening", "head") and start + r["frames"] > film:
                    raise ValueError("Spazio insufficiente prima del film: servono almeno %.2fs nella zona %s. Sposta il film manualmente e aggiorna il suo inizio." % (offsets[z] / fmt["fps"], z))
                lines.append("+ %s · %s · %.2fs" % (r["label"], self._frame_tc(start, fmt["fps"], fmt["drop_frame"]), r["frames"] / fmt["fps"]))
            options.update(anchors=anchors, protected_until=leader, film_start=film, before_film=before)
            self.project["insertion"] = {"anchors_tc": anchors_tc, "film_start": film_tc, "film_end": film_end_tc, "leader_end": leader_tc}
        else:
            lines += ["↻ %s · %d → %d frame%s" % (r["label"], r["current_frames"], r["frames"],
                      " (durata timeline conservata)" if options["duration_policy"] == "preserve" else "") for r in rows]
        lines += [i["message"] for i in issues] + notes
        # Bind the action to exactly the reviewed sections, timeline and data snapshot.
        options["section_ids"] = [r["id"] for r in rows]
        self.pending_operation = {"options": options, "snapshot": self._snapshot(),
                                  "timeline": sess._uid(sess.timeline),
                                  "positions": [(r["id"], r.get("current_start"), r.get("current_frames")) for r in rows]}
        self.it["OperationReview"].PlainText = "\n".join(lines)
        self.it["ConfirmRemoval"].Enabled = False
        self.it["ConfirmRemoval"].Checked = False
        self.set_insert_page(2)

    @staticmethod
    def _frame_tc(frame, fps, drop=False):
        return filmstrip.timecode(frame, fps, drop)

    def prepare_removed(self, delete):
        self.ui_to_project()
        sess = self._session()
        if not sess:
            return
        try:
            sid = self.it["Sections"].CurrentItem().Text[2]
        except Exception:
            raise ValueError("Seleziona l'elemento rosso da gestire.")
        rows, _i, _n = sess.review(self.project, card_mode=self._card_mode())
        row = next((r for r in rows if r["id"] == sid and r["status"] == "removed"), None)
        if not row:
            raise ValueError("L'elemento selezionato non è stato eliminato dal configuratore.")
        self.pending_operation = {"removed": sid, "delete": delete, "snapshot": self._snapshot(), "timeline": sess._uid(sess.timeline)}
        self.it["OperationReview"].PlainText = ("Rimuovi la clip collegata senza ripple: " if delete else "Conserva la clip e scollegala: ") + row["label"]
        self.it["ConfirmRemoval"].Enabled = delete
        self.it["ConfirmRemoval"].Checked = False
        self.set_insert_page(2)

    def apply_operation(self, ev):
        pending = self.pending_operation
        if not pending:
            return
        self.ui_to_project()
        sess = self._session()
        if sess._uid(sess.timeline) != pending["timeline"] or self._snapshot() != pending["snapshot"]:
            self.cancel_operation()
            raise ValueError("Progetto o timeline cambiati: prepara di nuovo il riepilogo.")
        if "removed" in pending:
            if pending["delete"] and not self.it["ConfirmRemoval"].Checked:
                raise ValueError("Conferma la rimozione della clip collegata.")
            sess.resolve_removed(self.project, pending["removed"], pending["delete"])
        else:
            rows, _i, _n = sess.review(self.project, card_mode=self._card_mode(), section_ids=pending["options"]["section_ids"])
            positions = [(r["id"], r.get("current_start"), r.get("current_frames")) for r in rows]
            if positions != pending["positions"]:
                self.cancel_operation()
                raise ValueError("Le clip sono cambiate in timeline: prepara di nuovo il riepilogo.")
            res = sess.sync(self.project, self._work_dir(), progress=self.status, **pending["options"])
            self._report(res["issues"], [("✓ " if r["ok"] else "✖ ") + r["message"] for r in res["sections"]] + res["notes"] + sess.log)
        self.cancel_operation()
        if self.path:
            model.save(self.project, self.path)
            self.saved_snapshot = self._snapshot()
        self.refresh_sections()
        self.refresh_film_map()

    # ------------------------------------------------------------------ helpers
    def T(self, key, **kw):
        return i18n.ui_text(self.lang, key, **kw)

    def L(self):
        return "it" if self.lang == "it" else "en"

    def status(self, text):
        try:
            self.it["Status"].Text = text
        except Exception:
            pass

    def row_sel(self):
        return self.rows[self.sel] if 0 <= self.sel < len(self.rows) else None

    def block(self):
        r = self.row_sel()
        return outline.block_of(self.project, r) if r else None

    def seq(self):
        seqs = self.project["sequences"]
        if not seqs:
            seqs.append(model.new_sequence("end", "crawl", "Titoli di coda"))
        r = self.row_sel()
        i = r["seq"] if r else self.seq_idx
        return seqs[max(0, min(i, len(seqs) - 1))]

    def _combo(self, cid, labels, index=0):
        c = self.it[cid]
        c.Clear()
        for l in labels:
            c.AddItem(l)
        c.CurrentIndex = max(0, min(index, len(labels) - 1)) if labels else 0

    def _on(self, cid, event, fn):
        if cid not in self.win.GetItems():
            return
        def wrapped(ev):
            if self.busy:
                return
            try:
                before = self._snapshot()
                fn(ev)
                if before != self._snapshot():
                    self.refresh_film_map()
            except Exception as e:  # mai chiudere il pannello per un errore
                self.status("Errore: %s (dettagli in %s)" % (e, log.path()))
                log.exception("%s.%s" % (cid, event))
                traceback.print_exc()
        setattr(getattr(self.win.On, cid), event, wrapped)

    def _idx(self, cid):
        """Indice corrente di un menu (>= 0). Un menu vuoto vale -1 in Qt."""
        try:
            return max(0, int(self.it[cid].CurrentIndex))
        except Exception:
            return 0

    # ------------------------------------------------------------------ finestra
    def build(self):
        self._widget_visibility = {}
        self._build_page = self._build_editor = self._build_aspect = None
        ui = _WorkspaceUI(self)
        T = self.T
        button = lambda props: ui.Button(dict({"Weight": 0, "MaximumSize": [16777215, 40]}, **props))
        checkbox = lambda props: ui.CheckBox(dict({"Weight": 0}, **props))
        combo = lambda props: ui.ComboBox(dict({"MinimumSize": [0, 28], "MaximumSize": [240, 36]}, **props))
        L = lambda text, **kw: ui.Label(dict({"Text": text, "Weight": 0}, **kw))
        lw = {"MinimumSize": [150, 0]}

        def row(*children, **kw):
            return ui.HGroup(dict({"Weight": 0}, **kw), list(children))

        def help_label(key):
            return ui.Label({"Text": T(key), "WordWrap": True, "Weight": 0,
                             "StyleSheet": "color:#e0b04a; padding:4px 0 8px 0;"})

        def make_nav():
            return row(
            button({"ID": "Step0", "Text": "Progetto" if self.lang == "it" else "Project", "Checkable": True}),
            button({"ID": "Step1", "Text": "Editor", "Checkable": True}),
            button({"ID": "Step2", "Text": "Timeline", "Checkable": True}),
            button({"ID": "Step3", "Text": "Aspetto" if self.lang == "it" else "Appearance", "Checkable": True}),
            ui.HGap(0, 1),
            button({"ID": "Open", "Text": T("project.open")}),
            button({"ID": "Save", "Text": T("project.save")}),
            button({"ID": "SaveAs", "Text": T("project.save_as")}),
        )

        # ------------------------------------------------------------ passo 1
        self._build_page = 0
        e_rows = []
        for chunk in (UI_ELEMENTS[0:3], UI_ELEMENTS[3:6], UI_ELEMENTS[6:9]):
            e_rows.append(row(*[checkbox({"ID": "E_" + k, "Text": T("v3.e_" + k)}) for k, _v in chunk]))
        p1 = ui.VGroup([
            help_label("v3.help1"),
            row(L(T("v3.title"), **lw), ui.LineEdit({"ID": "Title"})),
            row(L(T("project.year")), ui.SpinBox({"ID": "Year", "Minimum": 1895, "Maximum": 2200, "Weight": 0}),
                L(T("project.owner")), ui.LineEdit({"ID": "Owner"}), L(T("project.language")), combo({"ID": "Lang", "Weight": 0})),
            row(L(T("guided.work"), **lw), combo({"ID": "Work"}), L(T("guided.territory")), combo({"ID": "Territory"})),
            row(L(T("guided.destination"), **lw), combo({"ID": "Dest"}),
                button({"ID": "DestFromTl", "Text": T("guided.from_timeline"), "Weight": 0})),
            ui.VGap(6),
            checkbox({"ID": "Placeholders", "Text": T("v3.fill"), "Checked": True}),
            ui.VGap(6),
            L(T("v3.what")),
        ] + e_rows + [
            L(T("v3.always"), StyleSheet="color:#9a9aa3;"),
            ui.VGap(0, 1),
            ui.Label({"ID": "ProjInfo", "Text": "", "WordWrap": True, "Weight": 0, "StyleSheet": "color:#9a9aa3;"}),
            row(button({"ID": "Continue", "Text": T("v3.continue"), "MinimumSize": [260, 36]}), ui.HGap(0, 1),
                button({"ID": "Create", "Text": T("v3.create"), "MinimumSize": [260, 40]})),
        ])

        # ------------------------------------------------------------ passo 2
        self._build_page = 1
        self._build_editor = ED_HINT
        ed_hint = ui.VGroup([ui.Label({"ID": "Help", "Text": T("v3.edit_hint"), "WordWrap": True, "Weight": 0,
                                       "StyleSheet": "color:#9a9aa3;"}), ui.VGap(0, 1)])
        self._build_page = 1
        self._build_editor = ED_ENTRY
        ed_entry = ui.VGroup([
            row(L(T("rows.dept")), combo({"ID": "RDept"})),
            row(L(T("rows.role")), combo({"ID": "RRole"})),
            row(L(""), ui.LineEdit({"ID": "RRoleText", "PlaceholderText": T("rows.custom")})),
            row(L(T("rows.names")), ui.LineEdit({"ID": "RNames", "PlaceholderText": T("rows.names_hint"),
                                                 "Events": {"ReturnPressed": True}})),
            row(button({"ID": "RSave", "Text": T("v3.save"), "MinimumSize": [120, 30]}), button({"ID": "RAdd", "Text": T("v3.add_below")})),
            row(button({"ID": "RDel", "Text": T("v3.del_entry")}), button({"ID": "RBreak", "Text": T("v3.new_col")})),
            row(button({"ID": "EntryPrev", "Text": "←"}), button({"ID": "EntryNext", "Text": "→"})),
            ui.VGap(0, 1),
        ])
        self._build_page = 1
        self._build_editor = ED_TEXT
        ed_text = ui.VGroup([
            L(T("v3.text_help")),
            ui.TextEdit({"ID": "BlockText", "AcceptRichText": False}),
            L(T("v3.section_title")),
            combo({"ID": "Heading"}),
            ui.LineEdit({"ID": "HeadingText", "Weight": 0}),
            row(L(T("data.arrangement")), combo({"ID": "Arr"})),
            row(button({"ID": "TSave", "Text": T("v3.save"), "MinimumSize": [120, 30]})),
        ])
        self._build_page = 1
        self._build_editor = ED_LOGOS
        ed_logos = ui.VGroup([
            row(L(T("logos.pick")), combo({"ID": "LogoPick"}), button({"ID": "LogoAdd", "Text": T("logos.add"), "Weight": 0})),
            button({"ID": "LogoPng", "Text": T("logos.own")}),
            button({"ID": "LogoImport", "Text": T("logos.import")}),
            button({"ID": "LogoPage", "Text": T("logos.page")}),
            button({"ID": "LogoUpdate", "Text": T("logos.update")}),
            ui.TextEdit({"ID": "LogoText", "ReadOnly": True}),
            ui.VGap(0, 1),
        ])
        self._build_page = 1
        self._build_editor = ED_LAURELS
        ed_laurels = ui.VGroup([
            row(L(T("laurels.festival")), combo({"ID": "LFest"})),
            row(L(T("laurels.status")), combo({"ID": "LStatus"})),
            row(L(T("laurels.section")), combo({"ID": "LSection"})),
            row(L(T("laurels.year")), ui.SpinBox({"ID": "LYear", "Minimum": 1932, "Maximum": 2200, "Value": 2026}),
                L(T("laurels.award")), ui.LineEdit({"ID": "LAward"})),
            row(button({"ID": "LAdd", "Text": T("laurels.add")}), button({"ID": "LOfficial", "Text": T("laurels.official")})),
            ui.VGap(0, 1),
        ])
        self._build_page = 1
        self._build_editor = ED_COMPANY
        ed_company = ui.VGroup([
            row(L(self.W("company_name")), ui.LineEdit({"ID": "CompanyName"})),
            row(L(self.W("company_relation")), combo({"ID": "CompanyRelation"})),
            checkbox({"ID": "CompanyContract", "Text": self.W("company_contract")}),
            L(self.W("company_statement")),
            ui.TextEdit({"ID": "CompanyStatement", "AcceptRichText": False, "MinimumSize": [250, 65], "MaximumSize": [16777215, 100], "Weight": 0}),
            row(L("Fonte" if self.lang == "it" else "Source"), ui.LineEdit({"ID": "CompanySource"})),
            checkbox({"ID": "CompanyApproved", "Text": self.W("company_approved")}),
            L(self.W("company_note"), WordWrap=True, MinimumSize=[0, 40], StyleSheet="color:#9a9aa3;"),
            button({"ID": "CompanySave", "Text": T("project.save")}),
            ui.VGap(0, 1),
        ])
        self._build_editor = None
        p2 = ui.VGroup([
            L("Seleziona una zona nella barra, poi modifica i suoi elementi. Salva non cambia selezione." if self.lang == "it" else "Select a film zone, then edit its elements. Save keeps the current selection.", WordWrap=True),

            ui.HGroup([
                ui.VGroup({"Weight": 1, "MinimumSize": [300, 0], "MaximumSize": [380, 16777215]}, [
                    ui.Tree({"ID": "Outline", "MinimumSize": [230, 200], "MaximumSize": [320, 16777215], "SortingEnabled": False, "Events": {"ItemClicked": True}}),
                    row(button({"ID": "Up", "Text": T("v3.sec_up")}), button({"ID": "Down", "Text": T("v3.sec_down")}),
                        button({"ID": "DelSec", "Text": T("v3.sec_del")})),
                    combo({"ID": "AddElement"}),
                    button({"ID": "AddEl", "Text": T("data.add"), "Weight": 0}),
                    button({"ID": "AddCompany", "Text": self.W("add_company")}),
                    button({"ID": "MoreTools", "Text": "Altri strumenti ▾" if self.lang == "it" else "More tools ▾"}),
                    ui.Label({"ID": "PhCount", "Text": "", "Weight": 0, "StyleSheet": "color:#e0b04a;"}),
                ]),
                ui.VGroup({"Weight": 1.2, "MinimumSize": [330, 0]}, [
                    L(self.W("content_proof")),
                    ui.VGap(0, 1),
                    ui.TextEdit({"ID": "ContentProof", "ReadOnly": True, "AcceptRichText": True,
                                 "MinimumSize": [400, 220], "MaximumSize": [16777215, 280],
                                 "StyleSheet": "background:#07090d; color:#f1f1f1; border:1px solid #3c4656; border-radius:8px; padding:30px;"}),
                    ui.VGap(0, 1),
                    L(self.W("proof_note"), WordWrap=True, MinimumSize=[0, 60], StyleSheet="color:#9a9aa3;"),
                    button({"ID": "PreviewEditor", "Text": self.W("animated_preview")}),
                ]),
                ui.VGroup({"Weight": 1, "MinimumSize": [300, 0], "MaximumSize": [440, 16777215]}, [
                    ui.Label({"ID": "EdTitle", "Text": "", "Weight": 0, "StyleSheet": "font-weight:bold;"}),
                    ui.Stack({"ID": "EdStack", "MaximumSize": [380, 500]}, [ed_hint, ed_entry, ed_text, ed_logos, ed_laurels, ed_company]),
                ]),
            ]),
            row(button({"ID": "Back1", "Text": "← Progetto" if self.lang == "it" else "← Project"}), ui.HGap(0, 1), button({"ID": "Next1", "Text": "Timeline →",
                                                                                               "MinimumSize": [160, 34]})),
        ])

        # ------------------------------------------------------------ passo 3
        self._build_page = 2
        p3 = ui.VGroup([
            L(self.W("timeline_help"), WordWrap=True),
            ui.Tree({"ID": "Sections", "MinimumSize": [0, 70], "MaximumSize": [16777215, 120], "SortingEnabled": False, "Events": {"ItemClicked": True}}),
            row(L(T("generate.where")), combo({"ID": "Where"}),
                checkbox({"ID": "UseTl", "Text": T("project.from_timeline"), "Checked": True})),
            row(combo({"ID": "OperationScope"}),
                button({"ID": "GenerateNew", "Text": self.W("generate"), "MinimumSize": [220, 40]}),
                button({"ID": "SyncChanged", "Text": self.W("update"), "MinimumSize": [220, 40]})),
            checkbox({"ID": "PreserveDuration", "Text": self.W("preserve_duration"), "Checked": True}),
            row(button({"ID": "RemoveLinked", "Text": self.W("remove_linked")}),
                button({"ID": "DetachLinked", "Text": self.W("detach_linked")})),
            ui.Stack({"ID": "InsertSetup", "MaximumSize": [16777215, 32]}, [
                ui.Label({"Text": self.W("review_hint"), "WordWrap": True}),
                ui.VGroup([
                    L(self.W("first_generation")),
                    checkbox({"ID": "ProtectLeader", "Text": self.W("protect_leader"), "Checked": True}),
                    row(L(self.W("film_start")), ui.LineEdit({"ID": "FilmStart", "Text": "01:00:02:00"})),
                    row(L(self.W("film_end")), ui.LineEdit({"ID": "FilmEnd", "Text": "01:30:00:00"})),
                    row(L(self.W("leader_end")), ui.LineEdit({"ID": "LeaderEnd", "Text": "01:00:02:00"})),
                    checkbox({"ID": "BeforeFilm", "Text": self.W("before_film")}),
                    L(self.W("manual_shift"), WordWrap=True, StyleSheet="color:#e0b04a;"),
                    *[row(L(workspace.ZONE_LABELS[self.L()][i]), ui.LineEdit({"ID": "Anchor_" + z}))
                      for i, z in enumerate(workspace.ZONES)],
                    button({"ID": "PrepareInsert", "Text": self.W("prepare_insert")}),
                ]),
                ui.VGroup([
                    ui.TextEdit({"ID": "OperationReview", "ReadOnly": True, "MinimumSize": [0, 80], "MaximumSize": [16777215, 150]}),
                    checkbox({"ID": "ConfirmRemoval", "Text": self.W("confirm_removal")}),
                    row(button({"ID": "CancelOperation", "Text": self.W("cancel")}),
                        button({"ID": "ApplyOperation", "Text": self.W("apply_operation")})),
                ]),
            ]),
            row(button({"ID": "Preview", "Text": T("generate.preview")}), button({"ID": "Check", "Text": T("generate.check")}),
                button({"ID": "Export", "Text": T("generate.export")})),
            L(T("generate.results")),
            ui.TextEdit({"ID": "Results", "ReadOnly": True, "MinimumSize": [0, 50], "MaximumSize": [16777215, 85]}),
            row(button({"ID": "Back2", "Text": T("v3.back")}), ui.HGap(0, 1)),
        ])

        # ------------------------------------------------------------ aspetto e avanzate
        self._build_page = 3
        self._build_aspect = 0
        a_look = ui.VGroup([
            row(L(T("guided.destination"), **lw), combo({"ID": "SDest"})),
            row(L(T("style.theme"), **lw), combo({"ID": "Theme"}), L(T("style.fontset")), combo({"ID": "Fontset"})),
            row(L(T("style.density"), **lw), combo({"ID": "Density"}), L(T("style.leading")), combo({"ID": "Leading"})),
            row(L(T("style.background"), **lw), combo({"ID": "Bg"}), L(T("style.color")), ui.LineEdit({"ID": "BgColor"}),
                ui.LineEdit({"ID": "BgColor2"})),
            row(L(T("style.bg_media"), **lw), ui.LineEdit({"ID": "BgMedia"}), button({"ID": "BgPick", "Text": "…", "Weight": 0}),
                L(T("style.dim")), ui.DoubleSpinBox({"ID": "BgDim", "Minimum": 0, "Maximum": 1, "SingleStep": 0.05, "Decimals": 2}),
                L(T("style.blur")), ui.DoubleSpinBox({"ID": "BgBlur", "Minimum": 0, "Maximum": 100, "Decimals": 0})),
            row(L(T("style.split"), **lw), combo({"ID": "Split"}), L(T("style.text_lane")),
                ui.SpinBox({"ID": "Lane", "Minimum": 30, "Maximum": 80})),
            ui.VGap(0, 1),
        ])
        self._build_page = 3
        self._build_aspect = 1
        a_styles = ui.VGroup([
            row(L(T("style.override"), **lw), combo({"ID": "StyleKey"})),
            row(L(T("style.family"), **lw), combo({"ID": "SFamily", "Editable": True}), L(T("style.font_style")),
                ui.LineEdit({"ID": "SStyle"})),
            row(L(T("style.size"), **lw), ui.DoubleSpinBox({"ID": "SSize", "Minimum": 6, "Maximum": 400, "Decimals": 1}),
                L(T("style.color")), ui.LineEdit({"ID": "SColor"}), L(T("style.case")), combo({"ID": "SCase"})),
            row(L(T("style.tracking"), **lw), ui.DoubleSpinBox({"ID": "STrack", "Minimum": 0.5, "Maximum": 3, "SingleStep": 0.02, "Decimals": 2}),
                L(T("style.line_spacing")), ui.DoubleSpinBox({"ID": "SLine", "Minimum": 0.6, "Maximum": 3, "SingleStep": 0.05, "Decimals": 2})),
            row(ui.HGap(0, 1), button({"ID": "SReset", "Text": T("style.reset"), "Weight": 0}),
                button({"ID": "SApply", "Text": T("style.apply"), "Weight": 0})),
            ui.VGap(0, 1),
        ])
        self._build_page = 3
        self._build_aspect = 2
        a_timing = ui.VGroup([
            row(L(T("timing.speed"), **lw), combo({"ID": "Speed"}), ui.SpinBox({"ID": "Px", "Minimum": 1, "Maximum": 60, "Weight": 0})),
            row(L(T("timing.end_mode"), **lw), combo({"ID": "EndMode"}), L(T("timing.hold_last_s")),
                ui.DoubleSpinBox({"ID": "HoldLast", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1})),
            row(L(T("timing.lead_in"), **lw), ui.DoubleSpinBox({"ID": "LeadIn", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2}),
                L(T("timing.lead_out")), ui.DoubleSpinBox({"ID": "LeadOut", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2})),
            row(L(T("timing.card_pace"), **lw), combo({"ID": "Pace"}), L(T("timing.fade")),
                ui.DoubleSpinBox({"ID": "Fade", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2}),
                L(T("timing.gap")), ui.DoubleSpinBox({"ID": "Gap", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2})),
            L(T("timing.per_sequence")),
            row(L(T("data.sequence"), **lw), combo({"ID": "TSeq"})),
            row(L(T("timing.fit"), **lw), combo({"ID": "Fit"}), L(T("timing.target")),
                ui.DoubleSpinBox({"ID": "Target", "Minimum": 0, "Maximum": 3600, "SingleStep": 1, "Decimals": 2})),
            row(ui.HGap(0, 1), button({"ID": "Calc", "Text": T("timing.result"), "Weight": 0})),
            ui.TextEdit({"ID": "TimingOut", "ReadOnly": True}),
        ])
        self._build_page = 3
        self._build_aspect = 3
        a_work = ui.VGroup([
            row(L(T("project.original_title"), **lw), ui.LineEdit({"ID": "OrigTitle"}), L(T("project.country")),
                ui.LineEdit({"ID": "Country", "Weight": 0.4})),
            row(L(T("project.ui_language"), **lw), combo({"ID": "UiLang"})),
            L(T("project.funding")),
            row(*[checkbox({"ID": "F_" + f, "Text": validate.FUNDING_LABELS.get(f, f)}) for f in FUNDING[:6]]),
            row(*[checkbox({"ID": "F_" + f, "Text": validate.FUNDING_LABELS.get(f, f)}) for f in FUNDING[6:]]),
            row(checkbox({"ID": "AiUsed", "Text": T("project.ai_used"), "Weight": 0}), L(T("project.ai_uses")), ui.LineEdit({"ID": "AiUses"})),
            ui.VGap(0, 1),
        ])
        self._build_page = 3
        self._build_aspect = 4
        a_more = ui.VGroup([
            row(L(T("style.render_mode"), **lw), combo({"ID": "Render"}), L(T("style.axis")),
                ui.SpinBox({"ID": "Axis", "Minimum": 20, "Maximum": 80})),
            row(L(T("generate.card_mode"), **lw), combo({"ID": "CardMode"})),
            row(button({"ID": "Lock", "Text": T("generate.lock")}), button({"ID": "SyncAll", "Text": self.W("update")}),
                button({"ID": "Calibrate", "Text": T("generate.calibrate")})),
            L(T("v3.sec_options")),
            row(L(T("data.hold"), **lw), ui.DoubleSpinBox({"ID": "Hold", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1}),
                L(T("data.before")), ui.DoubleSpinBox({"ID": "Before", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1}),
                L(T("data.after")), ui.DoubleSpinBox({"ID": "After", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1})),
            row(L(self.W("zone"), **lw), combo({"ID": "BlockZone"})),
            row(L(T("data.position"), **lw), combo({"ID": "Position"}), L(T("data.order")), combo({"ID": "Order"}),
                L(T("data.columns")), combo({"ID": "Columns"})),
            row(checkbox({"ID": "PageBreak", "Text": T("data.page_break")}), checkbox({"ID": "Team", "Text": T("data.team")}),
                checkbox({"ID": "SideLane", "Text": T("data.side_lane")}), ui.HGap(0, 1),
                button({"ID": "SecApply", "Text": T("v3.sec_apply"), "Weight": 0})),
            ui.VGap(0, 1),
        ])
        self._build_aspect = None
        self._build_aspect = 5
        a_tools = ui.VGroup([
            L("Strumenti del progetto" if self.lang == "it" else "Project tools"),
            button({"ID": "Reorder", "Text": "Proponi ordine…" if self.lang == "it" else "Suggest order…"}),
            button({"ID": "Suggest", "Text": T("data.suggest")}),
            button({"ID": "Unfilled", "Text": T("v3.unfilled")}),
            button({"ID": "Import", "Text": T("data.import")}),
            ui.VGap(0, 1),
        ])
        self._build_aspect = None
        p4 = ui.VGroup([
            row(*[button({"ID": "A%d" % i, "Text": ("Strumenti" if self.lang == "it" else "Tools") if i == 5 else T("v3." + k), "Checkable": True})
                  for i, k in enumerate(["a_look", "a_styles", "a_timing", "a_work", "a_more", "a_tools"])]),
            ui.Stack({"ID": "AStack"}, [a_look, a_styles, a_timing, a_work, a_more, a_tools]),
        ])

        self._build_page = None
        self.windows = []
        self.it = {}
        for idx, page in enumerate((p1, p2, p3, p4)):
            main = ui.VGroup([
                row(L("<b style='font-size:18px;color:#f2f4f8'>FilmCredits</b>"),
                    L("MÉCENA  /  " + ("Editor dei titoli" if self.lang == "it" else "Film title editor")), ui.HGap(0, 1)),
                make_nav(),
                page,
                ui.Label({"ID": "FilmStrip", "Text": "", "WordWrap": False, "Weight": 0,
                          "MinimumSize": [1100, 90], "MaximumSize": [16777215, 105],
                          "OpenExternalLinks": False, "Events": {"LinkActivated": True},
                          "StyleSheet": "background:#0e1219; border:1px solid #303a48; border-radius:6px; padding:8px;"}),
                row(button({"ID": "ZoneAll", "Text": "Tutte le zone" if self.lang == "it" else "All zones"}),
                    *[button({"ID": "Zone_" + z, "Text": workspace.ZONE_LABELS[self.L()][i], "MaximumSize": [16777215, 28]})
                      for i, z in enumerate(workspace.ZONES)]),
                ui.Label({"ID": "FilePath", "Text": "", "Weight": 0, "WordWrap": True}),
                row(L("✓ " + self.W("legend"), StyleSheet="color:#9a9aa3;"), ui.HGap(0, 1),
                    ui.Label({"ID": "SaveState", "Text": "", "Weight": 0})),
                ui.Label({"ID": "Status", "Text": "", "Weight": 0, "WordWrap": True, "StyleSheet": "color:#e0b04a;"}),
            ])
            win = self.disp.AddWindow({"ID": "DRFCView%d" % idx, "WindowTitle": "FilmCredits · Mécena",
                                       "Geometry": [25, 30, 1380, 810], "StyleSheet": UI_STYLESHEET}, main)
            self.windows.append(win)
            self.it.update(win.GetItems())
        self.win = self.windows[0]
        class PageState:
            CurrentIndex = 0
        self.it["Stack"] = PageState()
        self._populate_static()
        self.set_insert_page(0)
        for idx, win in enumerate(self.windows):
            self.win = win
            self._window_id = "DRFCView%d" % idx
            self._bind()
        self.win = self.windows[0]
        self.it.update(self.win.GetItems())
        self.load_project_to_ui()
        self.go(0 if self.fresh else 1)
        self.refresh_film_map()

    def _tree_header(self, cid, labels, widths):
        tree = self.it[cid]
        tree.ColumnCount = len(labels)
        hdr = tree.NewItem()
        for i, k in enumerate(labels):
            hdr.Text[i] = k
        tree.SetHeaderItem(hdr)
        for i, w in enumerate(widths):
            tree.ColumnWidth[i] = w

    def _populate_static(self):
        T, L = self.T, self.L()
        self.busy = True
        self._combo("CompanyRelation", ["Distribuzione", "Produzione", "Coproduzione", "Collaborazione", "Sostegno"] if self.lang == "it" else ["Distribution", "Production", "Coproduction", "Collaboration", "Support"])
        self._combo("OperationScope", [self.W("scope_all"), self.W("scope_zone"), self.W("scope_selected")])
        self._combo("BlockZone", [self.W("automatic")] + list(workspace.ZONE_LABELS[self.L()]))
        self._combo("Work", [guide.WORK_LABELS[L][w] for w in guide.WORK_TYPES])
        self._combo("Territory", [guide.TERRITORY_LABELS[L][t] for t in guide.TERRITORIES])
        dlabels = [design.label(design.destinations()[d], L) for d in self.dests]
        self._combo("Dest", dlabels)
        self._combo("SDest", dlabels)
        self._combo("Lang", list(i18n.LANGUAGES))
        self._combo("UiLang", list(i18n.LANGUAGES), list(i18n.LANGUAGES).index(self.lang) if self.lang in i18n.LANGUAGES else 0)
        self._combo("AddElement", [guide.ELEMENT_LABELS[L][e] for e in guide.ELEMENTS])
        self._combo("RDept", [T("rows.any_dept")] + [i18n.department_label(d, self.project["meta"]["language"]) for d in self.depts])
        self._combo("Arr", [T("arr." + a) for a in ARRANGEMENTS])
        self._combo("Columns", COLUMNS)
        self._combo("Position", POSITIONS)
        self._combo("Order", ORDERS)
        self.headings = [""] + ["dept:" + k for k in i18n.roles()["departments"]] + \
            ["h:" + k for k in i18n.phrases("en")["headers"]]
        self._combo("Heading", [h if not h else "%s — %s" % (h, _heading(h, self.project["meta"]["language"]))
                                for h in self.headings])
        self._combo("LogoPick", ["%s — %s" % (e["name"], e.get("tag", "")) for e in logos.registry()["logos"]])
        self._combo("LFest", [laurels.festivals()["festivals"][f]["name"] for f in self.festivals])
        self._combo("LStatus", [laurels.festivals()["status"][s].get(self.lang, s) for s in STATUS_KEYS])
        self._fill_sections_combo()
        self.themes = list(layout.themes().keys())
        self._combo("Theme", [layout.themes()[t]["label"].get(self.lang, t) for t in self.themes])
        self._combo("Fontset", [T("style.fontset_theme")] + [design.label(design.fontsets()[f], L) for f in self.fontsets])
        self._combo("Density", [T("style.density_" + d) for d in DENSITIES])
        self._combo("Leading", [T("style.leading_" + d) for d in LEADINGS])
        self._combo("Bg", [T("style.bg_" + b) for b in BACKGROUNDS])
        self._combo("Render", [T("style.render_" + r) for r in RENDER])
        self._combo("Split", [T("style.split_none"), T("style.split_left"), T("style.split_right")])
        self._combo("StyleKey", STYLE_KEYS)
        fams = sorted({f[0] for fs in design.fontsets().values() for k, f in fs.items() if isinstance(f, list)})
        self._combo("SFamily", fams)
        self._combo("SCase", CASES)
        self._combo("Speed", [T("timing." + s) for s in SPEEDS])
        self._combo("Fit", [T("timing.fit_" + f) for f in FITS])
        self._combo("EndMode", [T("timing." + e) for e in END_MODES])
        self._combo("Pace", [T("timing." + p) for p in PACES])
        self._combo("Where", [T("generate." + w) for w in WHERE])
        self._combo("CardMode", [T("generate." + c) for c in CARD_MODES])
        self._tree_header("Outline", ["#", T("v3.rows_header"), T("v3.names_header")], [0, 250, 0])
        self._tree_header("Sections", [T("generate.col_section"), T("generate.col_status"), "id"], [420, 140, 200])
        self.busy = False

    def _fill_sections_combo(self):
        f = self.festivals[self.it["LFest"].CurrentIndex] if self.festivals else None
        secs = laurels.festivals()["festivals"].get(f, {}).get("sections", {}) if f else {}
        self.section_keys = [""] + list(secs.keys())
        self._combo("LSection", ["—"] + list(secs.values()))

    def _fill_roles(self, keep=None):
        di = self._idx("RDept")
        dept = self.depts[di - 1] if di > 0 else None
        lang = self.project["meta"]["language"]
        choices = outline.role_choices(lang, dept)
        self.role_keys = [k for k, _l in choices]
        self._combo("RRole", ["%s %s" % (CUSTOM, self.T("rows.custom"))] + [l for _k, l in choices])
        if keep in self.role_keys:
            self.it["RRole"].CurrentIndex = self.role_keys.index(keep) + 1

    def _bind(self):
        getattr(self.win.On, self._window_id).Close = lambda ev: self.close_views()
        b = self._on
        for i in range(4):
            b("Step%d" % i, "Clicked", (lambda idx: lambda ev: self.go(idx))(i))
        for i in range(6):
            b("A%d" % i, "Clicked", (lambda idx: lambda ev: self.go_aspect(idx))(i))
        b("Back1", "Clicked", lambda ev: self.go(0))
        b("Next1", "Clicked", lambda ev: self.go(2))
        b("Back2", "Clicked", lambda ev: self.go(1))
        b("Work", "CurrentIndexChanged", self.on_work)
        b("Territory", "CurrentIndexChanged", self.on_work)
        b("DestFromTl", "Clicked", self.on_dest_from_tl)
        b("Create", "Clicked", self.on_create)
        b("Continue", "Clicked", lambda ev: self.go(1))
        b("Open", "Clicked", self.on_open)
        b("Save", "Clicked", lambda ev: self.on_save(False))
        b("SaveAs", "Clicked", lambda ev: self.on_save(True))
        b("UiLang", "CurrentIndexChanged", self.on_ui_lang)
        b("Outline", "ItemClicked", self.on_outline_click)
        b("EntryPrev", "Clicked", lambda ev: self.navigate_entry(-1))
        b("EntryNext", "Clicked", lambda ev: self.navigate_entry(1))
        b("PreviewEditor", "Clicked", self.on_preview)
        b("FilmStrip", "LinkActivated", self.on_strip_link)
        b("ZoneAll", "Clicked", lambda ev: self.select_zone(None))
        for z in workspace.ZONES:
            b("Zone_" + z, "Clicked", (lambda zone: lambda ev: self.select_zone(zone))(z))
        b("GenerateNew", "Clicked", lambda ev: self.prepare_operation("generate"))
        b("PrepareInsert", "Clicked", lambda ev: self.prepare_operation("generate", setup_done=True))
        b("ApplyOperation", "Clicked", self.apply_operation)
        b("CancelOperation", "Clicked", lambda ev: self.cancel_operation())
        b("RemoveLinked", "Clicked", lambda ev: self.prepare_removed(True))
        b("DetachLinked", "Clicked", lambda ev: self.prepare_removed(False))
        b("Up", "Clicked", lambda ev: self.on_move(-1))
        b("Down", "Clicked", lambda ev: self.on_move(1))
        b("DelSec", "Clicked", self.on_del_section)
        b("AddEl", "Clicked", self.on_add_element)
        b("Reorder", "Clicked", self.on_reorder)
        b("Suggest", "Clicked", self.on_suggest)
        b("Unfilled", "Clicked", self.on_unfilled)
        b("Import", "Clicked", self.on_import)
        b("RDept", "CurrentIndexChanged", lambda ev: self._fill_roles())
        b("RSave", "Clicked", lambda ev: self.on_entry("save"))
        b("RNames", "ReturnPressed", lambda ev: self.on_pending_edit(ev))
        b("RAdd", "Clicked", lambda ev: self.on_entry("add"))
        b("RDel", "Clicked", lambda ev: self.on_entry("del"))
        b("RBreak", "Clicked", lambda ev: self.on_entry("break"))
        b("CompanySave", "Clicked", lambda ev: self.on_save(False))
        b("AddCompany", "Clicked", lambda ev: self.on_add_company())
        b("MoreTools", "Clicked", lambda ev: self.toggle_more_tools())
        b("CompanyRelation", "CurrentIndexChanged", self.on_pending_edit)
        b("CompanyContract", "Clicked", self.on_pending_edit)
        b("CompanyApproved", "Clicked", self.on_pending_edit)
        b("TSave", "Clicked", self.on_text_save)
        for cid in ("RNames", "RRoleText", "BlockText", "Title", "Owner", "CompanyName", "CompanyStatement", "CompanySource"):
            b(cid, "TextChanged", self.on_pending_edit)
        b("LogoAdd", "Clicked", self.on_logo_add)
        b("LogoPng", "Clicked", self.on_logo_png)
        b("LogoImport", "Clicked", self.on_logo_import)
        b("LogoPage", "Clicked", self.on_logo_page)
        b("LogoUpdate", "Clicked", self.on_logo_update)
        b("LFest", "CurrentIndexChanged", lambda ev: self._fill_sections_combo())
        b("LAdd", "Clicked", self.on_laurel_add)
        b("LOfficial", "Clicked", self.on_laurel_official)
        b("SDest", "CurrentIndexChanged", self.on_style_dest)
        b("BgPick", "Clicked", self.on_bg_pick)
        b("StyleKey", "CurrentIndexChanged", lambda ev: self.load_style_override())
        b("SApply", "Clicked", self.on_style_apply)
        b("SReset", "Clicked", self.on_style_reset)
        b("TSeq", "CurrentIndexChanged", lambda ev: self.load_seq_timing())
        b("Calc", "Clicked", self.on_calc)
        b("Lock", "Clicked", self.on_lock)
        b("SyncChanged", "Clicked", lambda ev: self.prepare_operation("update"))
        b("SyncAll", "Clicked", lambda ev: self.prepare_operation("update"))
        b("Check", "Clicked", self.on_check)
        b("Preview", "Clicked", self.on_preview)
        b("Export", "Clicked", self.on_export)
        b("Calibrate", "Clicked", self.on_calibrate)
        b("SecApply", "Clicked", self.on_sec_apply)

    def go(self, idx):
        self.ui_to_project()
        self._current_page = idx
        self.it["Stack"].CurrentIndex = idx
        if hasattr(self, "windows"):
            for i, win in enumerate(self.windows):
                if i != idx:
                    win.Hide()
            self.win = self.windows[idx]
            self.it.update(self.win.GetItems())
            if getattr(self, "_view_shown", False):
                self.win.Show()
        for i in range(4):
            self.it["Step%d" % i].Checked = (i == idx)
        if idx == 1:
            self.refresh_outline()
        elif idx == 2:
            self.refresh_sections()
        elif idx == 3:
            self.go_aspect(self._aspect if hasattr(self, "_aspect") else 0)
        self.update_visibility()

    def go_aspect(self, i):
        self._aspect = i
        self.it["AStack"].CurrentIndex = i
        for k in range(6):
            self.it["A%d" % k].Checked = (k == i)
        self.update_visibility()
        if i == 2:
            self.on_calc(None)

    # ------------------------------------------------------------------ progetto <-> UI
    def load_project_to_ui(self):
        p, it = self.project, self.it
        self.busy = True
        m = p["meta"]
        if m.get("work_type") in guide.WORK_TYPES:
            it["Work"].CurrentIndex = guide.WORK_TYPES.index(m["work_type"])
        if m.get("territory") in guide.TERRITORIES:
            it["Territory"].CurrentIndex = guide.TERRITORIES.index(m["territory"])
        dest = p["format"].get("destination") or design.guess_destination(p["format"]["width"], p["format"]["height"])
        it["Dest"].CurrentIndex = it["SDest"].CurrentIndex = self.dests.index(dest)
        present = {guide.element_of(b) for s in p["sequences"] for b in s["blocks"]}
        for k, els in UI_ELEMENTS:
            it["E_" + k].Checked = any(e in present for e in els)
        it["Placeholders"].Checked = bool(m.get("placeholders", True))
        it["FilePath"].Text = os.path.basename(self.path) if self.path else ""
        it["ProjInfo"].Text = (self.T("v3.open_info", name=m.get("title") or os.path.basename(self.path or "") or "-")
                               if not self.fresh else self.T("v3.none_info"))
        it["Title"].Text = m.get("title", "")
        it["OrigTitle"].Text = m.get("original_title", "")
        it["Year"].Value = int(m.get("year") or 2026)
        it["Owner"].Text = m.get("copyright_owner", "")
        it["Country"].Text = m.get("country", "")
        it["Lang"].CurrentIndex = list(i18n.LANGUAGES).index(m.get("language", "it"))
        for f in FUNDING:
            it["F_" + f].Checked = f in (m.get("funding") or [])
        it["AiUsed"].Checked = bool(m.get("ai_used"))
        it["AiUses"].Text = m.get("ai_uses", "")
        st = p["style"]
        it["Theme"].CurrentIndex = self.themes.index(st.get("theme")) if st.get("theme") in self.themes else 0
        it["Fontset"].CurrentIndex = self.fontsets.index(st["fontset"]) + 1 if st.get("fontset") in self.fontsets else 0
        it["Density"].CurrentIndex = DENSITIES.index(st.get("density")) if st.get("density") in DENSITIES else 1
        it["Leading"].CurrentIndex = LEADINGS.index(st.get("leading")) if st.get("leading") in LEADINGS else 1
        bg = design.background(p["format"])
        raw = p["format"].get("background")
        mode = {"color": "color"}.get(bg["mode"], bg["mode"])
        if raw == "black" or (bg["mode"] == "color" and bg.get("color", "").upper() == "#000000"):
            mode = "black"
        elif raw == "white" or (bg["mode"] == "color" and bg.get("color", "").upper() == "#FFFFFF"):
            mode = "white"
        it["Bg"].CurrentIndex = BACKGROUNDS.index(mode) if mode in BACKGROUNDS else 0
        cols = bg.get("colors") or [bg.get("color", "#000000"), "#202020"]
        it["BgColor"].Text, it["BgColor2"].Text = cols[0], cols[-1] if len(cols) > 1 else "#202020"
        it["BgMedia"].Text = bg.get("path", "")
        it["BgDim"].Value = float(bg.get("dim", bg.get("opacity", 0.5)))
        it["BgBlur"].Value = float(bg.get("blur", 0))
        lay = p["layout"]
        it["Render"].CurrentIndex = RENDER.index(lay.get("render_mode", "auto"))
        it["Axis"].Value = int(round(float(lay.get("axis", 0.5)) * 100))
        it["Split"].CurrentIndex = SPLITS.index(lay.get("split", "none"))
        it["Lane"].Value = int(round(float(lay.get("text_lane", 0.5)) * 100))
        t = p["timing"]
        it["Speed"].CurrentIndex = SPEEDS.index(t.get("speed", "normal"))
        it["Px"].Value = int(t.get("px_per_frame") or 4)
        it["EndMode"].CurrentIndex = END_MODES.index(t.get("end_mode", "scroll_out"))
        it["HoldLast"].Value = float(t.get("hold_last_s") or 0)
        it["LeadIn"].Value = float(t.get("lead_in_s") or 0)
        it["LeadOut"].Value = float(t.get("lead_out_s") or 0)
        it["Pace"].CurrentIndex = PACES.index(t.get("card_pace", "normal"))
        it["Fade"].Value = float(t.get("card_fade_s", 0.5))
        it["Gap"].Value = float(t.get("card_gap_s", 0.25))
        names = ["%s (%s)" % (s.get("name", s["id"]), s["kind"]) for s in p["sequences"]]
        self._combo("TSeq", names, self.seq_idx)
        self.busy = False
        self._fill_roles()
        self.load_style_override()
        self.load_seq_timing()
        self.refresh_outline()

    def ui_to_project(self):
        if self.busy or not hasattr(self, "it"):
            return
        p, it = self.project, self.it
        self.commit_editor()
        m = p["meta"]
        m["title"] = it["Title"].Text
        m["original_title"] = it["OrigTitle"].Text
        m["year"] = int(it["Year"].Value)
        m["copyright_owner"] = it["Owner"].Text
        m["country"] = it["Country"].Text
        m["language"] = i18n.LANGUAGES[it["Lang"].CurrentIndex]
        m["funding"] = [f for f in FUNDING if it["F_" + f].Checked]
        m["ai_used"] = bool(it["AiUsed"].Checked)
        m["ai_uses"] = it["AiUses"].Text
        st = p["style"]
        st["theme"] = self.themes[it["Theme"].CurrentIndex]
        fi = it["Fontset"].CurrentIndex
        st["fontset"] = self.fontsets[fi - 1] if fi > 0 else None
        st["density"] = DENSITIES[it["Density"].CurrentIndex]
        st["leading"] = LEADINGS[it["Leading"].CurrentIndex]
        mode = BACKGROUNDS[it["Bg"].CurrentIndex]
        if mode in ("transparent", "black", "white"):
            p["format"]["background"] = mode
        elif mode == "color":
            p["format"]["background"] = {"mode": "color", "color": it["BgColor"].Text or "#000000"}
        elif mode == "gradient":
            p["format"]["background"] = {"mode": "gradient", "colors": [it["BgColor"].Text or "#000000", it["BgColor2"].Text or "#202020"]}
        elif mode == "media":
            p["format"]["background"] = {"mode": "media", "path": it["BgMedia"].Text, "dim": float(it["BgDim"].Value),
                                         "blur": float(it["BgBlur"].Value)}
        elif mode == "dim":
            p["format"]["background"] = {"mode": "dim", "opacity": float(it["BgDim"].Value)}
        elif mode == "panel":
            p["format"]["background"] = {"mode": "panel", "color": it["BgColor"].Text or "#000000",
                                         "opacity": float(it["BgDim"].Value) or 0.85}
        lay = p["layout"]
        lay["render_mode"] = RENDER[it["Render"].CurrentIndex]
        lay["axis"] = it["Axis"].Value / 100.0
        lay["split"] = SPLITS[it["Split"].CurrentIndex]
        lay["text_lane"] = it["Lane"].Value / 100.0
        t = p["timing"]
        t["speed"] = SPEEDS[it["Speed"].CurrentIndex]
        t["px_per_frame"] = int(it["Px"].Value)
        t["end_mode"] = END_MODES[it["EndMode"].CurrentIndex]
        t["hold_last_s"] = float(it["HoldLast"].Value)
        t["lead_in_s"] = float(it["LeadIn"].Value)
        t["lead_out_s"] = float(it["LeadOut"].Value)
        t["card_pace"] = PACES[it["Pace"].CurrentIndex]
        t["card_fade_s"] = float(it["Fade"].Value)
        t["card_gap_s"] = float(it["Gap"].Value)
        self.save_seq_timing()
        self._sync_ai_legal()

    def _sync_ai_legal(self):
        m = self.project["meta"]
        if not m.get("ai_used"):
            return
        for s in self.project["sequences"]:
            for b in s["blocks"]:
                for item in b.get("items", []) if b["type"] == "legal" else []:
                    if item.get("key") == "ai_disclosure":
                        item.setdefault("values", {})["uses"] = m.get("ai_uses", "")
                        b["enabled"] = True
                        return
        end = next((s for s in self.project["sequences"] if s["kind"] == "crawl"), None)
        if end is not None:
            end["blocks"].append(model.new_block("legal", items=[{"key": "ai_disclosure", "values": {"uses": m.get("ai_uses", "")}}]))
            guide.reorder(end, m.get("territory", "it"))

    # ------------------------------------------------------------------ passo 1
    def on_work(self, ev):
        # Gli eventi dei menu riempiti dal codice arrivano a RunLoop gia' avviato: se la scelta
        # coincide con il progetto non e' un'azione dell'utente e non si tocca niente.
        wt = guide.WORK_TYPES[self._idx("Work")]
        ter = guide.TERRITORIES[self._idx("Territory")]
        meta = self.project["meta"]
        if wt == meta.get("work_type") and ter == meta.get("territory"):
            return
        defaults = set(guide.DEFAULT_ELEMENTS.get(wt, []))
        for k, els in UI_ELEMENTS:
            self.it["E_" + k].Checked = any(e in defaults for e in els)
        pid = guide.preset_for(wt, ter)
        dest = presets.load_preset(pid).get("destination")
        if dest in self.dests:
            self.it["Dest"].CurrentIndex = self.dests.index(dest)

    def on_dest_from_tl(self, ev):
        if not self.resolve:
            self.status(self.T("msg.no_resolve"))
            return
        f = resolve_bridge.ResolveSession(self.resolve).timeline_format()
        d = design.guess_destination(f["width"], f["height"])
        self.it["Dest"].CurrentIndex = self.dests.index(d)
        self.status("%dx%d @ %s fps → %s" % (f["width"], f["height"], f["fps"], design.label(design.destinations()[d], self.L())))

    def on_create(self, ev):
        keep = {"title": self.it["Title"].Text.strip(), "year": int(self.it["Year"].Value),
                "copyright_owner": self.it["Owner"].Text}
        for k in ("original_title", "country", "funding", "ai_used", "ai_uses"):
            if self.project["meta"].get(k):
                keep[k] = self.project["meta"][k]
        wt = guide.WORK_TYPES[self._idx("Work")]
        ter = guide.TERRITORIES[self._idx("Territory")]
        els = list(ALWAYS)
        for k, group in UI_ELEMENTS:
            if self.it["E_" + k].Checked:
                els += group
        ph = bool(self.it["Placeholders"].Checked)
        dest = self.dests[self._idx("Dest")]
        self.project = guide.new_project(wt, ter, els, destination=dest, use_placeholders=ph, **keep)
        self.project["meta"]["placeholders"] = ph
        self.path = None
        self.saved_snapshot = None
        self.zone = None
        self.fresh = False
        self.seq_idx, self.sel = 0, -1
        log.write("progetto creato: %s/%s, %d sezioni, segnaposto=%s" % (
            wt, ter, sum(len(s["blocks"]) for s in self.project["sequences"]), ph))
        self.load_project_to_ui()
        self.go(1)
        self.status(self.T("v3.msg_created"))

    def _request_file(self, save=False, pattern="*.drfc.json", title=""):
        opts = {"FReqB_Saving": save, "FReqS_Filter": "%s|%s" % (pattern, pattern), "FReqS_Title": title}
        start = os.path.dirname(self.path) if self.path else os.path.expanduser("~")
        try:
            return self.fu.RequestFile(start, "", opts)
        except Exception:
            return self.fu.RequestFile(start)

    def on_open(self, ev):
        path = self._request_file(False)
        if not path:
            return
        self.project = model.load(path)
        self.path = path
        self.saved_snapshot = self._snapshot()
        self.zone = None
        self.fresh = False
        self.seq_idx, self.sel = 0, -1
        self.settings["last_project"] = path
        save_settings(self.settings)
        self.load_project_to_ui()
        self.go(1)
        self.status(self.T("msg.opened", path=path))

    def on_save(self, as_new):
        self.ui_to_project()
        path = self.path
        if as_new or not path:
            path = self._request_file(True)
            if not path:
                return
            if not path.endswith(".json"):
                path += ".drfc.json"
            self.project["_base_dir"] = os.path.dirname(os.path.abspath(path))
        model.save(self.project, path)
        self.path = path
        self.it["FilePath"].Text = path
        self.settings["last_project"] = path
        save_settings(self.settings)
        self.saved_snapshot = self._snapshot()
        self.refresh_film_map()
        self.status(self.T("msg.saved", path=path))

    def on_ui_lang(self, ev):
        new = i18n.LANGUAGES[self._idx("UiLang")]
        if new == self.lang:
            return  # evento generato dal riempimento del menu, non una scelta dell'utente
        log.write("cambio lingua interfaccia %s -> %s" % (self.lang, new))
        self.ui_to_project()
        self.settings["ui_lang"] = new
        save_settings(self.settings)
        self.restart = True
        self.disp.ExitLoop()

    # ------------------------------------------------------------------ passo 2: elenco
    def refresh_outline(self, select=None):
        """Ricostruisce l'elenco; `select` = (seq, block, row) da riselezionare."""
        if not hasattr(self, "it"):
            return
        lang = self.project["meta"]["language"]
        self.rows = outline.build(self.project, lang)
        self.rows = [r for r in self.rows if r["kind"] != "item"]
        if self.zone:
            self.rows = [r for r in self.rows if r.get("block") is not None and
                         workspace.zone_of(self.project["sequences"][r["seq"]],
                                           outline.block_of(self.project, r)) == self.zone]
        tree = self.it["Outline"]
        tree.Clear()
        self.items = []
        for i, r in enumerate(self.rows):
            t = tree.NewItem()
            t.Text[0] = str(i + 1)
            block = outline.block_of(self.project, r)
            label = r["label"]
            if block and block["type"] == "card" and block.get("note"):
                if "distribuzione:" in block["note"].lower():
                    label = "Distribuzione"
                elif "coproduzione" in block["note"].lower():
                    label = "Coproduzione / collaborazione"
                elif "produzione:" in block["note"].lower():
                    label = "Produzione"
            if block and block.get("company"):
                label = block["company"].get("name") or self.W("company_panel")
            t.Text[1] = label
            t.Text[2] = r["value"]
            tree.AddTopLevelItem(t)
            self.items.append(t)
        n = placeholders.count(self.project)
        self.it["PhCount"].Text = self.T("v3.ph_count", n=n) if n else self.T("v3.ph_none")
        if select is not None:
            self.select(outline.find(self.rows, *select), focus=True)
        else:
            self.sel = min(self.sel, len(self.rows) - 1)
            if self.sel >= 0:
                self.select(self.sel, focus=True)
            else:
                self.show_editor(ED_HINT)

    def _focus(self, idx):
        try:
            self.it["Outline"].CurrentItem = self.items[idx]
        except Exception:
            pass  # la selezione evidenziata e' un di piu'

    def on_outline_click(self, ev):
        self.commit_editor()
        try:
            idx = int(ev["item"].Text[0]) - 1
        except Exception:
            return
        self.select(idx)

    def show_editor(self, page):
        self._editor_page = page
        self.it["EdStack"].CurrentIndex = page
        self.update_visibility()

    def select(self, idx, focus=False):
        """Seleziona una riga dell'elenco e mostra l'editor adatto."""
        if not (0 <= idx < len(self.rows)):
            self.sel = -1
            self.show_editor(ED_HINT)
            self.it["ContentProof"].HTML = ""
            return
        self.sel = idx
        if focus:
            self._focus(idx)
        row = self.rows[idx]
        self.seq_idx = row["seq"]
        lang = self.project["meta"]["language"]
        b = outline.block_of(self.project, row)
        self.busy = True
        if row["kind"] == "seq" or b is None:
            self.it["EdTitle"].Text = ""
            self.show_editor(ED_HINT)
        elif row["kind"] == "entry" and "company" not in b:
            role, names = outline.entry_values(self.project, row)
            dept = i18n.role_department(role)
            self.it["RDept"].CurrentIndex = self.depts.index(dept) + 1 if dept in self.depts else 0
            self.busy = False
            self._fill_roles(keep=role)
            self.busy = True
            if role not in self.role_keys:
                self.it["RRole"].CurrentIndex = 0
                self.it["RRoleText"].Text = role
            else:
                self.it["RRoleText"].Text = ""
            self.it["RNames"].Text = ", ".join(names)
            self.it["EdTitle"].Text = phrases_role(role, lang)
            self.show_editor(ED_ENTRY)
        elif b["type"] == "card" and (b.get("company") is not None or any(word in b.get("note", "").lower() for word in ("distribuzione:", "produzione:", "coproduzione con"))):
            company = b.get("company", {})
            self.it["EdTitle"].Text = self.W("company_panel")
            self.it["CompanyName"].Text = company.get("name", "")
            self.it["CompanyRelation"].CurrentIndex = company.get("relation", 0 if "distribuzione" in b.get("note", "").lower() else 2 if "coproduzione" in b.get("note", "").lower() else 1)
            # Preserve existing free text until a deliberate company edit.
            self.it["CompanyContract"].Checked = company.get("contractual", True)
            self.it["CompanyStatement"].PlainText = company.get("statement", "\n".join(l.get("text", "") for l in b.get("lines", [])))
            self.it["CompanySource"].Text = company.get("source", "")
            self.it["CompanyApproved"].Checked = company.get("approved", False)
            self.show_editor(ED_COMPANY)
        elif b["type"] == "logos":
            self.it["EdTitle"].Text = self.T("types.logos")
            self.it["LogoText"].PlainText = self.T("help.logos")
            self.show_editor(ED_LOGOS)
        elif b["type"] == "laurels":
            self.it["EdTitle"].Text = self.T("types.laurels")
            self.show_editor(ED_LAURELS)
        else:
            self.it["EdTitle"].Text = blocktext.summary(b, lang)[0] or self.T("types." + b["type"])
            self.it["BlockText"].PlainText = blocktext.render(b)
            heading = b.get("heading", "")
            if heading in self.headings:
                self.it["Heading"].CurrentIndex = self.headings.index(heading)
                self.it["HeadingText"].Text = ""
            else:
                self.it["Heading"].CurrentIndex = 0
                self.it["HeadingText"].Text = heading or ""
            arr = layout.list_arrangement(b) if b["type"] == "list" else (
                "pair" if b.get("layout") == "two_column" else "pair")
            self.it["Arr"].CurrentIndex = ARRANGEMENTS.index(arr) if arr in ARRANGEMENTS else 0
            self.show_editor(ED_TEXT)
        self.busy = False
        self.load_section_options()
        self.it["ContentProof"].HTML = workspace.content_html(b, lang)

    def _row_from_ui(self):
        ri = self._idx("RRole")
        role = self.it["RRoleText"].Text.strip() if ri <= 0 else self.role_keys[ri - 1]
        names = blocktext.split_names(self.it["RNames"].Text)
        return role, names

    def _next_entry(self, idx):
        for j in range(idx + 1, len(self.rows)):
            if self.rows[j]["kind"] == "entry":
                return j
        return idx

    def on_entry(self, action):
        row = self.row_sel()
        if row is None or row["kind"] != "entry":
            self.status(self.T("v3.msg_no_row"))
            return
        sel = (row["seq"], row["block"], row["row"])
        if action == "save":
            role, names = self._row_from_ui()
            outline.set_entry(self.project, row, role, names)
            # aggiorna solo la riga (niente ricostruzione: la lista non salta) e passa alla voce successiva
            lang = self.project["meta"]["language"]
            role2, names2 = outline.entry_values(self.project, row)
            row["label"] = row["label"][:len(row["label"]) - len(row["label"].lstrip())] + phrases_role(role2, lang)
            row["value"] = ", ".join(names2)
            try:
                self.items[self.sel].Text[1] = row["label"]
                self.items[self.sel].Text[2] = row["value"]
            except Exception:
                pass
            n = placeholders.count(self.project)
            self.it["PhCount"].Text = self.T("v3.ph_count", n=n) if n else self.T("v3.ph_none")
            self.status(self.T("v3.msg_row_saved"))
            self.it["ContentProof"].HTML = workspace.content_html(self.block(), lang)
            self.on_save(False)
            return
        if action == "add":
            role, names = self._row_from_ui()
            ph = placeholders.texts(self.project["meta"]["language"])["name"]
            if not outline.add_entry_after(self.project, row, role, names or [ph]):
                self.status(self.T("v3.msg_only_dept"))
                return
            self.refresh_outline(select=(sel[0], sel[1], sel[2] + 1))
            self.status(self.T("v3.msg_added_below"))
        elif action == "del":
            kind = outline.delete_entry(self.project, row)
            self.sel = -1
            self.refresh_outline(select=(sel[0], sel[1], max(0, sel[2] - 1)) if kind == "entry" else None)
        elif action == "break":
            b = outline.block_of(self.project, row)
            if b["type"] != "list":
                self.status(self.T("v3.msg_only_dept"))
                return
            b["rows"].insert(row["row"] + 1, {"break": True})
            if not str(b.get("arrangement") or "").startswith("pairs_"):
                b["arrangement"] = "pairs_2"
            self.refresh_outline(select=sel)

    def on_text_save(self, ev):
        row = self.row_sel()
        b = self.block()
        if b is None:
            self.status(self.T("v3.msg_no_row"))
            return
        t = b["type"]
        blocktext.parse(b, self.it["BlockText"].PlainText)
        heading = self.it["HeadingText"].Text.strip() or self.headings[self._idx("Heading")]
        if "heading" in BLOCK_TYPES[t]["fields"]:
            b["heading"] = heading
        arr = ARRANGEMENTS[self._idx("Arr")]
        if t == "list":
            b["arrangement"] = arr
        if t == "credit":
            b["layout"] = "two_column" if arr == "pair" else "stacked"
        self.refresh_outline(select=(row["seq"], row["block"], None))
        self.on_save(False)

    def on_move(self, d):
        row = self.row_sel()
        if row is None or row.get("block") is None:
            self.status(self.T("v3.msg_no_row"))
            return
        new = outline.move_section(self.project, row, d)
        self.refresh_outline(select=(row["seq"], new, None))

    def on_del_section(self, ev):
        row = self.row_sel()
        if row is None or row.get("block") is None:
            self.status(self.T("v3.msg_no_row"))
            return
        outline.delete_section(self.project, row)
        self.sel = -1
        self.refresh_outline(select=(row["seq"], max(0, row["block"] - 1), None))

    def on_add_element(self, ev):
        e = guide.ELEMENTS[self._idx("AddElement")]
        n = guide.add_element(self.project, e)
        if self.project["meta"].get("placeholders", True):
            placeholders.fill(self.project)
        self.refresh_outline()
        self.status(self.T("msg.added", n=n))

    def on_reorder(self, ev):
        for s in self.project["sequences"]:
            guide.reorder(s, self.project["meta"].get("territory", "it"))
        self.sel = -1
        self.refresh_outline()
        self.status(self.T("msg.reordered"))

    def on_suggest(self, ev):
        sugg = guide.suggestions(self.project)
        L = self.L()
        self.show_editor(ED_HINT)
        if not sugg:
            self.it["Help"].Text = self.T("msg.nothing_missing")
            return
        self.it["Help"].Text = self.T("msg.suggestions") + "\n" + "\n".join(
            "• %s — %s" % (guide.ELEMENT_LABELS[L].get(e, e), why) for e, why in sugg)
        if sugg[0][0] in guide.ELEMENTS:
            self.it["AddElement"].CurrentIndex = guide.ELEMENTS.index(sugg[0][0])

    def on_unfilled(self, ev):
        n = placeholders.remove_unfilled(self.project)
        self.sel = -1
        self.refresh_outline()
        self.status(self.T("v3.msg_removed", n=n))

    def on_import(self, ev):
        path = self._request_file(False, "*.csv;*.tsv;*.txt;*.xlsx")
        if not path:
            return
        n = io_import.import_file(self.project, path)
        self.refresh_outline()
        self.status(self.T("msg.imported", n=n))

    def on_template(self, ev):
        path = self._request_file(True, "*.csv")
        if path:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            io_import.write_template(path)
            self.status(path)

    # ------------------------------------------------------------------ loghi e allori
    def _logo_id(self):
        return self.logo_ids[self.it["LogoPick"].CurrentIndex]

    def on_logo_add(self, ev):
        b = self.block()
        if b is None or b["type"] != "logos":
            return
        lid = self._logo_id()
        b["items"] = [i for i in b["items"] if not placeholders.is_placeholder_logo(i.get("logo"))] + [{"logo": lid}]
        st = logos.status(lid)
        row = self.row_sel()
        self.refresh_outline(select=(row["seq"], row["block"], None))
        if st != "ready":
            e = logos.entry(lid) or {}
            self.it["LogoText"].PlainText = "%s: %s\n%s\n%s" % (
                e.get("name", lid), logos.STATUS_LABEL["it" if self.lang == "it" else "en"][st],
                e.get("usage_notes", ""), e.get("request_contact") or e.get("official_page", ""))

    def on_logo_png(self, ev):
        b = self.block()
        path = self._request_file(False, "*.png;*.tif;*.jpg")
        if not path or b is None:
            return
        b["items"] = [i for i in b["items"] if not placeholders.is_placeholder_logo(i.get("logo"))] + [{"path": path}]
        row = self.row_sel()
        self.refresh_outline(select=(row["seq"], row["block"], None))

    def on_logo_import(self, ev):
        path = self._request_file(False, "*.png;*.zip;*.tif;*.jpg")
        if path:
            stored = logos.import_file(self._logo_id(), path)
            self.status(self.T("msg.logo_imported", n=len(stored)))

    def on_logo_page(self, ev):
        url = logos.open_page(self._logo_id())
        self.status(url or "-")

    def on_logo_update(self, ev):
        msgs = []
        try:
            msgs.append("Registro: %d enti" % logos.update_registry())
        except Exception as e:
            msgs.append("Registro non aggiornato: %s" % e)
        res = logos.update(log=lambda m: None)
        msgs += ["%s: %s" % (k, v) for k, v in res.items()]
        self.it["LogoText"].PlainText = "\n".join(msgs[:40])

    def on_laurel_add(self, ev):
        b = self.block()
        if b is None or b["type"] != "laurels":
            return
        item = {"festival": self.festivals[self._idx("LFest")], "status": STATUS_KEYS[self._idx("LStatus")],
                "year": int(self.it["LYear"].Value)}
        sec = self.section_keys[self._idx("LSection")]
        if sec:
            item["section"] = sec
        if self.it["LAward"].Text.strip():
            item["award"] = self.it["LAward"].Text.strip()
        b["items"] = [i for i in b["items"] if not i.get("placeholder")] + [item]
        row = self.row_sel()
        self.refresh_outline(select=(row["seq"], row["block"], None))

    def on_laurel_official(self, ev):
        b = self.block()
        path = self._request_file(False, "*.png")
        if path and b is not None:
            b["items"] = [i for i in b["items"] if not i.get("placeholder")] + [{"path": path}]
            row = self.row_sel()
            self.refresh_outline(select=(row["seq"], row["block"], None))

    # ------------------------------------------------------------------ opzioni della sezione (avanzate)
    def load_section_options(self):
        b = self.block()
        it = self.it
        was = self.busy
        self.busy = True
        if b is not None:
            it["Hold"].Value = float(b.get("hold_s") or 0)
            it["Before"].Value = -1 if b.get("spacing_before") is None else float(b["spacing_before"])
            it["After"].Value = -1 if b.get("spacing_after") is None else float(b["spacing_after"])
            it["BlockZone"].CurrentIndex = workspace.ZONES.index(b["zone"]) + 1 if b.get("zone") in workspace.ZONES else 0
            it["PageBreak"].Checked = bool(b.get("page_break"))
            it["Team"].Checked = bool(b.get("team"))
            it["SideLane"].Checked = b.get("lane") == "side"
            p = b.get("position", "center")
            it["Position"].CurrentIndex = POSITIONS.index(p) if p in POSITIONS else 0
            it["Order"].CurrentIndex = ORDERS.index(b.get("order", "actor_character")) if b.get("order") in ORDERS else 0
            col = str(b.get("columns", b.get("per_row", "auto")))
            it["Columns"].CurrentIndex = COLUMNS.index(col) if col in COLUMNS else 0
        self.busy = was

    def on_sec_apply(self, ev):
        b = self.block()
        if b is None:
            self.status(self.T("v3.msg_no_row"))
            return
        it = self.it
        t = b["type"]
        b["hold_s"] = float(it["Hold"].Value)
        b["spacing_before"] = None if it["Before"].Value < 0 else float(it["Before"].Value)
        b["spacing_after"] = None if it["After"].Value < 0 else float(it["After"].Value)
        zi = self._idx("BlockZone")
        if zi:
            b["zone"] = workspace.ZONES[zi - 1]
        else:
            b.pop("zone", None)
        b["page_break"] = bool(it["PageBreak"].Checked)
        if t in ("credit", "card"):
            b["team"] = bool(it["Team"].Checked)
        if t == "media":
            b["lane"] = "side" if it["SideLane"].Checked else "main"
        if t == "card" or self.seq()["kind"] == "cards":
            b["position"] = POSITIONS[self._idx("Position")]
        if t == "cast":
            b["order"] = ORDERS[self._idx("Order")]
        if t in ("names", "agreements"):
            c = COLUMNS[self._idx("Columns")]
            b["columns"] = c if c == "auto" else int(c)
        if t == "logos":
            c = COLUMNS[self._idx("Columns")]
            b["per_row"] = c if c == "auto" else int(c)
        # Moving between a crawl and panels moves the data to a compatible sequence.
        if zi:
            zone = workspace.ZONES[zi - 1]
            current = self.seq()
            desired_kind = "crawl" if zone == "crawl" else "cards"
            if current["kind"] != desired_kind or (zone == "closing" and current.get("id") not in ("closing", "final")):
                target = next((seq for seq in self.project["sequences"] if seq.get("zone") == zone), None)
                if target is None:
                    target = model.new_sequence("zone_" + zone, desired_kind, workspace.ZONE_LABELS[self.L()][zi - 1])
                    target["zone"] = zone
                    self.project["sequences"].append(target)
                current["blocks"].remove(b)
                target["blocks"].append(b)
                self.sel = -1
                self.zone = zone
                self.refresh_outline(select=(self.project["sequences"].index(target), len(target["blocks"]) - 1, None))
        self.refresh_film_map()
        self.status("OK")

    # ------------------------------------------------------------------ stile e tempi
    def on_style_dest(self, ev):
        d = self.dests[self._idx("SDest")]
        f0 = self.project["format"]
        current = f0.get("destination") or design.guess_destination(f0["width"], f0["height"])
        if d == current:
            return  # nessuna scelta nuova (evento di riempimento del menu)
        design.apply_destination(self.project, d)
        self.busy = True
        self.it["Dest"].CurrentIndex = self.it["SDest"].CurrentIndex
        self.it["Speed"].CurrentIndex = SPEEDS.index(self.project["timing"]["speed"])
        self.busy = False
        f = self.project["format"]
        self.status("%dx%d @ %s fps" % (f["width"], f["height"], f["fps"]))

    def on_bg_pick(self, ev):
        path = self._request_file(False, "*.png;*.jpg;*.tif;*.mov;*.mp4")
        if path:
            self.it["BgMedia"].Text = path
            self.it["Bg"].CurrentIndex = BACKGROUNDS.index("media")

    def load_style_override(self):
        key = STYLE_KEYS[self.it["StyleKey"].CurrentIndex]
        th = layout.themes().get(self.project["style"]["theme"]) or layout.themes()["classic"]
        st = dict(th["styles"].get(key, {}))
        if self.project["style"].get("fontset"):
            st.update(design.fontset_style(self.project["style"]["fontset"], key))
        st.update(self.project["style"].get("overrides", {}).get(key, {}))
        it = self.it
        self.busy = True
        try:
            it["SFamily"].CurrentText = st.get("family", "")
        except Exception:
            pass
        it["SStyle"].Text = st.get("style", "Regular")
        it["SSize"].Value = float(st.get("size", 30))
        it["SColor"].Text = st.get("color", "#FFFFFF")
        it["SCase"].CurrentIndex = CASES.index(st.get("case", "none"))
        it["STrack"].Value = float(st.get("tracking", 1.0))
        it["SLine"].Value = float(st.get("line_spacing", 1.1))
        self.busy = False

    def on_style_apply(self, ev):
        key = STYLE_KEYS[self.it["StyleKey"].CurrentIndex]
        it = self.it
        self.project["style"].setdefault("overrides", {})[key] = {
            "family": it["SFamily"].CurrentText, "style": it["SStyle"].Text, "size": float(it["SSize"].Value),
            "color": it["SColor"].Text, "case": CASES[it["SCase"].CurrentIndex],
            "tracking": float(it["STrack"].Value), "line_spacing": float(it["SLine"].Value)}
        self.status("OK — %s" % key)

    def on_style_reset(self, ev):
        key = STYLE_KEYS[self.it["StyleKey"].CurrentIndex]
        self.project["style"].get("overrides", {}).pop(key, None)
        self.load_style_override()

    def _tseq(self):
        seqs = self.project["sequences"]
        i = self.it["TSeq"].CurrentIndex
        return seqs[i] if 0 <= i < len(seqs) else None

    def load_seq_timing(self):
        s = self._tseq()
        if s is None:
            return
        t = dict(self.project["timing"])
        t.update(s.get("timing") or {})
        self.busy = True
        self.it["Fit"].CurrentIndex = FITS.index(t.get("fit", "none")) if s.get("timing") else 0
        self.it["Target"].Value = float((s.get("timing") or {}).get("target_seconds") or 0)
        self.busy = False

    def save_seq_timing(self):
        s = self._tseq()
        if s is None:
            return
        fit = FITS[self.it["Fit"].CurrentIndex]
        target = float(self.it["Target"].Value)
        if fit == "none" or target <= 0:
            s.pop("timing", None)
        else:
            s["timing"] = {"fit": fit, "target_seconds": target}

    def on_calc(self, ev):
        self.ui_to_project()
        _c, results, issues = engine.solve_all(self.project)
        lines = []
        for seq, lay, tl, notes in results:
            secs = tl["total_frames"] / float(tl["fps"])
            if tl["kind"] == "crawl":
                lines.append("%s: %.2fs · %d px/frame · %d pause" % (seq.get("name", seq["id"]), secs, tl["speed_px"], len(tl["holds"])))
            else:
                lines.append("%s: %d cartelli · %.2fs" % (seq.get("name", seq["id"]), len(tl["cards"]), secs))
            lines += ["   " + n for n in notes]
        self.it["TimingOut"].PlainText = "\n".join(lines)

    # ------------------------------------------------------------------ passo 3
    def _card_mode(self):
        return CARD_MODES[self.it["CardMode"].CurrentIndex]

    def _session(self):
        if not self.resolve:
            return None
        return resolve_bridge.ResolveSession(self.resolve)

    def refresh_sections(self):
        self.ui_to_project()
        tree = self.it["Sections"]
        tree.Clear()
        sess = self._session()
        if sess is not None:
            rows = sess.section_status(self.project, card_mode=self._card_mode())
        else:
            secs, _i, _n = resolve_bridge.plan_sections(self.project, card_mode=self._card_mode())
            rows = [(s["id"], s["label"], "new") for s in secs]
        self.section_rows = rows
        for sid, label, st in rows:
            r = tree.NewItem()
            r.Text[0] = label
            r.Text[1], color = workspace.status_label(st, self.lang)
            try:
                r.TextColor[1] = self._rgba(color)
            except Exception:
                pass
            r.Text[2] = sid
            tree.AddTopLevelItem(r)

    def on_lock(self, ev):
        try:
            cur = self.it["Sections"].CurrentItem()
            sid = cur.Text[2]
        except Exception:
            self.status(self.T("msg.select_section"))
            return
        st = self.project.setdefault("render_state", {}).setdefault(sid, {})
        st["locked"] = not st.get("locked", False)
        self.refresh_sections()

    def _report(self, issues, extra=None):
        icons = {"error": "✖", "warning": "⚠", "info": "ℹ"}
        lines = list(extra or [])
        lines += ["%s %s%s" % (icons.get(i["level"], "-"), i["message"], (" [%s]" % i["block"]) if i.get("block") else "")
                  for i in issues]
        ne = sum(1 for i in issues if i["level"] == "error")
        nw = sum(1 for i in issues if i["level"] == "warning")
        lines.insert(0, "%d %s · %d %s" % (ne, self.T("generate.errors"), nw, self.T("generate.warnings")))
        self.it["Results"].PlainText = "\n".join(lines)

    def _maybe_timeline_format(self):
        if self.it["UseTl"].Checked and self.resolve:
            try:
                resolve_bridge.ResolveSession(self.resolve).apply_timeline_format(self.project)
            except Exception as e:
                self.status(str(e))

    def on_check(self, ev):
        self.ui_to_project()
        self._maybe_timeline_format()
        _c, results, issues = engine.solve_all(self.project)
        self._report(issues)

    def _work_dir(self):
        return resolve_bridge.default_work_dir(self.path)

    def on_preview(self, ev):
        self.ui_to_project()
        self._maybe_timeline_format()
        files, results, issues = engine.export(self.project, self._work_dir(), kinds=())
        self._report(issues)
        if files:
            webbrowser.open("file://" + os.path.abspath(files[-1]["path"]))

    def on_export(self, ev):
        self.ui_to_project()
        self._maybe_timeline_format()
        try:
            out = self.fu.RequestDir(self._work_dir())
        except Exception:
            out = None
        out = out or self._work_dir()
        files, results, issues = engine.export(self.project, out)
        self._report(issues, ["→ " + f["path"] for f in files])

    def on_sync(self, only_changed=True):
        self.prepare_operation("update")

    def on_calibrate(self, ev):
        from . import calibration
        calibration.reset()
        self.status(self.T("generate.recalibrate_done"))

    def run(self):
        """Ciclo finestra. Si rilancia solo dopo un reale cambio di lingua (max 5 volte)."""
        for attempt in range(5):
            self.restart = False
            log.write("avvio pannello (tentativo %d)" % (attempt + 1))
            self.build()
            self._view_shown = True
            self.win.Show()
            self.disp.RunLoop()
            log.write("pannello chiuso (restart=%s)" % self.restart)
            self.ui_to_project()
            self.win.Hide()
            if self.path:
                try:
                    model.save(self.project, self.path)
                except Exception:
                    log.exception("salvataggio alla chiusura")
            if not self.restart:
                break
            self.lang = self.settings.get("ui_lang", "it")


def phrases_role(role, lang):
    from . import phrases
    return phrases.role_text(role, lang)


def _heading(h, lang):
    from . import phrases
    try:
        return phrases.heading_text(h, lang)
    except KeyError:
        return h


def show_error(fusion, bmd, text):
    """Finestra minima con l'errore (invece di una finestra che sparisce)."""
    try:
        ui = fusion.UIManager
        disp = bmd.UIDispatcher(ui)
        win = disp.AddWindow({"ID": "DRFCErr", "WindowTitle": "DR-FilmCredits \u2013 errore", "Geometry": [200, 200, 760, 420]},
                             ui.VGroup([ui.Label({"Text": "Qualcosa non ha funzionato. Manda il file di log a Ivan:\n%s" % log.path(),
                                                  "WordWrap": True, "Weight": 0}),
                                        ui.TextEdit({"ID": "Err", "ReadOnly": True, "PlainText": text}),
                                        ui.Button({"ID": "Ok", "Text": "OK", "Weight": 0})]))
        win.On.DRFCErr.Close = lambda ev: disp.ExitLoop()
        win.On.Ok.Clicked = lambda ev: disp.ExitLoop()
        win.Show()
        disp.RunLoop()
        win.Hide()
    except Exception:
        log.exception("finestra di errore")
        print(text)


def main(fusion, bmd, resolve=None):
    try:
        Wizard(fusion, bmd, resolve).run()
    except Exception:
        text = log.exception("main")
        show_error(fusion, bmd, text)

