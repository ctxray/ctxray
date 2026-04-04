"""Command journey suggestions — guide users to the next useful action."""

from __future__ import annotations

import sys

FEEDBACK_URL = "https://github.com/ctxray/ctxray/issues/new?template=feedback.yml"
FEEDBACK_COMMANDS_THRESHOLD = 5  # show feedback hint after 5 distinct commands used

SUGGESTIONS: dict[str, str] = {
    "scan": "ctxray report (see results) · ctxray insights (personal patterns)",
    "report": "ctxray insights (patterns) · ctxray distill --last (session review)",
    "score": 'ctxray compress "..." (optimize) · ctxray insights (all patterns)',
    "insights": ('ctxray template save "..." (reuse patterns) · ctxray distill --last (sessions)'),
    "distill": (
        "ctxray agent (workflow analysis) · ctxray distill --export --copy (context recovery)"
    ),
    "agent": (
        "ctxray agent --loops-only (error loops) · ctxray privacy --deep (sensitive content)"
    ),
    "sessions": ("ctxray sessions --detail <id> (deep-dive) · ctxray agent (error loop analysis)"),
    "repetition": ('ctxray template save "..." (reuse patterns) · ctxray insights (all patterns)'),
    "template": "ctxray insights (see which patterns work best)",
    "lint": "ctxray init (generate .ctxray.toml) · ctxray rewrite (improve prompts)",
    "build": "ctxray rewrite (improve existing) · ctxray score (check any prompt)",
    "check": "ctxray build (construct from parts) · ctxray rewrite --diff (see changes)",
    "explain": "ctxray rewrite (auto-improve) · ctxray build (construct from parts)",
    "rewrite": "ctxray compress (reduce tokens) · ctxray score (verify improvement)",
    "projects": "ctxray sessions --detail <id> (deep-dive) · ctxray insights (patterns)",
    "patterns": "ctxray rewrite (auto-improve gaps) · ctxray insights (full analysis)",
}


def get_suggestion(command: str) -> str | None:
    """Return the suggestion line for a command, or None."""
    return SUGGESTIONS.get(command)


def maybe_feedback_hint(db: object, command: str) -> str | None:
    """Return a one-time feedback hint if the user has used enough commands.

    Returns the hint string (replacing the journey hint) exactly once,
    then never again. Returns None in non-TTY / CI / JSON contexts.
    """
    if not sys.stdout.isatty():
        return None
    if hasattr(db, "get_setting") and db.get_setting("feedback_hint_shown"):  # type: ignore[union-attr]
        return None
    # Track distinct commands used
    used_raw = db.get_setting("commands_used") if hasattr(db, "get_setting") else None  # type: ignore[union-attr]
    used: set[str] = set(used_raw.split(",")) if used_raw else set()
    used.add(command)
    if hasattr(db, "set_setting"):
        db.set_setting("commands_used", ",".join(sorted(used)))  # type: ignore[union-attr]
    if len(used) >= FEEDBACK_COMMANDS_THRESHOLD:
        if hasattr(db, "set_setting"):
            db.set_setting("feedback_hint_shown", "1")  # type: ignore[union-attr]
        return "Feedback or ideas? ctxray feedback"
    return None
