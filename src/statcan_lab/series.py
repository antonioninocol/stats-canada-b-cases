"""Seleccion de una serie limpia (una fila por periodo y geografia) desde una tabla de StatCan.

Los filtros son regex sobre nombre de columna y valor. Si el esquema real difiere de lo
esperado, se falla con un mensaje que lista los valores disponibles, en vez de sumar
categorias por accidente.
"""
from __future__ import annotations

import re

import duckdb
import pandas as pd

from .db import dim_columns, table_name


class SchemaError(RuntimeError):
    pass


def _find_col(dims: list[str], pattern: str, pid: str, optional: bool) -> str | None:
    hits = [c for c in dims if re.search(pattern, c, re.I)]
    if len(hits) == 1:
        return hits[0]
    if not hits and optional:
        return None
    problem = "ninguna columna coincide" if not hits else f"varias columnas coinciden {hits}"
    raise SchemaError(f"{pid}: {problem} con /{pattern}/. Dimensiones disponibles: {dims}. Corre 'describe {pid}'.")


def _distinct(con: duckdb.DuckDBPyConnection, t: str, col: str, where: str = "TRUE", params: list | None = None, n: int = 12) -> str:
    vals = [r[0] for r in con.execute(f'SELECT DISTINCT "{col}" FROM {t} WHERE {where} ORDER BY 1', params or []).fetchall()]
    return " | ".join(vals[:n]) + (f" (+{len(vals) - n} mas)" if len(vals) > n else "")


def select_series(
    con: duckdb.DuckDBPyConnection,
    pid: str,
    filters: dict[str, str],
    keep: tuple[str, ...] = (),
    geo: str | None = None,
) -> pd.DataFrame:
    """Devuelve period, geo, value (+ columnas de `keep`).

    filters: {regex_columna: regex_valor}. Prefijo '?' en la clave = ignorar si la columna no existe.
    keep: regex de columnas a conservar como dimension (por ejemplo estatus migratorio).
    """
    t = table_name(pid)
    dims = dim_columns(con, t)
    where, params, used = ["value_num IS NOT NULL"], [], []

    for kpat, vpat in filters.items():
        col = _find_col(dims, kpat.lstrip("?"), pid, optional=kpat.startswith("?"))
        if col is None:
            continue
        used.append(col)
        where.append(f"regexp_matches(\"{col}\", ?, 'i')")
        params.append(vpat)
    if geo:
        where.append("regexp_matches(GEO, ?, 'i')")
        params.append(geo)

    keep_cols = [_find_col(dims, k, pid, optional=False) for k in keep]
    select = ", ".join(["period", "GEO AS geo", "value_num AS value"] + [f'"{c}"' for c in keep_cols])
    where_sql = " AND ".join(where)
    df = con.execute(f"SELECT {select} FROM {t} WHERE {where_sql}", params).df()

    if df.empty:
        detail = "; ".join(f"{c}: {_distinct(con, t, c)}" for c in used)
        raise SchemaError(f"{pid}: los filtros no dejaron filas. Valores disponibles -> {detail}")

    key = ["period", "geo"] + keep_cols
    if df.duplicated(key).any():
        free = [c for c in dims if c not in used and c not in keep_cols]
        varying = []
        for c in free:
            vals = _distinct(con, t, c, where_sql, params)
            if "|" in vals:
                varying.append(f"{c}: {vals}")
        raise SchemaError(f"{pid}: hay varias filas por periodo y geografia. Agrega filtros para -> " + "; ".join(varying))

    return df.sort_values(key).reset_index(drop=True)
