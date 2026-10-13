"""Pydantic models shared by the API (backend + clients)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


IncidentType = Literal["Terrorist Incident", "VITA"]


class DashboardTopItem(BaseModel):
    label: str
    count: int


class DashboardSummary(BaseModel):
    total_incidents: int
    total_killed: int
    total_wounded: int
    total_casualties: int
    most_affected_region: Optional[str] = None

    top_regions: list[DashboardTopItem] = Field(default_factory=list)
    top_countries: list[DashboardTopItem] = Field(default_factory=list)
    top_ideologies: list[DashboardTopItem] = Field(default_factory=list)
    top_tactics: list[DashboardTopItem] = Field(default_factory=list)
    top_weapon_types: list[DashboardTopItem] = Field(default_factory=list)
    top_groups: list[DashboardTopItem] = Field(default_factory=list)


class ChartIntentModel(BaseModel):
    chart_kind: Literal[
        "bar", "line", "temporal", "pie", "scatter", "heatmap", "geo", "table", "none"
    ] = "table"
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    label_column: Optional[str] = None
    value_column: Optional[str] = None
    lat_column: Optional[str] = None
    lon_column: Optional[str] = None
    title: Optional[str] = None


class NLQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    incident_types: list[IncidentType] = Field(default_factory=list)
    region: Optional[str] = Field(default=None, max_length=200)
    date_from: Optional[str] = Field(default=None, max_length=30)
    date_to: Optional[str] = Field(default=None, max_length=30)


class NLQueryResponse(BaseModel):
    sql: str
    chart: ChartIntentModel


class RunQueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)


class RunQueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    row_count: int


class NLRunQueryResponse(BaseModel):
    sql: str
    chart: ChartIntentModel
    results: RunQueryResponse


class ExplainRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    sql: str = Field(min_length=1, max_length=20000)
    result_rows: list[dict[str, Any]] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    explanation_markdown: str

