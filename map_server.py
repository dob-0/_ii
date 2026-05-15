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
#tab-map,#tab-ctrl,#tab-zones,#tab-media,#tab-camera,#tab-outputs,#tab-help,#tab-term{flex:1;display:none;overflow:hidden}
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
   CAMERA TAB
   ════════════════════════════════════════ */
#tab-camera.active{display:flex;flex-direction:column;background:#030303}
#camera-toolbar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--bg1);border-bottom:1px solid var(--border);flex-shrink:0;flex-wrap:wrap}
#camera-toolbar label{font-size:9px;letter-spacing:2px;color:var(--text4);margin-top:0}
#camera-url{width:min(520px,60vw);margin-top:0}
#camera-status{margin-left:auto;font-size:10px;color:var(--text4);letter-spacing:1px}
#camera-status.ok{color:var(--accent3)}
#camera-status.warn{color:var(--accent2)}
#camera-body{flex:1;display:flex;min-height:0}
#camera-view{flex:1;display:flex;align-items:center;justify-content:center;background:#000;position:relative;overflow:hidden}
#camera-stream{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;image-rendering:auto;display:none}
#camera-empty{color:#222;font-size:12px;letter-spacing:2px}
#camera-side{width:240px;flex-shrink:0;border-left:1px solid var(--border);background:#070707;padding:12px;overflow-y:auto}
.camera-side-label{font-size:9px;letter-spacing:2px;color:#333;margin:2px 0 8px}
.camera-preset{width:100%;text-align:left;font-size:10px;padding:6px 8px;margin:0 0 5px;background:#0a0a0a;border:1px solid #1a1a1a;color:#777}
.camera-preset:hover{color:var(--text2);border-color:#333}

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
canvas{cursor:crosshair}
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
.ctrl-stack{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px}
.ctrl-stack label{margin-top:0}

/* blackout */
#blackout-btn{width:100%;padding:18px;font-size:14px;letter-spacing:4px;border:2px solid #3a1515;color:#aa3333;background:var(--bg2);border-radius:3px;cursor:pointer;font-family:monospace;transition:background .1s,border-color .1s,color .1s}
#blackout-btn:hover{background:#1a0808;border-color:#5a2525}
#blackout-btn.on{background:#2a0808;border-color:#ff3333;color:#ff5555}

/* alpha slider full row */
.alpha-row{margin-top:8px}
.alpha-row label{font-size:9px;letter-spacing:1px;color:var(--text3);display:block;margin-bottom:4px}
.alpha-row input[type=range]{width:100%;accent-color:var(--accent2)}

/* ── OUTPUTS TAB ─────────────────────────────────────────────────────────── */
#tab-outputs.active{display:flex;flex-direction:column;background:var(--bg)}
/* top bar */
#out-topbar{display:flex;align-items:center;gap:10px;padding:8px 16px;background:var(--bg1);border-bottom:1px solid var(--border);flex-shrink:0}
#out-x-badge{font:10px/1 monospace;letter-spacing:1px;color:#555}
#out-x-badge.ok{color:var(--accent3)}
#out-x-badge.warn{color:var(--accent2)}
#out-topbar-right{margin-left:auto;display:flex;align-items:center;gap:10px}
#out-apply-btn{padding:8px 24px;font:10px/1 monospace;letter-spacing:2px;border:1px solid #1c4a1c;color:var(--accent3);background:#071207;cursor:pointer}
#out-apply-btn:hover{background:#0a1f0a;border-color:#2a6a2a}
#out-layout-status{font:10px/1 monospace;color:#555}
/* body: sidebar + main */
#out-body{flex:1;display:flex;overflow:hidden}
/* ── sidebar ── */
#out-sidebar{width:240px;flex-shrink:0;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow-y:auto;background:#080808}
.out-sb-section{padding:14px 14px 10px;border-bottom:1px solid #111}
.out-sb-label{font:9px/1 monospace;letter-spacing:2px;color:#333;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between}
.out-sb-label button{font:9px/1 monospace;letter-spacing:1px;padding:1px 6px;background:transparent;border:1px solid #1c3a1c;color:#2a5a2a;cursor:pointer}
.out-sb-label button:hover{color:#44aa44;border-color:#2a6a2a}
/* display rows */
.out-disp-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.out-disp-role{font:9px/1 monospace;letter-spacing:1px;color:#444;width:28px;flex-shrink:0}
.out-disp-sel{flex:1;font:10px/1 monospace;background:#0e0e0e;border:1px solid #1a1a1a;color:var(--text);padding:5px 6px;cursor:pointer}
.out-disp-sel.active-ok{border-color:#1a3a1a;color:var(--accent3)}
/* mapping list */
.out-map-item{display:flex;align-items:center;gap:0;margin-bottom:4px;cursor:pointer;border:1px solid transparent;padding:6px 8px;border-radius:2px}
.out-map-item:hover{background:#0d0d0d}
.out-map-item.active{background:#0a140a;border-color:#1a3a1a}
.out-map-item-name{font:11px/1 monospace;color:#888;flex:1}
.out-map-item.active .out-map-item-name{color:var(--accent3)}
.out-map-item-n{font:9px/1 monospace;color:#333}
.out-map-item.active .out-map-item-n{color:#3a7a3a}
/* project */
.out-proj-input{width:100%;box-sizing:border-box;background:#0e0e0e;border:1px solid #1a1a1a;color:var(--text);font:11px/1 monospace;padding:6px 8px;margin-bottom:6px}
.out-proj-row{display:flex;gap:6px;margin-bottom:6px}
.out-proj-sel{flex:1;font:10px/1 monospace;background:#0e0e0e;border:1px solid #1a1a1a;color:var(--text);padding:5px 6px}
.out-proj-btn{font:9px/1 monospace;letter-spacing:1px;padding:5px 10px;background:transparent;border:1px solid #1c3a1c;color:#3a7a3a;cursor:pointer;white-space:nowrap}
.out-proj-btn:hover{color:#55cc55;border-color:#2a6a2a}
#proj-status{font:10px/1.4 monospace;color:#555;min-height:14px}
/* ── main surface area ── */
#out-main{flex:1;display:flex;flex-direction:column;overflow:hidden}
#out-main-hdr{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid #111;flex-shrink:0}
#out-main-hdr-title{font:9px/1 monospace;letter-spacing:2px;color:#333;flex:1}
#out-surfaces{flex:1;overflow-y:auto;padding:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;align-content:start}
/* surface layer card */
.lyr-card{background:#0c0c0c;border:1px solid #1a1a1a;display:flex;flex-direction:column;cursor:default;transition:border-color .15s}
.lyr-card:hover{border-color:#2a2a2a}
.lyr-card.selected{border-color:#1a3a1a}
.lyr-head{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #111}
.lyr-id{font:10px/1 monospace;letter-spacing:1px;color:#555;flex:1}
.lyr-card.selected .lyr-id{color:var(--accent3)}
.lyr-toggle{display:flex}
.lyr-tog-btn{font:8px/1 monospace;letter-spacing:1px;padding:3px 7px;border:1px solid #1e1e1e;background:transparent;color:#333;cursor:pointer}
.lyr-tog-btn:first-child{border-radius:2px 0 0 2px}
.lyr-tog-btn:last-child{border-radius:0 2px 2px 0;border-left:none}
.lyr-tog-btn.on{background:#0a1a0a;border-color:#2a5a2a;color:var(--accent3)}
/* source display (big label) */
.lyr-src-display{padding:14px 12px;flex:1;display:flex;flex-direction:column;gap:4px}
.lyr-src-name{font:15px/1 monospace;color:#ccc;letter-spacing:1px}
.lyr-src-sub{font:9px/1 monospace;color:#333;letter-spacing:1px;text-transform:uppercase}
/* picker area */
.lyr-picker{border-top:1px solid #111;padding:8px}
/* mode grid inside card */
.lyr-mode-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:2px}
.lyr-mg-btn{font:9px/1 monospace;padding:5px 2px;border:1px solid #161616;background:#080808;color:#444;cursor:pointer;text-align:center}
.lyr-mg-btn:hover{color:#aaa;border-color:#2a2a2a}
.lyr-mg-btn.on{background:#081a08;border-color:#1c4a1c;color:var(--accent3)}
/* video list */
.lyr-vid-list{display:flex;flex-direction:column;gap:3px;max-height:120px;overflow-y:auto}
.lyr-vid-item{font:10px/1 monospace;padding:5px 7px;border:1px solid #161616;background:#080808;color:#555;cursor:pointer;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lyr-vid-item:hover{color:#aaa;border-color:#2a2a2a}
.lyr-vid-item.on{background:#081a08;border-color:#1c4a1c;color:var(--accent3)}
.lyr-vid-empty{font:10px/1 monospace;color:#252525;padding:4px 2px}
/* empty state */
#out-empty{display:flex;align-items:center;justify-content:center;height:100%;color:#1e1e1e;font:11px/1 monospace;letter-spacing:2px}
.out-warn{color:var(--accent2)!important}
/* strip-status alias kept for restartXLayout compat */
#out-strip-status{display:none}

/* ── HELP TAB ────────────────────────────────────────────────────────────── */
#tab-help{flex-direction:column;overflow-y:auto;background:var(--bg);padding:16px}
#tab-help.active{display:flex}

/* ── TERM TAB ────────────────────────────────────────────────────────────── */
#tab-term.active{display:flex;flex-direction:column;background:#000}
#term-quickbar{display:flex;flex-wrap:wrap;gap:4px;padding:6px 8px;background:#0a0a0a;border-bottom:1px solid #1a1a1a;flex-shrink:0}
#term-quickbar button{font:10px/1 monospace;letter-spacing:1px;padding:3px 8px;background:#0a0f0a;border:1px solid #1c3a1c;color:#3d8a3d;cursor:pointer}
#term-quickbar button:hover{background:#0d1f0d;color:#55cc55}
#term-output{flex:1;overflow-y:auto;padding:10px 14px;font:12px/1.5 monospace;color:#c8ffc8;background:#000;white-space:pre-wrap;word-break:break-all}
#term-output .t-prompt{color:#44ff88}
#term-output .t-cmd{color:#ffffff}
#term-output .t-out{color:#aaffaa}
#term-output .t-err{color:#ff8866}
#term-output .t-rc{color:#555;font-size:10px}
#term-input-row{display:flex;align-items:center;gap:6px;padding:6px 14px;background:#050505;border-top:1px solid #111;flex-shrink:0}
#term-input-row span{color:#44ff88;font:12px/1 monospace;white-space:nowrap}
#term-input{flex:1;background:transparent;border:none;outline:none;color:#fff;font:12px/1 monospace;caret-color:#44ff88}
#term-cwd{font:10px/1 monospace;color:#333;flex-shrink:0}
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
  <button class="tab-btn"        id="btn-camera" onclick="switchTab('camera')">[ CAMERA ]</button>
  <button class="tab-btn"        id="btn-media" onclick="switchTab('media')">[ MEDIA ]</button>
  <button class="tab-btn"        id="btn-outputs" onclick="switchTab('outputs')">[ OUTPUTS ]</button>
  <button class="tab-btn"        id="btn-help" onclick="switchTab('help')">[ HELP ]</button>
  <button class="tab-btn"        id="btn-term" onclick="switchTab('term')">[ TERM ]</button>
</div>

<!-- ════════════════════════════════════════
     MAP TAB
     ════════════════════════════════════════ -->
<div id="tab-map" class="active">
  <div id="side">
    <h1>MAP EDITOR</h1>
    <button id="mapmode-btn" onclick="toggleMapMode()" style="letter-spacing:2px;margin-bottom:6px">[ PREVIEW LIVE ]</button>
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
      <label>AREA ZOOM</label>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
        <button onclick="scaleSurf(0.96)">- ZOOM OUT</button>
        <button onclick="scaleSurf(1.04)">+ ZOOM IN</button>
      </div>
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
     CAMERA TAB
     ════════════════════════════════════════ -->
<div id="tab-camera">
  <div id="camera-toolbar">
    <label>ESP CAM</label>
    <input id="camera-url" type="text" spellcheck="false" autocomplete="off"
           placeholder="http://192.168.88.x:81/stream" onkeydown="cameraKey(event)">
    <button class="cbtn" onclick="cameraConnect()" style="width:auto;padding:3px 12px;margin-top:0">CONNECT</button>
    <button class="cbtn" onclick="cameraStop()" style="width:auto;padding:3px 12px;margin-top:0">STOP</button>
    <span id="camera-status">idle</span>
  </div>
  <div id="camera-body">
    <div id="camera-view">
      <img id="camera-stream" alt="ESP camera stream" onload="cameraLoaded()" onerror="cameraError()">
      <div id="camera-empty">NO CAMERA STREAM</div>
    </div>
    <div id="camera-side">
      <div class="camera-side-label">STREAM PATHS</div>
      <button class="camera-preset" onclick="cameraUsePath(':81/stream')">:81/stream</button>
      <button class="camera-preset" onclick="cameraUsePath('/stream')">/stream</button>
      <button class="camera-preset" onclick="cameraUsePath('/video')">/video</button>
      <button class="camera-preset" onclick="cameraUsePath('/mjpeg/1')">/mjpeg/1</button>
      <button class="camera-preset" onclick="cameraUsePath('/capture')">/capture</button>
      <div class="camera-side-label" style="margin-top:14px">COMMON LOCAL URLS</div>
      <button class="camera-preset" onclick="cameraSetUrl('http://192.168.4.1:81/stream')">192.168.4.1:81/stream</button>
      <button class="camera-preset" onclick="cameraSetUrl('http://192.168.88.1:81/stream')">192.168.88.1:81/stream</button>
      <button class="camera-preset" onclick="cameraSetUrl('http://esp32cam.local:81/stream')">esp32cam.local:81/stream</button>
    </div>
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
        <input type="text" id="flash-input" placeholder="SIGNAL" value="SIGNAL"
               onkeydown="if(event.key==='Enter')triggerFlash()">
        <button class="cbtn" onclick="triggerFlash()">TRIGGER</button>
      </div>
    </div>

    <div class="ctrl-section" style="grid-column:1/-1">
      <h3>EVENT COPY</h3>
      <div class="ctrl-stack">
        <div>
          <label>TITLE</label>
          <input type="text" id="event-title" placeholder="SIGNAL"
                 oninput="ctrlSet('event_title',this.value)">
        </div>
        <div>
          <label>KICKER</label>
          <input type="text" id="event-kicker" placeholder="LIVE SESSION"
                 oninput="ctrlSet('event_kicker',this.value)">
        </div>
        <div>
          <label>WHEN</label>
          <input type="text" id="event-when" placeholder="TONIGHT"
                 oninput="ctrlSet('event_when',this.value)">
        </div>
        <div>
          <label>WHERE</label>
          <input type="text" id="event-where" placeholder="MAIN ROOM"
                 oninput="ctrlSet('event_where',this.value)">
        </div>
        <div style="grid-column:1/-1">
          <label>LINEUP (use | between names)</label>
          <input type="text" id="event-lineup" placeholder="ARTIST A|ARTIST B|ARTIST C|ARTIST D"
                 oninput="ctrlSet('event_lineup',this.value)">
        </div>
        <div style="grid-column:1/-1">
          <label>FOOTER</label>
          <input type="text" id="event-footer" placeholder="DOORS OPEN 23:00"
                 oninput="ctrlSet('event_footer',this.value)">
        </div>
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
const OW=1366,OH=768,MAP_OVERSCAN=0.25,MAP_MIN=-0.25,MAP_MAX=1.25;
let canvasW=1,canvasH=1,canvasDpr=1;
let SCALE=1,surfaces=[],sel=-1,drag=null,MODES=[],curFile='fb_map.json';
const canvas=document.getElementById('c'),ctx=canvas.getContext('2d');
const COLS=['#4488ff','#ff4466','#44ff88','#ffaa22','#cc44ff','#22ccff','#ffcc22','#ff6644'];

// ══════════════════════════════════════════════════════════════
//  TAB SWITCHER
// ══════════════════════════════════════════════════════════════
let activeTab='map';
function switchTab(t){
  if(activeTab==='map'&&t!=='map'){
    // leaving MAP tab → always restore projection to live visuals
    clearMapCursor();
    mapModeActive=false;
    fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({map_mode:false,map_cursor_x:null,map_cursor_y:null})}).catch(()=>{});
    _updateMapBtn();
  }
  activeTab=t;
  ['map','zones','ctrl','camera','media','outputs','help','term'].forEach(n=>{
    document.getElementById('tab-'+n).classList.toggle('active',t===n);
    document.getElementById('btn-'+n).classList.toggle('active',t===n);
  });
  if(t==='map'){resize();_enterMapTab();}
  if(t==='ctrl'){startCtrlPoll();}
  if(t==='zones'){fetchMedia().then(()=>zonesInit());}
  if(t==='camera'){cameraInit();}
  if(t==='media'){mediaLoad();mediaStatusPoll();}
  if(t==='outputs'){outputsLoad();}
  if(t==='help'){helpLoad();}
  if(t==='term'){setTimeout(()=>document.getElementById('term-input').focus(),50);}
}
function _enterMapTab(){
  mapModeActive=false;
  _updateMapBtn();
  fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({map_mode:false,map_cursor_x:null,map_cursor_y:null})}).catch(()=>{});
}
function _updateMapBtn(){
  const btn=document.getElementById('mapmode-btn');
  if(!btn)return;
  if(mapModeActive){
    btn.textContent='[ PREVIEW LIVE ]';
    btn.style.color='#44ff88';btn.style.borderColor='#44ff88';
  }else{
    btn.textContent='[ SHOW MAP VIEW ]';
    btn.style.color='#ff4466';btn.style.borderColor='#ff4466';
  }
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

window.onload=()=>{resize();fetchMedia();fetchModes().then(()=>fetchFiles().then(()=>load()));_enterMapTab();};
window.onresize=()=>{if(activeTab==='map')resize()};
document.addEventListener('keydown',e=>{
  if(activeTab!=='map')return;
  if(e.key==='n'||e.key==='N'){addSurf();return}
  if((e.key==='Delete'||e.key==='Backspace')&&sel>=0&&document.activeElement===document.body){delSurf();return}
  if((e.key==='+'||e.key==='=')&&sel>=0&&document.activeElement===document.body){e.preventDefault();scaleSurf(1.02);return}
  if((e.key==='-'||e.key==='_')&&sel>=0&&document.activeElement===document.body){e.preventDefault();scaleSurf(0.98);return}
  if((e.metaKey||e.ctrlKey)&&e.key==='s'){e.preventDefault();save()}
});

function resize(){
  const w=document.getElementById('wrap');
  SCALE=Math.max(0.1,Math.min((w.clientWidth-40)/OW,(w.clientHeight-60)/OH));
  canvasW=Math.max(1,Math.round(OW*SCALE));
  canvasH=Math.max(1,Math.round(OH*SCALE));
  canvasDpr=Math.max(1,window.devicePixelRatio||1);
  canvas.style.width=`${canvasW}px`;
  canvas.style.height=`${canvasH}px`;
  canvas.width=Math.max(1,Math.round(canvasW*canvasDpr));
  canvas.height=Math.max(1,Math.round(canvasH*canvasDpr));
  ctx.setTransform(canvasDpr,0,0,canvasDpr,0,0);
  ctx.imageSmoothingEnabled=true;
  if('imageSmoothingQuality' in ctx)ctx.imageSmoothingQuality='high';
  ctx.lineJoin='round';
  ctx.lineCap='round';
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
function scaleSurf(factor){
  if(sel<0)return;
  const s=surfaces[sel];
  if(!s.corners||s.corners.length<4)return;
  const cx=s.corners.reduce((a,p)=>a+p[0],0)/s.corners.length;
  const cy=s.corners.reduce((a,p)=>a+p[1],0)/s.corners.length;
  s.corners=s.corners.map(([x,y])=>[
    clampMap(cx+(x-cx)*factor),
    clampMap(cy+(y-cy)*factor)
  ]);
  draw();
  save();
}
let mapModeActive=false;
function toggleMapMode(){
  mapModeActive=!mapModeActive;
  _updateMapBtn();
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
const s2c=([nx,ny])=>[
  ((nx+MAP_OVERSCAN)/(1+MAP_OVERSCAN*2))*canvasW,
  ((ny+MAP_OVERSCAN)/(1+MAP_OVERSCAN*2))*canvasH
];
const c2s=(cx,cy)=>[
  (cx/canvasW)*(1+MAP_OVERSCAN*2)-MAP_OVERSCAN,
  (cy/canvasH)*(1+MAP_OVERSCAN*2)-MAP_OVERSCAN
];
const clampMap=v=>Math.max(MAP_MIN,Math.min(MAP_MAX,v));
function rgba(hex,a){
  const h=hex.replace('#','');
  const r=parseInt(h.slice(0,2),16),g=parseInt(h.slice(2,4),16),b=parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}
function fillQuad(pts,color){
  ctx.beginPath();
  ctx.moveTo(...pts[0]);
  pts.slice(1).forEach(p=>ctx.lineTo(...p));
  ctx.closePath();
  ctx.fillStyle=color;
  ctx.fill();
}

function draw(){
  ctx.fillStyle='#000';ctx.fillRect(0,0,canvasW,canvasH);
  ctx.strokeStyle='#0c0c0c';ctx.lineWidth=0.5;
  [.1,.2,.3,.4,.5,.6,.7,.8,.9].forEach(t=>{
    const [gx0,gy0]=s2c([t,0]),[gx1,gy1]=s2c([t,1]),[hx0,hy0]=s2c([0,t]),[hx1,hy1]=s2c([1,t]);
    ctx.beginPath();ctx.moveTo(gx0,gy0);ctx.lineTo(gx1,gy1);ctx.stroke();
    ctx.beginPath();ctx.moveTo(hx0,hy0);ctx.lineTo(hx1,hy1);ctx.stroke();
  });
  ctx.strokeStyle='#181818';ctx.lineWidth=1;
  [1/3,2/3].forEach(t=>{
    const [gx0,gy0]=s2c([t,0]),[gx1,gy1]=s2c([t,1]),[hx0,hy0]=s2c([0,t]),[hx1,hy1]=s2c([1,t]);
    ctx.beginPath();ctx.moveTo(gx0,gy0);ctx.lineTo(gx1,gy1);ctx.stroke();
    ctx.beginPath();ctx.moveTo(hx0,hy0);ctx.lineTo(hx1,hy1);ctx.stroke();
  });
  const [bx0,by0]=s2c([0,0]),[bx1,by1]=s2c([1,1]);
  ctx.strokeStyle='#333';ctx.lineWidth=1;
  ctx.strokeRect(bx0,by0,bx1-bx0,by1-by0);

  surfaces.forEach((s,i)=>{
    if(!s.corners||s.corners.length<4)return;
    const pts=s.corners.map(s2c);
    const col=COLS[i%COLS.length];
    const isSel=i===sel;
    const off=s.enabled===false;
    fillQuad(pts,rgba(col,off?0.55:1));
    ctx.beginPath();ctx.moveTo(...pts[0]);pts.slice(1).forEach(p=>ctx.lineTo(...p));ctx.closePath();
    ctx.strokeStyle=rgba(col,off?0.35:isSel?1:0.85);ctx.lineWidth=isSel?1.5:1;ctx.stroke();
    const cx=pts.reduce((a,p)=>a+p[0],0)/4,cy=pts.reduce((a,p)=>a+p[1],0)/4;
    ctx.fillStyle=rgba(col,off?0.45:1);ctx.font=`${isSel?12:10}px monospace`;ctx.textAlign='center';
    ctx.fillText(s.id||`S${i+1}`,cx,cy);
    const ml=s.mode===null?'∅':(MODES[s.mode]||`${s.mode}`);
    ctx.font='8px monospace';ctx.fillStyle='#33333399';ctx.fillText(ml,cx,cy+12);
    pts.forEach(([px,py],ci)=>{
      ctx.beginPath();ctx.arc(px,py,isSel?7:4,0,Math.PI*2);
      ctx.fillStyle=isSel?col:rgba(col,0.75);ctx.fill();
      if(isSel){ctx.strokeStyle='#ffffff33';ctx.lineWidth=1;ctx.stroke();
        ctx.fillStyle='#fff';ctx.font='7px monospace';ctx.textAlign='center';ctx.fillText(ci+1,px,py+2.5)}
    });
  });
  ctx.strokeStyle='#ffffff06';ctx.lineWidth=1;
  const [vx0,vy0]=s2c([0.5,0]),[vx1,vy1]=s2c([0.5,1]),[hx0,hy0]=s2c([0,0.5]),[hx1,hy1]=s2c([1,0.5]);
  ctx.beginPath();ctx.moveTo(vx0,vy0);ctx.lineTo(vx1,vy1);ctx.stroke();
  ctx.beginPath();ctx.moveTo(hx0,hy0);ctx.lineTo(hx1,hy1);ctx.stroke();
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
  sendMapCursor(clampMap(nx),clampMap(ny));
  if(!drag)return;
  surfaces[drag.s].corners[drag.c]=[clampMap(nx),clampMap(ny)];
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

  syncTextInput('flash-input',c.flash_text??'SIGNAL');
  syncTextInput('event-title',c.event_title??'');
  syncTextInput('event-kicker',c.event_kicker??'');
  syncTextInput('event-when',c.event_when??'');
  syncTextInput('event-where',c.event_where??'');
  syncTextInput('event-lineup',c.event_lineup??'');
  syncTextInput('event-footer',c.event_footer??'');
}

function syncTextInput(id,value){
  const el=document.getElementById(id);
  if(el&&document.activeElement!==el)el.value=value??'';
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
  const txt=document.getElementById('flash-input').value||'SIGNAL';
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

// ══════════════════════════════════════════════════════════════
//  CAMERA TAB
// ══════════════════════════════════════════════════════════════
let _cameraReady=false;

function cameraInit(){
  const input=document.getElementById('camera-url');
  const saved=localStorage.getItem('ii.camera.url')||'';
  if(input&&!input.value)input.value=saved;
  if(input&&!input.value&&location.hostname){
    input.value=`http://${location.hostname}:81/stream`;
  }
  setTimeout(()=>input&&input.focus(),50);
}

function cameraKey(e){
  if(e.key==='Enter'){
    e.preventDefault();
    cameraConnect();
  }
}

function cameraSetStatus(text,kind){
  const st=document.getElementById('camera-status');
  st.textContent=text;
  st.classList.toggle('ok',kind==='ok');
  st.classList.toggle('warn',kind==='warn');
}

function cameraSetUrl(url){
  document.getElementById('camera-url').value=url;
  cameraConnect();
}

function cameraUsePath(path){
  const input=document.getElementById('camera-url');
  const cur=(input.value||'').trim();
  let base='';
  try{
    const u=new URL(cur||`http://${location.hostname}`);
    base=`${u.protocol}//${u.hostname}`;
  }catch(e){
    base=`http://${location.hostname}`;
  }
  if(path.startsWith(':')){
    input.value=base+path;
  }else{
    input.value=base+path;
  }
  cameraConnect();
}

function cameraConnect(){
  const input=document.getElementById('camera-url');
  const img=document.getElementById('camera-stream');
  const empty=document.getElementById('camera-empty');
  let url=(input.value||'').trim();
  if(!url){
    cameraSetStatus('missing url','warn');
    return;
  }
  if(!/^https?:\/\//i.test(url))url='http://'+url;
  input.value=url;
  localStorage.setItem('ii.camera.url',url);
  _cameraReady=false;
  cameraSetStatus('connecting','');
  empty.style.display='none';
  img.style.display='block';
  img.src=url+(url.includes('?')?'&':'?')+'t='+Date.now();
  setTimeout(()=>{
    if(!_cameraReady&&activeTab==='camera')cameraSetStatus('waiting for frames','warn');
  },2500);
}

function cameraStop(){
  const img=document.getElementById('camera-stream');
  img.removeAttribute('src');
  img.style.display='none';
  document.getElementById('camera-empty').style.display='block';
  cameraSetStatus('stopped','');
}

function cameraLoaded(){
  _cameraReady=true;
  cameraSetStatus('live','ok');
}

function cameraError(){
  _cameraReady=false;
  document.getElementById('camera-stream').style.display='none';
  document.getElementById('camera-empty').style.display='block';
  cameraSetStatus('stream error','warn');
}
</script>
<!-- ════════════════════════════════════════
     OUTPUTS TAB
     ════════════════════════════════════════ -->
<div id="tab-outputs">
  <!-- top bar: status + apply -->
  <div id="out-topbar">
    <span id="out-x-badge">X11 ●</span>
    <button class="cbtn" onclick="restartXLayout()" style="width:auto;padding:3px 10px;margin-top:0;font-size:9px;letter-spacing:1px">RESTART X</button>
    <span id="out-strip-status"></span>
    <div id="out-topbar-right">
      <span id="out-layout-status"></span>
      <button id="out-apply-btn" onclick="applyOutputPlan()">APPLY TO STAGE</button>
    </div>
  </div>
  <!-- body -->
  <div id="out-body">
    <!-- sidebar -->
    <div id="out-sidebar">
      <!-- project -->
      <div class="out-sb-section">
        <div class="out-sb-label">PROJECT</div>
        <input id="proj-name" class="out-proj-input" type="text" placeholder="project name…" autocomplete="off">
        <div class="out-proj-row">
          <select id="proj-load-sel" class="out-proj-sel"><option value="">load…</option></select>
          <button class="out-proj-btn" onclick="loadProject()">LOAD</button>
          <button class="out-proj-btn" onclick="saveProject()">SAVE</button>
        </div>
        <div id="proj-status"></div>
      </div>
      <!-- displays -->
      <div class="out-sb-section">
        <div class="out-sb-label">DISPLAYS <button onclick="autoAssignDisplays()">AUTO</button></div>
        <div class="out-disp-row">
          <span class="out-disp-role">CTRL</span>
          <select id="out-ctrl-sel" class="out-disp-sel" onchange="selCtrl=this.value;checkSameDisp()"></select>
        </div>
        <div class="out-disp-row">
          <span class="out-disp-role">VIS</span>
          <select id="out-vis-sel" class="out-disp-sel" onchange="selVis=this.value;checkSameDisp()"></select>
        </div>
      </div>
      <!-- mapping -->
      <div class="out-sb-section">
        <div class="out-sb-label">MAPPING</div>
        <div id="out-map-list"></div>
      </div>
    </div>
    <!-- main: surface layer cards -->
    <div id="out-main">
      <div id="out-main-hdr">
        <span id="out-main-hdr-title">SURFACES</span>
      </div>
      <div id="out-surfaces"><div id="out-empty">select a mapping</div></div>
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

<!-- ════════════════════════════════════════
     TERM TAB
     ════════════════════════════════════════ -->
<div id="tab-term">
  <div id="term-quickbar">
    <button onclick="termRun('ii status')">ii status</button>
    <button onclick="termRun('ii logs vis')">logs vis</button>
    <button onclick="termRun('ii logs ctrl')">logs ctrl</button>
    <button onclick="termRun('ii logs web')">logs web</button>
    <button onclick="termRun('git log --oneline -8')">git log</button>
    <button onclick="termRun('git status')">git status</button>
    <button onclick="termRun('df -h /')">df</button>
    <button onclick="termRun('free -h')">mem</button>
    <button onclick="termRun('uptime')">uptime</button>
    <button onclick="termRun('ls media/')">ls media</button>
    <button onclick="termClear()">CLEAR</button>
  </div>
  <div id="term-output"></div>
  <div id="term-input-row">
    <span id="term-ps1">dob@ii:~$ </span>
    <input id="term-input" type="text" autocomplete="off" spellcheck="false"
           placeholder="enter command…" onkeydown="termKey(event)">
    <span id="term-cwd"></span>
  </div>
</div>

<script>
let outputsTimer=null, outputApplyBusy=false;
let selCtrl='', selVis='', selMapping=0, _outInited=false;
let _lastOutState=null, _currentMappings=[], _currentMappingFile='';
let _outModes=[];

async function outputsLoad(){
  if(!_outModes.length){
    _outModes=await fetch('/api/modes').then(r=>r.json()).catch(()=>[]);
  }
  await Promise.all([refreshOutputs(), fetchMedia(), _refreshProjects()]);
  clearInterval(outputsTimer);
  outputsTimer=setInterval(()=>{if(activeTab==='outputs')refreshOutputs()},5000);
}

async function refreshOutputs(){
  try{
    const d=await fetch('/api/output-setup').then(r=>r.json());
    _lastOutState=d;
    _renderOutputs(d);
  }catch(e){
    const b=document.getElementById('out-x-badge');
    if(b){b.textContent='X11 ✕';b.className='warn';}
  }
}

function _renderOutputs(d){
  const badge=document.getElementById('out-x-badge');
  if(badge){badge.textContent=d.x_running?'X11 ●':'X11 ✕';badge.className=d.x_running?'ok':'warn';}
  const displays=(d.displays||[]).filter(x=>x.connected);
  _currentMappings=d.mappings||[];
  if(!_outInited){
    _outInited=true;
    selCtrl=d.assign?.ctrl||d.suggested_ctrl||displays[0]?.name||'';
    selVis=d.assign?.vis||d.suggested_vis||displays[1]?.name||displays[0]?.name||'';
    selMapping=d.active_mapping??0;
  }
  _buildDispSel('out-ctrl-sel',displays,selCtrl,n=>{selCtrl=n;checkSameDisp();});
  _buildDispSel('out-vis-sel',displays,selVis,n=>{selVis=n;checkSameDisp();});
  _currentMappingFile=d.active_mapping_file||'';
  _buildMapList(_currentMappings,selMapping);
  _buildSurfaces(d.surfaces||[],_currentMappingFile);
  const mname=_currentMappings[selMapping]?.name||_currentMappingFile||'—';
  const el=document.getElementById('out-main-hdr-title');
  if(el)el.textContent='SOURCES  ·  '+mname;
  checkSameDisp();
}

function _buildDispSel(id,displays,selected,onChange){
  const sel=document.getElementById(id);
  if(!sel)return;
  const cur=sel.value||selected;
  sel.innerHTML='';
  if(!displays.length){
    const o=document.createElement('option');o.textContent='no display';sel.appendChild(o);return;
  }
  displays.forEach(d=>{
    const o=document.createElement('option');
    o.value=d.name;o.textContent=d.name+'  '+(d.resolution||'');o.selected=(d.name===cur);
    sel.appendChild(o);
  });
  if(cur&&!sel.value){sel.value=displays[0].name;}
  sel.onchange=()=>onChange(sel.value);
}

function autoAssignDisplays(){
  if(!_lastOutState)return;
  const sc=_lastOutState.suggested_ctrl,sv=_lastOutState.suggested_vis;
  if(sc){selCtrl=sc;const s=document.getElementById('out-ctrl-sel');if(s)s.value=sc;}
  if(sv){selVis=sv;const s=document.getElementById('out-vis-sel');if(s)s.value=sv;}
  checkSameDisp();
}

function checkSameDisp(){
  const s=document.getElementById('out-layout-status');
  if(!s)return;
  if(selCtrl&&selCtrl===selVis){s.textContent='⚠ same display';s.className='out-warn';}
  else{s.textContent='';s.className='';}
}

function _buildMapList(mappings,activeIdx){
  const box=document.getElementById('out-map-list');
  if(!box)return;
  box.innerHTML='';
  if(!mappings.length){box.innerHTML='<div style="color:#252525;font-size:10px;padding:4px">no mappings</div>';return;}
  mappings.forEach((m,i)=>{
    const row=document.createElement('div');
    row.className='out-map-item'+(i===activeIdx?' active':'');
    row.innerHTML='<span class="out-map-item-name">'+(m.name||m.file)+'</span><span class="out-map-item-n">'+(m.surfaces||0)+'</span>';
    row.onclick=async()=>{
      selMapping=i;_currentMappingFile=m.file;
      box.querySelectorAll('.out-map-item').forEach(r=>r.classList.remove('active'));
      row.classList.add('active');
      await fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mapping:i})}).catch(()=>{});
      await refreshOutputs();
    };
    box.appendChild(row);
  });
}

function _buildSurfaces(surfaces, mappingFile){
  const grid=document.getElementById('out-surfaces');
  if(!grid)return;
  if(!surfaces||!surfaces.length){
    grid.innerHTML='<div id="out-empty">select a mapping</div>';return;
  }
  grid.innerHTML='';
  surfaces.forEach(s=>{
    const id=s.id||'?';
    const curMode=(s.mode!=null)?parseInt(s.mode):null;
    const curVideo=s.video||'';
    const isVid=!!curVideo;

    const card=document.createElement('div');
    card.className='lyr-card';
    card.dataset.id=id;

    const head=document.createElement('div');
    head.className='lyr-head';
    const idEl=document.createElement('span');
    idEl.className='lyr-id';idEl.textContent=id;
    const tog=document.createElement('div');
    tog.className='lyr-toggle';
    const modeTog=document.createElement('button');
    modeTog.className='lyr-tog-btn'+(!isVid?' on':'');
    modeTog.textContent='MODE';
    const vidTog=document.createElement('button');
    vidTog.className='lyr-tog-btn'+(isVid?' on':'');
    vidTog.textContent='VIDEO';
    tog.append(modeTog,vidTog);
    head.append(idEl,tog);
    card.appendChild(head);

    const srcDisp=document.createElement('div');
    srcDisp.className='lyr-src-display';
    const srcName=document.createElement('div');
    srcName.className='lyr-src-name';
    const srcSub=document.createElement('div');
    srcSub.className='lyr-src-sub';
    if(isVid){
      srcName.textContent=curVideo.split('/').pop()||'—';
      srcSub.textContent='video';
    } else if(curMode!=null&&_outModes[curMode]){
      srcName.textContent=_outModes[curMode];
      srcSub.textContent='mode '+curMode;
    } else {
      srcName.textContent='visuals';
      srcSub.textContent='default';
    }
    srcDisp.append(srcName,srcSub);
    card.appendChild(srcDisp);

    const picker=document.createElement('div');
    picker.className='lyr-picker';

    const modeGrid=document.createElement('div');
    modeGrid.className='lyr-mode-grid';
    modeGrid.style.display=isVid?'none':'';
    _outModes.forEach((m,i)=>{
      const b=document.createElement('button');
      b.className='lyr-mg-btn'+(curMode===i?' on':'');
      b.textContent=m;b.dataset.idx=i;
      b.onclick=()=>{
        setSurfaceSource(mappingFile,id,'mode',i,'');
        srcName.textContent=m;srcSub.textContent='mode '+i;
        modeGrid.querySelectorAll('.lyr-mg-btn').forEach(x=>x.classList.remove('on'));
        b.classList.add('on');
      };
      modeGrid.appendChild(b);
    });
    picker.appendChild(modeGrid);

    const vidList=document.createElement('div');
    vidList.className='lyr-vid-list';
    vidList.style.display=isVid?'':'none';
    const vids=(MEDIA_FILES||[]).filter(_isVideoFile);
    const noneItem=document.createElement('button');
    noneItem.className='lyr-vid-item'+(!curVideo?' on':'');
    noneItem.textContent='— default visuals —';
    noneItem.onclick=()=>{
      setSurfaceSource(mappingFile,id,'mode',curMode??0,'');
      srcName.textContent=curMode!=null&&_outModes[curMode]?_outModes[curMode]:'visuals';
      srcSub.textContent=curMode!=null?'mode '+curMode:'default';
      vidList.querySelectorAll('.lyr-vid-item').forEach(x=>x.classList.remove('on'));
      noneItem.classList.add('on');
    };
    vidList.appendChild(noneItem);
    if(!vids.length){
      const e=document.createElement('div');e.className='lyr-vid-empty';e.textContent='no video files in media/';vidList.appendChild(e);
    }
    vids.forEach(f=>{
      const item=document.createElement('button');
      item.className='lyr-vid-item'+(f===curVideo?' on':'');
      item.textContent=f;
      item.onclick=()=>{
        setSurfaceSource(mappingFile,id,'video',null,f);
        srcName.textContent=f.split('/').pop();srcSub.textContent='video';
        vidList.querySelectorAll('.lyr-vid-item').forEach(x=>x.classList.remove('on'));
        item.classList.add('on');
      };
      vidList.appendChild(item);
    });
    picker.appendChild(vidList);
    card.appendChild(picker);

    modeTog.onclick=()=>{
      modeTog.classList.add('on');vidTog.classList.remove('on');
      modeGrid.style.display='';vidList.style.display='none';
      const ab=modeGrid.querySelector('.lyr-mg-btn.on');
      const mi=ab?parseInt(ab.dataset.idx):0;
      setSurfaceSource(mappingFile,id,'mode',mi,'');
      if(_outModes[mi]){srcName.textContent=_outModes[mi];srcSub.textContent='mode '+mi;}
    };
    vidTog.onclick=()=>{
      vidTog.classList.add('on');modeTog.classList.remove('on');
      vidList.style.display='';modeGrid.style.display='none';
      const ab=vidList.querySelector('.lyr-vid-item.on');
      const v=(ab&&ab.textContent!=='— default visuals —')?ab.textContent:'';
      if(v){setSurfaceSource(mappingFile,id,'video',null,v);srcName.textContent=v;srcSub.textContent='video';}
    };

    grid.appendChild(card);
  });
}

async function setSurfaceSource(file,id,type,mode,video){
  try{
    await fetch('/api/surface-source',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({file,id,type,mode,video})});
  }catch(e){}
}

async function applyOutputPlan(){
  if(outputApplyBusy)return;
  const ctrlSel=document.getElementById('out-ctrl-sel');
  const visSel=document.getElementById('out-vis-sel');
  if(ctrlSel)selCtrl=ctrlSel.value;
  if(visSel)selVis=visSel.value;
  const st=document.getElementById('out-layout-status');
  if(!selCtrl||!selVis){if(st){st.textContent='select displays first';st.className='';}return;}
  if(selCtrl===selVis&&!confirm('Same display for both — apply anyway?'))return;
  outputApplyBusy=true;
  if(st){st.textContent='applying…';st.className='';}
  try{
    const r=await fetch('/api/output-setup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ctrl:selCtrl,vis:selVis,mapping:selMapping,blackout:true})});
    const d=await r.json();
    if(st)st.textContent=d.msg||'applied ✓';
  }catch(e){
    if(st)st.textContent='error: '+e;
  }finally{outputApplyBusy=false;}
  setTimeout(refreshOutputs,800);
}

async function restartXLayout(){
  if(!confirm('Restart the X show layout? The display may blink.'))return;
  try{
    const r=await fetch('/api/display-layout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layout:'restart-x'})});
    const d=await r.json();
    const st=document.getElementById('out-layout-status');
    if(st){st.textContent=d.msg||'restart requested';setTimeout(()=>{st.textContent='';},4000);}
  }catch(e){}
}

// ── PROJECT SAVE / LOAD ───────────────────────────────────────────────────────
async function saveProject(){
  const name=document.getElementById('proj-name').value.trim();
  if(!name){_projStatus('enter a name');return;}
  const sources={};
  document.querySelectorAll('.lyr-card').forEach(card=>{
    const id=card.dataset.id;
    const isVid=card.querySelector('.lyr-tog-btn:last-child').classList.contains('on');
    if(isVid){
      const ab=card.querySelector('.lyr-vid-item.on');
      const v=(ab&&ab.textContent!=='— default visuals —')?ab.textContent:'';
      sources[id]={type:'video',video:v};
    } else {
      const ab=card.querySelector('.lyr-mg-btn.on');
      sources[id]={type:'mode',mode:ab?parseInt(ab.dataset.idx):null};
    }
  });
  try{
    const r=await fetch('/api/project',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,display_ctrl:selCtrl,display_vis:selVis,mapping:_currentMappingFile,sources})});
    const d=await r.json();
    _projStatus(d.msg||'saved');
    await _refreshProjects(name);
  }catch(e){_projStatus('error: '+e);}
}

async function loadProject(){
  const name=document.getElementById('proj-load-sel').value;
  if(!name){_projStatus('select a project');return;}
  try{
    const proj=await fetch('/api/project?name='+encodeURIComponent(name)).then(r=>r.json());
    if(!proj||proj.error){_projStatus('not found');return;}
    if(proj.display_ctrl){selCtrl=proj.display_ctrl;const s=document.getElementById('out-ctrl-sel');if(s)s.value=selCtrl;}
    if(proj.display_vis){selVis=proj.display_vis;const s=document.getElementById('out-vis-sel');if(s)s.value=selVis;}
    if(proj.mapping){
      const idx=_currentMappings.findIndex(m=>m.file===proj.mapping);
      if(idx>=0){
        selMapping=idx;_currentMappingFile=proj.mapping;
        await fetch('/api/ctrl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mapping:idx})}).catch(()=>{});
      }
    }
    if(proj.sources&&proj.mapping){
      for(const [id,src] of Object.entries(proj.sources)){
        await setSurfaceSource(proj.mapping,id,src.type,src.mode??null,src.video??'');
      }
    }
    document.getElementById('proj-name').value=proj.name||name;
    _outInited=false;_projStatus('loaded: '+(proj.name||name));
    await refreshOutputs();
  }catch(e){_projStatus('error: '+e);}
}

async function _refreshProjects(selectName){
  try{
    const names=await fetch('/api/projects').then(r=>r.json());
    const sel=document.getElementById('proj-load-sel');
    const cur=selectName||sel.value;
    sel.innerHTML='<option value="">load…</option>';
    names.forEach(n=>{
      const o=document.createElement('option');o.value=n;o.textContent=n;o.selected=(n===cur);
      sel.appendChild(o);
    });
  }catch(e){}
}

function _projStatus(msg){
  const el=document.getElementById('proj-status');
  if(el){el.textContent=msg;setTimeout(()=>{if(el.textContent===msg)el.textContent='';},3500);}
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

// ── TERM TAB ──────────────────────────────────────────────────────────────────
let _termHistory=[], _termHistIdx=-1, _termBusy=false;

function termClear(){
  document.getElementById('term-output').innerHTML='';
}

function termKey(e){
  if(e.key==='Enter'){
    e.preventDefault();
    const inp=document.getElementById('term-input');
    const cmd=inp.value.trim();
    if(!cmd)return;
    inp.value='';
    _termHistory.unshift(cmd);
    if(_termHistory.length>100)_termHistory.pop();
    _termHistIdx=-1;
    termRun(cmd);
  } else if(e.key==='ArrowUp'){
    e.preventDefault();
    _termHistIdx=Math.min(_termHistIdx+1,_termHistory.length-1);
    if(_termHistIdx>=0)document.getElementById('term-input').value=_termHistory[_termHistIdx];
  } else if(e.key==='ArrowDown'){
    e.preventDefault();
    _termHistIdx=Math.max(_termHistIdx-1,-1);
    document.getElementById('term-input').value=_termHistIdx>=0?_termHistory[_termHistIdx]:'';
  }
}

async function termRun(cmd){
  if(_termBusy)return;
  _termBusy=true;
  const out=document.getElementById('term-output');
  const row=document.createElement('div');
  row.innerHTML=`<span class="t-prompt">dob@ii:~$ </span><span class="t-cmd">${_esc(cmd)}</span>`;
  out.appendChild(row);
  out.scrollTop=out.scrollHeight;
  try{
    const r=await fetch('/api/terminal',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cmd,timeout:15})});
    const d=await r.json();
    if(d.output){
      const o=document.createElement('div');
      o.className='t-out';
      o.textContent=d.output;
      out.appendChild(o);
    }
    if(d.returncode!==0){
      const rc=document.createElement('div');
      rc.className='t-rc';
      rc.textContent=`[exit ${d.returncode}]`;
      out.appendChild(rc);
    }
  }catch(e){
    const er=document.createElement('div');
    er.className='t-err';
    er.textContent='error: '+e;
    out.appendChild(er);
  }
  _termBusy=false;
  out.scrollTop=out.scrollHeight;
  document.getElementById('term-input').focus();
}

function _esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
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


PROJECTS_DIR = os.path.join(BASE, 'projects')


def _list_projects():
    try:
        os.makedirs(PROJECTS_DIR, exist_ok=True)
        return sorted(f[:-5] for f in os.listdir(PROJECTS_DIR) if f.endswith('.json'))
    except Exception:
        return []


def _save_project(body):
    import re as _re
    name = str(body.get('name', '')).strip()
    if not name:
        return 'name required'
    if not _re.match(r'^[\w\- ]{1,50}$', name):
        return 'invalid project name (alphanumeric, dash, space, max 50)'
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    proj = {
        'name': name,
        'display_ctrl': str(body.get('display_ctrl', '') or ''),
        'display_vis': str(body.get('display_vis', '') or ''),
        'mapping': str(body.get('mapping', '') or ''),
        'sources': body.get('sources') or {},
    }
    fname = _re.sub(r'[^\w\-]', '_', name) + '.json'
    save_json_atomic(os.path.join(PROJECTS_DIR, fname), proj)
    return f'saved: {name}'


def _load_project(name):
    import re as _re
    fname = _re.sub(r'[^\w\-]', '_', name) + '.json'
    path = os.path.join(PROJECTS_DIR, fname)
    if os.path.exists(path):
        return load_json(path, {})
    # fallback: scan by name field
    try:
        for f in os.listdir(PROJECTS_DIR):
            if f.endswith('.json'):
                p = load_json(os.path.join(PROJECTS_DIR, f), {})
                if p.get('name') == name:
                    return p
    except Exception:
        pass
    return {'error': 'not found'}


def _set_surface_source(body):
    mapping_file = os.path.basename(str(body.get('file', '') or ''))
    surf_id = str(body.get('id', '') or '').strip()
    source_type = str(body.get('type', 'mode')).strip()
    mode_val = body.get('mode')
    video_val = str(body.get('video', '') or '').strip()
    if not mapping_file or not surf_id:
        return 'missing file or id'
    path = os.path.join(MAPPINGS_DIR, mapping_file)
    if not os.path.exists(path):
        return f'mapping not found: {mapping_file}'
    data = load_json(path, {})
    key = 'surfaces' if 'surfaces' in data else 'zones'
    surfaces = data.get(key) or []
    updated = False
    for s in surfaces:
        if s.get('id') == surf_id:
            if source_type == 'video':
                s['video'] = video_val
                s['mode'] = None
            else:
                s['mode'] = int(mode_val) if mode_val is not None else None
                s['video'] = ''
            updated = True
            break
    if not updated:
        return f'surface not found: {surf_id}'
    data[key] = surfaces
    save_json_atomic(path, data)
    return 'ok'


def _terminal_run(body):
    import re, time
    cmd = str(body.get('cmd', '')).strip()
    if not cmd:
        return {'output': '', 'returncode': 0}
    timeout = min(int(body.get('timeout', 15)), 30)
    env = {**os.environ, 'TERM': 'xterm-256color', 'HOME': '/home/dob',
           'PATH': '/home/dob/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'}
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=BASE, env=env
        )
        raw = (proc.stdout or '') + (proc.stderr or '')
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        raw = f'[timeout after {timeout}s]'
        rc = -1
    except Exception as exc:
        raw = f'[error: {exc}]'
        rc = -1
    # strip ANSI escape codes
    ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    output = ansi_escape.sub('', raw).rstrip()
    # truncate very long output
    lines = output.splitlines()
    if len(lines) > 200:
        output = '\n'.join(['[... truncated, showing last 200 lines ...]'] + lines[-200:])
    return {'output': output, 'returncode': rc, 'elapsed': round(time.monotonic()-t0, 2)}


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
    surfaces = []
    if active_mapping_file:
        mdata = load_json(os.path.join(MAPPINGS_DIR, active_mapping_file), {})
        surfaces = mdata.get('surfaces') or mdata.get('zones') or []
    return {
        'displays': displays,
        'layout': _detect_layout(displays),
        'assign': assign,
        'suggested_ctrl': suggested_ctrl,
        'suggested_vis': suggested_vis,
      'mappings': mappings,
      'active_mapping': active_mapping,
      'active_mapping_file': active_mapping_file,
      'surfaces': surfaces,
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
        elif p.path == '/api/projects':
            self._json(_list_projects())
        elif p.path == '/api/project':
            name = qs.get('name', [''])[0]
            self._json(_load_project(name) if name else {'error': 'name required'})
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
        elif p.path == '/api/terminal':
            self._json(_terminal_run(body))
        elif p.path == '/api/surface-source':
            msg = _set_surface_source(body)
            self._json({'ok': msg == 'ok', 'msg': msg})
        elif p.path == '/api/project':
            msg = _save_project(body)
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
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    print(f'open on your laptop:  http://192.168.88.136:{PORT}')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
