"""
PASO 3 - Cargar la base maestra (Excel descargado del Google Sheet) a la base local.

Uso (Anaconda Prompt, dentro de pedregal_datos):
    python 3_cargar_maestro.py

Busca el .xlsx dentro de la carpeta "Maestro" y:
  - guarda en datos/pedregal.duckdb:
        maestro_historico  -> todas las campanas (una fila por cuartel y campana)
        maestro_cuartel    -> la ultima campana de cada cuartel (lo que usa la ficha)
  - genera validacion_maestro.xlsx con lo que no cuadra entre Excel, mapa y evaluaciones.

Cada vez que actualices el Sheet: descargalo de nuevo a la carpeta Maestro y vuelve a correr esto.
"""
import json
import os
import sys
import traceback

import pandas as pd

import maestro as mx

DB = os.path.join("datos", "pedregal.duckdb")
GEO = "cuarteles_pedregal.geojson"
SALIDA = "validacion_maestro.xlsx"


def codigos_evaluaciones(db):
    """Valores de lote/cuartel usados en cada evaluacion cargada (para ver si existen en el maestro)."""
    filas = []
    tablas = [r[0] for r in db.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE left(table_name, 1) <> '_' AND table_name NOT LIKE 'maestro%'").fetchall()]
    for t in tablas:
        cols = [r[0] for r in db.execute(f'DESCRIBE "{t}"').fetchall()]
        col = next((c for c in cols if "cuartel" in c.lower()), None) or \
            next((c for c in cols if "lote" in c.lower()), None)
        if not col:
            continue
        for v, n in db.execute(f'SELECT CAST("{col}" AS VARCHAR), count(*) FROM "{t}" GROUP BY 1').fetchall():
            if v is not None:
                filas.append({"tabla": t, "columna": col, "valor": v, "registros": n})
    return pd.DataFrame(filas)


def main():
    import duckdb

    ruta = mx.buscar_excel(".")
    if not ruta:
        print("No encontré ningún .xlsx dentro de la carpeta 'Maestro'.")
        return 1
    print(f"Leyendo {ruta} ...")
    hoja, historico, actual, duplicados = mx.leer(ruta)
    vigente = int(historico["anio"].max())
    print(f"Hoja '{hoja}': {len(historico):,} filas, {historico['cuartel_id'].nunique()} cuarteles, "
          f"campañas {int(historico['anio'].min())}-{vigente}")
    print(f"Cuarteles en la campaña {vigente}: {(historico['anio'] == vigente).sum()}")

    os.makedirs("datos", exist_ok=True)
    db = duckdb.connect(DB)
    db.register("h", historico)
    db.register("a", actual)
    db.execute("CREATE OR REPLACE TABLE maestro_historico AS SELECT * FROM h")
    db.execute("CREATE OR REPLACE TABLE maestro_cuartel AS SELECT * FROM a")
    db.unregister("h")
    db.unregister("a")
    db.execute("""CREATE TABLE IF NOT EXISTS _cargas(tabla VARCHAR, tabla_athena VARCHAR, col_fecha VARCHAR,
                  desde VARCHAR, filas BIGINT, segundos DOUBLE, cargado_en TIMESTAMP)""")
    db.execute("DELETE FROM _cargas WHERE tabla LIKE 'maestro%'")
    ev = codigos_evaluaciones(db)
    db.close()
    print(f"Guardado en {DB}: maestro_historico y maestro_cuartel")

    with open(GEO, encoding="utf-8") as f:
        features = json.load(f)["features"]
    rep = mx.validar(actual, features, ev)
    if len(duplicados):
        rep["Filas duplicadas"] = duplicados[["cuartel_id", "anio", "variedad", "ha_lote"]]

    with pd.ExcelWriter(SALIDA) as xw:
        resumen = pd.DataFrame({"Revisión": list(rep), "Casos": [len(v) for v in rep.values()]})
        resumen.to_excel(xw, sheet_name="Resumen", index=False)
        for nombre, df in rep.items():
            df.to_excel(xw, sheet_name=nombre[:31], index=False)
    print(f"\nRevisión (detalle en {SALIDA}):")
    for nombre, df in rep.items():
        print(f"  {nombre:28s} {len(df):>4}")
    return 0


try:
    sys.exit(main())
except SystemExit:
    raise
except Exception:
    print("\n!! ERROR:\n" + traceback.format_exc())
    sys.exit(1)
