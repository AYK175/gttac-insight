"""RAG retrieval helpers (used by both NL→SQL and explanations)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from gttac_insight.config import Settings
from gttac_insight.rag.index import load_bundle, search


def retrieve_context(
    settings: Settings,
    query: str,
    top_k: int = 5,
) -> list[tuple[float, str, dict[str, Any]]]:
    bundle = load_bundle(settings.rag_index_dir)
    model = SentenceTransformer(settings.embedding_model)
    q = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0]
    hits = search(bundle, np.asarray(q, dtype="float32"), top_k=top_k)
    return [(h[1], h[2], h[3]) for h in hits]


def format_context_blocks(
    hits: list[tuple[float, str, dict[str, Any]]],
    *,
    prefix: str = "Retrieved excerpts",
    min_score: float = 0.0,
    max_context_chars: int = 12000,
) -> str:
    if max_context_chars <= 0:
        return f"{prefix}:\n(No context budget.)"
    filtered = [(s, t, m) for (s, t, m) in hits if float(s) >= float(min_score)]
    if not filtered:
        return f"{prefix}:\n(No indexed documents matched.)"
    blocks: list[str] = []
    used = 0
    shown = 0
    for i, (score, text, meta) in enumerate(filtered, 1):
        src = meta.get("source", "unknown")
        block = f"[{i}] (source: {src}, score={score:.3f})\n{text}"
        sep = "\n\n---\n\n" if blocks else ""
        next_len = len(sep) + len(block)
        if used + next_len > max_context_chars:
            break
        blocks.append(block)
        used += next_len
        shown += 1
    if not blocks:
        return f"{prefix}:\n(No retrieved chunks fit the context budget.)"
    suffix = ""
    if shown < len(filtered):
        suffix = f"\n\n(Showing {shown} of {len(filtered)} retrieved chunks; truncated to fit context budget.)"
    return f"{prefix}:\n" + ("\n\n---\n\n".join(blocks)) + suffix

