"""App de exploracion: mercado laboral canadiense con tablas abiertas de Statistics Canada.

Lee los CSV precalculados en published/ (o published_demo/ con datos sinteticos, claramente marcado).
No llama a StatCan en vivo: por eso carga rapido.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
st.set_page_config(page_title="Mercado laboral en Canadá", layout="wide")


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
        st.line_chart(view.pivot(index="period", columns="geo", values="ei_per_unemployed"))
        last = view[view["period"] == latest].set_index("geo")
        cols = st.columns(len(pick))
        for col, g in zip(cols, pick):
            if g in last.index:
                col.metric(g, f"{last.loc[g, 'ei_per_unemployed']:.2f}", help="Beneficiarios de EI regular por desempleado, último mes")

with tab_imm:
    gap = get("immigrant_gap")
    st.subheader("Brecha de desempleo frente a nacidos en Canadá (puntos porcentuales)")
    if gap is None:
        st.warning(f"Esta sección no está disponible: {meta.get('errors', {}).get('immigrant_gap', 'sin datos')}")
    else:
        g_geo = st.selectbox("Geografía", sorted(gap["geo"].unique()), index=sorted(gap["geo"].unique()).index("Canada") if "Canada" in set(gap["geo"]) else 0)
        statuses = sorted(gap["immigrant_status"].unique())
        g_status = st.multiselect("Grupos", statuses, default=statuses)
        sel = gap[(gap["geo"] == g_geo) & (gap["immigrant_status"].isin(g_status))]
        if not sel.empty:
            st.line_chart(sel.pivot(index="period", columns="immigrant_status", values="gap_pp"))
        st.markdown("**Último dato por geografía**, para un grupo")
        one = st.selectbox("Grupo a rankear", statuses)
        rank = gap[(gap["immigrant_status"] == one) & (gap["period"] == gap["period"].max())].set_index("geo")["gap_pp"].sort_values()
        st.bar_chart(rank)
        st.caption("Serie de media móvil de 3 meses sin ajuste estacional: sirve para brechas y tendencias, no para comparar niveles mes a mes.")

with tab_edu:
    ratio = get("degree_ratio")
    st.subheader("Desempleados por vacante según nivel educativo exigido")
    if ratio is None:
        st.warning(f"Esta sección no está disponible: {meta.get('errors', {}).get('degree_ratio', 'sin datos')}")
    else:
        st.line_chart(ratio.pivot_table(index="period", columns="education_required", values="unemployed_per_vacancy"))

with tab_lab:
    st.subheader("¿El EI reacciona al desempleo, y con cuántos meses de retraso?")
    lag = get("lag_correlation_canada")
    st.bar_chart(lag.set_index("lag_months")["corr"])
    st.caption("Correlación de cambios mensuales entre la tasa de desempleo (t) y el indicador de EI (t + k meses). Descriptivo, no causal.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Provincias, promedio últimos 12 meses**")
        cs = get("cross_section_12m")
        if {"unemployment_rate", "ei_per_unemployed"} <= set(cs.columns):
            st.scatter_chart(cs, x="unemployment_rate", y="ei_per_unemployed")
        st.dataframe(cs.round(3), hide_index=True)
    with right:
        st.markdown("**Qué tan inusual es el último valor frente a su propia historia (z-score)**")
        st.dataframe(get("outliers_ei_gap").round(3), hide_index=True)

with st.expander("Fuentes, frescura y límites"):
    if meta.get("tables"):
        st.dataframe(pd.DataFrame(meta["tables"])[["productId", "title", "start", "end", "release"]], hide_index=True)
    st.markdown(
        "- Las correlaciones son descriptivas: con tablas separadas no se puede inferir causalidad.\n"
        "- Una geografía con desempleo alto y poco EI puede reflejar elegibilidad, no solo cobertura.\n"
        "- Código y método: ver el repositorio del proyecto."
    )
