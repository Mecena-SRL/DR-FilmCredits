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
            self._p.setdefault("CurrentIndex", 0)
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
            self._p[k] = v

    # ComboBox
    def AddItem(self, t):
        self.items.append(t)

    def Clear(self):
        del self.items[:]
        del self.top[:]

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
    def __init__(self, props, root):
        self.props = props
        self.On = On()
        self.ids = {}
        self._collect(root)
        self.shown = False

    def _collect(self, w):
        if isinstance(w, Widget):
            if "ID" in w._p:
                self.ids[w._p["ID"]] = w
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
    def __init__(self, ui):
        self.ui = ui
        self.windows = []

    def AddWindow(self, props, root):
        w = Window(props, root)
        self.windows.append(w)
        return w

    def RunLoop(self):
        pass

    def ExitLoop(self):
        pass


class FakeBmd(object):
    @staticmethod
    def UIDispatcher(ui):
        return Dispatcher(ui)


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
class FakeTool(object):
    def __init__(self, name):
        self.name = name
        self.inputs = {}

    def SetInput(self, k, v, *a):
        self.inputs[k] = v

    def GetAttrs(self, *a):
        return {"TOOLIT_Clip_Width": {1: 1000}}


class FakeComp(object):
    def __init__(self, path, start=0):
        self.path = path
        self.start = start
        self.tools = {}

    def GetAttrs(self):
        return {"COMPN_RenderStart": self.start, "COMPN_GlobalStart": self.start}

    def FindTool(self, name):
        return self.tools.setdefault(name, FakeTool(name))

    def Lock(self):
        pass

    def Unlock(self):
        pass


class FakeItem(object):
    def __init__(self, mpi, start, dur, track):
        self.mpi, self.start, self.dur, self.track = mpi, start, dur, track
        self.comps = []
        self.names = []

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

    comp_start = 0

    def GetFusionCompNameList(self):
        return list(self.names)

    def DeleteFusionCompByName(self, n):
        i = self.names.index(n)
        del self.names[i]
        del self.comps[i]

    def RenameFusionCompByName(self, old, new):
        self.names[self.names.index(old)] = new

    def LoadFusionCompByName(self, n):
        return True


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
    def __init__(self, **kw):
        self.tl = FakeTimeline(**kw)
        self.project = FakeProject(self.tl)

    def GetProjectManager(self):
        return self

    def GetCurrentProject(self):
        return self.project
