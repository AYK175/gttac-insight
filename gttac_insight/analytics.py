"""Reusable analytics queries for dashboards and summaries."""

from __future__ import annotations

from typing import Optional

from gttac_insight.api_models import DashboardSummary, DashboardTopItem
from gttac_insight.config import Settings
from gttac_insight.db import execute_query, view_exists


def _top_items(
    settings: Settings,
    sql: str,
    label_col: str,
    count_col: str = "cnt",
) -> list[DashboardTopItem]:
    df = execute_query(settings, sql)
    if df.empty:
        return []
    out: list[DashboardTopItem] = []
    for _, row in df.iterrows():
        label = row.get(label_col)
        if label is None:
            continue
        out.append(DashboardTopItem(label=str(label), count=int(row.get(count_col) or 0)))
    return out


def load_dashboard_summary(settings: Settings, top_n: int = 8) -> DashboardSummary:
    # Prefer the view if present for the headline stats.
    most_affected_region: Optional[str] = None
    if view_exists(settings, "dashboard_summary_stats"):
        v = execute_query(settings, "SELECT * FROM dashboard_summary_stats LIMIT 1")
        if not v.empty:
            r = v.iloc[0]
            most_affected_region = (
                str(r["most_affected_region"])
                if r.get("most_affected_region") is not None
                else None
            )

    totals = execute_query(
        settings,
        """
        SELECT
          (SELECT COUNT(*) FROM incidents) AS total_incidents,
          (SELECT COALESCE(SUM(killed_total), 0) FROM casualties) AS total_killed,
          (SELECT COALESCE(SUM(wounded_total), 0) FROM casualties) AS total_wounded,
          (SELECT COALESCE(SUM(killed_total + wounded_total), 0) FROM casualties) AS total_casualties
        """,
    )
    if totals.empty:
        base = {
            "total_incidents": 0,
            "total_killed": 0,
            "total_wounded": 0,
            "total_casualties": 0,
        }
    else:
        t = totals.iloc[0]
        base = {
            "total_incidents": int(t.get("total_incidents") or 0),
            "total_killed": int(t.get("total_killed") or 0),
            "total_wounded": int(t.get("total_wounded") or 0),
            "total_casualties": int(t.get("total_casualties") or 0),
        }

    top_regions = _top_items(
        settings,
        f"""
        SELECT region, COUNT(*) AS cnt
        FROM incidents
        WHERE region IS NOT NULL AND region <> ''
        GROUP BY region
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="region",
    )
    top_countries = _top_items(
        settings,
        f"""
        SELECT country, COUNT(*) AS cnt
        FROM incidents
        WHERE country IS NOT NULL AND country <> ''
        GROUP BY country
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="country",
    )
    top_ideologies = _top_items(
        settings,
        f"""
        SELECT ideology_category, COUNT(*) AS cnt
        FROM perpetrators
        WHERE ideology_category IS NOT NULL AND ideology_category <> ''
        GROUP BY ideology_category
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="ideology_category",
    )
    top_tactics = _top_items(
        settings,
        f"""
        SELECT tactic_type, COUNT(*) AS cnt
        FROM tactics
        WHERE tactic_type IS NOT NULL AND tactic_type <> ''
        GROUP BY tactic_type
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="tactic_type",
    )
    top_weapon_types = _top_items(
        settings,
        f"""
        SELECT weapon_type, COUNT(*) AS cnt
        FROM tactics
        WHERE weapon_type IS NOT NULL AND weapon_type <> ''
        GROUP BY weapon_type
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="weapon_type",
    )
    top_groups = _top_items(
        settings,
        f"""
        SELECT group_name, COUNT(*) AS cnt
        FROM perpetrators
        WHERE group_name IS NOT NULL AND group_name <> ''
        GROUP BY group_name
        ORDER BY cnt DESC
        LIMIT {int(top_n)}
        """,
        label_col="group_name",
    )

    if most_affected_region is None and top_regions:
        most_affected_region = top_regions[0].label

    return DashboardSummary(
        **base,
        most_affected_region=most_affected_region,
        top_regions=top_regions,
        top_countries=top_countries,
        top_ideologies=top_ideologies,
        top_tactics=top_tactics,
        top_weapon_types=top_weapon_types,
        top_groups=top_groups,
    )

