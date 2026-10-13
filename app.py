"""
GTTAC Insight — Streamlit dashboard (GRID + NL SQL + RAG explanations).
Run: streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from gttac_insight.config import get_settings
from gttac_insight.db import execute_query
from gttac_insight.metrics import load_dashboard_metrics
from gttac_insight.rag.explain import explain_with_rag
from gttac_insight.text_to_sql import generate_sql
from gttac_insight.viz import dataframe_to_figure

st.set_page_config(
    page_title="GTTAC Insight",
    page_icon="📊",
    layout="wide",
)

st.title("GTTAC Insight")
st.caption("Global Terrorism Trends and Analysis Center — GRID explorer")

try:
    settings = get_settings()
except ValueError as e:
    st.error(str(e))
    st.stop()

# --- Landing metrics ---
st.subheader("Dashboard overview")
try:
    m = load_dashboard_metrics(settings)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total incidents", f"{m.total_incidents:,}")
    c2.metric("Total casualties", f"{m.total_casualties:,}")
    c3.metric("Prevalent tactic (top)", m.prevalent_tactics)
    c4.metric("Most affected region", m.most_affected_region or "—")
except Exception as e:
    st.warning(f"Could not load metrics: {e}")

st.divider()

# --- Natural language + filters ---
st.subheader("Natural language query")
incident_opts = ["Terrorist Incident", "VITA"]
col_a, col_b = st.columns([2, 1])
with col_a:
    question = st.text_area(
        "Ask a question about the data",
        height=120,
        placeholder="e.g. Total casualties by region in 2023 for VITA incidents",
    )
with col_b:
    mode = st.radio(
        "Incident type filter",
        options=["Both", "Terrorist Incident only", "VITA only"],
        horizontal=False,
    )
    region_hint = st.text_input("Region hint (optional)", placeholder="e.g. South Asia")
    d1, d2 = st.columns(2)
    with d1:
        date_from = st.text_input("From (YYYY-MM-DD)", placeholder="optional")
    with d2:
        date_to = st.text_input("To (YYYY-MM-DD)", placeholder="optional")

if mode == "Both":
    incident_types = list(incident_opts)
elif mode == "Terrorist Incident only":
    incident_types = ["Terrorist Incident"]
else:
    incident_types = ["VITA"]

run = st.button("Generate SQL & run", type="primary")

if run:
    if not question.strip():
        st.warning("Enter a question.")
    elif not settings.anthropic_api_key:
        st.error("Set ANTHROPIC_API_KEY for text-to-SQL.")
    else:
        with st.spinner("Generating SQL…"):
            try:
                t2s = generate_sql(
                    settings,
                    question.strip(),
                    incident_types=incident_types,
                    region=region_hint.strip() or None,
                    date_from=date_from.strip() or None,
                    date_to=date_to.strip() or None,
                )
            except Exception as e:
                st.exception(e)
                st.stop()
        st.session_state["last_question"] = question.strip()
        st.session_state["last_sql"] = t2s.sql
        st.session_state["last_chart"] = t2s.chart
        with st.spinner("Executing query…"):
            try:
                df = execute_query(settings, t2s.sql)
            except Exception as e:
                st.exception(e)
                st.stop()
        st.session_state["last_df"] = df
        st.code(t2s.sql, language="sql")
        st.dataframe(df, use_container_width=True)
        fig = dataframe_to_figure(df, t2s.chart)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

if "last_df" in st.session_state and settings.anthropic_api_key:
    if st.button("Explain results (RAG + LLM)"):
        with st.spinner("Retrieving context and drafting explanation…"):
            try:
                df = st.session_state["last_df"]
                if not isinstance(df, pd.DataFrame):
                    df = pd.DataFrame(df)
                expl = explain_with_rag(
                    settings,
                    user_question=str(st.session_state.get("last_question", "")),
                    sql=str(st.session_state.get("last_sql", "")),
                    result_df=df,
                )
                st.markdown("### Why (RAG-assisted)")
                st.markdown(expl)
            except Exception as e:
                st.exception(e)

st.divider()
st.markdown(
    """
**Safety:** Only `SELECT` on allowlisted tables is executed; `LIMIT` is enforced.  
**RAG:** Put `.md`/`.txt` files in `docs/` (or `RAG_DOCS_DIR`), then run  
`python -m gttac_insight.rag` to build the index.
"""
)
