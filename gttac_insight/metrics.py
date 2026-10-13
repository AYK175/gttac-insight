"""Landing-page metrics from dashboard view or SQL fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from gttac_insight.config import Settings
from gttac_insight.db import execute_query, view_exists


@dataclass
class DashboardMetrics:
    total_incidents: int
    total_casualties: int
    prevalent_tactics: str
    most_affected_region: Optional[str] = None


def _from_view(settings: Settings) -> Optional[DashboardMetrics]:
    if not view_exists(settings, "dashboard_summary_stats"):
        return None
    df = execute_query(settings, "SELECT * FROM dashboard_summary_stats LIMIT 1")
    if df.empty:
        return None
    row = df.iloc[0]
    tactics_df = execute_query(
        settings,
        """
        SELECT tactic_type, COUNT(*) AS cnt
        FROM tactics
        GROUP BY tactic_type
        ORDER BY cnt DESC
        LIMIT 1
        """,
    )
    prevalent = (
        str(tactics_df.iloc[0]["tactic_type"])
        if not tactics_df.empty
        else "N/A"
    )
    return DashboardMetrics(
        total_incidents=int(row.get("total_incidents") or 0),
        total_casualties=int(row.get("total_casualties") or 0),
        prevalent_tactics=prevalent,
        most_affected_region=(
            str(row["most_affected_region"])
            if row.get("most_affected_region") is not None
            else None
        ),
    )


def _from_fallback(settings: Settings) -> DashboardMetrics:
    inc = execute_query(
        settings,
        """
        SELECT COUNT(*) AS total_incidents FROM incidents
        """,
    )
    cas = execute_query(
        settings,
        """
        SELECT COALESCE(SUM(killed_total + wounded_total), 0) AS total_casualties
        FROM casualties
        """,
    )
    tac = execute_query(
        settings,
        """
        SELECT tactic_type, COUNT(*) AS cnt
        FROM tactics
        GROUP BY tactic_type
        ORDER BY cnt DESC
        LIMIT 1
        """,
    )
    reg = execute_query(
        settings,
        """
        SELECT region, COUNT(*) AS cnt
        FROM incidents
        WHERE region IS NOT NULL AND region <> ''
        GROUP BY region
        ORDER BY cnt DESC
        LIMIT 1
        """,
    )
    return DashboardMetrics(
        total_incidents=int(inc.iloc[0]["total_incidents"]) if not inc.empty else 0,
        total_casualties=int(cas.iloc[0]["total_casualties"]) if not cas.empty else 0,
        prevalent_tactics=str(tac.iloc[0]["tactic_type"]) if not tac.empty else "N/A",
        most_affected_region=str(reg.iloc[0]["region"]) if not reg.empty else None,
    )


def load_dashboard_metrics(settings: Settings) -> DashboardMetrics:
    m = _from_view(settings)
    if m is not None:
        return m
    return _from_fallback(settings)
