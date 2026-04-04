"""Token cost estimation for prompts.

Estimates token count and API cost based on the prompt source (AI tool).
Uses a word-count heuristic (no external dependencies) with locale-aware
adjustments for CJK text.

Pricing is input-only (prompts are inputs to the model).
"""

from __future__ import annotations

import re

# Input pricing per 1M tokens (USD), as of March 2026
# Only the most common model per source is listed
MODEL_PRICING: dict[str, float] = {
    "claude-sonnet": 3.00,
    "claude-haiku": 0.80,
    "claude-opus": 15.00,
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "gemini-2.0-flash": 0.10,
    "gemini-2.5-pro": 1.25,
    "deepseek-v3": 0.27,
}

# Map ctxray adapter source names to their default model
SOURCE_TO_MODEL: dict[str, str] = {
    "claude-code": "claude-sonnet",
    "cursor": "gpt-4o",
    "chatgpt-export": "gpt-4o",
    "chatgpt": "gpt-4o",
    "aider": "claude-sonnet",
    "gemini": "gemini-2.0-flash",
    "cline": "claude-sonnet",
    "openclaw": "claude-sonnet",
    "codex": "gpt-4o",
    "claude-chat": "claude-sonnet",
    "extension": "gpt-4o",
    "manual": "claude-sonnet",
    "mcp": "claude-sonnet",
}

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_WHITESPACE_PUNCT_RE = re.compile(r"[\s\u3000-\u303f\uff00-\uffef.,;:!?\"'()\[\]{}]+")


def estimate_tokens(text: str, locale: str = "en") -> int:
    """Estimate token count using locale-aware heuristic.

    English: ~1.3 tokens per word (BPE splits some words).
    CJK: ~1.5 tokens per character (each char is typically 1-2 tokens).
    """
    if not text or not text.strip():
        return 0

    if locale in ("zh", "ja", "ko"):
        cleaned = _WHITESPACE_PUNCT_RE.sub("", text)
        return max(1, int(len(cleaned) * 1.5))

    # For mixed text, check CJK ratio
    cjk_chars = len(_CJK_RE.findall(text))
    total_chars = len(text.strip())
    if total_chars > 0 and cjk_chars / total_chars > 0.3:
        cleaned = _WHITESPACE_PUNCT_RE.sub("", text)
        return max(1, int(len(cleaned) * 1.5))

    # English-dominant
    words = len(text.split())
    return max(1, int(words * 1.3))


def estimate_cost(token_count: int, source: str = "claude-code") -> float:
    """Estimate API input cost in USD for a given token count and source.

    Returns cost in USD (e.g., 0.000045).
    """
    model = SOURCE_TO_MODEL.get(source, "claude-sonnet")
    rate = MODEL_PRICING.get(model, 3.00)
    return token_count / 1_000_000 * rate


def format_cost(cost_usd: float) -> str:
    """Format cost for display. Uses appropriate precision."""
    if cost_usd == 0:
        return "$0.00"
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    if cost_usd < 1.0:
        return f"${cost_usd:.3f}"
    return f"${cost_usd:.2f}"


def model_for_source(source: str) -> str:
    """Return the default model name for a given adapter source."""
    return SOURCE_TO_MODEL.get(source, "claude-sonnet")
