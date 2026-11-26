"""
El Pedregal - mapa interactivo de lotes y cuarteles.

Ejecutar (Anaconda Prompt, dentro de pedregal_datos):
    streamlit run app.py

Flujo: mapa -> clic en un cuartel -> datos generales (lote o cuartel)
       -> elegir una evaluacion (brotacion ... cosecha) -> detalle.
Lee SOLO la base local datos/pedregal.duckdb. Nunca consulta Athena.
"""
import json
import os
import re

import duckdb
import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

import brotacion as br
import vista_cosecha as vc
from union_mapa import UnionMapa

DB = os.path.join("datos", "pedregal.duckdb")
# En linea (Streamlit Cloud) la base viaja comprimida (.gz) porque GitHub no acepta archivos de mas de 25 MB por la web
_GZ = DB + ".gz"
def _db_sana():
    try:
        with duckdb.connect(DB, read_only=True) as _c:
            _c.execute("SELECT count(*) FROM information_schema.tables").fetchone()
        return True
    except Exception:
        return False


if os.path.exists(_GZ) and (not os.path.exists(DB) or os.path.getmtime(_GZ) > os.path.getmtime(DB) or not _db_sana()):
    import gzip
    import shutil
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with gzip.open(_GZ, "rb") as _g, open(DB, "wb") as _f:
        shutil.copyfileobj(_g, _f)
    os.utime(DB, (1, 1))     # base "vieja" a proposito: asi la de la tarea de GitHub siempre se ve mas nueva y se baja
# GitHub (tarea programada cada hora) deja la base lista aqui; la app en linea la baja al despertar
RELEASE = "https://github.com/omartel-crypto/PEDREGAL-PLATAFORMA/releases/download/datos/pedregal.duckdb.gz"


def bajar_release():
    """Solo en linea: si GitHub tiene una base mas nueva que la actual, la baja (unos segundos).
    Devuelve la hora (timestamp) en que GitHub preparo esa base, o None si no hay."""
    if os.name == "nt":
        return None
    import email.utils
    import gzip
    import shutil
    import time
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(RELEASE, method="HEAD"), timeout=15) as r:
            lm = r.headers.get("Last-Modified")
        t = email.utils.parsedate_to_datetime(lm).timestamp() if lm else time.time()
        if os.path.exists(DB) and os.path.getmtime(DB) >= t - 60:
            return t
        tmp = DB + ".rel"
        with urllib.request.urlopen(RELEASE, timeout=90) as r, open(tmp + ".gz", "wb") as f:
            shutil.copyfileobj(r, f)
        with gzip.open(tmp + ".gz", "rb") as g, open(tmp, "wb") as f:
            shutil.copyfileobj(g, f)
        os.remove(tmp + ".gz")
        try:                                     # se prueba antes de usarla: si no abre, se queda la actual
            with duckdb.connect(tmp, read_only=True) as c:
                c.execute("SELECT count(*) FROM information_schema.tables").fetchone()
        except Exception:
            os.remove(tmp)
            return None
        os.replace(tmp, DB)
        os.utime(DB, (t, t))                     # la base queda con la hora en que GitHub la preparo
        return t
    except Exception:
        return None


GEO = "cuarteles_pedregal.geojson"
ROJO = "#d71920"      # rojo Pedregal
AZUL = "#7aa2ff"      # azul de % Brotacion (claro para el fondo oscuro)
GRIS = "#a89c97"

st.set_page_config(page_title="El Pedregal", page_icon="🍇", layout="wide")


@st.cache_resource(show_spinner="Trayendo los datos más recientes…")
def _inicio():
    return bajar_release()                       # una vez al despertar la app


_inicio()


# ---------------------------------------------------------------- actualizacion automatica (solo en linea)
# En Streamlit Cloud, si en Secrets estan las claves de Athena (ATHENA_KEY, ATHENA_SECRET, ATHENA_REGION, ATHENA_S3),
# cada hora se bajan los datos nuevos de Pedregal en segundo plano. En la laptop se sigue usando el boton.
CADA_SEG = 3600


@st.cache_resource
def _auto_estado():
    return {"corriendo": False, "ultimo": 0.0, "ok": None, "msg": ""}


def _auto_actualizar():
    import subprocess
    import sys
    import threading
    import time
    if os.name == "nt" or not (os.environ.get("ATHENA_KEY") and os.environ.get("ATHENA_SECRET")):
        return None
    est = _auto_estado()
    if est["corriendo"] or time.time() - est["ultimo"] < CADA_SEG:
        return est

    def trabajo():
        import shutil
        tmp = DB + ".nuevo"
        try:
            t_rel = bajar_release()
            if t_rel and time.time() - t_rel < 3300:
                est["ok"], est["msg"] = True, "datos de la tarea de GitHub"
                return                            # GitHub ya la dejo al dia: no hace falta bajar de Athena
            if os.path.exists(DB):
                shutil.copyfile(DB, tmp)          # se trabaja en una copia: la plataforma sigue leyendo la actual
            env = dict(os.environ, PEDREGAL_DB=tmp)
            r = subprocess.run([sys.executable, "4_extraer_tablas.py"], env=env, capture_output=True, text=True, timeout=1800)
            txt = (r.stdout or "") + (r.stderr or "")
            est["log"] = "\n".join(l for l in txt.splitlines() if l.startswith(("===", "  OK", "  !!", "!!", "Tablas", "Conexi", "  ->"))
                                    or "rror" in l)[-3000:]
            ok = txt.count("  OK ")
            if ok and os.path.exists(tmp):
                os.replace(tmp, DB)               # cambio instantaneo a la base nueva
                est["ok"], est["msg"] = True, f"{ok} tablas"
            else:
                est["ok"], est["msg"] = False, (txt.strip().splitlines() or ["sin respuesta"])[-1][:160]
        except Exception as e:
            est["ok"], est["msg"] = False, str(e)[:160]
        finally:
            import datetime as _dt
            est["hora"] = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=5)).strftime("%d/%m %H:%M")
            est["ultimo"] = time.time()
            est["corriendo"] = False
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    est["corriendo"] = True
    threading.Thread(target=trabajo, daemon=True).start()
    return est


AUTO = _auto_actualizar()
# cambio de nivel pedido por un boton en la corrida anterior (se aplica antes de crear el selector)
if "nivel_pendiente" in st.session_state:
    st.session_state["nivel"] = st.session_state.pop("nivel_pendiente")
if "modo_pendiente" in st.session_state:
    st.session_state["vista_app"] = st.session_state.pop("modo_pendiente")
st.session_state.setdefault("nivel", "Lote")
if st.session_state.get("vista_app") not in ("Packing", "Cosecha", "Directorio", "Admin"):
    st.session_state["vista_app"] = "Packing"
st.session_state.setdefault("sec_cos", "Limpieza")

VARIEDAD_COLOR = {
    "TIMPSON": "#5b8c3a", "ALLISON": "#c2456a", "AUTUMN_CRISP": "#d9b230",
    "COTTON_CANDY": "#7fb3d5", "CANDY_HEARTS": "#e08bb4", "RED_GLOBE": "#9c2f2f",
    "SUGRA_54": "#3f9a8f", "APPLAUSE": "#8e5cc2", "SABLE_SEEDLESS": "#3d3f6b",
    "JACK_S_SALUTE": "#e07b39", "MAGENTA": "#c2185b", "K2_G5": "#6d8b9e",
    "VARIEDADES_NUEVAS": "#b0a48a", "": "#9a9a8c",
}
VARIEDAD_NOMBRE = {
    "TIMPSON": "Timpson", "ALLISON": "Allison", "AUTUMN_CRISP": "Autumn Crisp",
    "COTTON_CANDY": "Cotton Candy", "CANDY_HEARTS": "Candy Hearts", "RED_GLOBE": "Red Globe",
    "SUGRA_54": "Sugra 54", "APPLAUSE": "Applause", "SABLE_SEEDLESS": "Sable Seedless",
    "JACK_S_SALUTE": "Jack's Salute", "MAGENTA": "Magenta", "K2_G5": "K2 G5",
    "VARIEDADES_NUEVAS": "Variedades nuevas", "": "Sin variedad",
}

# Evaluaciones en orden fenologico. "patron" busca la tabla cargada por su nombre.
EVALUACIONES = [
    {"clave": "brotacion", "nombre": "Brotación", "patron": "brot",
     "desc": "% de yemas brotadas y etapas fenológicas"},
    {"clave": "floracion", "nombre": "Floración", "patron": "flora", "desc": "Avance de floración"},
    {"clave": "cuaja", "nombre": "Cuaja", "patron": "cuaj", "desc": "Racimos y bayas cuajadas"},
    {"clave": "raleo", "nombre": "Raleo", "patron": "rale", "desc": "Racimos dejados por planta"},
    {"clave": "bayas", "nombre": "Crecimiento de bayas", "patron": "baya", "desc": "Calibre y peso de bayas"},
    {"clave": "brix", "nombre": "Madurez / Brix", "patron": "brix", "desc": "Sólidos solubles y acidez"},
    {"clave": "cosecha", "nombre": "Cosecha", "patron": "cosech", "desc": "Kilos, cajas y rendimiento"},
]

# escala de % brotacion: rojo (0%) -> ambar -> verde (100%)
ESCALA = [(0, (215, 48, 39)), (25, (244, 109, 67)), (50, (253, 204, 92)), (75, (120, 198, 98)), (100, (10, 143, 58))]


def color_pct(p):
    if p is None or pd.isna(p):
        return "#5e6457"
    p = max(0, min(100, float(p)))
    for (a, ca), (b, cb) in zip(ESCALA, ESCALA[1:]):
        if p <= b:
            t = (p - a) / (b - a)
            r, g, bl = (round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))
            return f"#{r:02x}{g:02x}{bl:02x}"
    return "#0a8f3a"


st.markdown(f"""
<style>
.block-container {{padding-top: 3.4rem; padding-bottom: 2rem; max-width: 1500px;}}
.banda {{display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 18px; background:{ROJO}; color:white;
        border-radius:10px; padding:12px 20px; margin-bottom:12px;}}
.banda h1 {{color:white; font-size:1.6rem; font-weight:800; margin:0; padding:0; letter-spacing:.01em;}}
.banda .sub {{opacity:.9; font-size:.9rem;}}
.kpis {{display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:10px; margin-bottom:12px;}}
.kpi {{background:#1c1517; border:1px solid #2e2427; border-radius:12px; padding:10px 14px;}}
.kpi .l {{font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:#a89c97;}}
.kpi .v {{font-size:1.8rem; font-weight:800; line-height:1.15; font-variant-numeric: tabular-nums;}}
.kpi .v.rojo {{color:{ROJO};}}
@media (max-width: 800px) {{ .kpis {{grid-template-columns: repeat(2, minmax(0,1fr));}} }}
.miga {{font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; color:{GRIS};}}
.miga b {{color:#f4ece8;}}
.titulo {{font-size:2.4rem; font-weight:800; line-height:1.05; margin:.15rem 0 .35rem;}}
.titulo small {{font-size:1rem; font-weight:600; color:{GRIS}; margin-left:6px;}}
.chip {{display:inline-block; padding:3px 12px; border-radius:99px; font-size:.85rem; font-weight:600; margin:0 4px 4px 0; color:white;}}
.info {{display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:8px 18px; margin:6px 0 4px; font-size:1rem;}}
.info div {{border-top:1px solid #2e2427; padding-top:5px; min-width:0; overflow-wrap:anywhere;}}
.info span {{display:block; font-size:.66rem; letter-spacing:.07em; text-transform:uppercase; color:{GRIS};}}
.mix {{display:flex; height:12px; border-radius:6px; overflow:hidden; margin:4px 0 2px;}}
.mix div {{height:100%;}}
.paso {{font-size:.68rem; letter-spacing:.08em; text-transform:uppercase; color:{GRIS};}}
.ev-nombre {{font-weight:700; font-size:1.02rem; margin:2px 0 0;}}
.ev-dato {{font-size:1.7rem; font-weight:800; color:{AZUL}; font-variant-numeric: tabular-nums; line-height:1.2;}}
.ev-desc {{font-size:.8rem; color:{GRIS};}}
.leyenda {{height:10px; border-radius:5px; margin:4px 0 2px;
          background: linear-gradient(90deg, #d73027, #f46d43 25%, #fdcc5c 50%, #78c662 75%, #0a8f3a);}}
.leyenda-txt {{display:flex; justify-content:space-between; font-size:.75rem; color:{GRIS};}}
.seccion {{font-size:1.25rem; font-weight:800; margin:.4rem 0 .2rem;}}
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] {{padding-top: 1rem;}}
.marca {{display:flex; align-items:center; justify-content:space-between; gap:10px; color:#fff; border-radius:14px;
        padding:14px 16px; margin-bottom:18px; background:linear-gradient(110deg,#c8102e 0%,#a3112a 50%,#5e0d18 100%);
        box-shadow:0 6px 18px rgba(200,16,46,.25);}}
.marca .wm {{font:700 1.7rem/1 Georgia,serif; color:#fff;}}
.marca .tg {{font:italic 600 .72rem Georgia,serif; color:#fff; text-align:right; opacity:.95;}}
.menu-t {{font-size:.72rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700; color:{GRIS}; margin:0 0 6px 2px;}}
.menu-sep {{height:1px; background:rgba(168,156,151,.25); margin:10px 0 12px;}}
[data-testid="stSidebar"] .stButton button {{justify-content:flex-start; padding:.62rem 1rem; border-radius:12px; min-height:3rem;}}
[data-testid="stSidebar"] .stButton button p {{font-size:1.05rem !important; font-weight:700;}}
[data-testid="stSidebar"] .stButton button[kind="primary"], [data-testid="stSidebar"] .stButton button[data-variant="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
        background:linear-gradient(100deg,#c8102e,#9b0f26) !important; border-color:#c8102e !important; color:#fff !important;
        box-shadow:0 4px 14px rgba(200,16,46,.3);}}
[data-testid="stSidebar"] .stButton button[kind="primary"] p, [data-testid="stSidebar"] .stButton button[data-variant="primary"] p {{color:#fff !important;}}
</style>
""", unsafe_allow_html=True)


# ================================================================ datos
@st.cache_data
def cargar_geo():
    with open(GEO, encoding="utf-8") as f:
        return json.load(f)


@st.cache_resource
def union():
    return UnionMapa(cargar_geo()["features"])


def con():
    return duckdb.connect(DB, read_only=True)


@st.cache_data(ttl=300)
def tablas_cargadas(version=None):
    if not os.path.exists(DB):
        return pd.DataFrame(columns=["tabla", "col_fecha", "desde", "filas", "cargado_en"])
    with con() as c:
        nombres = [r[0] for r in c.execute(
            "SELECT table_name FROM information_schema.tables WHERE left(table_name, 1) <> '_' "
            "AND table_name NOT LIKE 'maestro%'").fetchall()]
        try:
            meta = c.execute("SELECT * FROM _cargas").df()
        except duckdb.Error:
            meta = pd.DataFrame(columns=["tabla", "col_fecha", "desde", "filas", "cargado_en"])
    meta = meta[meta["tabla"].isin(nombres)]
    faltan = [n for n in nombres if n not in set(meta["tabla"])]
    if faltan:
        meta = pd.concat([meta, pd.DataFrame({"tabla": faltan})], ignore_index=True)
    return meta.reset_index(drop=True)


@st.cache_data(ttl=300)
def columnas(tabla):
    with con() as c:
        return list(c.execute(f'DESCRIBE "{tabla}"').df()["column_name"])


def etiqueta(t):
    m = re.search(r"uva_(?:pk_|bd_)?(.+?)(?:_vid)?_[0-9a-f]{8}_", t)
    base = m.group(1) if m else t
    base = re.sub(r"_vid$", "", base).replace("_", " ").strip().capitalize()
    return base.replace("Brotacion", "Brotación").replace("Recepcion", "Recepción")


def adivinar_union(cols):
    for clave in ["cuartel", "lote", "parcela", "sector", "campo", "fundo"]:
        for n in cols:
            if clave in n.lower():
                return n
    return None


def _ver():
    """Fecha de modificacion de la base: los caches se renuevan apenas llega una actualizacion."""
    return os.path.getmtime(DB) if os.path.exists(DB) else 0


@st.cache_data(ttl=300)
def mapeo(tabla, col, version=None):
    with con() as c:
        vals = c.execute(f'SELECT "{col}" AS v, count(*) AS n FROM "{tabla}" GROUP BY 1').df()
    res = vals["v"].map(union().resolver)
    vals["lote_id"] = [r[0] for r in res]
    vals["cuartel_id"] = [r[1] for r in res]
    vals["v"] = vals["v"].astype(str)
    return vals


@st.cache_data(ttl=300)
def brot_resumen(tabla, col_union, col_fecha):
    cols_e = br.detectar(columnas(tabla))
    if not cols_e or not col_fecha:
        return None
    lista = [col_union, col_fecha] + list(cols_e.values())
    sel = ", ".join(f'"{c}"' for c in dict.fromkeys(lista))
    with con() as c:
        datos = c.execute(f'SELECT {sel} FROM "{tabla}"').df()
    return br.resumir(datos, col_union, col_fecha, cols_e, mapeo(tabla, col_union, _ver()))


@st.cache_data(ttl=300)
def maestro_cuartel():
    if not os.path.exists(DB):
        return pd.DataFrame()
    with con() as c:
        try:
            return c.execute("SELECT * FROM maestro_cuartel").df()
        except duckdb.Error:
            return pd.DataFrame()


def registros(tabla, col, valores, limite=20000):
    if not valores:
        return pd.DataFrame()
    with con() as c:
        c.register("vals", pd.DataFrame({"v": valores}))
        return c.execute(
            f'SELECT t.* FROM "{tabla}" t JOIN vals ON CAST(t."{col}" AS VARCHAR) = vals.v LIMIT {limite}').df()


def fmt_fecha(x):
    return f"{x:%d/%m/%Y}" if x is not None and not pd.isna(x) else "—"


def fmt(x, suf=""):
    if x is None or x is pd.NaT or (isinstance(x, float) and pd.isna(x)):
        return "—"
    if isinstance(x, float):
        return f"{x:,.2f}".rstrip("0").rstrip(".") + suf
    return f"{x}{suf}"


def unicos(serie):
    vals = [v for v in serie.dropna().unique() if str(v).strip()]
    return " · ".join(sorted(map(str, vals))) if vals else "—"


def cerrar_ficha():
    """Vuelve a la vista general. Cambia la clave del mapa para que olvide el ultimo clic."""
    for k in ("sel", "vista", "ultimo_clic"):
        st.session_state.pop(k, None)
    st.session_state["mapa_n"] = st.session_state.get("mapa_n", 0) + 1


def ir_a_lote(lote_id):
    """Abre un lote elegido en el buscador (sin pasar por el mapa)."""
    cu = props.loc[props["lote_id"] == lote_id, "cuartel_id"]
    st.session_state["sel"] = {"lote_id": lote_id, "cuartel_id": cu.iloc[0] if len(cu) else lote_id}
    st.session_state.pop("ultimo_clic", None)
    st.session_state.pop("vista", None)
    st.session_state["mapa_n"] = st.session_state.get("mapa_n", 0) + 1


def al_buscar(clave, limpiar=True):
    v = st.session_state.get(clave)
    if v:
        ir_a_lote(v)
    if limpiar:
        st.session_state[clave] = None


def info_grid(datos):
    """datos: lista de (etiqueta, valor, ayuda). La ayuda aparece al pasar el mouse."""
    st.markdown("<div class='info'>" + "".join(
        f"<div title='{a}'><span>{l}</span>{v}</div>" for l, v, a in datos) + "</div>",
        unsafe_allow_html=True)


# ================================================================ preparacion
geo = cargar_geo()
props = pd.DataFrame([f["properties"] for f in geo["features"]])
props["variedad"] = props["variedad"].fillna("")
mae = maestro_cuartel()
MAE = mae.set_index("cuartel_id") if len(mae) else pd.DataFrame()
if len(mae):
    props["variedad"] = props["cuartel_id"].map(dict(zip(mae["cuartel_id"], mae["variedad_cod"]))).fillna(props["variedad"])
    for cod, nom in zip(mae["variedad_cod"], mae["variedad"]):
        VARIEDAD_NOMBRE.setdefault(cod, nom)
    for col in ("jefe_campo", "patron", "fecha_plantacion"):
        props[col] = props["cuartel_id"].map(dict(zip(mae["cuartel_id"], mae[col])))
else:
    props["jefe_campo"] = props["patron"] = props["fecha_plantacion"] = None
VAR_CU = dict(zip(props["cuartel_id"], props["variedad"]))
meta = tablas_cargadas(_ver())


def tabla_de(ev):
    t = [x for x in meta["tabla"] if ev["patron"] in x.lower()]
    return t[0] if t else None


# ================================================================ barra lateral
tabla_principal = col_principal = col_fecha = None
brot = None
VISTAS = {"Packing": ("📦", "Cajas por lote y packing"), "Directorio": ("📊", "Consolidado para presentar"),
          "Cosecha": ("🍇", "Calidad por lote"), "Admin": ("🔒", "Estado de lotes")}
if st.session_state.get("vista_app") not in VISTAS:      # (no usar la clave "modo": era de un widget antiguo)
    st.session_state["vista_app"] = "Packing"


def ir_vista(v):
    st.session_state["vista_app"] = v
    st.session_state.pop("sel", None)


def actualizar_datos():
    """Vuelve a leer todo. En la laptop (con el ODBC) primero baja los datos nuevos de Pedregal."""
    import subprocess
    import sys
    msg = ""
    if os.name == "nt" and os.path.exists("4_extraer_tablas.py"):
        with st.spinner("Bajando los datos nuevos de Pedregal… (1 a 3 minutos)"):
            st.cache_data.clear()
            st.cache_resource.clear()
            import gc
            gc.collect()                                   # suelta la base para poder escribirla
            r = subprocess.run([sys.executable, "4_extraer_tablas.py"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1200)
            txt = (r.stdout or "") + (r.stderr or "")
            ok = txt.count("  OK ")
            err = txt.count("!! ERROR")
            msg = f"✅ {ok} tablas actualizadas" + (f" · ⚠️ {err} con error (ver resumen_tablas.txt)" if err else "")
    st.cache_data.clear()
    st.cache_resource.clear()
    st.session_state["_msg_act"] = msg or "✅ Datos recargados"


modo = st.session_state["vista_app"]
fundo_sel, var_sel, jefe_sel = "Todos", "Todas", "Todos"
with st.sidebar:
    st.markdown(
        "<div class='marca'><div><div class='wm'>Pedregal</div><div class='tg'>the fruit company</div></div>"
        "<svg width='34' height='44' viewBox='0 0 48 60' aria-hidden='true'><path d='M24 3v7M24 7c4-4 9-4 13-1' stroke='#9fd45a' "
        "stroke-width='3' fill='none' stroke-linecap='round'/><g fill='#9fd45a' stroke='#5f9e2c' stroke-width='1.2'>"
        + "".join(f"<circle cx='{x}' cy='{y}' r='6'/>" for x, y in [(13, 17), (24, 16), (35, 17), (18, 27), (30, 27), (12, 37),
                                                                   (24, 37), (36, 37), (18, 47), (30, 47), (24, 55)])
        + "</g></svg></div><div class='menu-t'>¿Qué quieres ver?</div>", unsafe_allow_html=True)
    for v, (icono, desc) in VISTAS.items():
        st.button(f"{icono}  {v}", key=f"nav_{v}", on_click=ir_vista, args=(v,), use_container_width=True,
                  type="primary" if v == modo else "secondary", help=desc)
    st.markdown("<div class='menu-sep'></div>", unsafe_allow_html=True)
    st.button("⟳  Actualizar datos", key="btn_act", on_click=actualizar_datos, use_container_width=True,
              help="Vuelve a cargar todo con los datos más recientes")
    if st.session_state.get("_msg_act"):
        st.caption(st.session_state.pop("_msg_act"))
    if len(meta) and "cargado_en" in meta and meta["cargado_en"].notna().any():
        _ts = pd.Timestamp(meta['cargado_en'].max())      # el extractor guarda la hora de Lima
        st.caption(f"Datos al **{_ts:%d/%m · %H:%M}**")
    if AUTO is not None:
        if AUTO["corriendo"]:
            st.caption("🔄 Bajando datos nuevos de Pedregal… (2 a 5 min, luego recarga)")
        elif AUTO["ok"] is False:
            st.caption(f"⚠️ Actualización automática del {AUTO.get('hora', '')} falló: {AUTO['msg']}")
        elif AUTO["ok"]:
            st.caption(f"✅ Actualizado solo el {AUTO.get('hora', '')} ({AUTO['msg']}) · cada hora")
        else:
            st.caption("🔄 Se actualiza solo cada hora")
        if AUTO.get("log"):
            with st.expander("Detalle de la última actualización"):
                st.code(AUTO["log"], language=None)
    st.toggle("☀️ Fondo claro", key="claro", help="Cambia toda la plataforma a fondo blanco")

t_brot = tabla_de(EVALUACIONES[0])
if t_brot:
    fm = meta[meta["tabla"] == t_brot].iloc[0]
    col_fecha = fm.get("col_fecha") if isinstance(fm.get("col_fecha"), str) else None
    col_principal = adivinar_union(columnas(t_brot))
    tabla_principal = t_brot
    brot = brot_resumen(t_brot, col_principal, col_fecha) if col_principal else None
por_cuartel, por_lote, historia = brot if brot else (None, None, None)
pct_cu = dict(zip(por_cuartel["cuartel_id"], por_cuartel["pct_brot"])) if brot else {}
fecha_cu = dict(zip(por_cuartel["cuartel_id"], por_cuartel["fecha"])) if brot else {}
conteo = {}

# el mapa se colorea por variedad; solo al abrir el detalle de brotacion pasa a % de brotacion
color_por = "% Brotación" if (st.session_state.get("vista") == "brotacion" and brot) else "Variedad"
vc.css(st.session_state.get("claro", False))
vc.configurar({"props": props, "MAE": MAE, "VARIEDAD_NOMBRE": VARIEDAD_NOMBRE, "VARIEDAD_COLOR": VARIEDAD_COLOR, "geo": geo,
               "mapeo": lambda t, c: mapeo(t, c, _ver()), "VAR_CU": VAR_CU})
COS = vc.estado_lotes()          # lote -> inicio, ultimo dia, dias y estado de cosecha
if modo == "Cosecha":
    color_por = "Cosecha"

# ================================================================ encabezado
vista = props[((props["fundo"] == fundo_sel) | (fundo_sel == "Todos"))
              & ((props["variedad"] == var_sel) | (var_sel == "Todas"))
              & ((props["jefe_campo"] == jefe_sel) | (jefe_sel == "Todos"))]
VISIBLES = set(vista["cuartel_id"])
if vista.empty:
    st.warning("Ningún cuartel cumple los filtros elegidos.")
    st.stop()

filtros_txt = " · ".join(x for x in [
    fundo_sel.title() if fundo_sel != "Todos" else "Todos los fundos",
    VARIEDAD_NOMBRE.get(var_sel, var_sel) if var_sel != "Todas" else "",
    jefe_sel if jefe_sel != "Todos" else ""] if x)
if len(MAE):
    vig = MAE[MAE["anio"] == MAE["anio"].max()]
    campania = vig["campania"].mode().iloc[0] if vig["campania"].notna().any() else str(int(MAE["anio"].max()))
else:
    campania = str(pd.Timestamp.today().year)
if modo == "Admin":
    vc.admin(vista["lote_id"])
    st.stop()
if modo == "Packing":
    vc.vista_packing()
    st.stop()
if modo == "Directorio":
    vc.vista_directorio(vista["lote_id"])
    st.stop()
if modo == "Cosecha":
    vc.cabecera(vista, campania, con_kpis=not st.session_state.get("sel"))

else:
    vc.encabezado(f"Mapa de cuarteles · Campaña {campania}", f"El Pedregal · {filtros_txt}")
    vc.kpis([
        ("Hectáreas", f"{vista['area_ha'].sum():,.0f}", "superficie de los polígonos", "#f6eef7"),
        ("Lotes", f"{vista['lote_id'].nunique()}", "", "#eef6ef"),
        ("Cuarteles", f"{len(vista)}", "", "#fdeeee"),
        ("Variedades", f"{vista.loc[vista['variedad'] != '', 'variedad'].nunique()}", "", "#fbf5ea"),
    ])

# ================================================================ mapa
sel = st.session_state.get("sel")
nivel = st.session_state.get("nivel") or "Lote"
sel_lote = sel["lote_id"] if sel else None
sel_cu = sel["cuartel_id"] if sel else None
vmax = max(conteo.values()) if conteo else 1


def estado_cos(p):
    return COS.get(p["lote_id"], {}).get("estado", "Sin cosecha")


def color_cuartel(p):
    if color_por == "Cosecha":
        return vc.ESTADO_COLOR.get(estado_cos(p), "#c9c4b8")
    if color_por == "% Brotación":
        return color_pct(pct_cu.get(p["cuartel_id"]))
    if color_por == "N° de registros":
        n = conteo.get(p["lote_id"], 0)
        return color_pct(100 * n / vmax) if n else "#5e6457"
    return VARIEDAD_COLOR.get(p["variedad"] or "", "#9a9a8c")


feats, lats, lons = [], [], []
pr_idx = props.set_index("cuartel_id")
for f in geo["features"]:
    p = f["properties"]
    if p["cuartel_id"] not in VISIBLES:
        continue
    p2 = dict(p)
    p2["variedad"] = VAR_CU.get(p["cuartel_id"], p["variedad"])
    p2["lote_txt"] = f"{p['fundo'].title()} · Lote {p['lote'][1:]}"
    p2["cuartel_txt"] = p["cuartel"]
    p2["variedad_txt"] = VARIEDAD_NOMBRE.get(p2["variedad"] or "", p2["variedad"])
    p2["ha_txt"] = f"{p['area_ha']:.2f} ha"
    pat = pr_idx.at[p["cuartel_id"], "patron"]
    p2["patron_txt"] = pat if isinstance(pat, str) else "—"
    fp = pr_idx.at[p["cuartel_id"], "fecha_plantacion"]
    p2["plant_txt"] = f"{pd.Timestamp(fp).year}" if fp is not None and not pd.isna(fp) else "—"
    pb = pct_cu.get(p["cuartel_id"])
    p2["brot_txt"] = f"{pb:.1f}%" if pb is not None and not pd.isna(pb) else "sin evaluar"
    fc_ = fecha_cu.get(p["cuartel_id"])
    p2["fecha_txt"] = f"{fc_:%d/%m/%Y}" if fc_ is not None else "—"
    rc = COS.get(p["lote_id"])
    p2["cos_txt"] = estado_cos(p) + (f" · {rc['inicio']:%d/%m}–{rc['ultimo']:%d/%m} · {rc['dias']} día(s)" if rc else "")
    p2["_color"] = color_cuartel(p2)
    feats.append({"type": "Feature", "properties": p2, "geometry": f["geometry"]})
    g = f["geometry"]
    rings = g["coordinates"] if g["type"] == "Polygon" else [r for poly in g["coordinates"] for r in poly]
    for ring in rings:
        for x, y in ring:
            lons.append(x)
            lats.append(y)


def estilo(f):
    nivel_m = "Lote" if modo == "Cosecha" else nivel
    pp = f["properties"]
    en_lote = pp["lote_id"] == sel_lote
    es_cu = pp["cuartel_id"] == sel_cu
    if nivel_m == "Cuartel" and es_cu:
        borde, ancho = "#ffffff", 4
    elif en_lote:
        borde, ancho = "#ffffff", 2.5 if nivel_m == "Lote" else 1.2
    else:
        borde, ancho = "#1b1d18", 0.6
    opac = 0.9 if (not sel_lote or en_lote) else 0.45
    if nivel_m == "Cuartel" and sel_cu and en_lote and not es_cu:
        opac = 0.65
    if color_por == "Cosecha" and estado_cos(pp) == "Sin cosecha" and not en_lote:
        opac = 0.3
    return {"fillColor": pp["_color"], "color": borde, "weight": ancho, "fillOpacity": opac}


mapa = folium.Map(location=[sum(lats) / len(lats), sum(lons) / len(lons)], zoom_start=13,
                  tiles=None, control_scale=True, prefer_canvas=True)
folium.TileLayer("OpenStreetMap", name="Calles", show=False).add_to(mapa)
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, Maxar, Earthstar Geographics", name="Satélite", max_zoom=19, show=True).add_to(mapa)
campos = ["lote_txt", "cuartel_txt", "variedad_txt", "ha_txt", "patron_txt", "plant_txt"]
alias = ["Lote", "Cuartel", "Variedad", "Superficie", "Patrón", "Plantación"]
if color_por == "% Brotación":
    campos += ["brot_txt", "fecha_txt"]
    alias += ["% Brotación", "Última evaluación"]
if color_por == "Cosecha":
    campos += ["cos_txt"]
    alias += ["Cosecha"]
folium.GeoJson(
    {"type": "FeatureCollection", "features": feats}, name="Cuarteles", style_function=estilo,
    highlight_function=lambda f: {"weight": 3, "color": "#ffffff", "fillOpacity": 0.95},
    tooltip=folium.GeoJsonTooltip(
        fields=campos, aliases=alias, sticky=True,
        style="font-family: sans-serif; font-size: 12px; padding: 8px 10px; border-radius: 6px;"),
).add_to(mapa)
folium.LayerControl(collapsed=True).add_to(mapa)
if modo == "Cosecha":
    zl, zo = [], []
    for f in feats:
        if COS.get(f["properties"]["lote_id"], {}).get("estado") in ("En cosecha", "Terminada"):
            g = f["geometry"]
            for ring in (g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]):
                for x, y in ring:
                    zo.append(x)
                    zl.append(y)
    if zl:   # acercar a los lotes con cosecha
        mg = 0.004
        mapa.fit_bounds([[min(zl) - mg, min(zo) - mg], [max(zl) + mg, max(zo) + mg]])
    else:
        mapa.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
else:
    mapa.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])

MOSTRAR_MAPA = not (sel and modo == "Cosecha")   # en la vista del lote de cosecha no va el satelite
if MOSTRAR_MAPA:   # buscador de lotes sobre el mapa
    lotes_op = vc.orden_lotes(vista["lote_id"])
    b1, b2, b3 = st.columns([1.3, 1.2, 1.2], gap="medium", vertical_alignment="bottom")
    b1.selectbox("Buscar lote", lotes_op, index=None, key="buscar_lote", format_func=vc.etiqueta_lote,
                 placeholder="🔎  Escribe el número del lote, por ejemplo 37", on_change=al_buscar, args=("buscar_lote",))
    en_cos = [l for l in lotes_op if COS.get(l, {}).get("estado") == "En cosecha"]
    term = [l for l in lotes_op if COS.get(l, {}).get("estado") == "Terminada"]
    if modo == "Cosecha" and (en_cos or term):
        if en_cos:
            b2.pills("🟠 En cosecha · un clic para abrir", en_cos, key="pill_lote",
                     format_func=lambda l: f"L{vc.num_lote(l)}", on_change=al_buscar, args=("pill_lote",))
        if term:
            b3.pills("🟢 Terminadas", term, key="pill_term",
                     format_func=lambda l: f"L{vc.num_lote(l)}", on_change=al_buscar, args=("pill_term",))
if sel and MOSTRAR_MAPA:
    col_mapa, col_ficha = st.columns([3, 2], gap="medium")
else:
    col_mapa, col_ficha = st.container(), None
if MOSTRAR_MAPA:
  with col_mapa:
      salida = st_folium(mapa, height=470, use_container_width=True,
                         returned_objects=["last_active_drawing"], key=f"mapa_{fundo_sel}_{var_sel}_{jefe_sel}_{st.session_state.get('mapa_n', 0)}")
      clic = (salida or {}).get("last_active_drawing")
      if clic and clic.get("properties"):
          nuevo = {"lote_id": clic["properties"]["lote_id"], "cuartel_id": clic["properties"]["cuartel_id"]}
          if nuevo != st.session_state.get("ultimo_clic"):
              st.session_state["ultimo_clic"] = nuevo
              st.session_state["sel"] = nuevo
              st.rerun()
      if color_por == "Cosecha":
          st.markdown(" ".join(f"<span class='chip' style='background:{c}'>{e}</span>"
                               for e, c in vc.ESTADO_COLOR.items()), unsafe_allow_html=True)
      elif color_por == "Variedad":
          st.markdown(" ".join(
              f"<span class='chip' style='background:{VARIEDAD_COLOR.get(v, '#9a9a8c')}'>{VARIEDAD_NOMBRE.get(v, v)}</span>"
              for v in sorted(set(vista["variedad"]))), unsafe_allow_html=True)
      else:
          izq, der = ("0%", "100%") if color_por == "% Brotación" else ("pocos", f"{vmax:,} registros")
          txt = "% Brotación a la última fecha evaluada · gris = sin evaluar" if color_por == "% Brotación" \
              else "Registros por lote"
          st.markdown(f"<div class='leyenda'></div><div class='leyenda-txt'><span>{izq}</span>"
                      f"<span>{txt}</span><span>{der}</span></div>", unsafe_allow_html=True)
      if not sel:
          st.info("Haz clic en un lote naranja (en cosecha) o verde (terminado) para ver su cosecha: limpieza, "
                  "categorización, brix, peso de racimos y descarte." if modo == "Cosecha" else
                  "Haz clic en cualquier cuartel para ver su ficha: datos generales del lote o del cuartel "
                  "y las evaluaciones de la campaña. Usa los filtros de la izquierda para acotar el mapa.")


# ================================================================ graficos
def gauge(valor, titulo=""):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=valor,
        number={"suffix": "%", "valueformat": ".1f", "font": {"size": 44, "color": AZUL}},
        title={"text": titulo, "font": {"size": 13, "color": GRIS}},
        gauge={"axis": {"range": [0, 100], "ticksuffix": "%", "tickcolor": "#999"},
               "bar": {"color": "#f4ece8", "thickness": 0.28}, "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [a, b], "color": color_pct((a + b) / 2)}
                         for a, b in [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]]}))
    fig.update_layout(height=220, margin=dict(l=25, r=25, t=30 if titulo else 10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def barras_etapas(df, etiquetas, resaltar=None, alto_fila=38):
    """Barras 100% apiladas con las 6 etapas; al final el % de brotacion."""
    fig = go.Figure()
    for clave, nombre, color in br.ETAPAS:
        fig.add_bar(y=etiquetas, x=df[f"pct_{clave}"], name=nombre, orientation="h", marker_color=color,
                    customdata=df[clave], hovertemplate=f"<b>%{{y}}</b><br>{nombre}: %{{x:.1f}}% "
                                                       f"(%{{customdata:,.0f}} yemas)<extra></extra>")
    fig.add_scatter(y=etiquetas, x=[101] * len(df), mode="text", showlegend=False,
                    text=[f"<b>{v:.1f}%</b>" for v in df["pct_brot"]], textposition="middle right",
                    textfont=dict(color=AZUL, size=13), hoverinfo="skip")
    fig.update_layout(
        barmode="stack", height=80 + alto_fila * len(df), margin=dict(l=0, r=60, t=34, b=0),
        xaxis=dict(range=[0, 118], showgrid=False, showticklabels=False),
        yaxis=dict(autorange="reversed", tickfont=dict(size=13), tickvals=etiquetas,
                   ticktext=[f"<b>▶ {e}</b>" if e == resaltar else e for e in etiquetas]),
        legend=dict(orientation="h", y=1.14, x=0, font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def linea_evolucion(series, ddc_base=None):
    """series: lista de (nombre, df con fecha/pct_brot, color, ancho)."""
    fig = go.Figure()
    for nombre, df, color, ancho in series:
        if df is None or df.empty:
            continue
        df = df.sort_values("fecha")
        ddc = (df["fecha"] - ddc_base).dt.days if ddc_base is not None else None
        fig.add_scatter(
            x=df["fecha"], y=df["pct_brot"], mode="lines+markers", name=nombre,
            line=dict(color=color, width=ancho), marker=dict(size=6 + ancho),
            customdata=ddc if ddc is not None else None,
            hovertemplate="%{x|%d/%m/%Y}<br><b>%{y:.1f}%</b>" + (" · DDC %{customdata}" if ddc is not None else "")
                          + f"<extra>{nombre}</extra>")
    fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                      yaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#2e2427"),
                      xaxis=dict(gridcolor="#2e2427"),
                      legend=dict(orientation="h", y=-0.18), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    return fig


# ================================================================ ficha: datos generales
def datos_generales(lote_id, cuartel_id, nivel):
    cu_lote = props[props["lote_id"] == lote_id]
    m_lote = MAE[MAE["lote_id"] == lote_id] if len(MAE) else pd.DataFrame()
    if nivel == "Lote":
        ha = m_lote["ha_lote"].dropna().iloc[0] if len(m_lote) and m_lote["ha_lote"].notna().any() \
            else cu_lote["area_ha"].sum()
        # mezcla de variedades por superficie de poligonos
        mezcla = cu_lote.groupby("variedad")["area_ha"].sum().sort_values(ascending=False)
        st.markdown("<div class='mix'>" + "".join(
            f"<div title='{VARIEDAD_NOMBRE.get(v, v)}: {a:.1f} ha' style='width:{a / mezcla.sum() * 100:.1f}%;"
            f"background:{VARIEDAD_COLOR.get(v, '#9a9a8c')}'></div>" for v, a in mezcla.items()) + "</div>"
            + " ".join(f"<span class='chip' style='background:{VARIEDAD_COLOR.get(v, '#9a9a8c')}'>"
                       f"{VARIEDAD_NOMBRE.get(v, v)} · {a / mezcla.sum() * 100:.0f}%</span>" for v, a in mezcla.items()),
            unsafe_allow_html=True)
        datos = [("Superficie del lote", f"{ha:,.2f} ha", "Según la base maestra; si falta, suma de polígonos"),
                 ("Cuarteles", f"{len(cu_lote)} · {', '.join(sorted(cu_lote['cuartel']))}", "Cuarteles con polígono")]
        if len(m_lote):
            plant = m_lote["fecha_plantacion"].dropna()
            anios = f"{plant.min().year}" + (f" – {plant.max().year}" if plant.max().year != plant.min().year else "") \
                if len(plant) else "—"
            edad = f"{(pd.Timestamp.today() - plant.mean()).days / 365.25:.1f} años" if len(plant) else "—"
            datos += [
                ("Año de plantación", anios, "Rango entre el cuartel más antiguo y el más nuevo"),
                ("Edad promedio", edad, "Desde la fecha de plantación"),
                ("Patrón", unicos(m_lote["patron"]), "Portainjerto"),
                ("Tipo de parrón", unicos(m_lote["tipo_parron"]), "Sistema de conducción"),
                ("Densidad", unicos(m_lote["densidad"].map(lambda d: f"{d:,.0f} pl/ha" if pd.notna(d) else None)),
                 "Plantas por hectárea"),
                ("Campaña", unicos(m_lote["campania"]), "Campaña vigente en la base maestra"),
                ("Jefe de campo", unicos(m_lote["jefe_campo"]), ""),
                ("Encargado de lote", unicos(m_lote["encargado_lote"]), ""),
                ("Supervisor CC", unicos(m_lote["supervisor_cc"]), "Control de calidad"),
                ("Cianamida", unicos(m_lote["fecha_cianamida"].map(lambda d: fmt_fecha(d) if pd.notna(d) else None)),
                 "Fecha(s) de aplicación de cianamida"),
            ]
        info_grid(datos)
        return

    # ---- nivel cuartel
    mc = MAE.loc[cuartel_id] if len(MAE) and cuartel_id in MAE.index else None
    pol = cu_lote[cu_lote["cuartel_id"] == cuartel_id]
    v = VAR_CU.get(cuartel_id, "")
    st.markdown(f"<span class='chip' style='background:{VARIEDAD_COLOR.get(v, '#9a9a8c')}'>"
                f"{VARIEDAD_NOMBRE.get(v, v)}</span>", unsafe_allow_html=True)
    if mc is None:
        info_grid([("Superficie", f"{pol['area_ha'].sum():.2f} ha", "Del polígono del KML")])
        st.caption("Este cuartel no está en la base maestra.")
        return
    plant = mc.get("fecha_plantacion")
    edad = f" · {(pd.Timestamp.today() - plant).days / 365.25:.1f} años" if pd.notna(plant) else ""
    ha_cu = mc.get("ha_cuartel")
    fuente_ha = "Base maestra"
    if pd.isna(ha_cu):
        ha_cu, fuente_ha = pol["area_ha"].sum(), "Polígono del KML (el maestro solo trae el total del lote)"
    cian = mc.get("fecha_cianamida")
    cian_txt = fmt_fecha(cian) + "".join(f" · {mc.get(c)}" for c in ("producto_cianamida", "dosis_total")
                                         if isinstance(mc.get(c), str))
    info_grid([
        ("Superficie", f"{float(ha_cu):,.2f} ha", fuente_ha),
        ("Patrón", fmt(mc.get("patron")), "Portainjerto"),
        ("Plantación", fmt_fecha(plant) + edad, "Fecha de plantación y edad del parral"),
        ("Inicio de producción", fmt_fecha(mc.get("fecha_produccion")), ""),
        ("Tipo de parrón", fmt(mc.get("tipo_parron")), "Sistema de conducción"),
        ("Densidad", fmt(mc.get("densidad"), " pl/ha"), "Plantas por hectárea"),
        ("Jefe de campo", fmt(mc.get("jefe_campo")), ""),
        ("Encargado de lote", fmt(mc.get("encargado_lote")), ""),
        ("Supervisor CC", fmt(mc.get("supervisor_cc")), "Control de calidad"),
        ("Cianamida", cian_txt, "Fecha, producto y dosis total"),
    ])


# ================================================================ ficha: menu de evaluaciones
def resumen_eval(ev, lote_id, cuartel_id, nivel):
    """Dato corto para la tarjeta de cada evaluacion."""
    if ev["clave"] == "brotacion" and brot:
        df = por_lote[por_lote["lote_id"] == lote_id] if nivel == "Lote" \
            else por_cuartel[por_cuartel["cuartel_id"] == cuartel_id]
        if df.empty:
            return "Sin evaluar", ""
        r = df.iloc[0]
        return f"{r['pct_brot']:.1f}%", f"al {r['fecha']:%d/%m/%Y}"
    if ev["clave"] == "cosecha":
        r = COS.get(lote_id)
        if r:
            return f"{r['dias']} día(s)", f"desde {r['inicio']:%d/%m}"
        return None, None
    t = tabla_de(ev)
    if t:
        col = adivinar_union(columnas(t))
        if col:
            mp = mapeo(t, col, _ver())
            n = mp.loc[(mp["lote_id"] == lote_id) if nivel == "Lote" else (mp["cuartel_id"] == cuartel_id), "n"].sum()
            return f"{n:,}", "registros"
    return None, None


def menu_evaluaciones(lote_id, cuartel_id, nivel):
    st.markdown("<div class='seccion'>Evaluaciones</div>", unsafe_allow_html=True)
    st.caption("Elige una para ver su detalle. Están en el orden de la campaña.")
    cols = st.columns(2)
    for i, ev in enumerate(EVALUACIONES):
        dato, sub = resumen_eval(ev, lote_id, cuartel_id, nivel)
        disponible = dato is not None
        with cols[i % 2].container(border=True):
            st.markdown(
                f"<div class='paso'>Etapa {i + 1}{'' if disponible else ' · próximamente'}</div>"
                f"<div class='ev-nombre'>{ev['nombre']}</div>"
                + (f"<div class='ev-dato'>{dato} <span class='ev-desc'>{sub}</span></div>" if disponible
                   else f"<div class='ev-desc'>{ev['desc']}</div>"), unsafe_allow_html=True)
            if st.button("Ver detalle →" if disponible else "Aún sin datos", key=f"ev_{ev['clave']}",
                         disabled=not disponible, use_container_width=True, help=ev["desc"]):
                if ev["clave"] == "cosecha":
                    st.session_state["modo_pendiente"] = "Cosecha"
                else:
                    st.session_state["vista"] = ev["clave"]
                st.rerun()


# ================================================================ detalle: brotacion
def detalle_brotacion(lote_id, cuartel_id, nivel):
    if not brot:
        st.info("No hay datos de brotación cargados.")
        return
    fc = por_cuartel[por_cuartel["lote_id"] == lote_id].sort_values("cuartel_id")
    fl = por_lote[por_lote["lote_id"] == lote_id]
    if fl.empty:
        st.info("Este lote no tiene evaluaciones de brotación en el periodo cargado.")
        return
    m_lote = MAE[MAE["lote_id"] == lote_id] if len(MAE) else pd.DataFrame()
    cian = MAE["fecha_cianamida"].to_dict() if len(MAE) else {}
    cian_lote = m_lote["fecha_cianamida"].dropna().min() if len(m_lote) else None

    if nivel == "Lote":
        r = fl.iloc[0]
        ddc = (r["fecha"] - cian_lote).days if cian_lote is not None and pd.notna(cian_lote) else None
        c1, c2 = st.columns([1, 1.25])
        with c1:
            st.plotly_chart(gauge(r["pct_brot"], "% Brotación del lote"), use_container_width=True,
                            config={"displayModeBar": False})
        with c2:
            info_grid([
                ("Última evaluación", f"{r['fecha']:%d/%m/%Y} · sem. {r['fecha'].isocalendar()[1]}",
                 "Fecha más reciente entre sus cuarteles"),
                ("DDC", f"{ddc} días" if ddc is not None else "—", "Días después de la aplicación de cianamida"),
                ("Yemas evaluadas", f"{int(r['total']):,}", "Suma de yemas a la última fecha de cada cuartel"),
                ("Cuarteles evaluados", f"{int(r['cuarteles'])} de {len(props[props['lote_id'] == lote_id])}", ""),
                ("Puntas verdes", f"{r['pct_punta_verde']:.1f}%", ""),
                ("Hojas desplegadas", f"{r['pct_hoja']:.1f}%", ""),
            ])
        st.markdown("**Por cuartel** · etapas a la última fecha de cada uno")
        st.plotly_chart(barras_etapas(fc, [c.split(".")[-1] for c in fc["cuartel_id"]]),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown("**Evolución semanal del lote**")
        evo = br.evolucion_lote(historia, lote_id)
        st.plotly_chart(linea_evolucion([(f"Lote {lote_id.split('.')[-1][1:]}", evo, AZUL, 3)], cian_lote),
                        use_container_width=True, config={"displayModeBar": False})
        tabla = fc.assign(
            Cuartel=fc["cuartel_id"].str.split(".").str[-1],
            Fecha=fc["fecha"].dt.strftime("%d/%m/%Y"),
            DDC=[(f - cian.get(c)).days if pd.notna(cian.get(c)) else None for f, c in zip(fc["fecha"], fc["cuartel_id"])])
    else:
        rc = fc[fc["cuartel_id"] == cuartel_id]
        if rc.empty:
            st.info("Este cuartel no tiene evaluaciones de brotación en el periodo cargado.")
            return
        r = rc.iloc[0]
        cc = cian.get(cuartel_id)
        ddc = (r["fecha"] - cc).days if cc is not None and pd.notna(cc) else None
        prom_lote = fl.iloc[0]["pct_brot"]
        c1, c2 = st.columns([1, 1.25])
        with c1:
            st.plotly_chart(gauge(r["pct_brot"], f"% Brotación cuartel {cuartel_id.split('.')[-1]}"),
                            use_container_width=True, config={"displayModeBar": False})
        with c2:
            dif = r["pct_brot"] - prom_lote
            info_grid([
                ("Última evaluación", f"{r['fecha']:%d/%m/%Y} · sem. {r['fecha'].isocalendar()[1]}", ""),
                ("DDC", f"{ddc} días" if ddc is not None else "—", "Días después de la aplicación de cianamida"),
                ("Yemas evaluadas", f"{int(r['total']):,}", f"{int(r['evaluaciones'])} evaluación(es) ese día"),
                ("Vs. promedio del lote", f"{'+' if dif >= 0 else ''}{dif:.1f} pts",
                 f"Lote: {prom_lote:.1f}%"),
                ("Puntas verdes", f"{r['pct_punta_verde']:.1f}%", ""),
                ("Hojas desplegadas", f"{r['pct_hoja']:.1f}%", ""),
            ])
        st.markdown("**Etapas del cuartel frente a sus vecinos del lote**")
        st.plotly_chart(barras_etapas(fc, [c.split(".")[-1] for c in fc["cuartel_id"]],
                                      resaltar=cuartel_id.split(".")[-1]),
                        use_container_width=True, config={"displayModeBar": False})
        st.markdown("**Evolución del cuartel vs. el lote**")
        hc = historia[historia["cuartel_id"] == cuartel_id]
        evo = br.evolucion_lote(historia, lote_id)
        st.plotly_chart(linea_evolucion([(f"Cuartel {cuartel_id.split('.')[-1]}", hc, ROJO, 3),
                                         ("Promedio del lote", evo, "#a89c97", 1.5)], cc),
                        use_container_width=True, config={"displayModeBar": False})
        hc = hc.sort_values("fecha", ascending=False)
        tabla = hc.assign(
            Cuartel=hc["cuartel_id"].str.split(".").str[-1],
            Fecha=hc["fecha"].dt.strftime("%d/%m/%Y"),
            DDC=[(f - cc).days if cc is not None and pd.notna(cc) else None for f in hc["fecha"]])

    # tabla estilo reporte
    cols_pct = {f"pct_{k}": n for k, n, _ in br.ETAPAS}
    vista_t = tabla[["Cuartel", "Fecha", "DDC", "total"] + list(cols_pct) + ["pct_brot"]].rename(
        columns={"total": "Total yemas", **{k: f"% {v}" for k, v in cols_pct.items()}})
    st.markdown("**Resumen**" if nivel == "Lote" else "**Todas las evaluaciones del cuartel**")
    st.dataframe(
        vista_t, hide_index=True, use_container_width=True,
        column_config={
            "DDC": st.column_config.NumberColumn("DDC", help="Días después de cianamida", format="%d"),
            "Total yemas": st.column_config.NumberColumn(format="%d"),
            **{f"% {v}": st.column_config.NumberColumn(format="%.1f%%") for v in cols_pct.values()},
            "pct_brot": st.column_config.ProgressColumn("% Brotación", format="%.1f%%", min_value=0, max_value=100,
                                                        help="(Puntas verdes + Hojas desplegadas) / Total yemas"),
        })


def detalle_generico(ev, lote_id, cuartel_id, nivel):
    t = tabla_de(ev)
    col = adivinar_union(columnas(t)) if t else None
    if not col:
        st.info("No encontré una columna de lote/cuartel en esta evaluación.")
        return
    mp = mapeo(t, col, _ver())
    filtro = (mp["lote_id"] == lote_id) if nivel == "Lote" else (mp["cuartel_id"] == cuartel_id)
    df = registros(t, col, list(mp.loc[filtro, "v"]))
    if df.empty:
        st.info("Sin registros para esta selección.")
        return
    st.caption(f"{len(df):,} registros")
    st.dataframe(df, hide_index=True, use_container_width=True, height=380)


# ================================================================ ficha (columna derecha) + detalle (abajo)
if sel and modo == "Cosecha":
    t1, t2 = st.columns([1, 3], gap="medium", vertical_alignment="bottom")
    if t1.button("← Volver al mapa de lotes", key="cerrar_cos", use_container_width=True):
        cerrar_ficha()
        st.rerun()
    st.session_state["lote_cos"] = sel["lote_id"]
    t2.selectbox("Cambiar de lote · escribe para buscar", vc.orden_lotes(list(vista["lote_id"]) + [sel["lote_id"]]),
                 key="lote_cos", format_func=vc.etiqueta_lote, on_change=al_buscar, args=("lote_cos", False))
    vc.ficha(sel["lote_id"])
    vc.cajas_detalle(sel["lote_id"])
    sec = vc.barra(sel["lote_id"])
    vc.seccion(sel["lote_id"], sec)

if sel and modo != "Cosecha":
    with col_ficha:
        if st.button("✕ Cerrar ficha", key="cerrar", help="Volver al mapa completo"):
            cerrar_ficha()
            st.rerun()
        lote_id, cuartel_id = sel["lote_id"], sel["cuartel_id"]
        fundo, lote = lote_id.split(".")
        cu = cuartel_id.split(".")[-1]
        nivel = st.segmented_control("Ver", ["Lote", "Cuartel"], key="nivel",
                                     help="Lote: resumen de todos sus cuarteles. Cuartel: solo el seleccionado.") or "Lote"
        if nivel == "Lote":
            st.markdown(f"<div class='miga'><b>{fundo}</b> › Lote {lote[1:]}</div>"
                        f"<div class='titulo'>Lote {lote[1:]}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='miga'><b>{fundo}</b> › Lote {lote[1:]} › Cuartel {cu}</div>"
                        f"<div class='titulo'>Cuartel {cu}<small>Lote {lote[1:]}</small></div>",
                        unsafe_allow_html=True)
        datos_generales(lote_id, cuartel_id, nivel)
        vista_ev = st.session_state.get("vista")
        if not vista_ev:
            menu_evaluaciones(lote_id, cuartel_id, nivel)
        else:
            ev = next(e for e in EVALUACIONES if e["clave"] == vista_ev)
            st.markdown(f"<div class='seccion'>{ev['nombre']}</div>", unsafe_allow_html=True)
            st.caption("El detalle está debajo del mapa ↓")
            c1, c2 = st.columns(2)
            if c1.button("← Otras evaluaciones", use_container_width=True):
                st.session_state.pop("vista", None)
                st.rerun()
            otro = "Cuartel" if nivel == "Lote" else "Lote"
            if c2.button(f"Ver por {otro.lower()}", use_container_width=True):
                st.session_state["nivel_pendiente"] = otro
                st.rerun()

if sel and modo != "Cosecha" and st.session_state.get("vista"):
    lote_id, cuartel_id = sel["lote_id"], sel["cuartel_id"]
    nivel = st.session_state.get("nivel") or "Lote"
    ev = next(e for e in EVALUACIONES if e["clave"] == st.session_state["vista"])
    st.divider()
    quien = f"Lote {lote_id.split('.')[-1][1:]}" if nivel == "Lote" \
        else f"Cuartel {cuartel_id.split('.')[-1]} · Lote {lote_id.split('.')[-1][1:]}"
    st.markdown(f"<div class='miga'>{lote_id.split('.')[0]} › {quien}</div>"
                f"<div class='titulo'>{ev['nombre']} <small>{'por lote' if nivel == 'Lote' else 'por cuartel'}</small></div>",
                unsafe_allow_html=True)
    if ev["clave"] == "brotacion":
        detalle_brotacion(lote_id, cuartel_id, nivel)
    else:
        detalle_generico(ev, lote_id, cuartel_id, nivel)
