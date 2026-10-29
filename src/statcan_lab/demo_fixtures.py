"""Genera zips sinteticos con el mismo formato que las descargas completas de StatCan.

Siembra relaciones conocidas para poder verificar los cruces:
  - EI sigue al desempleo con 2 meses de rezago (en cada geografia)
  - inmigrantes muy recientes tienen +4.0 puntos de desempleo vs nacidos en Canada
  - ratio desempleados/vacante: ~4.9 para titulo universitario, ~1.7 para certificado tecnico
"""
from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import numpy as np

STD_TAIL = ["UOM", "UOM_ID", "SCALAR_FACTOR", "SCALAR_ID", "VECTOR", "COORDINATE", "VALUE", "STATUS", "SYMBOL", "TERMINATED", "DECIMALS"]
PROVS = ["Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick", "Quebec",
         "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]
MONTHS = [f"{y}-{m:02d}" for y in (2023, 2024, 2025) for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]


def _write_zip(out_dir: Path, pid: str, dims: list[str], rows: list[tuple]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(["REF_DATE", "GEO", "DGUID", *dims, *STD_TAIL])
    for ref, geo, dvals, uom, scalar, value in rows:
        w.writerow([ref, geo, "x", *dvals, uom, "1", scalar, "0", "v1", "1.1", value, "", "", "", "1"])
    with zipfile.ZipFile(out_dir / f"{pid}-eng.zip", "w") as zf:
        zf.writestr(f"{pid}.csv", b"\xef\xbb\xbf" + buf.getvalue().encode())  # StatCan incluye BOM


def build(out_dir: Path, seed: int = 7) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    geos = ["Canada"] + PROVS
    rate = {}
    for g in geos:
        base = rng.uniform(5, 9)
        rate[g] = np.clip(base + np.cumsum(rng.normal(0, 0.15, len(MONTHS))), 3, 14)
    lf = {g: rng.uniform(400, 3000) if g != "Canada" else 21000 for g in geos}  # miles

    # 14-10-0287-03: sin dimension de sexo/edad, con filas "ruido" que el filtro debe descartar
    rows = []
    for g in geos:
        for i, ref in enumerate(MONTHS):
            unemployed_k = rate[g][i] / 100 * lf[g]
            rows += [
                (ref, g, ["Unemployment", "Estimate", "Seasonally adjusted"], "Persons", "thousands", f"{unemployed_k:.1f}"),
                (ref, g, ["Unemployment rate", "Estimate", "Seasonally adjusted"], "Percent", "units", f"{rate[g][i]:.2f}"),
                (ref, g, ["Unemployment", "Estimate", "Trend-cycle"], "Persons", "thousands", f"{unemployed_k * 1.01:.1f}"),
                (ref, g, ["Unemployment", "Standard error", "Seasonally adjusted"], "Persons", "thousands", "9.9"),
            ]
    _write_zip(out_dir, "14100287", ["Labour force characteristics", "Statistics", "Data type"], rows)

    # 14-10-0011-01: EI_t = cobertura_g * desempleados_(t-2), en personas
    rows = []
    for g in geos + ["Yukon"]:
        cover = rng.uniform(0.25, 0.5)
        src = rate[g] if g in rate else rate["Canada"]
        size = lf[g] if g in lf else 20
        for i, ref in enumerate(MONTHS):
            if i < 2:
                continue
            ei = cover * src[i - 2] / 100 * size * 1000
            rows += [
                (ref, g, ["Both sexes", "15 years and over", "Total, declared earnings"], "Persons", "units", f"{ei:.0f}"),
                (ref, g, ["Both sexes", "15 years and over", "With declared earnings"], "Persons", "units", f"{ei * 0.4:.0f}"),
                (ref, g, ["Males", "15 years and over", "Total, declared earnings"], "Persons", "units", f"{ei * 0.55:.0f}"),
            ]
    _write_zip(out_dir, "14100011", ["Sex", "Age group", "Declared earnings"], rows)

    # 14-10-0471-01: estatus migratorio, incluye una CMA
    gaps = {"Total, immigrant status": 0.8, "Born in Canada": 0.0, "Landed immigrants": 1.2, "Very recent immigrants, 5 years or less": 4.0}
    rows = []
    for g in geos + ["Toronto, Ontario"]:
        src = rate[g] if g in rate else rate["Ontario"]
        for i, ref in enumerate(MONTHS):
            for status, gap in gaps.items():
                for gender, bump in (("Total, all genders", 0.0), ("Men+", 0.3)):
                    rows.append((ref, g, ["Unemployment rate", status, gender, "15 years and over", "Estimate"], "Percent", "units", f"{src[i] + gap + bump:.2f}"))
    _write_zip(out_dir, "14100471", ["Labour force characteristics", "Immigrant status", "Gender", "Age group", "Statistics"], rows)

    # 14-10-0443-01: trimestral
    rows = []
    for ref in [m for m in MONTHS if m[-2:] in ("01", "04", "07", "10")]:
        rows += [
            (ref, "Canada", ["Bachelor's degree or higher", "Unemployment-to-job vacancy ratio"], "Ratio", "units", f"{4.9 + rng.normal(0, .05):.2f}"),
            (ref, "Canada", ["Trade certificate or diploma", "Unemployment-to-job vacancy ratio"], "Ratio", "units", f"{1.7 + rng.normal(0, .05):.2f}"),
            (ref, "Canada", ["Bachelor's degree or higher", "Job vacancies"], "Number", "units", "15000"),
        ]
    _write_zip(out_dir, "14100443", ["Education level required", "Statistics"], rows)


if __name__ == "__main__":
    import sys

    build(Path(sys.argv[1]))
