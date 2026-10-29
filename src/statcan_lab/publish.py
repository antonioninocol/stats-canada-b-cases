"""Genera los archivos que lee la app: CSV de resultados + meta.json con frescura y errores."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from . import analyses as A


def publish(con: duckdb.DuckDBPyConnection, out_dir: Path, synthetic: bool = False, table_meta: list[dict] | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    errors: dict[str, str] = {}

    def write(df: pd.DataFrame, name: str) -> None:
        df.to_csv(out_dir / f"{name}.csv", index=False)

    # El panel es el nucleo: si falla, se aborta (no se publica nada a medias).
    panel = A.province_panel(con)
    write(panel, "province_panel")
    write(A.cross_section(panel).reset_index(), "cross_section_12m")
    write(A.lag_correlation(panel), "lag_correlation_canada")
    write(A.outliers(panel), "outliers_ei_gap")

    # Los demas se publican si funcionan; el error queda registrado y visible en la app.
    for name, fn in {"immigrant_gap": A.immigrant_gap, "degree_ratio": A.degree_ratio}.items():
        try:
            write(fn(con), name)
        except Exception as exc:  # noqa: BLE001
            errors[name] = str(exc)[:400]
            (out_dir / f"{name}.csv").unlink(missing_ok=True)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "synthetic": synthetic,
        "latest_period": str(panel["period"].max()),
        "tables": table_meta or [],
        "errors": errors,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta
