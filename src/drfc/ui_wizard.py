"""Pannello guidato (UIManager di Resolve/Fusion): Progetto > Contenuti > Stile > Tempi > Genera.

Modalita' Semplice (default): procedura guidata "tipo di opera + cosa hai", editor delle
righe con menu a tendina (reparto > ruolo > nomi), loghi dal kit, allori dei festival.
Modalita' Avanzata: in piu' editor testuale, spaziature, override di stile, nodi Fusion.

Tutta la logica sta nei moduli puri (guide, model, blocktext, engine, resolve_bridge...):
qui solo il collegamento tra campi e progetto.
"""

import copy
import json
import os
import traceback
import webbrowser

from . import (__version__, blocktext, design, engine, fusion_constants, guide, i18n, io_import, laurels,
               layout, logos, model, presets, resolve_bridge)
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
ROW_TYPES = ("credit", "list", "card")
CUSTOM = "✎"


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
        self.advanced = bool(self.settings.get("advanced", False))
        self.path = self.settings.get("last_project")
        self.project = None
        if self.path and os.path.exists(self.path):
            try:
                self.project = model.load(self.path)
            except Exception:
                self.project = None
        if self.project is None:
            self.path = None
            self.project = guide.new_project("corto", "it")
        self.seq_idx, self.block_idx, self.row_idx = 0, -1, -1
        self.busy = False
        self.restart = False
        self.presets = presets.list_presets()
        self.depts = list(i18n.roles()["departments"].keys())
        self.dests = list(design.destinations().keys())
        self.fontsets = list(design.fontsets().keys())
        self.festivals = list(laurels.festivals()["festivals"].keys())
        self.logo_ids = [e["id"] for e in logos.registry()["logos"]]

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

    def seq(self):
        seqs = self.project["sequences"]
        if not seqs:
            seqs.append(model.new_sequence("end", "crawl", "Titoli di coda"))
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
        c.CurrentIndex = max(0, min(index, len(labels) - 1)) if labels else 0

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

    def _show(self, ids, visible):
        for cid in ids:
            w = self.it.get(cid) if hasattr(self.it, "get") else self.it[cid]
            if w is None:
                continue
            try:
                w.Hidden = not visible
            except Exception:
                pass
            try:
                w.Enabled = bool(visible) or w.Enabled
            except Exception:
                pass

    # ------------------------------------------------------------------ finestra
    def build(self):
        ui = self.ui
        T = self.T
        L = lambda text, **kw: ui.Label(dict({"Text": text, "Weight": 0}, **kw))
        lw = {"MinimumSize": [150, 0]}

        def row(*children, **kw):
            return ui.HGroup(dict({"Weight": 0}, **kw), list(children))

        steps = ["project", "data", "style", "timing", "generate"]
        nav = ui.VGroup({"Weight": 0, "MinimumSize": [190, 0]},
                        [ui.Button({"ID": "Step%d" % i, "Text": T("steps." + s), "Checkable": True,
                                    "MinimumSize": [180, 34]}) for i, s in enumerate(steps)] +
                        [ui.VGap(0, 1),
                         ui.CheckBox({"ID": "Advanced", "Text": T("app.advanced"), "Checked": self.advanced}),
                         L("v" + __version__, Alignment={"AlignHCenter": True})])

        elements = guide.ELEMENTS
        p_project = ui.VGroup([
            L("<b>%s</b>" % T("guided.title")),
            row(L(T("guided.work"), **lw), ui.ComboBox({"ID": "Work"}), L(T("guided.territory")), ui.ComboBox({"ID": "Territory"})),
            row(L(T("guided.destination"), **lw), ui.ComboBox({"ID": "Dest"}),
                ui.Button({"ID": "DestFromTl", "Text": T("guided.from_timeline"), "Weight": 0})),
            L(T("guided.what")),
            row(*[ui.CheckBox({"ID": "E_" + e, "Text": guide.ELEMENT_LABELS[self.L()][e]}) for e in elements[:5]]),
            row(*[ui.CheckBox({"ID": "E_" + e, "Text": guide.ELEMENT_LABELS[self.L()][e]}) for e in elements[5:9]]),
            row(*[ui.CheckBox({"ID": "E_" + e, "Text": guide.ELEMENT_LABELS[self.L()][e]}) for e in elements[9:]]),
            row(ui.HGap(0, 1), ui.Button({"ID": "Create", "Text": T("guided.create"), "MinimumSize": [240, 34], "Weight": 0})),
            ui.VGap(8),
            row(L(T("project.file"), **lw), ui.LineEdit({"ID": "FilePath", "ReadOnly": True}),
                ui.Button({"ID": "Open", "Text": T("project.open"), "Weight": 0}),
                ui.Button({"ID": "Save", "Text": T("project.save"), "Weight": 0}),
                ui.Button({"ID": "SaveAs", "Text": T("project.save_as"), "Weight": 0})),
            row(L(T("project.title"), **lw), ui.LineEdit({"ID": "Title"}), L(T("project.original_title")), ui.LineEdit({"ID": "OrigTitle"})),
            row(L(T("project.year"), **lw), ui.SpinBox({"ID": "Year", "Minimum": 1895, "Maximum": 2200, "Weight": 0}),
                L(T("project.owner")), ui.LineEdit({"ID": "Owner"}), L(T("project.country")), ui.LineEdit({"ID": "Country", "Weight": 0.4})),
            row(L(T("project.language"), **lw), ui.ComboBox({"ID": "Lang"}), L(T("project.ui_language")), ui.ComboBox({"ID": "UiLang"})),
            L(T("project.funding")),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[:6]]),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[6:]]),
            row(ui.CheckBox({"ID": "AiUsed", "Text": T("project.ai_used"), "Weight": 0}), L(T("project.ai_uses")), ui.LineEdit({"ID": "AiUses"})),
            row(L(T("project.preset"), **lw), ui.ComboBox({"ID": "Preset"}), ui.Button({"ID": "New", "Text": T("project.new"), "Weight": 0}),
                ID="PresetRow"),
            L(T("project.notes")),
            ui.TextEdit({"ID": "Notes", "ReadOnly": True}),
        ])

        p_data = ui.HGroup([
            ui.VGroup({"Weight": 1}, [
                row(L(T("data.sequence")), ui.ComboBox({"ID": "Seq"}), ui.Button({"ID": "NewSeq", "Text": T("data.new_seq"), "Weight": 0})),
                ui.Tree({"ID": "Blocks", "SortingEnabled": False, "Events": {"ItemClicked": True}}),
                row(ui.ComboBox({"ID": "AddElement"}), ui.Button({"ID": "AddEl", "Text": T("data.add"), "Weight": 0})),
                row(ui.ComboBox({"ID": "AddType"}), ui.Button({"ID": "Add", "Text": T("data.add_block"), "Weight": 0})),
                row(ui.Button({"ID": "Up", "Text": T("data.up")}), ui.Button({"ID": "Down", "Text": T("data.down")}),
                    ui.Button({"ID": "Dup", "Text": T("data.dup")}), ui.Button({"ID": "Del", "Text": T("data.delete")}),
                    ui.Button({"ID": "Toggle", "Text": T("data.toggle")})),
                row(ui.Button({"ID": "Reorder", "Text": T("data.reorder")}), ui.Button({"ID": "Suggest", "Text": T("data.suggest")})),
                row(ui.Button({"ID": "Import", "Text": T("data.import")}), ui.Button({"ID": "Template", "Text": T("data.template")})),
            ]),
            ui.VGroup({"Weight": 1.5}, [
                ui.Label({"ID": "BlockTitle", "Text": "", "Weight": 0, "StyleSheet": "font-weight:bold;"}),
                # editor righe (reparto > ruolo > nomi)
                ui.Tree({"ID": "Rows", "SortingEnabled": False, "Events": {"ItemClicked": True}}),
                row(L(T("rows.dept")), ui.ComboBox({"ID": "RDept"}), L(T("rows.role")), ui.ComboBox({"ID": "RRole"}),
                    ui.LineEdit({"ID": "RRoleText", "PlaceholderText": T("rows.custom")}), ID="RowSel"),
                row(L(T("rows.names")), ui.LineEdit({"ID": "RNames", "PlaceholderText": T("rows.names_hint")}), ID="RowNames"),
                row(ui.Button({"ID": "RAdd", "Text": T("rows.add")}), ui.Button({"ID": "RSet", "Text": T("rows.set")}),
                    ui.Button({"ID": "RDel", "Text": T("rows.delete")}), ui.Button({"ID": "RUp", "Text": "▲"}),
                    ui.Button({"ID": "RDown", "Text": "▼"}), ui.Button({"ID": "RBreak", "Text": T("rows.column_break")}),
                    ID="RowBtns"),
                # loghi
                row(L(T("logos.pick")), ui.ComboBox({"ID": "LogoPick"}), ui.Button({"ID": "LogoAdd", "Text": T("logos.add"), "Weight": 0}),
                    ID="LogoRow1"),
                row(ui.Button({"ID": "LogoPng", "Text": T("logos.own")}), ui.Button({"ID": "LogoImport", "Text": T("logos.import")}),
                    ui.Button({"ID": "LogoPage", "Text": T("logos.page")}), ui.Button({"ID": "LogoUpdate", "Text": T("logos.update")}),
                    ID="LogoRow2"),
                # allori
                row(L(T("laurels.festival")), ui.ComboBox({"ID": "LFest"}), L(T("laurels.status")), ui.ComboBox({"ID": "LStatus"}),
                    ID="LaurelRow1"),
                row(L(T("laurels.section")), ui.ComboBox({"ID": "LSection"}), L(T("laurels.year")),
                    ui.SpinBox({"ID": "LYear", "Minimum": 1932, "Maximum": 2200, "Value": 2026}),
                    L(T("laurels.award")), ui.LineEdit({"ID": "LAward"}), ID="LaurelRow2"),
                row(ui.Button({"ID": "LAdd", "Text": T("laurels.add")}), ui.Button({"ID": "LOfficial", "Text": T("laurels.official")}),
                    ID="LaurelRow3"),
                # testo (tutti i tipi in avanzata, quelli senza editor dedicato in semplice)
                ui.TextEdit({"ID": "BlockText", "AcceptRichText": False, "Font": ui.Font({"Family": "Courier New", "PixelSize": 13})}),
                row(L(T("data.heading")), ui.ComboBox({"ID": "Heading"}), ui.LineEdit({"ID": "HeadingText"}), ID="HeadRow"),
                row(L(T("data.arrangement")), ui.ComboBox({"ID": "Arr"}), L(T("data.kind")), ui.ComboBox({"ID": "Kind"}),
                    L(T("data.columns")), ui.ComboBox({"ID": "Columns"}), ID="ArrRow"),
                row(L(T("data.position")), ui.ComboBox({"ID": "Position"}), L(T("data.order")), ui.ComboBox({"ID": "Order"}), ID="PosRow"),
                row(L(T("data.hold")), ui.DoubleSpinBox({"ID": "Hold", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1}),
                    L(T("data.before")), ui.DoubleSpinBox({"ID": "Before", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1}),
                    L(T("data.after")), ui.DoubleSpinBox({"ID": "After", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1}),
                    ID="SpaceRow"),
                row(ui.CheckBox({"ID": "PageBreak", "Text": T("data.page_break")}), ui.CheckBox({"ID": "Team", "Text": T("data.team")}),
                    ui.CheckBox({"ID": "SideLane", "Text": T("data.side_lane")}), ui.HGap(0, 1),
                    ui.Button({"ID": "Apply", "Text": T("data.apply"), "MinimumSize": [180, 30], "Weight": 0})),
                ui.Label({"ID": "Help", "Text": "", "WordWrap": True, "Weight": 0, "StyleSheet": "color: #9a9aa3;"}),
            ]),
        ])

        p_style = ui.VGroup([
            row(L(T("guided.destination"), **lw), ui.ComboBox({"ID": "SDest"})),
            row(L(T("style.theme"), **lw), ui.ComboBox({"ID": "Theme"}), L(T("style.fontset")), ui.ComboBox({"ID": "Fontset"})),
            row(L(T("style.density"), **lw), ui.ComboBox({"ID": "Density"}), L(T("style.leading")), ui.ComboBox({"ID": "Leading"})),
            row(L(T("style.background"), **lw), ui.ComboBox({"ID": "Bg"}), L(T("style.color")), ui.LineEdit({"ID": "BgColor"}),
                ui.LineEdit({"ID": "BgColor2"})),
            row(L(T("style.bg_media"), **lw), ui.LineEdit({"ID": "BgMedia"}), ui.Button({"ID": "BgPick", "Text": "…", "Weight": 0}),
                L(T("style.dim")), ui.DoubleSpinBox({"ID": "BgDim", "Minimum": 0, "Maximum": 1, "SingleStep": 0.05, "Decimals": 2}),
                L(T("style.blur")), ui.DoubleSpinBox({"ID": "BgBlur", "Minimum": 0, "Maximum": 100, "Decimals": 0})),
            row(L(T("style.split"), **lw), ui.ComboBox({"ID": "Split"}), L(T("style.text_lane")),
                ui.SpinBox({"ID": "Lane", "Minimum": 30, "Maximum": 80})),
            row(L(T("style.render_mode"), **lw), ui.ComboBox({"ID": "Render"}), L(T("style.axis")),
                ui.SpinBox({"ID": "Axis", "Minimum": 20, "Maximum": 80}), ID="AdvStyle1"),
            L(T("style.override"), ID="OvrLabel"),
            row(L("", **lw), ui.ComboBox({"ID": "StyleKey"}), ID="OvrRow0"),
            row(L(T("style.family"), **lw), ui.ComboBox({"ID": "SFamily", "Editable": True}), L(T("style.font_style")),
                ui.LineEdit({"ID": "SStyle"}), ID="OvrRow1"),
            row(L(T("style.size"), **lw), ui.DoubleSpinBox({"ID": "SSize", "Minimum": 6, "Maximum": 400, "Decimals": 1}),
                L(T("style.color")), ui.LineEdit({"ID": "SColor"}), L(T("style.case")), ui.ComboBox({"ID": "SCase"}), ID="OvrRow2"),
            row(L(T("style.tracking"), **lw), ui.DoubleSpinBox({"ID": "STrack", "Minimum": 0.5, "Maximum": 3, "SingleStep": 0.02, "Decimals": 2}),
                L(T("style.line_spacing")), ui.DoubleSpinBox({"ID": "SLine", "Minimum": 0.6, "Maximum": 3, "SingleStep": 0.05, "Decimals": 2}),
                ID="OvrRow3"),
            row(ui.HGap(0, 1), ui.Button({"ID": "SReset", "Text": T("style.reset"), "Weight": 0}),
                ui.Button({"ID": "SApply", "Text": T("style.apply"), "Weight": 0}), ID="OvrRow4"),
            ui.VGap(0, 1),
        ])

        p_timing = ui.VGroup([
            row(L(T("timing.speed"), **lw), ui.ComboBox({"ID": "Speed"}), ui.SpinBox({"ID": "Px", "Minimum": 1, "Maximum": 60, "Weight": 0})),
            row(L(T("timing.end_mode"), **lw), ui.ComboBox({"ID": "EndMode"}), L(T("timing.hold_last_s")),
                ui.DoubleSpinBox({"ID": "HoldLast", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1})),
            row(L(T("timing.lead_in"), **lw), ui.DoubleSpinBox({"ID": "LeadIn", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2}),
                L(T("timing.lead_out")), ui.DoubleSpinBox({"ID": "LeadOut", "Minimum": 0, "Maximum": 30, "SingleStep": 0.5, "Decimals": 2})),
            row(L(T("timing.card_pace"), **lw), ui.ComboBox({"ID": "Pace"}), L(T("timing.fade")),
                ui.DoubleSpinBox({"ID": "Fade", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2}),
                L(T("timing.gap")), ui.DoubleSpinBox({"ID": "Gap", "Minimum": 0, "Maximum": 5, "SingleStep": 0.1, "Decimals": 2})),
            L(T("timing.per_sequence")),
            row(L(T("data.sequence"), **lw), ui.ComboBox({"ID": "TSeq"})),
            row(L(T("timing.fit"), **lw), ui.ComboBox({"ID": "Fit"}), L(T("timing.target")),
                ui.DoubleSpinBox({"ID": "Target", "Minimum": 0, "Maximum": 3600, "SingleStep": 1, "Decimals": 2})),
            row(ui.HGap(0, 1), ui.Button({"ID": "Calc", "Text": T("timing.result"), "Weight": 0})),
            ui.TextEdit({"ID": "TimingOut", "ReadOnly": True}),
        ])

        p_gen = ui.VGroup([
            row(L(T("generate.where")), ui.ComboBox({"ID": "Where"}), L(T("generate.track")), ui.ComboBox({"ID": "Track"}),
                L(T("generate.card_mode")), ui.ComboBox({"ID": "CardMode"})),
            row(ui.CheckBox({"ID": "UseTl", "Text": T("project.from_timeline"), "Checked": True})),
            ui.Tree({"ID": "Sections", "SortingEnabled": False, "Events": {"ItemClicked": True}}),
            row(ui.Button({"ID": "Refresh", "Text": T("generate.refresh")}), ui.Button({"ID": "Lock", "Text": T("generate.lock")}),
                ui.Button({"ID": "SyncChanged", "Text": T("generate.update_changed"), "MinimumSize": [240, 40]}),
                ui.Button({"ID": "SyncAll", "Text": T("generate.regenerate_all")})),
            row(ui.Button({"ID": "Check", "Text": T("generate.check")}), ui.Button({"ID": "Preview", "Text": T("generate.preview")}),
                ui.Button({"ID": "Export", "Text": T("generate.export")}), ui.Button({"ID": "Calibrate", "Text": T("generate.calibrate")})),
            L(T("generate.results")),
            ui.TextEdit({"ID": "Results", "ReadOnly": True}),
        ])

        main = ui.VGroup([
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "<b style='font-size:16px'>%s</b>" % T("app.title"), "Weight": 0}),
                ui.Label({"Text": T("app.subtitle"), "StyleSheet": "color:#9a9aa3;"}),
            ]),
            ui.HGroup([nav, ui.Stack({"ID": "Stack"}, [p_project, p_data, p_style, p_timing, p_gen])]),
            ui.Label({"ID": "Status", "Text": "", "Weight": 0, "WordWrap": True, "StyleSheet": "color:#e0b04a;"}),
        ])
        self.win = self.disp.AddWindow({"ID": "DRFCWin", "WindowTitle": "DR-FilmCredits", "Geometry": [60, 40, 1260, 880]}, main)
        self.it = self.win.GetItems()
        self._populate_static()
        self._bind()
        self.load_project_to_ui()
        self.apply_mode()
        self.go(0)

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
        self._combo("Work", [guide.WORK_LABELS[L][w] for w in guide.WORK_TYPES])
        self._combo("Territory", [guide.TERRITORY_LABELS[L][t] for t in guide.TERRITORIES])
        dlabels = [design.label(design.destinations()[d], L) for d in self.dests]
        self._combo("Dest", dlabels)
        self._combo("SDest", dlabels)
        self._combo("Preset", [presets.preset_label(p, self.lang) for p in self.presets])
        self._combo("Lang", list(i18n.LANGUAGES))
        self._combo("UiLang", list(i18n.LANGUAGES), list(i18n.LANGUAGES).index(self.lang) if self.lang in i18n.LANGUAGES else 0)
        self._combo("AddType", [T("types." + t) for t in BLOCK_TYPES])
        self._combo("AddElement", [guide.ELEMENT_LABELS[L][e] for e in guide.ELEMENTS])
        self._combo("RDept", [T("rows.any_dept")] + [i18n.department_label(d, self.project["meta"]["language"]) for d in self.depts])
        self._combo("Arr", [T("arr." + a) for a in ARRANGEMENTS])
        self._combo("Kind", KINDS)
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
        self._combo("Track", [T("generate.track_dr"), T("generate.track_new")])
        self._combo("CardMode", [T("generate." + c) for c in CARD_MODES])
        self._tree_header("Blocks", ["#", T("data.col_on"), T("data.col_type"), T("data.col_label"), T("data.col_n")], [34, 34, 150, 230, 40])
        self._tree_header("Rows", ["#", T("rows.role"), T("rows.names")], [34, 220, 320])
        self._tree_header("Sections", [T("generate.col_section"), T("generate.col_status"), "id"], [420, 140, 200])
        self.busy = False

    def _fill_sections_combo(self):
        f = self.festivals[self.it["LFest"].CurrentIndex] if self.festivals else None
        secs = laurels.festivals()["festivals"].get(f, {}).get("sections", {}) if f else {}
        self.section_keys = [""] + list(secs.keys())
        self._combo("LSection", ["—"] + list(secs.values()))

    def _fill_roles(self, keep=None):
        di = self.it["RDept"].CurrentIndex
        dept = self.depts[di - 1] if di > 0 else None
        lang = self.project["meta"]["language"]
        keys = [k for k, r in sorted(i18n.roles()["roles"].items(), key=lambda kv: kv[1].get(lang, kv[0]))
                if dept is None or r["dept"] == dept]
        self.role_keys = keys
        self._combo("RRole", ["%s %s" % (CUSTOM, self.T("rows.custom"))] + [i18n.role_label(k, lang) for k in keys])
        if keep in keys:
            self.it["RRole"].CurrentIndex = keys.index(keep) + 1

    def _bind(self):
        self.win.On.DRFCWin.Close = lambda ev: self.disp.ExitLoop()
        for i in range(5):
            self._on("Step%d" % i, "Clicked", (lambda idx: lambda ev: self.go(idx))(i))
        b = self._on
        b("Advanced", "Clicked", self.on_advanced)
        b("Work", "CurrentIndexChanged", self.on_work)
        b("DestFromTl", "Clicked", self.on_dest_from_tl)
        b("Create", "Clicked", self.on_create)
        b("New", "Clicked", self.on_new)
        b("Open", "Clicked", self.on_open)
        b("Save", "Clicked", lambda ev: self.on_save(False))
        b("SaveAs", "Clicked", lambda ev: self.on_save(True))
        b("UiLang", "CurrentIndexChanged", self.on_ui_lang)
        b("Seq", "CurrentIndexChanged", self.on_seq)
        b("NewSeq", "Clicked", self.on_new_seq)
        b("Blocks", "ItemClicked", self.on_block_click)
        b("AddEl", "Clicked", self.on_add_element)
        b("Add", "Clicked", self.on_add)
        b("Up", "Clicked", lambda ev: self.on_move(-1))
        b("Down", "Clicked", lambda ev: self.on_move(1))
        b("Dup", "Clicked", self.on_dup)
        b("Del", "Clicked", self.on_del)
        b("Toggle", "Clicked", self.on_toggle)
        b("Reorder", "Clicked", self.on_reorder)
        b("Suggest", "Clicked", self.on_suggest)
        b("Import", "Clicked", self.on_import)
        b("Template", "Clicked", self.on_template)
        b("Rows", "ItemClicked", self.on_row_click)
        b("RDept", "CurrentIndexChanged", lambda ev: self._fill_roles())
        b("RAdd", "Clicked", lambda ev: self.on_row_edit("add"))
        b("RSet", "Clicked", lambda ev: self.on_row_edit("set"))
        b("RDel", "Clicked", lambda ev: self.on_row_edit("del"))
        b("RUp", "Clicked", lambda ev: self.on_row_edit("up"))
        b("RDown", "Clicked", lambda ev: self.on_row_edit("down"))
        b("RBreak", "Clicked", lambda ev: self.on_row_edit("break"))
        b("LogoAdd", "Clicked", self.on_logo_add)
        b("LogoPng", "Clicked", self.on_logo_png)
        b("LogoImport", "Clicked", self.on_logo_import)
        b("LogoPage", "Clicked", self.on_logo_page)
        b("LogoUpdate", "Clicked", self.on_logo_update)
        b("LFest", "CurrentIndexChanged", lambda ev: self._fill_sections_combo())
        b("LAdd", "Clicked", self.on_laurel_add)
        b("LOfficial", "Clicked", self.on_laurel_official)
        b("Apply", "Clicked", self.on_apply)
        b("SDest", "CurrentIndexChanged", self.on_style_dest)
        b("BgPick", "Clicked", self.on_bg_pick)
        b("StyleKey", "CurrentIndexChanged", lambda ev: self.load_style_override())
        b("SApply", "Clicked", self.on_style_apply)
        b("SReset", "Clicked", self.on_style_reset)
        b("TSeq", "CurrentIndexChanged", lambda ev: self.load_seq_timing())
        b("Calc", "Clicked", self.on_calc)
        b("Refresh", "Clicked", lambda ev: self.refresh_sections())
        b("Lock", "Clicked", self.on_lock)
        b("SyncChanged", "Clicked", lambda ev: self.on_sync(True))
        b("SyncAll", "Clicked", lambda ev: self.on_sync(False))
        b("Check", "Clicked", self.on_check)
        b("Preview", "Clicked", self.on_preview)
        b("Export", "Clicked", self.on_export)
        b("Calibrate", "Clicked", self.on_calibrate)

    def go(self, idx):
        self.ui_to_project()
        self.it["Stack"].CurrentIndex = idx
        for i in range(5):
            self.it["Step%d" % i].Checked = (i == idx)
        if idx == 3:
            self.on_calc(None)
        if idx == 4:
            self.refresh_sections()

    ADV_IDS = ("PresetRow", "AdvStyle1", "OvrLabel", "OvrRow0", "OvrRow1", "OvrRow2", "OvrRow3", "OvrRow4",
               "SpaceRow", "AddType", "Add", "NewSeq", "Template")

    def apply_mode(self):
        self._show(self.ADV_IDS, self.advanced)
        self.load_block_to_ui()

    def on_advanced(self, ev):
        self.advanced = bool(self.it["Advanced"].Checked)
        self.settings["advanced"] = self.advanced
        save_settings(self.settings)
        self.apply_mode()

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
        for e in guide.ELEMENTS:
            it["E_" + e].Checked = e in present
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
            it["Notes"].PlainText = "\n\n".join(presets.load_preset(m.get("preset")).get("notes", []))
        except Exception:
            it["Notes"].PlainText = ""
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
        self._combo("Seq", names, self.seq_idx)
        self._combo("TSeq", names, self.seq_idx)
        self.busy = False
        self._fill_roles()
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

    # ------------------------------------------------------------------ pagina progetto
    def on_work(self, ev):
        wt = guide.WORK_TYPES[self.it["Work"].CurrentIndex]
        defaults = set(guide.DEFAULT_ELEMENTS.get(wt, []))
        for e in guide.ELEMENTS:
            self.it["E_" + e].Checked = e in defaults
        pid = guide.preset_for(wt, guide.TERRITORIES[self.it["Territory"].CurrentIndex])
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
        self.ui_to_project()
        keep = {k: self.project["meta"].get(k) for k in ("title", "original_title", "year", "copyright_owner", "country",
                                                          "funding", "ai_used", "ai_uses")}
        wt = guide.WORK_TYPES[self.it["Work"].CurrentIndex]
        ter = guide.TERRITORIES[self.it["Territory"].CurrentIndex]
        els = [e for e in guide.ELEMENTS if self.it["E_" + e].Checked]
        dest = self.dests[self.it["Dest"].CurrentIndex]
        self.project = guide.new_project(wt, ter, els, destination=dest, language=self.project["meta"].get("language"), **keep)
        self.path = None
        self.seq_idx, self.block_idx = 0, -1
        self.load_project_to_ui()
        self.status(self.T("msg.confirm_new"))

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
            r = tree.NewItem()
            label, n = blocktext.summary(b, lang)
            r.Text[0] = str(i + 1)
            r.Text[1] = "●" if b.get("enabled", True) else "○"
            r.Text[2] = self.T("types." + b["type"])
            r.Text[3] = label or ("(%s)" % b.get("note", "")[:30] if b.get("note") else "")
            r.Text[4] = str(n) if n else ""
            tree.AddTopLevelItem(r)
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
        item = ev["item"]
        try:
            self.block_idx = int(item.Text[0]) - 1
        except Exception:
            return
        self.row_idx = -1
        self.load_block_to_ui()

    def _rows(self, b):
        """Righe modificabili con l'editor a tendina."""
        if b["type"] == "list":
            return b["rows"]
        if b["type"] in ("credit", "card") and not b.get("lines"):
            return [{"role": b.get("role", ""), "names": b.get("names", [])}]
        return None

    def refresh_rows(self):
        b = self.block()
        tree = self.it["Rows"]
        tree.Clear()
        rows = self._rows(b) if b else None
        lang = self.project["meta"]["language"]
        for i, r in enumerate(rows or []):
            t = tree.NewItem()
            t.Text[0] = str(i + 1)
            if r.get("break"):
                t.Text[1] = "── " + self.T("rows.column_break")
                t.Text[2] = ""
            else:
                t.Text[1] = i18n.role_label(r.get("role", ""), lang)
                t.Text[2] = ", ".join(r.get("names") or [])
            tree.AddTopLevelItem(t)

    def load_block_to_ui(self):
        if not hasattr(self, "it"):
            return
        b = self.block()
        it = self.it
        self.busy = True
        t = b["type"] if b else None
        rows_mode = b is not None and self._rows(b) is not None
        self._show(("Rows", "RowSel", "RowNames", "RowBtns"), rows_mode)
        self._show(("RBreak",), rows_mode and t == "list")
        self._show(("LogoRow1", "LogoRow2"), t == "logos")
        self._show(("LaurelRow1", "LaurelRow2", "LaurelRow3"), t == "laurels")
        self._show(("BlockText",), b is not None and (self.advanced or not rows_mode))
        self._show(("HeadRow",), t in ("list", "names", "cast", "music", "agreements", "logos"))
        self._show(("ArrRow",), t in ("list", "names", "agreements", "logos", "credit"))
        self._show(("PosRow",), t in ("card", "cast") or (b is not None and self.seq()["kind"] == "cards"))
        self._show(("SpaceRow",), self.advanced and b is not None)
        self._show(("SideLane",), t == "media")
        self._show(("Team",), t in ("credit", "card"))
        if b is None:
            it["BlockTitle"].Text = ""
            it["BlockText"].PlainText = ""
            it["Help"].Text = self.T("msg.select_block")
            self.it["Rows"].Clear()
            self.busy = False
            return
        lab, _n = blocktext.summary(b, self.project["meta"]["language"])
        it["BlockTitle"].Text = "%s — %s" % (self.T("types." + t), lab)
        it["BlockText"].PlainText = blocktext.render(b)
        it["Help"].Text = self.T("data.help") + ":  " + self.T("help." + t) + (("\n\n" + b["note"]) if b.get("note") else "")
        heading = b.get("heading") if "heading" in b else b.get("caption", "")
        if heading in self.headings:
            it["Heading"].CurrentIndex = self.headings.index(heading)
            it["HeadingText"].Text = ""
        else:
            it["Heading"].CurrentIndex = 0
            it["HeadingText"].Text = heading or ""
        if t == "list":
            arr = layout.list_arrangement(b)
        elif t == "credit":
            arr = "pair" if b.get("layout") == "two_column" else "single"
        else:
            arr = "pair"
        it["Arr"].CurrentIndex = ARRANGEMENTS.index(arr) if arr in ARRANGEMENTS else 0
        it["Kind"].CurrentIndex = KINDS.index(b.get("kind", "location")) if t == "agreements" else 0
        col = str(b.get("columns", b.get("per_row", "auto")))
        it["Columns"].CurrentIndex = COLUMNS.index(col) if col in COLUMNS else 0
        it["Position"].CurrentIndex = POSITIONS.index(b.get("position", "center")) if b.get("position", "center") in POSITIONS else 0
        it["Order"].CurrentIndex = ORDERS.index(b.get("order", "actor_character")) if t == "cast" else 0
        it["Hold"].Value = float(b.get("hold_s") or 0)
        it["Before"].Value = -1 if b.get("spacing_before") is None else float(b["spacing_before"])
        it["After"].Value = -1 if b.get("spacing_after") is None else float(b["spacing_after"])
        it["PageBreak"].Checked = bool(b.get("page_break"))
        it["Team"].Checked = bool(b.get("team"))
        it["SideLane"].Checked = b.get("lane") == "side"
        self.busy = False
        self.refresh_rows()

    def on_apply(self, ev):
        b = self.block()
        if b is None:
            self.status(self.T("msg.select_block"))
            return
        it = self.it
        t = b["type"]
        if self.advanced or self._rows(b) is None:
            if t != "laurels" or it["BlockText"].PlainText.strip():
                blocktext.parse(b, it["BlockText"].PlainText) if t != "laurels" else None
        heading = it["HeadingText"].Text.strip() or self.headings[it["Heading"].CurrentIndex]
        if t == "logos":
            b["caption"] = heading
        elif "heading" in BLOCK_TYPES[t]["fields"]:
            b["heading"] = heading
        arr = ARRANGEMENTS[it["Arr"].CurrentIndex]
        if t == "list":
            b["arrangement"] = arr
        if t == "credit":
            b["layout"] = "two_column" if arr == "pair" else "stacked"
        if t == "agreements":
            b["kind"] = KINDS[it["Kind"].CurrentIndex]
        if t in ("names", "agreements"):
            c = COLUMNS[it["Columns"].CurrentIndex]
            b["columns"] = c if c == "auto" else int(c)
        if t == "logos":
            c = COLUMNS[it["Columns"].CurrentIndex]
            b["per_row"] = c if c == "auto" else int(c)
        if t == "card" or self.seq()["kind"] == "cards":
            b["position"] = POSITIONS[it["Position"].CurrentIndex]
        if t == "cast":
            b["order"] = ORDERS[it["Order"].CurrentIndex]
        b["hold_s"] = float(it["Hold"].Value)
        if self.advanced:
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

    # --- righe
    def on_row_click(self, ev):
        try:
            self.row_idx = int(ev["item"].Text[0]) - 1
        except Exception:
            return
        b = self.block()
        rows = self._rows(b) if b else None
        if not rows or not (0 <= self.row_idx < len(rows)) or rows[self.row_idx].get("break"):
            return
        r = rows[self.row_idx]
        role = r.get("role", "")
        dept = i18n.role_department(role)
        self.busy = True
        self.it["RDept"].CurrentIndex = self.depts.index(dept) + 1 if dept in self.depts else 0
        self.busy = False
        self._fill_roles(keep=role)
        if role not in self.role_keys:
            self.it["RRole"].CurrentIndex = 0
            self.it["RRoleText"].Text = role
        else:
            self.it["RRoleText"].Text = ""
        self.it["RNames"].Text = ", ".join(r.get("names") or [])

    def _row_from_ui(self):
        ri = self.it["RRole"].CurrentIndex
        role = self.it["RRoleText"].Text.strip() if ri <= 0 else self.role_keys[ri - 1]
        return {"role": role, "names": blocktext.split_names(self.it["RNames"].Text)}

    def on_row_edit(self, action):
        b = self.block()
        if b is None:
            self.status(self.T("msg.select_block"))
            return
        if b["type"] in ("credit", "card") and not b.get("lines"):
            if action in ("add", "set"):
                r = self._row_from_ui()
                b["role"], b["names"] = r["role"], r["names"]
            self.refresh_blocks()
            return
        if b["type"] != "list":
            return
        rows = b["rows"]
        i = self.row_idx
        if action == "add":
            rows.insert(i + 1 if 0 <= i < len(rows) else len(rows), self._row_from_ui())
            self.row_idx = i + 1 if 0 <= i < len(rows) - 1 else len(rows) - 1
        elif action == "set" and 0 <= i < len(rows):
            rows[i] = self._row_from_ui()
        elif action == "del" and 0 <= i < len(rows):
            del rows[i]
            self.row_idx = min(i, len(rows) - 1)
        elif action in ("up", "down") and 0 <= i < len(rows):
            j = i + (-1 if action == "up" else 1)
            if 0 <= j < len(rows):
                rows[i], rows[j] = rows[j], rows[i]
                self.row_idx = j
        elif action == "break":
            rows.insert(i + 1 if 0 <= i < len(rows) else len(rows), {"break": True})
            if not str(b.get("arrangement", "")).startswith("pairs_"):
                b["arrangement"] = "pairs_2"
        self.it["RNames"].Text = ""
        keep_row = self.row_idx
        self.refresh_blocks()
        self.row_idx = keep_row

    def on_add_element(self, ev):
        e = guide.ELEMENTS[self.it["AddElement"].CurrentIndex]
        n = guide.add_element(self.project, e)
        self.load_project_to_ui()
        self.status(self.T("msg.added", n=n))

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

    def on_reorder(self, ev):
        guide.reorder(self.seq(), self.project["meta"].get("territory", "it"))
        self.block_idx = -1
        self.refresh_blocks()
        self.status(self.T("msg.reordered"))

    def on_suggest(self, ev):
        sugg = guide.suggestions(self.project)
        L = self.L()
        if not sugg:
            self.it["Help"].Text = self.T("msg.nothing_missing")
            return
        self.it["Help"].Text = self.T("msg.suggestions") + "\n" + "\n".join(
            "• %s — %s" % (guide.ELEMENT_LABELS[L].get(e, e), why) for e, why in sugg)
        if sugg[0][0] in guide.ELEMENTS:
            self.it["AddElement"].CurrentIndex = guide.ELEMENTS.index(sugg[0][0])

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

    # --- loghi
    def _logo_id(self):
        return self.logo_ids[self.it["LogoPick"].CurrentIndex]

    def on_logo_add(self, ev):
        b = self.block()
        if b is None or b["type"] != "logos":
            return
        lid = self._logo_id()
        b["items"].append({"logo": lid})
        st = logos.status(lid)
        self.refresh_blocks()
        if st != "ready":
            e = logos.entry(lid) or {}
            self.it["Help"].Text = "%s: %s\n%s\n%s" % (e.get("name", lid), logos.STATUS_LABEL["it" if self.lang == "it" else "en"][st],
                                                       e.get("usage_notes", ""), e.get("request_contact") or e.get("official_page", ""))

    def on_logo_png(self, ev):
        b = self.block()
        path = self._request_file(False, "*.png;*.tif;*.jpg")
        if not path or b is None:
            return
        b["items"].append({"path": path})
        self.refresh_blocks()

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
        self.it["Help"].Text = "\n".join(msgs[:40])

    # --- allori
    def on_laurel_add(self, ev):
        b = self.block()
        if b is None or b["type"] != "laurels":
            return
        item = {"festival": self.festivals[self.it["LFest"].CurrentIndex],
                "status": STATUS_KEYS[self.it["LStatus"].CurrentIndex], "year": int(self.it["LYear"].Value)}
        sec = self.section_keys[self.it["LSection"].CurrentIndex]
        if sec:
            item["section"] = sec
        if self.it["LAward"].Text.strip():
            item["award"] = self.it["LAward"].Text.strip()
        b["items"].append(item)
        self.refresh_blocks()

    def on_laurel_official(self, ev):
        b = self.block()
        path = self._request_file(False, "*.png")
        if path and b is not None:
            b["items"].append({"path": path})
            self.refresh_blocks()

    # ------------------------------------------------------------------ pagina stile
    def on_style_dest(self, ev):
        d = self.dests[self.it["SDest"].CurrentIndex]
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
            r.Text[1] = self.T("generate.st_" + st)
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

    def on_sync(self, only_changed):
        self.ui_to_project()
        sess = self._session()
        if sess is None:
            self.status(self.T("msg.no_resolve"))
            return
        where = WHERE[self.it["Where"].CurrentIndex]
        track = "dr" if self.it["Track"].CurrentIndex == 0 else "new"
        res = sess.sync(self.project, self._work_dir(), where=where, track=track, only_changed=only_changed,
                        progress=self.status, card_mode=self._card_mode())
        msgs = [("✔ " if r["ok"] else "✖ ") + r["message"] for r in res["sections"]]
        msgs += ["   " + n for n in res["notes"]] + ["   " + l for l in sess.log]
        if self.path:
            model.save(self.project, self.path)
        self._report(res["issues"], msgs)
        self.refresh_sections()
        self.status(self.T("generate.ok"))

    # compatibilita' con la v1
    def on_insert(self, ev):
        self.on_sync(False)

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


def _heading(h, lang):
    from . import phrases
    try:
        return phrases.heading_text(h, lang)
    except KeyError:
        return h


def main(fusion, bmd, resolve=None):
    Wizard(fusion, bmd, resolve).run()
