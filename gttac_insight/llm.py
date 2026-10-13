"""LLM provider abstraction (Anthropic or Ollama)."""

from __future__ import annotations

from typing import Literal, Optional

import httpx

from gttac_insight.config import Settings


def _ollama_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def chat_completion(
    settings: Settings,
    *,
    system: Optional[str],
    user: str,
    max_tokens: int,
    json_mode: bool = False,
) -> str:
    settings.require_llm()

    if settings.llm_provider == "anthropic":
        import anthropic  # local import so Ollama users don't need it at runtime

        client = anthropic.Anthropic(api_key=settings.require_anthropic())
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": user}],
        )
        text = ""
        for block in msg.content:
            if hasattr(block, "text"):
                text += block.text
        return text

    # Ollama
    payload: dict = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": (
            ([{"role": "system", "content": system}] if system else [])
            + [{"role": "user", "content": user}]
        ),
        "options": {
            # Keep it deterministic for SQL generation.
            "temperature": 0.1,
            # Ask for enough room; Ollama models vary, but this helps.
            "num_predict": max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"
    url = _ollama_url(settings.ollama_base_url, "/api/chat")
    with httpx.Client(timeout=60) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    msg = data.get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise ValueError("Ollama response missing message.content")
    return content

