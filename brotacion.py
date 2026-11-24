"""Calculo de % de brotacion por cuartel y lote (ultima fecha evaluada).

% Brotacion = (puntas verdes + hojas desplegadas) / total de yemas
Total de yemas = receso + danadas + hinchadas + algodonosas + puntas verdes + hojas desplegadas
"""
import re
import unicodedata

import pandas as pd

# (clave, nombre, color) en el orden fenologico del reporte
ETAPAS = [
    ("receso", "Receso", "#f2b8bf"),
    ("danada", "Dañadas", "#d9434f"),
    ("hinchada", "Hinchadas", "#f8c98a"),
    ("algodon", "Algodonosas", "#a57a3e"),
    ("punta_verde", "Puntas verdes", "#6fd99a"),
    ("hoja", "Hojas desplegadas", "#0a8f3a"),
]
BROTADAS = ("punta_verde", "hoja")


def _n(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", x)


REGLAS = {
    "receso": lambda c: "receso" in c,
    "danada": lambda c: "danad" in c,
    "hinchada": lambda c: "hinchad" in c,
    "algodon": lambda c: "algodon" in c,
    "punta_verde": lambda c: "punta" in c and "verde" in c,
    "hoja": lambda c: "hoja" in c and "despleg" in c,
}


def detectar(columnas):
    """Devuelve {etapa: columna} si encuentra las 6 etapas; si no, None.
    Prefiere columnas de conteo antes que las de porcentaje."""
    res = {}
    for etapa, regla in REGLAS.items():
        cand = [c for c in columnas if regla(_n(c))]
        conteo = [c for c in cand if not any(k in _n(c) for k in ("porc", "pct", "percent"))
                  and "%" not in str(c)]
        elegido = (conteo or cand or [None])[0]
        if elegido is None:
            return None
        res[etapa] = elegido
    return res


def _pct(df):
    claves = [e[0] for e in ETAPAS]
    df["total"] = df[claves].sum(axis=1)
    df["pct_brot"] = (df[list(BROTADAS)].sum(axis=1) / df["total"].where(df["total"] > 0)) * 100
    for k in claves:
        df[f"pct_{k}"] = df[k] / df["total"].where(df["total"] > 0) * 100
    return df


def resumir(datos, col_union, col_fecha, cols_etapa, mapa_valores):
    """datos: registros crudos. mapa_valores: DataFrame v -> lote_id, cuartel_id.
    Devuelve (por_cuartel, por_lote, historia)."""
    claves = [e[0] for e in ETAPAS]
    d = datos[[col_union, col_fecha] + [cols_etapa[k] for k in claves]].copy()
    d.columns = ["v", "fecha"] + claves
    d["v"] = d["v"].astype(str)
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.normalize()
    for k in claves:
        d[k] = pd.to_numeric(d[k], errors="coerce").fillna(0)
    d = d.merge(mapa_valores[["v", "lote_id", "cuartel_id"]], on="v", how="inner")
    d = d.dropna(subset=["cuartel_id", "fecha"])

    historia = d.groupby(["lote_id", "cuartel_id", "fecha"], as_index=False)[claves].sum()
    historia["evaluaciones"] = d.groupby(["lote_id", "cuartel_id", "fecha"]).size().values
    historia = _pct(historia)

    ult = historia.groupby("cuartel_id")["fecha"].transform("max")
    por_cuartel = historia[historia["fecha"] == ult].reset_index(drop=True)

    por_lote = por_cuartel.groupby("lote_id", as_index=False).agg(
        **{k: (k, "sum") for k in claves}, fecha=("fecha", "max"),
        cuarteles=("cuartel_id", "nunique"))
    por_lote = _pct(por_lote)
    return por_cuartel, por_lote, historia


def total_general(por_cuartel):
    claves = [e[0] for e in ETAPAS]
    s = por_cuartel[claves].sum()
    tot = s.sum()
    return (s[list(BROTADAS)].sum() / tot * 100) if tot else None


def evolucion_lote(historia, lote_id):
    """% de brotacion del lote por semana: en cada semana toma la ultima evaluacion de cada cuartel."""
    claves = [e[0] for e in ETAPAS]
    h = historia[historia["lote_id"] == lote_id].copy()
    if h.empty:
        return h
    h["semana"] = h["fecha"] - pd.to_timedelta(h["fecha"].dt.weekday, unit="D")
    h = h.sort_values("fecha").groupby(["semana", "cuartel_id"], as_index=False).tail(1)
    s = h.groupby("semana", as_index=False).agg(**{k: (k, "sum") for k in claves},
                                                 cuarteles=("cuartel_id", "nunique"),
                                                 fecha=("fecha", "max"))
    return _pct(s)
