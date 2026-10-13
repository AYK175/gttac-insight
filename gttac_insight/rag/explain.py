"""Retrieve discourse context and generate explanations via LLM provider."""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List

from gttac_insight.config import Settings
from gttac_insight.llm import chat_completion
from gttac_insight.rag.retrieve import format_context_blocks, retrieve_context


def _summarize_df(df: pd.DataFrame, max_rows: int = 8) -> str:
    if df.empty:
        return "No result rows."
    return df.head(max_rows).to_string(index=False)


def explain_with_rag(
    settings: Settings,
    user_question: str,
    sql: str,
    result_df: pd.DataFrame,
    top_k: int | None = None,
) -> str:
    try:
        k = int(top_k) if top_k is not None else int(settings.rag_explain_top_k)
        hits = retrieve_context(settings, user_question, top_k=k)
    except FileNotFoundError:
        hits = []
    context_str = format_context_blocks(
        hits,
        prefix="Retrieved discourse excerpts (may be empty)",
        min_score=settings.rag_min_score,
        max_context_chars=settings.rag_max_context_chars,
    )

    prompt = f"""You are briefing a terrorism analyst at GTTAC. Write a direct analytical narrative — under 200 words — about the findings below.

Question asked: {user_question}

Data:
{_summarize_df(result_df)}

{context_str}

Instructions:
- Open immediately with the key finding or pattern. Never start with "The SQL query shows", "The data indicates", "The results suggest", or any similar phrase.
- Write in active voice as if narrating what happened in the world, not what the table contains.
- Where the excerpts add context, weave them in naturally and cite as [1], [2], etc.
- Close with one crisp caveat only if it materially affects interpretation (e.g. dataset scope, definition ambiguity).
- Stay under 200 words. No bullet points. No headers.
"""
    return chat_completion(settings, system=None, user=prompt, max_tokens=1200)
