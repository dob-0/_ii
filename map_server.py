#!/usr/bin/env python3
"""_ii — web-based projection mapping editor + VJ control panel.
Run on the Debian machine:  python3 map_server.py
Open on any browser:        http://192.168.88.136:7777
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
from email.parser import BytesParser
from email.policy import default as email_default
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from architecture import MAPPINGS_DIR, CTRL_PATH, STATUS_PATH, discover_mode_names, save_json_atomic, load_json

PORT = 7777
BASE = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE, 'media')

_mpv_proc = None  # currently playing mpv process

# ── embedded single-file editor app ──────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>ii EDITOR</title>
<style>
:root{
  --bg:#080808;--bg1:#0f0f0f;--bg2:#141414;--bg3:#1c1c1c;
  --border:#1e1e1e;--border2:#2a2a2a;--border3:#444;
  --text:#d0d0d0;--text2:#bbb;--text3:#666;--text4:#555;
  --accent:#4488ff;--accent2:#ff4466;--accent3:#44ff88;
  --red:#aa3333;--green:#33aa33;
  --tab-active:#d0d0d0;--tab-inactive:#444;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:monospace;display:flex;flex-direction:column;height:100vh;overflow:hidden}

/* ── tab header ── */
#header{display:flex;align-items:center;background:var(--bg1);border-bottom:1px solid var(--border);padding:0 12px;height:36px;flex-shrink:0;gap:4px}
#header .logo{font-size:11px;color:var(--text4);letter-spacing:3px;margin-right:12px}
.tab-btn{background:none;border:1px solid transparent;color:var(--tab-inactive);padding:4px 14px;font-family:monospace;font-size:11px;letter-spacing:2px;cursor:pointer;border-radius:2px;transition:color .1s,border-color .1s}
.tab-btn:hover{color:var(--text2)}
.tab-btn.active{color:var(--tab-active);border-color:var(--border3)}

/* ── tab panes ── */
#tab-map,#tab-ctrl,#tab-zones,#tab-media,#tab-outputs,#tab-help{flex:1;display:none;overflow:hidden}
#tab-map.active{display:flex}
#tab-ctrl.active{display:flex;overflow-y:auto}
#tab-zones.active{display:flex;flex-direction:column;overflow:hidden}

/* ════════════════════════════════════════
   ZONES TAB
   ════════════════════════════════════════ */
#zones-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg1);border-bottom:1px solid var(--border);flex-shrink:0}
#zones-toolbar label{font-size:9px;letter-spacing:2px;color:var(--text4)}
#zones-toolbar select{width:160px;padding:3px 6px}
#zones-toolbar span{margin-left:auto;font-size:10px;color:var(--text4)}
#zones-body{flex:1;overflow-y:auto;padding:12px}
#zones-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.zone-card{background:var(--bg1);border:1px solid var(--border);border-left:3px solid #444;border-radius:3px;padding:10px 12px;display:flex;flex-direction:column;gap:7px}
.zone-id{font-size:12px;font-weight:bold;letter-spacing:2px;color:var(--text)}
.zone-card select{width:100%}
.zone-card .toggle-wrap{font-size:10px;color:var(--text3)}
.zone-empty{color:var(--text4);font-size:11px;padding:20px}

/* ════════════════════════════════════════
   MEDIA TAB
   ════════════════════════════════════════ */
#tab-media.active{display:flex;flex-direction:column;overflow:hidden}
#media-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg1);border-bottom:1px solid var(--border);flex-shrink:0;flex-wrap:wrap}
#media-toolbar label{font-size:9px;letter-spacing:2px;color:var(--text4)}
#drop-zone{flex:1;min-width:180px;border:1px dashed #333;border-radius:3px;padding:6px 12px;font-size:10px;color:#555;cursor:pointer;text-align:center;transition:border-color .2s,color .2s}
#drop-zone:hover,#drop-zone.drag{border-color:#4488ff;color:var(--text2)}
#drop-zone input{display:none}
#upload-progress{font-size:10px;color:var(--accent3);display:none}
#media-body{flex:1;overflow-y:auto;padding:12px}
#media-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.media-card{background:var(--bg1);border:1px solid var(--border);border-radius:3px;padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.media-name{font-size:11px;color:var(--text);word-break:break-all}
.media-meta{font-size:9px;color:var(--text4);letter-spacing:1px}
.media-btns{display:flex;gap:5px;margin-top:2px}
.media-btns button{flex:1;padding:5px 4px;font-size:9px;letter-spacing:1px}
#media-player-bar{background:#0a0a0a;border-top:1px solid var(--border);padding:6px 12px;font-size:10px;color:#555;display:flex;align-items:center;gap:12px;flex-shrink:0}
#now-playing{flex:1;color:var(--text3)}
.media-empty{color:var(--text4);font-size:11px;padding:20px}

/* ════════════════════════════════════════
   MAP TAB — original layout preserved
   ════════════════════════════════════════ */
#side{width:220px;background:var(--bg1);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:12px 10px;gap:6px;overflow-y:auto;flex-shrink:0}
#side h1{font-size:11px;color:var(--text4);letter-spacing:3px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.si{background:var(--bg2);border:1px solid #222;border-left-width:3px;border-radius:2px;padding:7px 8px;cursor:pointer}
.si:hover{background:#181818}.si.sel{background:var(--bg3);border-color:var(--border3)}
.sn{font-size:11px;font-weight:bold}.sm{font-size:10px;color:var(--text4);margin-top:2px}
#props{border-top:1px solid var(--border);padding-top:8px;display:none;flex-direction:column;gap:4px}
#props h2{font-size:10px;color:#444;letter-spacing:2px;margin-bottom:2px}
label{font-size:10px;color:var(--text3);display:block;margin-top:4px}
select,input{width:100%;background:#0a0a0a;border:1px solid var(--border2);color:var(--text2);padding:4px 6px;font-family:monospace;font-size:11px;border-radius:2px;margin-top:2px}
button{background:var(--bg2);border:1px solid var(--border2);color:var(--text2);padding:5px 8px;font-family:monospace;font-size:10px;cursor:pointer;border-radius:2px;width:100%;margin-top:3px}
button:hover{background:var(--bg3);border-color:var(--border3)}
.btn-del{border-color:#3a1515;color:var(--red)}.btn-ok{border-color:#153a15;color:var(--green)}
#wrap{flex:1;display:flex;align-items:center;justify-content:center;background:#040404;position:relative}
canvas{cursor:crosshair;image-rendering:pixelated}
#bar{position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;border-top:1px solid #1a1a1a;padding:4px 12px;font-size:10px;color:#444;display:flex;gap:16px}

/* ════════════════════════════════════════
   CTRL TAB
   ════════════════════════════════════════ */
#tab-ctrl{flex-direction:column;background:var(--bg);padding:0}
#ctrl-inner{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;padding:12px;align-content:start}
#ctrl-status-bar{background:#0a0a0a;border-top:1px solid var(--border);padding:5px 14px;font-size:10px;color:#555;display:flex;gap:20px;flex-shrink:0;order:999}

.ctrl-section{background:var(--bg1);border:1px solid var(--border);border-radius:3px;padding:10px 12px}
.ctrl-section h3{font-size:9px;letter-spacing:3px;color:var(--text4);margin-bottom:10px;border-bottom:1px solid var(--border);padding-bottom:5px}

/* mode grid */
.mode-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:5px}
.mode-grid.sm{grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:3px}
.mbtn{background:var(--bg2);border:1px solid #222;color:#888;padding:6px 4px;font-family:monospace;font-size:9px;cursor:pointer;border-radius:2px;text-align:center;line-height:1.3;transition:background .1s,color .1s,border-color .1s}
.mbtn:hover{background:var(--bg3);color:var(--text2)}
.mbtn.active{background:#1a2a1a;border-color:#44ff88;color:#44ff88}
.mbtn .midx{font-size:8px;color:#444;display:block}
.mbtn.sm{padding:4px 2px;font-size:8px}

/* layer b row */
.layer-b-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.toggle-wrap{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--text3)}
.toggle{appearance:none;-webkit-appearance:none;width:34px;height:18px;border-radius:9px;background:#1a1a1a;border:1px solid #333;cursor:pointer;position:relative;transition:background .2s}
.toggle:checked{background:#1a3a1a;border-color:#44ff88}
.toggle::after{content:'';position:absolute;width:12px;height:12px;border-radius:50%;background:#555;top:2px;left:2px;transition:left .2s,background .2s}
.toggle:checked::after{left:18px;background:#44ff88}

/* sliders */
.slider-row{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.slider-row label{width:52px;font-size:9px;letter-spacing:1px;color:var(--text3);flex-shrink:0}
.slider-row input[type=range]{flex:1;height:3px;accent-color:var(--accent);cursor:pointer}
.slider-row .sval{width:36px;font-size:10px;color:var(--text2);text-align:right;flex-shrink:0}

/* palette */
.pal-grid{display:flex;gap:6px;flex-wrap:wrap}
.pal-btn{width:54px;height:38px;border:2px solid #222;border-radius:3px;cursor:pointer;font-family:monospace;font-size:8px;letter-spacing:1px;display:flex;align-items:flex-end;justify-content:center;padding-bottom:4px;transition:border-color .1s,transform .1s;color:#000}
.pal-btn:hover{transform:scale(1.05)}
.pal-btn.active{border-color:#fff;color:#fff;text-shadow:0 0 4px #000}

/* bpm */
.bpm-row{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.bpm-display{font-size:36px;font-weight:bold;color:var(--text);letter-spacing:-1px;min-width:80px}
.bpm-sub{display:flex;flex-direction:column;gap:4px}
.bpm-adj{display:flex;gap:4px}
.cbtn{background:var(--bg2);border:1px solid #333;color:var(--text2);padding:6px 10px;font-family:monospace;font-size:10px;cursor:pointer;border-radius:2px;transition:background .1s}
.cbtn:hover{background:var(--bg3);border-color:var(--border3)}
.cbtn.active{background:#1a2a1a;border-color:#44ff88;color:#44ff88}
#tap-btn{padding:10px 18px;font-size:12px;letter-spacing:2px;border-color:#444;color:var(--text)}
#tap-btn:hover{background:#1a1a2a;border-color:#4488ff}
#tap-btn:active{background:#0a0a1a}

/* flash */
.flash-row{display:flex;gap:6px}
.flash-row input{flex:1;background:#0a0a0a;border:1px solid var(--border2);color:var(--text2);padding:6px 8px;font-family:monospace;font-size:11px;border-radius:2px}
.flash-row button{width:auto;padding:6px 14px;letter-spacing:1px}

/* blackout */
#blackout-btn{width:100%;padding:18px;font-size:14px;letter-spacing:4px;border:2px solid #3a1515;color:#aa3333;background:var(--bg2);border-radius:3px;cursor:pointer;font-family:monospace;transition:background .1s,border-color .1s,color .1s}
#blackout-btn:hover{background:#1a0808;border-color:#5a2525}
#blackout-btn.on{background:#2a0808;border-color:#ff3333;color:#ff5555}

/* alpha slider full row */
.alpha-row{margin-top:8px}
.alpha-row label{font-size:9px;letter-spacing:1px;color:var(--text3);display:block;margin-bottom:4px}
.alpha-row input[type=range]{width:100%;accent-color:var(--accent2)}

/* ── OUTPUTS TAB ─────────────────────────────────────────────────────────── */
#tab-outputs{flex-direction:column;overflow:hidden;background:var(--bg)}
#tab-outputs.active{display:flex}
#out-strip{display:flex;align-items:center;gap:10px;padding:7px 14px;background:var(--bg1);border-bottom:1px solid var(--border);flex-shrink:0;font-size:10px;letter-spacing:1px}
#out-x-badge{color:#555}
#out-x-badge.ok{color:var(--accent3)}
#out-x-badge.warn{color:var(--accent2)}
#out-strip-status{margin-left:auto;color:#555;font-size:10px}
#out-main{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px;max-width:820px}
#out-assign-area{display:grid;grid-template-columns:1fr 1fr;gap:14px;background:var(--bg1);border:1px solid var(--border);border-radius:4px;padding:14px 16px}
.out-role-label{font-size:9px;letter-spacing:2px;color:var(--text4);margin-bottom:8px}
.out-disp-btns{display:flex;flex-direction:column;gap:5px}
.out-disp-btn{background:#111;border:1px solid #222;border-radius:3px;padding:9px 12px;cursor:pointer;font-family:monospace;font-size:10px;text-align:left;transition:border-color .1s;display:flex;flex-direction:column;gap:2px}
.out-disp-btn:hover{border-color:#444}
.out-disp-btn.active{border-color:var(--accent3);background:#0a1a0a}
.out-disp-btn .dname{font-size:11px;color:var(--text)}
.out-disp-btn.active .dname{color:var(--accent3)}
.out-disp-btn .dres{color:#555;font-size:9px}
#out-map-area{background:var(--bg1);border:1px solid var(--border);border-radius:4px;padding:14px 16px}
#out-map-btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}
.out-map-btn{background:#111;border:1px solid #222;border-radius:3px;padding:8px 12px;cursor:pointer;font-family:monospace;font-size:10px;text-align:left;transition:border-color .1s}
.out-map-btn:hover{border-color:#444}
.out-map-btn.active{border-color:var(--accent3);color:var(--accent3);background:#0a1a0a}
.msurfs{font-size:9px;color:#555;margin-top:2px}
.out-map-btn.active .msurfs{color:#3a6}
#out-action-area{display:flex;align-items:center;gap:14px;padding-top:2px}
#out-apply-btn{padding:11px 28px;font-size:11px;letter-spacing:2px;border:1px solid #153a15;color:var(--green);background:var(--bg1);border-radius:3px;cursor:pointer;font-family:monospace;flex-shrink:0}
#out-apply-btn:hover{background:#0a1a0a;border-color:#2a5a2a}
#out-layout-status{font-size:10px;color:#555}
.out-warn{color:var(--accent2)!important}

/* ── HELP TAB ────────────────────────────────────────────────────────────── */
#tab-help{flex-direction:column;overflow-y:auto;background:var(--bg);padding:16px}
#tab-help.active{display:flex}
#help-body{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;max-width:1100px;width:100%;margin:0 auto}
.help-section{background:var(--bg1);border:1px solid var(--border);border-radius:4px;padding:14px 16px}
.help-section h3{font-size:10px;letter-spacing:2px;color:var(--text2);margin-bottom:10px}
.help-section p{font-size:11px;line-height:1.5;color:var(--text3);margin-bottom:8px}
.help-list{display:flex;flex-direction:column;gap:6px}
.help-row{display:flex;justify-content:space-between;gap:12px;border-bottom:1px solid #171717;padding-bottom:5px;font-size:11px}
.help-row span:first-child{color:var(--text4)}
.help-row span:last-child{color:var(--text);text-align:right}
.help-code{background:#090909;border:1px solid var(--border);border-radius:3px;color:var(--accent3);font-size:11px;line-height:1.5;padding:9px 10px;white-space:pre-wrap;word-break:break-word}
.help-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px;margin-top:8px}
.help-actions button{margin-top:0}
.help-ok{color:var(--accent3)}
.help-warn{color:var(--accent2)}

</style></head>
<body>

<!-- ── tab header ──────────────────────────────────────── -->
<div id="header">
  <span class="logo">ii</span>
  <button class="tab-btn active" id="btn-map"   onclick="switchTab('map')">[ MAP ]</button>
  <button class="tab-btn"        id="btn-zones" onclick="switchTab('zones')">[ ZONES ]</button>
  <button class="tab-btn"        id="btn-ctrl"  onclick="switchTab('ctrl')">[ CTRL ]</button>
  <button class="tab-btn"        id="btn-media" onclick="switchTab('media')">[ MEDIA ]</button>
  <button class="tab-btn"        id="btn-outputs" onclick="switchTab('outputs')">[ OUTPUTS ]</button>
  <button class="tab-btn"        id="btn-help" onclick="switchTab('help')">[ HELP ]</button>
</div>

<!-- ════════════════════════════════════════
     MAP TAB
     ════════════════════════════════════════ -->
<div id="tab-map" class="active">
  <div id="side">
    <h1>MAP EDITOR</h1>
    <button id="mapmode-btn" onclick="toggleMapMode()" style="letter-spacing:2px;margin-bottom:6px">[ MAP MODE OFF ]</button>
    <div id="slist"></div>
    <button class="btn-ok" onclick="addSurf()">+ NEW SURFACE</button>
    <div id="props">
      <h2>SURFACE</h2>
      <label>ID</label><input id="p-id" oninput="uprop('id',this.value)">
      <label>MODE (null = follow active)</label>
      <select id="p-mode" onchange="uprop('mode',this.value==='null'?null:+this.value)">
        <option value="null">∅  null — follow active</option>
      </select>
      <label>VIDEO FILE (overrides mode if set)</label>
      <select id="p-video" onchange="uprop('video',this.value||null)">
        <option value="">none — use mode</option>
      </select>
      <label>PHASE  (seconds time-offset)</label>
      <input id="p-phase" type="number" step="0.1" oninput="uprop('phase',+this.value)">
      <label>ENABLED</label>
      <select id="p-en" onchange="uprop('enabled',this.value==='true')">
        <option value="true">ON</option><option value="false">OFF</option>
      </select>
      <button onclick="resetCorn()">RESET CORNERS</button>
      <button class="btn-del" onclick="delSurf()">DELETE SURFACE</button>
    </div>
    <div style="margin-top:auto;border-top:1px solid #1e1e1e;padding-top:8px">
      <label>MAPPING FILE</label>
      <select id="fileSel" onchange="switchFile(this.value)"></select>
      <button class="btn-ok" onclick="save()">SAVE  ⌘S</button>
      <button onclick="load()">RELOAD</button>
    </div>
  </div>
  <div id="wrap"><canvas id="c"></canvas></div>
  <div id="bar">
    <span id="st">ready</span>
    <span>drag corners to warp · click surface to select · N new · Del delete</span>
    <span id="coords"></span>
  </div>
</div>

<!-- ════════════════════════════════════════
     MEDIA TAB
     ════════════════════════════════════════ -->
<div id="tab-media">
  <div id="media-toolbar">
    <label>MEDIA</label>
    <div id="drop-zone" onclick="document.getElementById('file-input').click()"
         ondragover="event.preventDefault();this.classList.add('drag')"
         ondragleave="this.classList.remove('drag')"
         ondrop="event.preventDefault();this.classList.remove('drag');uploadFiles(event.dataTransfer.files)">
      <input type="file" id="file-input" multiple accept="video/*,image/*"
             onchange="uploadFiles(this.files)">
      DROP FILES HERE  or  CLICK TO BROWSE
    </div>
    <span id="upload-progress"></span>
    <button class="cbtn" onclick="mediaLoad()" style="width:auto;padding:3px 10px;margin-top:0">REFRESH</button>
  </div>
  <div id="media-body"><div id="media-grid"></div></div>
  <div id="media-player-bar">
    <span id="now-playing">no video playing</span>
    <button class="cbtn" id="stop-btn" onclick="mediaStop()" style="width:auto;padding:4px 14px;display:none">■ STOP</button>
  </div>
</div>

<!-- ════════════════════════════════════════
     ZONES TAB
     ════════════════════════════════════════ -->
<div id="tab-zones">
  <div id="zones-toolbar">
    <label>FILE</label>
    <select id="zones-file-sel" onchange="zonesLoadFile(this.value)"></select>
    <button class="cbtn" onclick="zonesLoad()" style="width:auto;padding:3px 10px;margin-top:0">REFRESH</button>
    <span id="zones-status">●</span>
  </div>
  <div id="zones-body"><div id="zones-grid"></div></div>
</div>

<!-- ════════════════════════════════════════
     CTRL TAB
     ════════════════════════════════════════ -->
<div id="tab-ctrl">
  <div id="ctrl-inner">

    <!-- MODES -->
    <div class="ctrl-section" style="grid-column:1/-1">
      <h3>MODES</h3>
      <div class="mode-grid" id="mode-grid"></div>
    </div>

    <!-- LAYER B -->
    <div class="ctrl-section">
      <h3>LAYER B</h3>
      <div class="layer-b-row">
        <label class="toggle-wrap">
          <input type="checkbox" class="toggle" id="layer-b-toggle" onchange="ctrlSet('layer_b_enabled',this.checked)">
          ENABLED
        </label>
      </div>
      <div style="font-size:9px;letter-spacing:1px;color:var(--text3);margin-bottom:6px">MODE B</div>
      <div class="mode-grid sm" id="mode-b-grid"></div>
      <div class="alpha-row">
        <label>ALPHA  <span id="layer-b-alpha-val">1.00</span></label>
        <input type="range" id="layer-b-alpha" min="0" max="1" step="0.01" value="1"
               oninput="document.getElementById('layer-b-alpha-val').textContent=parseFloat(this.value).toFixed(2);ctrlSet('layer_b_alpha',parseFloat(this.value))">
      </div>
    </div>

    <!-- PALETTE -->
    <div class="ctrl-section">
      <h3>PALETTE</h3>
      <div class="pal-grid" id="pal-grid"></div>
    </div>

    <!-- BPM -->
    <div class="ctrl-section">
      <h3>BPM</h3>
      <div class="bpm-row">
        <div class="bpm-display" id="bpm-display">140</div>
        <div class="bpm-sub">
          <div class="bpm-adj">
            <button class="cbtn" onclick="adjustBpm(-5)">−5</button>
            <button class="cbtn" onclick="adjustBpm(+5)">+5</button>
          </div>
          <button class="cbtn" id="sync-btn" onclick="toggleSync()">SYNC</button>
        </div>
        <button class="cbtn" id="tap-btn" onclick="tapTempo()">TAP</button>
      </div>
    </div>

    <!-- EFFECTS -->
    <div class="ctrl-section">
      <h3>EFFECTS</h3>
      <div class="slider-row">
        <label>DIM</label>
        <input type="range" id="sl-master_dim" min="0" max="1" step="0.01" value="1"
               oninput="sliderChange('master_dim',this.value,'sl-master_dim-val')">
        <span class="sval" id="sl-master_dim-val">1.00</span>
      </div>
      <div class="slider-row">
        <label>GLITCH</label>
        <input type="range" id="sl-glitch_intensity" min="0.05" max="1" step="0.01" value="0.4"
               oninput="sliderChange('glitch_intensity',this.value,'sl-glitch_intensity-val')">
        <span class="sval" id="sl-glitch_intensity-val">0.40</span>
      </div>
      <div class="slider-row">
        <label>RAIN</label>
        <input type="range" id="sl-rain_density" min="0.1" max="1" step="0.01" value="0.7"
               oninput="sliderChange('rain_density',this.value,'sl-rain_density-val')">
        <span class="sval" id="sl-rain_density-val">0.70</span>
      </div>
      <div class="slider-row">
        <label>WAVE</label>
        <input type="range" id="sl-wave_amplitude" min="0.1" max="0.5" step="0.01" value="0.35"
               oninput="sliderChange('wave_amplitude',this.value,'sl-wave_amplitude-val')">
        <span class="sval" id="sl-wave_amplitude-val">0.35</span>
      </div>
      <div class="slider-row">
        <label>SPEED</label>
        <input type="range" id="sl-frame_delay" min="0.01" max="0.15" step="0.005" value="0.05"
               oninput="sliderChange('frame_delay',this.value,'sl-frame_delay-val')">
        <span class="sval" id="sl-frame_delay-val">0.050</span>
      </div>
    </div>

    <!-- FLASH -->
    <div class="ctrl-section">
      <h3>FLASH TEXT</h3>
      <div class="flash-row">
        <input type="text" id="flash-input" placeholder="MOCT" value="MOCT"
               onkeydown="if(event.key==='Enter')triggerFlash()">
        <button class="cbtn" onclick="triggerFlash()">TRIGGER</button>
      </div>
    </div>

    <!-- BLACKOUT -->
    <div class="ctrl-section">
      <h3>BLACKOUT</h3>
      <button id="blackout-btn" onclick="toggleBlackout()">BLACKOUT</button>
    </div>

  </div><!-- /ctrl-inner -->

  <!-- status bar always at bottom of ctrl tab -->
  <div id="ctrl-status-bar">
    <span id="cs-fps">fps —</span>
    <span id="cs-uptime">uptime —</span>
    <span id="cs-mode">mode —</span>
    <span id="cs-poll" style="margin-left:auto;color:#333">●</span>
  </div>
</div><!-- /tab-ctrl -->

<script>
// ══════════════════════════════════════════════════════════════
//  SHARED STATE
// ══════════════════════════════════════════════════════════════
const OW=1366,OH=768;
let SCALE=1,surfaces=[],sel=-1,drag=null,MODES=[],curFile='fb_map.json';
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
const COLS=['#4488ff','#ff4466','#44ff88','#ffaa22','#cc44ff','#22ccff','#ffcc22','#ff6644'];

// ══════════════════════════════════════════════════════════════
//  TAB SWITCHER
// ══════════════════════════════════════════════════════════════
let activeTab='map';
function switchTab(t){
  if(activeTab==='map'&&t!=='map'){
    clearMapCursor();
    if(mapModeActive){
      mapModeActive=false;
      const btn=document.getElementById('mapmode-btn');
      if(btn){btn.textContent='[ MAP MODE OFF ]';btn.style.borderColor='';btn.style.color='';}
      fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({map_mode:false})}).catch(()=>{});
    }
  }
  activeTab=t;
  ['map','zones','ctrl','media','outputs','help'].forEach(n=>{
    document.getElementById('tab-'+n).classList.toggle('active',t===n);
    document.getElementById('btn-'+n).classList.toggle('active',t===n);
  });
  if(t==='map'){resize();}
  if(t==='ctrl'){startCtrlPoll();}
  if(t==='zones'){fetchMedia().then(()=>zonesInit());}
  if(t==='media'){mediaLoad();mediaStatusPoll();}
  if(t==='outputs'){outputsLoad();}
  if(t==='help'){helpLoad();}
}

// ══════════════════════════════════════════════════════════════
//  MAP TAB — original logic (unchanged)
// ══════════════════════════════════════════════════════════════
let MEDIA_FILES=[];
async function fetchMedia(){
  try{
    const r=await fetch('/api/media');
    MEDIA_FILES=await r.json();
    _fillVideoSelects();
  }catch(e){}
}
function _isVideoFile(name){return/\.(mp4|mkv|avi|mov|webm|ts|m4v)$/i.test(name);}
function _fillVideoSelects(){
  const videoOpts='<option value="">none — use mode</option>'+
    MEDIA_FILES.filter(f=>_isVideoFile(f.name))
      .map(f=>`<option value="${f.name}">▶ ${f.name}</option>`).join('');
  const el=document.getElementById('p-video');
  if(el){const cur=el.value;el.innerHTML=videoOpts;el.value=cur;}
}

window.onload=()=>{resize();fetchMedia();fetchModes().then(()=>fetchFiles().then(()=>load()))};
window.onresize=()=>{if(activeTab==='map')resize()};
document.addEventListener('keydown',e=>{
  if(activeTab!=='map')return;
  if(e.key==='n'||e.key==='N'){addSurf();return}
  if((e.key==='Delete'||e.key==='Backspace')&&sel>=0&&document.activeElement===document.body){delSurf();return}
  if((e.metaKey||e.ctrlKey)&&e.key==='s'){e.preventDefault();save()}
});

function resize(){
  const w=document.getElementById('wrap');
  SCALE=Math.min((w.clientWidth-40)/OW,(w.clientHeight-60)/OH);
  canvas.width=Math.round(OW*SCALE);canvas.height=Math.round(OH*SCALE);
  draw();
}

async function fetchModes(){
  try{
    const r=await fetch('/api/modes');
    MODES=await r.json();
    buildModesSel();
    buildModeGrids();
  }catch(e){}
}
function buildModesSel(){
  const s=document.getElementById('p-mode');
  const cur=s.value;
  s.innerHTML='<option value="null">∅  null — follow active</option>';
  MODES.forEach((n,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i}  ${n}`;s.appendChild(o)});
  s.value=cur;
}
async function fetchFiles(){
  try{
    const r=await fetch('/api/list');const files=await r.json();
    const sel=document.getElementById('fileSel');sel.innerHTML='';
    files.forEach(f=>{const o=document.createElement('option');o.value=f;o.textContent=f;if(f===curFile)o.selected=true;sel.appendChild(o)});
    if(!files.includes(curFile)&&files.length)curFile=files[0];
  }catch(e){}
}
function switchFile(f){curFile=f;load()}

async function load(){
  try{
    const r=await fetch(`/api/mapping?file=${curFile}`);
    const d=await r.json();surfaces=d.surfaces||[];sel=-1;renderSide();draw();st('loaded '+curFile);
  }catch(e){st('load error: '+e)}
}
async function save(){
  try{
    await fetch(`/api/save?file=${curFile}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:curFile.replace('.json',''),surfaces})});
    st('saved ✓');
  }catch(e){st('error: '+e)}
}

function addSurf(){
  const i=surfaces.length,cx=0.08+(i%5)*0.18,cy=0.15+Math.floor(i/5)*0.35,w=0.15,h=0.3;
  surfaces.push({id:`SURF-${i+1}`,corners:[[cx,cy],[cx+w,cy],[cx+w,cy+h],[cx,cy+h]],mode:null,phase:0,enabled:true});
  sel=surfaces.length-1;renderSide();draw();
}
function delSurf(){if(sel<0)return;surfaces.splice(sel,1);sel=Math.min(sel,surfaces.length-1);renderSide();draw()}
function resetCorn(){
  if(sel<0)return;
  const cx=0.1,cy=0.2,w=0.2,h=0.4;
  surfaces[sel].corners=[[cx,cy],[cx+w,cy],[cx+w,cy+h],[cx,cy+h]];draw();
}
let mapModeActive=false;
function toggleMapMode(){
  mapModeActive=!mapModeActive;
  const btn=document.getElementById('mapmode-btn');
  btn.textContent=mapModeActive?'[ MAP MODE ON ]':'[ MAP MODE OFF ]';
  btn.style.borderColor=mapModeActive?'#44ff88':'';
  btn.style.color=mapModeActive?'#44ff88':'';
  const patch={map_mode:mapModeActive};
  if(mapModeActive)patch.map_selected=sel;
  fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)}).catch(()=>{});
}
function _syncMapSelected(){
  if(mapModeActive)fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({map_selected:sel})}).catch(()=>{});
}

function selSurf(i){sel=i;renderSide();draw();_syncMapSelected()}
function uprop(k,v){if(sel<0)return;surfaces[sel][k]=v;renderSide();draw()}

function renderSide(){
  document.getElementById('slist').innerHTML='';
  surfaces.forEach((s,i)=>{
    const d=document.createElement('div');d.className='si'+(i===sel?' sel':'');
    d.style.borderLeftColor=COLS[i%COLS.length];
    const ml=s.mode===null?'∅ active':(MODES[s.mode]||`mode ${s.mode}`);
    d.innerHTML=`<div class="sn">${s.id||'SURF'}</div><div class="sm">${ml}  φ=${s.phase||0}  ${s.enabled===false?'OFF':''}</div>`;
    d.onclick=()=>selSurf(i);document.getElementById('slist').appendChild(d);
  });
  const p=document.getElementById('props');
  if(sel>=0){
    p.style.display='flex';const s=surfaces[sel];
    document.getElementById('p-id').value=s.id||'';
    document.getElementById('p-mode').value=s.mode===null?'null':s.mode;
    document.getElementById('p-video').value=s.video||'';
    document.getElementById('p-phase').value=s.phase||0;
    document.getElementById('p-en').value=s.enabled===false?'false':'true';
  }else p.style.display='none';
}

// ── canvas ────────────────────────────────────────────────────────────────────
const s2c=([nx,ny])=>[nx*canvas.width,ny*canvas.height];
const c2s=(cx,cy)=>[cx/canvas.width,cy/canvas.height];

function draw(){
  ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle='#0c0c0c';ctx.lineWidth=0.5;
  [.1,.2,.3,.4,.5,.6,.7,.8,.9].forEach(t=>{
    ctx.beginPath();ctx.moveTo(t*canvas.width,0);ctx.lineTo(t*canvas.width,canvas.height);ctx.stroke();
    ctx.beginPath();ctx.moveTo(0,t*canvas.height);ctx.lineTo(canvas.width,t*canvas.height);ctx.stroke();
  });
  ctx.strokeStyle='#181818';ctx.lineWidth=1;
  [1/3,2/3].forEach(t=>{
    ctx.beginPath();ctx.moveTo(t*canvas.width,0);ctx.lineTo(t*canvas.width,canvas.height);ctx.stroke();
    ctx.beginPath();ctx.moveTo(0,t*canvas.height);ctx.lineTo(canvas.width,t*canvas.height);ctx.stroke();
  });

  surfaces.forEach((s,i)=>{
    if(!s.corners||s.corners.length<4)return;
    const pts=s.corners.map(s2c);
    const col=COLS[i%COLS.length];
    const isSel=i===sel;
    const off=s.enabled===false;
    ctx.beginPath();ctx.moveTo(...pts[0]);pts.slice(1).forEach(p=>ctx.lineTo(...p));ctx.closePath();
    ctx.fillStyle=col+(isSel?'18':'0c');ctx.fill();
    ctx.strokeStyle=col+(off?'33':isSel?'dd':'66');ctx.lineWidth=isSel?1.5:1;ctx.stroke();
    const cx=pts.reduce((a,p)=>a+p[0],0)/4,cy=pts.reduce((a,p)=>a+p[1],0)/4;
    ctx.fillStyle=col+(off?'44':isSel?'ff':'99');ctx.font=`${isSel?12:10}px monospace`;ctx.textAlign='center';
    ctx.fillText(s.id||`S${i+1}`,cx,cy);
    const ml=s.mode===null?'∅':(MODES[s.mode]||`${s.mode}`);
    ctx.font='8px monospace';ctx.fillStyle='#33333399';ctx.fillText(ml,cx,cy+12);
    pts.forEach(([px,py],ci)=>{
      ctx.beginPath();ctx.arc(px,py,isSel?7:4,0,Math.PI*2);
      ctx.fillStyle=isSel?col:col+'77';ctx.fill();
      if(isSel){ctx.strokeStyle='#ffffff33';ctx.lineWidth=1;ctx.stroke();
        ctx.fillStyle='#fff';ctx.font='7px monospace';ctx.textAlign='center';ctx.fillText(ci+1,px,py+2.5)}
    });
  });
  ctx.strokeStyle='#ffffff06';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(canvas.width/2,0);ctx.lineTo(canvas.width/2,canvas.height);ctx.stroke();
  ctx.beginPath();ctx.moveTo(0,canvas.height/2);ctx.lineTo(canvas.width,canvas.height/2);ctx.stroke();
}

// ── mouse ─────────────────────────────────────────────────────────────────────
function hitCorner(mx,my){
  const R=10;
  for(let i=surfaces.length-1;i>=0;i--){
    const s=surfaces[i];if(!s.corners)continue;
    for(let c=0;c<4;c++){const[px,py]=s2c(s.corners[c]);if(Math.hypot(mx-px,my-py)<R)return{s:i,c}}
  }return null;
}
function hitSurf(mx,my){
  const[nx,ny]=c2s(mx,my);
  for(let i=surfaces.length-1;i>=0;i--)if(pip([nx,ny],surfaces[i].corners))return i;
  return-1;
}
function pip([px,py],corners){
  let inside=false,n=corners.length,[jx,jy]=corners[n-1];
  for(const[ix,iy]of corners){if(((iy>py)!==(jy>py))&&px<(jx-ix)*(py-iy)/(jy-iy)+ix)inside=!inside;[jx,jy]=[ix,iy]}
  return inside;
}

canvas.addEventListener('mousedown',e=>{
  const r=canvas.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const h=hitCorner(mx,my);
  if(h){drag=h;if(h.s!==sel){sel=h.s;renderSide()};return}
  const s=hitSurf(mx,my);
  if(s>=0){sel=s;renderSide();draw()}else{sel=-1;renderSide();draw()}
});
let _cursorThrottle=null;
function sendMapCursor(nx,ny){
  if(_cursorThrottle)return;
  _cursorThrottle=setTimeout(()=>{_cursorThrottle=null},50);
  fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({map_cursor_x:nx,map_cursor_y:ny})}).catch(()=>{});
}
function clearMapCursor(){
  fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({map_cursor_x:null,map_cursor_y:null})}).catch(()=>{});
}

canvas.addEventListener('mousemove',e=>{
  const r=canvas.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const[nx,ny]=c2s(mx,my);
  document.getElementById('coords').textContent=`${(nx*OW).toFixed(0)}, ${(ny*OH).toFixed(0)} px  (${nx.toFixed(3)}, ${ny.toFixed(3)})`;
  sendMapCursor(Math.max(0,Math.min(1,nx)),Math.max(0,Math.min(1,ny)));
  if(!drag)return;
  surfaces[drag.s].corners[drag.c]=[Math.max(0,Math.min(1,nx)),Math.max(0,Math.min(1,ny))];
  draw();
});
canvas.addEventListener('mouseup',()=>{if(drag){save();drag=null}});
canvas.addEventListener('mouseleave',()=>{drag=null;clearMapCursor()});

function st(msg){document.getElementById('st').textContent=msg}

// ══════════════════════════════════════════════════════════════
//  CTRL TAB
// ══════════════════════════════════════════════════════════════

// palette definitions: [label, css-bg-color, text-color]
const PALETTES=[
  ['STEEL','#2244aa','#8ab4ff'],
  ['ACID', '#00aaaa','#00ffff'],
  ['VOID', '#444444','#ffffff'],
  ['NEON', '#aa0088','#ff44ff'],
  ['ULTRA','#aaaa00','#ffff00'],
  ['DEEP', '#440088','#aa44ff'],
  ['BLOOD','#880000','#ff2222'],
  ['EMBER','#aa2200','#ff6622'],
];

let ctrlState={};   // last known control.json
let ctrlPollTimer=null;
let ctrlPollActive=false;
let flashTimer=null;

// tap tempo state
let tapTimes=[];

function buildModeGrids(){
  _buildGrid('mode-grid','mode',false);
  _buildGrid('mode-b-grid','mode_b',true);
}

function _buildGrid(containerId,field,small){
  const g=document.getElementById(containerId);
  g.innerHTML='';
  MODES.forEach((name,i)=>{
    const b=document.createElement('button');
    b.className='mbtn'+(small?' sm':'');
    b.id=`${containerId}-${i}`;
    b.innerHTML=`<span class="midx">${i}</span>${name}`;
    b.onclick=()=>ctrlSet(field,i);
    g.appendChild(b);
  });
}

function buildPaletteGrid(){
  const g=document.getElementById('pal-grid');
  g.innerHTML='';
  PALETTES.forEach(([label,bg,fg],i)=>{
    const b=document.createElement('button');
    b.className='pal-btn';
    b.id=`pal-${i}`;
    b.style.background=bg;
    b.style.color=fg;
    b.style.borderColor=bg;
    b.textContent=label;
    b.onclick=()=>ctrlSet('palette',i);
    g.appendChild(b);
  });
}

// Send a partial update to control.json
async function ctrlSet(key,value){
  const patch={};patch[key]=value;
  try{
    await fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
  }catch(e){console.warn('ctrlSet failed',e)}
}

// Apply full ctrl state to UI (called after each poll)
function applyCtrlToUI(c){
  ctrlState=c;

  // modes
  const modeVal=c.mode??0;
  const modeBVal=c.mode_b??0;
  MODES.forEach((_,i)=>{
    const b=document.getElementById(`mode-grid-${i}`);
    if(b)b.classList.toggle('active',i===modeVal);
    const bb=document.getElementById(`mode-b-grid-${i}`);
    if(bb)bb.classList.toggle('active',i===modeBVal);
  });

  // layer b
  const tog=document.getElementById('layer-b-toggle');
  if(tog&&!tog._touched)tog.checked=!!(c.layer_b_enabled);
  const alphaEl=document.getElementById('layer-b-alpha');
  if(alphaEl&&!alphaEl._touched){
    alphaEl.value=c.layer_b_alpha??1;
    document.getElementById('layer-b-alpha-val').textContent=parseFloat(alphaEl.value).toFixed(2);
  }

  // palette
  const palVal=c.palette??0;
  PALETTES.forEach((_,i)=>{
    const b=document.getElementById(`pal-${i}`);
    if(b)b.classList.toggle('active',i===palVal);
  });

  // bpm
  const bpmVal=c.bpm??140;
  document.getElementById('bpm-display').textContent=bpmVal;
  const syncBtn=document.getElementById('sync-btn');
  if(syncBtn)syncBtn.classList.toggle('active',!!(c.bpm_sync));

  // sliders (only update if user not currently dragging — checked via _touched flag)
  const sliders={
    master_dim:      [0,1,    (v)=>v.toFixed(2)],
    glitch_intensity:[0.05,1, (v)=>v.toFixed(2)],
    rain_density:    [0.1,1,  (v)=>v.toFixed(2)],
    wave_amplitude:  [0.1,0.5,(v)=>v.toFixed(2)],
    frame_delay:     [0.01,0.15,(v)=>v.toFixed(3)],
  };
  Object.entries(sliders).forEach(([key,[,, fmt]])=>{
    const el=document.getElementById(`sl-${key}`);
    const valEl=document.getElementById(`sl-${key}-val`);
    if(el&&!el._touched&&c[key]!=null){
      el.value=c[key];
      if(valEl)valEl.textContent=fmt(parseFloat(c[key]));
    }
  });

  // blackout
  const bb=document.getElementById('blackout-btn');
  if(bb)bb.classList.toggle('on',!!(c.blackout));
}

function sliderChange(key,value,valId){
  const fmt=key==='frame_delay'?3:2;
  document.getElementById(valId).textContent=parseFloat(value).toFixed(fmt);
  ctrlSet(key,parseFloat(value));
  // mark as touched so poll doesn't overwrite while dragging
  const el=document.getElementById(`sl-${key}`);
  if(el){el._touched=true;clearTimeout(el._touchTimer);el._touchTimer=setTimeout(()=>{el._touched=false},2000);}
}

function adjustBpm(delta){
  const cur=parseInt(document.getElementById('bpm-display').textContent)||140;
  const next=Math.max(40,Math.min(240,cur+delta));
  ctrlSet('bpm',next);
}

function toggleSync(){
  ctrlSet('bpm_sync',!(ctrlState.bpm_sync));
}

function tapTempo(){
  const now=performance.now();
  tapTimes.push(now);
  if(tapTimes.length>4)tapTimes=tapTimes.slice(-4);
  if(tapTimes.length>=2){
    const intervals=[];
    for(let i=1;i<tapTimes.length;i++)intervals.push(tapTimes[i]-tapTimes[i-1]);
    const avg=intervals.reduce((a,b)=>a+b,0)/intervals.length;
    const bpm=Math.round(60000/avg);
    const clamped=Math.max(40,Math.min(240,bpm));
    document.getElementById('bpm-display').textContent=clamped;
    ctrlSet('bpm',clamped);
  }
  // visual flash on tap button
  const btn=document.getElementById('tap-btn');
  btn.style.background='#1a1a3a';
  setTimeout(()=>{btn.style.background=''},120);
}

function triggerFlash(){
  const txt=document.getElementById('flash-input').value||'MOCT';
  ctrlSet('flash_text',txt);
  ctrlSet('flash_active',true);
  clearTimeout(flashTimer);
  flashTimer=setTimeout(()=>ctrlSet('flash_active',false),3000);
}

function toggleBlackout(){
  ctrlSet('blackout',!(ctrlState.blackout));
}

// ── polling ───────────────────────────────────────────────────
function startCtrlPoll(){
  if(ctrlPollActive)return;
  ctrlPollActive=true;
  pollCtrl();
}

async function pollCtrl(){
  if(!ctrlPollActive)return;
  try{
    const [statusRes,ctrlRes]=await Promise.all([
      fetch('/api/status'),
      fetch('/api/ctrl'),
    ]);
    const status=await statusRes.json();
    const ctrl=await ctrlRes.json();

    applyCtrlToUI(ctrl);

    // update status bar
    if(status.fps!=null)document.getElementById('cs-fps').textContent=`fps ${status.fps.toFixed?status.fps.toFixed(1):status.fps}`;
    if(status.uptime!=null){
      const u=Math.round(status.uptime);
      const m=Math.floor(u/60),s=u%60;
      document.getElementById('cs-uptime').textContent=`up ${m}:${String(s).padStart(2,'0')}`;
    }
    const modeIdx=ctrl.mode??0;
    const modeName=MODES[modeIdx]||`mode ${modeIdx}`;
    document.getElementById('cs-mode').textContent=`mode ${modeIdx} ${modeName}`;
    document.getElementById('cs-poll').style.color='#33aa33';
  }catch(e){
    document.getElementById('cs-poll').style.color='#aa3333';
  }
  setTimeout(pollCtrl,500);
}

// ── init ctrl UI ──────────────────────────────────────────────
// buildModeGrids() is called from fetchModes() which runs on load
// so by the time the user clicks CTRL, grids are ready.
// Build palette grid immediately (doesn't need server data).
buildPaletteGrid();

// Load initial ctrl state on page load so UI isn't blank even on MAP tab
(async()=>{
  try{
    const r=await fetch('/api/ctrl');
    const c=await r.json();
    applyCtrlToUI(c);
  }catch(e){}
})();

// ══════════════════════════════════════════════════════════════
//  MEDIA TAB
// ══════════════════════════════════════════════════════════════
let mediaStatusTimer=null;

async function mediaLoad(){
  try{
    const r=await fetch('/api/media');
    const files=await r.json();
    renderMediaGrid(files);
  }catch(e){}
}

function renderMediaGrid(files){
  const g=document.getElementById('media-grid');
  if(!files.length){g.innerHTML='<div class="media-empty">no media files — upload something above</div>';return;}
  g.innerHTML='';
  files.forEach(f=>{
    const card=document.createElement('div');
    card.className='media-card';
    const ext=f.name.split('.').pop().toLowerCase();
    const isVideo=['mp4','mkv','avi','mov','webm','ts','m4v'].includes(ext);
    const sizeMB=(f.size/1024/1024).toFixed(1);
    card.innerHTML=`
      <div class="media-name">${f.name}</div>
      <div class="media-meta">${isVideo?'▶ VIDEO':'🖼 IMAGE'}  ·  ${sizeMB} MB</div>
      <div class="media-btns">
        ${isVideo?`<button class="cbtn btn-ok" onclick="mediaPlay('${f.name}')">▶ PLAY</button>`:''}
        <button class="cbtn btn-del" onclick="mediaDelete('${f.name}')">✕ DELETE</button>
      </div>`;
    g.appendChild(card);
  });
}

async function uploadFiles(files){
  const prog=document.getElementById('upload-progress');
  prog.style.display='block';
  for(let i=0;i<files.length;i++){
    const f=files[i];
    prog.textContent=`uploading ${f.name} (${i+1}/${files.length})...`;
    const fd=new FormData();fd.append('file',f);
    try{
      await fetch('/api/upload',{method:'POST',body:fd});
    }catch(e){prog.textContent='upload error: '+e;return;}
  }
  prog.textContent='done ✓';
  setTimeout(()=>{prog.style.display='none';prog.textContent=''},2000);
  document.getElementById('file-input').value='';
  mediaLoad();
}

async function mediaPlay(name){
  try{
    await fetch('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:name})});
    document.getElementById('now-playing').textContent='▶  '+name;
    document.getElementById('stop-btn').style.display='';
  }catch(e){}
}

async function mediaStop(){
  try{
    await fetch('/api/playstop',{method:'POST'});
    document.getElementById('now-playing').textContent='no video playing';
    document.getElementById('stop-btn').style.display='none';
  }catch(e){}
}

function mediaStatusPoll(){
  clearInterval(mediaStatusTimer);
  mediaStatusTimer=setInterval(async()=>{
    if(activeTab!=='media')return;
    try{
      const r=await fetch('/api/playstatus');
      const d=await r.json();
      if(d.playing){
        document.getElementById('now-playing').textContent='▶  '+d.file;
        document.getElementById('stop-btn').style.display='';
      }else{
        document.getElementById('now-playing').textContent='no video playing';
        document.getElementById('stop-btn').style.display='none';
      }
    }catch(e){}
  },2000);
}

async function mediaDelete(name){
  if(!confirm('Delete '+name+'?'))return;
  try{
    await fetch('/api/media?file='+encodeURIComponent(name),{method:'DELETE'});
    mediaLoad();
  }catch(e){}
}

// ══════════════════════════════════════════════════════════════
//  ZONES TAB
// ══════════════════════════════════════════════════════════════
let zonesFile='fb_map.json';
let zonesSurfaces=[];
let zonesInited=false;
let zonesPollTimer=null;

async function zonesInit(){
  if(!zonesInited){
    zonesInited=true;
    // populate file selector (reuse same list)
    try{
      const r=await fetch('/api/list');const files=await r.json();
      const sel=document.getElementById('zones-file-sel');sel.innerHTML='';
      files.forEach(f=>{const o=document.createElement('option');o.value=f;o.textContent=f;if(f===zonesFile)o.selected=true;sel.appendChild(o)});
    }catch(e){}
  }
  await zonesLoad();
  clearInterval(zonesPollTimer);
  zonesPollTimer=setInterval(()=>{if(activeTab==='zones')zonesLoad()},2000);
}

function zonesLoadFile(f){zonesFile=f;zonesLoad();}

async function zonesLoad(){
  try{
    const r=await fetch('/api/mapping?file='+zonesFile);
    const d=await r.json();
    zonesSurfaces=d.surfaces||[];
    renderZonesGrid();
    document.getElementById('zones-status').style.color='#33aa33';
  }catch(e){
    document.getElementById('zones-status').style.color='#aa3333';
  }
}

function renderZonesGrid(){
  const g=document.getElementById('zones-grid');
  if(!zonesSurfaces.length){g.innerHTML='<div class="zone-empty">no surfaces in this mapping</div>';return;}
  g.innerHTML='';
  zonesSurfaces.forEach((s,i)=>{
    const col=COLS[i%COLS.length];
    const card=document.createElement('div');
    card.className='zone-card';
    card.style.borderLeftColor=col;

    const modeOpts='<option value="null"'+(s.mode===null?' selected':'')+'>∅  follow active</option>'+
      MODES.map((n,mi)=>`<option value="${mi}"${s.mode===mi?' selected':''}>${mi}  ${n}</option>`).join('');
    const videoOpts='<option value="">none — use mode</option>'+
      MEDIA_FILES.filter(f=>_isVideoFile(f.name))
        .map(f=>`<option value="${f.name}"${s.video===f.name?' selected':''}>▶ ${f.name}</option>`).join('');

    card.innerHTML=`
      <div class="zone-id" style="color:${col}">${s.id||'SURF-'+i}</div>
      <select onchange="zoneSet(${i},'mode',this.value==='null'?null:+this.value)">${modeOpts}</select>
      <select onchange="zoneSet(${i},'video',this.value||null)" style="font-size:9px">${videoOpts}</select>
      <label class="toggle-wrap">
        <input type="checkbox" class="toggle" ${s.enabled!==false?'checked':''}
               onchange="zoneSet(${i},'enabled',this.checked)">
        ENABLED
      </label>
      <div class="slider-row" style="margin-bottom:0">
        <label style="width:40px">PHASE</label>
        <input type="range" min="0" max="8" step="0.1" value="${s.phase||0}"
               oninput="zoneSet(${i},'phase',parseFloat(this.value));this.nextElementSibling.textContent=parseFloat(this.value).toFixed(1)">
        <span class="sval">${(s.phase||0).toFixed(1)}</span>
      </div>`;
    g.appendChild(card);
  });
}

function zoneSet(i,key,val){
  zonesSurfaces[i][key]=val;
  zonesSave();
  // reflect immediately in renderSide if map tab was editing same file
  if(curFile===zonesFile){surfaces=JSON.parse(JSON.stringify(zonesSurfaces));renderSide();draw();}
}

async function zonesSave(){
  try{
    await fetch('/api/save?file='+zonesFile,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:zonesFile.replace('.json',''),surfaces:zonesSurfaces})
    });
    document.getElementById('zones-status').textContent='✓';
    setTimeout(()=>document.getElementById('zones-status').textContent='●',800);
  }catch(e){}
}
</script>
<!-- ════════════════════════════════════════
     OUTPUTS TAB
     ════════════════════════════════════════ -->
<div id="tab-outputs">
  <div id="out-strip">
    <span id="out-x-badge">X11 ●</span>
    <button class="cbtn" onclick="restartXLayout()" style="width:auto;padding:3px 10px;margin-top:0;font-size:9px;letter-spacing:1px">RESTART X</button>
    <span id="out-strip-status"></span>
  </div>
  <div id="out-main">
    <div id="out-assign-area">
      <div>
        <div class="out-role-label">CONTROLLER</div>
        <div id="out-ctrl-btns" class="out-disp-btns"></div>
      </div>
      <div>
        <div class="out-role-label">PROJECTOR</div>
        <div id="out-vis-btns" class="out-disp-btns"></div>
      </div>
    </div>
    <div id="out-map-area">
      <div class="out-role-label">MAPPING</div>
      <div id="out-map-btns"></div>
    </div>
    <div id="out-action-area">
      <button id="out-apply-btn" onclick="applyOutputPlan()">APPLY TO STAGE</button>
      <span id="out-layout-status"></span>
    </div>
  </div>
</div>

<!-- ════════════════════════════════════════
     HELP TAB
     ════════════════════════════════════════ -->
<div id="tab-help">
  <div id="help-body">
    <div class="help-section">
      <h3>CONNECT</h3>
      <div class="help-list">
        <div class="help-row"><span>Web portal</span><span id="help-web">—</span></div>
        <div class="help-row"><span>SSH</span><span id="help-ssh">—</span></div>
        <div class="help-row"><span>Host</span><span id="help-host">—</span></div>
        <div class="help-row"><span>IP addresses</span><span id="help-ips">—</span></div>
      </div>
    </div>
    <div class="help-section">
      <h3>RUN THE SHOW</h3>
      <div class="help-code">ii status
ii xstart
ii restart x
ii logs x
ii attach</div>
      <p>Use X mode for laptop controller plus projector visuals. Use CTRL for live controls and OUTPUTS for display placement.</p>
    </div>
    <div class="help-section">
      <h3>DISPLAY CHECK</h3>
      <div class="help-list">
        <div class="help-row"><span>X11</span><span id="help-x">—</span></div>
        <div class="help-row"><span>Layout</span><span id="help-layout">—</span></div>
        <div class="help-row"><span>Displays</span><span id="help-displays">—</span></div>
      </div>
      <div class="help-actions">
        <button class="cbtn" onclick="switchTab('outputs')">OPEN OUTPUTS</button>
        <button class="cbtn" onclick="helpLoad()">REFRESH</button>
      </div>
    </div>
    <div class="help-section">
      <h3>RESTART SERVICES</h3>
      <div class="help-actions">
        <button class="cbtn" onclick="restartProgram('vis')">RESTART VISUALS</button>
        <button class="cbtn" onclick="restartProgram('ctrl')">RESTART CTRL</button>
        <button class="cbtn" onclick="restartProgram('web')">RESTART WEB</button>
        <button class="cbtn" onclick="restartProgram('x')">RESTART X</button>
        <button class="cbtn" onclick="restartProgram('all')">RESTART ALL</button>
      </div>
      <div class="out-status" id="help-restart-status">Use these to apply changes without rebooting Debian.</div>
    </div>
    <div class="help-section">
      <h3>EMERGENCY</h3>
      <div class="help-code">ii restart x
ii restart vis
ii stop</div>
      <p>Use BLACKOUT in CTRL for a clean blank screen. Restart X if the controller is on the wrong screen or the projector is black.</p>
    </div>
  </div>
</div>

<script>
let outputsTimer=null;
let outputApplyBusy=false;
let selCtrl='', selVis='', selMapping=0, _outInited=false;

async function outputsLoad(){
  await refreshOutputs();
  clearInterval(outputsTimer);
  outputsTimer=setInterval(()=>{if(activeTab==='outputs')refreshOutputs()},3000);
}

async function refreshOutputs(){
  try{
    const r=await fetch('/api/output-setup');
    const d=await r.json();
    renderOutputs(d);
  }catch(e){
    const b=document.getElementById('out-x-badge');
    if(b){b.textContent='X11 ✕';b.className='warn';}
  }
}

function renderOutputs(d){
  const badge=document.getElementById('out-x-badge');
  if(badge){badge.textContent=d.x_running?'X11 ●':'X11 ✕';badge.className=d.x_running?'ok':'warn';}
  const displays=(d.displays||[]).filter(x=>x.connected);
  if(!_outInited){
    _outInited=true;
    selCtrl=d.assign?.ctrl||d.suggested_ctrl||displays[0]?.name||'';
    selVis=d.assign?.vis||d.suggested_vis||displays[1]?.name||displays[0]?.name||'';
    selMapping=d.active_mapping??0;
  }
  buildDispButtons('out-ctrl-btns',displays,selCtrl,n=>{selCtrl=n;checkSameDisp();});
  buildDispButtons('out-vis-btns',displays,selVis,n=>{selVis=n;checkSameDisp();});
  buildMapButtons(d.mappings||[],selMapping);
  checkSameDisp();
}

function checkSameDisp(){
  const s=document.getElementById('out-layout-status');
  if(!s)return;
  if(selCtrl&&selCtrl===selVis){s.textContent='⚠ same display for both';s.className='out-warn';}
  else if(s.className==='out-warn'){s.textContent='';s.className='';}
}

function buildDispButtons(id,displays,selected,onSelect){
  const box=document.getElementById(id);
  if(!box)return;
  box.innerHTML='';
  if(!displays.length){box.innerHTML='<div style="color:#555;font-size:10px;padding:6px">no displays detected</div>';return;}
  displays.forEach(d=>{
    const btn=document.createElement('button');
    btn.className='out-disp-btn'+(d.name===selected?' active':'');
    btn.innerHTML=`<span class="dname">${d.name}</span><span class="dres">${d.resolution||'—'}</span>`;
    btn.onclick=()=>{onSelect(d.name);box.querySelectorAll('.out-disp-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');};
    box.appendChild(btn);
  });
}

function buildMapButtons(mappings,activeIdx){
  const box=document.getElementById('out-map-btns');
  if(!box)return;
  box.innerHTML='';
  if(!mappings.length){box.innerHTML='<div style="color:#555;font-size:10px;padding:6px">no mapping files</div>';return;}
  mappings.forEach((m,i)=>{
    const btn=document.createElement('button');
    btn.className='out-map-btn'+(i===activeIdx?' active':'');
    const n=m.surfaces||0;
    btn.innerHTML=`${m.name||m.file}<div class="msurfs">${n} surface${n!==1?'s':''}</div>`;
    btn.onclick=()=>{
      selMapping=i;
      box.querySelectorAll('.out-map-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mapping:i})}).catch(()=>{});
    };
    box.appendChild(btn);
  });
}

async function applyOutputPlan(){
  if(outputApplyBusy)return;
  const st=document.getElementById('out-layout-status');
  if(!selCtrl||!selVis){if(st){st.textContent='select controller and projector first';st.className='';}return;}
  if(selCtrl===selVis&&!confirm('Controller and projector are the same display. Apply anyway?'))return;
  outputApplyBusy=true;
  if(st){st.textContent='applying…';st.className='';}
  try{
    const r=await fetch('/api/output-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ctrl:selCtrl,vis:selVis,mapping:selMapping,blackout:true})});
    const d=await r.json();
    if(st)st.textContent=d.msg||'applied ✓';
  }catch(e){
    if(st)st.textContent='error: '+e;
  }finally{outputApplyBusy=false;}
  setTimeout(refreshOutputs,800);
}

async function restartXLayout(){
  if(!confirm('Restart the X show layout? The display may blink.'))return;
  const st=document.getElementById('out-strip-status');
  if(st)st.textContent='restarting X…';
  try{
    const r=await fetch('/api/display-layout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layout:'restart-x'})});
    const d=await r.json();
    if(st){st.textContent=d.msg||'restart requested';setTimeout(()=>{st.textContent='';},4000);}
  }catch(e){if(st)st.textContent='error: '+e;}
}

async function helpLoad(){
  try{
    const [sysRes,dispRes]=await Promise.all([fetch('/api/system'),fetch('/api/displays')]);
    const sys=await sysRes.json();
    const disp=await dispRes.json();
    document.getElementById('help-web').textContent=sys.portal_url||location.origin;
    document.getElementById('help-ssh').textContent=sys.ssh||'ssh dob@'+location.hostname;
    document.getElementById('help-host').textContent=sys.hostname||'—';
    document.getElementById('help-ips').textContent=(sys.ips||[]).join(', ')||location.hostname;
    document.getElementById('help-x').innerHTML=disp.x_running?'<span class="help-ok">running</span>':'<span class="help-warn">stopped</span>';
    document.getElementById('help-layout').textContent=disp.layout||'unknown';
    document.getElementById('help-displays').textContent=(disp.displays||[]).filter(d=>d.connected).map(d=>`${d.name} ${d.resolution||'off'}`).join(' · ')||'none';
  }catch(e){}
}

async function restartProgram(target){
  const loud = target === 'x' || target === 'all';
  if(loud && !confirm('This will restart running show processes. Continue?'))return;
  const status = document.getElementById('help-restart-status');
  status.textContent = 'sending restart request...';
  try{
    const r = await fetch('/api/system-action', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:'restart', target})
    });
    const d = await r.json();
    status.textContent = d.msg || ('restart requested: ' + target);
    if(target === 'web' || target === 'all'){
      setTimeout(() => { status.textContent += ' (portal may reconnect)'; }, 120);
    }
  }catch(e){
    status.textContent = 'error: ' + e;
  }
}
</script>

</body></html>"""


# ── display management helpers ────────────────────────────────────────────────
_ASSIGN_FILE = os.path.join(BASE, 'display_assign.json')

def _parse_xrandr():
    import re
    try:
        env = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/home/dob/.Xauthority'}
        out = subprocess.check_output(['xrandr', '--query'], env=env,
                                      stderr=subprocess.DEVNULL, timeout=3).decode()
    except Exception:
        return []
    displays = []
    for line in out.splitlines():
        m = re.match(r'^([\w\-]+) (connected|disconnected)(?: primary)? ?(\d+x\d+\+\d+\+\d+)?', line)
        if m:
            name, status, geom = m.group(1), m.group(2), m.group(3)
            res = pos = None
            if geom:
                parts = geom.split('+')
                res = parts[0]
                pos = f'{parts[1]},{parts[2]}'
            displays.append({
                'name': name,
                'connected': status == 'connected',
                'primary': ' primary ' in f' {line} ',
                'resolution': res,
                'position': pos,
            })
    return displays

def _detect_layout(displays):
    active = [d for d in displays if d['resolution']]
    if not active:
        return 'none'
    if len(active) == 1:
        return 'projector' if 'HDMI' in active[0]['name'] else 'laptop'
    positions = set(d['position'] for d in active if d['position'])
    return 'mirror' if len(positions) == 1 else 'extend'

def _load_assign():
    try:
        with open(_ASSIGN_FILE) as f:
            return json.load(f)
    except Exception:
        return {'ctrl': None, 'vis': None}

def _save_assign(a):
    with open(_ASSIGN_FILE, 'w') as fh:
        json.dump(a, fh)

def _x_running():
    return os.path.exists('/tmp/.X11-unix/X0')

def _local_ips():
    ips = []
    try:
        out = subprocess.check_output(['hostname', '-I'], stderr=subprocess.DEVNULL, timeout=2).decode()
        ips.extend(ip for ip in out.split() if not ip.startswith('127.'))
    except Exception:
        pass
    if not ips:
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if not ip.startswith('127.'):
                ips.append(ip)
        except Exception:
            pass
    return ips

def _system_info():
    ips = _local_ips()
    host = socket.gethostname()
    primary = ips[0] if ips else 'localhost'
    return {
        'hostname': host,
        'ips': ips,
        'portal_url': f'http://{primary}:{PORT}',
        'ssh': f'ssh dob@{primary}',
        'repo': BASE,
        'port': PORT,
    }


def _system_action(body):
    action = str(body.get('action', '')).strip().lower()
    target = str(body.get('target', '')).strip().lower()
    if action != 'restart':
        return 'unsupported action'

    helper = '/home/dob/bin/ii'
    if not os.path.exists(helper):
        return 'restart helper not found: /home/dob/bin/ii'

    aliases = {
        'visuals': 'vis',
        'vis': 'vis',
        'controller': 'ctrl',
        'ctrl': 'ctrl',
        'web': 'web',
        'x': 'x',
        'all': 'x',
    }
    resolved = aliases.get(target)
    if not resolved:
        return 'unknown restart target'

    try:
        subprocess.Popen([helper, 'restart', resolved],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        label = 'full show' if target == 'all' else resolved
        return f'restart requested: {label}'
    except Exception as exc:
        return f'restart failed: {exc}'


def _get_display_names(displays):
    laptop = projector = None
    for d in displays:
        n = d['name']
        if any(k in n for k in ('LVDS', 'eDP', 'LVDS-1', 'eDP-1')):
            laptop = n
        elif any(k in n for k in ('HDMI', 'DP-', 'DisplayPort')):
            if projector is None:
                projector = n
    return laptop, projector

def _suggest_assignments(displays):
    active = [d for d in displays if d.get('connected')]
    laptop, projector = _get_display_names(active)
    if not laptop:
        primary = next((d['name'] for d in active if d.get('primary')), None)
        laptop = primary or (active[0]['name'] if active else None)
    if not projector:
        projector = next((d['name'] for d in active if d['name'] != laptop), None)
    return laptop, projector

def _mapping_files():
    files = []
    try:
        names = sorted(f for f in os.listdir(MAPPINGS_DIR) if f.endswith('.json'))
    except Exception:
        return files
    for name in names:
        data = load_json(os.path.join(MAPPINGS_DIR, name), {})
        files.append({
            'file': name,
            'name': data.get('name') or name.replace('.json', ''),
            'surfaces': len(data.get('surfaces') or data.get('zones') or []),
        })
    return files

def _display_geometry(display):
    if not display or not display.get('position') or not display.get('resolution'):
        return None
    try:
        x, y = [int(v) for v in display['position'].split(',', 1)]
        w, h = [int(v) for v in display['resolution'].split('x', 1)]
        return x, y, w, h
    except Exception:
        return None

def _move_window(title, display, fullscreen=False, maximize=False):
    geom = _display_geometry(display)
    if not geom:
        return False
    x, y, w, h = geom
    env = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/home/dob/.Xauthority'}
    try:
        subprocess.run(['wmctrl', '-r', title, '-b', 'remove,fullscreen,maximized_vert,maximized_horz'],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        subprocess.run(['wmctrl', '-r', title, '-e', f'0,{x},{y},{w},{h}'],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        if fullscreen:
            subprocess.run(['wmctrl', '-r', title, '-b', 'add,fullscreen'],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        if maximize:
            subprocess.run(['wmctrl', '-r', title, '-b', 'add,maximized_vert,maximized_horz'],
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return True
    except Exception:
        return False

def _output_setup_state():
    displays = _parse_xrandr()
    assign = _load_assign()
    suggested_ctrl, suggested_vis = _suggest_assignments(displays)
    ctrl = load_json(CTRL_PATH, {})
    mappings = _mapping_files()
    active_mapping = int(ctrl.get('mapping', 0) or 0)
    if active_mapping < 0:
      active_mapping = 0
    if mappings:
      active_mapping = min(active_mapping, len(mappings) - 1)
      active_mapping_file = mappings[active_mapping]['file']
    else:
      active_mapping_file = ''
    return {
        'displays': displays,
        'layout': _detect_layout(displays),
        'assign': assign,
        'suggested_ctrl': suggested_ctrl,
        'suggested_vis': suggested_vis,
      'mappings': mappings,
      'active_mapping': active_mapping,
      'active_mapping_file': active_mapping_file,
        'ctrl': ctrl,
        'x_running': _x_running(),
        'display': ':0',
    }

def _apply_output_setup(body):
    ctrl_name = body.get('ctrl')
    vis_name = body.get('vis')
    mapping = int(body.get('mapping', 0) or 0)
    blackout = bool(body.get('blackout', True))
    displays = _parse_xrandr()
    ctrl_display = next((d for d in displays if d['name'] == ctrl_name and d.get('connected')), None)
    vis_display = next((d for d in displays if d['name'] == vis_name and d.get('connected')), None)
    if not ctrl_display or not vis_display:
        return 'choose connected controller and projector displays'
    if ctrl_name == vis_name:
      return 'controller and visuals cannot be assigned to the same display'

    env = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/home/dob/.Xauthority'}
    previous_ctrl = load_json(CTRL_PATH, {})
    previous_blackout = bool(previous_ctrl.get('blackout', False))
    mappings = _mapping_files()
    if mappings:
        mapping = max(0, min(mapping, len(mappings) - 1))
    else:
        mapping = 0

    if not _x_running():
        return 'X is not running; start or restart X first'

    if blackout:
        state = dict(previous_ctrl)
        state['blackout'] = True
        save_json_atomic(CTRL_PATH, state)

    try:
      cmd = ['xrandr', '--output', ctrl_name, '--auto', '--primary',
           '--output', vis_name, '--auto', '--right-of', ctrl_name]
      proc = subprocess.run(cmd, env=env, timeout=5,
                  stdout=subprocess.DEVNULL,
                  stderr=subprocess.PIPE, text=True)
      if proc.returncode != 0:
        err = (proc.stderr or 'xrandr failed').strip()
        return f'xrandr failed: {err}'
    except Exception as exc:
      return f'xrandr error: {exc}'
    finally:
      if blackout:
        restore = dict(load_json(CTRL_PATH, {}))
        restore['blackout'] = previous_blackout
        save_json_atomic(CTRL_PATH, restore)

    time_sleep = 0.4
    try:
        import time
        time.sleep(time_sleep)
    except Exception:
        pass

    displays = _parse_xrandr()
    ctrl_display = next((d for d in displays if d['name'] == ctrl_name), ctrl_display)
    vis_display = next((d for d in displays if d['name'] == vis_name), vis_display)
    _move_window('_ii controller', ctrl_display, maximize=True)
    _move_window('ii-VISUALS', vis_display, fullscreen=True)

    assign = _load_assign()
    assign.update({'ctrl': ctrl_name, 'vis': vis_name})
    _save_assign(assign)

    state = dict(load_json(CTRL_PATH, {}))
    state['mapping'] = mapping
    if blackout:
      state['blackout'] = previous_blackout
    save_json_atomic(CTRL_PATH, state)
    return f'stage output applied: controller={ctrl_name}, visuals={vis_name}, mapping={mapping}'

def _apply_layout(layout):
    env = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/home/dob/.Xauthority'}
    displays = _parse_xrandr()
    laptop, projector = _get_display_names(displays)
    try:
        if layout == 'restart-x':
            helper = '/home/dob/bin/ii'
            if os.path.exists(helper):
                subprocess.Popen([helper, 'restart', 'x'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return 'X show layout restarting'
            return 'restart helper not found: /home/dob/bin/ii'
        if layout == 'extend':
            cmd = ['xrandr']
            if laptop:
                cmd += ['--output', laptop, '--auto', '--primary']
            if projector:
                ref = laptop or 'LVDS-1'
                cmd += ['--output', projector, '--auto', '--right-of', ref]
            subprocess.run(cmd, env=env, timeout=5)
            return 'extended desktop applied'
        elif layout == 'mirror':
            return 'mirror is disabled in the portal; use OS display settings if you really need it'
        elif layout == 'projector':
            return 'projector-only is disabled to avoid losing the controller'
        elif layout == 'laptop':
            return 'laptop-only is disabled in the portal; use ii stop for teardown'
        elif layout == 'start':
            xscript = '/home/dob/_ii/scripts/start-x.sh'
            subprocess.Popen(['sudo', '-u', 'dob', 'bash', '-c',
                              f'startx {xscript} -- :0 vt7 &'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 'X11 starting on VT7…'
    except Exception as e:
        return f'error: {e}'
    return f'unknown layout: {layout}'

def _assign_content(role, display):
    env = {**os.environ, 'DISPLAY': ':0', 'XAUTHORITY': '/home/dob/.Xauthority'}
    assign = _load_assign()
    assign[role] = display
    _save_assign(assign)
    displays = _parse_xrandr()
    disp = next((d for d in displays if d['name'] == display), None)
    if not disp or not disp['position']:
        return f'{role} saved → {display} (position unknown)'
    px, py = disp['position'].split(',')
    title = '_ii controller' if role == 'ctrl' else 'ii-VISUALS'
    try:
        subprocess.run(['wmctrl', '-r', title, '-e', f'0,{px},{py},-1,-1'],
                       env=env, timeout=3)
        return f'{role} moved → {display.replace("card0-","")} ({px},{py})'
    except Exception as e:
        return f'saved; wmctrl: {e}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        global _mpv_proc
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        if p.path == '/':
            self._send(200, 'text/html; charset=utf-8', HTML.encode())
        elif p.path == '/api/modes':
            self._json(discover_mode_names())
        elif p.path == '/api/list':
            files = sorted(f for f in os.listdir(MAPPINGS_DIR) if f.endswith('.json'))
            self._json(files)
        elif p.path == '/api/mapping':
            fname = qs.get('file', ['fb_map.json'])[0]
            path = os.path.join(MAPPINGS_DIR, fname)
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
            else:
                data = {'name': fname.replace('.json', ''), 'surfaces': []}
            if 'zones' in data and 'surfaces' not in data:
                data['surfaces'] = [_zone_to_surface(z) for z in data['zones']]
            self._json(data)
        elif p.path == '/api/status':
            self._json(load_json(STATUS_PATH, {}))
        elif p.path == '/api/ctrl':
            self._json(load_json(CTRL_PATH, {}))
        elif p.path == '/api/media':
            os.makedirs(MEDIA_DIR, exist_ok=True)
            files = []
            for f in sorted(os.listdir(MEDIA_DIR)):
                fp = os.path.join(MEDIA_DIR, f)
                if os.path.isfile(fp):
                    files.append({'name': f, 'size': os.path.getsize(fp)})
            self._json(files)
        elif p.path == '/api/playstatus':
            playing = _mpv_proc is not None and _mpv_proc.poll() is None
            self._json({'playing': playing, 'file': getattr(_mpv_proc, '_filename', '') if playing else ''})
        elif p.path == '/api/displays':
            displays = _parse_xrandr()
            self._json({
                'displays': displays,
                'layout': _detect_layout(displays),
                'assign': _load_assign(),
                'x_running': _x_running(),
                'display': ':0',
            })
        elif p.path == '/api/system':
            self._json(_system_info())
        elif p.path == '/api/output-setup':
            self._json(_output_setup_state())
        else:
            self._send(404, 'text/plain', b'not found')

    def do_DELETE(self):
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        if p.path == '/api/media':
            fname = qs.get('file', [''])[0]
            path = os.path.join(MEDIA_DIR, os.path.basename(fname))
            if os.path.isfile(path):
                os.remove(path)
                self._json({'ok': True})
            else:
                self._send(404, 'text/plain', b'not found')
        else:
            self._send(404, 'text/plain', b'not found')

    def do_POST(self):
        global _mpv_proc
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        n = int(self.headers.get('Content-Length', 0))
        ct = self.headers.get('Content-Type', '')
        raw = self.rfile.read(n) if n else b''
        body = json.loads(raw) if n and not ct.startswith('multipart') else {}

        if p.path == '/api/save':
            fname = qs.get('file', ['fb_map.json'])[0]
            path = os.path.join(MAPPINGS_DIR, fname)
            with open(path, 'w') as f:
                json.dump(body, f, indent=2)
            self._json({'ok': True})
        elif p.path == '/api/ctrl':
            existing = load_json(CTRL_PATH, {})
            existing.update(body)
            save_json_atomic(CTRL_PATH, existing)
            self._json({'ok': True})
        elif p.path == '/api/upload':
            os.makedirs(MEDIA_DIR, exist_ok=True)
            msg = BytesParser(policy=email_default).parsebytes(
                b'Content-Type: ' + ct.encode() + b'\r\n\r\n' + raw)
            saved = []
            for part in msg.iter_attachments():
                fname = part.get_filename() or 'upload'
                fname = os.path.basename(fname)
                dest = os.path.join(MEDIA_DIR, fname)
                with open(dest, 'wb') as f:
                    f.write(part.get_payload(decode=True))
                saved.append(fname)
            self._json({'ok': True, 'saved': saved})
        elif p.path == '/api/play':
            fname = body.get('file', '')
            path = os.path.join(MEDIA_DIR, os.path.basename(fname))
            if not os.path.isfile(path):
                self._send(404, 'text/plain', b'file not found')
                return
            # pause visuals so tty1 is free
            subprocess.run(['pkill', '-STOP', '-f', 'visuals.py'], capture_output=True)
            if _mpv_proc and _mpv_proc.poll() is None:
                _mpv_proc.terminate()
            proc = subprocess.Popen(
                ['mpv', '--vo=drm', '--loop=no', '--fs', path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc._filename = fname
            _mpv_proc = proc
            self._json({'ok': True, 'playing': fname})
        elif p.path == '/api/playstop':
            if _mpv_proc and _mpv_proc.poll() is None:
                _mpv_proc.terminate()
            _mpv_proc = None
            subprocess.run(['pkill', '-CONT', '-f', 'visuals.py'], capture_output=True)
            self._json({'ok': True})
        elif p.path == '/api/display-layout':
            msg = _apply_layout(body.get('layout', ''))
            self._json({'ok': True, 'msg': msg})
        elif p.path == '/api/display-assign':
            msg = _assign_content(body.get('role', ''), body.get('display', ''))
            self._json({'ok': True, 'msg': msg})
        elif p.path == '/api/output-setup':
            msg = _apply_output_setup(body)
            self._json({'ok': True, 'msg': msg})
        elif p.path == '/api/system-action':
            msg = _system_action(body)
            self._json({'ok': True, 'msg': msg})
        else:
            self._send(404, 'text/plain', b'not found')

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        self._send(200, 'application/json', json.dumps(data).encode())


def _zone_to_surface(z):
    x, y = z.get('x', 0.0), z.get('y', 0.0)
    w, h = z.get('w', 1.0), z.get('h', 1.0)
    return {
        'id': z.get('id', 'SURF'),
        'corners': [[x, y], [x+w, y], [x+w, y+h], [x, y+h]],
        'mode': z.get('mode'),
        'phase': z.get('phase', 0.0),
        'enabled': z.get('enabled', True),
    }


if __name__ == '__main__':
    os.makedirs(MAPPINGS_DIR, exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    print(f'open on your laptop:  http://192.168.88.136:{PORT}')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
