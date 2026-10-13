"""Ingest text/markdown files into a FAISS index."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from gttac_insight.config import Settings
from gttac_insight.rag.index import IndexBundle, save_bundle


def _chunk_text(text: str, max_chars: int, overlap: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= max_chars:
        overlap = max(0, max_chars // 6)
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _collect_files(docs_dir: str) -> List[Path]:
    root = Path(docs_dir)
    if not root.is_dir():
        return []
    out: List[Path] = []
    for ext in ("*.md", "*.txt", "*.markdown", "*.pdf"):
        out.extend(root.rglob(ext))
    return sorted(set(out))


def _read_pdf_text(path: Path) -> str:
    """Extract text from a PDF (text-based PDFs only; scanned PDFs need OCR)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(t)
    return "\n\n".join(parts).strip()


def build_index(settings: Settings, docs_dir: Optional[str] = None) -> IndexBundle:
    ddir = docs_dir or settings.rag_docs_dir
    model = SentenceTransformer(settings.embedding_model)
    dim = model.get_sentence_embedding_dimension()
    chunks: List[str] = []
    metas: List[dict] = []
    for path in _collect_files(ddir):
        try:
            if path.suffix.lower() == ".pdf":
                raw = _read_pdf_text(path)
            else:
                raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        except Exception:
            continue
        if not raw.strip():
            continue
        for i, ch in enumerate(
            _chunk_text(
                raw,
                max_chars=settings.rag_chunk_chars,
                overlap=settings.rag_chunk_overlap,
            )
        ):
            chunks.append(ch)
            metas.append(
                {
                    "source": str(path),
                    "chunk_index": i,
                    "file_type": path.suffix.lower().lstrip("."),
                }
            )
    if not chunks:
        raise ValueError(f"No document chunks found under {ddir}")
    emb = model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    emb = np.asarray(emb, dtype="float32")
    index = faiss.IndexFlatIP(dim)
    index.add(emb)
    return IndexBundle(index=index, chunks=chunks, metas=metas, embedding_dim=dim)


def ingest_and_save(settings: Settings, docs_dir: Optional[str] = None) -> None:
    bundle = build_index(settings, docs_dir=docs_dir)
    save_bundle(bundle, settings.rag_index_dir)
