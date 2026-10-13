"""FAISS index persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

import faiss
import numpy as np


@dataclass
class IndexBundle:
    index: faiss.Index
    chunks: List[str]
    metas: List[dict[str, Any]]
    embedding_dim: int


def _paths(index_dir: str) -> Tuple[Path, Path, Path]:
    base = Path(index_dir)
    return base / "faiss.index", base / "chunks.jsonl", base / "meta.json"


def save_bundle(bundle: IndexBundle, index_dir: str) -> None:
    os.makedirs(index_dir, exist_ok=True)
    idx_path, chunks_path, meta_path = _paths(index_dir)
    faiss.write_index(bundle.index, str(idx_path))
    with open(chunks_path, "w", encoding="utf-8") as f:
        for line in bundle.chunks:
            f.write(json.dumps({"text": line}, ensure_ascii=False) + "\n")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metas": bundle.metas, "embedding_dim": bundle.embedding_dim},
            f,
            ensure_ascii=False,
        )


def load_bundle(index_dir: str) -> IndexBundle:
    idx_path, chunks_path, meta_path = _paths(index_dir)
    if not idx_path.is_file() or not chunks_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError(f"RAG index not found under {index_dir}")
    index = faiss.read_index(str(idx_path))
    chunks: List[str] = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line)["text"])
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    metas = meta["metas"]
    dim = int(meta["embedding_dim"])
    return IndexBundle(index=index, chunks=chunks, metas=metas, embedding_dim=dim)


def search(
    bundle: IndexBundle,
    query_vector: np.ndarray,
    top_k: int = 5,
) -> List[Tuple[int, float, str, dict[str, Any]]]:
    """Returns list of (idx, score, text, meta)."""
    q = query_vector.astype("float32").reshape(1, -1)
    faiss.normalize_L2(q)
    scores, indices = bundle.index.search(q, min(top_k, len(bundle.chunks)))
    out: List[Tuple[int, float, str, dict[str, Any]]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        out.append(
            (int(idx), float(score), bundle.chunks[idx], bundle.metas[idx])
        )
    return out
