from __future__ import annotations

import time
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from gttac_insight.analytics import load_dashboard_summary
from gttac_insight.api_models import (
    DashboardSummary,
    ExplainRequest,
    ExplainResponse,
    NLQueryRequest,
    NLQueryResponse,
    NLRunQueryResponse,
    RunQueryRequest,
    RunQueryResponse,
)
from gttac_insight.config import get_settings
from gttac_insight.db import execute_query
from gttac_insight.rag.explain import explain_with_rag
from gttac_insight.rag.ingest import ingest_and_save
from gttac_insight.rag.index import load_bundle
from gttac_insight.sql_safety import validate_and_prepare_sql
from gttac_insight.text_to_sql import generate_sql


app = FastAPI(title="GTTAC Insight API", version="0.1.0")

# Local-dev friendly; lock down in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(top_n: int = 8) -> DashboardSummary:
    try:
        settings = get_settings()
        return load_dashboard_summary(settings, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/nl", response_model=NLQueryResponse)
def nl_to_sql(req: NLQueryRequest) -> NLQueryResponse:
    settings = get_settings()
    try:
        t2s = generate_sql(
            settings,
            req.question.strip(),
            incident_types=list(req.incident_types),
            region=(req.region.strip() if req.region else None),
            date_from=(req.date_from.strip() if req.date_from else None),
            date_to=(req.date_to.strip() if req.date_to else None),
        )
        return NLQueryResponse(sql=t2s.sql, chart=t2s.chart.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/query/run", response_model=RunQueryResponse)
def run_sql(req: RunQueryRequest) -> RunQueryResponse:
    settings = get_settings()
    t0 = time.time()
    try:
        safe_sql = validate_and_prepare_sql(req.sql, settings.max_rows)
        df = execute_query(settings, safe_sql, max_rows=settings.max_rows)
        # execute_query already caps; infer truncation by requesting max_rows+1 is handled there.
        # We can't know if truncated here without changing execute_query; use a best-effort:
        truncated = len(df) >= settings.max_rows
        cols = list(df.columns)
        rows: list[dict[str, Any]] = df.to_dict(orient="records")
        _ = (time.time() - t0) * 1000
        return RunQueryResponse(
            columns=cols,
            rows=rows,
            truncated=truncated,
            row_count=len(rows),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _nl_generate_and_run(settings, req: NLQueryRequest):
    """Generate SQL from NL and execute it, retrying once if DB execution fails."""
    kwargs = dict(
        incident_types=list(req.incident_types),
        region=(req.region.strip() if req.region else None),
        date_from=(req.date_from.strip() if req.date_from else None),
        date_to=(req.date_to.strip() if req.date_to else None),
    )
    extra_context = ""
    for attempt in range(2):
        t2s = generate_sql(settings, req.question.strip(), extra_context=extra_context, **kwargs)
        try:
            df = execute_query(settings, t2s.sql, max_rows=settings.max_rows)
            return t2s, df
        except Exception as db_err:
            if attempt == 0:
                extra_context = (
                    f"Your previous SQL failed when executed against the database:\n"
                    f"  SQL: {t2s.sql}\n"
                    f"  Error: {db_err}\n"
                    f"Fix the SQL using ONLY these real column names:\n"
                    f"  casualties:    killed_total, wounded_total, perpetrator_fatalities\n"
                    f"  tactics:       tactic_type, weapon_type, is_suicide_attack\n"
                    f"  perpetrators:  ideology_category, group_name, is_designated_fto\n"
                    f"  incidents:     incident_id, incident_date, year, month, region, country,\n"
                    f"                 state_province, city, latitude, longitude, incident_type, incident_summary\n"
                    f"Do NOT invent column names. Output corrected JSON now."
                )
            else:
                raise


@app.post("/query/nl_run", response_model=NLRunQueryResponse)
def nl_run(req: NLQueryRequest) -> NLRunQueryResponse:
    settings = get_settings()
    try:
        t2s, df = _nl_generate_and_run(settings, req)
        truncated = len(df) >= settings.max_rows
        results = RunQueryResponse(
            columns=list(df.columns),
            rows=df.to_dict(orient="records"),
            truncated=truncated,
            row_count=int(df.shape[0]),
        )
        return NLRunQueryResponse(sql=t2s.sql, chart=t2s.chart.model_dump(), results=results)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest) -> ExplainResponse:
    settings = get_settings()
    try:
        df = pd.DataFrame(req.result_rows)
        md = explain_with_rag(
            settings,
            user_question=req.question,
            sql=req.sql,
            result_df=df,
        )
        return ExplainResponse(explanation_markdown=md)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/rag/status")
def rag_status() -> dict[str, Any]:
    settings = get_settings()
    try:
        b = load_bundle(settings.rag_index_dir)
        return {
            "ok": True,
            "index_dir": settings.rag_index_dir,
            "chunks": len(b.chunks),
            "embedding_dim": b.embedding_dim,
        }
    except FileNotFoundError:
        return {"ok": False, "index_dir": settings.rag_index_dir, "chunks": 0}


@app.post("/rag/reindex")
def rag_reindex() -> dict[str, Any]:
    settings = get_settings()
    try:
        ingest_and_save(settings)
        b = load_bundle(settings.rag_index_dir)
        return {
            "ok": True,
            "index_dir": settings.rag_index_dir,
            "chunks": len(b.chunks),
            "embedding_dim": b.embedding_dim,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

