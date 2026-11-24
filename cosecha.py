"""Logica de cosecha: jabas diarias por lote, avance, ritmo y estado.

Fuente: Maestro/jabas_diarias.xlsx (despues podra venir de Google Drive)
  hoja "jabas"      fecha | lote_id | jabas | grupos | comentario
  hoja "lotes"      lote_id | jabas_estimadas | inicio | fin | nota
  hoja "cuarteles"  fecha | cuartel_id | estado        (opcional: En cosecha / Terminado)
"""
import os

import pandas as pd

RUTA = os.path.join("Maestro", "jabas_diarias.xlsx")
ESTADO_COLOR = {"En cosecha": "#f28c28", "Terminado": "#2e9e4f", "Pendiente": "#c9c4b8"}


def _norm_lote(x):
    if not isinstance(x, str):
        return None
    return " ".join(x.upper().split()).replace(" .", ".")


def cargar(ruta=RUTA):
    vacio = {"jabas": pd.DataFrame(columns=["fecha", "lote_id", "jabas", "grupos", "comentario"]),
             "lotes": pd.DataFrame(columns=["lote_id", "jabas_estimadas", "inicio", "fin", "nota"]),
             "cuarteles": pd.DataFrame(columns=["fecha", "cuartel_id", "estado"])}
    if not os.path.exists(ruta):
        return vacio, False
    hojas = pd.read_excel(ruta, sheet_name=None)
    hojas = {k.strip().lower(): v for k, v in hojas.items()}
    out = {}
    for nombre, base in vacio.items():
        df = hojas.get(nombre, base.copy())
        df.columns = [str(c).strip().lower() for c in df.columns]
        for c in base.columns:
            if c not in df:
                df[c] = None
        out[nombre] = df[list(base.columns)].copy()
    j = out["jabas"]
    j["fecha"] = pd.to_datetime(j["fecha"], errors="coerce", dayfirst=True).dt.normalize()
    j["lote_id"] = j["lote_id"].map(_norm_lote)
    j["jabas"] = pd.to_numeric(j["jabas"], errors="coerce")
    j["grupos"] = pd.to_numeric(j["grupos"], errors="coerce")
    out["jabas"] = j.dropna(subset=["fecha", "lote_id", "jabas"])
    l = out["lotes"]
    l["lote_id"] = l["lote_id"].map(_norm_lote)
    l["jabas_estimadas"] = pd.to_numeric(l["jabas_estimadas"], errors="coerce")
    for c in ("inicio", "fin"):
        l[c] = pd.to_datetime(l[c], errors="coerce", dayfirst=True)
    out["lotes"] = l.dropna(subset=["lote_id"])
    c = out["cuarteles"]
    c["fecha"] = pd.to_datetime(c["fecha"], errors="coerce", dayfirst=True)
    c["cuartel_id"] = c["cuartel_id"].map(_norm_lote)
    out["cuarteles"] = c.dropna(subset=["cuartel_id", "estado"])
    return out, True


def por_dia(jabas, lote_id):
    d = jabas[jabas["lote_id"] == lote_id].groupby("fecha", as_index=False).agg(
        jabas=("jabas", "sum"), grupos=("grupos", "max"),
        comentario=("comentario", lambda s: " · ".join(str(x) for x in s.dropna() if str(x).strip())))
    d = d.sort_values("fecha")
    d["acumulado"] = d["jabas"].cumsum()
    return d


def resumen_lotes(jabas, lotes):
    """Una fila por lote con inicio, fin, dias, total, ritmo, avance y estado."""
    ids = sorted(set(jabas["lote_id"]) | set(lotes["lote_id"]))
    filas = []
    for lid in ids:
        d = por_dia(jabas, lid)
        info = lotes[lotes["lote_id"] == lid]
        info = info.iloc[0] if len(info) else pd.Series(dtype=object)
        total = d["jabas"].sum() if len(d) else 0
        est = info.get("jabas_estimadas")
        est = est if pd.notna(est) and est > 0 else None
        inicio = info.get("inicio") if pd.notna(info.get("inicio")) else (d["fecha"].min() if len(d) else None)
        fin = info.get("fin") if pd.notna(info.get("fin")) else None
        ritmo = d["jabas"].tail(3).mean() if len(d) else None
        avance = total / est if est else None
        restante = max(est - total, 0) if est else None
        dias_rest = (restante / ritmo) if (restante is not None and ritmo) else None
        fin_est = (d["fecha"].max() + pd.Timedelta(days=int(round(dias_rest)))) \
            if dias_rest is not None and len(d) and not fin else None
        if fin is not None or (avance is not None and avance >= 0.999):
            estado = "Terminado"
        elif total > 0:
            estado = "En cosecha"
        else:
            estado = "Pendiente"
        mejor = d.loc[d["jabas"].idxmax()] if len(d) else None
        filas.append({
            "lote_id": lid, "estado": estado, "inicio": inicio, "fin": fin,
            "ultimo_dia": d["fecha"].max() if len(d) else None,
            "dias": d["fecha"].nunique(), "total": total, "estimado": est,
            "avance": avance, "restante": restante, "ritmo": ritmo, "fin_estimado": fin_est,
            "mejor_dia": mejor["fecha"] if mejor is not None else None,
            "mejor_jabas": mejor["jabas"] if mejor is not None else None,
            "ultimo_jabas": d["jabas"].iloc[-1] if len(d) else None,
            "grupos": d["grupos"].dropna().iloc[-1] if len(d) and d["grupos"].notna().any() else None,
            "comentario": next((c for c in reversed(d["comentario"].tolist()) if c), "") if len(d) else "",
        })
    return pd.DataFrame(filas)


def estado_cuarteles(cuarteles):
    """Ultimo estado informado de cada cuartel."""
    if cuarteles.empty:
        return {}
    c = cuarteles.sort_values("fecha").groupby("cuartel_id").tail(1)
    return dict(zip(c["cuartel_id"], c["estado"].str.strip().str.capitalize()))
