"""Build FAISS index from RAG_DOCS_DIR: python -m gttac_insight.rag"""

from __future__ import annotations

from gttac_insight.config import get_settings
from gttac_insight.rag.ingest import ingest_and_save

if __name__ == "__main__":
    ingest_and_save(get_settings())
