"""Prompt effectiveness scoring based on session-level signals."""

from __future__ import annotations

from reprompt.core.session_meta import SessionMeta

# Error indicators in assistant messages
ERROR_PATTERNS = (
    "error",
    "Error",
    "ERROR",
    "traceback",
    "Traceback",
    "failed",
    "Failed",
    "FAILED",
    "exception",
    "Exception",
)


def compute_effectiveness(meta: SessionMeta, prompt_specificity: float = 0.5) -> float:
    """Return effectiveness score in [0.0, 1.0].

    Heuristic weights:
    - Clean exit (no trailing errors): 0.30
    - Reasonable duration (10min - 2h): 0.15
    - Tool calls > 0: 0.10
    - Low error-to-tool ratio: 0.25
    - Prompt specificity: 0.20
    """
    score = 0.0

    # Clean exit
    if meta.final_status == "success":
        score += 0.30
    elif meta.final_status == "unknown":
        score += 0.15

    # Duration
    if 600 <= meta.duration_seconds <= 7200:
        score += 0.15
    elif meta.duration_seconds > 7200:
        score += 0.05

    # Tool calls exist
    if meta.tool_call_count > 0:
        score += 0.10

    # Error ratio
    if meta.tool_call_count > 0:
        error_ratio = meta.error_count / meta.tool_call_count
        score += 0.25 * max(0.0, 1.0 - error_ratio * 2)

    # Specificity
    score += 0.20 * min(prompt_specificity, 1.0)

    return round(min(score, 1.0), 2)


def detect_final_status(entries: list[dict[str, object]]) -> str:
    """Check last 3 assistant messages for error indicators.

    Supports two entry formats:
    - Message-wrapped (Claude Code): ``{"message": {"role": "assistant", "content": ...}}``
    - Top-level (OpenClaw, Gemini, etc.): ``{"role": "assistant", "content": ...}``
    """
    assistant_msgs: list[str] = []
    for entry in entries[-20:]:
        # Try message-wrapped format (Claude Code)
        msg = entry.get("message", {})
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
        # Also try top-level format (OpenClaw, Gemini, etc.)
        elif entry.get("role") == "assistant":
            content = entry.get("content", "")
        else:
            continue

        if isinstance(content, list):
            parts = [
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            text = " ".join(parts)
        else:
            text = str(content)
        assistant_msgs.append(text)

    last_three = assistant_msgs[-3:]
    for text in last_three:
        if any(p in text for p in ERROR_PATTERNS):
            return "error"
    return "success"


def effectiveness_stars(score: float) -> str:
    """Convert 0.0-1.0 score to star rating string."""
    filled = round(score * 5)
    return "\u2605" * filled + "\u2606" * (5 - filled)
