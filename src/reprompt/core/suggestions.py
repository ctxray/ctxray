"""Command journey suggestions — guide users to the next useful action."""

from __future__ import annotations

import sys

FEEDBACK_URL = "https://github.com/reprompt-dev/reprompt/issues/new?template=feedback.yml"
FEEDBACK_COMMANDS_THRESHOLD = 5  # show feedback hint after 5 distinct commands used

SUGGESTIONS: dict[str, str] = {
    "scan": "reprompt report (see results) · reprompt insights (personal patterns)",
    "report": "reprompt insights (patterns) · reprompt distill --last (session review)",
    "score": 'reprompt compress "..." (optimize) · reprompt insights (all patterns)',
    "insights": (
        'reprompt template save "..." (reuse patterns) · reprompt distill --last (sessions)'
    ),
    "distill": (
        "reprompt agent (workflow analysis) · reprompt distill --export --copy (context recovery)"
    ),
    "agent": (
        "reprompt agent --loops-only (error loops) · reprompt privacy --deep (sensitive content)"
    ),
    "sessions": (
        "reprompt sessions --detail <id> (deep-dive) · reprompt agent (error loop analysis)"
    ),
    "repetition": (
        'reprompt template save "..." (reuse patterns) · reprompt insights (all patterns)'
    ),
    "template": "reprompt insights (see which patterns work best)",
    "lint": "reprompt init (generate .reprompt.toml) · reprompt rewrite (improve prompts)",
    "build": "reprompt rewrite (improve existing) · reprompt score (check any prompt)",
    "check": "reprompt build (construct from parts) · reprompt rewrite --diff (see changes)",
    "explain": "reprompt rewrite (auto-improve) · reprompt build (construct from parts)",
    "rewrite": "reprompt compress (reduce tokens) · reprompt score (verify improvement)",
    "projects": "reprompt sessions --detail <id> (deep-dive) · reprompt insights (patterns)",
    "patterns": "reprompt rewrite (auto-improve gaps) · reprompt insights (full analysis)",
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
        return "Feedback or ideas? reprompt feedback"
    return None
