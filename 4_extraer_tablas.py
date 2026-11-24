"""
PASO 4 - Extraer VARIAS tablas de Athena segun el panel de control config_tablas.xlsx

Uso (Anaconda Prompt, dentro de pedregal_datos):
    python 4_extraer_tablas.py              -> solo las tablas con activa = SI
    python 4_extraer_tablas.py --completo   -> fuerza carga completa (ignora "dias a recargar")

Panel de control (config_tablas.xlsx), una fila por tabla:
    activa        SI / NO
    seccion       en que parte de la plataforma se usa (Limpieza, Categorizacion, ...)
    tabla_athena  nombre completo de la tabla en Athena
    desde         fecha desde la que se trae (AAAA-MM-DD)
    col_fecha     columna de fecha (vacio = la detecta sola)
    dias_recarga  despues de la primera carga, cuantos dias recientes se vuelven a traer

Escribe resumen_tablas.txt con columnas, filas y fechas de cada tabla.
"""
import argparse
import os
import re
import sys
import traceback

DSN = "pedregal"
DB = os.path.join("datos", "pedregal.duckdb")
CONFIG = "config_tablas.xlsx"
LOG = "resumen_tablas.txt"
lineas = []


def log(m=""):
    print(m)
    lineas.append(str(m))


def main():
    import duckdb
    import pandas as pd
    from extractor import expr_fecha, extraer, nombre_corto

    ap = argparse.ArgumentParser()
    ap.add_argument("--completo", action="store_true")
    a = ap.parse_args()

    cfg = pd.read_excel(CONFIG, dtype=str).fillna("")
    cfg = cfg[cfg["activa"].str.upper().str.strip().isin(["SI", "SÍ", "S", "X", "1"])]
    if cfg.empty:
        log("No hay tablas con activa = SI en config_tablas.xlsx")
        return
    log(f"Tablas activas: {len(cfg)}")

    from athena_nube import ConexionNube, hay_claves
    if hay_claves():                      # en la nube (GitHub): claves de Secrets, sin ODBC
        log("Conexión: Athena directo (claves de la nube)")
        cn = ConexionNube()
    else:                                 # en la laptop: el ODBC "pedregal" de siempre
        import pyodbc
        cn = pyodbc.connect(f"DSN={DSN}", autocommit=True, timeout=60)
    cur = cn.cursor()
    en_athena = {r.table_name: r.table_schem for r in cur.tables()}
    log(f"Tablas visibles en Athena: {len(en_athena)}")
    os.makedirs("datos", exist_ok=True)
    db = duckdb.connect(DB)

    for _, fila in cfg.iterrows():
        tabla = fila["tabla_athena"].strip()
        log(f"\n=== [{fila['seccion']}] {tabla}")
        if tabla not in en_athena:
            # se acepta el nombre incompleto (como se ve cortado en Athena) si coincide con una sola tabla
            cand = [k for k in en_athena if k.startswith(tabla)]
            if not cand:
                # la lista del driver a veces no trae las tablas nuevas: se pregunta directo a Athena
                esquema = max(set(en_athena.values()), key=list(en_athena.values()).count)
                try:
                    cur.execute(f"SHOW TABLES IN `{esquema}` '{tabla}*'")
                    cand = [r[0] for r in cur.fetchall()]
                    for k in cand:
                        en_athena[k] = esquema
                except Exception as e:
                    log(f"  (SHOW TABLES falló: {e})")
            if len(cand) != 1:
                log(f"  !! {'No existe' if not cand else 'Coincide con varias'} en Athena (revisa el nombre)")
                for k in cand:
                    log("     " + k)
                continue
            tabla = cand[0]
            log(f"  -> {tabla}")
        corto = nombre_corto(tabla)
        viejo = re.sub(r"[^a-z0-9]+", "_", tabla.lower()).strip("_")   # nombre largo de versiones anteriores
        if viejo != corto:
            db.execute(f'DROP TABLE IF EXISTS "{viejo}"')
            try:
                db.execute("DELETE FROM _cargas WHERE tabla = ?", [viejo])
            except duckdb.Error:
                pass
        try:
            dias = None if a.completo or not fila["dias_recarga"].strip() else int(float(fila["dias_recarga"]))
            r = extraer(cur, db, en_athena[tabla], tabla, corto, fila["desde"].strip() or "2026-01-01",
                        fila["col_fecha"].strip() or None, dias)
        except Exception as e:  # una tabla con problemas no detiene a las demas
            log(f"  !! ERROR: {e}")
            continue
        if not r["ok"]:
            log(f"  !! {r['error']}. Columnas: {', '.join(n for n, _ in r['columnas'])}")
            continue
        log(f"  OK {r['modo']}: {r['traidas']:,} filas traídas desde {r['desde']} en {r['segundos']:.1f} s"
            f" | total en base: {r['filas']:,} | fecha: {r['col_fecha']}")
        log(f"  Nombre en la base: {corto}")
        log("  Columnas: " + ", ".join(f"{n}[{t}]" for n, t in r["columnas"]))
        fcol = r["col_fecha"].split(" [")[0]
        ftipo = r["col_fecha"].split("[")[1].rstrip("]")
        fx = expr_fecha(fcol, ftipo, "duckdb")
        rango = db.execute(f'SELECT min({fx}), max({fx}) FROM "{corto}"').fetchone()
        log(f"  Fechas: {rango[0]} -> {rango[1]}")
        pistas = [n for n, _ in r["columnas"] if any(k in n.lower() for k in ("lote", "cuartel", "fundo", "plot"))]
        for p in pistas[:3]:
            vals = db.execute(f'SELECT CAST("{p}" AS VARCHAR), count(*) n FROM "{corto}" '
                              f'GROUP BY 1 ORDER BY n DESC LIMIT 8').fetchall()
            log(f"  {p}: " + ", ".join(f"{v} ({n})" for v, n in vals))
        muestra = db.execute(f'SELECT * FROM "{corto}" LIMIT 3').df()
        log("  Muestra:\n" + muestra.to_string(max_colwidth=25))
    db.close()
    cn.close()


try:
    main()
except Exception:
    log("\n!! ERROR:\n" + traceback.format_exc())
finally:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"\n>> Resumen guardado en {LOG}")
    sys.exit(0)
