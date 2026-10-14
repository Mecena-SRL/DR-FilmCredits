"""Pannello guidato (UIManager di Resolve/Fusion): Progetto > Contenuti > Stile > Tempi > Genera.

Funziona dentro Resolve (Workspace > Scripts > DR-FilmCredits). Tutta la logica sta nei
moduli puri (model, blocktext, engine...): qui solo collegamento campi <-> progetto.
"""

import copy
import json
import os
import traceback
import webbrowser

from . import (__version__, blocktext, engine, fusion_constants, i18n, io_import, layout, model,
               presets, resolve_bridge)
from .model import BLOCK_TYPES

FUNDING = ["mic_tax_credit", "mic_selective", "cultural_interest", "film_commission", "creative_europe",
           "eurimages", "italian_tax_credit_foreign", "rai_cinema", "cnc", "ffa", "dfff", "icaa"]
SPEEDS = ["slow", "normal", "fast", "custom"]
FITS = ["none", "speed", "spacing"]
END_MODES = ["scroll_out", "hold_last"]
PACES = ["slow", "normal", "fast"]
LAYOUTS = ["stacked", "two_column"]
POSITIONS = ["center", "lower_third", "upper_third", "left", "right"]
ORDERS = ["actor_character", "character_actor"]
KINDS = ["location", "rental", "archive", "product", "artwork"]
COLUMNS = ["auto", "1", "2", "3", "4"]
CASES = ["none", "upper", "lower", "title"]
STYLE_KEYS = ["title", "heading", "role", "name", "character", "small", "legal", "card_role", "card_name"]
WHERE = ["playhead", "end", "start", "replace"]
SPLITS = ["none", "media_left", "media_right"]
RENDER = ["auto", "block", "line"]


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


class Wizard(object):
    def __init__(self, fusion, bmd, resolve=None):
        self.fu, self.bmd, self.resolve = fusion, bmd, resolve
        self.ui = fusion.UIManager
        self.disp = bmd.UIDispatcher(self.ui)
        self.settings = load_settings()
        self.lang = self.settings.get("ui_lang", "it")
        self.path = self.settings.get("last_project")
        self.project = None
        if self.path and os.path.exists(self.path):
            try:
                self.project = model.load(self.path)
            except Exception:
                self.project = None
        if self.project is None:
            self.path = None
            self.project = presets.project_from_preset("it_cinema")
        self.seq_idx, self.block_idx = 0, -1
        self.busy = False
        self.restart = False
        self.presets = presets.list_presets()
        self.role_keys = sorted(i18n.roles()["roles"].keys())

    # ------------------------------------------------------------------ helpers
    def T(self, key, **kw):
        return i18n.ui_text(self.lang, key, **kw)

    def status(self, text):
        try:
            self.it["Status"].Text = text
        except Exception:
            pass

    def seq(self):
        seqs = self.project["sequences"]
        if not seqs:
            seqs.append(model.new_sequence("end", "crawl", "End"))
        self.seq_idx = max(0, min(self.seq_idx, len(seqs) - 1))
        return seqs[self.seq_idx]

    def block(self):
        s = self.seq()
        if 0 <= self.block_idx < len(s["blocks"]):
            return s["blocks"][self.block_idx]
        return None

    def _combo(self, cid, labels, index=0):
        c = self.it[cid]
        c.Clear()
        for l in labels:
            c.AddItem(l)
        c.CurrentIndex = max(0, index)

    def _on(self, cid, event, fn):
        def wrapped(ev):
            if self.busy:
                return
            try:
                fn(ev)
            except Exception as e:  # mai chiudere il pannello per un errore
                self.status("Errore: %s" % e)
                traceback.print_exc()
        setattr(getattr(self.win.On, cid), event, wrapped)

    # ------------------------------------------------------------------ finestra
    def build(self):
        ui = self.ui
        T = self.T
        L = lambda text, **kw: ui.Label(dict({"Text": text, "Weight": 0}, **kw))
        lbl_w = {"MinimumSize": [150, 0]}

        def row(*children, **kw):
            return ui.HGroup(dict({"Weight": 0}, **kw), list(children))

        steps = ["project", "data", "style", "timing", "generate"]
        nav = ui.VGroup({"Weight": 0, "MinimumSize": [190, 0]},
                        [ui.Button({"ID": "Step%d" % i, "Text": T("steps." + s), "Checkable": True,
                                    "MinimumSize": [180, 34]}) for i, s in enumerate(steps)] +
                        [ui.VGap(0, 1), L("v" + __version__, Alignment={"AlignHCenter": True})])

        p_project = ui.VGroup([
            row(L(T("project.preset"), **lbl_w), ui.ComboBox({"ID": "Preset"}), ui.Button({"ID": "New", "Text": T("project.new"), "Weight": 0})),
            row(L(T("project.file"), **lbl_w), ui.LineEdit({"ID": "FilePath", "ReadOnly": True}),
                ui.Button({"ID": "Open", "Text": T("project.open"), "Weight": 0}),
                ui.Button({"ID": "Save", "Text": T("project.save"), "Weight": 0}),
                ui.Button({"ID": "SaveAs", "Text": T("project.save_as"), "Weight": 0})),
            row(L(T("project.title"), **lbl_w), ui.LineEdit({"ID": "Title"}), L(T("project.original_title")), ui.LineEdit({"ID": "OrigTitle"})),
            row(L(T("project.year"), **lbl_w), ui.SpinBox({"ID": "Year", "Minimum": 1895, "Maximum": 2200, "Weight": 0}),
                L(T("project.owner")), ui.LineEdit({"ID": "Owner"}), L(T("project.country")), ui.LineEdit({"ID": "Country", "Weight": 0.4})),
            row(L(T("project.language"), **lbl_w), ui.ComboBox({"ID": "Lang"}), L(T("project.ui_language")), ui.ComboBox({"ID": "UiLang"})),
            L(T("project.funding")),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[:6]]),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[6:]]),
            row(ui.CheckBox({"ID": "AiUsed", "Text": T("project.ai_used"), "Weight": 0}), L(T("project.ai_uses")), ui.LineEdit({"ID": "AiUses"})),
            L(T("project.notes")),
            ui.TextEdit({"ID": "Notes", "ReadOnly": True}),
        ])

        p_data = ui.HGroup([
            ui.VGroup({"Weight": 1}, [
                row(L(T("data.sequence")), ui.ComboBox({"ID": "Seq"}), ui.Button({"ID": "NewSeq", "Text": T("data.new_seq"), "Weight": 0})),
                ui.Tree({"ID": "Blocks", "SortingEnabled": False, "Events": {"ItemClicked": True, "CurrentItemChanged": True}}),
                row(ui.ComboBox({"ID": "AddType"}), ui.Button({"ID": "Add", "Text": T("data.add"), "Weight": 0})),
                row(ui.Button({"ID": "Up", "Text": T("data.up")}), ui.Button({"ID": "Down", "Text": T("data.down")}),
                    ui.Button({"ID": "Dup", "Text": T("data.dup")}), ui.Button({"ID": "Del", "Text": T("data.delete")}),
                    ui.Button({"ID": "Toggle", "Text": T("data.toggle")})),
                row(ui.Button({"ID": "Import", "Text": T("data.import")}), ui.Button({"ID": "Template", "Text": T("data.template")})),
            ]),
            ui.VGroup({"Weight": 1.4}, [
                L(T("data.content")),
                ui.TextEdit({"ID": "BlockText", "AcceptRichText": False, "Font": ui.Font({"Family": "Courier New", "PixelSize": 13})}),
                row(L(T("data.roles")), ui.ComboBox({"ID": "RoleHelper"}), ui.Button({"ID": "InsertRole", "Text": T("data.insert_role"), "Weight": 0})),
                row(L(T("data.heading")), ui.ComboBox({"ID": "Heading"}), ui.LineEdit({"ID": "HeadingText"})),
                row(L(T("data.layout")), ui.ComboBox({"ID": "Layout"}), L(T("data.kind")), ui.ComboBox({"ID": "Kind"}),
                    L(T("data.columns")), ui.ComboBox({"ID": "Columns"})),
                row(L(T("data.position")), ui.ComboBox({"ID": "Position"}), L(T("data.order")), ui.ComboBox({"ID": "Order"})),
                row(L(T("data.hold")), ui.DoubleSpinBox({"ID": "Hold", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1}),
                    L(T("data.before")), ui.DoubleSpinBox({"ID": "Before", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1}),
                    L(T("data.after")), ui.DoubleSpinBox({"ID": "After", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1})),
                row(ui.CheckBox({"ID": "PageBreak", "Text": T("data.page_break")}), ui.CheckBox({"ID": "Team", "Text": T("data.team")}),
                    ui.CheckBox({"ID": "SideLane", "Text": T("data.side_lane")}),
                    ui.HGap(0, 1), ui.Button({"ID": "Apply", "Text": T("data.apply"), "MinimumSize": [180, 30], "Weight": 0})),
                ui.Label({"ID": "Help", "Text": "", "WordWrap": True, "Weight": 0, "StyleSheet": "color: #9a9aa3;"}),
            ]),
        ])

        p_style = ui.VGroup([
            row(L(T("style.theme"), **lbl_w), ui.ComboBox({"ID": "Theme"}), L(T("style.render_mode")), ui.ComboBox({"ID": "Render"})),
            row(L(T("style.safe"), **lbl_w), ui.SpinBox({"ID": "Safe", "Minimum": 70, "Maximum": 100}),
                L(T("style.background")), ui.ComboBox({"ID": "Bg"}), L(T("style.axis")), ui.SpinBox({"ID": "Axis", "Minimum": 20, "Maximum": 80})),
            row(L(T("style.split"), **lbl_w), ui.ComboBox({"ID": "Split"}), L(T("style.text_lane")), ui.SpinBox({"ID": "Lane", "Minimum": 30, "Maximum": 80})),
            L(T("style.override")),
            row(L("", **lbl_w), ui.ComboBox({"ID": "StyleKey"})),
            row(L(T("style.family"), **lbl_w), ui.LineEdit({"ID": "SFamily"}), L(T("style.font_style")), ui.LineEdit({"ID": "SStyle"})),
            row(L(T("style.size"), **lbl_w), ui.DoubleSpinBox({"ID": "SSize", "Minimum": 6, "Maximum": 400, "Decimals": 1}),
                L(T("style.color")), ui.LineEdit({"ID": "SColor"}), L(T("style.case")), ui.ComboBox({"ID": "SCase"})),
            row(L(T("style.tracking"), **lbl_w), ui.DoubleSpinBox({"ID": "STrack", "Minimum": 0.5, "Maximum": 3, "SingleStep": 0.02, "Decimals": 2}),
                L(T("style.line_spacing")), ui.DoubleSpinBox({"ID": "SLine", "Minimum": 0.6, "Maximum": 3, "SingleStep": 0.05, "Decimals": 2})),
            row(ui.HGap(0, 1), ui.Button({"ID": "SReset", "Text": T("style.reset"), "Weight": 0}),
                ui.Button({"ID": "SApply", "Text": T("style.apply"), "Weight": 0})),
            ui.VGap(0, 1),
        ])

        p_timing = ui.VGroup([
            row(L(T("timing.speed"), **lbl_w), ui.ComboBox({"ID": "Speed"}),
                ui.SpinBox({"ID": "Px", "Minimum": 1, "Maximum": 60, "Weight": 0})),
            row(L(T("timing.end_mode"), **lbl_w), ui.ComboBox({"ID": "EndMode"}), L(T("timing.hold_last_s")),
                ui.DoubleSpinBox({"ID": "HoldLast", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1})),
            row(L(T("timing.lead_in"), **lbl_w), ui.DoubleSpinBox({"ID": "LeadIn", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2}),
                L(T("timing.lead_out")), ui.DoubleSpinBox({"ID": "LeadOut", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2})),
            row(L(T("timing.card_pace"), **lbl_w), ui.ComboBox({"ID": "Pace"}), L(T("timing.fade")),
                ui.DoubleSpinBox({"ID": "Fade", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2}),
                L(T("timing.gap")), ui.DoubleSpinBox({"ID": "Gap", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2})),
            L(T("timing.per_sequence")),
            row(L(T("data.sequence"), **lbl_w), ui.ComboBox({"ID": "TSeq"})),
            row(L(T("timing.fit"), **lbl_w), ui.ComboBox({"ID": "Fit"}), L(T("timing.target")),
                ui.DoubleSpinBox({"ID": "Target", "Minimum": 0, "Maximum": 3600, "SingleStep": 1, "Decimals": 2})),
            row(ui.HGap(0, 1), ui.Button({"ID": "Calc", "Text": T("timing.result"), "Weight": 0})),
            ui.TextEdit({"ID": "TimingOut", "ReadOnly": True}),
        ])

        p_gen = ui.VGroup([
            row(L(T("generate.sequence"), **lbl_w), ui.ComboBox({"ID": "GSeq"}), L(T("generate.where")), ui.ComboBox({"ID": "Where"}),
                L(T("generate.track")), ui.ComboBox({"ID": "Track"})),
            row(ui.CheckBox({"ID": "Replace", "Text": T("generate.replace"), "Checked": True}),
                ui.CheckBox({"ID": "UseTl", "Text": T("project.from_timeline"), "Checked": True})),
            row(ui.Button({"ID": "Check", "Text": T("generate.check")}), ui.Button({"ID": "Preview", "Text": T("generate.preview")}),
                ui.Button({"ID": "Insert", "Text": T("generate.insert"), "MinimumSize": [220, 40]}),
                ui.Button({"ID": "Export", "Text": T("generate.export")}), ui.Button({"ID": "Calibrate", "Text": T("generate.calibrate")})),
            L(T("generate.results")),
            ui.TextEdit({"ID": "Results", "ReadOnly": True}),
        ])

        layout_main = ui.VGroup([
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "<b style='font-size:16px'>%s</b>" % T("app.title"), "Weight": 0}),
                ui.Label({"Text": T("app.subtitle"), "StyleSheet": "color:#9a9aa3;"}),
            ]),
            ui.HGroup([nav, ui.Stack({"ID": "Stack"}, [p_project, p_data, p_style, p_timing, p_gen])]),
            ui.Label({"ID": "Status", "Text": "", "Weight": 0, "WordWrap": True, "StyleSheet": "color:#e0b04a;"}),
        ])
        self.win = self.disp.AddWindow({"ID": "DRFCWin", "WindowTitle": "DR-FilmCredits", "Geometry": [80, 60, 1180, 820]},
                                       layout_main)
        self.it = self.win.GetItems()
        self._populate_static()
        self._bind()
        self.load_project_to_ui()
        self.go(0)

    def _populate_static(self):
        T = self.T
        self.busy = True
        self._combo("Preset", [presets.preset_label(p, self.lang) for p in self.presets])
        self._combo("Lang", list(i18n.LANGUAGES))
        self._combo("UiLang", list(i18n.LANGUAGES), list(i18n.LANGUAGES).index(self.lang) if self.lang in i18n.LANGUAGES else 0)
        self._combo("AddType", [T("types." + t) for t in BLOCK_TYPES])
        self._combo("RoleHelper", ["%s — %s" % (k, i18n.role_label(k, self.project["meta"]["language"])) for k in self.role_keys])
        self._combo("Layout", LAYOUTS)
        self._combo("Kind", KINDS)
        self._combo("Columns", COLUMNS)
        self._combo("Position", POSITIONS)
        self._combo("Order", ORDERS)
        self.headings = [""] + ["dept:" + k for k in i18n.roles()["departments"]] + \
            ["h:" + k for k in i18n.phrases("en")["headers"]]
        self._combo("Heading", [h if not h else "%s — %s" % (h, layout_heading(h, self.project["meta"]["language"]))
                                for h in self.headings])
        self.themes = list(layout.themes().keys())
        self._combo("Theme", [layout.themes()[t]["label"].get(self.lang, t) for t in self.themes])
        self._combo("Render", [T("style.render_" + r) for r in RENDER])
        self._combo("Bg", [T("style.transparent"), T("style.black")])
        self._combo("Split", [T("style.split_none"), T("style.split_left"), T("style.split_right")])
        self._combo("StyleKey", STYLE_KEYS)
        self._combo("SCase", CASES)
        self._combo("Speed", [T("timing." + s) for s in SPEEDS])
        self._combo("Fit", [T("timing.fit_" + f) for f in FITS])
        self._combo("EndMode", [T("timing." + e) for e in END_MODES])
        self._combo("Pace", [T("timing." + p) for p in PACES])
        self._combo("Where", [T("generate." + w) for w in WHERE])
        self._combo("Track", [T("generate.track_dr"), T("generate.track_new")])
        tree = self.it["Blocks"]
        tree.ColumnCount = 5
        hdr = tree.NewItem()
        for i, k in enumerate(["#", "data.col_on", "data.col_type", "data.col_label", "data.col_n"]):
            hdr.Text[i] = k if k == "#" else T(k)
        tree.SetHeaderItem(hdr)
        for i, w in enumerate([34, 34, 150, 230, 40]):
            tree.ColumnWidth[i] = w
        self.busy = False

    def _bind(self):
        self.win.On.DRFCWin.Close = lambda ev: self.disp.ExitLoop()
        for i in range(5):
            self._on("Step%d" % i, "Clicked", (lambda idx: lambda ev: self.go(idx))(i))
        b = self._on
        b("New", "Clicked", self.on_new)
        b("Open", "Clicked", self.on_open)
        b("Save", "Clicked", lambda ev: self.on_save(False))
        b("SaveAs", "Clicked", lambda ev: self.on_save(True))
        b("UiLang", "CurrentIndexChanged", self.on_ui_lang)
        b("Seq", "CurrentIndexChanged", self.on_seq)
        b("NewSeq", "Clicked", self.on_new_seq)
        b("Blocks", "ItemClicked", self.on_block_click)
        b("Add", "Clicked", self.on_add)
        b("Up", "Clicked", lambda ev: self.on_move(-1))
        b("Down", "Clicked", lambda ev: self.on_move(1))
        b("Dup", "Clicked", self.on_dup)
        b("Del", "Clicked", self.on_del)
        b("Toggle", "Clicked", self.on_toggle)
        b("Apply", "Clicked", self.on_apply)
        b("InsertRole", "Clicked", self.on_insert_role)
        b("Import", "Clicked", self.on_import)
        b("Template", "Clicked", self.on_template)
        b("StyleKey", "CurrentIndexChanged", lambda ev: self.load_style_override())
        b("SApply", "Clicked", self.on_style_apply)
        b("SReset", "Clicked", self.on_style_reset)
        b("TSeq", "CurrentIndexChanged", lambda ev: self.load_seq_timing())
        b("Calc", "Clicked", self.on_calc)
        b("Check", "Clicked", self.on_check)
        b("Preview", "Clicked", self.on_preview)
        b("Insert", "Clicked", self.on_insert)
        b("Export", "Clicked", self.on_export)
        b("Calibrate", "Clicked", self.on_calibrate)

    def go(self, idx):
        self.ui_to_project()
        self.it["Stack"].CurrentIndex = idx
        for i in range(5):
            self.it["Step%d" % i].Checked = (i == idx)
        if idx == 3:
            self.on_calc(None)

    # ------------------------------------------------------------------ progetto <-> UI
    def load_project_to_ui(self):
        p = self.project
        it = self.it
        self.busy = True
        m = p["meta"]
        ids = [x["id"] for x in self.presets]
        it["Preset"].CurrentIndex = ids.index(m.get("preset")) if m.get("preset") in ids else 0
        it["FilePath"].Text = self.path or ""
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
        try:
            pr = presets.load_preset(m.get("preset"))
            it["Notes"].PlainText = "\n\n".join(pr.get("notes", []))
        except Exception:
            it["Notes"].PlainText = ""
        st = p["style"]
        it["Theme"].CurrentIndex = self.themes.index(st.get("theme")) if st.get("theme") in self.themes else 0
        lay = p["layout"]
        it["Render"].CurrentIndex = RENDER.index(lay.get("render_mode", "auto"))
        it["Safe"].Value = int(round(float(p["format"].get("safe_title", 0.9)) * 100))
        it["Bg"].CurrentIndex = 0 if p["format"].get("background", "transparent") == "transparent" else 1
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
        self._combo("Seq", names, self.seq_idx)
        self._combo("TSeq", names, self.seq_idx)
        self._combo("GSeq", [self.T("generate.all")] + names, 0)
        self.busy = False
        self.refresh_blocks()
        self.load_style_override()
        self.load_seq_timing()

    def ui_to_project(self):
        if self.busy or not hasattr(self, "it"):
            return
        p, it = self.project, self.it
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
        p["style"]["theme"] = self.themes[it["Theme"].CurrentIndex]
        p["layout"]["render_mode"] = RENDER[it["Render"].CurrentIndex]
        p["format"]["safe_title"] = it["Safe"].Value / 100.0
        p["format"]["background"] = "transparent" if it["Bg"].CurrentIndex == 0 else "#000000"
        p["layout"]["axis"] = it["Axis"].Value / 100.0
        p["layout"]["split"] = SPLITS[it["Split"].CurrentIndex]
        p["layout"]["text_lane"] = it["Lane"].Value / 100.0
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
        """Se e' dichiarato l'uso di IA, la dicitura viene aggiunta/aggiornata automaticamente."""
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

    # ------------------------------------------------------------------ pagina progetto
    def on_new(self, ev):
        pr = self.presets[self.it["Preset"].CurrentIndex]
        self.ui_to_project()
        keep = {k: self.project["meta"].get(k) for k in ("title", "original_title", "year", "copyright_owner", "country")}
        self.project = presets.project_from_preset(pr["id"], **keep)
        self.path = None
        self.seq_idx, self.block_idx = 0, -1
        self.load_project_to_ui()
        self.status(self.T("msg.confirm_new"))

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
        self.seq_idx, self.block_idx = 0, -1
        self.settings["last_project"] = path
        save_settings(self.settings)
        self.load_project_to_ui()
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
        self.status(self.T("msg.saved", path=path))

    def on_ui_lang(self, ev):
        self.ui_to_project()
        self.settings["ui_lang"] = i18n.LANGUAGES[self.it["UiLang"].CurrentIndex]
        save_settings(self.settings)
        self.restart = True
        self.disp.ExitLoop()

    # ------------------------------------------------------------------ pagina contenuti
    def refresh_blocks(self):
        tree = self.it["Blocks"]
        tree.Clear()
        lang = self.project["meta"]["language"]
        for i, b in enumerate(self.seq()["blocks"]):
            row = tree.NewItem()
            label, n = blocktext.summary(b, lang)
            row.Text[0] = str(i + 1)
            row.Text[1] = "●" if b.get("enabled", True) else "○"
            row.Text[2] = self.T("types." + b["type"])
            row.Text[3] = label or ("(%s)" % b.get("note", "")[:30] if b.get("note") else "")
            row.Text[4] = str(n) if n else ""
            tree.AddTopLevelItem(row)
        self.load_block_to_ui()

    def on_seq(self, ev):
        self.seq_idx = self.it["Seq"].CurrentIndex
        self.block_idx = -1
        self.refresh_blocks()

    def on_new_seq(self, ev):
        n = len(self.project["sequences"]) + 1
        self.project["sequences"].append(model.new_sequence("seq%d" % n, "crawl", "Sequenza %d" % n))
        self.seq_idx = n - 1
        self.load_project_to_ui()

    def on_block_click(self, ev):
        item = ev.get("item") if hasattr(ev, "get") else ev["item"]
        try:
            self.block_idx = int(item.Text[0]) - 1
        except Exception:
            return
        self.load_block_to_ui()

    def load_block_to_ui(self):
        b = self.block()
        it = self.it
        self.busy = True
        enabled = b is not None
        for cid in ("BlockText", "Apply", "Heading", "HeadingText", "Layout", "Kind", "Columns", "Position", "Order",
                    "Hold", "Before", "After", "PageBreak", "Team", "SideLane"):
            it[cid].Enabled = enabled
        if b is None:
            it["BlockText"].PlainText = ""
            it["Help"].Text = self.T("msg.select_block")
            self.busy = False
            return
        t = b["type"]
        it["BlockText"].PlainText = blocktext.render(b)
        it["Help"].Text = self.T("data.help") + ":  " + self.T("help." + t) + (("\n\n" + b["note"]) if b.get("note") else "")
        heading = b.get("heading") if "heading" in b else b.get("caption", "")
        if heading in self.headings:
            it["Heading"].CurrentIndex = self.headings.index(heading)
            it["HeadingText"].Text = ""
        else:
            it["Heading"].CurrentIndex = 0
            it["HeadingText"].Text = heading or ""
        it["Heading"].Enabled = it["HeadingText"].Enabled = t in ("list", "names", "cast", "music", "agreements", "logos")
        it["Layout"].Enabled = t in ("credit", "list")
        it["Layout"].CurrentIndex = LAYOUTS.index(b.get("layout")) if b.get("layout") in LAYOUTS else (1 if t == "list" else 0)
        it["Kind"].Enabled = t == "agreements"
        it["Kind"].CurrentIndex = KINDS.index(b.get("kind", "location")) if t == "agreements" else 0
        it["Columns"].Enabled = t in ("names", "agreements", "logos")
        col = str(b.get("columns", b.get("per_row", "auto")))
        it["Columns"].CurrentIndex = COLUMNS.index(col) if col in COLUMNS else 0
        it["Position"].Enabled = t == "card" or self.seq()["kind"] == "cards"
        it["Position"].CurrentIndex = POSITIONS.index(b.get("position", "center")) if b.get("position", "center") in POSITIONS else 0
        it["Order"].Enabled = t == "cast"
        it["Order"].CurrentIndex = ORDERS.index(b.get("order", "actor_character")) if t == "cast" else 0
        it["Hold"].Value = float(b.get("hold_s") or 0)
        it["Before"].Value = -1 if b.get("spacing_before") is None else float(b["spacing_before"])
        it["After"].Value = -1 if b.get("spacing_after") is None else float(b["spacing_after"])
        it["PageBreak"].Checked = bool(b.get("page_break"))
        it["Team"].Enabled = t in ("credit", "card")
        it["Team"].Checked = bool(b.get("team"))
        it["SideLane"].Enabled = t == "media"
        it["SideLane"].Checked = b.get("lane") == "side"
        self.busy = False

    def on_apply(self, ev):
        b = self.block()
        if b is None:
            self.status(self.T("msg.select_block"))
            return
        it = self.it
        t = b["type"]
        blocktext.parse(b, it["BlockText"].PlainText)
        heading = it["HeadingText"].Text.strip() or self.headings[it["Heading"].CurrentIndex]
        if t == "logos":
            b["caption"] = heading
        elif "heading" in BLOCK_TYPES[t]["fields"]:
            b["heading"] = heading
        if t in ("credit", "list"):
            b["layout"] = LAYOUTS[it["Layout"].CurrentIndex]
        if t == "agreements":
            b["kind"] = KINDS[it["Kind"].CurrentIndex]
        if t in ("names", "agreements"):
            c = COLUMNS[it["Columns"].CurrentIndex]
            b["columns"] = c if c == "auto" else int(c)
        if t == "logos":
            c = COLUMNS[it["Columns"].CurrentIndex]
            b["per_row"] = c if c == "auto" else int(c)
        if it["Position"].Enabled:
            b["position"] = POSITIONS[it["Position"].CurrentIndex]
        if t == "cast":
            b["order"] = ORDERS[it["Order"].CurrentIndex]
        b["hold_s"] = float(it["Hold"].Value)
        b["spacing_before"] = None if it["Before"].Value < 0 else float(it["Before"].Value)
        b["spacing_after"] = None if it["After"].Value < 0 else float(it["After"].Value)
        b["page_break"] = bool(it["PageBreak"].Checked)
        if t in ("credit", "card"):
            b["team"] = bool(it["Team"].Checked)
        if t == "media":
            b["lane"] = "side" if it["SideLane"].Checked else "main"
        keep = self.block_idx
        self.refresh_blocks()
        self.block_idx = keep
        self.load_block_to_ui()
        self.status("OK — %s" % self.T("types." + t))

    def on_insert_role(self, ev):
        key = self.role_keys[self.it["RoleHelper"].CurrentIndex]
        txt = self.it["BlockText"].PlainText
        self.it["BlockText"].PlainText = (txt.rstrip("\n") + "\n" if txt.strip() else "") + key + ": "

    def on_add(self, ev):
        t = list(BLOCK_TYPES.keys())[self.it["AddType"].CurrentIndex]
        blocks = self.seq()["blocks"]
        pos = self.block_idx + 1 if self.block_idx >= 0 else len(blocks)
        b = model.new_block(t)
        b["id"] = "%s_%s_%d" % (self.seq()["id"], t, len(blocks) + 1)
        blocks.insert(pos, b)
        self.block_idx = pos
        self.refresh_blocks()

    def on_move(self, d):
        self.block_idx = model.move_block(self.seq(), self.block_idx, d)
        self.refresh_blocks()

    def on_dup(self, ev):
        b = self.block()
        if b:
            c = copy.deepcopy(b)
            c["id"] = b["id"] + "_copy"
            self.seq()["blocks"].insert(self.block_idx + 1, c)
            self.block_idx += 1
            self.refresh_blocks()

    def on_del(self, ev):
        if self.block():
            del self.seq()["blocks"][self.block_idx]
            self.block_idx = min(self.block_idx, len(self.seq()["blocks"]) - 1)
            self.refresh_blocks()

    def on_toggle(self, ev):
        b = self.block()
        if b:
            b["enabled"] = not b.get("enabled", True)
            self.refresh_blocks()

    def on_import(self, ev):
        path = self._request_file(False, "*.csv;*.tsv;*.txt;*.xlsx")
        if not path:
            return
        n = io_import.import_file(self.project, path)
        self.refresh_blocks()
        self.status(self.T("msg.imported", n=n))

    def on_template(self, ev):
        path = self._request_file(True, "*.csv")
        if path:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            io_import.write_template(path)
            self.status(path)

    # ------------------------------------------------------------------ pagina stile
    def load_style_override(self):
        key = STYLE_KEYS[self.it["StyleKey"].CurrentIndex]
        th = layout.themes().get(self.project["style"]["theme"]) or layout.themes()["classic"]
        st = dict(th["styles"].get(key, {}))
        st.update(self.project["style"].get("overrides", {}).get(key, {}))
        it = self.it
        self.busy = True
        it["SFamily"].Text = st.get("family", "")
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
            "family": it["SFamily"].Text, "style": it["SStyle"].Text, "size": float(it["SSize"].Value),
            "color": it["SColor"].Text, "case": CASES[it["SCase"].CurrentIndex],
            "tracking": float(it["STrack"].Value), "line_spacing": float(it["SLine"].Value)}
        self.status("OK — %s" % key)

    def on_style_reset(self, ev):
        key = STYLE_KEYS[self.it["StyleKey"].CurrentIndex]
        self.project["style"].get("overrides", {}).pop(key, None)
        self.load_style_override()

    # ------------------------------------------------------------------ pagina tempi
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

    # ------------------------------------------------------------------ pagina genera
    def _report(self, issues, extra=None):
        icons = {"error": "✖", "warning": "⚠", "info": "ℹ"}
        lines = list(extra or [])
        lines += ["%s %s%s" % (icons.get(i["level"], "-"), i["message"], (" [%s]" % i["block"]) if i.get("block") else "")
                  for i in issues]
        ne = sum(1 for i in issues if i["level"] == "error")
        nw = sum(1 for i in issues if i["level"] == "warning")
        lines.insert(0, "%d %s · %d %s" % (ne, self.T("generate.errors"), nw, self.T("generate.warnings")))
        self.it["Results"].PlainText = "\n".join(lines)

    def _selected_seqs(self):
        i = self.it["GSeq"].CurrentIndex
        seqs = self.project["sequences"]
        return [s["id"] for s in seqs] if i <= 0 else [seqs[i - 1]["id"]]

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

    def on_insert(self, ev):
        self.ui_to_project()
        if not self.resolve:
            self.status(self.T("msg.no_resolve"))
            return
        sess = resolve_bridge.ResolveSession(self.resolve)
        where = WHERE[self.it["Where"].CurrentIndex]
        track = "dr" if self.it["Track"].CurrentIndex == 0 else "new"
        msgs, all_issues = [], []
        for sid in self._selected_seqs():
            res = sess.insert(self.project, sid, self._work_dir(), where=where, track=track,
                              replace=bool(self.it["Replace"].Checked), progress=self.status)
            msgs.append(("✔ " if res["ok"] else "✖ ") + res["message"])
            msgs += ["   " + n for n in res.get("notes", [])]
            all_issues = res.get("issues", all_issues)
        if self.path:
            model.save(self.project, self.path)
        self._report(all_issues, msgs)
        self.status(self.T("generate.ok"))

    def on_calibrate(self, ev):
        from . import calibration
        res, path = calibration.run(self.fu)
        self.it["Results"].PlainText = "Calibrazione salvata in %s\n%s" % (path, json.dumps(res, indent=2))

    # ------------------------------------------------------------------ ciclo
    def run(self):
        while True:
            self.restart = False
            self.build()
            self.win.Show()
            self.disp.RunLoop()
            self.ui_to_project()
            self.win.Hide()
            if self.path:
                try:
                    model.save(self.project, self.path)
                except Exception:
                    pass
            if not self.restart:
                break
            self.lang = self.settings.get("ui_lang", "it")


def layout_heading(h, lang):
    from . import phrases
    try:
        return phrases.heading_text(h, lang)
    except KeyError:
        return h


def main(fusion, bmd, resolve=None):
    Wizard(fusion, bmd, resolve).run()
