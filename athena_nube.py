"""Conexion a Athena SIN el ODBC, para correr en la nube (GitHub Actions / Streamlit Cloud).

Lee las claves de variables de entorno (en GitHub van en Settings > Secrets, nunca en el codigo):
    ATHENA_KEY      clave de acceso   (en el ODBC "pedregal" es el campo User / Access key)
    ATHENA_SECRET   clave secreta     (en el ODBC es el campo Password / Secret key)
    ATHENA_REGION   region            (ej. us-east-1)
    ATHENA_S3       carpeta de resultados de consultas (ej. s3://.../)   -> opcional si el workgroup ya la tiene
    ATHENA_WORKGROUP workgroup        (vacio = primary)

Devuelve un cursor que se comporta como el de pyodbc, asi extractor.py funciona igual."""
import datetime as dt
import decimal
import os

TIPO_PY = {"varchar": str, "char": str, "string": str, "json": str, "bigint": int, "integer": int, "int": int,
           "smallint": int, "tinyint": int, "double": float, "float": float, "real": float, "decimal": decimal.Decimal,
           "timestamp": dt.datetime, "date": dt.date, "boolean": bool}


class _Fila:
    def __init__(self, **k):
        self.__dict__.update(k)


class CursorNube:
    def __init__(self, cur):
        self._c = cur

    def execute(self, sql):
        self._c.execute(sql)
        return self

    @property
    def description(self):
        d = self._c.description or []
        return [(x[0], TIPO_PY.get(str(x[1]).lower().split("(")[0].strip(), str)) + tuple(x[2:]) for x in d]

    def fetchmany(self, n):
        return self._c.fetchmany(n)

    def fetchall(self):
        return self._c.fetchall()

    def tables(self):
        self._c.execute("SELECT table_schema, table_name FROM information_schema.tables "
                        "WHERE table_schema <> 'information_schema'")
        return [_Fila(table_schem=s, table_name=t) for s, t in self._c.fetchall()]

    def columns(self, table, schema):
        self._c.execute("SELECT column_name, data_type FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}' AND table_name = '{table}' ORDER BY ordinal_position")
        return [_Fila(column_name=c, type_name=t) for c, t in self._c.fetchall()]


class ConexionNube:
    def __init__(self):
        from pyathena import connect
        e = os.environ
        args = dict(aws_access_key_id=e["ATHENA_KEY"], aws_secret_access_key=e["ATHENA_SECRET"],
                    region_name=e.get("ATHENA_REGION") or "us-east-1",
                    work_group=e.get("ATHENA_WORKGROUP") or "primary")
        if e.get("ATHENA_S3"):
            args["s3_staging_dir"] = e["ATHENA_S3"]
        self._cn = connect(**args)

    def cursor(self):
        return CursorNube(self._cn.cursor())

    def close(self):
        self._cn.close()


def hay_claves():
    return bool(os.environ.get("ATHENA_KEY") and os.environ.get("ATHENA_SECRET"))
