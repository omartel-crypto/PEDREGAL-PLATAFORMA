"""Calculos de cosecha (sin Streamlit, para poder probarlos).

Formulas acordadas con Oscar:
- Limpieza:   % de cada defecto = suma del defecto / suma de racimos por jaba.
              Desviacion = suma de todos los defectos; Calidad lograda = 100 - desviacion.
- Descartes:  igual, sobre el total de bayas (o racimos) evaluados.
- Peso:       peso de baya = promedio de peso de racimo / promedio de bayas por racimo.
- Brix:       rangos por variedad (bajo / tolerable / optimo / exceso > 20).
- Categoria:  suma de cada categoria / suma del total de racimos.
"""
import os
import re

import pandas as pd

INICIO_CAMPANIA = "2026-07-01"   # lo anterior es la cosecha pasada (ene-mar 2026)

TABLAS = {
    "limpieza": "ccc_pr_cosecha_optimizado",
    "categoria": "cc_categorizacion_de_racimos_cosecha_optimizado",
    "peso": "cc_pr_peso_de_racimo_cosecha_optimizado",
    "desc_bayas": "ccc_pr_descarte_bayas_optimizado",
    "desc_racimos": "ccc_pr_descarte_racimo_optimizado",
    "brix": "ccc_pr_brix_cosecha_optimizado",
    "jabas": "peso_de_jaba_vid",
    "temp": "temperaturas_campo_vid",
    "traza": "trazabilidad_de_jabas_amarillas_vid",
}
COL_LOTE = {"categoria": "datos-generales-lote", "peso": "datos-generales-lote-cuartel"}
GRUPO_COLOR = {"Condición": "#e8453c", "Calidad": "#f2a33a", "Plagas": "#8e44ad"}

# grupo por defecto de cada defecto (se puede corregir en Maestro/grupos_defectos.xlsx)
PLAGAS = ("chanchito", "mosca", "insecto")
CALIDAD = ("paludo", "pampano", "aureola", "uvilla", "pedunculo", "russet", "sol", "bajo-calibre",
           "falta-de-color", "apretado", "lenticela", "raqui-vigoroso", "descalibrad", "deforme",
           "atrazad", "verdes", "pequen", "astringente", "bajo-brix", "rac-descarte", "baya-verde")

BRIX_BINS = [(-1, 12, "<12"), (12, 13, "12"), (13, 14, "13"), (14, 14.5, "14–14.4"), (14.5, 15, "14.5–14.9"),
             (15, 15.5, "15–15.4"), (15.5, 16, "15.5–15.9"), (16, 16.5, "16–16.4"), (16.5, 17, "16.5–16.9"),
             (17, 17.5, "17–17.4"), (17.5, 18, "17.5–17.9"), (18, 19, "18"), (19, 20, "19"), (20, 21, "20"),
             (21, 99, ">20")]   # "20" = 20.0-20.9 ; ">20" = 21 o mas
BRIX_RANGOS = {"TIMPSON": (15.5, 16.5), "ALLISON": (16.5, 17.5)}   # (tolerable desde, optimo desde)
BRIX_DEFECTO = (16.0, 17.0)

NOMBRES = {"dano": "daño", "oidium": "oídio", "pudricion": "pudrición", "aranas": "arañas",
           "traslucidos": "traslúcidos", "pedunculo": "pedúnculo", "pampanos": "pámpanos",
           "pequenos": "pequeños", "atrazados": "atrasados", "raqui": "raquis", "greater than 5": "> 5",
           "rac ": "", "dg ": "", "dmy ": "", "dmn ": "", "tierra": "polvo"}


def nombre_defecto(col):
    t = col.replace("-", " ") + " "
    for a, b in NOMBRES.items():
        t = t.replace(a, b)
    t = re.sub(r"raquiss", "raquis", t).strip()
    return t[:1].upper() + t[1:]


def grupo_por_defecto(col):
    c = col.lower()
    if any(k in c for k in PLAGAS):
        return "Plagas"
    if c.startswith("rac-") or any(k in c for k in CALIDAD):
        return "Calidad"
    return "Condición"


def cargar_grupos(ruta=os.path.join("Maestro", "grupos_defectos.xlsx")):
    if not os.path.exists(ruta):
        return {}
    g = pd.read_excel(ruta, dtype=str).fillna("")
    return {r["columna"]: r["grupo"].strip().capitalize().replace("Condicion", "Condición")
            for _, r in g.iterrows() if r.get("grupo")}


def columnas_defecto(df):
    return [c for c in df.columns if re.match(r"^(dg|dmy|dmn|rac)-", c) and pd.api.types.is_numeric_dtype(df[c])]


def fecha(df):
    return pd.to_datetime(df["meta-fecha"].astype(str).str[:10], errors="coerce")


# ---------------------------------------------------------------- limpieza y descartes
def desviacion(df, col_total, grupos=None, col_buenos=None):
    """Resumen de defectos: total evaluado, % por defecto, % por grupo, desviacion y calidad lograda."""
    grupos = grupos or {}
    total = pd.to_numeric(df[col_total], errors="coerce").sum()
    cols = columnas_defecto(df)
    if not total or df.empty:
        return None
    pct = (df[cols].sum() / total * 100).sort_values(ascending=False)
    det = pd.DataFrame({"columna": pct.index, "pct": pct.values})
    det["defecto"] = det["columna"].map(nombre_defecto)
    det["grupo"] = det["columna"].map(lambda c: grupos.get(c) or grupo_por_defecto(c))
    desv = det["pct"].sum()
    out = {"muestras": len(df), "total": total, "por_muestra": total / len(df), "detalle": det,
           "desviacion": desv, "calidad": max(0.0, 100 - desv),
           "grupos": det.groupby("grupo")["pct"].sum().reindex(list(GRUPO_COLOR), fill_value=0).to_dict()}
    if col_buenos and col_buenos in df:
        out["buenos"] = pd.to_numeric(df[col_buenos], errors="coerce").sum() / total * 100
    if "desgrane-de-bayas" in df:
        d = pd.to_numeric(df["desgrane-de-bayas"], errors="coerce").dropna()
        out["desgrane"] = (d.mean(), d.max(), d.min()) if len(d) else None
    if "higiene-de-jaba" in df:
        h = df["higiene-de-jaba"].dropna().astype(str).str.strip().str.lower()
        out["higiene_mala"] = (h != "buena").mean() * 100 if len(h) else None
    return out


def cuadre(df, col_total, col_buenos, extras=()):
    """Revisa que cada muestra este bien clasificada: total = buenos + extras (ej. desgrane) + todos los defectos.
    Devuelve una fila por muestra con total, clasificado y diferencia (+ sobra sin clasificar, - se clasifico de mas)."""
    if df.empty or col_total not in df:
        return pd.DataFrame()
    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    cols = columnas_defecto(df)
    clas = df[cols].apply(num).sum(axis=1) + (num(df[col_buenos]) if col_buenos in df else 0)
    for e in extras:
        if e in df:
            clas = clas + num(df[e])
    tot = pd.to_numeric(df[col_total], errors="coerce")
    out = pd.DataFrame({"fecha": df.get("_fecha"), "hora": df.get("meta-hora"), "cuartel": df.get("lote-cuartel"),
                        "evaluador": df.get("meta-evaluador"), "total": tot, "clasificado": clas})
    out["diferencia"] = out["total"] - out["clasificado"]
    return out.dropna(subset=["total"])


def por_dia(df, col_total, grupos=None, col_buenos=None):
    filas = []
    for f, g in df.assign(_f=fecha(df)).dropna(subset=["_f"]).groupby("_f"):
        r = desviacion(g, col_total, grupos, col_buenos)
        if r:
            top = r["detalle"].iloc[0]
            filas.append({"fecha": f, "muestras": r["muestras"], "desviacion": r["desviacion"],
                          "calidad": r["calidad"], "top": top["defecto"], "top_pct": top["pct"],
                          "top_grupo": top["grupo"], **{f"g_{k}": v for k, v in r["grupos"].items()}})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- peso de racimos
def peso(df):
    p = pd.to_numeric(df["medidas-peso-de-racimo-kg"], errors="coerce")
    p = p.where(p <= 20, p / 1000)                    # algunos dias se anoto en gramos (ej. 562 en vez de 0.562)
    p = p.where((p >= 0.05) & (p <= 3))               # fuera de rango = error de registro
    b = pd.to_numeric(df["medidas-cantidad-de-bayas"], errors="coerce")
    r = pd.to_numeric(df.get("medidas-longitud-de-raquis"), errors="coerce")
    if p.notna().sum() == 0:
        return None
    out = {"muestras": int(p.notna().sum()), "peso": p.mean(), "bayas": b.mean(),
           "peso_baya_g": (p.mean() / b.mean() * 1000) if b.mean() else None,
           "raquis": r.mean() if r is not None else None, "p_min": p.min(), "p_max": p.max()}
    d = df.assign(_p=p, _b=b)
    for clave, col in (("por_calibre", "datos-generales-calibre"), ("por_tipo", "medidas-tipo-de-racimo")):
        if col in d:
            t = d.groupby(col).agg(peso=("_p", "mean"), bayas=("_b", "mean"), n=("_p", "count")).reset_index()
            t["peso_baya_g"] = t["peso"] / t["bayas"] * 1000
            out[clave] = t.rename(columns={col: "grupo"}).sort_values("n", ascending=False)
    return out


def peso_por_dia(df):
    filas = []
    for f, g in df.assign(_f=fecha(df)).dropna(subset=["_f"]).groupby("_f"):
        r = peso(g)
        if r:
            filas.append({"fecha": f, "muestras": r["muestras"], "peso": r["peso"], "bayas": r["bayas"],
                          "peso_baya_g": r["peso_baya_g"]})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- brix
def rangos_brix(variedad_cod):
    return BRIX_RANGOS.get((variedad_cod or "").upper(), BRIX_DEFECTO)


def brix(df, variedad_cod):
    x = pd.to_numeric(df["grado-brix"], errors="coerce").dropna()
    if x.empty:
        return None
    tol, opt = rangos_brix(variedad_cod)
    n = len(x)
    hist = [(lab, ((x >= a) & (x < b)).sum() / n * 100,
             "exceso" if lab == ">20" else ("bajo" if b <= tol else ("tolerable" if b <= opt else "optimo")))
            for a, b, lab in BRIX_BINS]
    return {"muestras": n, "prom": x.mean(), "moda": x.round(1).mode().iloc[0], "max": x.max(), "min": x.min(),
            "bajo": (x < tol).mean() * 100, "tolerable": ((x >= tol) & (x < opt)).mean() * 100,
            "optimo": ((x >= opt) & (x < 21)).mean() * 100, "exceso": (x >= 21).mean() * 100,
            "hist": hist, "tol": tol, "opt": opt}


def brix_por_dia(df, variedad_cod):
    filas = []
    for f, g in df.assign(_f=fecha(df)).dropna(subset=["_f"]).groupby("_f"):
        r = brix(g, variedad_cod)
        if r:
            filas.append({"fecha": f, **{k: r[k] for k in ("muestras", "prom", "bajo", "tolerable", "optimo", "exceso")}})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- categorizacion
CALIBRES = [("ml", "ML", 16), ("l", "L", 17.5), ("x", "X", 19), ("sx", "SX", 21), ("jj", "JJ", 23),
            ("3j", "3J", 25), ("4j", "4J", 27), ("5j", "5J", 29), ("j", "J", 21)]


def categoria(df):
    tot = pd.to_numeric(df["datos-generales-total-de-racimos"], errors="coerce")
    T = tot.sum()
    if not T:
        return None

    def pct(cols):
        # cada seccion (categoria, color, calibre, raquis) suma 100%: se divide entre el total de esa seccion,
        # asi una muestra que no lleno una seccion no la baja (igual que el reporte de Oscar)
        tot_sec = df[cols].sum().sum()
        return {c: (df[c].sum() / tot_sec * 100 if tot_sec else 0.0) for c in cols}

    cats = [c for c in df.columns if c.startswith("categoria-") and "margen" not in c]
    verdes = [c for c in df.columns if c.startswith("color-verde-") and "margen" not in c]
    rojas = [c for c in df.columns if c.startswith("color-roja-y-negra-") and "margen" not in c]
    sin = [c for c in df.columns if c.startswith("sin-semilla-") and "margen" not in c]
    con = [c for c in df.columns if c.startswith("con-semilla-") and "margen" not in c]
    raq = [c for c in df.columns if c.startswith("raquis-") and "margen" not in c]
    color_cols = verdes if df[verdes].sum().sum() >= df[rojas].sum().sum() else rojas
    cal_cols = sin if df[sin].sum().sum() >= df[con].sum().sum() else con

    def etiqueta_cal(c):
        cod = c.replace("sin-semilla-", "").replace("con-semilla-rojo-y-negra-", "").split("-")[0]
        return next((lab for k, lab, _ in CALIBRES if k == cod), cod.upper())

    def etiqueta(c, pref):
        t = c.replace(pref, "").replace("-", " ")
        t = (t.replace("cat1 premium", "Cat 1 Premium").replace("cat 15", "Cat 1.5").replace("cat 1", "Cat 1")
             .replace("cat 2", "Cat 2").replace("full color r", "full color").replace("raquis raquis", "raquis")
             .replace("greater than 7mm", "> 7 mm").replace("less than 2mm", "< 2 mm")
             .replace("ambar", "ámbar").replace("debil", "débil"))
        return t[:1].upper() + t[1:]

    def rango_cal(c):
        m = re.search(r"-(\d+)-(\d+|mm)$", c)
        if not m:
            return ""
        a, b = m.group(1), m.group(2)
        a = f"{a[:2]}.{a[2:]}" if len(a) > 2 else a
        b = "+" if b == "mm" else (f"{b[:2]}.{b[2:]}" if len(b) > 2 else b)
        return f"{a}–{b} mm" if b != "+" else f"{a} mm +"

    return {
        "muestras": len(df), "racimos_prom": tot.mean(), "tipo_color": "verde" if color_cols is verdes else "roja",
        "categorias": [(etiqueta(c, "categoria-"), v) for c, v in pct(cats).items()],
        "color": [(etiqueta(c, "color-verde-" if color_cols is verdes else "color-roja-y-negra-"), v)
                  for c, v in pct(color_cols).items()],
        "calibre": [(etiqueta_cal(c), rango_cal(c), v) for c, v in pct(cal_cols).items()],
        "raquis": [(etiqueta(c, "raquis-"), v) for c, v in pct(raq).items()],
    }


def categoria_por_dia(df):
    filas = []
    for f, g in df.assign(_f=fecha(df)).dropna(subset=["_f"]).groupby("_f"):
        r = categoria(g)
        if r:
            cats = dict(r["categorias"])
            cal = max(r["calibre"], key=lambda x: x[2]) if r["calibre"] else ("—", "", 0)
            filas.append({"fecha": f, "muestras": r["muestras"], "cat1": cats.get("Cat 1", 0) + cats.get("Cat 1 Premium", 0),
                          "descarte": cats.get("Descarte", 0), "calibre": cal[0], "calibre_pct": cal[2]})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- descarte de bayas (base por lote)
def descarte_bayas(desc, peso_df, limp_df, grupos=None):
    """% de cada defecto de descarte de bayas, por lote.
    base = bayas por racimo (promedio del lote, tabla de peso) x racimos por jaba (promedio del lote, tabla de limpieza)
    % defecto = promedio por jaba de ese defecto / base x 100. No se suma un total."""
    grupos = grupos or {}
    bayas = pd.to_numeric(peso_df.get("medidas-cantidad-de-bayas"), errors="coerce").mean() if len(peso_df) else None
    rxj = pd.to_numeric(limp_df.get("racimos-por-jaba"), errors="coerce").mean() if len(limp_df) else None
    cols = columnas_defecto(desc) if len(desc) else []
    out = {"muestras": len(desc), "bayas_racimo": bayas, "racimos_jaba": rxj, "base": None, "detalle": pd.DataFrame()}
    if bayas is None or rxj is None or pd.isna(bayas) or pd.isna(rxj) or not cols:
        return out
    base = bayas * rxj
    prom = desc[cols].apply(pd.to_numeric, errors="coerce").fillna(0).mean()
    det = pd.DataFrame({"columna": prom.index, "prom_jaba": prom.values, "pct": prom.values / base * 100})
    det["defecto"] = det["columna"].map(nombre_defecto)
    det["grupo"] = det["columna"].map(lambda c: grupos.get(c) or grupo_por_defecto(c))
    out.update(base=base, detalle=det.sort_values("pct", ascending=False).reset_index(drop=True))
    for col, k in (("n-bayas-buenas", "buenas"), ("desgrane-de-bayas", "desgrane")):
        if col in desc:
            p = pd.to_numeric(desc[col], errors="coerce").mean()
            out[k] = (p, p / base * 100) if pd.notna(p) else None
    return out


# ---------------------------------------------------------------- peso de jabas
def peso_jaba(df):
    p = pd.to_numeric(df.get("peso-de-jaba-kg"), errors="coerce")
    n = pd.to_numeric(df.get("n-racimo-por-jaba"), errors="coerce")
    if p is None or p.notna().sum() == 0:
        return None
    kr = (p / n).where(n > 0)
    out = {"muestras": int(p.notna().sum()), "peso": p.mean(), "p_min": p.min(), "p_max": p.max(),
           "racimos": n.mean(), "kg_racimo": kr.mean(), "valores": p.dropna()}
    if "turno" in df:
        t = df.assign(_p=p).dropna(subset=["_p"]).groupby(df["turno"].fillna("—").astype(str).str.title())["_p"]
        out["por_turno"] = t.agg(["mean", "count"]).reset_index().rename(columns={"turno": "grupo"})
    if "cuartel_id" in df:
        c = df.assign(_p=p, _n=n).dropna(subset=["_p"]).groupby("cuartel_id").agg(peso=("_p", "mean"), racimos=("_n", "mean"),
                                                                                  n=("_p", "count"))
        out["por_cuartel"] = c.reset_index().sort_values("peso", ascending=False)
    return out


def peso_jaba_por_dia(df):
    filas = []
    for f, g in df.assign(_f=fecha(df)).dropna(subset=["_f"]).groupby("_f"):
        r = peso_jaba(g)
        if r:
            filas.append({"fecha": f, "muestras": r["muestras"], "peso": r["peso"], "racimos": r["racimos"]})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- temperaturas de campo
def hora_de(df):
    """Hora (0-23) de cada medicion: columna 'hora' (ej. '12:00 PM') o, si falta, 'meta-hora'."""
    h = pd.Series(pd.NA, index=df.index, dtype="Float64")
    if "hora" in df:
        t = pd.to_datetime(df["hora"].astype(str).str.strip().str.upper(), format="%I:%M %p", errors="coerce")
        h = t.dt.hour.astype("Float64")
    if "meta-hora" in df:
        m = pd.to_datetime(df["meta-hora"].astype(str).str[:8], format="%H:%M:%S", errors="coerce").dt.hour.astype("Float64")
        h = h.fillna(m)
    return h


def temperaturas(df):
    a = pd.to_numeric(df.get("t-ambiente"), errors="coerce")
    p = pd.to_numeric(df.get("t-pulpa"), errors="coerce")
    if p is None or (p.notna().sum() == 0 and a.notna().sum() == 0):
        return None
    d = df.assign(_a=a, _p=p, _h=hora_de(df), _f=fecha(df).dt.normalize())
    imax = d["_p"].idxmax() if d["_p"].notna().any() else None
    return {"muestras": int(p.notna().sum()), "pulpa": p.mean(), "ambiente": a.mean(), "dif": (a - p).mean(),
            "p_max": p.max(), "p_min": p.min(), "a_max": a.max(),
            "max_cuando": (d.at[imax, "_f"], d.at[imax, "_h"]) if imax is not None else None,
            "por_hora": d.dropna(subset=["_h"]).groupby("_h").agg(pulpa=("_p", "mean"), ambiente=("_a", "mean"),
                                                                   n=("_p", "count")).reset_index(),
            "por_dia": d.dropna(subset=["_f"]).groupby("_f").agg(pulpa=("_p", "mean"), ambiente=("_a", "mean"),
                                                                p_max=("_p", "max"), n=("_p", "count")).reset_index(),
            "dia_hora": d.dropna(subset=["_f", "_h"]).groupby(["_f", "_h"])["_p"].mean().reset_index()}


# ---------------------------------------------------------------- tiempos: trazabilidad de jabas amarillas
# tramos entre puntos de evaluacion, de la cosecha hasta la llegada a recepcion (punto 11)
TRAMOS = [(1, 2, "Cosecha de fruta", "Campo"), (2, 3, "Espera a limpieza", "Campo"), (3, 4, "Limpieza de fruta", "Campo"),
          (4, 5, "Espera en campo", "Campo"), (5, 6, "Espera en calle", "Campo"), (6, 7, "Espera de estiba", "Carga"),
          (7, 8, "Estibado", "Carga"), (8, 9, "Campo a acopio", "Traslado"), (9, 10, "En centro de acopio", "Acopio"),
          (10, 11, "Acopio a packing", "Traslado")]
PUNTOS = {1: "Cosecha", 2: "Llenado de jaba", 3: "Inicio limpieza", 4: "Fin limpieza", 5: "Sacado a calle",
          6: "Llegada a tractor", 7: "Inicio estiba", 8: "Fin estiba", 9: "Llega a acopio", 10: "Sale de acopio",
          11: "Llega a recepción"}
MAX_TRAMO_MIN = 12 * 60          # se descartan tramos imposibles (negativos o de mas de 12 h)


_RE_HORA = re.compile(r"(?<!\d)([01]?\d|2[0-3])\s*[:.hH]\s*([0-5]\d)(?!\d)\s*([aApP])?\.?\s*[mM]?", re.I)


def _hora_txt(txt):
    """'Llegada a recepcion 14:32 Pm' -> (14, 32); '2:32 pm' -> (14, 32); sin hora -> None."""
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None
    m = _RE_HORA.search(str(txt))
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ap == "p" and h < 12:
        h += 12
    elif ap == "a" and h == 12:
        h = 0
    return h, mi


def hora_real(d):
    """Hora de cada registro y de donde salio, en este orden:
    1) un campo propio de hora (columna que empiece con 'hora', ej. 'hora' u 'hora-real') que se agregara a la cartilla,
    2) una hora escrita en observaciones/comentarios (ej. 'Llegada a recepcion 14:32 pm'),
    3) la hora automatica en que se guardo la muestra en el app (meta-hora)."""
    fecha_txt = d["meta-fecha"].astype(str).str[:10]
    t_app = pd.to_datetime(fecha_txt + " " + d["meta-hora"].astype(str).str[:8], errors="coerce")
    t, fuente = t_app.copy(), pd.Series("app", index=d.index)
    obs = next((c for c in d.columns if c.startswith("observacion")), None)
    campos = [c for c in d.columns if re.match(r"^hora", c)]
    for col, nombre in ([(obs, "comentario")] if obs else []) + [(c, "campo hora") for c in campos]:
        hm = d[col].map(_hora_txt)
        ok = hm.notna()
        if not ok.any():
            continue
        nuevo = pd.to_datetime(fecha_txt[ok] + " " + hm[ok].map(lambda x: f"{x[0]:02d}:{x[1]:02d}:00"), errors="coerce")
        # sin am/pm, una hora chica (ej. 2:32) escrita en la tarde se entiende como pm
        sin_ap = ~d.loc[ok, col].astype(str).str.contains(r"\d\s*[aApP]\.?\s*[mM]", regex=True)
        tarde = sin_ap & (nuevo.dt.hour < 7) & (t_app[ok].dt.hour >= 12)
        nuevo[tarde] = nuevo[tarde] + pd.Timedelta(hours=12)
        buenos = nuevo.notna()
        idx = nuevo[buenos].index
        t[idx] = nuevo[buenos]
        fuente[idx] = nombre
    return t, fuente


def viajes(df):
    """Una fila por viaje de jaba (codigo + recorrido), con la hora de cada punto 1..11.
    La misma jaba se reutiliza: empieza un viaje nuevo cuando el punto no avanza o pasan mas de 24 h."""
    if df.empty or "punto-de-evaluacion" not in df:
        return pd.DataFrame()
    d = df.copy()
    d["_n"] = pd.to_numeric(d["punto-de-evaluacion"].astype(str).str.extract(r"^\s*(\d+)")[0], errors="coerce")
    d["_t"], d["_fuente"] = hora_real(d)
    d["_j"] = d["jaba"].astype(str).str.strip()
    d = d.dropna(subset=["_n", "_t"])
    d = d[(d["_n"] <= 11) & (d["_j"] != "") & (d["_j"].str.lower() != "none")].sort_values(["_j", "_t", "_n"])
    if d.empty:
        return pd.DataFrame()
    nuevo = (d["_j"] != d["_j"].shift()) | (d["_n"] <= d["_n"].shift()) | ((d["_t"] - d["_t"].shift()).dt.total_seconds() > 86400)
    d["_viaje"] = nuevo.cumsum()
    w = d.pivot_table(index="_viaje", columns="_n", values="_t", aggfunc="min")
    w.columns = [int(c) for c in w.columns]
    info = d.groupby("_viaje").agg(jaba=("_j", "first"), lote_id=("lote_id", "first"), turno=("turno", "first"),
                                    inicio=("_t", "min"))
    w = info.join(w)
    for a, b, nombre, _ in TRAMOS:
        if a in w and b in w:
            m = (w[b] - w[a]).dt.total_seconds() / 60
            w[nombre] = m.where((m >= 0) & (m <= MAX_TRAMO_MIN))
    if 1 in w and 11 in w:
        t = (w[11] - w[1]).dt.total_seconds() / 60
        w["total"] = t.where((t >= 0) & (t <= 24 * 60))
    if 1 in w and 9 in w:
        t = (w[9] - w[1]).dt.total_seconds() / 60
        w["cos_acopio"] = t.where((t >= 0) & (t <= 24 * 60))
    if 9 in w and 11 in w:
        t = (w[11] - w[9]).dt.total_seconds() / 60
        w["acopio_rec"] = t.where((t >= 0) & (t <= 24 * 60))
    w["fecha"] = (w[1] if 1 in w else w["inicio"]).fillna(w["inicio"]).dt.normalize()
    return w.reset_index(drop=True)


def tiempos(df):
    w = viajes(df)
    if w.empty:
        return None
    tr = []
    for a, b, nombre, fase in TRAMOS:
        v = w[nombre].dropna() if nombre in w else pd.Series(dtype=float)
        tr.append({"de": a, "a": b, "tramo": nombre, "fase": fase, "prom": v.mean() if len(v) else None,
                   "max": v.max() if len(v) else None, "n": len(v)})
    tot = w["total"].dropna() if "total" in w else pd.Series(dtype=float)
    fu = hora_real(df)[1] if "meta-hora" in df else pd.Series(dtype=str)
    out = {"viajes": w, "tramos": pd.DataFrame(tr), "jabas": w["jaba"].nunique(), "n_total": len(tot),
           "fuentes": fu.value_counts().to_dict(),
           "total": tot.mean() if len(tot) else None, "t_max": tot.max() if len(tot) else None,
           "t_min": tot.min() if len(tot) else None,
           "cos_acopio": w["cos_acopio"].mean() if "cos_acopio" in w else None,
           "acopio_rec": w["acopio_rec"].mean() if "acopio_rec" in w else None}
    if len(tot):
        out["por_dia"] = w.dropna(subset=["total"]).groupby("fecha").agg(total=("total", "mean"), t_max=("total", "max"),
                                                                         n=("total", "count")).reset_index()
    return out
