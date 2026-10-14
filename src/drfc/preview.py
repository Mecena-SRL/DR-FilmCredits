"""Anteprima HTML animata, fedele a layout e tempi (stessa funzione di scorrimento).

Si apre nel browser: play/pausa, timeline a frame, guide safe-area. Utile per rivedere
i titoli prima di generarli in Resolve o per mandarli in approvazione (Eurimages, MiC,
broadcaster) come bozza.
"""

import html
import json
import os

from . import design


def _el_json(e, base_dir):
    if e["kind"] == "text":
        st = e["style"]
        return {"k": "t", "lines": e["lines"], "x": e["x"], "b": e["baseline"], "adv": e["advance"],
                "a": e["anchor"], "font": st["family"], "style": st.get("style", "Regular"),
                "size": st["size_px"], "color": st.get("color", "#fff"),
                "track": (float(st.get("tracking", 1.0)) - 1.0) * st["size_px"]}
    src = e["path"]
    try:
        src = os.path.relpath(src, base_dir).replace(os.sep, "/")
    except ValueError:
        src = "file:///" + src.replace(os.sep, "/")
    return {"k": "v" if e["kind"] == "video" else "i", "src": src, "x": e["x"], "y": e["top"], "w": e["w"], "h": e["h"]}


def build_html(project, results, out_path):
    """results: lista di (sequence, layout, timeline, notes)."""
    base_dir = os.path.dirname(os.path.abspath(out_path))
    seqs = []
    for seq, lay, tl, notes in results:
        d = {"id": seq["id"], "name": seq.get("name", seq["id"]), "kind": lay["kind"], "tl": tl, "notes": notes,
             "warnings": [w["message"] for w in lay.get("warnings", [])]}
        if lay["kind"] == "crawl":
            d["els"] = [_el_json(e, base_dir) for e in lay["elements"]]
        else:
            d["cards"] = [[_el_json(e, base_dir) for e in c["elements"]] for c in lay["cards"]]
        seqs.append(d)
    bg = design.background(project["format"])
    if bg.get("path"):
        try:
            bg["src"] = os.path.relpath(bg["path"], base_dir).replace(os.sep, "/")
        except ValueError:
            bg["src"] = "file:///" + bg["path"].replace(os.sep, "/")
    sl, st, sr, sb = design.safe_box(project["format"])
    W = project["format"]["width"]
    lane = None
    if bg["mode"] == "panel":
        split = project["layout"].get("split", "none")
        tl_ = float(project["layout"].get("text_lane", 0.5))
        x0, x1 = (sr - (sr - sl) * tl_, W) if split == "media_left" else ((0, sl + (sr - sl) * tl_) if split == "media_right" else (0, W))
        lane = [max(0, x0 - W * 0.02), min(W, x1 + W * 0.02)]
    data = {"W": W, "H": project["format"]["height"], "fps": project["format"]["fps"],
            "safebox": [sl, st, sr, sb], "bg": bg, "lane": lane,
            "title": project["meta"].get("title", ""), "seqs": seqs}
    page = TEMPLATE.replace("/*FONTS*/", _font_faces(results, base_dir))
    page = page.replace("/*DATA*/", json.dumps(data, ensure_ascii=False)).replace(
        "<!--TITLE-->", html.escape(project["meta"].get("title") or "DR-FilmCredits"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


def _weight(style):
    st = (style or "").lower()
    for k, w in (("thin", 100), ("extralight", 200), ("light", 300), ("semibold", 600), ("extrabold", 800),
                 ("bold", 700), ("black", 900), ("medium", 500)):
        if k in st:
            return w
    return 400


def _font_faces(results, base_dir):
    """@font-face per i font usati, cosi' l'anteprima usa gli stessi file del rendering."""
    from . import engine
    from .fontmetrics import FontIndex, default_cache_path
    used = set()
    for _seq, lay, _tl, _n in results:
        els = lay.get("elements") or [e for c in lay.get("cards", []) for e in c["elements"]]
        for e in els:
            if e["kind"] == "text":
                used.add((e["style"]["family"], e["style"].get("style", "Regular")))
    idx = FontIndex(extra_dirs=engine.font_dirs_extra(), cache_path=default_cache_path())
    css = []
    for fam, sty in sorted(used):
        rec, score = idx.find(fam, sty)
        if not rec or score < 2:
            continue
        try:
            url = os.path.relpath(rec["path"], base_dir).replace(os.sep, "/")
        except ValueError:
            url = "file:///" + rec["path"].replace(os.sep, "/")
        css.append("@font-face{font-family:'%s';src:url('%s');font-weight:%d;font-style:%s}" % (
            fam.replace("'", ""), url, _weight(sty), "italic" if "italic" in sty.lower() or "oblique" in sty.lower() else "normal"))
    return "\n".join(css)


TEMPLATE = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title><!--TITLE--> – anteprima titoli</title>
<style>
/*FONTS*/
:root{--bg:#0e0e10;--panel:#18181b;--fg:#e7e7ea;--muted:#9a9aa3;--accent:#e0b04a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}
header{display:flex;gap:12px;align-items:center;padding:10px 16px;background:var(--panel);flex-wrap:wrap}
header h1{font-size:15px;margin:0 12px 0 0;font-weight:600}
select,button,label{font:inherit;color:var(--fg)}select,button{background:#26262b;border:1px solid #333;border-radius:6px;padding:5px 10px}
button.on{border-color:var(--accent);color:var(--accent)}
#stage{display:flex;justify-content:center;padding:16px}
#frame{position:relative;width:100%;max-width:1280px;aspect-ratio:var(--ar);background:#000 repeating-conic-gradient(#111 0 25%,#000 0 50%) 0 0/24px 24px;overflow:hidden}
svg{position:absolute;inset:0;width:100%;height:100%}
#bar{display:flex;gap:10px;align-items:center;padding:0 16px 12px;max-width:1312px;margin:auto}
#scrub{flex:1}#tc{font-variant-numeric:tabular-nums;min-width:170px;text-align:right;color:var(--muted)}
#info{max-width:1312px;margin:auto;padding:0 16px 24px;color:var(--muted)}#info li.w{color:#f0a35e}
</style></head><body>
<header><h1><!--TITLE--></h1><select id="seq"></select>
<button id="play">▶ Play</button><button id="safe" class="on">Safe area</button>
<label><input type="checkbox" id="loop" checked> Loop</label></header>
<div id="stage"><div id="frame"><svg id="svg"></svg></div></div>
<div id="bar"><input type="range" id="scrub" min="0" value="0"><span id="tc"></span></div>
<div id="info"></div>
<script>
const D=/*DATA*/;
const NS="http://www.w3.org/2000/svg";
const svg=document.getElementById('svg'),scrub=document.getElementById('scrub'),tc=document.getElementById('tc');
document.getElementById('frame').style.setProperty('--ar',D.W+'/'+D.H);
svg.setAttribute('viewBox','0 0 '+D.W+' '+D.H);
let S=null,frame=0,playing=false,last=0,showSafe=true;
const sel=document.getElementById('seq');
D.seqs.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s.name+' ('+s.kind+')';sel.appendChild(o)});
function scrollAt(tl,f){let x=f-tl.lead_in;if(x<=0)return 0;let m=x;for(const h of tl.holds){const a=h.start-tl.lead_in;m-=Math.min(Math.max(x-a,0),h.frames)}return Math.min(m*tl.speed_px,tl.travel_px)}
function cardOp(c,f){const fi=Math.max(c.fade_in,1),fo=Math.max(c.fade_out,1);return Math.max(0,Math.min(1,(f-c.start)/fi,(c.start+c.frames-f)/fo))}
function weight(st){st=st.toLowerCase();if(st.includes('thin'))return 100;if(st.includes('extralight'))return 200;if(st.includes('light'))return 300;if(st.includes('semibold'))return 600;if(st.includes('extrabold'))return 800;if(st.includes('bold'))return 700;if(st.includes('black'))return 900;if(st.includes('medium'))return 500;return 400}
function mk(e,dy,op){
 if(e.k==='t'){const t=document.createElementNS(NS,'text');t.setAttribute('x',e.x);t.setAttribute('font-family',"'"+e.font+"', serif");
  t.setAttribute('font-size',e.size);t.setAttribute('font-weight',weight(e.style));if(/italic|oblique/i.test(e.style))t.setAttribute('font-style','italic');
  t.setAttribute('fill',e.color);t.setAttribute('letter-spacing',e.track);t.setAttribute('text-anchor',{left:'start',center:'middle',right:'end'}[e.a]);
  if(op<1)t.setAttribute('opacity',op);
  e.lines.forEach((l,i)=>{const s=document.createElementNS(NS,'tspan');s.setAttribute('x',e.x);s.setAttribute('y',e.b+dy+i*e.adv);s.textContent=l||' ';t.appendChild(s)});return t}
 const im=document.createElementNS(NS,e.k==='v'?'foreignObject':'image');
 im.setAttribute('x',e.x-e.w/2);im.setAttribute('y',e.y+dy);im.setAttribute('width',e.w);im.setAttribute('height',e.h);if(op<1)im.setAttribute('opacity',op);
 if(e.k==='v'){im.innerHTML='<video xmlns="http://www.w3.org/1999/xhtml" src="'+e.src+'" muted autoplay loop style="width:100%;height:100%;object-fit:contain;background:#222"></video>'}
 else im.setAttribute('href',e.src);return im}
function rect(x,y,w,h,fill,op){const r=document.createElementNS(NS,'rect');r.setAttribute('x',x);r.setAttribute('y',y);r.setAttribute('width',w);r.setAttribute('height',h);r.setAttribute('fill',fill);if(op!==undefined)r.setAttribute('fill-opacity',op);svg.appendChild(r);return r}
function drawBg(){const b=D.bg;if(!b)return;
 if(b.mode==='color')rect(0,0,D.W,D.H,b.color);
 else if(b.mode==='gradient'){const c=b.colors||['#000','#222'];const d=document.createElementNS(NS,'defs');d.innerHTML='<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+c[0]+'"/><stop offset="1" stop-color="'+c[c.length-1]+'"/></linearGradient>';svg.appendChild(d);rect(0,0,D.W,D.H,'url(#g)')}
 else if(b.mode==='media'){const im=document.createElementNS(NS,'image');im.setAttribute('href',b.src||'');im.setAttribute('width',D.W);im.setAttribute('height',D.H);im.setAttribute('preserveAspectRatio','xMidYMid slice');if(b.blur)im.setAttribute('style','filter:blur('+(b.blur/4)+'px)');svg.appendChild(im);rect(0,0,D.W,D.H,'#000',b.dim===undefined?0.5:b.dim)}
 else if(b.mode==='dim')rect(0,0,D.W,D.H,'#000',b.opacity===undefined?0.5:b.opacity);
 else if(b.mode==='panel'&&D.lane)rect(D.lane[0],0,D.lane[1]-D.lane[0],D.H,b.color||'#000',b.opacity===undefined?0.85:b.opacity)}
function draw(){svg.textContent='';
 drawBg();
 if(S.kind==='crawl'){const s=scrollAt(S.tl,frame),dy=D.H-s;for(const e of S.els){const top=(e.k==='t'?e.b-e.size:e.y)+dy,bot=(e.k==='t'?e.b+e.lines.length*e.adv:e.y+e.h)+dy;if(bot<-50||top>D.H+50)continue;svg.appendChild(mk(e,dy,1))}}
 else{S.tl.cards.forEach((c,i)=>{const op=cardOp(c,frame);if(op<=0)return;for(const e of S.cards[i])svg.appendChild(mk(e,0,op))})}
 if(showSafe){const b=D.safebox;const r=document.createElementNS(NS,'rect');r.setAttribute('x',b[0]);r.setAttribute('y',b[1]);r.setAttribute('width',b[2]-b[0]);r.setAttribute('height',b[3]-b[1]);r.setAttribute('fill','none');r.setAttribute('stroke','#e0b04a');r.setAttribute('stroke-opacity','.45');r.setAttribute('stroke-dasharray','8 8');r.setAttribute('vector-effect','non-scaling-stroke');svg.appendChild(r)}
 const fps=S.tl.fps,secs=frame/fps;tc.textContent='frame '+frame+' / '+(S.tl.total_frames-1)+'  ·  '+secs.toFixed(2)+'s / '+(S.tl.total_frames/fps).toFixed(2)+'s';scrub.value=frame}
function pick(i){S=D.seqs[i];frame=0;scrub.max=S.tl.total_frames-1;
 const tl=S.tl;let h='<ul>';if(S.kind==='crawl')h+='<li>Velocità: <b>'+tl.speed_px+' px/frame</b> · durata '+(tl.total_frames/tl.fps).toFixed(2)+'s · '+tl.holds.length+' pause</li>';
 else h+='<li>'+tl.cards.length+' cartelli · durata '+(tl.total_frames/tl.fps).toFixed(2)+'s</li>';
 (S.notes||[]).forEach(n=>h+='<li>'+n+'</li>');(S.warnings||[]).forEach(n=>h+='<li class="w">⚠ '+n+'</li>');document.getElementById('info').innerHTML=h+'</ul>';draw()}
function tick(t){if(playing){const fps=S.tl.fps;if(t-last>=1000/fps-1){last=t;frame++;if(frame>=S.tl.total_frames){if(document.getElementById('loop').checked)frame=0;else{frame=S.tl.total_frames-1;toggle()}}draw()}}requestAnimationFrame(tick)}
function toggle(){playing=!playing;document.getElementById('play').textContent=playing?'❚❚ Pausa':'▶ Play'}
document.getElementById('play').onclick=toggle;
document.getElementById('safe').onclick=e=>{showSafe=!showSafe;e.target.classList.toggle('on',showSafe);draw()};
scrub.oninput=()=>{frame=+scrub.value;draw()};sel.onchange=()=>pick(+sel.value);
document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();toggle()}if(e.code==='ArrowRight'){frame=Math.min(frame+1,S.tl.total_frames-1);draw()}if(e.code==='ArrowLeft'){frame=Math.max(frame-1,0);draw()}});
pick(0);requestAnimationFrame(tick);
</script></body></html>
"""
