"""Lectura y limpieza de la base maestra (Excel descargado del Google Sheet).

Una fila por cuartel y campana. La llave es la columna "Area de Manejo"
(FUNDO.LOTE.CUARTEL), igual que en el mapa.
"""
import glob
import os
import re
import unicodedata

import pandas as pd

LLAVE = "Área de Manejo"

# nombre de columna en el Excel -> nombre en la base
COLUMNAS = {
    "Área de Manejo": "cuartel_id", "Año": "anio", "Campaña": "campania", "Fundo": "fundo",
    "Lote": "lote_num", "Cuartel": "cuartel", "Variedad": "variedad", "Patrón": "patron",
    "Jefe de campo": "jefe_campo", "Encargado de lote": "encargado_lote",
    "Aplicación de Cianamida": "fecha_cianamida", "Producto": "producto_cianamida",
    "# Pasadas": "pasadas", "1° Dosis": "dosis_1", "2° Dosis": "dosis_2", "Dosis Total": "dosis_total",
    "Mojamiento": "mojamiento", "Tipo de Parrón": "tipo_parron", "Mes Plantación": "fecha_plantacion",
    "Mes Producción": "fecha_produccion", "Supervisor De CC.": "supervisor_cc", "Densidad": "densidad",
    "Total Hectareas": "ha_lote",
}


def buscar_excel(carpeta_base="."):
    """Encuentra el .xlsx dentro de la carpeta maestro/Maestro."""
    for nombre in ("maestro", "Maestro", "MAESTRO"):
        archivos = [a for a in glob.glob(os.path.join(carpeta_base, nombre, "*.xlsx"))
                    if not os.path.basename(a).startswith("~$")
                    and not os.path.basename(a).lower().startswith("jabas")]   # ese es el de cosecha
        if archivos:
            return max(archivos, key=os.path.getmtime)
    return None


def _txt(x):
    if pd.isna(x):
        return None
    s = re.sub(r"\s+", " ", str(x)).strip()
    return s or None


def _dosis(x):
    if not isinstance(x, str):
        return None
    pct = x.strip().endswith("%")
    try:
        v = float(x.strip().rstrip("%").replace(",", "."))
    except ValueError:
        return x
    if not pct and v <= 1:
        v *= 100
    return f"{v:g}%"


def codigo_variedad(nombre):
    """'Autumn Crisp' -> 'AUTUMN_CRISP' (mismo codigo que usa el mapa)."""
    if not isinstance(nombre, str) or not nombre:
        return ""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[´'`]", "", s)
    return re.sub(r"[^A-Z0-9]+", "_", s).strip("_")


def leer(ruta):
    xls = pd.ExcelFile(ruta)
    hoja = next((h for h in xls.sheet_names
                 if LLAVE in pd.read_excel(xls, sheet_name=h, nrows=0).columns), None)
    if hoja is None:
        raise ValueError(f"Ninguna hoja tiene la columna '{LLAVE}'. Hojas: {xls.sheet_names}")
    df = pd.read_excel(xls, sheet_name=hoja)
    faltan = [c for c in ("Área de Manejo", "Año", "Fundo", "Variedad") if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en '{hoja}': {faltan}")
    df = df[[c for c in COLUMNAS if c in df.columns]].rename(columns=COLUMNAS)

    for c in ("cuartel_id", "fundo", "variedad", "patron", "jefe_campo", "encargado_lote",
              "producto_cianamida", "tipo_parron", "supervisor_cc", "campania",
              "dosis_1", "dosis_2", "dosis_total"):
        if c in df:
            df[c] = df[c].map(_txt)
    for c in ("dosis_1", "dosis_2", "dosis_total"):
        if c in df:   # 0.035 -> "3.5%" ; "3.5%" se queda igual
            df[c] = df[c].map(_dosis)
    df["cuartel_id"] = df["cuartel_id"].str.upper()
    df["cuartel"] = df["cuartel"].map(_txt).astype(object)
    df["patron"] = df["patron"].map(
        lambda p: "/".join(x.strip().title() for x in p.split("/")) if isinstance(p, str) else None)
    df["patron"] = df["patron"].str.replace("So4", "SO4", regex=False)
    for c in ("fecha_cianamida", "fecha_plantacion", "fecha_produccion"):
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("anio", "pasadas", "mojamiento", "densidad", "ha_lote"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["lote_id"] = df["cuartel_id"].str.rsplit(".", n=1).str[0]
    df["variedad_cod"] = df["variedad"].map(codigo_variedad)

    df = df.dropna(subset=["cuartel_id", "anio"])
    # "Total Hectareas" viene a veces por cuartel y a veces repetido con el total del lote.
    # Si todos los cuarteles de un lote (en una campana) tienen el mismo valor, es el total del lote.
    df = df.rename(columns={"ha_lote": "ha_excel"})
    g = df.groupby(["lote_id", "anio"])["ha_excel"]
    repetido = (g.transform("size") > 1) & (g.transform("nunique") == 1)
    df["ha_cuartel"] = df["ha_excel"].where(~repetido)
    df["ha_lote"] = df["ha_excel"].where(repetido, g.transform("sum").where(g.transform("count") > 0))
    duplicados = df[df.duplicated(["cuartel_id", "anio"], keep=False)].copy()
    df = df.drop_duplicates(["cuartel_id", "anio"], keep="last")
    df["anio"] = df["anio"].astype(int)
    actual = df.sort_values("anio").groupby("cuartel_id", as_index=False).tail(1).reset_index(drop=True)
    return hoja, df.reset_index(drop=True), actual, duplicados


def validar(actual, features, valores_evaluaciones=None):
    """Compara la campana vigente con el mapa (y opcionalmente con codigos de evaluaciones).
    Devuelve {nombre_hoja: DataFrame} para el reporte."""
    mapa = pd.DataFrame([f["properties"] for f in features])
    vig = actual[actual["anio"] == actual["anio"].max()]
    rep = {}
    rep["Excel sin polígono"] = (vig[~vig["cuartel_id"].isin(mapa["cuartel_id"])]
                                 [["cuartel_id", "variedad", "ha_lote", "anio"]].sort_values("cuartel_id"))
    rep["Polígono sin Excel"] = (mapa[~mapa["cuartel_id"].isin(vig["cuartel_id"])]
                                 [["cuartel_id", "variedad", "area_ha"]].sort_values("cuartel_id"))
    m = vig.merge(mapa[["cuartel_id", "variedad"]].rename(columns={"variedad": "variedad_kml"}),
                  on="cuartel_id")
    dif = m[(m["variedad_kml"].fillna("") != m["variedad_cod"])]
    rep["Variedad distinta"] = dif[["cuartel_id", "variedad", "variedad_kml"]].rename(
        columns={"variedad": "variedad_excel"}).sort_values("cuartel_id")
    ha_kml = mapa.groupby(mapa["cuartel_id"].str.rsplit(".", n=1).str[0])["area_ha"].sum()
    ha_xl = vig.groupby("lote_id")["ha_lote"].first()
    comp = pd.DataFrame({"ha_excel": ha_xl, "ha_poligonos": ha_kml}).dropna()
    comp["diferencia_%"] = ((comp["ha_poligonos"] - comp["ha_excel"]) / comp["ha_excel"] * 100).round(1)
    rep["Hectáreas por lote"] = comp[comp["diferencia_%"].abs() > 5].reset_index(names="lote_id")
    if valores_evaluaciones is not None and len(valores_evaluaciones):
        ev = valores_evaluaciones.copy()
        ev["en_maestro"] = ev["valor"].str.upper().isin(vig["cuartel_id"])
        rep["Evaluaciones sin maestro"] = ev[~ev["en_maestro"]].drop(columns="en_maestro")
    return rep
