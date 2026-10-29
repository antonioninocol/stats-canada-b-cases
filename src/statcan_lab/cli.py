from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from . import analyses as A
from . import config as C
from .client import cube_metadata, download_table
from .db import connect, describe_table, load_table
from .publish import publish

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def _show(df: pd.DataFrame) -> str:
    return df.apply(lambda s: s.round(3) if s.dtype.kind == "f" else s).to_string(index=False)


def _fetch(con, data_dir: Path, local: Path | None, refresh: bool) -> None:
    for pid, label in C.TABLES.items():
        csv = download_table(pid, data_dir / "raw", local, refresh)
        print(f"{pid} {label}: {load_table(con, pid, csv):,} filas")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="statcan_lab")
    ap.add_argument("--data-dir", default="data", help="cache de CSV y base DuckDB")
    ap.add_argument("--out-dir", default="out", help="CSV de resultados")
    ap.add_argument("--local-dir", help="usar zips locales en vez de bajar (pruebas)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freshness", help="titulo, rango de fechas y release de cada tabla (WDS)")
    f = sub.add_parser("fetch", help="bajar tablas y cargarlas a DuckDB")
    f.add_argument("--refresh", action="store_true")
    d = sub.add_parser("describe", help="dimensiones y valores de una tabla cargada")
    d.add_argument("pid")
    r = sub.add_parser("run", help="correr un analisis")
    r.add_argument("analysis", choices=["ei_gap", "immigrant_gap", "degree_ratio", "explore"])
    p = sub.add_parser("publish", help="bajar datos frescos y generar published/ para la app")
    p.add_argument("--published-dir", default="published")
    dm = sub.add_parser("demo", help="generar published_demo/ con datos SINTETICOS para ver la app")
    dm.add_argument("--published-dir", default="published_demo")
    args = ap.parse_args(argv)

    data_dir, out_dir = Path(args.data_dir), Path(args.out_dir)

    if args.cmd == "freshness":
        for m in cube_metadata(list(C.TABLES)):
            print(f"{m['productId']}  {m['start']} a {m['end']}  release {m['release']}\n    {m['title']}")
        return 0

    if args.cmd == "demo":
        from .demo_fixtures import build

        with tempfile.TemporaryDirectory() as tmp:
            fixtures = Path(tmp) / "fixtures"
            build(fixtures)
            con = connect(Path(tmp) / "demo.duckdb")
            _fetch(con, Path(tmp) / "data", fixtures, True)
            meta = publish(con, Path(args.published_dir), synthetic=True)
        print(f"Demo SINTETICO escrito en {args.published_dir} (periodo mas reciente {meta['latest_period']})")
        return 0

    con = connect(data_dir / "statcan.duckdb")

    if args.cmd == "fetch":
        _fetch(con, data_dir, Path(args.local_dir) if args.local_dir else None, args.refresh)
        return 0

    if args.cmd == "publish":
        _fetch(con, data_dir, Path(args.local_dir) if args.local_dir else None, True)
        try:
            table_meta = cube_metadata(list(C.TABLES))
        except Exception as exc:  # noqa: BLE001
            print(f"[aviso] sin metadatos WDS: {exc}")
            table_meta = []
        meta = publish(con, Path(args.published_dir), synthetic=False, table_meta=table_meta)
        print(f"Publicado en {args.published_dir}. Periodo mas reciente: {meta['latest_period']}. Errores: {meta['errors'] or 'ninguno'}")
        return 0

    if args.cmd == "describe":
        print(describe_table(con, args.pid))
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    def save(df: pd.DataFrame, name: str) -> None:
        df.to_csv(out_dir / f"{name}.csv", index=False)
        print(f"\n== {name} ({len(df)} filas) -> {out_dir / (name + '.csv')}")

    if args.analysis == "explore":
        panel = A.province_panel(con)
        save(panel, "province_panel")
        for name, df in {
            "cross_section_12m": A.cross_section(panel).reset_index(),
            "lag_correlation_canada": A.lag_correlation(panel),
            "outliers_ei_gap": A.outliers(panel),
        }.items():
            save(df, name)
            print(_show(df))
    else:
        df = {"ei_gap": A.ei_gap, "immigrant_gap": A.immigrant_gap, "degree_ratio": A.degree_ratio}[args.analysis](con)
        save(df, args.analysis)
        print(_show(df.groupby(df.columns[1]).tail(1)))
    return 0
