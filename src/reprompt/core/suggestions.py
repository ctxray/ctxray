"""Command journey suggestions — guide users to the next useful action."""

from __future__ import annotations

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
    "rewrite": "reprompt compress (reduce tokens) · reprompt score (verify improvement)",
}


def get_suggestion(command: str) -> str | None:
    """Return the suggestion line for a command, or None."""
    return SUGGESTIONS.get(command)
