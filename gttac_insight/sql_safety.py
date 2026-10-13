"""Strict read-only SQL validation (SELECT-only, allowlisted tables, LIMIT)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Set

import sqlglot
from sqlglot import exp

from gttac_insight.schema import ALLOWED_TABLES


@dataclass
class ValidationResult:
    ok: bool
    sql: str
    error: Optional[str] = None


def _strip_trailing_semicolon(s: str) -> str:
    s = s.strip()
    if s.endswith(";"):
        s = s[:-1].strip()
    return s


def _has_multiple_statements(sql: str) -> bool:
    stripped = _strip_trailing_semicolon(sql)
    return ";" in stripped


def _collect_tables(expression: exp.Expression) -> Set[str]:
    names: Set[str] = set()
    for node in expression.walk():
        if isinstance(node, exp.Table):
            n = node.name
            if n:
                names.add(n.lower())
    return names


def _cte_aliases(parsed: exp.Expression) -> Set[str]:
    """Return names that are defined within the query (CTEs and derived-table aliases).

    These must not be rejected by the allowlist check because they are not
    real table references — they are names defined by the query itself.
    """
    aliases: Set[str] = set()
    for node in parsed.walk():
        # WITH alias AS (...)
        if isinstance(node, exp.CTE) and node.alias:
            aliases.add(node.alias.lower())
        # FROM (...) AS derived_name
        if isinstance(node, exp.Subquery) and node.alias:
            aliases.add(str(node.alias).lower())
    return aliases


_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


def _apply_limit(sql: str, max_rows: int) -> str:
    """Add or cap the LIMIT clause via string post-processing.

    Avoids a sqlglot serialization bug where injecting a Limit node via AST
    mutation causes the value to be printed without a space after ORDER BY DESC
    (e.g. ``ORDER BY col DESC5000``).
    """
    m = _LIMIT_RE.search(sql)
    if m:
        current = int(m.group(1))
        if current > max_rows:
            return _LIMIT_RE.sub(f"LIMIT {max_rows}", sql)
        return sql
    return sql.rstrip(" \t\n;") + f" LIMIT {max_rows}"


def _forbidden_types() -> tuple[type, ...]:
    return (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.TruncateTable,
        exp.Command,
    )


def validate_select_sql(raw_sql: str, max_rows: int = 5000) -> ValidationResult:
    sql = raw_sql.strip()
    if not sql:
        return ValidationResult(ok=False, sql=sql, error="Empty SQL")

    if _has_multiple_statements(sql):
        return ValidationResult(
            ok=False, sql=sql, error="Multiple statements are not allowed"
        )

    sql_clean = _strip_trailing_semicolon(sql)

    try:
        parsed = sqlglot.parse_one(sql_clean, read="postgres")
    except sqlglot.errors.ParseError as e:
        return ValidationResult(ok=False, sql=sql, error=f"Parse error: {e}")

    if isinstance(parsed, exp.With):
        if not isinstance(parsed.this, exp.Select):
            return ValidationResult(
                ok=False, sql=sql, error="Only SELECT queries are allowed"
            )
        select_expr = parsed.this
        walk_root = parsed
    elif isinstance(parsed, exp.Select):
        select_expr = parsed
        walk_root = parsed
    else:
        return ValidationResult(
            ok=False, sql=sql, error="Only SELECT queries are allowed"
        )

    forbidden = _forbidden_types()
    for node in walk_root.walk():
        if isinstance(node, forbidden):
            return ValidationResult(
                ok=False,
                sql=sql,
                error=f"Forbidden statement type: {type(node).__name__}",
            )

    tables = _collect_tables(walk_root)
    cte_ok = _cte_aliases(walk_root)
    unknown = tables - ALLOWED_TABLES - cte_ok
    if unknown:
        return ValidationResult(
            ok=False,
            sql=sql,
            error=(
                f"Tables not allowed: {sorted(unknown)}. "
                f"Allowed: {sorted(ALLOWED_TABLES)}"
            ),
        )

    safe_sql = _apply_limit(walk_root.sql(dialect="postgres"), max_rows)
    return ValidationResult(ok=True, sql=safe_sql, error=None)


def validate_and_prepare_sql(raw_sql: str, max_rows: int) -> str:
    result = validate_select_sql(raw_sql, max_rows=max_rows)
    if not result.ok:
        raise ValueError(result.error or "Invalid SQL")
    return result.sql
