"""Carga de los CSV de StatCan a DuckDB, con periodo y valor numerico ya normalizados."""
from __future__ import annotations

from pathlib import Path

import duckdb

from .client import pid8

# Columnas fijas del formato de descarga completa; el resto son dimensiones de la tabla.
STD_COLS = {
    "REF_DATE", "GEO", "DGUID", "UOM", "UOM_ID", "SCALAR_FACTOR", "SCALAR_ID",
    "VECTOR", "COORDINATE", "VALUE", "STATUS", "SYMBOL", "TERMINATED", "DECIMALS",
    "period", "value_num",
}

SCALE_SQL = """CASE lower(SCALAR_FACTOR)
    WHEN 'units' THEN 1 WHEN 'tens' THEN 10 WHEN 'hundreds' THEN 100
    WHEN 'thousands' THEN 1000 WHEN 'ten thousands' THEN 10000
    WHEN 'hundred thousands' THEN 100000 WHEN 'millions' THEN 1000000
    ELSE 1 END"""


def connect(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def table_name(pid: str) -> str:
    return f"t_{pid8(pid)}"


def load_table(con: duckdb.DuckDBPyConnection, pid: str, csv_path: Path) -> int:
    t = table_name(pid)
    csv = str(csv_path).replace("'", "''")
    con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute(
        f"""
        CREATE TABLE {t} AS
        SELECT *,
          COALESCE(TRY_STRPTIME(REF_DATE, '%Y-%m'), TRY_STRPTIME(REF_DATE, '%Y-%m-%d'),
                   TRY_STRPTIME(REF_DATE, '%Y'))::DATE AS period,
          TRY_CAST(VALUE AS DOUBLE) * ({SCALE_SQL}) AS value_num
        FROM read_csv('{csv}', header=true, all_varchar=true, sample_size=-1)
        """
    )
    return con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]


def dim_columns(con: duckdb.DuckDBPyConnection, t: str) -> list[str]:
    cols = [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
    return [c for c in cols if c not in STD_COLS]


def describe_table(con: duckdb.DuckDBPyConnection, pid: str, top: int = 25) -> str:
    t = table_name(pid)
    n, lo, hi = con.execute(f"SELECT count(*), min(period), max(period) FROM {t}").fetchone()
    lines = [f"{pid}: {n:,} filas, periodos {lo} a {hi}", f"  GEO: {con.execute(f'SELECT count(DISTINCT GEO) FROM {t}').fetchone()[0]} valores"]
    for c in dim_columns(con, t):
        vals = [r[0] for r in con.execute(f'SELECT DISTINCT "{c}" FROM {t} ORDER BY 1').fetchall()]
        extra = f" (+{len(vals) - top} mas)" if len(vals) > top else ""
        lines.append(f"  {c} ({len(vals)}): " + " | ".join(vals[:top]) + extra)
    uom = con.execute(f"SELECT DISTINCT UOM, SCALAR_FACTOR FROM {t}").fetchall()
    lines.append(f"  unidades: {uom}")
    return "\n".join(lines)
