"""Modo Cosecha de la plataforma (diseno "Sala de control"): estado de lotes, ficha del lote,
filtros y secciones (Limpieza, Categorizacion, Brix, Peso, Descarte) con letras grandes."""
import base64
import math
import os
from html import escape

import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import cajas as cj
import cosecha_calc as cc
import directorio as dr

# ---------------------------------------------------------------- paleta (modo oscuro)
BG, PANEL, PANEL2, BORDE = "#120d0f", "#1c1517", "#241b1e", "#2e2427"
TXT, TXT2, TXT3 = "#f4ece8", "#a89c97", "#d8ccc6"
ROJO, ROJO_V, AMBAR, VERDE, MORADO = "#C8102E", "#ff5a5f", "#ffb547", "#3ecf7a", "#c48bff"
NARANJA, GRIS = "#ff8a2a", "#6b6460"
GC = {"Condición": ROJO_V, "Calidad": AMBAR, "Plagas": MORADO}          # grupos de defectos
ESTADO_COLOR = {"En cosecha": NARANJA, "Terminada": VERDE, "Revisar": MORADO, "Sin cosecha": GRIS}
NOMBRE_TABLA = {"limpieza": "Limpieza (Cosecha optimizado)", "categoria": "Categorización", "peso": "Peso de racimos",
                "desc_bayas": "Descarte de bayas", "desc_racimos": "Descarte de racimos", "brix": "Brix",
                "jabas": "Peso de jabas", "temp": "Temperaturas", "traza": "Trazabilidad jabas amarillas"}
MIN_REGISTROS = 15        # un lote con menos registros que esto (en todas las tablas) se marca "Revisar"
ESTADOS_XLSX = os.path.join("Maestro", "estado_lotes.xlsx")
SECCIONES = ["Limpieza", "Categorización", "Brix", "Pesos", "Descarte", "Temperaturas", "Tiempos"]
PERIODOS = ["Toda la cosecha", "Últimos 7 días", "Último día"]
DB = os.path.join("datos", "pedregal.duckdb")
LOGO = os.path.join("Maestro", "logo_pedregal.png")
FUENTE = "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif"
_CTX = {}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..800&display=swap');
:root{--bg:#120d0f;--panel:#1c1517;--panel2:#241b1e;--borde:#2e2427;--txt:#f4ece8;--txt2:#a89c97;--txt3:#d8ccc6;--hi:#fff;
      --rojo:#C8102E;--rojov:#ff5a5f;--ambar:#ffb547;--verde:#3ecf7a;--morado:#c48bff;--naranja:#ff8a2a;}
.stApp{background:var(--bg);}
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp button p, .stApp div[data-testid="stMarkdownContainer"]{
  font-family:Inter,"Segoe UI",-apple-system,"Helvetica Neue",Arial,sans-serif !important;}
.block-container{max-width:1560px;}
/* etiquetas de los filtros mas visibles */
.stApp [data-testid="stWidgetLabel"] p{font-size:.78rem !important; font-weight:600; letter-spacing:.08em;
  text-transform:uppercase; color:var(--txt2) !important;}
.stApp [data-testid="stButtonGroup"] button p{font-size:1rem !important; font-weight:600;}
/* ---------- encabezado ---------- */
.pd-head{display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:18px; color:#fff; border-radius:16px;
  padding:16px 28px; margin:0 0 18px; background:linear-gradient(100deg,#c8102e 0%,#a3112a 45%,#5e0d18 100%);
  box-shadow:0 8px 24px rgba(200,16,46,.22);}
.pd-head .mk{display:flex; align-items:center; gap:12px;}
.pd-head .wm{font:700 2rem/1 Georgia,serif; color:#fff;} .pd-head .tg{font:italic 600 .8rem Georgia,serif; color:#fff; text-align:right;}
.pd-head .ttl{text-align:center; min-width:0;}
.pd-head h1{margin:0; padding:0; color:#fff !important; font-size:clamp(1.2rem,2.4vw,1.9rem); font-weight:800; letter-spacing:.04em; text-transform:uppercase;}
.pd-head .sub{font-size:.9rem; color:#fff; opacity:.9; margin-top:4px;}
.pd-head .der{text-align:right; color:#fff;} .pd-head .der span{display:block; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; opacity:.85;}
.pd-head .der b{display:block; font-size:1.35rem; color:#fff;}
@media (max-width:760px){.pd-head{grid-template-columns:1fr; text-align:center;} .pd-head .mk{justify-content:center;} .pd-head .der{text-align:center;}}
/* ---------- tarjetas de KPI ---------- */
.pd-kpis{display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin-bottom:14px;}
.pd-kpi{background:var(--panel); border:1px solid var(--borde); border-radius:14px; padding:16px 18px;}
.pd-kpi .l, .lbl{font-size:.74rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:var(--txt2);}
.pd-kpi .v{font-size:2.5rem; font-weight:800; line-height:1.1; color:var(--txt); font-variant-numeric:tabular-nums; letter-spacing:-.02em;}
.pd-kpi .v.txt{font-size:1.45rem; line-height:1.3; padding:6px 0 2px; letter-spacing:0;}
.pd-kpi .s{font-size:.85rem; color:var(--txt3);}
/* ---------- ficha del lote ---------- */
.hero{display:grid; grid-template-columns:minmax(0,1fr) 380px; background:var(--panel); border:1px solid var(--borde);
      border-radius:18px; overflow:hidden; margin-bottom:6px;}
@media (max-width: 1000px){.hero{grid-template-columns:1fr;}}
.hl{padding:24px 30px 26px; background:radial-gradient(80% 130% at 0% 0%, rgba(200,16,46,.50), transparent 62%);}
.eyebrow{font-size:.8rem; font-weight:700; letter-spacing:.32em; color:#ff8a8f; text-transform:uppercase;}
.n{font-size:clamp(4.2rem, 8.5vw, 8.4rem); font-weight:800; line-height:.92; letter-spacing:-.05em; color:var(--hi); white-space:nowrap;}
.chips{display:flex; gap:8px; flex-wrap:wrap; margin:14px 0 20px;}
.chip2{padding:7px 16px; border-radius:99px; font-size:1rem; font-weight:700;}
.vivo i{display:inline-block; width:10px; height:10px; border-radius:50%; background:currentColor; margin-right:7px;
        vertical-align:0; animation:latido 1.6s infinite;}
@keyframes latido{0%{box-shadow:0 0 0 0 rgba(255,181,71,.7)} 70%{box-shadow:0 0 0 10px rgba(255,181,71,0)} 100%{box-shadow:0 0 0 0 rgba(255,181,71,0)}}
@media (prefers-reduced-motion: reduce){.vivo i{animation:none;}}
.sts{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:1px; background:var(--borde); border:1px solid var(--borde);
     border-radius:12px; overflow:hidden;}
@media (max-width: 700px){.sts{grid-template-columns:repeat(2,minmax(0,1fr));}}
.st1{background:var(--panel); padding:14px 16px;}
.st1 b{display:block; font-size:2.2rem; font-weight:800; line-height:1.05; color:var(--hi); letter-spacing:-.02em; font-variant-numeric:tabular-nums;}
.st1 span{font-size:.74rem; font-weight:600; color:var(--txt2); text-transform:uppercase; letter-spacing:.08em;}
.st1.pend b{color:#5a5250;}
.pl{background:#171113; border-left:1px solid var(--borde); display:flex; flex-direction:column; align-items:center;
    justify-content:center; gap:10px; padding:16px;}
.pl svg path{transition:opacity .15s;} .pl svg path:hover{opacity:.8;}
.ley{display:flex; gap:14px; flex-wrap:wrap; justify-content:center; font-size:.8rem; color:var(--txt2);}
.ley i{display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:5px; vertical-align:-1px;}
/* ---------- bandas y tarjetas de seccion ---------- */
.pd-band{display:flex; align-items:center; gap:10px; color:var(--txt); font-size:1.05rem; font-weight:800; letter-spacing:.1em;
         text-transform:uppercase; margin:26px 0 12px;}
.pd-band::before{content:""; width:5px; height:22px; border-radius:3px; background:var(--rojo);}
.pd-band small{font-size:.8rem; font-weight:500; color:var(--txt2); letter-spacing:.04em; text-transform:none;}
.card{background:var(--panel); border:1px solid var(--borde); border-radius:16px; padding:22px 24px;}
.duo{display:grid; grid-template-columns:380px minmax(0,1fr); gap:16px;}
@media (max-width: 1000px){.duo{grid-template-columns:1fr;}}
.gauge{font-size:5.6rem; font-weight:800; line-height:1; letter-spacing:-.04em; margin:8px 0 6px; font-variant-numeric:tabular-nums;}
.gsub{font-size:1.05rem; color:var(--txt3);}
.gsub b{font-weight:800;}
.g3{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin-top:18px;}
.g3 div{background:var(--panel2); border-radius:12px; padding:12px;}
.g3 b{display:block; font-size:1.9rem; font-weight:800; line-height:1.15; letter-spacing:-.02em;}
.tr{display:grid; grid-template-columns:120px minmax(0,1fr); align-items:center; gap:16px; margin:14px 0;}
.tr b{font-size:2.6rem; font-weight:800; color:var(--hi); line-height:1; letter-spacing:-.03em; font-variant-numeric:tabular-nums;}
.tr b small{font-size:1.1rem; color:var(--txt2); font-weight:600; margin-left:2px;}
.bar{height:10px; background:var(--borde); border-radius:5px; overflow:hidden;}
.bar i{display:block; height:10px; border-radius:5px;}
.tr span{display:block; font-size:1.1rem; font-weight:500; color:var(--txt3); margin-top:7px;}
.tr span em{font-style:normal; font-size:.8rem; color:var(--txt2); margin-left:6px;}
.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-top:16px;}
.tile{background:var(--panel); border:1px solid var(--borde); border-radius:14px; padding:16px 18px;}
.tile b{display:block; font-size:2.4rem; font-weight:800; line-height:1.1; letter-spacing:-.02em; color:var(--hi); font-variant-numeric:tabular-nums;}
.tile .s{font-size:.88rem; color:var(--txt3);}
/* ---------- por dia ---------- */
.dias{background:var(--panel); border:1px solid var(--borde); border-radius:16px; padding:18px 22px 16px; overflow-x:auto;}
.dias-in{min-width:max-content; width:100%;}
.dias-plot, .dias-lab{display:flex; gap:12px;}
.dias-plot{position:relative; align-items:flex-end; height:230px; border-bottom:1px solid var(--borde);}
.dcol, .dlab{flex:1 0 96px; display:flex; flex-direction:column; align-items:center;}
.dcol{justify-content:flex-end; gap:8px; height:100%;}
.dcol .cv{font-size:1.6rem; font-weight:800; letter-spacing:-.02em; font-variant-numeric:tabular-nums; color:var(--hi);
          position:relative; z-index:3; background:var(--panel); padding:0 8px; border-radius:8px;}
.dcol .cb{width:64%; max-width:120px; border-radius:10px 10px 3px 3px; position:relative;}
.c100{display:flex; flex-direction:column; overflow:hidden; border-radius:10px 10px 3px 3px;}
.c100 .sg{display:flex; align-items:center; justify-content:center; font-size:1.05rem; font-weight:800; flex:none;}
.c100 .sg + .sg{border-top:2px solid var(--panel);}
.dcol.last .cb{box-shadow:0 0 0 2px #fff, 0 0 24px rgba(255,255,255,.18);}
.prom{position:absolute; left:0; right:0; border-top:2px dashed rgba(244,236,232,.55); pointer-events:none; z-index:2;}
.prom span{position:absolute; right:0; top:-24px; font-size:.78rem; font-weight:700; color:var(--txt); background:var(--bg);
           padding:2px 8px; border-radius:99px; border:1px solid var(--borde);}
.dlab{padding-top:10px; gap:3px; text-align:center;}
.dlab .cd{font-size:.8rem; font-weight:700; color:var(--txt2); text-transform:uppercase; letter-spacing:.08em;}
.dlab.last .cd{color:#fff; background:var(--rojo); padding:3px 9px; border-radius:99px;}
.dlab .ct{font-size:.85rem; color:var(--txt3); line-height:1.25;}
.dlab .ct b{color:var(--hi);}
.dley{display:flex; gap:16px; flex-wrap:wrap; font-size:.82rem; color:var(--txt2); margin-top:10px;}
.dley i{display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:5px; vertical-align:-1px;}
/* ---------- detalle de un dia ---------- */
.dd{display:grid; grid-template-columns:300px minmax(0,1fr) minmax(0,1fr); gap:16px;}
@media (max-width: 1100px){.dd{grid-template-columns:1fr;}}
.dd .fecha{font-size:2.4rem; font-weight:800; line-height:1; color:var(--hi); letter-spacing:-.02em;}
.delta{display:inline-block; margin-top:10px; padding:4px 12px; border-radius:99px; font-size:.9rem; font-weight:700;}
.cu{display:grid; grid-template-columns:70px minmax(0,1fr) 80px; align-items:center; gap:12px; margin:12px 0;}
.cu .k{font-size:1.15rem; font-weight:800; color:var(--hi);}
.cu .v{font-size:1.3rem; font-weight:800; text-align:right; font-variant-numeric:tabular-nums;}
.cu .bar{height:14px; border-radius:7px;} .cu .bar i{height:14px; border-radius:7px;}
/* ---------- iconos ---------- */
.tile, .pd-kpi, .st1{position:relative;}
.tile .ic, .pd-kpi .ic{position:absolute; right:16px; top:14px; opacity:.95; line-height:0;}
.st1 .ic{position:absolute; right:12px; top:12px; opacity:.85; line-height:0;}
/* espacio reservado para el icono: el texto nunca pasa por debajo, si no entra baja de linea */
.tile, .pd-kpi{padding-right:58px !important;}
.st1{padding-right:44px !important;}
.tile .lbl, .pd-kpi .l, .st1 span{display:block;}
/* los numeros nunca se parten: si no entran, se achican */
.tile b{white-space:nowrap; font-size:clamp(1.6rem, 2.3vw, 2.4rem) !important;}
.pd-kpi .v:not(.txt){white-space:nowrap; font-size:clamp(1.7rem, 2.3vw, 2.5rem) !important;}
.st1 b{white-space:nowrap; font-size:clamp(1.35rem, 2vw, 2.2rem) !important;}
.pd-band .icn{flex:none;}
.g3 .icn{display:block; margin-bottom:6px;}
/* ---------- pesos: cadena jaba -> racimo -> baya ---------- */
.cadena{display:grid; grid-template-columns:minmax(0,1.2fr) 140px minmax(0,1fr) 140px minmax(0,.85fr); align-items:stretch;
        background:var(--panel); border:1px solid var(--borde); border-radius:18px; padding:22px 24px; gap:0;
        background-image:radial-gradient(60% 120% at 0% 0%, rgba(255,138,42,.16), transparent 60%);}
@media (max-width: 1000px){.cadena{grid-template-columns:1fr;} .flecha{min-height:46px;} .flecha::before{display:none;}}
.eslabon{display:flex; flex-direction:column; gap:6px; padding:4px 8px;}
.eslabon .ico{height:62px; display:flex; align-items:flex-end;}
.eslabon .pv{font-size:clamp(3rem, 5vw, 4.6rem); font-weight:800; line-height:1; letter-spacing:-.04em; color:var(--hi);
             font-variant-numeric:tabular-nums;}
.eslabon .pv small{font-size:1.4rem; color:var(--txt2); font-weight:700; margin-left:4px; letter-spacing:0;}
.eslabon .ps{font-size:.95rem; color:var(--txt3); line-height:1.4;} .eslabon .ps b{color:var(--hi);}
.flecha{position:relative; display:flex; align-items:center; justify-content:center;}
.flecha::before{content:""; position:absolute; left:8px; right:8px; top:50%; border-top:2px dashed var(--borde);}
.flecha::after{content:"›"; position:absolute; right:2px; top:50%; transform:translateY(-55%); font-size:2rem; color:var(--txt2);}
.flecha span{position:relative; z-index:1; background:var(--panel); color:var(--ambar); font-size:.8rem; font-weight:700;
             padding:3px 8px; border-radius:99px; border:1px solid var(--borde); white-space:nowrap;}
/* ---------- temperaturas ---------- */
.cadena.temp{background-image:radial-gradient(60% 120% at 0% 0%, rgba(255,90,95,.16), transparent 60%);}
.tflex{flex-direction:row; align-items:center; gap:18px;}
.termo{display:flex; flex-direction:column; align-items:center; flex:none;}
.termo .tubo{width:18px; height:96px; border-radius:9px 9px 0 0; background:var(--panel2); border:2px solid var(--borde);
             border-bottom:none; display:flex; align-items:flex-end; overflow:hidden;}
.termo .tubo i{display:block; width:100%; border-radius:6px 6px 0 0;}
.termo .bulbo{width:34px; height:34px; border-radius:50%; margin-top:-4px; border:3px solid var(--borde);}
.calor{display:grid; gap:6px; min-width:max-content;}
.calor .hh{font-size:.8rem; font-weight:700; color:var(--txt2); text-align:center; text-transform:uppercase;}
.calor .hd{font-size:.85rem; font-weight:700; color:var(--txt3); display:flex; align-items:center; text-transform:uppercase;}
.calor .cel{border-radius:8px; height:44px; display:flex; align-items:center; justify-content:center;
            font-size:1rem; font-weight:800; color:#120d0f;}
.calor .cel.vacia{background:var(--panel2);}
/* ---------- tiempos ---------- */
.cadena.tiempos{background-image:radial-gradient(60% 120% at 0% 0%, rgba(255,181,71,.16), transparent 60%);}
.ruta{display:flex; height:46px; border-radius:12px; overflow:hidden; gap:3px;}
.ruta .seg{display:flex; align-items:center; justify-content:center; min-width:6px;}
.ruta .seg span{font-size:.9rem; font-weight:800; color:#120d0f; white-space:nowrap;}
.paradas{display:flex; gap:3px; margin-top:6px;}
.paradas span{min-width:6px; overflow:hidden; white-space:nowrap; text-align:center; font-size:.72rem; font-weight:800;
              color:var(--txt2); border-top:2px solid var(--borde); padding-top:4px;}
.tramo{display:grid; grid-template-columns:70px minmax(170px,1.1fr) minmax(0,2fr) 90px 110px; align-items:center; gap:14px;
       padding:9px 10px; border-radius:10px;}
.tramo.lento{background:rgba(255,90,95,.10); box-shadow:inset 0 0 0 1px rgba(255,90,95,.45);}
.tramo .pp{font-size:.85rem; font-weight:800; color:var(--txt2);}
.tramo .nm{font-size:1.05rem; font-weight:600; color:var(--hi); display:flex; align-items:center; gap:8px; flex-wrap:wrap;}
.tramo .nm i{width:11px; height:11px; border-radius:3px; flex:none;}
.tramo .nm em{font-style:normal; font-size:.7rem; font-weight:800; color:#fff; background:var(--rojov); padding:2px 8px; border-radius:99px;}
.tramo .bar{position:relative; height:12px; overflow:visible;}
.tramo .bar i{height:12px;}
.tramo .bar b{position:absolute; top:-4px; width:3px; height:20px; background:#fff; border-radius:2px; transform:translateX(-1px);}
.tramo .pr{font-size:1.35rem; font-weight:800; color:var(--hi); text-align:right; font-variant-numeric:tabular-nums;}
.tramo .mx{font-size:.85rem; color:var(--txt2);}
@media (max-width: 900px){.tramo{grid-template-columns:60px 1fr 80px;} .tramo .bar, .tramo .mx{display:none;}}
.jabas{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px;}
.jaba{background:var(--panel); border:1px solid var(--borde); border-radius:14px; padding:16px 18px;}
.jaba .cod{display:flex; align-items:center; gap:8px; font-size:.85rem; color:var(--txt2); text-transform:uppercase; letter-spacing:.06em;}
.jaba .cod b{color:var(--hi); font-size:1.05rem; letter-spacing:0;}
.jaba .tt{font-size:2.3rem; font-weight:800; letter-spacing:-.02em; margin:4px 0;}
.jaba .ps{font-size:.88rem; color:var(--txt3);} .jaba .ps b{color:var(--hi);}
/* ---------- cajas: reparto ---------- */
.rp-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; margin-top:14px;}
.rp{display:grid; grid-template-columns:minmax(90px,1.2fr) minmax(0,1.2fr) auto 44px; align-items:center; gap:10px; margin:10px 0;}
.rp .nm{font-size:.95rem; font-weight:600; color:var(--hi); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.rp .vl{font-size:1rem; font-weight:800; color:var(--hi); text-align:right; font-variant-numeric:tabular-nums;}
.rp .pc{font-size:.85rem; color:var(--txt2); text-align:right;}
/* ---------- categorizacion ---------- */
.pd-bayas{display:flex; align-items:flex-end; justify-content:space-around; gap:8px; flex-wrap:wrap;}
.pd-baya{display:flex; flex-direction:column; align-items:center; gap:5px; min-width:64px;}
.pd-baya .c{border-radius:50%; box-shadow:inset -6px -8px 0 rgba(0,0,0,.18), inset 5px 5px 0 rgba(255,255,255,.22);}
.pd-baya b{font-size:1.3rem; font-weight:800; color:var(--hi);}
.pd-baya span{font-size:.78rem; color:var(--txt2); text-align:center;}
.nota{font-size:.85rem; color:var(--txt2); margin-top:8px;}
.tpk{width:100%; border-collapse:collapse; font-size:.95rem; font-variant-numeric:tabular-nums;}
.tpk th{font-size:.7rem; letter-spacing:.07em; text-transform:uppercase; color:var(--txt2); text-align:left; padding:8px; border-bottom:2px solid var(--borde);}
.tpk td{padding:9px 8px; border-bottom:1px solid var(--borde); color:var(--txt);} .tpk .nr{text-align:right;}
.tpk th.nr{text-align:right;}
.lbl-f{font-size:.78rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--txt2); margin:0 0 6px;}
</style>
"""

pio.templates["pedregal"] = go.layout.Template(layout=dict(
    font=dict(family=FUENTE, size=14, color=TXT3),
    xaxis=dict(gridcolor=BORDE, linecolor=BORDE, zeroline=False, tickfont=dict(color=TXT2, size=13)),
    yaxis=dict(gridcolor=BORDE, linecolor=BORDE, zeroline=False, tickfont=dict(color=TXT2, size=13)),
    hoverlabel=dict(font=dict(family=FUENTE, size=14, color=TXT), bgcolor=PANEL2, bordercolor=BORDE),
    legend=dict(font=dict(color=TXT2)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"))
pio.templates.default = "plotly_dark+pedregal"
pio.templates["pedregal_claro"] = go.layout.Template(layout=dict(
    font=dict(family=FUENTE, size=14, color="#3d3432"),
    xaxis=dict(gridcolor="#e4dbd7", linecolor="#e4dbd7", zeroline=False, tickfont=dict(color="#6e625e", size=13)),
    yaxis=dict(gridcolor="#e4dbd7", linecolor="#e4dbd7", zeroline=False, tickfont=dict(color="#6e625e", size=13)),
    hoverlabel=dict(font=dict(family=FUENTE, size=14, color="#1d1517"), bgcolor="#ffffff", bordercolor="#e4dbd7"),
    legend=dict(font=dict(color="#6e625e")), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"))


# ---------------------------------------------------------------- modo claro (toda la plataforma)
_TEMA = {"claro": False}
CLARO_HEX = {PANEL: "#ffffff", PANEL2: "#f3eeec", BORDE: "#e4dbd7", TXT: "#1d1517", TXT2: "#6e625e", TXT3: "#3d3432",
             AMBAR: "#d08a10", VERDE: "#1f9d55", MORADO: "#8a4fd6", NARANJA: "#e06c00",
             "#3a2a12": "#fbefd9", "#12301f": "#dcf3e6", "#2a1f38": "#efe5fb", "#171113": "#efe9e6"}
CSS_CLARO = """
<style>
:root{--bg:#f6f3f1;--panel:#ffffff;--panel2:#f3eeec;--borde:#e4dbd7;--txt:#1d1517;--txt2:#6e625e;--txt3:#3d3432;--hi:#1d1517;
      --ambar:#d08a10;--verde:#1f9d55;--morado:#8a4fd6;--naranja:#e06c00;--rojov:#d93a40;}
.stApp, [data-testid="stHeader"], [data-testid="stBottomBlockContainer"]{background:var(--bg) !important; color:var(--txt) !important;}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div{background:#ffffff !important; border-right:1px solid var(--borde);}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp li, .stApp label{color:var(--txt);}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{color:var(--txt2) !important;}
/* listas desplegables y buscadores: blancas, borde suave, texto oscuro */
.stApp [data-baseweb="select"] > div{background:#ffffff !important; border:1px solid #d9cdc8 !important; border-radius:10px !important;}
.stApp [data-baseweb="select"] > div div, .stApp [data-baseweb="select"] input{background:transparent !important; color:var(--txt) !important;}
.stApp [data-baseweb="select"] svg{fill:var(--txt2) !important; color:var(--txt2) !important;}
.stApp [data-baseweb="select"] input::placeholder, .stApp [data-baseweb="select"] [aria-hidden="true"]{color:#8d817c !important; opacity:1 !important;}
.stApp [data-baseweb="select"] > div:focus-within{border-color:#C8102E !important; box-shadow:0 0 0 3px rgba(200,16,46,.12) !important;}
/* listas de esta version de Streamlit (react-aria): caja blanca, texto oscuro, menu blanco */
.stApp .react-aria-ComboBox > [role="group"]{background:#ffffff !important; border:1px solid #d9cdc8 !important; border-radius:10px !important;}
.stApp .react-aria-ComboBox > [role="group"]:focus-within{border-color:#C8102E !important; box-shadow:0 0 0 3px rgba(200,16,46,.12) !important;}
.stApp .react-aria-ComboBox input{background:transparent !important; color:var(--txt) !important; border:0 !important;}
.stApp .react-aria-ComboBox input::placeholder{color:#8d817c !important; opacity:1 !important;}
.stApp .react-aria-ComboBox button, .stApp .react-aria-ComboBox button svg{background:transparent !important; color:var(--txt2) !important;}
[data-testid$="VirtualDropdown"], [data-trigger="ComboBox"], .react-aria-Popover{
  background:#ffffff !important; border:1px solid #e4dbd7 !important; box-shadow:0 10px 30px rgba(40,20,20,.14) !important;}
[data-testid$="VirtualDropdown"] *, [data-trigger="ComboBox"] *{color:var(--txt) !important;}
[data-testid$="VirtualDropdown"] [role="option"][data-focused="true"] > div, [data-testid$="VirtualDropdown"] [role="option"]:hover > div{background:#fbe8ea !important;}
[data-testid$="VirtualDropdown"] [role="option"][data-selected="true"] > div{background:#f6dfe2 !important; font-weight:600;}
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-testid="stTextInput"] input, .stApp textarea{
  background:#ffffff !important; color:var(--txt) !important; border-color:#d9cdc8 !important;}
.stApp [data-baseweb="select"] [data-baseweb="tag"], .stApp [data-baseweb="tag"]{background:#C8102E !important; border-radius:99px !important;}
.stApp [data-baseweb="select"] [data-baseweb="tag"] *, .stApp [data-baseweb="tag"] *{background:transparent !important; color:#ffffff !important; fill:#ffffff !important;}
/* menu que se despliega */
[data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"]{
  background:#ffffff !important; color:var(--txt) !important;}
[data-baseweb="popover"] > div{border:1px solid #e4dbd7 !important; box-shadow:0 10px 30px rgba(40,20,20,.12) !important;}
[data-baseweb="popover"] li *, [role="option"], [role="option"] *{color:var(--txt) !important;}
[data-baseweb="popover"] li:hover, [role="option"]:hover, [aria-selected="true"][role="option"]{background:#fbe8ea !important;}
[data-baseweb="popover"] input{background:#f6f3f1 !important;}
/* botones */
.stButton button, .stDownloadButton button, [data-testid="stButtonGroup"] button, [data-testid^="stBaseButton"]{
  background:#ffffff !important; color:var(--txt) !important; border:1px solid #d9cdc8 !important;}
.stButton button p, .stDownloadButton button p, [data-testid="stButtonGroup"] button p{color:inherit !important;}
/* opcion elegida en los filtros (segmentos y pastillas): rojo Pedregal, imposible no verla */
.stApp [data-testid="stButtonGroup"] button[data-testid$="Active"], .stApp [data-testid="stButtonGroup"] button[kind$="Active"],
.stApp button[data-testid$="Active"], .stApp button[kind$="Active"], .stApp [data-testid="stButtonGroup"] button[aria-checked="true"],
.stApp [data-testid="stButtonGroup"] button[aria-pressed="true"], .stApp [data-testid="stButtonGroup"] button[data-selected="true"]{
  background:#C8102E !important; color:#ffffff !important; border-color:#C8102E !important; box-shadow:0 2px 8px rgba(200,16,46,.25) !important;}
.stApp button[data-testid$="Active"] p, .stApp button[kind$="Active"] p, .stApp button[aria-checked="true"] p{color:#ffffff !important;}
.stApp [data-testid="stBaseButton-primary"], .stApp button[kind="primary"], .stApp button[data-variant="primary"]{background:#C8102E !important; color:#ffffff !important; border-color:#C8102E !important;}
.stApp button[kind="primary"] p, .stApp button[data-variant="primary"] p{color:#fff !important;}
[data-testid="stExpander"] details, [data-testid="stExpander"] summary{background:#ffffff !important; border-color:var(--borde) !important;}
[data-testid="stExpander"] summary *{color:var(--txt) !important;}
[data-testid="stAlert"]{background:#fff6e5 !important;} [data-testid="stAlert"] *{color:#5a4100 !important;}
.stApp hr{border-color:var(--borde) !important;}
[data-testid="stToggle"] *{color:var(--txt);}
/* bloques propios de app.py */
.kpi{background:#ffffff !important; border-color:var(--borde) !important;} .kpi .l{color:var(--txt2) !important;}
.miga b{color:var(--txt) !important;} .info div{border-color:var(--borde) !important;}
.pd-baya .c{box-shadow:inset -6px -8px 0 rgba(0,0,0,.12), inset 5px 5px 0 rgba(255,255,255,.35);}
.dcol.last .cb{box-shadow:0 0 0 2px #1d1517;}
.pl{background:#efe9e6 !important;}
</style>
"""


def claro():
    return _TEMA["claro"]


def a_claro(t):
    """Cambia los colores fijos del modo oscuro por los del modo claro."""
    t = t.replace("color:#fff'", "color:var(--hi)'").replace("color:#fff;", "color:var(--hi);")
    for a, b in CLARO_HEX.items():
        t = t.replace(a, b).replace(a.upper(), b)
    return t


def graf(fig):
    if claro():
        for tr in fig.data:                                   # numeros fuera de la barra: oscuros sobre fondo blanco
            if getattr(tr, "textposition", None) == "outside":
                tr.textfont.color = "#1d1517"
        fig = pio.from_json(a_claro(pio.to_json(fig)))
        fig.update_layout(template="plotly_white+pedregal_claro")
    st.plotly_chart(fig, use_container_width=True, theme=None, config={"displayModeBar": False})


def html(h):
    st.markdown(a_claro(h) if claro() else h, unsafe_allow_html=True)


def configurar(ctx):
    _CTX.update(ctx)


def css(modo_claro=False):
    _TEMA["claro"] = bool(modo_claro)
    st.markdown(CSS + (CSS_CLARO if modo_claro else ""), unsafe_allow_html=True)


def logo_html():
    if os.path.exists(LOGO):
        with open(LOGO, "rb") as f:
            return f"<span class='logo'><img src='data:image/png;base64,{base64.b64encode(f.read()).decode()}' alt='Pedregal'></span>"
    return "<span class='logo' style='color:#C8102E;font-weight:800;font-size:1.4rem'>Pedregal</span>"


UVA = ("<svg width='40' height='50' viewBox='0 0 48 60' aria-hidden='true'><path d='M24 3v7M24 7c4-4 9-4 13-1' stroke='#9fd45a' "
       "stroke-width='3' fill='none' stroke-linecap='round'/><g fill='#9fd45a' stroke='#5f9e2c' stroke-width='1.2'>"
       + "".join(f"<circle cx='{x}' cy='{y}' r='6'/>" for x, y in
                 [(13, 17), (24, 16), (35, 17), (18, 27), (30, 27), (12, 37), (24, 37), (36, 37), (18, 47), (30, 47), (24, 55)])
       + "</g></svg>")


def encabezado(titulo, sub, derecha=""):
    """Banda roja Pedregal (igual que Packing y Directorio)."""
    if "<b>" in derecha:
        et, val = derecha.split("<b>", 1)
        der = f"<span>{et}</span><b>{val}"
    else:
        der = derecha
    html(f"<header class='pd-head'><div class='mk'><div><div class='wm'>Pedregal</div><div class='tg'>the fruit company</div></div>{UVA}</div>"
         f"<div class='ttl'><h1>{titulo}</h1><div class='sub'>{sub}</div></div><div class='der'>{der}</div></header>")



# ---------------------------------------------------------------- iconos (mismo estilo que la seccion Pesos)
_RAC = "".join(f"<circle cx='{x}' cy='{y}' r='2.6' fill='currentColor' stroke='none'/>" for x, y in
               [(7, 8), (12, 7.6), (17, 8), (9.5, 12.6), (14.5, 12.6), (7, 17), (12, 17), (17, 17), (12, 21.2)])
IC = {
    "jaba": "<path d='M3 9h18l-2 12H5z'/><path d='M2 9h20M6 13.5h12M7 17.5h10M9.5 9v12M14.5 9v12'/>"
            "<circle cx='8' cy='5.5' r='2' fill='currentColor' stroke='none'/><circle cx='12' cy='4.6' r='2' fill='currentColor' stroke='none'/>"
            "<circle cx='16' cy='5.5' r='2' fill='currentColor' stroke='none'/>",
    "racimo": "<path d='M12 1.5v3.5M12 3.2c2-1.6 4.4-1.6 6-.4'/>" + _RAC,
    "baya": "<circle cx='12' cy='12' r='8' fill='currentColor' stroke='none'/><circle cx='9' cy='9' r='2.4' fill='#fff' stroke='none' opacity='.35'/>",
    "bayas": "<circle cx='8' cy='9' r='4.5' fill='currentColor' stroke='none'/><circle cx='16.5' cy='13' r='3.5' fill='currentColor' stroke='none'/>"
             "<circle cx='9' cy='19' r='2.6' fill='currentColor' stroke='none'/><path d='M15 3l1.5 2M19 6l-2 .8M20 19l-1.6-1.4'/>",
    "lupa": "<circle cx='10.5' cy='10.5' r='6.5'/><path d='M15.5 15.5L21 21'/>",
    "alerta": "<path d='M12 3L2.5 20h19z'/><path d='M12 9.5v5'/><circle cx='12' cy='17.3' r='.6' fill='currentColor'/>",
    "estrella": "<path d='M12 3l2.7 5.6 6.1.8-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.8z'/>",
    "bicho": "<ellipse cx='12' cy='14' rx='5' ry='6.5'/><path d='M12 7.5V21M9 6l-2-3M15 6l2-3M7 11H3M7 15.5H3M17 11h4M17 15.5h4M8 19.5l-3 2M16 19.5l3 2'/>"
             "<circle cx='12' cy='6.2' r='2.4'/>",
    "check": "<circle cx='12' cy='12' r='9'/><path d='M7.5 12.3l3 3 6-6.3'/>",
    "brillo": "<path d='M12 2.5l2 5.5 5.5 2-5.5 2-2 5.5-2-5.5-5.5-2 5.5-2z'/><path d='M19 15l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z'/>",
    "medalla": "<circle cx='12' cy='15' r='6'/><path d='M8.5 10L5.5 2.5h4l2.5 6M15.5 10l3-7.5h-4l-2.5 6'/><path d='M12 12.2v5.6M10.3 13.4l1.7-1.2'/>",
    "gota": "<path d='M12 2.5c3.8 5 6.5 8.4 6.5 11.8a6.5 6.5 0 0 1-13 0c0-3.4 2.7-6.8 6.5-11.8z'/><path d='M9 14.5a3 3 0 0 0 3 3'/>",
    "balanza": "<path d='M12 3v18M7 21h10M4 7h16M12 4.5l-.01 0'/><path d='M4 7l-2.5 6h5zM20 7l-2.5 6h5z'/><path d='M1.5 13a2.5 2 0 0 0 5 0M17.5 13a2.5 2 0 0 0 5 0'/>",
    "tacho": "<path d='M4 6.5h16M9.5 6.5V4h5v2.5M6 6.5l1 14h10l1-14'/><path d='M10 10.5v6.5M14 10.5v6.5'/>",
    "calendario": "<rect x='3' y='4.5' width='18' height='16' rx='2.5'/><path d='M3 9.5h18M8 2.5v4M16 2.5v4'/><path d='M7.5 13.5h2M11 13.5h2M14.5 13.5h2M7.5 17h2M11 17h2'/>",
    "bandera": "<path d='M5 21.5V3'/><path d='M5 4h12l-2.5 4L17 12H5'/>",
    "reloj": "<circle cx='12' cy='12' r='9'/><path d='M12 7v5.2l3.5 2'/>",
    "brote": "<path d='M12 21v-9'/><path d='M12 12c0-4.5-3-7-8-7 0 5 3 7.5 8 7z'/><path d='M12 14.5c0-4 2.6-6.5 7.5-6.5 0 4.5-2.8 6.5-7.5 6.5z'/>",
    "area": "<rect x='3' y='3' width='18' height='18' rx='2'/><path d='M3 12h18M12 3v18'/>",
    "cuarteles": "<rect x='3' y='3' width='8' height='8' rx='1.5'/><rect x='13' y='3' width='8' height='8' rx='1.5'/>"
                 "<rect x='3' y='13' width='8' height='8' rx='1.5'/><rect x='13' y='13' width='8' height='8' rx='1.5'/>",
    "caja": "<path d='M3 7.5l9-4.5 9 4.5v9l-9 4.5-9-4.5z'/><path d='M3 7.5l9 4.5 9-4.5M12 12v9'/>",
    "regla": "<rect x='2.5' y='8' width='19' height='8' rx='1.5'/><path d='M6.5 8v3.5M10.5 8v2.2M14.5 8v3.5M18.5 8v2.2'/>",
    "raquis": "<path d='M12 2.5v8M12 6.5l-5 4M12 6.5l5 4M12 10.5l-4 5M12 10.5l4 5M12 10.5v11'/>",
    "sol": "<circle cx='12' cy='12' r='4.5'/><path d='M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8'/>",
    "luna": "<path d='M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z'/>",
    "barras": "<path d='M4 20.5h16'/><rect x='5' y='11' width='3.4' height='9.5' rx='.8'/><rect x='10.3' y='6' width='3.4' height='14.5' rx='.8'/><rect x='15.6' y='13.5' width='3.4' height='7' rx='.8'/>",
    "termometro": "<path d='M14 14.8V4.5a2.5 2.5 0 0 0-5 0v10.3a4.5 4.5 0 1 0 5 0z'/><path d='M11.5 9v8'/>"
                  "<circle cx='11.5' cy='18.3' r='1.6' fill='currentColor'/><path d='M17 5h3M17 8.5h2M17 12h3'/>",
    "camion": "<path d='M2 6h11v10H2zM13 9.5h4.5L21 13v3h-8'/><circle cx='6' cy='17.5' r='2'/><circle cx='17' cy='17.5' r='2'/>",
    "mapa": "<path d='M12 21.5s-6.5-6.2-6.5-11.5a6.5 6.5 0 0 1 13 0c0 5.3-6.5 11.5-6.5 11.5z'/><circle cx='12' cy='10' r='2.4'/>",
}
# palabra clave (en minusculas) -> icono; se usa el primero que aparezca en la etiqueta
CLAVES = [("tiempo", "reloj"), ("recorrido", "mapa"), ("más lentas", "alerta"), ("traslado", "camion"),
          ("temperatura", "termometro"), ("pulpa", "termometro"), ("ambiente", "sol"), ("diferencia", "barras"),
          ("más caliente", "alerta"), ("por hora", "reloj"), ("distribución", "barras"), ("ddc", "brote"), ("bayas por racimo", "racimo"), ("racimos por jaba", "jaba"), ("racimos/jaba", "jaba"), ("bayas por jaba", "bayas"),
          ("higiene", "brillo"), ("desgrane", "bayas"), ("muestra", "lupa"), ("más defectos", "alerta"),
          ("defecto principal", "alerta"), ("defecto", "alerta"), ("plaga", "bicho"), ("condición", "alerta"),
          ("calidad lograda", "check"), ("sin defecto", "check"), ("buenos", "check"), ("calidad", "estrella"),
          ("lotes en cosecha", "racimo"), ("días de cosecha", "reloj"), ("inicio", "calendario"), ("último", "bandera"),
          ("fin de", "bandera"), ("hectárea", "area"), ("cuartel", "cuarteles"), ("caja", "caja"),
          ("turno diurno", "sol"), ("turno nocturno", "luna"), ("raquis", "raquis"), ("rango", "balanza"),
          ("limpieza", "brillo"), ("categor", "medalla"), ("cat ", "medalla"), ("descarte", "tacho"), ("brix", "gota"),
          ("bajo", "gota"), ("tolerable", "gota"), ("óptimo", "gota"), ("exceso", "gota"), ("promedio", "gota"),
          ("moda", "gota"), ("máximo", "gota"), ("mínimo", "gota"), ("pesos", "balanza"), ("peso de jaba", "jaba"),
          ("peso de racimo", "racimo"), ("peso de baya", "baya"), ("por día", "calendario"), ("un día", "calendario"),
          ("color", "baya"), ("calibre", "regla"), ("top 5", "barras"),
          ("lotes", "mapa"), ("variedades", "racimo")]


def ic(nombre, t=26, color="currentColor", ancho=1.9):
    if nombre not in IC:
        return ""
    return (f"<svg class='icn' width='{t}' height='{t}' viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='{ancho}' "
            f"stroke-linecap='round' stroke-linejoin='round' style='color:{color}' aria-hidden='true'>{IC[nombre]}</svg>")


def ic_para(texto, t=26, color="currentColor"):
    s = f"{texto} ".lower()
    return next((ic(n, t, color) for k, n in CLAVES if k in s), "")


def kpis(items):
    """items: (etiqueta, valor, subtitulo, _)"""
    def clase(v):
        t = str(v).replace("%", "").replace(",", "").replace(".", "").replace("°", "").strip()
        return "v" if t.isdigit() or t in ("—", "") else "v txt"
    html("<div class='pd-kpis'>" + "".join(
        f"<div class='pd-kpi'><span class='ic'>{ic_para(l, 30, AMBAR)}</span><div class='l'>{l}</div><div class='{clase(v)}'>{v}</div>"
        f"<div class='s'>{s}</div></div>" for l, v, s, *_ in items) + "</div>")


def tile(l, v, s="", color="#fff", icono=None):
    i = ic(icono, 32, color if color != "#fff" else AMBAR) if icono else ic_para(l, 32, color if color != "#fff" else AMBAR)
    return (f"<div class='tile'><span class='ic'>{i}</span><div class='lbl'>{l}</div><b style='color:{color}'>{v}</b>"
            f"<div class='s'>{s}</div></div>")


def tiles(items):
    html("<div class='tiles'>" + "".join(tile(*it) for it in items) + "</div>")


def fmtp(x, d=1):
    return "—" if x is None or pd.isna(x) else f"{x:.{d}f}%"


def band(texto, sub=""):
    html(f"<div class='pd-band'>{ic_para(texto, 24, AMBAR)}{texto}{f' <small>{sub}</small>' if sub else ''}</div>")


DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def dia(f):
    f = pd.Timestamp(f)
    return f"{DIAS[f.weekday()]} {f:%d/%m}"


def num_lote(lote_id):
    return lote_id.split(".")[1][1:].zfill(3)


def etiqueta_lote(lote_id):
    """Texto para el buscador: 'Lote 037 · Orongo · Timpson · En cosecha (9 días)'."""
    props = _CTX["props"]
    cu = props[props["lote_id"] == lote_id]
    codv = sorted({v for v in cu["variedad"] if v})
    vari = ", ".join(_CTX["VARIEDAD_NOMBRE"].get(v, v) for v in codv) or "sin variedad"
    est = estado_lotes().get(lote_id)
    e = f"{est['estado']} ({est['dias']} días)" if est else "sin cosecha"
    return f"Lote {num_lote(lote_id)} · {lote_id.split('.')[0].title()} · {vari} · {e}"


def orden_lotes(lotes):
    """En cosecha primero, luego terminadas, luego el resto; dentro, por numero de lote."""
    est = estado_lotes()
    rango = {"En cosecha": 0, "Terminada": 1}
    def clave(l):
        n = "".join(ch for ch in l.split(".")[1] if ch.isdigit())
        return (rango.get(est.get(l, {}).get("estado"), 2), int(n) if n else 999, l)
    return sorted(set(lotes), key=clave)


# ---------------------------------------------------------------- datos
def _db_mtime():
    return os.path.getmtime(DB) if os.path.exists(DB) else 0


def tabla(clave):
    """Registros de la campana actual de una tabla de cosecha, con su lote y cuartel.
    Se lee una sola vez por cada actualizacion de datos (se vuelve a leer solo si cambia la base)."""
    return _tabla(clave, _db_mtime())


@st.cache_data(max_entries=40, show_spinner=False)
def _tabla(clave, version):          # version (sin "_") para que el cache se renueve al actualizar la base
    t = cc.TABLAS[clave]
    if not os.path.exists(DB):
        return pd.DataFrame()
    with duckdb.connect(DB, read_only=True) as c:
        existe = c.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [t]).fetchone()[0]
        if not existe:
            return pd.DataFrame()
        df = c.execute(f'''SELECT * FROM "{t}" WHERE TRY_CAST(substr(CAST("meta-fecha" AS VARCHAR), 1, 10) AS DATE)
                           >= DATE '{cc.INICIO_CAMPANIA}' ''').df()
    col = cc.COL_LOTE.get(clave, "lote-cuartel")
    if df.empty or col not in df:
        return pd.DataFrame()
    mp = _CTX["mapeo"](t, col)[["v", "lote_id", "cuartel_id"]]
    df["_v"] = df[col].astype(str)
    df = df.merge(mp, left_on="_v", right_on="v", how="left").drop(columns=["v", "_v"])
    df["_fecha"] = cc.fecha(df)
    return df.dropna(subset=["lote_id"])


@st.cache_data(ttl=300)
def grupos():
    return cc.cargar_grupos()


def estado_lotes():
    """Por lote: inicio, ultimo dia, dias, registros y estado.
    Automatico: 'En cosecha' (registro en los ultimos 2 dias), 'Terminada', o 'Revisar' si tiene muy pocos registros
    (posible error de digitacion). Lo que escribas en Maestro/estado_lotes.xlsx manda sobre lo automatico."""
    return _estado_lotes((os.path.getmtime(ESTADOS_XLSX) if os.path.exists(ESTADOS_XLSX) else 0, _db_mtime()))


def estados_manuales():
    """Maestro/estado_lotes.xlsx: columnas lote_id y estado_manual (En cosecha / Terminada / Excluir) y nota."""
    if not os.path.exists(ESTADOS_XLSX):
        return {}
    try:
        m = pd.read_excel(ESTADOS_XLSX, dtype=str).fillna("")
    except Exception:
        return {}
    out = {}
    for _, f in m.iterrows():
        e = str(f.get("estado_manual", "")).strip().lower()
        if not e:
            continue
        e = {"en cosecha": "En cosecha", "terminada": "Terminada", "terminado": "Terminada", "excluir": "Excluir",
             "no": "Excluir", "error": "Excluir"}.get(e)
        if e:
            out[str(f.get("lote_id", "")).strip().upper()] = (e, str(f.get("nota", "")).strip())
    return out


@st.cache_data(max_entries=20, show_spinner=False)
def _estado_lotes(firma):            # firma = fechas de modificacion del Excel de estados y de la base
    partes = [tabla(k)[["lote_id", "_fecha"]] for k in cc.TABLAS if not tabla(k).empty]
    if not partes:
        return {}
    d = pd.concat(partes).dropna()
    hoy = d["_fecha"].max()
    man = estados_manuales()
    out = {}
    for lid, g in d.groupby("lote_id"):
        ult = g["_fecha"].max()
        auto = "En cosecha" if (hoy - ult).days <= 2 else "Terminada"
        if len(g) < MIN_REGISTROS:
            auto = "Revisar"
        e, nota = man.get(str(lid).upper(), (None, ""))
        if e == "Excluir":
            continue
        out[lid] = {"inicio": g["_fecha"].min(), "ultimo": ult, "dias": g["_fecha"].dt.date.nunique(),
                    "registros": len(g), "estado": e or auto, "auto": auto, "manual": bool(e), "nota": nota}
    return out


def origen_lote(lote_id):
    """De donde vienen los registros de un lote: por tabla, cuantos, dias, fechas y evaluadores."""
    filas = []
    for k in cc.TABLAS:
        t = tabla(k)
        if t.empty:
            continue
        g = t[t["lote_id"] == lote_id]
        if g.empty:
            continue
        ev = g["meta-evaluador"].astype(str).value_counts() if "meta-evaluador" in g else pd.Series(dtype=int)
        col = cc.COL_LOTE.get(k, "lote-cuartel")
        filas.append({"Tabla": NOMBRE_TABLA.get(k, k), "Registros": len(g), "Días": g["_fecha"].dt.date.nunique(),
                      "Primero": g["_fecha"].min(), "Último": g["_fecha"].max(),
                      "Como lo escribieron": ", ".join(sorted(g[col].astype(str).unique())[:6]) if col in g else "",
                      "Evaluadores": " · ".join(f"{n} ({c})" for n, c in ev.head(3).items())})
    return pd.DataFrame(filas)


def registros_lote(lote_id, maximo=200):
    """Cada registro de un lote (para lotes con pocos datos): tabla, fecha, hora, evaluador y lote escrito."""
    filas = []
    for k in cc.TABLAS:
        t = tabla(k)
        if t.empty:
            continue
        g = t[t["lote_id"] == lote_id]
        col = cc.COL_LOTE.get(k, "lote-cuartel")
        for _, f in g.head(maximo).iterrows():
            filas.append({"Tabla": NOMBRE_TABLA.get(k, k), "Fecha": f["_fecha"], "Hora": f.get("meta-hora", ""),
                          "Evaluador": f.get("meta-evaluador", ""), "Lote escrito": f.get(col, ""), "Id": f.get("id", "")})
    return pd.DataFrame(filas).sort_values("Fecha") if filas else pd.DataFrame()


def tabla_origen(df):
    st.dataframe(df, hide_index=True, use_container_width=True, column_config={
        "Primero": st.column_config.DateColumn(format="DD/MM/YYYY"), "Último": st.column_config.DateColumn(format="DD/MM/YYYY"),
        "Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})


# ---------------------------------------------------------------- vista de administrador (con clave)
def clave_admin():
    try:
        return str(st.secrets.get("admin_clave", "")).strip()
    except Exception:
        return ""


def es_admin():
    return bool(st.session_state.get("admin_ok"))


def admin(lotes_visibles):
    """Pantalla solo para el administrador: estado de los lotes y revision de datos."""
    import hmac
    encabezado("Administrador", "Estado de los lotes · revisión de datos")
    clave = clave_admin()
    if not clave:
        st.warning("Falta la clave de administrador. Abre el archivo .streamlit\\secrets.toml de la carpeta de la "
                   "plataforma, escribe tu clave en admin_clave = \"...\", guarda y presiona R.")
        return
    if not es_admin():
        c, _ = st.columns([1, 2])
        with c.form("login_admin"):
            p = st.text_input("Clave de administrador", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if hmac.compare_digest(p.strip(), clave):
                    st.session_state["admin_ok"] = True
                    st.rerun()
                st.error("Clave incorrecta.")
        return
    if st.button("Cerrar sesión de administrador"):
        st.session_state.pop("admin_ok", None)
        st.rerun()
    est = {l: e for l, e in estado_lotes_todos().items() if l in set(lotes_visibles)}
    if not est:
        st.info("Aún no hay lotes con registros de cosecha.")
        return
    band("Estado de los lotes", "elige el estado a mano solo si el automático está mal · luego Guardar")
    man = estados_manuales()
    base = pd.DataFrame([{"Lote": l, "Registros": e["registros"], "Días": e["dias"], "Último": e["ultimo"],
                          "Automático": e["auto"], "Estado a mano": man.get(l.upper(), ("", ""))[0],
                          "Nota": man.get(l.upper(), ("", ""))[1]} for l, e in sorted(est.items())])
    ed = st.data_editor(base, hide_index=True, use_container_width=True, key="editor_estados",
                        disabled=["Lote", "Registros", "Días", "Último", "Automático"],
                        column_config={"Último": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                       "Estado a mano": st.column_config.SelectboxColumn(
                                           options=["", "En cosecha", "Terminada", "Excluir"],
                                           help="Vacío = automático. Excluir = el lote no aparece (ej. error de digitación)."),
                                       "Nota": st.column_config.TextColumn(help="Por qué lo cambiaste")})
    if st.button("💾  Guardar estados", type="primary"):
        pd.DataFrame({"lote_id": ed["Lote"], "estado_automatico": ed["Automático"],
                      "estado_manual": ed["Estado a mano"].fillna(""), "nota": ed["Nota"].fillna("")}).to_excel(
            ESTADOS_XLSX, index=False)
        st.success("Guardado. Ya se aplica para todos los usuarios.")
        st.rerun()
    revision_datos(lotes_visibles)
    band("¿De dónde vienen los datos de un lote?")
    l = st.selectbox("Lote", orden_lotes(list(est)), index=None, placeholder="Elige un lote", format_func=etiqueta_lote,
                     key="admin_origen")
    if l:
        og = origen_lote(l)
        tabla_origen(og) if not og.empty else st.caption("Sin registros.")


def estado_lotes_todos():
    """Como estado_lotes, pero incluye los lotes excluidos a mano (para poder devolverlos)."""
    est = dict(estado_lotes())
    man = estados_manuales()
    partes = [tabla(k)[["lote_id", "_fecha"]] for k in cc.TABLAS if not tabla(k).empty]
    if partes:
        d = pd.concat(partes).dropna()
        for lid, g in d.groupby("lote_id"):
            if lid not in est:
                est[lid] = {"inicio": g["_fecha"].min(), "ultimo": g["_fecha"].max(), "dias": g["_fecha"].dt.date.nunique(),
                            "registros": len(g), "estado": "Excluir", "auto": "Revisar" if len(g) < MIN_REGISTROS else "Terminada",
                            "manual": True, "nota": man.get(str(lid).upper(), ("", ""))[1]}
    return est


def revision_datos(lotes_visibles):
    """Panel en la pantalla de Cosecha: lotes a revisar y estado de cada lote."""
    est = {l: e for l, e in estado_lotes_todos().items() if l in set(lotes_visibles)}
    if not est:
        return
    rev = [l for l, e in est.items() if e["estado"] == "Revisar"]
    titulo = (f"🔎  Revisión de datos · {len(rev)} lote(s) con muy pocos registros" if rev
              else "🔎  Revisión de datos · estado de los lotes")
    with st.expander(titulo, expanded=bool(rev)):
        html(f"<div class='nota'>Un lote se marca <b style='color:{MORADO}'>Revisar</b> cuando tiene menos de {MIN_REGISTROS} "
             "registros en todas las tablas: suele ser un error al escribir el lote. Abajo ves en qué tabla, qué día, quién "
             "y cómo lo escribió, para corregirlo en origen. Para fijar el estado usa la tabla de arriba.</div>")
        for l in rev:
            html(f"<div class='pd-band' style='margin:18px 0 8px'>{ic('alerta', 22, MORADO)}Lote {num_lote(l)} · "
                 f"{l.split('.')[0].title()} <small>{est[l]['registros']} registro(s)</small></div>")
            tabla_origen(registros_lote(l))
        resumen = pd.DataFrame([{"Lote": f"L{num_lote(l)} · {l.split('.')[0].title()}", "Estado": e["estado"],
                                 "Automático": e["auto"], "Fijado a mano": "sí" if e["manual"] else "",
                                 "Registros": e["registros"], "Días": e["dias"], "Inicio": e["inicio"], "Último": e["ultimo"],
                                 "Nota": e["nota"]} for l, e in sorted(est.items(), key=lambda x: x[0])])
        html("<div class='pd-band' style='margin:18px 0 8px'>Estado de todos los lotes con registros</div>")
        st.dataframe(resumen, hide_index=True, use_container_width=True, column_config={
            "Inicio": st.column_config.DateColumn(format="DD/MM/YYYY"), "Último": st.column_config.DateColumn(format="DD/MM/YYYY")})


def actividad_cuarteles(lote_id):
    """cuartel -> ('hoy'|'antes', ultima fecha) segun los registros de cosecha del lote."""
    partes = [tabla(k) for k in cc.TABLAS if not tabla(k).empty]
    if not partes:
        return {}
    d = pd.concat([p.loc[p["lote_id"] == lote_id, ["cuartel_id", "_fecha"]] for p in partes]).dropna()
    if d.empty:
        return {}
    ult_lote = d["_fecha"].max()
    u = d.groupby("cuartel_id")["_fecha"].max()
    return {c: ("hoy" if f == ult_lote else "antes", f) for c, f in u.items()}


def filtro_actual(lote_id):
    """(dias, cuarteles) elegidos en la barra de filtros del lote. dias vacio = toda la cosecha."""
    dias_ = st.session_state.get(f"dias_cos_{lote_id}") or []
    cus = st.session_state.get(f"cu_cos_{lote_id}") or []
    return sorted(pd.Timestamp(x) for x in dias_), list(cus)


DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def texto_dias(dias_):
    if not dias_:
        return "toda la cosecha"
    if len(dias_) == 1:
        return f"solo el {dia(dias_[0])}"
    if len(dias_) <= 4:
        return f"{len(dias_)} días: " + ", ".join(f"{x:%d/%m}" for x in dias_)
    return f"{len(dias_)} días elegidos ({dias_[0]:%d/%m} al {dias_[-1]:%d/%m})"


def dias_lote(lote_id):
    """Dias con algun registro de cosecha en el lote, del mas reciente al mas antiguo."""
    fs = set()
    for k in cc.TABLAS:
        t = tabla(k)
        if not t.empty:
            fs |= set(t.loc[t["lote_id"] == lote_id, "_fecha"].dropna().dt.date)
    return sorted(fs, reverse=True)


def de_lote(clave, lote_id):
    d = tabla(clave)
    if d.empty:
        return d
    d = d[d["lote_id"] == lote_id]
    dias_, cus = filtro_actual(lote_id)
    if dias_:
        d = d[d["_fecha"].dt.normalize().isin(dias_)]
    if cus:
        d = d[d["cuartel_id"].isin(cus)]
    return d


# ---------------------------------------------------------------- encabezado y KPIs del modo cosecha
def cabecera(vista, campania="", con_kpis=True):
    est = estado_lotes()
    lotes_v = set(vista["lote_id"])
    en = [l for l, e in est.items() if e["estado"] == "En cosecha" and l in lotes_v]
    ultimo = max((e["ultimo"] for e in est.values()), default=None)
    encabezado("Calidad de cosecha",
               f"Limpieza · Categorización · Brix · Pesos · Descarte · Temperaturas · Tiempos · Campaña {campania}",
               f"Datos al<b>{ultimo:%d/%m}</b>" if ultimo is not None else "")
    if ultimo is None:
        st.info("Aún no hay datos de cosecha. Corre ACTUALIZAR_DATOS.bat.")
        return
    if not con_kpis:
        return
    L = tabla("limpieza")
    if not L.empty:                       # KPIs del ultimo dia CON limpieza (otras tablas pueden ir un dia adelante)
        L = L[L["lote_id"].isin(lotes_v) & L["lote_id"].isin(list(est))]
        ultimo = L["_fecha"].max() if not L.empty else ultimo
        L = L[L["_fecha"] == ultimo]
    peor = mejor_plaga = top = des = None
    if not L.empty:
        res = {lid: cc.desviacion(g, "racimos-por-jaba", grupos()) for lid, g in L.groupby("lote_id")}
        res = {k: v for k, v in res.items() if v}
        if res:
            peor = max(res.items(), key=lambda kv: kv[1]["desviacion"])
            mejor_plaga = max(res.items(), key=lambda kv: kv[1]["grupos"]["Plagas"])
        des = cc.desviacion(L, "racimos-por-jaba", grupos())
        top = des["detalle"].iloc[0] if des else None
    nom = lambda lid: f"Lote {num_lote(lid)} · {lid.split('.')[0].title()}"
    corto = lambda lid: f"L{num_lote(lid)}"
    kpis([
        ("Lotes en cosecha", f"{len(en)}", f"de {len(est)} con registros esta campaña", ""),
        (f"Muestras del {ultimo:%d/%m}", f"{len(L):,}", f"{L['lote_id'].nunique()} lote(s) evaluados" if len(L) else "", ""),
        ("Lote con más defectos", fmtp(peor[1]["desviacion"], 2) if peor else "—", nom(peor[0]) if peor else "", ""),
        ("Defecto principal", top["defecto"] if top is not None else "—",
         f"{top['pct']:.2f}% · {top['grupo'].lower()}" if top is not None else "", ""),
        ("Mayor plagas", fmtp(mejor_plaga[1]["grupos"]["Plagas"], 2) if mejor_plaga else "—",
         nom(mejor_plaga[0]) if mejor_plaga else "", ""),
        ("Desgrane", f"{des['desgrane'][0]:.2f}" if des and des.get("desgrane") else "—", "bayas por muestra (promedio)", ""),
    ])


# ---------------------------------------------------------------- ficha del lote
# ---------------------------------------------------------------- cajas producidas (Excel en Maestro/cajas)
@st.cache_data(ttl=300)
def _cajas(firma):
    return cj.leer(sorted(set(_CTX["props"]["lote_id"])))


def cajas_datos():
    """Se vuelve a leer solo cuando cambia algun archivo de la carpeta Maestro/cajas."""
    return _cajas(tuple(cj.archivos()))


def ha_de(lote_id):
    props, MAE = _CTX["props"], _CTX["MAE"]
    m = MAE[MAE["lote_id"] == lote_id] if len(MAE) else pd.DataFrame()
    if len(m) and m["ha_lote"].notna().any():
        return float(m["ha_lote"].dropna().iloc[0])
    return float(props.loc[props["lote_id"] == lote_id, "area_ha"].sum())


def resumen_cajas(lote_id):
    d = cajas_datos()
    return cj.resumen_lote(d, lote_id, ha_de(lote_id)) if not d.empty else None


PALETA = [AMBAR, VERDE, MORADO, "#4fc3f7", ROJO_V, NARANJA, "#e0d6cf", "#a1887f", "#7aa2ff", "#f48fb1"]
VAR_CAJA = {"TM": "TIMPSON", "AL": "ALLISON", "RG": "RED_GLOBE", "AC": "AUTUMN_CRISP", "CC": "COTTON_CANDY"}
POR_CAJAS = {"Variedad": "_var", "Lote": "_lote", "Calibre": "calibre", "Presentación": "presentacion", "Categoría": "_cat"}
MEDIDAS = {"Cajas equivalentes": "cajas_eq", "Kilos reales": "kg"}


def preparar_cajas(d):
    """Columnas legibles para agrupar: variedad, lote, categoria."""
    d = d.copy()
    nom = _CTX.get("VARIEDAD_NOMBRE", {})
    d["_var"] = d.get("variedad", pd.Series("", index=d.index)).astype(str).str.strip().map(
        lambda c: nom.get(VAR_CAJA.get(c, c), VAR_CAJA.get(c, c).title()) if c and c != "nan" else "Sin variedad")
    d["_lote"] = d["lote_id"].map(lambda l: f"L{num_lote(l)}" if isinstance(l, str) else "Ensayos")
    # lotes que no estan en el mapa (ej. 282 con FN y RR) son ensayos: se agrupan como "Ensayos"
    d.loc[d["lote_id"].isna(), "_var"] = "Ensayos"
    c = pd.to_numeric(d.get("categoria"), errors="coerce")
    d["_cat"] = c.map(lambda x: "—" if pd.isna(x) else f"Cat {x:g}")
    if "calibre" in d:
        d["calibre"] = d["calibre"].astype(str).str.strip().str.upper().replace({"NAN": "—", "": "—"})
    else:
        d["calibre"] = "—"
    if "presentacion" in d:
        d["presentacion"] = d["presentacion"].astype(str).str.strip().str.capitalize().replace({"Nan": "—", "": "—"})
    else:
        d["presentacion"] = "—"
    return d


def colores_de(col, cats):
    if col == "_cat":
        fijo = {"Cat 1": VERDE, "Cat 1.5": AMBAR, "Cat 2": ROJO_V}
        return {c: fijo.get(c, PALETA[i % len(PALETA)]) for i, c in enumerate(cats)}
    if col == "_lote" and "Ensayos" in cats:
        out = {c: PALETA[i % len(PALETA)] for i, c in enumerate([c for c in cats if c != "Ensayos"])}
        out["Ensayos"] = "#8a7f7b"
        return out
    if col == "_var":
        vc_ = _CTX.get("VARIEDAD_COLOR", {})
        inv = {v: k for k, v in _CTX.get("VARIEDAD_NOMBRE", {}).items()}
        return {c: "#8a7f7b" if c == "Ensayos" else vc_.get(inv.get(c, ""), PALETA[i % len(PALETA)]) for i, c in enumerate(cats)}
    return {c: PALETA[i % len(PALETA)] for i, c in enumerate(cats)}


def fmt_med(x, med):
    return f"{x / 1000:,.1f} t" if med == "kg" else f"{x:,.0f}"


def reparto(d, col, med, titulo, n=8):
    """Lista con barra: nombre · cantidad · % (como tu reporte de cajas)."""
    g = d.groupby(col)[med].sum().sort_values(ascending=False)
    tot = g.sum() or 1
    cols = colores_de(col, list(g.index))
    mx = g.max() or 1
    filas = "".join(
        f"<div class='rp'><span class='nm'>{escape(str(k))}</span><div class='bar'><i style='width:{v / mx * 100:.0f}%;"
        f"background:{cols[k]}'></i></div><span class='vl'>{fmt_med(v, med)}</span><span class='pc'>{v / tot * 100:.0f}%</span></div>"
        for k, v in g.head(n).items())
    return f"<div class='card'><div class='lbl'>{titulo}</div>{filas}</div>"


def apiladas_dias(d, col, med, alto=230):
    """Columnas por dia, partidas por la categoria elegida, con el total arriba."""
    t = d.groupby(["fecha", col])[med].sum().unstack(fill_value=0).sort_index()
    if t.empty:
        return
    orden = list(t.sum().sort_values(ascending=False).index)
    t = t[orden]
    cols = colores_de(col, orden)
    mx = t.sum(axis=1).max() or 1
    cs, ls = [], []
    for k, (f, fila) in enumerate(t.iterrows()):
        last = " last" if k == len(t) - 1 else ""
        segs = "".join(f"<div class='sg' title='{escape(str(c))}: {fmt_med(v, med)}' style='height:{v / mx * alto:.1f}px;"
                       f"background:{cols[c]}'></div>" for c, v in fila[::-1].items() if v > 0)
        cs.append(f"<div class='dcol{last}'><div class='cv' style='font-size:1.05rem'>{fmt_med(fila.sum(), med)}</div>"
                  f"<div class='cb c100' style='height:auto'>{segs}</div></div>")
        ls.append(f"<div class='dlab{last}'><div class='cd'>{dia(f)}</div></div>")
    ley = "<div class='dley'>" + "".join(f"<span><i style='background:{cols[c]}'></i>{escape(str(c))}</span>" for c in orden) + "</div>"
    html(f"<div class='dias'><div class='dias-in'><div class='dias-plot' style='height:{alto + 50}px'>{''.join(cs)}</div>"
         f"<div class='dias-lab'>{''.join(ls)}</div></div>{ley}</div>")


def controles_cajas(clave, opciones):
    c1, c2 = st.columns([2, 1], gap="medium")
    por = c1.segmented_control("Colorear por", opciones, key=f"cpor_{clave}", default=opciones[0]) or opciones[0]
    med = c2.segmented_control("Medir en", list(MEDIDAS), key=f"cmed_{clave}", default="Cajas equivalentes") or "Cajas equivalentes"
    return POR_CAJAS.get(por, POR_CAJAS[opciones[0]]), MEDIDAS.get(med, "cajas_eq")


def cajas_general(lotes_visibles):
    """Primera pantalla de Cosecha: cuantas cajas van en total, por variedad y por lote."""
    d = cajas_datos()
    if d.empty:
        return
    d = preparar_cajas(d[d["lote_id"].isin(set(lotes_visibles)) | d["lote_id"].isna()])
    if d.empty:
        return
    lotes_c = d["lote_id"].dropna().unique()
    ha = sum(ha_de(l) for l in lotes_c)
    tot = d["cajas_eq"].sum()
    band("Cajas producidas · campaña", f"del {d['fecha'].min():%d/%m} al {d['fecha'].max():%d/%m} · Excel diario de calidad")
    porvar = d[d["_var"] != "Ensayos"].groupby("_var")["cajas_eq"].sum().sort_values(ascending=False)
    ens = d[d["_var"] == "Ensayos"]
    cv = colores_de("_var", list(porvar.index))
    tiles([("Total cajas equivalentes", f"{tot:,.0f}", f"{d['kg'].sum() / 1000:,.1f} t · {d['fecha'].nunique()} días de packing",
            AMBAR, "caja"),
           ("Cajas por hectárea", f"{tot / ha:,.0f}" if ha else "—", f"{len(lotes_c)} lotes · {ha:,.1f} ha", "#fff", "area")]
          + [(f"{k}", f"{v:,.0f}", f"{v / tot * 100:.0f}% de las cajas", cv[k], "racimo") for k, v in porvar.items()]
          + ([("Ensayos", f"{ens['cajas_eq'].sum():,.0f}",
               " · ".join(f"{c} {x:,.0f}" for c, x in ens.groupby("variedad")["cajas_eq"].sum().items()), "#a89c97", "brote")]
             if len(ens) else []))
    with st.expander("📦  Ver detalle de cajas: por día, lote, calibre, categoría y presentación", expanded=False):
        col, med = controles_cajas("gen", ["Variedad", "Lote", "Calibre", "Presentación", "Categoría"])
        apiladas_dias(d, col, med)
        html("<div class='rp-grid'>" + reparto(d, "_lote", med, "Por lote") + reparto(d, "calibre", med, "Por calibre")
             + reparto(d, "_cat", med, "Por categoría") + reparto(d, "presentacion", med, "Por presentación") + "</div>")
        if len(ens):
            html(f"<div class='nota'>Ensayos: {ens['cajas_eq'].sum():,.0f} cajas de "
                 f"{', '.join(sorted(ens['lote'].astype(str).unique()))} (variedades "
                 f"{', '.join(sorted(ens['variedad'].astype(str).unique()))}); no tienen lote en el mapa.</div>")


# ---------------------------------------------------------------- vistas Packing y Directorio
def _hoy_txt():
    return f"plataforma · {pd.Timestamp.now():%d/%m/%Y %H:%M}"


def calidad_packing():
    """Categorizacion de campo (Pedregal) para la pestaña de calidad del reporte de packing."""
    props = _CTX["props"]
    var_de = {}
    for l, g in props.groupby("lote_id"):
        cods = [c for c in g["variedad"] if c]
        if cods:
            cod = max(set(cods), key=cods.count)
            var_de[l] = _CTX["VARIEDAD_NOMBRE"].get(cod, cod.title())
    return cj.filas_calidad(tabla("categoria"), var_de)


def vista_packing():
    """Primera vista: cajas producidas en packing por lote, packing, calibre, categoria, presentacion y cliente,
    y en otra pestaña la categoria de calidad de campo que viene de Pedregal."""
    import streamlit.components.v1 as components
    d = cajas_datos()
    if d.empty:
        st.info("Guarda el Excel diario de calidad en la carpeta Maestro\\cajas y presiona R.")
        return
    cal = calidad_packing()
    h = cj.html_packing(d, "light" if claro() else "dark", _hoy_txt(), cal).replace('<button class="tema"', '<button class="tema" style="display:none"')
    components.html(h, height=3150, scrolling=True)
    st.download_button("⬇  Descargar LOTE_PACKING.html (para subir a GitHub / Streamlit)",
                       cj.html_completo(cj.html_packing(d, "auto", f"actualizado {pd.Timestamp.now():%d/%m/%Y}", cal)),
                       file_name="LOTE_PACKING.html", mime="text/html")


def vista_directorio(lotes_visibles):
    """Consolidado de calidad de toda la cosecha, para presentar al directorio."""
    import streamlit.components.v1 as components
    est = {l: e for l, e in estado_lotes().items() if l in set(lotes_visibles) and e["estado"] in ("En cosecha", "Terminada")}
    if not est:
        st.info("Aún no hay lotes con cosecha.")
        return
    props = _CTX["props"]
    L = tabla("limpieza")
    lotes = []
    for l, e in est.items():
        cods = [c for c in props.loc[props["lote_id"] == l, "variedad"] if c]
        cod = max(set(cods), key=cods.count) if cods else ""
        ini = e["inicio"]
        if not L.empty and (L["lote_id"] == l).any():
            ini = L.loc[L["lote_id"] == l, "_fecha"].min()      # inicio real = primer dia de limpieza
        rc = resumen_cajas(l)
        lotes.append({"l": l, "corto": f"L{num_lote(l)}", "fundo": l.split(".")[0].title(),
                      "var": _CTX["VARIEDAD_NOMBRE"].get(cod, cod.title() or "—"), "var_cod": cod, "est": e["estado"],
                      "ini": ini, "fin": e["ultimo"], "dias": e["dias"], "ha": ha_de(l), "cajas": rc["total"] if rc else 0})
    # filtros: primero la variedad, luego (opcional) los lotes
    vars_ = sorted({x["var"] for x in lotes})
    c0, c1, c2 = st.columns([1.1, 3, 2.2], gap="medium")
    por = c0.segmented_control("Ver por", ["Variedad", "Lote"], key="dir_por", default="Variedad") or "Variedad"
    vsel = c1.segmented_control("Variedad", ["Todas"] + vars_, key="dir_var", default="Todas") or "Todas"
    opciones = [x["l"] for x in sorted(lotes, key=lambda x: x["corto"]) if vsel == "Todas" or x["var"] == vsel]
    lsel = c2.multiselect("Lote", opciones, key=f"dir_lotes_{vsel}", format_func=lambda l: f"Lote {num_lote(l)}",
                          placeholder="Todos los lotes")
    lotes = [x for x in lotes if x["l"] in (set(lsel) or set(opciones))]
    if not lotes:
        st.info("No hay lotes con esa variedad.")
        return
    T = {k: tabla(k) for k in cc.TABLAS}
    corte = max(x["fin"] for x in lotes)
    extra = (vsel if vsel != "Todas" else "Todas las variedades") + (f" · {len(lotes)} lotes" if len(lotes) > 1 else f" · Lote {lotes[0]['corto'][1:]}")
    n = len({x["var"] for x in lotes}) if por == "Variedad" else len(lotes)
    components.html(dr.html_directorio(lotes, T, "light" if claro() else "dark", corte, _hoy_txt(), extra,
                                       por="variedad" if por == "Variedad" else "lote"),
                    height=2350 + 150 * n, scrolling=True)


def cajas_detalle(lote_id):
    """Boton desplegable con las cajas del lote: por dia en barras y al lado el total y cajas por hectarea."""
    rc = resumen_cajas(lote_id)
    if not rc:
        if not cj.archivos():
            st.caption("📦 Cajas: guarda el Excel diario de calidad en la carpeta Maestro\\cajas y presiona R.")
        else:
            st.caption("📦 Este lote todavía no tiene cajas en el Excel diario de calidad.")
        return
    with st.expander(f"📦  Cajas producidas · {rc['total']:,.0f} cajas eq. · ver detalle por día", expanded=False):
        c1, c2 = st.columns([2.3, 1], gap="medium")
        with c1:
            dias = rc["dias"].sort_values("fecha")
            prom = dias["cajas_eq"].mean()
            barras_dias([{"fecha": d["fecha"], "v": d["cajas_eq"], "txt": f"{d['cajas_eq']:,.0f}",
                          "sub": f"<b>{d['kg'] / 1000:,.1f}</b> t",
                          "nivel": semaforo(d["cajas_eq"], prom, mayor_es_peor=False)} for _, d in dias.iterrows()],
                        prom=prom, prom_txt=f"promedio {prom:,.0f} / día", leyenda=False)
        with c2:
            html("<div class='tiles' style='grid-template-columns:1fr;margin-top:0'>"
                 + tile("Total cajas equivalentes", f"{rc['total']:,.0f}",
                        f"{rc['desde']:%d/%m} al {rc['hasta']:%d/%m} · {len(rc['dias'])} días de packing", AMBAR, "caja")
                 + tile("Cajas por hectárea", f"{rc['por_ha']:,.0f}" if rc["por_ha"] else "—",
                        f"sobre {rc['ha']:,.1f} ha del lote", "#fff", "area")
                 + tile("Kilos reales", f"{rc['kg'] / 1000:,.1f} t" if rc["kg"] else "—",
                        f"{rc['fisicas']:,.0f} cajas físicas" if rc["fisicas"] else "", "#fff", "balanza")
                 + "</div>")
        dl = preparar_cajas(cajas_datos())
        dl = dl[dl["lote_id"] == lote_id]
        if not dl.empty:
            html("<div class='pd-band' style='margin:20px 0 10px'>Detalle por día</div>")
            col, med = controles_cajas(f"l_{lote_id}", ["Calibre", "Presentación", "Categoría"])
            apiladas_dias(dl, col, med)
            html("<div class='rp-grid'>" + reparto(dl, "calibre", med, "Por calibre") + reparto(dl, "_cat", med, "Por categoría")
                 + reparto(dl, "presentacion", med, "Por presentación") + "</div>")
        html(f"<div class='nota'>Fuente: {escape(rc['archivo'])} (fecha de producción en planta). Las cajas de lotes "
             "mezclados (código AZ) se reparten mitad y mitad entre los dos lotes.</div>")


def ficha(lote_id):
    est = estado_lotes().get(lote_id)
    props, MAE = _CTX["props"], _CTX["MAE"]
    fundo = lote_id.split(".")[0]
    cu = props[props["lote_id"] == lote_id]
    codv = sorted({v for v in cu["variedad"] if v})
    vari = ", ".join(_CTX["VARIEDAD_NOMBRE"].get(v, v) for v in codv) or "Sin variedad"
    color_var = _CTX.get("VARIEDAD_COLOR", {}).get(codv[0] if codv else "", "#5b8c3a")
    m = MAE[MAE["lote_id"] == lote_id] if len(MAE) else pd.DataFrame()
    ha = m["ha_lote"].dropna().iloc[0] if len(m) and m["ha_lote"].notna().any() else cu["area_ha"].sum()
    cian = m["fecha_cianamida"].dropna().min() if len(m) else None
    estado = est["estado"] if est else "Sin cosecha"
    tiene_cian = bool(est) and cian is not None and pd.notna(cian)
    vivo = estado == "En cosecha"
    chip_est = {"En cosecha": ("#3a2a12", AMBAR), "Terminada": ("#12301f", VERDE), "Revisar": ("#2a1f38", MORADO),
                "Sin cosecha": (PANEL2, TXT2)}.get(estado, (PANEL2, TXT2))
    stats = [
        (f"{est['dias']}" if est else "—", "días de cosecha"),
        (f"{est['inicio']:%d/%m}" if est else "—", "inicio"),
        (f"{est['ultimo']:%d/%m}" if est else "—", "último registro" if vivo else "fin de cosecha"),
        (f"{(est['inicio'] - cian).days}" if tiene_cian else "—", "DDC al inicio"),
        (f"{(est['ultimo'] - cian).days}" if tiene_cian else "—", "DDC hoy" if vivo else "DDC al fin"),
        (f"{ha:,.1f}", "hectáreas"),
        (f"{len(cu)}", "cuarteles"),
    ]
    _, cus = filtro_actual(lote_id)
    rc = resumen_cajas(lote_id)
    caja_html = (f"<div class='st1'><span class='ic'>{ic('caja', 24, AMBAR)}</span><b style='color:{AMBAR}'>{rc['total']:,.0f}</b>"
                 f"<span>cajas eq. · {rc['por_ha']:,.0f}/ha</span></div>" if rc and rc["por_ha"] else
                 f"<div class='st1 pend'><span class='ic'>{ic('caja', 24, '#5a5250')}</span><b>—</b><span>cajas · sin datos</span></div>")
    dia_txt = f" · día {est['dias']}" if vivo else ""
    html(
        f"<div class='hero'><div class='hl'><div class='eyebrow'>Fundo {fundo.title()}</div>"
        f"<div class='n'>LOTE {num_lote(lote_id)}</div>"
        f"<div class='chips'><span class='chip2' style='background:{color_var};color:#fff'>{vari}</span>"
        f"<span class='chip2 {'vivo' if vivo else ''}' style='background:{chip_est[0]};color:{chip_est[1]}'>"
        f"{'<i></i>' if vivo else ''}{estado}{dia_txt}</span></div>"
        "<div class='sts'>" + "".join(f"<div class='st1'><span class='ic'>{ic_para(t, 24, '#ff8a8f')}</span><b>{v}</b><span>{t}</span></div>"
                                     for v, t in stats)
        + caja_html
        + f"</div></div><div class='pl'>{plano_svg(lote_id, marcados=cus)}"
        f"<div class='ley'><span><i style='background:{NARANJA}'></i>cosechado el último día</span>"
        f"<span><i style='background:#6b4a2a'></i>antes</span><span><i style='background:{BORDE}'></i>sin registros</span></div>"
        "</div></div>")


def plano_svg(lote_id, W=330, H=300, marcados=()):
    """Dibujo del lote con sus cuarteles (sin satelite), coloreado por actividad de cosecha."""
    feats = [f for f in _CTX["geo"]["features"] if f["properties"]["lote_id"] == lote_id]
    if not feats:
        return ""

    def anillos(f):
        g = f["geometry"]
        return g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]

    pts = [c for f in feats for r in anillos(f) for c in r]
    kx = math.cos(math.radians(sum(p[1] for p in pts) / len(pts)))
    xs, ys = [p[0] * kx for p in pts], [-p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    pad = 16
    s = min((W - 2 * pad) / ((max(xs) - x0) or 1e-9), (H - 2 * pad) / ((max(ys) - y0) or 1e-9))
    w, h = (max(xs) - x0) * s + 2 * pad, (max(ys) - y0) * s + 2 * pad
    pr = lambda c: ((c[0] * kx - x0) * s + pad, (-c[1] - y0) * s + pad)
    act = actividad_cuarteles(lote_id)
    PAL = {"hoy": NARANJA, "antes": "#6b4a2a", "no": BORDE}
    caminos, textos = [], []
    for f in feats:
        p = f["properties"]
        a = act.get(p["cuartel_id"])
        e = a[0] if a else "no"
        d = "".join("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in map(pr, r)) + "Z" for r in anillos(f))
        borde = "#ffffff" if p["cuartel_id"] in marcados else BG
        tip = f"Cuartel {p['cuartel']} · {p['area_ha']:.2f} ha · " + (f"último registro {a[1]:%d/%m}" if a else "sin registros")
        caminos.append(f"<path d='{d}' fill='{PAL[e]}' fill-rule='evenodd' stroke='{borde}' "
                       f"stroke-width='{3 if p['cuartel_id'] in marcados else 2}'><title>{escape(tip)}</title></path>")
        P = [pr(c) for c in anillos(f)[0][:-1]]
        cx, cy = sum(q[0] for q in P) / len(P), sum(q[1] for q in P) / len(P)
        textos.append(f"<text x='{cx:.0f}' y='{cy + 5:.0f}' text-anchor='middle' font-family='Inter,Segoe UI,sans-serif' "
                      f"font-weight='800' font-size='15' fill='#fff' style='pointer-events:none'>Ct {escape(str(p['cuartel']))}</text>")
    return (f"<svg width='{w:.0f}' height='{h:.0f}' viewBox='0 0 {w:.0f} {h:.0f}' role='img' "
            f"aria-label='Plano del lote {num_lote(lote_id)}'>" + "".join(caminos) + "".join(textos) + "</svg>")


def barra(lote_id):
    """Pestanas de evaluacion + filtros del lote. Devuelve la seccion elegida."""
    # fila 1: evaluaciones a lo ancho · fila 2: fecha y cuarteles (los cuarteles bajan de linea si son muchos)
    sec = st.segmented_control("Evaluación", SECCIONES, key="sec_cos") or "Limpieza"
    c2, c3 = st.columns([1, 3.2], gap="large", vertical_alignment="top")
    k = f"dias_cos_{lote_id}"
    dias_ = sorted(dias_lote(lote_id))
    if k in st.session_state:
        st.session_state[k] = [x for x in (st.session_state[k] or []) if x in dias_]
    sel = st.session_state.get(k) or []
    resumen = ("Toda la cosecha" if not sel or len(sel) == len(dias_) else
               (dia(sel[0]) if len(sel) == 1 else f"{len(sel)} días marcados"))

    def marcar(todos):
        st.session_state[k] = list(dias_) if todos else []

    with c2:
        html("<div class='lbl-f'>📅 Fechas</div>")
        with st.popover(f"{resumen}  ▾", use_container_width=True):
            b1, b2 = st.columns(2)
            b1.button("✔ Marcar todas", key=f"{k}_todas", on_click=marcar, args=(True,), use_container_width=True)
            b2.button("✕ Limpiar", key=f"{k}_nada", on_click=marcar, args=(False,), use_container_width=True,
                      help="Sin fechas marcadas se ve toda la cosecha")
            st.pills("Marca los días que quieres ver", dias_, selection_mode="multi", key=k,
                     format_func=lambda x: f"{x:%d/%m} {DIAS_CORTOS[x.weekday()]}")
    cus = sorted(_CTX["props"].loc[_CTX["props"]["lote_id"] == lote_id, "cuartel_id"])
    c3.pills("Cuarteles · sin marcar = todos", cus, selection_mode="multi", key=f"cu_cos_{lote_id}",
             format_func=lambda c: f"Ct {c.split('.')[-1]}")
    return sec


# ---------------------------------------------------------------- secciones
def seccion(lote_id, nombre):
    cod = _CTX["VAR_CU"].get(next(iter(_CTX["props"].loc[_CTX["props"]["lote_id"] == lote_id, "cuartel_id"]), ""), "")
    dias_, cus = filtro_actual(lote_id)
    quien = " · ".join(x for x in [
        texto_dias(dias_),
        ("cuarteles " + ", ".join(c.split(".")[-1] for c in cus)) if cus else "todos los cuarteles"] if x)
    band(f"{nombre} · Lote {num_lote(lote_id)}", quien)
    if nombre == "Limpieza":
        defectos(de_lote("limpieza", lote_id), "racimos-por-jaba", "racimos", True, clave="limpieza", lote_id=lote_id)
    elif nombre == "Descarte":
        c1, c2 = st.tabs(["Descarte de bayas", "Descarte de racimos"])
        with c1:
            m1, m2 = st.tabs(["Método nuevo · sobre bayas por jaba del lote", "Método tradicional · sobre bayas evaluadas"])
            with m1:
                vista_desc_bayas(lote_id)
            with m2:
                html("<div class='nota' style='margin:0 0 8px'>% de cada defecto = bayas con el defecto ÷ bayas evaluadas "
                     "en la jaba (n° de bayas por jaba de la cartilla), igual que el descarte de racimos.</div>")
                defectos(de_lote("desc_bayas", lote_id), "n-bayas-por-jaba", "bayas", False, "n-bayas-buenas",
                         clave="desc_bayas_trad", lote_id=lote_id)
            revision_cuadre(de_lote("desc_bayas", lote_id), "n-bayas-por-jaba", "n-bayas-buenas", "bayas",
                            ("desgrane-de-bayas",), "buenas + desgrane + defectos")
        with c2:
            defectos(de_lote("desc_racimos", lote_id), "racimos-por-jaba", "racimos", False, "n-racimos-buenos",
                     clave="desc_racimos", lote_id=lote_id)
            revision_cuadre(de_lote("desc_racimos", lote_id), "racimos-por-jaba", "n-racimos-buenos", "racimos",
                            (), "buenos + defectos")
    elif nombre == "Tiempos":
        vista_tiempos(de_lote("traza", lote_id))
    elif nombre == "Temperaturas":
        vista_temperaturas(de_lote("temp", lote_id))
    elif nombre in ("Pesos", "Peso de racimos"):
        vista_pesos(lote_id)
    elif nombre == "Brix":
        vista_brix(de_lote("brix", lote_id), cod)
    else:
        vista_categoria(por_origen(de_lote("categoria", lote_id)))


COL_ORIGEN = "datos-generales-origen"     # C.C. Campo / C.C. Packing: donde se evaluo con la misma cartilla


def por_origen(df, clave="origen_cos", etiqueta="Origen de la evaluación"):
    """Filtro Origen (Todos / C.C. Campo / C.C. Packing) de las cartillas de categorizacion y peso de racimos."""
    if df.empty or COL_ORIGEN not in df:
        return df
    val = st.segmented_control(etiqueta, ["Todos", "🌿 C.C. Campo", "📦 C.C. Packing"], key=clave,
                               default="Todos", help="Dónde se tomó la muestra con la misma cartilla: en campo o en packing") or "Todos"
    if val == "Todos":
        return df
    o = df[COL_ORIGEN].astype(str).str.strip().str.lower()
    return df[o.str.contains("packing" if "Packing" in val else "campo", na=False)]


def revision_cuadre(df, col_total, col_buenos, unidad, extras, regla):
    """Al final del descarte: muestras donde lo clasificado no suma el total (para corregirlas en la cartilla)."""
    r = cc.cuadre(df, col_total, col_buenos, extras)
    if r.empty:
        return
    mal = r[r["diferencia"].abs() > 0].sort_values(["fecha", "hora"])
    txt = lambda s: "" if s is None or (isinstance(s, float) and pd.isna(s)) else escape(str(s))
    n, m = len(r), len(mal)
    band("Revisión de muestras", f"cada muestra debe cumplir: {unidad} por jaba = {regla}")
    color = VERDE if m == 0 else (AMBAR if m / n <= .05 else ROJO_V)
    tiles([("Muestras revisadas", f"{n:,}", "con los filtros elegidos", "#fff", "lupa"),
           ("Bien clasificadas", f"{n - m:,}", fmtp((n - m) / n * 100) + " del total", VERDE, "check"),
           ("Por corregir", f"{m:,}", (f"{(mal['diferencia'] > 0).sum()} con {unidad} sin clasificar · "
                                       f"{(mal['diferencia'] < 0).sum()} clasificadas de más") if m else "todo cuadra", color, "alerta")])
    if not m:
        return
    filas = "".join(
        f"<tr><td><b>{x.fecha:%d/%m}</b></td><td>{txt(x.hora)[:5]}</td><td>{txt(x.cuartel)}</td>"
        f"<td>{txt(x.evaluador)}</td><td class='nr'>{x.total:,.0f}</td><td class='nr'>{x.clasificado:,.0f}</td>"
        f"<td class='nr'><b style='color:{AMBAR if x.diferencia > 0 else ROJO_V}'>{x.diferencia:+,.0f}</b></td>"
        f"<td style='color:var(--txt2)'>{'faltan clasificar' if x.diferencia > 0 else 'se clasificó de más'}</td></tr>"
        for x in mal.itertuples())
    with st.expander(f"⚠️  Ver las {m} muestras por corregir (fecha, cuartel, evaluador y diferencia)", expanded=m <= 8):
        html("<div class='card' style='overflow-x:auto'><table class='tpk'><thead><tr><th>Fecha</th><th>Hora</th><th>Cuartel</th>"
             f"<th>Evaluador</th><th class='nr'>Total {unidad}</th><th class='nr'>Clasificado</th><th class='nr'>Diferencia</th><th></th>"
             f"</tr></thead><tbody>{filas}</tbody></table></div>")


def sin_datos():
    st.info("Este lote no tiene registros de esta evaluación con los filtros elegidos.")


def color_calidad(v):
    return VERDE if v >= 92 else (AMBAR if v >= 88 else ROJO_V)


def filas_top(det, n=5):
    if det.empty:
        return "<div class='nota'>Sin defectos registrados.</div>"
    det = det[det["pct"] > 0].head(n)
    mx = det["pct"].max() or 1
    return "".join(
        f"<div class='tr'><b>{p:.1f}<small>%</small></b><div><div class='bar'><i style='width:{p / mx * 100:.0f}%;"
        f"background:linear-gradient(90deg,{AMBAR},{GC.get(g, ROJO_V)})'></i></div>"
        f"<span>{escape(str(d))}<em>{g.lower()}</em></span></div></div>"
        for d, p, g in zip(det["defecto"], det["pct"], det["grupo"]))


def vista_desc_bayas(lote_id):
    """Descarte de bayas: % de cada defecto sobre las bayas por jaba estimadas del lote (sin total)."""
    desc = de_lote("desc_bayas", lote_id)
    if desc.empty:
        return sin_datos()
    lote = lambda k: tabla(k)[tabla(k)["lote_id"] == lote_id] if not tabla(k).empty else pd.DataFrame()
    r = cc.descarte_bayas(desc, lote("peso"), lote("limpieza"), grupos())
    f1 = lambda x, d=1: "—" if x is None or pd.isna(x) else f"{x:,.{d}f}"
    tiles([("Bayas por racimo", f1(r["bayas_racimo"], 0), "promedio del lote · peso de racimos", "#fff", "racimo"),
           ("Racimos por jaba", f1(r["racimos_jaba"]), "promedio del lote · limpieza", "#fff", "jaba"),
           ("Bayas por jaba", f1(r["base"], 0), "bayas por racimo × racimos por jaba", AMBAR, "bayas"),
           ("Muestras", f"{r['muestras']:,}", "jabas evaluadas en descarte")])
    if r["base"] is None:
        st.warning("Para calcular el % falta el promedio de bayas por racimo (peso de racimos) o de racimos por "
                   "jaba (limpieza) de este lote.")
        return
    det = r["detalle"][r["detalle"]["pct"] > 0]
    band("% de cada defecto", "promedio por jaba del defecto ÷ bayas por jaba del lote")
    if det.empty:
        html("<div class='nota'>Sin defectos registrados.</div>")
        return
    mx = det["pct"].max() or 1
    filas = "".join(
        f"<div class='tr'><b>{p:.2f}<small>%</small></b><div><div class='bar'><i style='width:{p / mx * 100:.0f}%;"
        f"background:linear-gradient(90deg,{AMBAR},{GC.get(g, ROJO_V)})'></i></div>"
        f"<span>{escape(str(d))}<em>{g.lower()} · {pj:.1f} bayas por jaba</em></span></div></div>"
        for d, p, g, pj in zip(det["defecto"], det["pct"], det["grupo"], det["prom_jaba"]))
    html(f"<div class='card'>{filas}</div>")


def defectos(df, col_total, unidad, limpieza, col_buenos=None, clave="", lote_id=""):
    r = cc.desviacion(df, col_total, grupos(), col_buenos) if not df.empty else None
    if not r:
        return sin_datos()
    g = r["grupos"]
    etiqueta = "Calidad lograda" if limpieza else f"{unidad.capitalize()} sin defecto"
    html(
        f"<div class='duo'><div class='card'><div class='lbl' style='display:flex;align-items:center;gap:8px'>{ic('check', 24, color_calidad(r['calidad']))}{etiqueta}</div>"
        f"<div class='gauge' style='color:{color_calidad(r['calidad'])}'>{r['calidad']:.1f}%</div>"
        f"<div class='gsub'>Desviación total <b style='color:{ROJO_V}'>{r['desviacion']:.2f}%</b> · "
        f"{r['por_muestra']:.1f} {unidad}/jaba</div>"
        "<div class='g3'>" + "".join(f"<div>{ic({'Condición': 'alerta', 'Calidad': 'estrella', 'Plagas': 'bicho'}[k], 26, GC[k])}<span class='lbl'>{k}</span><b style='color:{GC[k]}'>{v:.1f}%</b></div>"
                                     for k, v in g.items()) + "</div></div>"
        f"<div class='card'><div class='lbl'>Top 5 más resaltantes · % de {unidad}</div>{filas_top(r['detalle'])}</div></div>")
    extras = [("Muestras", f"{r['muestras']:,}", f"{r['total']:,.0f} {unidad} evaluados")]
    if r.get("higiene_mala") is not None:
        extras.append(("Jabas con mala higiene", fmtp(r["higiene_mala"]), "distinto de 'Buena'",
                       ROJO_V if r["higiene_mala"] > 5 else "#fff"))
    if r.get("desgrane"):
        extras.append(("Desgrane", f"{r['desgrane'][0]:.1f}", f"bayas por muestra · máx {r['desgrane'][1]:.0f}"))
    if r.get("buenos") is not None:
        extras.append((f"{unidad.capitalize()} buenos (registro)", fmtp(r["buenos"]), "según la columna de buenos"))
    tiles(extras)

    dias = cc.por_dia(df, col_total, grupos(), col_buenos)
    if dias.empty:
        return
    dias = dias.sort_values("fecha")
    band("Desviación por día", "verde: mejor que el promedio del periodo · rojo: peor · la línea punteada es el promedio")
    barras_dias([{"fecha": d["fecha"], "v": d["desviacion"], "txt": f"{d['desviacion']:.1f}%",
                  "sub": f"{escape(str(d['top']))} <b>{d['top_pct']:.1f}%</b>",
                  "nivel": semaforo(d["desviacion"], r["desviacion"])} for _, d in dias.iterrows()],
                prom=r["desviacion"], prom_txt=f"promedio {r['desviacion']:.1f}%")
    detalle_dia(df, col_total, col_buenos, unidad, r["desviacion"], f"{clave}_{lote_id}")


SEMAFORO = {"bien": VERDE, "medio": AMBAR, "mal": ROJO_V}


def semaforo(v, prom, mayor_es_peor=True):
    if v is None or prom in (None, 0) or pd.isna(v):
        return "medio"
    r = v / prom
    if not mayor_es_peor:
        r = 1 / r if r else 9
    return "mal" if r > 1.1 else ("bien" if r < 0.9 else "medio")


def barras_dias(items, prom=None, prom_txt="", base=0.0, leyenda=True):
    """Columnas grandes por dia. items: fecha, v, txt (cifra sobre la barra), sub (texto bajo la fecha), nivel."""
    if not items:
        return
    ALTO = 150                                     # alto maximo de barra en px (el resto es la cifra)
    vals = [it["v"] for it in items if it["v"] is not None and pd.notna(it["v"])]
    mx = max(vals + ([prom] if prom else [])) if vals else 1
    rango = (mx - base) or 1
    alto = lambda v: max(6, (v - base) / rango * ALTO) if v is not None and pd.notna(v) else 4
    cols, labs = [], []
    for k, it in enumerate(items):
        last = " last" if k == len(items) - 1 else ""
        c = SEMAFORO.get(it.get("nivel"), "#8a7f7b")
        cols.append(f"<div class='dcol{last}'><div class='cv'>{it['txt']}</div>"
                    f"<div class='cb' style='height:{alto(it['v']):.0f}px;background:linear-gradient(180deg,{c},{c}cc)'></div></div>")
        labs.append(f"<div class='dlab{last}'><div class='cd'>{dia(it['fecha'])}</div><div class='ct'>{it.get('sub', '')}</div></div>")
    linea = (f"<div class='prom' style='bottom:{alto(prom):.0f}px'><span>{prom_txt}</span></div>"
             if prom is not None and pd.notna(prom) else "")
    ley = (f"<div class='dley'><span><i style='background:{VERDE}'></i>mejor que el promedio</span>"
           f"<span><i style='background:{AMBAR}'></i>en el promedio (±10%)</span>"
           f"<span><i style='background:{ROJO_V}'></i>peor que el promedio</span>"
           "<span>· el día con borde blanco es el último</span></div>") if leyenda else ""
    html(f"<div class='dias'><div class='dias-in'><div class='dias-plot'>{linea}{''.join(cols)}</div>"
         f"<div class='dias-lab'>{''.join(labs)}</div></div>{ley}</div>")


def barras_100(items, colores, alto=240):
    """Columnas 100% apiladas por dia. items: fecha, partes [(nombre, %)], sub. La primera parte va abajo."""
    if not items:
        return
    cols, labs = [], []
    for k, it in enumerate(items):
        last = " last" if k == len(items) - 1 else ""
        tot = sum(v for _, v in it["partes"] if v and pd.notna(v)) or 1
        segs = []
        for n, v in reversed(it["partes"]):
            v = v if v and pd.notna(v) else 0
            if v <= 0:
                continue
            h = v / tot * alto
            oscuro = n in ("Cat 1", "Cat 1.5", "Óptimo", "Tolerable")
            txt = (f"<span style='color:{'#120d0f' if oscuro else '#fff'}'>{v:.0f}%</span>" if h >= 22 else "")
            segs.append(f"<div class='sg' title='{n}: {v:.1f}%' style='height:{h:.1f}px;background:{colores.get(n, GRIS)}'>{txt}</div>")
        cols.append(f"<div class='dcol{last}'><div class='cb c100' style='height:{alto}px'>{''.join(segs)}</div></div>")
        labs.append(f"<div class='dlab{last}'><div class='cd'>{dia(it['fecha'])}</div><div class='ct'>{it.get('sub', '')}</div></div>")
    ley = "<div class='dley'>" + "".join(f"<span><i style='background:{c}'></i>{n}</span>" for n, c in colores.items()) + "</div>"
    html(f"<div class='dias'><div class='dias-in'><div class='dias-plot' style='height:{alto + 10}px'>{''.join(cols)}</div>"
         f"<div class='dias-lab'>{''.join(labs)}</div></div>{ley}</div>")


def detalle_dia(df, col_total, col_buenos, unidad, prom, clave):
    """Elegir un dia y ver su top 5 y la desviacion de cada cuartel."""
    fechas = sorted(pd.Series(df["_fecha"].dropna().dt.normalize().unique()))
    if not fechas:
        return
    fechas = [pd.Timestamp(f).date() for f in fechas]
    band("Detalle de un día", "elige la fecha")
    f = st.pills("Día", fechas, key=f"dd_{clave}_{len(fechas)}_{fechas[-1]}", default=fechas[-1],
                 format_func=lambda x: dia(x), label_visibility="collapsed") or fechas[-1]
    g = df[df["_fecha"].dt.normalize() == pd.Timestamp(f)]
    r = cc.desviacion(g, col_total, grupos(), col_buenos)
    if not r:
        return sin_datos()
    dif = r["desviacion"] - prom
    col_d = VERDE if dif < -0.1 * prom else (ROJO_V if dif > 0.1 * prom else AMBAR)
    porcu = []
    for cu, gg in g.groupby("cuartel_id"):
        rc = cc.desviacion(gg, col_total, grupos(), col_buenos)
        if rc:
            porcu.append((cu.split(".")[-1], rc["desviacion"], rc["muestras"]))
    porcu.sort(key=lambda x: -x[1])
    mxc = max((p[1] for p in porcu), default=1) or 1
    cu_html = "".join(
        f"<div class='cu'><span class='k'>Ct {escape(str(c))}</span><div class='bar'><i style='width:{v / mxc * 100:.0f}%;"
        f"background:{SEMAFORO[semaforo(v, prom)]}'></i></div><span class='v' style='color:{SEMAFORO[semaforo(v, prom)]}'>"
        f"{v:.1f}%</span></div>" for c, v, n in porcu) or "<div class='nota'>Sin cuartel identificado.</div>"
    html(
        f"<div class='dd'><div class='card'><div class='lbl'>{dia(f)}</div><div class='fecha'>{pd.Timestamp(f):%d/%m/%Y}</div>"
        f"<div class='gauge' style='font-size:4rem;color:{col_d}'>{r['desviacion']:.1f}%</div>"
        f"<div class='gsub'>desviación · calidad <b>{r['calidad']:.1f}%</b><br>{r['muestras']:,} muestras · "
        f"{r['por_muestra']:.1f} {unidad}/jaba</div>"
        f"<span class='delta' style='background:{col_d}22;color:{col_d}'>{'+' if dif >= 0 else ''}{dif:.1f} pts vs. promedio</span></div>"
        f"<div class='card'><div class='lbl'>Top 5 del día</div>{filas_top(r['detalle'])}</div>"
        f"<div class='card'><div class='lbl'>Desviación por cuartel</div>{cu_html}</div></div>")


def barras_plotly(x, y, textos, colores, alto=320, hover="%{x}: %{y}<extra></extra>", custom=None):
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=colores, marker_line_width=0, text=textos, textposition="outside",
                           textfont=dict(size=17, color="#ffffff"), customdata=custom, hovertemplate=hover))
    fig.update_layout(height=alto, margin=dict(l=0, r=0, t=36, b=0), bargap=0.25,
                      yaxis=dict(visible=False, range=[0, (max(y) if len(y) else 1) * 1.3 or 1]),
                      xaxis=dict(type="category", categoryorder="array", categoryarray=list(x),
                                 tickfont=dict(size=15, color=TXT3), showgrid=False))
    return fig


ICO_JABA = ("<svg width='74' height='60' viewBox='0 0 74 60' fill='none' stroke='currentColor' stroke-width='3' aria-hidden='true'>"
            "<path d='M6 16h62l-6 40H12z'/><path d='M4 16h66'/><path d='M14 28h46M16 40h42M27 16v40M47 16v40'/>"
            "<circle cx='22' cy='9' r='5' fill='currentColor'/><circle cx='33' cy='7' r='5' fill='currentColor'/>"
            "<circle cx='44' cy='9' r='5' fill='currentColor'/><circle cx='54' cy='10' r='4' fill='currentColor'/></svg>")
ICO_RACIMO = ("<svg width='44' height='58' viewBox='0 0 44 58' fill='currentColor' aria-hidden='true'>"
              "<path d='M22 2v8M22 6c5-4 11-4 15-1' stroke='currentColor' stroke-width='3' fill='none' stroke-linecap='round'/>"
              + "".join(f"<circle cx='{x}' cy='{y}' r='6.2'/>" for x, y in
                        [(10, 16), (22, 15), (34, 16), (16, 27), (28, 27), (10, 38), (22, 38), (34, 37), (16, 48), (28, 48), (22, 56)])
              + "</svg>")
ICO_BAYA = ("<svg width='34' height='34' viewBox='0 0 34 34' aria-hidden='true'><circle cx='17' cy='17' r='14' fill='currentColor'/>"
            "<circle cx='12' cy='12' r='4' fill='#fff' opacity='.35'/></svg>")


def vista_pesos(lote_id):
    """Pesos del lote en cadena: jaba -> racimo -> baya, y luego el detalle de cada uno."""
    J, P = de_lote("jabas", lote_id), de_lote("peso", lote_id)
    P = por_origen(P, "origen_peso", "Origen del peso de racimos (no cambia las jabas)")   # jabas no tienen origen
    rj = cc.peso_jaba(J) if not J.empty else None
    rp = cc.peso(P) if not P.empty else None
    if not rj and not rp:
        return sin_datos()
    f = lambda x, d: "—" if x is None or pd.isna(x) else f"{x:,.{d}f}"
    paso = lambda ico, color, eti, val, uni, sub: (
        f"<div class='eslabon'><div class='ico' style='color:{color}'>{ico}</div><div class='lbl'>{eti}</div>"
        f"<div class='pv'>{val}<small>{uni}</small></div><div class='ps'>{sub}</div></div>")
    flecha = lambda t: f"<div class='flecha'><span>{t}</span></div>"
    j_sub = (f"<b>{f(rj['racimos'], 1)}</b> racimos por jaba<br>{rj['muestras']:,} jabas pesadas" if rj else "sin pesadas de jaba")
    r_sub = (f"medido en <b>{rp['muestras']:,}</b> racimos" if rp else "sin peso de racimos")
    if rj and pd.notna(rj.get("kg_racimo")):
        r_sub += f"<br>desde la jaba: <b>{rj['kg_racimo']:.2f} kg</b>"
    html("<div class='cadena'>"
         + paso(ICO_JABA, NARANJA, "Jaba", f(rj["peso"], 2) if rj else "—", " kg", j_sub)
         + flecha(f"÷ {f(rj['racimos'], 1)} racimos" if rj else "")
         + paso(ICO_RACIMO, "#b9467a", "Racimo", f(rp["peso"], 3) if rp else "—", " kg", r_sub)
         + flecha(f"÷ {f(rp['bayas'], 0)} bayas" if rp else "")
         + paso(ICO_BAYA, VERDE, "Baya", f(rp["peso_baya_g"], 2) if rp and rp["peso_baya_g"] else "—", " g",
                f"<b>{f(rp['bayas'], 0)}</b> bayas por racimo<br>peso de racimo ÷ n° de bayas" if rp else "")
         + "</div>")
    if rj:
        vista_jaba(J, rj)
    if rp:
        band("Peso de racimo")
        vista_peso(P)


def vista_jaba(J, r):
    band("Peso de jaba", f"{r['muestras']:,} jabas · de {r['p_min']:.2f} a {r['p_max']:.2f} kg")
    c1, c2 = st.columns([1.5, 1], gap="medium")
    with c1:
        v = r["valores"]
        paso_b = 0.5
        lo, hi = math.floor(v.min() / paso_b) * paso_b, math.ceil(v.max() / paso_b) * paso_b + paso_b
        bins = [lo + i * paso_b for i in range(int(round((hi - lo) / paso_b)))]
        cuenta = pd.cut(v, bins + [bins[-1] + paso_b], right=False).value_counts(sort=False)
        pct = (cuenta / cuenta.sum() * 100).values
        etiquetas = [f"{b:.1f}" for b in bins]
        prom_bin = math.floor(r["peso"] / paso_b) * paso_b
        colores = [NARANJA if abs(b - prom_bin) < 1e-9 else "#6b4a2a" for b in bins]
        html(f"<div class='nota' style='margin:0 0 4px'>Distribución de jabas por peso (kg) · en naranja el rango del promedio</div>")
        graf(barras_plotly(etiquetas, list(pct), [f"<b>{p:.0f}%</b>" if p >= 1 else "" for p in pct], colores, alto=300,
                           hover="%{x} kg: %{y:.1f}% de las jabas<extra></extra>"))
    with c2:
        pc = r.get("por_cuartel")
        if pc is not None and len(pc):
            mx = pc["peso"].max() or 1
            mn = min(pc["peso"].min(), r["peso"]) * 0.9
            filas = "".join(
                f"<div class='cu'><span class='k'>Ct {escape(str(c).split('.')[-1])}</span><div class='bar'><i style='width:"
                f"{(p - mn) / ((mx - mn) or 1) * 100:.0f}%;background:{SEMAFORO[semaforo(p, r['peso'], False)]}'></i></div>"
                f"<span class='v' style='color:{SEMAFORO[semaforo(p, r['peso'], False)]}'>{p:.2f}</span></div>"
                for c, p in zip(pc["cuartel_id"], pc["peso"]))
            html(f"<div class='card'><div class='lbl'>Peso de jaba por cuartel · kg</div>{filas}</div>")
        pt = r.get("por_turno")
        if pt is not None and len(pt) > 1:
            tiles([(f"Turno {g.lower()}", f"{m:.2f} kg", f"{n:,} jabas") for g, m, n in zip(pt["grupo"], pt["mean"], pt["count"])])
    dias = cc.peso_jaba_por_dia(J)
    if dias.empty:
        return
    band("Peso de jaba por día", "verde: más pesada que el promedio · rojo: más liviana")
    barras_dias([{"fecha": d["fecha"], "v": d["peso"], "txt": f"{d['peso']:.2f}",
                  "sub": f"<b>{d['racimos']:.1f}</b> racimos/jaba · {d['muestras']} jabas",
                  "nivel": semaforo(d["peso"], r["peso"], mayor_es_peor=False)} for _, d in dias.sort_values("fecha").iterrows()],
                prom=r["peso"], prom_txt=f"promedio {r['peso']:.2f} kg", base=min(dias["peso"].min(), r["peso"]) * 0.8)


def vista_peso(df):
    r = cc.peso(df) if not df.empty else None
    if not r:
        return sin_datos()
    tiles([("Rango de peso de racimo", f"{r['p_min']:.2f}–{r['p_max']:.2f}", "kg"),
           ("Largo de raquis", f"{r['raquis']:.1f}" if r["raquis"] is not None and pd.notna(r["raquis"]) else "—", "promedio")])
    c1, c2 = st.columns(2, gap="medium")
    for col, clave, titulo in ((c1, "por_calibre", "Por calibre"), (c2, "por_tipo", "Por tipo de racimo")):
        t = r.get(clave)
        if t is None or t.empty:
            continue
        with col:
            band(titulo, "peso promedio de racimo y peso de baya")
            graf(barras_plotly(t["grupo"].astype(str), t["peso"],
                               [f"<b>{p:.2f} kg</b><br>{b:.1f} g/baya" for p, b in zip(t["peso"], t["peso_baya_g"])],
                               AMBAR, hover="%{x}: %{y:.3f} kg · %{customdata} racimos<extra></extra>", custom=t["n"]))
    dias = cc.peso_por_dia(df)
    if dias.empty:
        return
    band("Peso de racimo por día", "verde: más pesado que el promedio · rojo: más liviano")
    barras_dias([{"fecha": d["fecha"], "v": d["peso"], "txt": f"{d['peso']:.2f}",
                  "sub": f"<b>{d['bayas']:.0f}</b> bayas · <b>{d['peso_baya_g']:.1f} g</b>/baya",
                  "nivel": semaforo(d["peso"], r["peso"], mayor_es_peor=False)} for _, d in dias.sort_values("fecha").iterrows()],
                prom=r["peso"], prom_txt=f"promedio {r['peso']:.2f} kg", base=min(dias["peso"].min(), r["peso"]) * 0.7)


def vista_brix(df, variedad_cod):
    r = cc.brix(df, variedad_cod) if not df.empty else None
    if not r:
        return sin_datos()
    tiles([("Bajo", fmtp(r["bajo"]), f"menos de {r['tol']}°", ROJO_V),
           ("Tolerable", fmtp(r["tolerable"]), f"{r['tol']}–{r['opt'] - 0.1:.1f}°", AMBAR),
           ("Óptimo", fmtp(r["optimo"]), f"{r['opt']}–20.9°", VERDE),
           ("Exceso", fmtp(r["exceso"]), "21° o más", ROJO_V)])
    tiles([("Promedio", f"{r['prom']:.1f}°", f"{r['muestras']:,} mediciones"), ("Moda", f"{r['moda']:.1f}°", ""),
           ("Máximo", f"{r['max']:.1f}°", ""), ("Mínimo", f"{r['min']:.1f}°", "")])
    col_z = {"bajo": ROJO_V, "tolerable": AMBAR, "optimo": VERDE, "exceso": ROJO_V}
    band("Distribución por rango de °Brix", "rojo bajo o exceso · ámbar tolerable · verde óptimo")
    graf(barras_plotly([h[0] for h in r["hist"]], [h[1] for h in r["hist"]],
                       [f"<b>{h[1]:.1f}%</b>" if h[1] else "" for h in r["hist"]], [col_z[h[2]] for h in r["hist"]],
                       alto=340, hover="%{x}: %{y:.1f}%<extra></extra>"))
    dias = cc.brix_por_dia(df, variedad_cod)
    if dias.empty:
        return
    band("°Brix por día", "% de mediciones en óptimo, tolerable y bajo")
    barras_100([{"fecha": d["fecha"], "partes": [("Óptimo", d["optimo"]), ("Tolerable", d["tolerable"]), ("Bajo", d["bajo"])],
                 "sub": f"promedio <b>{d['prom']:.1f}°</b> · {d['muestras']} med."} for _, d in dias.sort_values("fecha").iterrows()],
               {"Óptimo": VERDE, "Tolerable": AMBAR, "Bajo": ROJO_V})


FASE_COLOR = {"Campo": VERDE, "Carga": AMBAR, "Traslado": NARANJA, "Acopio": MORADO}


def dur(m):
    """Minutos -> '24 min' o '2 h 05'."""
    if m is None or pd.isna(m):
        return "—"
    m = int(round(m))
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60:02d}"


def dur_big(m):
    """Para cifras grandes: '2<small>h</small> 05<small>min</small>'."""
    if m is None or pd.isna(m):
        return "—"
    m = int(round(m))
    return f"{m}<small>min</small>" if m < 60 else f"{m // 60}<small>h</small> {m % 60:02d}<small>min</small>"


def vista_tiempos(df):
    r = cc.tiempos(df) if not df.empty else None
    if not r:
        return sin_datos()
    w, tr = r["viajes"], r["tramos"]
    # ----- cifra principal: cosecha -> recepcion, partida en dos
    html("<div class='cadena tiempos'>"
         f"<div class='eslabon'><div class='ico' style='color:{AMBAR}'>{ic('reloj', 54, AMBAR, 1.6)}</div>"
         f"<div class='lbl'>Cosecha → recepción · promedio</div><div class='pv'>{dur_big(r['total'])}</div>"
         f"<div class='ps'>de <b>{dur(r['t_min'])}</b> a <b>{dur(r['t_max'])}</b> · {r['n_total']} viajes completos · "
         f"{r['jabas']} jabas</div></div>"
         "<div class='flecha'><span>se divide en</span></div>"
         f"<div class='eslabon'><div class='ico' style='color:{VERDE}'>{ICO_RACIMO}</div>"
         f"<div class='lbl'>Cosecha → acopio</div><div class='pv' style='font-size:clamp(2.4rem,4vw,3.6rem)'>{dur_big(r['cos_acopio'])}</div>"
         "<div class='ps'>puntos 1 → 9</div></div>"
         "<div class='flecha'><span>+</span></div>"
         f"<div class='eslabon'><div class='ico' style='color:{NARANJA}'>{ic('camion', 54, NARANJA, 1.6)}</div>"
         f"<div class='lbl'>Acopio → recepción</div><div class='pv' style='font-size:clamp(2.4rem,4vw,3.6rem)'>{dur_big(r['acopio_rec'])}</div>"
         "<div class='ps'>puntos 9 → 11</div></div></div>")
    fu = r.get("fuentes", {})
    if fu.get("comentario") or fu.get("campo hora"):
        html(f"<div class='nota'>Hora usada: <b>{fu.get('campo hora', 0):,}</b> registros con el campo de hora real · "
             f"<b>{fu.get('comentario', 0):,}</b> con la hora escrita en comentarios · {fu.get('app', 0):,} con la hora "
             "automática del app.</div>")
    # ----- recorrido de la jaba: cada tramo con ancho segun su tiempo promedio
    t = tr.dropna(subset=["prom"])
    if len(t):
        suma = t["prom"].sum() or 1
        lento = t.loc[t["prom"].idxmax()]
        segs = "".join(
            f"<div class='seg' style='flex:{max(p, suma * 0.025):.2f};background:{FASE_COLOR[f]}' "
            f"title='{a} → {b} · {escape(n)}: {dur(p)} promedio'><span>{dur(p) if p / suma >= 0.07 else ''}</span></div>"
            for a, b, n, f, p in zip(t["de"], t["a"], t["tramo"], t["fase"], t["prom"]))
        band("Recorrido de la jaba", "cada tramo es tan largo como su tiempo promedio · pasa el mouse para ver el detalle")
        ley = "".join(f"<span><i style='background:{c}'></i>{n}</span>" for n, c in FASE_COLOR.items())
        mx = t["max"].max() or 1
        filas = "".join(
            f"<div class='tramo{' lento' if n == lento['tramo'] else ''}'><span class='pp'>{a} → {b}</span>"
            f"<span class='nm'><i style='background:{FASE_COLOR[f]}'></i>{escape(n)}"
            f"{'<em>el más largo</em>' if n == lento['tramo'] else ''}</span>"
            f"<div class='bar'><i style='width:{(p or 0) / mx * 100:.0f}%;background:{FASE_COLOR[f]}'></i>"
            f"<b style='left:{(m or 0) / mx * 100:.0f}%' title='máximo {dur(m)}'></b></div>"
            f"<span class='pr'>{dur(p)}</span><span class='mx'>máx {dur(m)}</span></div>"
            for a, b, n, f, p, m in zip(tr["de"], tr["a"], tr["tramo"], tr["fase"], tr["prom"], tr["max"]))
        paradas = "".join(f"<span style='flex:{max(p, suma * 0.025):.2f}' title='{cc.PUNTOS.get(a, a)} → {cc.PUNTOS.get(b, b)}'>"
                          f"{a}→{b}</span>" for a, b, p in zip(t["de"], t["a"], t["prom"]))
        html(f"<div class='card'><div class='ruta'>{segs}</div><div class='paradas'>{paradas}</div>"
             f"<div class='dley' style='margin:6px 0 18px'>{ley}<span>· 1 = cosecha · 11 = llegada a recepción</span></div>"
             f"<div class='tramos'>{filas}</div>"
             "<div class='nota'>La barra es el promedio y la rayita blanca el máximo de cada tramo.</div></div>")
    # ----- por dia
    pdia = r.get("por_dia")
    if pdia is not None and len(pdia):
        band("Cosecha → recepción por día", "verde: más rápido que el promedio · rojo: más lento")
        barras_dias([{"fecha": d["fecha"], "v": d["total"], "txt": dur(d["total"]),
                      "sub": f"máx <b>{dur(d['t_max'])}</b> · {d['n']} viajes",
                      "nivel": semaforo(d["total"], r["total"])} for _, d in pdia.sort_values("fecha").iterrows()],
                    prom=r["total"], prom_txt=f"promedio {dur(r['total'])}")
    # ----- jabas mas lentas (el codigo de la jaba permite rastrearla)
    if "total" in w and w["total"].notna().any():
        nombres = [n for _, _, n, _ in cc.TRAMOS if n in w]
        top = w.dropna(subset=["total"]).nlargest(4, "total")
        tarjetas = ""
        for _, j in top.iterrows():
            peor = max(((n, j[n]) for n in nombres if pd.notna(j[n])), key=lambda x: x[1], default=(None, None))
            tarjetas += (f"<div class='jaba'><div class='cod'>{ic('jaba', 22, AMBAR)}Jaba <b>{escape(str(j['jaba']))}</b></div>"
                         f"<div class='tt' style='color:{SEMAFORO[semaforo(j['total'], r['total'])]}'>{dur(j['total'])}</div>"
                         f"<div class='ps'>{dia(j['fecha'])} · cosechada {j[1]:%H:%M} → recepción {j[11]:%H:%M}</div>"
                         + (f"<div class='ps'>tramo más largo: <b>{escape(peor[0])}</b> {dur(peor[1])}</div>" if peor[0] else "")
                         + "</div>")
        band("Jabas más lentas", "con su código para rastrearlas")
        html(f"<div class='jabas'>{tarjetas}</div>")


def color_temp(t, lo=18.0, hi=34.0):
    """Escala de calor: verde (fresco) -> ambar -> rojo (caliente). No es un limite de alerta."""
    if t is None or pd.isna(t):
        return BORDE
    x = max(0.0, min(1.0, (t - lo) / (hi - lo)))
    pts = [(0, (62, 207, 122)), (0.5, (255, 181, 71)), (1, (255, 90, 95))]
    for (a, ca), (b, cb) in zip(pts, pts[1:]):
        if x <= b:
            k = (x - a) / (b - a)
            return "#%02x%02x%02x" % tuple(round(ca[i] + (cb[i] - ca[i]) * k) for i in range(3))
    return ROJO_V


def hora_txt(h):
    h = int(h)
    return f"{(h % 12) or 12}{'am' if h < 12 else 'pm'}"


def vista_temperaturas(df):
    r = cc.temperaturas(df) if not df.empty else None
    if not r:
        return sin_datos()
    cp, ca = color_temp(r["pulpa"]), color_temp(r["ambiente"])
    mx = r["max_cuando"]
    cuando = f"{dia(mx[0])}{f' · {hora_txt(mx[1])}' if mx and pd.notna(mx[1]) else ''}" if mx and pd.notna(mx[0]) else ""
    termo = lambda t, c: (f"<div class='termo'><div class='tubo'><i style='height:{max(8, min(100, (t - 10) / 30 * 100)):.0f}%;"
                          f"background:{c}'></i></div><div class='bulbo' style='background:{c}'></div></div>")
    html("<div class='cadena temp'>"
         f"<div class='eslabon tflex'>{termo(r['pulpa'], cp)}<div><div class='lbl'>Pulpa · promedio</div>"
         f"<div class='pv' style='color:{cp}'>{r['pulpa']:.1f}<small>°C</small></div>"
         f"<div class='ps'>de <b>{r['p_min']:.1f}°</b> a <b>{r['p_max']:.1f}°</b> · {r['muestras']} mediciones</div></div></div>"
         f"<div class='flecha'><span>{'+' if r['dif'] >= 0 else ''}{r['dif']:.1f}° ambiente vs pulpa</span></div>"
         f"<div class='eslabon tflex'>{termo(r['ambiente'], ca)}<div><div class='lbl'>Ambiente · promedio</div>"
         f"<div class='pv' style='color:{ca}'>{r['ambiente']:.1f}<small>°C</small></div>"
         f"<div class='ps'>máxima <b>{r['a_max']:.1f}°</b></div></div></div>"
         f"<div class='flecha'><span>pico</span></div>"
         f"<div class='eslabon'><div class='ico' style='color:{ROJO_V}'>{ic('alerta', 54, ROJO_V, 1.6)}</div>"
         f"<div class='lbl'>Pulpa más caliente</div><div class='pv' style='color:{color_temp(r['p_max'])}'>{r['p_max']:.1f}"
         f"<small>°C</small></div><div class='ps'>{cuando}</div></div>"
         "</div>")
    ph = r["por_hora"].sort_values("_h")
    if len(ph):
        band("Temperatura por hora", "promedio de todas las mediciones del periodo a cada hora")
        x = [hora_txt(h) for h in ph["_h"]]
        fig = go.Figure()
        fig.add_scatter(x=x, y=ph["ambiente"], name="Ambiente", mode="lines+markers+text", line=dict(color=TXT2, width=3, dash="dot"),
                        marker=dict(size=9), text=[f"{t:.1f}°" for t in ph["ambiente"]], textposition="top center",
                        textfont=dict(color=TXT2, size=13), hovertemplate="%{x} · ambiente %{y:.1f}°C<extra></extra>")
        fig.add_scatter(x=x, y=ph["pulpa"], name="Pulpa", mode="lines+markers+text", line=dict(color=NARANJA, width=4),
                        marker=dict(size=13, color=[color_temp(t) for t in ph["pulpa"]], line=dict(color=BG, width=2)),
                        text=[f"<b>{t:.1f}°</b>" for t in ph["pulpa"]], textposition="bottom center",
                        textfont=dict(color="#fff", size=15), customdata=ph["n"],
                        hovertemplate="%{x} · pulpa %{y:.1f}°C · %{customdata} med.<extra></extra>")
        lo = min(ph["pulpa"].min(), ph["ambiente"].min()) - 3
        hi = max(ph["pulpa"].max(), ph["ambiente"].max()) + 3
        fig.update_layout(height=330, margin=dict(l=0, r=0, t=20, b=0), yaxis=dict(range=[lo, hi], ticksuffix="°"),
                          xaxis=dict(type="category", tickfont=dict(size=15, color=TXT3), showgrid=False),
                          legend=dict(orientation="h", y=1.12, x=0, font=dict(size=14, color=TXT3)))
        graf(fig)
    pd_ = r["por_dia"].sort_values("_f")
    if len(pd_):
        band("Pulpa por día", "verde: más fresca que el promedio · rojo: más caliente")
        barras_dias([{"fecha": d["_f"], "v": d["pulpa"], "txt": f"{d['pulpa']:.1f}°",
                      "sub": f"ambiente <b>{d['ambiente']:.1f}°</b> · máx <b>{d['p_max']:.1f}°</b>",
                      "nivel": semaforo(d["pulpa"], r["pulpa"])} for _, d in pd_.iterrows()],
                    prom=r["pulpa"], prom_txt=f"promedio {r['pulpa']:.1f}°", base=min(pd_["pulpa"].min(), r["pulpa"]) - 4)
    dh = r["dia_hora"]
    if len(dh):
        # llaves normalizadas (Timestamp, float): numpy y pandas no comparan igual sus fechas en un dict
        val = {(pd.Timestamp(f), float(h)): t for f, h, t in zip(dh["_f"], dh["_h"], dh["_p"]) if pd.notna(t)}
        horas = sorted({h for _, h in val})
        dias_ = sorted({f for f, _ in val})
        cab = "<div></div>" + "".join(f"<div class='hh'>{hora_txt(h)}</div>" for h in horas)
        filas = "".join(
            f"<div class='hd'>{dia(f)}</div>" + "".join(
                (f"<div class='cel' style='background:{color_temp(val[(f, h)])}' title='{dia(f)} {hora_txt(h)}: {val[(f, h)]:.1f}°C'>"
                 f"{val[(f, h)]:.1f}°</div>") if (f, h) in val else "<div class='cel vacia'></div>" for h in horas)
            for f in dias_)
        band("Mapa de calor de la pulpa", "cada casilla es el promedio de ese día a esa hora · verde fresco, rojo caliente")
        html(f"<div class='card' style='overflow-x:auto'><div class='calor' style='grid-template-columns:90px repeat({len(horas)}, minmax(64px,1fr))'>"
             f"{cab}{filas}</div><div class='dley' style='margin-top:14px'>"
             + "".join(f"<span><i style='background:{color_temp(t)}'></i>{t}°</span>" for t in (20, 24, 28, 32))
             + "</div></div>")


COLOR_BAYA = {"Verde": "#7fbf4d", "Cremoso": "#d9d77a", "Ámbar": "#e2a83a", "Full color oscuro": "#6a1640",
              "Full color claro": "#a8285c", "Aureola cremosa r oscuro": "#b8306a", "Aureola cremosa r claro": "#d9608a",
              "Aureola verde": "#9bb85a", "Color intermedio": "#e07aa6", "Falta de color": "#cfd9c8"}
COL_CAT = {"Cat 1 Premium": "#1f8f4e", "Cat 1": VERDE, "Cat 1.5": AMBAR, "Cat 2": ROJO_V, "Descarte": "#0a0708"}


def vista_categoria(df):
    r = cc.categoria(df) if not df.empty else None
    if not r:
        return sin_datos()
    cats = [(n, v) for n, v in r["categorias"] if v > 0 or n != "Cat 1 Premium"]
    tiles([(n, fmtp(v), "", COL_CAT.get(n, "#fff") if n != "Descarte" else "#fff", "tacho" if n == "Descarte" else "medalla")
           for n, v in cats])
    fig = go.Figure()
    for n, v in cats:
        fig.add_bar(y=["Categoría"], x=[v], orientation="h", name=n, marker_color=COL_CAT.get(n, GRIS),
                    marker_line=dict(color=BORDE if n == "Descarte" else COL_CAT.get(n, GRIS), width=1),
                    text=f"<b>{n}  {v:.1f}%</b>" if v >= 8 else "", textposition="inside", insidetextanchor="middle",
                    textfont=dict(color="#120d0f" if n in ("Cat 1", "Cat 1.5") else "#ffffff", size=16),
                    hovertemplate=f"{n}: {v:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack", height=90, margin=dict(l=0, r=0, t=14, b=0), showlegend=False,
                      xaxis=dict(visible=False, range=[0, 100]), yaxis=dict(visible=False))
    graf(fig)
    html(f"<div class='nota'>{r['muestras']} muestras · {r['racimos_prom']:.1f} racimos por muestra</div>")

    c1, c2 = st.columns([1, 1.6], gap="medium")
    with c1:
        band("Color", f"uva {r['tipo_color']} · el tamaño de cada baya es su %")
        mx = max((v for _, v in r["color"]), default=1) or 1
        html("<div class='card'><div class='pd-bayas'>" + "".join(
            f"<div class='pd-baya'><div class='c' style='width:{max(14, 100 * (v / mx) ** .5):.0f}px;"
            f"height:{max(14, 100 * (v / mx) ** .5):.0f}px;background:{COLOR_BAYA.get(n, '#bbb')}'></div>"
            f"<b>{v:.1f}%</b><span>{n}</span></div>" for n, v in r["color"]) + "</div></div>")
    with c2:
        band("Calibre", "la barra es el % de racimos · la baya crece con el diámetro")
        mxc = max((v for _, _, v in r["calibre"]), default=1) or 1
        html("<div class='card'><div class='pd-bayas'>" + "".join(
            f"<div class='pd-baya'><b style='color:{AMBAR if v == mxc else '#fff'}'>{v:.1f}%</b>"
            f"<div style='width:34px;height:{max(3, 130 * v / mxc):.0f}px;background:{AMBAR if v == mxc else '#5a4a3a'};border-radius:7px'></div>"
            f"<div class='c' style='width:{2 * (14 + i * 2)}px;height:{2 * (14 + i * 2)}px;background:#d9d77a'></div>"
            f"<b>{lab}</b><span>{rng}</span></div>" for i, (lab, rng, v) in enumerate(r["calibre"])) + "</div></div>")
    if r["raquis"]:
        band("Raquis")
        tiles([(n, fmtp(v), "") for n, v in r["raquis"]])
    items = []
    for f, g in df.dropna(subset=["_fecha"]).groupby(df["_fecha"].dt.normalize()):
        rd = cc.categoria(g)
        if rd:
            c = dict(rd["categorias"])
            items.append({"fecha": f, "partes": [("Cat 1", c.get("Cat 1", 0) + c.get("Cat 1 Premium", 0)),
                                                 ("Cat 1.5", c.get("Cat 1.5", 0)), ("Cat 2", c.get("Cat 2", 0)),
                                                 ("Descarte", c.get("Descarte", 0))],
                          "sub": f"{rd['muestras']} muestras"})
    if not items:
        return
    band("Categoría por día", "distribución de racimos de cada día")
    barras_100(items, {"Cat 1": VERDE, "Cat 1.5": AMBAR, "Cat 2": ROJO_V, "Descarte": "#5a5250"})
