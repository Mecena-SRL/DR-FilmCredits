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
import os
import traceback
import webbrowser

from . import (__version__, blocktext, design, engine, fusion_constants, guide, i18n, io_import, laurels,
               layout, log, logos, model, outline, placeholders, presets, resolve_bridge)
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
ED_HINT, ED_ENTRY, ED_TEXT, ED_LOGOS, ED_LAURELS = 0, 1, 2, 3, 4


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
        self.role_keys = []
        self.section_keys = [""]

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
        def wrapped(ev):
            if self.busy:
                return
            try:
                fn(ev)
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
        ui = self.ui
        T = self.T
        L = lambda text, **kw: ui.Label(dict({"Text": text, "Weight": 0}, **kw))
        lw = {"MinimumSize": [150, 0]}

        def row(*children, **kw):
            return ui.HGroup(dict({"Weight": 0}, **kw), list(children))

        def help_label(key):
            return ui.Label({"Text": T(key), "WordWrap": True, "Weight": 0,
                             "StyleSheet": "color:#e0b04a; padding:4px 0 8px 0;"})

        nav = ui.VGroup({"Weight": 0, "MinimumSize": [200, 0]}, [
            ui.Button({"ID": "Step0", "Text": T("v3.nav1"), "Checkable": True, "MinimumSize": [190, 38]}),
            ui.Button({"ID": "Step1", "Text": T("v3.nav2"), "Checkable": True, "MinimumSize": [190, 38]}),
            ui.Button({"ID": "Step2", "Text": T("v3.nav3"), "Checkable": True, "MinimumSize": [190, 38]}),
            ui.VGap(10),
            ui.Button({"ID": "Step3", "Text": T("v3.nav4"), "Checkable": True, "MinimumSize": [190, 30]}),
            ui.VGap(0, 1),
            ui.Button({"ID": "Open", "Text": T("project.open")}),
            ui.Button({"ID": "Save", "Text": T("project.save")}),
            ui.Button({"ID": "SaveAs", "Text": T("project.save_as")}),
            ui.Label({"ID": "FilePath", "Text": "", "WordWrap": True, "Weight": 0, "StyleSheet": "color:#9a9aa3;"}),
            L("v" + __version__, Alignment={"AlignHCenter": True}),
        ])

        # ------------------------------------------------------------ passo 1
        e_rows = []
        for chunk in (UI_ELEMENTS[0:3], UI_ELEMENTS[3:6], UI_ELEMENTS[6:9]):
            e_rows.append(row(*[ui.CheckBox({"ID": "E_" + k, "Text": T("v3.e_" + k)}) for k, _v in chunk]))
        p1 = ui.VGroup([
            help_label("v3.help1"),
            row(L(T("v3.title"), **lw), ui.LineEdit({"ID": "Title"})),
            row(L(T("guided.work"), **lw), ui.ComboBox({"ID": "Work"}), L(T("guided.territory")), ui.ComboBox({"ID": "Territory"})),
            row(L(T("guided.destination"), **lw), ui.ComboBox({"ID": "Dest"}),
                ui.Button({"ID": "DestFromTl", "Text": T("guided.from_timeline"), "Weight": 0})),
            ui.VGap(6),
            ui.CheckBox({"ID": "Placeholders", "Text": T("v3.fill"), "Checked": True}),
            ui.VGap(6),
            L(T("v3.what")),
        ] + e_rows + [
            L(T("v3.always"), StyleSheet="color:#9a9aa3;"),
            ui.VGap(0, 1),
            ui.Label({"ID": "ProjInfo", "Text": "", "WordWrap": True, "Weight": 0, "StyleSheet": "color:#9a9aa3;"}),
            row(ui.Button({"ID": "Continue", "Text": T("v3.continue"), "MinimumSize": [260, 36]}), ui.HGap(0, 1),
                ui.Button({"ID": "Create", "Text": T("v3.create"), "MinimumSize": [260, 40]})),
        ])

        # ------------------------------------------------------------ passo 2
        ed_hint = ui.VGroup([ui.Label({"ID": "Help", "Text": T("v3.edit_hint"), "WordWrap": True, "Weight": 0,
                                       "StyleSheet": "color:#9a9aa3;"}), ui.VGap(0, 1)])
        ed_entry = ui.VGroup([
            row(L(T("rows.dept")), ui.ComboBox({"ID": "RDept"})),
            row(L(T("rows.role")), ui.ComboBox({"ID": "RRole"})),
            row(L(""), ui.LineEdit({"ID": "RRoleText", "PlaceholderText": T("rows.custom")})),
            row(L(T("rows.names")), ui.LineEdit({"ID": "RNames", "PlaceholderText": T("rows.names_hint"),
                                                 "Events": {"ReturnPressed": True}})),
            row(ui.Button({"ID": "RSave", "Text": T("v3.save"), "MinimumSize": [120, 30]}),
                ui.Button({"ID": "RAdd", "Text": T("v3.add_below")}), ui.Button({"ID": "RDel", "Text": T("v3.del_entry")}),
                ui.Button({"ID": "RBreak", "Text": T("v3.new_col")})),
            ui.VGap(0, 1),
        ])
        ed_text = ui.VGroup([
            L(T("v3.text_help")),
            ui.TextEdit({"ID": "BlockText", "AcceptRichText": False}),
            row(L(T("v3.section_title")), ui.ComboBox({"ID": "Heading"}), ui.LineEdit({"ID": "HeadingText"})),
            row(L(T("data.arrangement")), ui.ComboBox({"ID": "Arr"})),
            row(ui.Button({"ID": "TSave", "Text": T("v3.save"), "MinimumSize": [120, 30]})),
        ])
        ed_logos = ui.VGroup([
            row(L(T("logos.pick")), ui.ComboBox({"ID": "LogoPick"}), ui.Button({"ID": "LogoAdd", "Text": T("logos.add"), "Weight": 0})),
            row(ui.Button({"ID": "LogoPng", "Text": T("logos.own")}), ui.Button({"ID": "LogoImport", "Text": T("logos.import")})),
            row(ui.Button({"ID": "LogoPage", "Text": T("logos.page")}), ui.Button({"ID": "LogoUpdate", "Text": T("logos.update")})),
            ui.TextEdit({"ID": "LogoText", "ReadOnly": True}),
            ui.VGap(0, 1),
        ])
        ed_laurels = ui.VGroup([
            row(L(T("laurels.festival")), ui.ComboBox({"ID": "LFest"})),
            row(L(T("laurels.status")), ui.ComboBox({"ID": "LStatus"})),
            row(L(T("laurels.section")), ui.ComboBox({"ID": "LSection"})),
            row(L(T("laurels.year")), ui.SpinBox({"ID": "LYear", "Minimum": 1932, "Maximum": 2200, "Value": 2026}),
                L(T("laurels.award")), ui.LineEdit({"ID": "LAward"})),
            row(ui.Button({"ID": "LAdd", "Text": T("laurels.add")}), ui.Button({"ID": "LOfficial", "Text": T("laurels.official")})),
            ui.VGap(0, 1),
        ])
        p2 = ui.VGroup([
            help_label("v3.help2"),
            row(L(T("project.year")), ui.SpinBox({"ID": "Year", "Minimum": 1895, "Maximum": 2200, "Weight": 0}),
                L(T("project.owner")), ui.LineEdit({"ID": "Owner"}), L(T("project.language")), ui.ComboBox({"ID": "Lang", "Weight": 0})),
            ui.HGroup([
                ui.VGroup({"Weight": 1.3}, [
                    ui.Tree({"ID": "Outline", "SortingEnabled": False, "Events": {"ItemClicked": True}}),
                    row(ui.Button({"ID": "Up", "Text": T("v3.sec_up")}), ui.Button({"ID": "Down", "Text": T("v3.sec_down")}),
                        ui.Button({"ID": "DelSec", "Text": T("v3.sec_del")})),
                    row(ui.ComboBox({"ID": "AddElement"}), ui.Button({"ID": "AddEl", "Text": T("data.add"), "Weight": 0})),
                    row(ui.Button({"ID": "Reorder", "Text": T("data.reorder")}), ui.Button({"ID": "Suggest", "Text": T("data.suggest")})),
                    row(ui.Button({"ID": "Unfilled", "Text": T("v3.unfilled")}), ui.Button({"ID": "Import", "Text": T("data.import")})),
                    ui.Label({"ID": "PhCount", "Text": "", "Weight": 0, "StyleSheet": "color:#e0b04a;"}),
                ]),
                ui.VGroup({"Weight": 1}, [
                    ui.Label({"ID": "EdTitle", "Text": "", "Weight": 0, "StyleSheet": "font-weight:bold;"}),
                    ui.Stack({"ID": "EdStack"}, [ed_hint, ed_entry, ed_text, ed_logos, ed_laurels]),
                ]),
            ]),
            row(ui.Button({"ID": "Back1", "Text": T("v3.back")}), ui.HGap(0, 1), ui.Button({"ID": "Next1", "Text": T("v3.next"),
                                                                                               "MinimumSize": [160, 34]})),
        ])

        # ------------------------------------------------------------ passo 3
        p3 = ui.VGroup([
            help_label("v3.help3"),
            ui.Tree({"ID": "Sections", "SortingEnabled": False, "Events": {"ItemClicked": True}}),
            row(L(T("generate.where")), ui.ComboBox({"ID": "Where"}),
                ui.CheckBox({"ID": "UseTl", "Text": T("project.from_timeline"), "Checked": True})),
            row(ui.Button({"ID": "SyncChanged", "Text": T("v3.sync"), "MinimumSize": [320, 46]})),
            row(ui.Button({"ID": "Preview", "Text": T("generate.preview")}), ui.Button({"ID": "Check", "Text": T("generate.check")}),
                ui.Button({"ID": "Export", "Text": T("generate.export")})),
            L(T("generate.results")),
            ui.TextEdit({"ID": "Results", "ReadOnly": True}),
            row(ui.Button({"ID": "Back2", "Text": T("v3.back")}), ui.HGap(0, 1)),
        ])

        # ------------------------------------------------------------ aspetto e avanzate
        a_look = ui.VGroup([
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
            ui.VGap(0, 1),
        ])
        a_styles = ui.VGroup([
            row(L(T("style.override"), **lw), ui.ComboBox({"ID": "StyleKey"})),
            row(L(T("style.family"), **lw), ui.ComboBox({"ID": "SFamily", "Editable": True}), L(T("style.font_style")),
                ui.LineEdit({"ID": "SStyle"})),
            row(L(T("style.size"), **lw), ui.DoubleSpinBox({"ID": "SSize", "Minimum": 6, "Maximum": 400, "Decimals": 1}),
                L(T("style.color")), ui.LineEdit({"ID": "SColor"}), L(T("style.case")), ui.ComboBox({"ID": "SCase"})),
            row(L(T("style.tracking"), **lw), ui.DoubleSpinBox({"ID": "STrack", "Minimum": 0.5, "Maximum": 3, "SingleStep": 0.02, "Decimals": 2}),
                L(T("style.line_spacing")), ui.DoubleSpinBox({"ID": "SLine", "Minimum": 0.6, "Maximum": 3, "SingleStep": 0.05, "Decimals": 2})),
            row(ui.HGap(0, 1), ui.Button({"ID": "SReset", "Text": T("style.reset"), "Weight": 0}),
                ui.Button({"ID": "SApply", "Text": T("style.apply"), "Weight": 0})),
            ui.VGap(0, 1),
        ])
        a_timing = ui.VGroup([
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
        a_work = ui.VGroup([
            row(L(T("project.original_title"), **lw), ui.LineEdit({"ID": "OrigTitle"}), L(T("project.country")),
                ui.LineEdit({"ID": "Country", "Weight": 0.4})),
            row(L(T("project.ui_language"), **lw), ui.ComboBox({"ID": "UiLang"})),
            L(T("project.funding")),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[:6]]),
            row(*[ui.CheckBox({"ID": "F_" + f, "Text": f}) for f in FUNDING[6:]]),
            row(ui.CheckBox({"ID": "AiUsed", "Text": T("project.ai_used"), "Weight": 0}), L(T("project.ai_uses")), ui.LineEdit({"ID": "AiUses"})),
            ui.VGap(0, 1),
        ])
        a_more = ui.VGroup([
            row(L(T("style.render_mode"), **lw), ui.ComboBox({"ID": "Render"}), L(T("style.axis")),
                ui.SpinBox({"ID": "Axis", "Minimum": 20, "Maximum": 80})),
            row(L(T("generate.card_mode"), **lw), ui.ComboBox({"ID": "CardMode"})),
            row(ui.Button({"ID": "Lock", "Text": T("generate.lock")}), ui.Button({"ID": "SyncAll", "Text": T("generate.regenerate_all")}),
                ui.Button({"ID": "Calibrate", "Text": T("generate.calibrate")})),
            L(T("v3.sec_options")),
            row(L(T("data.hold"), **lw), ui.DoubleSpinBox({"ID": "Hold", "Minimum": 0, "Maximum": 60, "SingleStep": 0.5, "Decimals": 1}),
                L(T("data.before")), ui.DoubleSpinBox({"ID": "Before", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1}),
                L(T("data.after")), ui.DoubleSpinBox({"ID": "After", "Minimum": -1, "Maximum": 20, "SingleStep": 0.5, "Decimals": 1})),
            row(L(T("data.position"), **lw), ui.ComboBox({"ID": "Position"}), L(T("data.order")), ui.ComboBox({"ID": "Order"}),
                L(T("data.columns")), ui.ComboBox({"ID": "Columns"})),
            row(ui.CheckBox({"ID": "PageBreak", "Text": T("data.page_break")}), ui.CheckBox({"ID": "Team", "Text": T("data.team")}),
                ui.CheckBox({"ID": "SideLane", "Text": T("data.side_lane")}), ui.HGap(0, 1),
                ui.Button({"ID": "SecApply", "Text": T("v3.sec_apply"), "Weight": 0})),
            ui.VGap(0, 1),
        ])
        p4 = ui.VGroup([
            row(*[ui.Button({"ID": "A%d" % i, "Text": T("v3." + k), "Checkable": True})
                  for i, k in enumerate(["a_look", "a_styles", "a_timing", "a_work", "a_more"])]),
            ui.Stack({"ID": "AStack"}, [a_look, a_styles, a_timing, a_work, a_more]),
        ])

        main = ui.VGroup([
            ui.HGroup({"Weight": 0}, [
                ui.Label({"Text": "<b style='font-size:16px'>%s</b>" % T("app.title"), "Weight": 0}),
                ui.Label({"Text": T("app.subtitle"), "StyleSheet": "color:#9a9aa3;"}),
            ]),
            ui.HGroup([nav, ui.Stack({"ID": "Stack"}, [p1, p2, p3, p4])]),
            ui.Label({"ID": "Status", "Text": "", "Weight": 0, "WordWrap": True, "StyleSheet": "color:#e0b04a;"}),
        ])
        self.win = self.disp.AddWindow({"ID": "DRFCWin", "WindowTitle": "DR-FilmCredits", "Geometry": [60, 40, 1260, 880]}, main)
        self.it = self.win.GetItems()
        self._populate_static()
        self._bind()
        self.load_project_to_ui()
        self.go(0 if self.fresh else 1)

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
        self._tree_header("Outline", ["#", T("v3.rows_header"), T("v3.names_header")], [34, 380, 300])
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
        self.win.On.DRFCWin.Close = lambda ev: self.disp.ExitLoop()
        b = self._on
        for i in range(4):
            b("Step%d" % i, "Clicked", (lambda idx: lambda ev: self.go(idx))(i))
        for i in range(5):
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
        b("RNames", "ReturnPressed", lambda ev: self.on_entry("save"))
        b("RAdd", "Clicked", lambda ev: self.on_entry("add"))
        b("RDel", "Clicked", lambda ev: self.on_entry("del"))
        b("RBreak", "Clicked", lambda ev: self.on_entry("break"))
        b("TSave", "Clicked", self.on_text_save)
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
        b("SyncChanged", "Clicked", lambda ev: self.on_sync(True))
        b("SyncAll", "Clicked", lambda ev: self.on_sync(False))
        b("Check", "Clicked", self.on_check)
        b("Preview", "Clicked", self.on_preview)
        b("Export", "Clicked", self.on_export)
        b("Calibrate", "Clicked", self.on_calibrate)
        b("SecApply", "Clicked", self.on_sec_apply)

    def go(self, idx):
        self.ui_to_project()
        self.it["Stack"].CurrentIndex = idx
        for i in range(4):
            self.it["Step%d" % i].Checked = (i == idx)
        if idx == 1:
            self.refresh_outline()
        elif idx == 2:
            self.refresh_sections()
        elif idx == 3:
            self.go_aspect(self._aspect if hasattr(self, "_aspect") else 0)

    def go_aspect(self, i):
        self._aspect = i
        self.it["AStack"].CurrentIndex = i
        for k in range(5):
            self.it["A%d" % k].Checked = (k == i)
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
        tree = self.it["Outline"]
        tree.Clear()
        self.items = []
        for i, r in enumerate(self.rows):
            t = tree.NewItem()
            t.Text[0] = str(i + 1)
            t.Text[1] = r["label"]
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
        try:
            idx = int(ev["item"].Text[0]) - 1
        except Exception:
            return
        self.select(idx)

    def show_editor(self, page):
        self.it["EdStack"].CurrentIndex = page

    def select(self, idx, focus=False):
        """Seleziona una riga dell'elenco e mostra l'editor adatto."""
        if not (0 <= idx < len(self.rows)):
            self.sel = -1
            self.show_editor(ED_HINT)
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
        elif row["kind"] == "entry":
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
            outline.set_entry(self.project, row, role, names or [placeholders.texts(self.project["meta"]["language"])["name"]])
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
            nxt = self._next_entry(self.sel)
            if nxt != self.sel:
                self.select(nxt, focus=True)
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
        self.status(self.T("v3.msg_row_saved"))

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
        where = WHERE[self._idx("Where")]
        res = sess.sync(self.project, self._work_dir(), where=where, track="dr", only_changed=only_changed,
                        progress=self.status, card_mode=self._card_mode())
        msgs = [("✔ " if r["ok"] else "✖ ") + r["message"] for r in res["sections"]]
        msgs += ["   " + n for n in res["notes"]] + ["   " + l for l in sess.log]
        if self.path:
            model.save(self.project, self.path)
        self._report(res["issues"], msgs)
        self.refresh_sections()
        self.status(self.T("generate.ok"))

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
