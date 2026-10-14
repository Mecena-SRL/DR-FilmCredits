"""Finti UIManager / Resolve per testare wizard e bridge senza DaVinci Resolve."""

import os


class _TextProxy(dict):
    def __getitem__(self, k):
        return dict.get(self, k, "")


class Widget(object):
    def __init__(self, kind, props=None, children=None):
        object.__setattr__(self, "_p", {"kind": kind})
        self._p.update(props or {})
        object.__setattr__(self, "children", children or [])
        object.__setattr__(self, "items", [])
        object.__setattr__(self, "top", [])
        object.__setattr__(self, "Text", _TextProxy() if kind == "TreeItem" else props.get("Text", "") if props else "")
        if kind in ("ComboBox",):
            self._p.setdefault("CurrentIndex", -1)  # come Qt: vuoto = -1
        if kind == "Tree":
            self._p["ColumnWidth"] = {}
        for k, v in {"PlainText": "", "Checked": props.get("Checked", False) if props else False, "Value": 0, "Enabled": True}.items():
            self._p.setdefault(k, v)

    def __getattr__(self, k):
        try:
            return self._p[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        if k == "Text":
            object.__setattr__(self, "Text", v)
        else:
            if k == "Value" and self._p.get("kind") == "SpinBox":
                v = int(v)
            changed = self._p.get(k) != v
            self._p[k] = v
            q = self._p.get("_queue")
            if q is not None and changed and k == "CurrentIndex":
                q.append((self._p.get("ID"), "CurrentIndexChanged"))

    # ComboBox
    def AddItem(self, t):
        self.items.append(t)
        if self._p.get("kind") == "ComboBox" and self._p.get("CurrentIndex", -1) == -1:
            self.CurrentIndex = 0  # il primo elemento diventa corrente (genera evento)

    def Clear(self):
        del self.items[:]
        del self.top[:]
        if self._p.get("kind") == "ComboBox":
            self.CurrentIndex = -1

    @property
    def CurrentText(self):
        i = self._p.get("CurrentIndex", 0)
        return self.items[i] if 0 <= i < len(self.items) else ""

    # Tree
    def NewItem(self):
        return Widget("TreeItem")

    def AddTopLevelItem(self, it):
        self.top.append(it)

    def SetHeaderItem(self, it):
        self._p["header"] = it


class On(object):
    def __init__(self):
        object.__setattr__(self, "slots", {})

    def __getattr__(self, k):
        slots = self.slots
        if k not in slots:
            class Slot(object):
                pass
            slots[k] = Slot()
        return slots[k]


class Window(object):
    def __init__(self, props, root, queued=False):
        self.props = props
        self.On = On()
        self.ids = {}
        self.queue = [] if queued else None
        self._collect(root)
        self.shown = False

    def deliver(self):
        """Consegna gli eventi accodati (come fa RunLoop in Resolve)."""
        while self.queue:
            cid, ev = self.queue.pop(0)
            fn = getattr(getattr(self.On, cid), ev, None)
            if fn is not None and callable(fn):
                fn({})

    def _collect(self, w):
        if isinstance(w, Widget):
            if "ID" in w._p:
                self.ids[w._p["ID"]] = w
                if self.queue is not None:
                    w._p["_queue"] = self.queue
            for c in w.children:
                self._collect(c)

    def GetItems(self):
        return self.ids

    def Show(self):
        self.shown = True

    def Hide(self):
        self.shown = False

    def fire(self, cid, event, **ev):
        fn = getattr(getattr(self.On, cid), event)
        fn(ev)


class UIManager(object):
    def __getattr__(self, kind):
        def make(props=None, children=None, *rest):
            if isinstance(props, list):
                props, children = {}, props
            if not isinstance(props, dict):
                props = {}
            if not isinstance(children, list):
                children = []
            return Widget(kind, props, children)
        return make


class Dispatcher(object):
    queued = False

    def __init__(self, ui):
        self.ui = ui
        self.windows = []
        self.exited = 0
        self.loops = 0

    def AddWindow(self, props, root):
        w = Window(props, root, queued=self.queued)
        self.windows.append(w)
        return w

    def RunLoop(self):
        self.loops += 1
        for w in self.windows:
            w.deliver()

    def ExitLoop(self):
        self.exited += 1


class FakeBmd(object):
    queued = False

    def UIDispatcher(self, ui):
        d = Dispatcher(ui)
        d.queued = self.queued
        return d


class QueuedBmd(FakeBmd):
    """Come Resolve: gli eventi generati dal codice arrivano quando parte RunLoop."""
    queued = True


class FakeFusion(object):
    def __init__(self, request=None):
        self.UIManager = UIManager()
        self.request = request

    def RequestFile(self, *a, **k):
        return self.request

    def RequestDir(self, *a, **k):
        return self.request

    def GetCurrentComp(self):
        return None


# --------------------------------------------------------------------- Resolve
class FakeOutput(object):
    def __init__(self, tool):
        self.tool = tool

    def GetTool(self):
        return self.tool


class FakeInput(object):
    def __init__(self, tool, iid):
        self.tool, self.iid = tool, iid

    def GetConnectedOutput(self):
        src = self.tool.links.get(self.iid)
        return FakeOutput(src) if src is not None else None

    def GetAttrs(self):
        return {"INPS_ID": self.iid}


class FakeTool(object):
    def __init__(self, name, reg="Tool"):
        self.Name = name
        self.reg = reg
        self.inputs = {}
        self.links = {}

    def SetInput(self, k, v, *a):
        self.inputs[k] = v

    def GetAttrs(self, *a):
        return {"TOOLIT_Clip_Width": {1: 1000}, "TOOLS_Name": self.Name, "TOOLS_RegID": self.reg}

    def ConnectInput(self, iid, tool):
        self.links[iid] = tool
        return True

    def GetInputList(self):
        return {i + 1: FakeInput(self, k) for i, k in enumerate(self.links)}

    @property
    def Input(self):
        return FakeInput(self, "Input")


class _Image(object):
    def __init__(self, dw):
        self.DataWindow = dw


class _Out(object):
    def __init__(self, tool):
        self.tool = tool

    def __getitem__(self, t):
        return self.tool.render()


class ProbeTool(FakeTool):
    """Text+ che 'renderizza' con le metriche reali del font e una scala nota (k_true)."""
    k_true = 1.0 / 1.2
    comp_width = 1920.0
    bearing = 0.03  # side-bearing: 3% dell'em per lato

    def __init__(self, name="Text1"):
        FakeTool.__init__(self, name, "TextPlus")
        self.deleted = False

    @property
    def Output(self):
        return _Out(self)

    def Delete(self):
        self.deleted = True

    def render(self):
        from drfc.fontmetrics import FontIndex
        fam, sty = self.inputs.get("Font", "Inter"), self.inputs.get("Style", "Regular")
        fi, _ = FontIndex(cache_path=None).font(fam, sty)
        text = self.inputs.get("StyledText", "H")
        em = self.inputs.get("Size", 0.02) * self.comp_width * self.k_true
        ink = fi.text_width_em(text) * em - 2 * self.bearing * em
        cx = self.inputs.get("Center", {1: 0.5})[1] * self.comp_width
        if self.inputs.get("HorizontalLeftCenterRight", 0) == self.left_value:
            x1 = cx
        else:
            x1 = cx - ink / 2.0
        return _Image({1: x1, 2: 0.0, 3: x1 + ink, 4: em})

    left_value = -1


class FakeComp(object):
    def __init__(self, path, start=0):
        self.path = path
        self.start = start
        self.tools = {}
        if path and os.path.exists(path):
            import re
            text = open(path, encoding="utf-8").read()
            for name, reg in re.findall(r"\n\t\t(\w+) = (\w+) \{", text):
                self.tools[name] = FakeTool(name, reg)
            last = re.search(r"MediaOut1 = MediaOut \{.*?SourceOp = \"(\w+)\"", text, re.S)
            if last and "MediaOut1" in self.tools:
                self.tools["MediaOut1"].links["Input"] = self.tools.get(last.group(1))
        self.pasted = []

    def GetAttrs(self):
        return {"COMPN_RenderStart": self.start, "COMPN_GlobalStart": self.start}

    def FindTool(self, name):
        return self.tools.setdefault(name, FakeTool(name))

    CurrentTime = 0

    def AddTool(self, reg, x=0, y=0):
        t = ProbeTool("Text%d" % (len(self.tools) + 1))
        self.tools[t.Name] = t
        return t

    def GetToolList(self, selected=False):
        return {i + 1: t for i, t in enumerate(self.tools.values())}

    def CopySettings(self, tools):
        return {"tools": [t.Name for t in tools]}

    def Paste(self, settings):
        for n in settings["tools"]:
            self.tools[n] = FakeTool(n)
        self.pasted.append(settings)
        return True

    def Lock(self):
        pass

    def Unlock(self):
        pass


class FakeItem(object):
    comp_start = 0

    def __init__(self, mpi, start, dur, track):
        self.mpi, self.start, self.dur, self.track = mpi, start, dur, track
        self.comps = []
        self.names = []
        self.props = {}
        self.color = ""

    def GetDuration(self, *a):
        return self.dur

    def GetStart(self):
        return self.start

    def GetMediaPoolItem(self):
        return self.mpi

    def ImportFusionComp(self, path):
        c = FakeComp(path, start=self.comp_start)
        self.comps.append(c)
        self.names.append("Composition %d" % len(self.comps))
        return c

    def AddFusionComp(self):
        c = FakeComp(None, start=self.comp_start)
        self.comps.append(c)
        self.names.append("Composition %d" % len(self.comps))
        return c

    def GetFusionCompNameList(self):
        return list(self.names)

    def GetFusionCompCount(self):
        return len(self.comps)

    def GetFusionCompByIndex(self, i):
        return self.comps[i - 1]

    def GetFusionCompByName(self, n):
        return self.comps[self.names.index(n)] if n in self.names else None

    def DeleteFusionCompByName(self, n):
        i = self.names.index(n)
        del self.names[i]
        del self.comps[i]

    def RenameFusionCompByName(self, old, new):
        self.names[self.names.index(old)] = new

    def LoadFusionCompByName(self, n):
        return True

    def GetProperty(self, k):
        return self.props.get(k)

    def SetProperty(self, k, v):
        self.props[k] = v
        return True

    def GetClipColor(self):
        return self.color

    def SetClipColor(self, c):
        self.color = c


class FakeMPI(object):
    def __init__(self, path, frames=None):
        self.path = path
        self.frames = frames

    def GetName(self):
        return os.path.basename(self.path)


class FakeTimeline(object):
    def __init__(self, still_ok=True, settings=None):
        self.tracks = {1: [], 2: []}
        self.names = {1: "V1", 2: "V2"}
        self.still_ok = still_ok
        self.settings = settings or {"timelineResolutionWidth": "3840", "timelineResolutionHeight": "2160",
                                     "timelineFrameRate": "25"}
        self.deleted = []

    def GetSetting(self, k):
        return self.settings.get(k)

    def GetTrackCount(self, kind):
        return len(self.tracks)

    def AddTrack(self, kind):
        n = len(self.tracks) + 1
        self.tracks[n] = []
        self.names[n] = "Video %d" % n
        return True

    def SetTrackName(self, kind, i, name):
        self.names[i] = name

    def GetTrackName(self, kind, i):
        return self.names[i]

    def GetItemListInTrack(self, kind, i):
        return list(self.tracks[i])

    def GetStartFrame(self):
        return 90000

    def GetEndFrame(self):
        return 90000 + 2400

    def GetCurrentTimecode(self):
        return "01:00:10:00"

    def DeleteClips(self, items, ripple=False):
        for it in items:
            for t in self.tracks.values():
                if it in t:
                    t.remove(it)
            self.deleted.append(it)
        return True

    def InsertFusionCompositionIntoTimeline(self):
        return None


class FakeMediaPool(object):
    def __init__(self, timeline):
        self.tl = timeline
        self.folders = []

    def GetRootFolder(self):
        return self

    def GetSubFolderList(self):
        return self.folders

    def AddSubFolder(self, root, name):
        f = type("F", (), {"GetName": lambda s: name})()
        self.folders.append(f)
        return f

    def SetCurrentFolder(self, f):
        return True

    def ImportMedia(self, items):
        it = items[0]
        if isinstance(it, dict):
            return [FakeMPI(it["FilePath"], it["EndIndex"] - it["StartIndex"] + 1)]
        return [FakeMPI(it)]

    def AppendToTimeline(self, infos):
        out = []
        for i in infos:
            mpi = i["mediaPoolItem"]
            want = i["endFrame"] - i["startFrame"] + 1
            dur = want if (mpi.frames or self.tl.still_ok) else 125
            item = FakeItem(mpi, i["recordFrame"], dur, i["trackIndex"])
            self.tl.tracks[i["trackIndex"]].append(item)
            out.append(item)
        return out


class FakeProject(object):
    def __init__(self, tl):
        self.tl = tl
        self.mp = FakeMediaPool(tl)

    def GetCurrentTimeline(self):
        return self.tl

    def GetMediaPool(self):
        return self.mp

    def GetSetting(self, k):
        return None


class FakeResolve(object):
    def GetVersionString(self):
        return "20.0.0.1"

    def __init__(self, **kw):
        self.tl = FakeTimeline(**kw)
        self.project = FakeProject(self.tl)

    def GetProjectManager(self):
        return self

    def GetCurrentProject(self):
        return self.project
