"""Cruces entre tablas. Cada funcion devuelve un DataFrame listo para explorar o graficar."""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from . import config as C
from .series import select_series


def ei_gap(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Beneficiarios de EI regular por cada desempleado (indicador aproximado, no tasa de cobertura)."""
    unemployed = select_series(con, C.LFS_PROVINCE, C.F_LFS_UNEMPLOYED).rename(columns={"value": "unemployed"})
    ei = select_series(con, C.EI_REGULAR, C.F_EI_REGULAR).rename(columns={"value": "ei_regular"})
    df = unemployed.merge(ei, on=["period", "geo"], how="inner")
    df["ei_per_unemployed"] = df["ei_regular"] / df["unemployed"]
    return df.sort_values(["geo", "period"]).reset_index(drop=True)


def immigrant_gap(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Brecha de tasa de desempleo (puntos porcentuales) de cada grupo migratorio vs nacidos en Canada."""
    r = select_series(con, C.LFS_IMMIGRANT, C.F_IMMIGRANT_RATE, keep=(C.K_IMMIGRANT_STATUS,))
    status_col = [c for c in r.columns if c not in ("period", "geo", "value")][0]
    wide = r.pivot_table(index=["period", "geo"], columns=status_col, values="value")
    base = [c for c in wide.columns if "born in canada" in c.lower()]
    if len(base) != 1:
        raise RuntimeError(f"No pude identificar 'nacidos en Canada' entre {list(wide.columns)}")
    gaps = wide.drop(columns=base).sub(wide[base[0]], axis=0)
    long = gaps.reset_index().melt(id_vars=["period", "geo"], var_name="immigrant_status", value_name="gap_pp")
    rate = wide[base[0]].rename("born_in_canada_rate").reset_index()
    return long.dropna().merge(rate, on=["period", "geo"]).sort_values(["geo", "immigrant_status", "period"]).reset_index(drop=True)


def degree_ratio(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Desempleados por vacante segun nivel educativo exigido."""
    r = select_series(con, C.JVWS_RATIO, C.F_JVWS_RATIO, keep=(C.K_EDUCATION,))
    edu_col = [c for c in r.columns if c not in ("period", "geo", "value")][0]
    return r.rename(columns={edu_col: "education_required", "value": "unemployed_per_vacancy"})


# ---------------------------------------------------------------- exploracion


def province_panel(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Panel provincia x mes: desempleo, brecha de EI y brecha de inmigrantes muy recientes."""
    panel = ei_gap(con)
    rate = select_series(con, C.LFS_PROVINCE, C.F_LFS_RATE).rename(columns={"value": "unemployment_rate"})
    panel = panel.merge(rate, on=["period", "geo"], how="left")
    try:
        imm = immigrant_gap(con)
        recent = imm[imm["immigrant_status"].str.contains("very recent|5 years or less", case=False, regex=True)]
        panel = panel.merge(recent[["period", "geo", "gap_pp"]].rename(columns={"gap_pp": "recent_immigrant_gap_pp"}), on=["period", "geo"], how="left")
    except Exception as exc:  # el cruce sigue sin esta pieza
        print(f"[aviso] sin brecha de inmigrantes en el panel: {exc}")
    return panel


def lag_correlation(panel: pd.DataFrame, geo: str = "Canada", a: str = "unemployment_rate", b: str = "ei_per_unemployed", max_lag: int = 6) -> pd.DataFrame:
    """Correlacion de primeras diferencias entre a_t y b_(t+k). k>0: b reacciona despues que a."""
    d = panel[panel["geo"] == geo].sort_values("period").set_index("period")[[a, b]].diff().dropna()
    rows = []
    for k in range(-max_lag, max_lag + 1):
        pair = pd.concat([d[a], d[b].shift(-k)], axis=1).dropna()
        rows.append({"lag_months": k, "corr": pair.corr().iloc[0, 1] if len(pair) > 5 else np.nan, "n": len(pair)})
    return pd.DataFrame(rows)


def cross_section(panel: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    """Promedio de los ultimos N meses por provincia, ordenado por brecha de EI."""
    prov = panel[panel["geo"].isin(C.PROVINCES)]
    recent = prov[prov["period"] >= prov["period"].max() - pd.DateOffset(months=months - 1)]
    cols = [c for c in ["unemployment_rate", "ei_per_unemployed", "recent_immigrant_gap_pp"] if c in recent]
    return recent.groupby("geo")[cols].mean().sort_values("ei_per_unemployed")


def outliers(panel: pd.DataFrame, col: str = "ei_per_unemployed", min_obs: int = 24) -> pd.DataFrame:
    """Que tan raro es el ultimo valor de cada geografia frente a su propia historia (z-score)."""
    rows = []
    for geo, g in panel.sort_values("period").groupby("geo"):
        s = g[col].dropna()
        if len(s) >= min_obs and s.std() > 0:
            rows.append({"geo": geo, "period": g["period"].iloc[-1], col: s.iloc[-1], "z_vs_history": (s.iloc[-1] - s.mean()) / s.std()})
    return pd.DataFrame(rows).sort_values("z_vs_history", ascending=False).reset_index(drop=True)
