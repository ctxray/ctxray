"""Command journey suggestions — guide users to the next useful action."""

from __future__ import annotations

SUGGESTIONS: dict[str, str] = {
    "scan": "reprompt report (see results) · reprompt insights (personal patterns)",
    "report": "reprompt insights (patterns) · reprompt distill --last (session review)",
    "score": 'reprompt compress "..." (optimize) · reprompt insights (all patterns)',
    "insights": (
        'reprompt template save "..." (reuse patterns)'
        " · reprompt distill --last (sessions)"
    ),
    "distill": (
        "reprompt distill --export --copy (context recovery)"
        ' · reprompt compress "..." (shorten turns)'
    ),
    "template": "reprompt insights (see which patterns work best)",
}


def get_suggestion(command: str) -> str | None:
    """Return the suggestion line for a command, or None."""
    return SUGGESTIONS.get(command)
