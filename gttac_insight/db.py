"""PostgreSQL access with statement timeout and row cap."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from gttac_insight.config import Settings


@contextmanager
def connection(settings: Settings) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings.database_url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{settings.query_timeout_ms}ms'")
        conn.commit()
        yield conn
    finally:
        conn.close()


def execute_query(
    settings: Settings,
    sql: str,
    params: Optional[tuple[Any, ...]] = None,
    max_rows: Optional[int] = None,
) -> pd.DataFrame:
    """
    Run a read-only SELECT. Fetches at most max_rows (defaults to settings.max_rows).
    """
    limit = max_rows if max_rows is not None else settings.max_rows
    with connection(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchmany(limit + 1)
    if len(rows) > limit:
        rows = rows[:limit]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def table_exists(settings: Settings, schema: str, table: str) -> bool:
    with connection(settings) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            return cur.fetchone() is not None


def view_exists(settings: Settings, view_name: str, schema: str = "public") -> bool:
    return table_exists(settings, schema, view_name)
