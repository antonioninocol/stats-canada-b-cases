"""App de exploracion: mercado laboral canadiense con tablas abiertas de Statistics Canada.

Lee los CSV precalculados en published/ (o published_demo/ con datos sinteticos, claramente marcado).
No llama a StatCan en vivo: por eso carga rapido.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Mercado laboral en Canadá", layout="wide")

ACCENT, MUTED = "#d94f3d", "#9db4d3"
PALETTE = ["#1f6feb", "#e8590c", "#2f9e44", "#9c36b5", "#f59f00", "#0b7285"]


def find_data_dir() -> Path | None:
    for name in ("published", "published_demo"):
        d = ROOT / name
        if (d / "province_panel.csv").exists():
            return d
    return None


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame | None:
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if "period" in df.columns:
        df["period"] = pd.to_datetime(df["period"])
    return df


def show(chart: alt.Chart) -> None:
    """Compatible con versiones nuevas y viejas de Streamlit."""
    try:
        st.altair_chart(chart, width="stretch")
    except Exception:  # noqa: BLE001
        st.altair_chart(chart, use_container_width=True)


def line_chart(df: pd.DataFrame, y: str, color: str, y_title: str, fmt: str = ".2f", height: int = 380) -> None:
    """Linea por serie, eje ajustado al rango real (sin forzar el cero), punto y valor al final de cada serie."""
    series = sorted(df[color].unique())
    scale = alt.Scale(domain=series, range=PALETTE[: len(series)])
    base = alt.Chart(df).encode(
        x=alt.X("period:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=0, tickCount=alt.TimeIntervalStep(interval="month", step=6), grid=False, labelOverlap="greedy")),
        y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=False, nice=True)),
        color=alt.Color(f"{color}:N", title=None, scale=scale, legend=alt.Legend(orient="bottom", labelLimit=500, symbolType="stroke", symbolStrokeWidth=3)),
    )
    lines = base.mark_line(strokeWidth=2.4, interpolate="monotone")
    last = df[df["period"] == df["period"].max()]
    end = alt.Chart(last).encode(
        x="period:T", y=f"{y}:Q", color=alt.Color(f"{color}:N", scale=scale, legend=None),
    )
    dots = end.mark_circle(size=70)
    labels = end.mark_text(align="left", dx=8, fontSize=12, fontWeight="bold").encode(text=alt.Text(f"{y}:Q", format=fmt))
    hover = base.mark_point(size=0, opacity=0).encode(
        tooltip=[
            alt.Tooltip("period:T", title="Período", format="%b %Y"),
            alt.Tooltip(f"{color}:N", title="Serie"),
            alt.Tooltip(f"{y}:Q", title=y_title, format=fmt),
        ]
    )
    chart = (lines + dots + labels + hover).properties(height=height).configure_view(stroke=None)
    show(chart)


def change_vs(df: pd.DataFrame, group: str, value: str, periods_back: int) -> pd.Series:
    """Cambio del ultimo valor frente a N periodos antes, por grupo."""
    out = {}
    for key, g in df.sort_values("period").groupby(group):
        s = g[value].reset_index(drop=True)
        if len(s) > periods_back:
            out[key] = s.iloc[-1] - s.iloc[-1 - periods_back]
    return pd.Series(out, dtype=float)


data_dir = find_data_dir()
st.title("Mercado laboral en Canadá: desempleo, seguro de empleo e inmigración")

if data_dir is None:
    st.error("Todavía no hay datos publicados. Corré `python -m statcan_lab publish` (o `demo` para una vista previa sintética).")
    st.stop()

meta = json.loads((data_dir / "meta.json").read_text()) if (data_dir / "meta.json").exists() else {}
if meta.get("synthetic") or data_dir.name == "published_demo":
    st.error("DATOS SINTÉTICOS DE PRUEBA: estos números son inventados para probar la app y NO provienen de Statistics Canada.")

get = lambda name: load_csv(str(data_dir / f"{name}.csv"))  # noqa: E731
panel = get("province_panel")
latest = panel["period"].max()
st.caption(f"Datos hasta {latest:%Y-%m} · generado {meta.get('generated_at', 'n/d')} · Fuente: Statistics Canada (Licencia abierta)")

tab_ei, tab_imm, tab_edu, tab_lab = st.tabs(["Seguro de empleo (EI)", "Inmigrantes", "Educación y vacantes", "Laboratorio"])

with tab_ei:
    st.subheader("Beneficiarios de EI regular por cada desempleado")
    st.caption("Indicador aproximado, no una tasa de cobertura: beneficiarios (datos administrativos) y desempleados (encuesta LFS) miden cosas distintas.")
    geos = sorted(panel["geo"].unique())
    pick = st.multiselect("Geografías", geos, default=[g for g in ("Canada", "Ontario", "Quebec") if g in geos])
    if pick:
        view = panel[panel["geo"].isin(pick)]
        deltas = change_vs(view, "geo", "ei_per_unemployed", 12)
        last = view[view["period"] == latest].set_index("geo")
        for col, g in zip(st.columns(len(pick)), pick):
            if g in last.index:
                delta = f"{deltas[g]:+.2f} vs hace 12 meses" if g in deltas.index else None
                col.metric(g, f"{last.loc[g, 'ei_per_unemployed']:.2f}", delta, delta_color="off")
        line_chart(view, "ei_per_unemployed", "geo", "EI regular por desempleado")

with tab_imm:
    gap = get("immigrant_gap")
    st.subheader("Brecha de desempleo frente a nacidos en Canadá (puntos porcentuales)")
    if gap is None:
        st.warning(f"Esta sección no está disponible: {meta.get('errors', {}).get('immigrant_gap', 'sin datos')}")
    else:
        gap_geos = sorted(gap["geo"].unique())
        g_geo = st.selectbox("Geografía", gap_geos, index=gap_geos.index("Canada") if "Canada" in gap_geos else 0)
        statuses = sorted(gap["immigrant_status"].unique())
        g_status = st.multiselect("Grupos", statuses, default=statuses)
        sel = gap[(gap["geo"] == g_geo) & (gap["immigrant_status"].isin(g_status))]
        if not sel.empty:
            line_chart(sel, "gap_pp", "immigrant_status", "Brecha (pp)", fmt="+.2f")
        st.markdown("**Último dato por geografía**, para un grupo")
        one = st.selectbox("Grupo a rankear", statuses)
        rank = gap[(gap["immigrant_status"] == one) & (gap["period"] == gap["period"].max())][["geo", "gap_pp"]]
        bar = (
            alt.Chart(rank)
            .mark_bar(color=ACCENT)
            .encode(
                x=alt.X("gap_pp:Q", title="Brecha (pp)"),
                y=alt.Y("geo:N", sort="-x", title=None),
                tooltip=[alt.Tooltip("geo:N", title="Geografía"), alt.Tooltip("gap_pp:Q", title="Brecha (pp)", format="+.2f")],
            )
            .properties(height=max(180, 26 * len(rank)))
        )
        show(bar)
        st.caption("Serie de media móvil de 3 meses sin ajuste estacional: sirve para brechas y tendencias, no para comparar niveles mes a mes.")

with tab_edu:
    ratio = get("degree_ratio")
    st.subheader("Desempleados por vacante según nivel educativo exigido")
    if ratio is None:
        st.warning(f"Esta sección no está disponible: {meta.get('errors', {}).get('degree_ratio', 'sin datos')}")
    else:
        deltas = change_vs(ratio, "education_required", "unemployed_per_vacancy", 4)  # trimestral: 4 = hace un año
        now = ratio[ratio["period"] == ratio["period"].max()].set_index("education_required")["unemployed_per_vacancy"]
        for col, level in zip(st.columns(len(now)), now.index):
            delta = f"{deltas[level]:+.2f} vs hace un año" if level in deltas.index else None
            col.metric(level, f"{now[level]:.1f}", delta, delta_color="off")
        line_chart(ratio, "unemployed_per_vacancy", "education_required", "Desempleados por vacante", fmt=".2f")

with tab_lab:
    st.subheader("¿El EI reacciona al desempleo, y con cuántos meses de retraso?")
    lag = get("lag_correlation_canada").dropna(subset=["corr"])
    best = int(lag.loc[lag["corr"].idxmax(), "lag_months"])
    lag_chart = (
        alt.Chart(lag)
        .mark_bar()
        .encode(
            x=alt.X("lag_months:O", title="Rezago k (meses)", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("corr:Q", title="Correlación"),
            color=alt.condition(alt.datum.lag_months == best, alt.value(ACCENT), alt.value(MUTED)),
            tooltip=[alt.Tooltip("lag_months:O", title="k"), alt.Tooltip("corr:Q", title="Correlación", format=".2f"), alt.Tooltip("n:Q", title="Observaciones")],
        )
        .properties(height=280)
    )
    show(lag_chart)
    st.caption(f"Pico en k = {best} meses. Correlación de cambios mensuales entre la tasa de desempleo (t) y el indicador de EI (t + k). Descriptivo, no causal. El valor negativo en k = 0 es en parte mecánico: el desempleo está en el denominador del indicador.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Provincias, promedio últimos 12 meses**")
        cs = get("cross_section_12m")
        if {"unemployment_rate", "ei_per_unemployed"} <= set(cs.columns):
            base = alt.Chart(cs).encode(
                x=alt.X("unemployment_rate:Q", title="Tasa de desempleo (%)", scale=alt.Scale(zero=False)),
                y=alt.Y("ei_per_unemployed:Q", title="EI por desempleado", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("geo:N", title="Provincia"), alt.Tooltip("unemployment_rate:Q", format=".2f"), alt.Tooltip("ei_per_unemployed:Q", format=".2f")],
            )
            show((base.mark_circle(size=90, color=ACCENT) + base.mark_text(dx=8, align="left", fontSize=11).encode(text="geo:N")).properties(height=340))
        st.dataframe(cs.round(3), hide_index=True)
    with right:
        st.markdown("**Qué tan inusual es el último valor frente a su propia historia (z-score)**")
        out = get("outliers_ei_gap").copy()
        out["period"] = out["period"].dt.strftime("%Y-%m")
        st.dataframe(out.round(3), hide_index=True)

with st.expander("Fuentes, frescura y límites"):
    if meta.get("tables"):
        st.dataframe(pd.DataFrame(meta["tables"])[["productId", "title", "start", "end", "release"]], hide_index=True)
    st.markdown(
        "- Las correlaciones son descriptivas: con tablas separadas no se puede inferir causalidad.\n"
        "- Una geografía con desempleo alto y poco EI puede reflejar elegibilidad, no solo cobertura.\n"
        "- Código y método: ver el repositorio del proyecto."
    )
