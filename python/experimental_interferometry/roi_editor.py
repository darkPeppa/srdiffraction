"""Инструмент ручной разметки ROI: автономная HTML-страница (без сервера и установки).

Открывается в любом браузере (Windows/macOS/Linux): results/interferometry/roi_editor/index.html.
Оператор выбирает кадр, рисует прямоугольники с метками (surface, bottom, left_edge,
right_edge, good_fringes, exclude), задаёт направление полос, при наличии —
независимый масштаб мкм/пиксель с указанием источника. Кнопка «Сохранить JSON»
скачивает <file_id>.json — его кладут в config/interferometry_roi/. Исходные
изображения не изменяются; координаты — в пикселях исходного снимка.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .archive_inventory import file_id, list_images

HTML = r"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>ROI интерферограмм</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#fcfcfb;--fg:#0b0b0b;--muted:#52514e;--line:#d9d8d4;--acc:#2a78d6}
@media (prefers-color-scheme: dark){:root{--bg:#1a1a19;--fg:#f0efec;--muted:#c3c2b7;--line:#3a3a38;--acc:#3987e5}}
body{margin:0;font:14px system-ui,sans-serif;background:var(--bg);color:var(--fg);display:flex;height:100vh}
#side{width:300px;overflow:auto;border-right:1px solid var(--line);padding:8px;box-sizing:border-box}
#main{flex:1;overflow:auto;position:relative}
#side li{cursor:pointer;padding:2px 4px;list-style:none;font-size:12px}#side li.sel{background:var(--acc);color:#fff}
canvas{display:block}label,select,input,button{font-size:13px}.row{margin:6px 0}
small{color:var(--muted)}#list{padding:0;margin:0}
</style></head><body>
<div id="side"><b>Кадры</b> <small>(клик — открыть)</small><ul id="list"></ul><hr>
<div class="row">Метка: <select id="lab"><option>surface</option><option>bottom</option><option>left_edge</option>
<option>right_edge</option><option>good_fringes</option><option>exclude</option></select></div>
<div class="row"><small>Тяните мышью прямоугольник. Shift+клик по прямоугольнику — удалить.</small></div>
<div class="row">Направление полос (°): <input id="ang" size="5" placeholder="авто"></div>
<div class="row">Масштаб, мкм/пкс: <input id="scale" size="7"><br>Источник масштаба: <input id="src" size="22"
 placeholder="эталон/паспорт (НЕ размер отверстия)"></div>
<div class="row">Отверстие (если известно независимо): <input id="ap" size="6"> мкм<br>основание: <input id="apb" size="22"></div>
<div class="row">Z-координаты (мкм) из окна прибора: <input id="zc" size="18" placeholder="напр. -20.331"></div>
<div class="row">Комментарий: <input id="note" size="26"></div>
<div class="row"><button id="save">Сохранить JSON</button> <button id="clear">Очистить</button></div>
<small id="info"></small></div>
<div id="main"><canvas id="cv"></canvas></div>
<script>
const FILES = __FILES__;
let cur=null, img=new Image(), rois=[], drag=null;
const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const colors={surface:'#1baf7a',bottom:'#2a78d6',left_edge:'#eb6834',right_edge:'#e87ba4',good_fringes:'#eda100',exclude:'#e34948'};
function draw(){ctx.drawImage(img,0,0);for(const r of rois){ctx.strokeStyle=colors[r.label];ctx.lineWidth=2;
 ctx.strokeRect(r.x0,r.y0,r.x1-r.x0,r.y1-r.y0);ctx.fillStyle=colors[r.label];ctx.fillText(r.label,r.x0+3,r.y0+12);}
 if(drag){ctx.strokeStyle='#fff';ctx.strokeRect(drag.x0,drag.y0,drag.x1-drag.x0,drag.y1-drag.y0);}}
function open(i){cur=FILES[i];rois=[];document.querySelectorAll('#list li').forEach((l,j)=>l.className=j==i?'sel':'');
 img.onload=()=>{cv.width=img.width;cv.height=img.height;draw();};img.src=cur.src;
 document.getElementById('info').textContent=cur.file+' ('+cur.id+')';}
FILES.forEach((f,i)=>{const li=document.createElement('li');li.textContent=f.file;li.onclick=()=>open(i);
 document.getElementById('list').appendChild(li);});
function pos(e){const b=cv.getBoundingClientRect();return [Math.round(e.clientX-b.left),Math.round(e.clientY-b.top)];}
cv.onmousedown=e=>{const [x,y]=pos(e);if(e.shiftKey){rois=rois.filter(r=>!(x>=r.x0&&x<=r.x1&&y>=r.y0&&y<=r.y1));draw();return;}
 drag={x0:x,y0:y,x1:x,y1:y};};
cv.onmousemove=e=>{if(!drag)return;[drag.x1,drag.y1]=pos(e);draw();};
cv.onmouseup=()=>{if(!drag)return;const r={label:document.getElementById('lab').value,
 x0:Math.min(drag.x0,drag.x1),y0:Math.min(drag.y0,drag.y1),x1:Math.max(drag.x0,drag.x1),y1:Math.max(drag.y0,drag.y1)};
 drag=null;if(r.x1-r.x0>3&&r.y1-r.y0>3)rois.push(r);draw();};
document.getElementById('clear').onclick=()=>{rois=[];draw();};
document.getElementById('save').onclick=()=>{if(!cur)return;const v=id=>document.getElementById(id).value||null;
 const out={file:cur.file,file_id:cur.id,rois:rois,fringe_angle_deg:v('ang')?parseFloat(v('ang')):null,
 lateral_um_per_px:v('scale')?parseFloat(v('scale')):null,lateral_scale_source:v('src'),
 aperture_um:v('ap')?parseFloat(v('ap')):null,aperture_basis:v('apb'),z_coordinates_um:v('zc'),note:v('note'),
 created:new Date().toISOString(),tool:'liga roi_editor 1.0'};
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));
 a.download=cur.id+'.json';a.click();};
if(FILES.length)open(0);
</script></body></html>
"""


def build_editor(archive: Path, out: Path, only=None) -> Path:
    files = []
    for p in list_images(archive):
        rel = p.relative_to(archive).as_posix()
        if only and rel not in only:
            continue
        src = os.path.relpath(p, out).replace(os.sep, "/")
        files.append({"file": rel, "id": file_id(rel), "src": src})
    html = HTML.replace("__FILES__", json.dumps(files, ensure_ascii=False))
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"  откройте в браузере: {out / 'index.html'}  ({len(files)} кадров); сохранённые JSON положите в "
          "config/interferometry_roi/")
    return out / "index.html"
