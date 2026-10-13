"""SQL safety validator tests."""

from __future__ import annotations

import pytest

from gttac_insight.sql_safety import validate_select_sql


def test_rejects_delete() -> None:
    r = validate_select_sql("DELETE FROM incidents WHERE incident_id = 1")
    assert not r.ok


def test_rejects_insert() -> None:
    r = validate_select_sql("INSERT INTO incidents (incident_date) VALUES ('2020-01-01')")
    assert not r.ok


def test_rejects_multiple_statements() -> None:
    r = validate_select_sql("SELECT 1; SELECT 2")
    assert not r.ok


def test_rejects_disallowed_table() -> None:
    r = validate_select_sql("SELECT * FROM users LIMIT 10", max_rows=100)
    assert not r.ok


def test_accepts_simple_select_and_injects_limit() -> None:
    r = validate_select_sql("SELECT incident_id FROM incidents", max_rows=50)
    assert r.ok
    assert "LIMIT" in r.sql.upper()
    assert "50" in r.sql


def test_caps_high_limit() -> None:
    r = validate_select_sql("SELECT * FROM incidents LIMIT 99999", max_rows=100)
    assert r.ok
    # Should cap to 100
    assert "100" in r.sql


def test_accepts_with_cte() -> None:
    sql = """
    WITH t AS (
      SELECT incident_id FROM incidents WHERE region = 'South Asia'
    )
    SELECT COUNT(*) AS n FROM t
    """
    r = validate_select_sql(sql, max_rows=20)
    assert r.ok


def test_prompt_to_sql_validate_smoke() -> None:
    """End-to-end style: raw LLM-like SQL string → validator."""
    raw = "SELECT COUNT(DISTINCT i.incident_id) FROM incidents i JOIN tactics t ON t.incident_id = i.incident_id WHERE i.incident_type = 'VITA'"
    r = validate_select_sql(raw, max_rows=100)
    assert r.ok
