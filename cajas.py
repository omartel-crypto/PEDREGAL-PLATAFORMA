"""Cajas producidas en planta por lote y dia, desde los Excel "diario de calidad" que te pasan.

Como se usa: guarda cada Excel que te llegue en la carpeta Maestro/cajas (con cualquier nombre).
No hay que borrar los anteriores: si dos archivos traen el mismo dia, se usa el mas nuevo.
La plataforma los lee sola al abrir o al presionar R.
"""
import glob
import os
import re

import pandas as pd

CARPETA = os.path.join("Maestro", "cajas")
COLS = {"FECHA PRODUCCION": "fecha", "LOTE": "lote", "LOTE ID": "lote_cod", "CAJAS EQUIVALENTES": "cajas_eq",
        "CANTIDAD CAJAS PRODUCCION": "cajas", "KILOS REALES": "kg", "CATEGORIA": "categoria", "PLANTA": "planta",
        "VARIEDAD ID": "variedad", "CALIBRE": "calibre", "TERMINACION": "presentacion",
        "CLIENTE FINAL": "cliente", "TURNO ID": "turno", "PESO COMERCIAL": "peso_com", "PESO REAL": "peso_real",
        "FORMULA CAJA": "formula"}


def archivos(carpeta=CARPETA):
    """(ruta, fecha de modificacion) de los Excel/CSV de la carpeta, del mas viejo al mas nuevo."""
    if not os.path.isdir(carpeta):
        return []
    rutas = [r for ext in ("xlsx", "xlsm", "xls", "csv") for r in glob.glob(os.path.join(carpeta, f"*.{ext}"))
             if not os.path.basename(r).startswith("~$")]
    return sorted(((r, os.path.getmtime(r)) for r in rutas), key=lambda x: x[1])


def _leer_uno(ruta):
    if ruta.lower().endswith(".csv"):
        hojas = {"csv": pd.read_csv(ruta)}
    else:
        hojas = pd.read_excel(ruta, sheet_name=None)
    for df in hojas.values():
        df.columns = [str(c).strip().upper() for c in df.columns]
        if {"FECHA PRODUCCION", "LOTE", "CAJAS EQUIVALENTES"} <= set(df.columns):
            return df[[c for c in COLS if c in df.columns]].rename(columns=COLS)
    return pd.DataFrame()


def leer(lote_ids, carpeta=CARPETA):
    """Una fila por registro del Excel con su lote_id de la plataforma.
    lote_ids: lista de lotes del mapa (ej. 'ORONGO.L37'); el lote se reconoce por su numero."""
    partes = []
    for ruta, mt in archivos(carpeta):
        try:
            d = _leer_uno(ruta)
        except Exception:
            continue
        if not d.empty:
            partes.append(d.assign(_archivo=os.path.basename(ruta), _mt=mt))
    if not partes:
        return pd.DataFrame()
    d = pd.concat(partes, ignore_index=True)
    d["fecha"] = pd.to_datetime(d["fecha"].astype(str).str[:10], errors="coerce")
    d = d.dropna(subset=["fecha"])
    # si varios archivos traen el mismo dia, vale el archivo mas nuevo
    ult = d.groupby("fecha")["_mt"].transform("max")
    d = d[d["_mt"] == ult]
    for c in ("cajas_eq", "cajas", "kg"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
    for c in ("peso_com", "peso_real"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    # lote del Excel ("LOTE 037") -> lote del mapa ("ORONGO.L37") por su numero
    por_num = {}
    for l in lote_ids:
        m = re.search(r"\.L0*(\d+)$", str(l))
        if m:
            por_num.setdefault(int(m.group(1)), []).append(l)
    num = d["lote"].astype(str).str.extract(r"(\d+)")[0]
    d["lote_id"] = [por_num[int(n)][0] if pd.notna(n) and len(por_num.get(int(n), [])) == 1 else None for n in num]
    # codigos "AZ" (fruta de dos lotes juntos): vienen repetidos, una fila por cada lote -> se reparte mitad y mitad
    mixto = d.get("lote_cod", pd.Series("", index=d.index)).astype(str).str.contains("AZ", case=False)
    for c in ("cajas_eq", "cajas", "kg"):
        if c in d:
            d.loc[mixto, c] = d.loc[mixto, c] * 0.5
    d["mixto"] = mixto
    return d


def resumen_lote(d, lote_id, ha=None):
    g = d[d["lote_id"] == lote_id]
    if g.empty:
        return None
    dia = g.groupby("fecha").agg(cajas_eq=("cajas_eq", "sum"), cajas=("cajas", "sum"), kg=("kg", "sum")).reset_index()
    tot = g["cajas_eq"].sum()
    cat = None
    if "categoria" in g:
        c = pd.to_numeric(g["categoria"], errors="coerce")
        cat = g.loc[c == 1, "cajas_eq"].sum() / tot * 100 if tot else None
    return {"total": tot, "fisicas": g["cajas"].sum() if "cajas" in g else None, "kg": g["kg"].sum() if "kg" in g else None,
            "por_ha": tot / ha if ha else None, "ha": ha, "dias": dia, "cat1": cat,
            "desde": g["fecha"].min(), "hasta": g["fecha"].max(), "archivo": g["_archivo"].iloc[-1]}


# ---------------------------------------------------------------- reporte de packing (HTML con filtros)
PLANTILLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantilla_packing.html")
VARIEDADES = {"TM": "Timpson", "AL": "Allison", "RG": "Red Globe", "AC": "Autumn Crisp", "CC": "Cotton Candy", "CH": "Candy Hearts"}


def filas_calidad(cat, var_de=None):
    """Categorizacion de racimos en campo (tabla de Pedregal) sumada por lote y dia:
    [fecha, lote, variedad, cat1, cat1.5, cat2, descarte, muestras, racimos]. Se guardan SUMAS para que el
    reporte pueda juntar dias y lotes y sacar el % correcto (igual que la plataforma)."""
    if cat is None or len(cat) == 0 or "lote_id" not in cat:
        return []
    c = cat.dropna(subset=["lote_id", "_fecha"]).copy()
    num = lambda col: pd.to_numeric(c[col], errors="coerce").fillna(0) if col in c else 0
    c["c1"] = num("categoria-cat-1") + num("categoria-cat1-premium")
    c["c15"], c["c2"], c["cd"] = num("categoria-cat-15"), num("categoria-cat-2"), num("categoria-descarte")
    c["rac"] = num("datos-generales-total-de-racimos")
    c["f"] = pd.to_datetime(c["_fecha"]).dt.strftime("%Y-%m-%d")
    g = c.groupby(["f", "lote_id"]).agg(c1=("c1", "sum"), c15=("c15", "sum"), c2=("c2", "sum"), cd=("cd", "sum"),
                                         n=("c1", "size"), rac=("rac", "sum")).reset_index()
    var_de = var_de or {}
    return [[r.f, f"Lote {str(r.lote_id).split('.')[1][1:].zfill(3)}", var_de.get(r.lote_id, ""),
             round(r.c1, 2), round(r.c15, 2), round(r.c2, 2), round(r.cd, 2), int(r.n), round(r.rac, 1)]
            for r in g.itertuples() if (r.c1 + r.c15 + r.c2 + r.cd) > 0]


def html_packing(d, tema="dark", generado="", calidad=None):
    """Pagina completa del reporte Lote Packing a partir de leer(): filtros de semana, fecha, lote y packing."""
    import json
    if d.empty:
        return ""
    d = d.copy()
    d["lt"] = [f"Lote {str(l).split('.')[1][1:].zfill(3)}" if isinstance(l, str) else "Ensayos" for l in d["lote_id"]]
    var = d["variedad"] if "variedad" in d else pd.Series("", index=d.index)
    d["va"] = ["Ensayos" if not isinstance(l, str) else VARIEDADES.get(str(v).strip(), str(v)) for l, v in zip(d["lote_id"], var)]
    d["pk"] = d["planta"].astype(str).str.replace(" - Ica", "", regex=False) if "planta" in d else "—"
    d["ca"] = pd.to_numeric(d.get("categoria"), errors="coerce").map(lambda x: "—" if pd.isna(x) else f"Cat {x:g}")
    d["cb"] = d["calibre"].astype(str).str.upper().str.strip() if "calibre" in d else "—"
    d["pr"] = d["presentacion"].astype(str).str.strip().str.capitalize() if "presentacion" in d else "—"
    d["cl"] = d["cliente"].astype(str).str.strip().str.title() if "cliente" in d else "—"
    d["f"] = d["fecha"].dt.strftime("%Y-%m-%d")
    g = d.groupby(["f", "lt", "va", "pk", "cb", "ca", "pr", "cl"])[["cajas_eq", "cajas", "kg"]].sum().reset_index()
    filas = [[r.f, r.lt, r.va, r.pk, r.cb, r.ca, r.pr, round(r.cajas_eq, 1), round(r.cajas, 1), round(r.kg, 1), r.cl]
             for r in g.itertuples()]
    with open(PLANTILLA, encoding="utf-8") as f:
        t = f.read()
    return (t.replace("__DATA__", json.dumps(filas, separators=(",", ":"), ensure_ascii=False))
             .replace("__CALIDAD__", json.dumps(calidad or [], separators=(",", ":"), ensure_ascii=False))
             .replace("__TEMA__", tema).replace("__GEN__", generado))


def html_completo(cuerpo):
    """Agrega el esqueleto HTML para usar el reporte fuera de la plataforma (GitHub / Streamlit Cloud)."""
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<style>*,*::before,*::after{box-sizing:border-box}body{margin:0;font:14px system-ui,sans-serif}'
            '[hidden]{display:none!important}</style>\n</head>\n<body>\n' + cuerpo + '\n</body>\n</html>\n')
