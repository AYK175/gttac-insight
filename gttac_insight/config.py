"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    llm_provider: Literal["anthropic", "ollama"]
    anthropic_api_key: Optional[str]
    anthropic_model: str
    ollama_base_url: str
    ollama_model: str
    query_timeout_ms: int
    max_rows: int
    rag_docs_dir: str
    rag_index_dir: str
    embedding_model: str
    rag_chunk_chars: int
    rag_chunk_overlap: int
    rag_min_score: float
    rag_max_context_chars: int
    rag_explain_top_k: int
    t2s_rag_top_k: int

    @classmethod
    def from_env(cls) -> "Settings":
        db = os.getenv("DATABASE_URL", "").strip()
        if not db:
            raise ValueError(
                "DATABASE_URL is required (e.g. postgresql://user:pass@host:5432/dbname)"
            )
        provider = (os.getenv("LLM_PROVIDER", "anthropic").strip().lower() or "anthropic")
        if provider not in ("anthropic", "ollama"):
            raise ValueError("LLM_PROVIDER must be 'anthropic' or 'ollama'")
        key = os.getenv("ANTHROPIC_API_KEY", "").strip() or None
        return cls(
            database_url=db,
            llm_provider=provider,  # type: ignore[arg-type]
            anthropic_api_key=key,
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            query_timeout_ms=int(os.getenv("QUERY_TIMEOUT_MS", "30000")),
            max_rows=int(os.getenv("MAX_ROWS", "5000")),
            rag_docs_dir=os.getenv("RAG_DOCS_DIR", "docs"),
            rag_index_dir=os.getenv("RAG_INDEX_DIR", ".rag_index"),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            rag_chunk_chars=int(os.getenv("RAG_CHUNK_CHARS", "1200")),
            rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200")),
            rag_min_score=float(os.getenv("RAG_MIN_SCORE", "0.0")),
            rag_max_context_chars=int(os.getenv("RAG_MAX_CONTEXT_CHARS", "12000")),
            rag_explain_top_k=int(os.getenv("RAG_EXPLAIN_TOP_K", "6")),
            t2s_rag_top_k=int(os.getenv("T2S_RAG_TOP_K", "6")),
        )

    def require_anthropic(self) -> str:
        if not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for text-to-SQL and RAG explanations"
            )
        return self.anthropic_api_key

    def require_llm(self) -> None:
        if self.llm_provider == "anthropic":
            self.require_anthropic()
        elif self.llm_provider == "ollama":
            if not (self.ollama_base_url or "").strip():
                raise ValueError("OLLAMA_BASE_URL is required when LLM_PROVIDER=ollama")
            if not (self.ollama_model or "").strip():
                raise ValueError("OLLAMA_MODEL is required when LLM_PROVIDER=ollama")


def get_settings() -> Settings:
    return Settings.from_env()
