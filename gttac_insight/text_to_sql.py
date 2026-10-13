"""Text-to-SQL with GTTAC methodology grounding (Anthropic or Ollama)."""

from __future__ import annotations

import json
import re
from typing import Any, List, Literal, Optional

import sqlglot
from sqlglot import exp as sqle
from pydantic import BaseModel, Field

from gttac_insight.config import Settings
from gttac_insight.llm import chat_completion
from gttac_insight.rag.retrieve import format_context_blocks, retrieve_context
from gttac_insight.schema import SCHEMA_FOR_LLM
from gttac_insight.sql_safety import validate_and_prepare_sql


class ChartIntent(BaseModel):
    chart_kind: Literal[
        "bar", "line", "temporal", "pie", "scatter", "heatmap", "geo", "table", "none"
    ] = "table"
    x_column: Optional[str] = None      # bar/line/temporal/scatter/heatmap x-axis
    y_column: Optional[str] = None      # bar/line/temporal/scatter/heatmap y-axis
    label_column: Optional[str] = None  # pie: category labels
    value_column: Optional[str] = None  # pie/heatmap: numeric value
    lat_column: Optional[str] = None    # geo: latitude
    lon_column: Optional[str] = None    # geo: longitude
    title: Optional[str] = None


class TextToSQLResult(BaseModel):
    sql: str
    chart: ChartIntent
    raw_response: str = ""


# Kept minimal — smaller models (Ollama) often ignore long system prompts.
# The full instruction lives in the user message instead.
SYSTEM_PROMPT = (
    "You are a PostgreSQL query generator for the GTTAC GRID terrorism database. "
    "Your only output is a single JSON object. Never answer questions in plain text. "
    "Never use retrieved documents to answer — use them only as SQL hints."
)

# Two-shot examples — one incidents-only, one with a JOIN to tactics.
_EXAMPLE_JSON = (
    '{"sql": "SELECT i.region, COUNT(DISTINCT i.incident_id) AS incident_count'
    " FROM incidents i WHERE i.incident_type IN ('Terrorist Incident', 'VITA')"
    ' AND i.year = 2022 GROUP BY i.region ORDER BY incident_count DESC",'
    ' "chart_kind": "bar", "x_column": "region", "y_column": "incident_count",'
    ' "label_column": null, "value_column": null,'
    ' "lat_column": null, "lon_column": null, "title": "Incidents by Region 2022"}'
)

# Second example showing the mandatory pattern for querying tactics/perpetrators/casualties.
_EXAMPLE_JSON2 = (
    '{"sql": "SELECT t.tactic_type, COUNT(DISTINCT i.incident_id) AS cnt'
    " FROM incidents i JOIN tactics t ON t.incident_id = i.incident_id"
    " WHERE i.incident_type IN ('Terrorist Incident', 'VITA') AND i.year = 2023"
    ' GROUP BY t.tactic_type ORDER BY cnt DESC",'
    ' "chart_kind": "bar", "x_column": "tactic_type", "y_column": "cnt",'
    ' "label_column": null, "value_column": null,'
    ' "lat_column": null, "lon_column": null, "title": "Tactics Used in 2023"}'
)

_FORMAT_BLOCK = """
=== OUTPUT FORMAT (JSON only — no prose, no explanation, no markdown) ===
Return exactly one JSON object. The first key MUST be "sql" (not "query", not "select").

Keys:
  "sql"          : a single PostgreSQL SELECT statement — no semicolon, no LIMIT
  "chart_kind"   : one of "bar"|"temporal"|"line"|"pie"|"scatter"|"heatmap"|"geo"|"table"|"none"
                   bar=compare categories  temporal=year/month trend  pie=≤8-slice proportion
                   heatmap=two categorical axes  geo=has lat+lon cols  table=detail rows  none=scalar
  "x_column"     : column name for x-axis (bar/line/temporal/scatter/heatmap-x), or null
  "y_column"     : column name for y-axis numeric (bar/line/temporal/scatter/heatmap-y), or null
  "label_column" : category column for pie, or null
  "value_column" : numeric value column for pie or heatmap cell, or null
  "lat_column"   : latitude column name for geo, or null
  "lon_column"   : longitude column name for geo, or null
  "title"        : short chart title, or null

SQL RULES:
  1. Tables: incidents, perpetrators, tactics, casualties, dashboard_summary_stats only.
  2. ALWAYS start FROM incidents i. To query tactics/perpetrators/casualties, JOIN them TO incidents.
     NEVER start FROM tactics or FROM perpetrators — year/region/incident_type live on incidents only.
  3. Deaths/killed = c.killed_total  |  wounded = c.wounded_total  |  total = SUM(c.killed_total + c.wounded_total)
     Join: JOIN casualties c ON c.incident_id = i.incident_id
  4. Joining perpetrators/tactics/casualties → COUNT(DISTINCT i.incident_id).
  5. Year filter: i.year = 2023  (NOT EXTRACT, NOT i.date, NOT i.incident_date).
  6. incident_id is TEXT in all tables.
  7. No LIMIT clause — the system adds it.
  8. EXACT column names — use only these, no invented names:
       tactics:      tactic_type, weapon_type, is_suicide_attack
       perpetrators: ideology_category, group_name, is_designated_fto
       casualties:   killed_total, wounded_total, perpetrator_fatalities

Example 1 (incidents query):
""" + _EXAMPLE_JSON + """

Example 2 (tactics/perpetrators/casualties query — ALWAYS join FROM incidents i):
""" + _EXAMPLE_JSON2 + "\n=== END FORMAT ==="


def _incident_type_clause(incident_types: List[str]) -> str:
    if not incident_types:
        return "('Terrorist Incident', 'VITA')"
    escaped = ", ".join("'" + t.replace("'", "''") + "'" for t in incident_types)
    return f"({escaped})"


def build_user_prompt(
    question: str,
    incident_types: List[str],
    region: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    retrieved_context: Optional[str] = None,
) -> str:
    filters = [
        f"i.incident_type IN {_incident_type_clause(incident_types)}",
    ]
    if region:
        filters.append(f"i.region ILIKE '%{region}%'")
    if date_from:
        filters.append(f"i.incident_date >= '{date_from}'")
    if date_to:
        filters.append(f"i.incident_date <= '{date_to}'")

    parts = [
        _FORMAT_BLOCK,
        "",
        "=== DATABASE SCHEMA ===",
        SCHEMA_FOR_LLM,
    ]

    if retrieved_context:
        parts += [
            "",
            "=== SQL MAPPING HINTS (use only to improve SQL accuracy, do NOT use to answer the question) ===",
            retrieved_context,
            "=== END HINTS ===",
        ]

    parts += [
        "",
        "=== QUESTION TO CONVERT TO SQL ===",
        f"Question: {question}",
        f"Required SQL filters: {' AND '.join(filters)}",
        "",
        "Generate the JSON object now. Output only the JSON, nothing else.",
    ]

    return "\n".join(parts)


_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")
_MD_FENCE = re.compile(r"^```[\w]*\s*|\s*```$", re.MULTILINE)
_SQL_FENCE = re.compile(r"^```[\w]*\s*|\s*```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that some models add despite instructions."""
    return _MD_FENCE.sub("", text).strip()


def _strip_sql_fences(sql: str) -> str:
    """Remove ```sql / ``` wrappers from inside a JSON sql field value."""
    return _SQL_FENCE.sub("", sql).strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if m:
            return json.loads(m.group())
        raise ValueError(
            f"LLM did not return valid JSON. Raw response (first 500 chars):\n{text[:500]}"
        )


_SQL_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
# Matches "sql": "..." or "query": "..." even when the value contains literal newlines
_SQL_KEY_RE = re.compile(
    r'"(?:sql|query|select|statement)"\s*:\s*"([\s\S]*?)"(?=\s*[,}\n])',
    re.IGNORECASE,
)


def _extract_sql_field(data: dict[str, Any], _depth: int = 0) -> str:
    """Extract the SQL string from the LLM JSON response.

    Handles:
    - {"sql": "SELECT ..."}                         canonical
    - {"query": "SELECT ..."}                       common alternative key
    - {"response": {"sql": "SELECT ..."}}           dict wrapper
    - {"response": "{\"sql\": \"SELECT ...\"}"}     double-encoded JSON string wrapper
    - any string value starting with SELECT/WITH    last-resort scan
    """
    if _depth > 3:
        return ""

    # 1. Direct SQL keys
    for key in ("sql", "query", "select", "SQL", "QUERY", "SELECT", "statement"):
        v = data.get(key)
        if isinstance(v, str):
            cleaned = _strip_sql_fences(v)
            if cleaned:
                return cleaned

    # 2. Wrapper keys whose value is a dict or a JSON-encoded string
    for key in ("response", "result", "output", "data", "answer"):
        v = data.get(key)
        if isinstance(v, dict):
            found = _extract_sql_field(v, _depth + 1)
            if found:
                return found
        elif isinstance(v, str):
            # Maybe double-encoded JSON: value is itself a JSON string
            try:
                inner = json.loads(v)
                if isinstance(inner, dict):
                    found = _extract_sql_field(inner, _depth + 1)
                    if found:
                        return found
            except (json.JSONDecodeError, ValueError):
                # The inner string is malformed JSON (e.g. literal newlines inside
                # a string value).  Fall back to regex extraction of the sql key.
                m = _SQL_KEY_RE.search(v)
                if m:
                    return _strip_sql_fences(m.group(1))
            # Or maybe the value IS the SQL
            cleaned = _strip_sql_fences(v)
            if _SQL_START.match(cleaned):
                return cleaned

    # 3. Scan every value for SQL strings or nested dicts
    for v in data.values():
        if isinstance(v, str):
            cleaned = _strip_sql_fences(v)
            if _SQL_START.match(cleaned):
                return cleaned
        elif isinstance(v, dict):
            found = _extract_sql_field(v, _depth + 1)
            if found:
                return found

    return ""


# Pairs of (pattern, replacement) to fix common column-name hallucinations.
# Applied unconditionally before SQL validation.
_COLUMN_FIXES: List[tuple[re.Pattern[str], str]] = [
    # ── deaths / killed ──────────────────────────────────────────────────────
    # alias.deaths → alias.killed_total
    (re.compile(r'\b(\w+)\.deaths\b', re.IGNORECASE), r'\1.killed_total'),
    # alias.num_killed / total_killed / fatalities → alias.killed_total
    (re.compile(r'\b(\w+)\.(?:num_killed|total_killed|fatalities)\b', re.IGNORECASE), r'\1.killed_total'),

    # ── wounded ──────────────────────────────────────────────────────────────
    (re.compile(r'\b(\w+)\.(?:num_wounded|total_wounded)\b', re.IGNORECASE), r'\1.wounded_total'),

    # ── "casualties" used as a bare column (not as the table name) ───────────
    # SUM(casualties) — no table prefix
    (re.compile(r'\bSUM\s*\(\s*casualties\s*\)', re.IGNORECASE),
     'SUM(c.killed_total + c.wounded_total)'),
    # alias.casualties → (alias.killed_total + alias.wounded_total)
    (re.compile(r'\b(\w+)\.casualties\b', re.IGNORECASE),
     r'(\1.killed_total + \1.wounded_total)'),
    # ", casualties" in a SELECT list — comma-separated bare reference
    # Negative lookahead excludes "JOIN casualties c" and "FROM casualties"
    (re.compile(r',\s*casualties\b(?!\s+\w+\s+ON\b)(?!\s+\w+\s*(?:INNER|LEFT|RIGHT|JOIN|WHERE|GROUP|ORDER|LIMIT))',
                re.IGNORECASE),
     ', (c.killed_total + c.wounded_total) AS casualties'),

    # ── date / region / country column aliases ────────────────────────────────
    (re.compile(r'\bi\.date\b', re.IGNORECASE), 'i.incident_date'),
    (re.compile(r'\bi\.(?:region_txt|region_text)\b', re.IGNORECASE), 'i.region'),
    (re.compile(r'\bi\.(?:country_txt|country_nongenc_txt|country_genc_txt)\b', re.IGNORECASE), 'i.country'),

    # ── SQLite-style date functions → PostgreSQL ──────────────────────────────
    # STRFTIME('%Y', col) and DATE_FORMAT(col, '%Y') → use pre-computed i.year
    # (also eliminates the % sign that psycopg misreads as a parameter placeholder)
    (re.compile(r"\bSTRFTIME\s*\(\s*'%Y'\s*,\s*\w+(?:\.\w+)?\s*\)", re.IGNORECASE), 'i.year'),
    (re.compile(r"\bDATE_FORMAT\s*\(\s*\w+(?:\.\w+)?\s*,\s*'%Y'\s*\)", re.IGNORECASE), 'i.year'),
    # STRFTIME('%m', ...) → EXTRACT(MONTH FROM i.incident_date)
    (re.compile(r"\bSTRFTIME\s*\(\s*'%m'\s*,\s*\w+(?:\.\w+)?\s*\)", re.IGNORECASE), 'EXTRACT(MONTH FROM i.incident_date)'),
    # YEAR(col) / YEAR(i.incident_date) → i.year  (MySQL-style)
    (re.compile(r"\bYEAR\s*\(\s*\w+(?:\.\w+)?\s*\)", re.IGNORECASE), 'i.year'),
    # EXTRACT(YEAR FROM col) → i.year  (already valid PG but redundant given pre-computed col)
    (re.compile(r"\bEXTRACT\s*\(\s*YEAR\s+FROM\s+\w+(?:\.\w+)?\s*\)", re.IGNORECASE), 'i.year'),
    # TO_CHAR with Python-style format strings → PostgreSQL format strings
    (re.compile(r"'%Y'"), "'YYYY'"),
    (re.compile(r"'%m'"), "'MM'"),
    (re.compile(r"'%d'"), "'DD'"),

    # ── tactics table column hallucinations ───────────────────────────────────
    # alias.weapon / alias.weapon_used / alias.weapon_name → alias.weapon_type
    (re.compile(r'\b(\w+)\.(?:weapon|weapon_used|weapon_name|weapons)\b', re.IGNORECASE), r'\1.weapon_type'),
    # alias.tactic / alias.attack_type / alias.method → alias.tactic_type
    (re.compile(r'\b(\w+)\.(?:tactic|attack_type|attack_method|method|tactic_name)\b', re.IGNORECASE), r'\1.tactic_type'),
    # alias.suicide / alias.is_suicide → alias.is_suicide_attack
    (re.compile(r'\b(\w+)\.(?:suicide|is_suicide)\b', re.IGNORECASE), r'\1.is_suicide_attack'),

    # ── perpetrators table column hallucinations ──────────────────────────────
    # alias.ideology / alias.group_ideology / alias.category → alias.ideology_category
    (re.compile(r'\b(\w+)\.(?:ideology|group_ideology|affiliation|extremism_type)\b', re.IGNORECASE), r'\1.ideology_category'),
    # alias.group / alias.group_name_col / alias.perpetrator_group → alias.group_name
    (re.compile(r'\b(\w+)\.(?:group|perpetrator_group|group_affiliation)\b', re.IGNORECASE), r'\1.group_name'),
    # alias.fto / alias.designated_fto → alias.is_designated_fto
    (re.compile(r'\b(\w+)\.(?:fto|designated_fto|is_fto)\b', re.IGNORECASE), r'\1.is_designated_fto'),
]


# Columns that live on the casualties table, not incidents.
_CASUALTIES_COLS = ("killed_total", "wounded_total", "perpetrator_fatalities")

# SQL keywords that can never be a table alias.
_SQL_KEYWORDS = frozenset({
    "join", "inner", "left", "right", "outer", "cross", "full",
    "where", "group", "order", "having", "limit", "on", "as",
    "select", "from", "and", "or", "not", "in", "is", "null",
    "by", "asc", "desc", "with", "union", "intersect", "except",
})

_INC_ALIAS_RE = re.compile(r'\bFROM\s+incidents\s+(?:AS\s+)?(\w+)', re.IGNORECASE)
_CAS_ALIAS_RE = re.compile(r'\bJOIN\s+casualties\s+(?:AS\s+)?(\w+)', re.IGNORECASE)


def _fix_wrong_table_alias(sql: str) -> str:
    """Rewrite casualties columns that are prefixed with the wrong table alias.

    Only the casualties table has killed_total / wounded_total / perpetrator_fatalities.
    If ANY alias other than the casualties alias is used, rewrite it.

    Example: ``SELECT T1.killed_total FROM incidents T1 JOIN casualties T2 ...``
    becomes: ``SELECT T2.killed_total FROM incidents T1 JOIN casualties T2 ...``
    """
    sql_lower = sql.lower()

    # Fast exit: no casualties columns at all.
    if not any(col in sql_lower for col in _CASUALTIES_COLS):
        return sql

    # Resolve the casualties alias from the JOIN clause, ignoring SQL keywords.
    cas_m = _CAS_ALIAS_RE.search(sql)
    if cas_m and cas_m.group(1).lower() not in _SQL_KEYWORDS:
        cas_alias = cas_m.group(1)
    else:
        # No usable casualties alias found — check if the JOIN itself is missing.
        if "join casualties" not in sql_lower:
            # Auto-inject the JOIN.
            inc_m = _INC_ALIAS_RE.search(sql)
            if inc_m and inc_m.group(1).lower() not in _SQL_KEYWORDS:
                inc_ref = inc_m.group(1)
            else:
                inc_ref = "incidents"
            join_clause = f" JOIN casualties c ON c.incident_id = {inc_ref}.incident_id"
            insert_re = re.compile(r'\b(WHERE|GROUP|ORDER|LIMIT)\b', re.IGNORECASE)
            m2 = insert_re.search(sql)
            if m2:
                sql = sql[: m2.start(1)] + join_clause + " " + sql[m2.start(1):]
            else:
                sql = sql.rstrip(" ;") + join_clause
        cas_alias = "c"

    # Replace EVERY `anything.col` → `cas_alias.col` when `anything != cas_alias`.
    # This covers all alias naming schemes the model might use.
    for col in _CASUALTIES_COLS:
        def _replacer(m: re.Match, _col: str = col, _cas: str = cas_alias) -> str:
            return m.group(0) if m.group(1).lower() == _cas.lower() else f"{_cas}.{_col}"
        sql = re.sub(r'\b(\w+)\.' + col + r'\b', _replacer, sql, flags=re.IGNORECASE)

    return sql


_INCIDENT_ONLY_BARE = re.compile(
    r'(?<![.\w])(year|incident_type|incident_date|region|country|state_province|city|incident_summary)\b',
    re.IGNORECASE,
)
_FROM_NONINCIDENTS = re.compile(
    r'\bFROM\s+(tactics|perpetrators|casualties|dashboard_summary_stats)\b(?:\s+(?:AS\s+)?(\w+))?',
    re.IGNORECASE,
)


def _fix_missing_incidents_join(sql: str) -> str:
    """When the model queries a non-incidents table directly but filters on incidents-only
    columns (year, region, incident_type …), auto-add the incidents JOIN and prefix the bare
    column references with ``i.``.
    """
    sql_lower = sql.lower()

    # If incidents is already referenced, nothing structural to fix here.
    if "incidents" in sql_lower:
        return sql

    # Only act when incidents-only columns appear bare (without a table prefix).
    if not _INCIDENT_ONLY_BARE.search(sql):
        return sql

    m = _FROM_NONINCIDENTS.search(sql)
    if not m:
        return sql

    tbl_name = m.group(1)
    alias_raw = m.group(2)
    # alias_raw might be a SQL keyword if the table has no alias (e.g. "FROM tactics WHERE")
    if alias_raw and alias_raw.lower() not in _SQL_KEYWORDS:
        primary_alias = alias_raw
    else:
        primary_alias = tbl_name  # use bare table name as the join key source

    join_clause = f" JOIN incidents i ON i.incident_id = {primary_alias}.incident_id"

    insert_re = re.compile(r'\b(WHERE|GROUP|ORDER|LIMIT)\b', re.IGNORECASE)
    m2 = insert_re.search(sql)
    if m2:
        sql = sql[: m2.start()] + join_clause + " " + sql[m2.start():]
    else:
        sql = sql.rstrip(" ;") + join_clause

    # Prefix bare incidents-only columns with i.
    sql = _INCIDENT_ONLY_BARE.sub(r'i.\1', sql)
    return sql


def _fix_column_names(sql: str) -> str:
    for pattern, replacement in _COLUMN_FIXES:
        sql = pattern.sub(replacement, sql)
    sql = _fix_missing_incidents_join(sql)
    sql = _fix_wrong_table_alias(sql)
    return sql


def _postprocess_casualties_hint(question: str, sql: str) -> str:
    q = question.lower()
    if "casualt" not in q and "killed" not in q and "wounded" not in q:
        return sql
    if "killed_total" in sql.lower() or "wounded_total" in sql.lower():
        return sql
    # Light nudge: cannot safely auto-rewrite; return as-is
    return sql


def _build_retry_prompt(original_user: str, bad_sql: str, error: str) -> str:
    """Append a correction request to the original prompt when validation fails."""
    return (
        original_user
        + f"\n\n=== YOUR PREVIOUS SQL WAS REJECTED ===\n"
        f"Bad SQL: {bad_sql}\n"
        f"Error: {error}\n"
        f"Fix the SQL so it uses ONLY these tables: "
        f"incidents, perpetrators, tactics, casualties, dashboard_summary_stats.\n"
        f"Do NOT invent table names. Output the corrected JSON now."
    )


def generate_sql(
    settings: Settings,
    question: str,
    incident_types: List[str],
    region: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    extra_context: str = "",
) -> TextToSQLResult:
    """Generate and validate a SQL query from a natural-language question.

    ``extra_context`` can be used to inject a previous execution error so the
    model gets a chance to self-correct (e.g. "column X does not exist").
    """
    retrieved = ""
    try:
        hits = retrieve_context(settings, question, top_k=settings.t2s_rag_top_k)
        retrieved = format_context_blocks(
            hits,
            prefix="Retrieved notes",
            min_score=settings.rag_min_score,
            max_context_chars=settings.rag_max_context_chars,
        )
    except Exception:
        retrieved = ""

    user_content = build_user_prompt(
        question,
        incident_types,
        region=region,
        date_from=date_from,
        date_to=date_to,
        retrieved_context=retrieved or None,
    )
    if extra_context:
        user_content += f"\n\n=== IMPORTANT CORRECTION ===\n{extra_context}\n=== END CORRECTION ==="

    last_error: str = ""
    data: dict[str, Any] = {}
    text: str = ""

    for attempt in range(3):  # up to 3 attempts
        prompt = (
            user_content
            if attempt == 0
            else _build_retry_prompt(user_content, _extract_sql_field(data), last_error)
        )
        text = chat_completion(
            settings,
            system=SYSTEM_PROMPT,
            user=prompt,
            max_tokens=2048,
            json_mode=True,
        )
        try:
            data = _parse_json_response(text)
        except ValueError:
            last_error = f"Response was not valid JSON: {text[:200]}"
            continue

        raw_sql = _extract_sql_field(data)
        if not raw_sql:
            last_error = f"SQL field was empty. Response: {text[:200]}"
            continue

        raw_sql = _fix_column_names(raw_sql)
        raw_sql = _postprocess_casualties_hint(question, raw_sql)
        try:
            safe_sql = validate_and_prepare_sql(raw_sql, settings.max_rows)
            break  # success
        except ValueError as e:
            last_error = str(e)
            continue
    else:
        raise ValueError(
            f"Could not generate valid SQL after 3 attempts. "
            f"Last error: {last_error}\n"
            f"Last response (500 chars): {text[:500]}"
        )
    _valid_kinds = {"bar", "line", "temporal", "pie", "scatter", "heatmap", "geo", "table", "none"}
    kind = (data.get("chart_kind") or "table").lower()
    if kind not in _valid_kinds:
        kind = "table"
    chart = ChartIntent.model_validate(
        {
            "chart_kind": kind,
            "x_column": data.get("x_column"),
            "y_column": data.get("y_column"),
            "label_column": data.get("label_column"),
            "value_column": data.get("value_column"),
            "lat_column": data.get("lat_column"),
            "lon_column": data.get("lon_column"),
            "title": data.get("title"),
        }
    )
    return TextToSQLResult(sql=safe_sql, chart=chart, raw_response=text)
