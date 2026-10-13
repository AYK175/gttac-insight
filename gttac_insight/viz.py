"""Safe Plotly charts from dataframe + chart intent."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from gttac_insight.text_to_sql import ChartIntent


def dataframe_to_figure(
    df: pd.DataFrame,
    intent: ChartIntent,
) -> Optional[go.Figure]:
    if df.empty or intent.chart_kind in ("table", "none"):
        return None
    x = intent.x_column
    y = intent.y_column
    if not x or not y:
        return None
    if x not in df.columns or y not in df.columns:
        # Try case-insensitive match
        colmap = {c.lower(): c for c in df.columns}
        x = colmap.get(x.lower(), x) if x else x
        y = colmap.get(y.lower(), y) if y else y
        if x not in df.columns or y not in df.columns:
            return None

    title = intent.title or f"{y} vs {x}"
    if intent.chart_kind == "bar":
        return px.bar(df, x=x, y=y, title=title)
    if intent.chart_kind == "line":
        return px.line(df, x=x, y=y, title=title)
    if intent.chart_kind == "scatter":
        return px.scatter(df, x=x, y=y, title=title)
    return None
