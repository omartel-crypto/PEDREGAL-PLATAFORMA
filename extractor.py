"""Funciones del extractor Athena -> base local (DuckDB). Las usan 2_extraer.py y 4_extraer_tablas.py."""
import datetime as dt
import decimal
import re
import time

TIPOS = {str: "VARCHAR", int: "BIGINT", float: "DOUBLE", decimal.Decimal: "DOUBLE",
         dt.datetime: "TIMESTAMP", dt.date: "DATE", bool: "BOOLEAN"}


def nombre_corto(tabla):
    """table_ica-pedregal_uva_cosecha-vid_04d90865-... -> cosecha_vid"""
    m = re.search(r"uva_(?:pk-|bd_)?(.+?)_[0-9a-f]{8}(?:-|$)", tabla)
    base = m.group(1) if m else tabla
    return re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")


def elegir_fecha(cols, forzada=None):
    if forzada:
        for n, t in cols:
            if n.lower() == forzada.lower():
                return n, t
        raise ValueError(f"No existe la columna de fecha '{forzada}'.")
    tipo_fecha = [(n, t) for n, t in cols if any(k in t.lower() for k in ("date", "timestamp"))]
    con_nombre = [(n, t) for n, t in cols if "fecha" in n.lower() or "date" in n.lower()]
    for grupo in ([c for c in tipo_fecha if "fecha" in c[0].lower()], tipo_fecha,
                  [c for c in con_nombre if "meta" in c[0].lower()], con_nombre):
        if grupo:
            return grupo[0]
    return None, None


def expr_fecha(col, tipo, motor="athena"):
    """Expresion SQL que convierte la columna a DATE, para Athena o para DuckDB."""
    q = f'"{col}"'
    t = (tipo or "").lower()
    if "timestamp" in t:
        return f"CAST({q} AS date)"
    if "date" in t:
        return q
    if motor == "duckdb":
        return f"TRY_CAST(substr(CAST({q} AS VARCHAR), 1, 10) AS DATE)"
    return f"try(CAST(substr(CAST({q} AS varchar), 1, 10) AS date))"


def _limpiar(v):
    return float(v) if isinstance(v, decimal.Decimal) else v


def extraer(cur, db, base, tabla, corto, desde, col_fecha=None, dias_recarga=None, log=print):
    """Copia la tabla de Athena a DuckDB.
    - Si la tabla no existe en la base (o dias_recarga es None): carga completa desde `desde`.
    - Si existe: borra y vuelve a traer solo los ultimos `dias_recarga` dias (incremental).
    Devuelve un dict con el resumen."""
    import pandas as pd

    cols = [(c.column_name, c.type_name) for c in cur.columns(table=tabla, schema=base)]
    if not cols:   # tabla nueva que el driver aun no describe: se leen las columnas de una consulta
        cur.execute(f'SELECT * FROM "{base}"."{tabla}" LIMIT 1')
        nombres_t = {str: "string", float: "double", int: "bigint", decimal.Decimal: "double",
                     dt.datetime: "timestamp", dt.date: "date", bool: "boolean"}
        cols = [(d[0], nombres_t.get(d[1], "string")) for d in cur.description]
        cur.fetchall()
    fcol, ftipo = elegir_fecha(cols, col_fecha)
    if not fcol:
        return {"tabla": corto, "ok": False, "error": "sin columna de fecha", "columnas": cols}

    existe = db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
                        [corto]).fetchone()[0] > 0
    incremental = existe and dias_recarga is not None
    corte = desde
    if incremental:
        corte = max(dt.date.fromisoformat(desde), dt.date.today() - dt.timedelta(days=int(dias_recarga))).isoformat()

    f_athena = expr_fecha(fcol, ftipo)
    sql = f'SELECT * FROM "{base}"."{tabla}" WHERE {f_athena} >= DATE \'{corte}\''
    t0 = time.time()
    cur.execute(sql)
    nombres = [d[0] for d in cur.description]
    ddl = ", ".join(f'"{n}" {TIPOS.get(d[1], "VARCHAR")}' for n, d in zip(nombres, cur.description))

    if not incremental:
        db.execute(f'CREATE OR REPLACE TABLE "{corto}" ({ddl})')
    else:
        # si el proveedor agrego columnas nuevas, se agregan a la tabla local (las filas viejas quedan vacias)
        actuales = {r[0] for r in db.execute(f'DESCRIBE "{corto}"').fetchall()}
        for n, d in zip(nombres, cur.description):
            if n not in actuales:
                db.execute(f'ALTER TABLE "{corto}" ADD COLUMN "{n}" {TIPOS.get(d[1], "VARCHAR")}')
                log(f"  + columna nueva en Athena: {n}")
        f_duck = expr_fecha(fcol, ftipo, "duckdb")
        db.execute(f'DELETE FROM "{corto}" WHERE {f_duck} >= DATE \'{corte}\'')

    total = 0
    while True:
        filas = cur.fetchmany(50000)
        if not filas:
            break
        df = pd.DataFrame([[_limpiar(v) for v in f] for f in filas], columns=nombres)
        db.register("lote_df", df)
        db.execute(f'INSERT INTO "{corto}" BY NAME SELECT * FROM lote_df')   # por nombre: no importa el orden
        db.unregister("lote_df")
        total += len(df)
    seg = time.time() - t0
    filas_tabla = db.execute(f'SELECT count(*) FROM "{corto}"').fetchone()[0]

    db.execute("""CREATE TABLE IF NOT EXISTS _cargas(tabla VARCHAR, tabla_athena VARCHAR, col_fecha VARCHAR,
                  desde VARCHAR, filas BIGINT, segundos DOUBLE, cargado_en TIMESTAMP)""")
    db.execute("DELETE FROM _cargas WHERE tabla = ?", [corto])
    db.execute("INSERT INTO _cargas VALUES (?,?,?,?,?,?,now())", [corto, tabla, fcol, desde, filas_tabla, seg])
    return {"tabla": corto, "ok": True, "modo": "incremental" if incremental else "completa",
            "desde": corte, "traidas": total, "filas": filas_tabla, "segundos": seg,
            "col_fecha": f"{fcol} [{ftipo}]", "columnas": cols}
