"""Shared prompt filtering logic for all adapters.

Filters out noise: short messages, CLI commands, system messages,
slash commands, and other non-prompt content.
"""

from __future__ import annotations

import re

# --- Minimum length ---
MIN_PROMPT_LENGTH = 10

# --- Exact matches to skip (acknowledgments, single-word replies) ---
SKIP_EXACT = {
    "好的",
    "OK",
    "ok",
    "Ok",
    "是的",
    "可以",
    "sure",
    "Sure",
    "yes",
    "Yes",
    "Done",
    "done",
    "Sent",
    "sent",
    "好",
    "对",
    "行",
    "嗯",
    "Tool loaded.",
    "1",
    "2",
    "3",
    "A",
    "B",
    "C",
    "D",
}

# --- Prefix patterns to skip ---
SKIP_PREFIXES = (
    "<",
    "/",  # slash commands (/help, /commit, /review, etc.)
    "Tool loaded",
    "Base directory for this skill",
    "This session is being continued from a previous conversation",
    "Summary:",
    "Continue the conversation from where it left off",
    "You are implementing Task",
    "You are reviewing whether",
    "Implement Task ",
    "Implement the following plan",
    "You are building ",
    "You are auditing ",
    "## Task:",
    "INFO:",
    "Find examples of ",
    "Review the code quality",
    "Review the entropy",
    "Migrate the ",
    "[Image: source:",
    # System/error messages
    "Unknown skill:",
    "Unknown command:",
    "Error:",
    "Warning:",
    "DEBUG:",
    "TRACE:",
    "Permission denied",
    "No such file",
    "Command not found",
)

# --- CLI tool commands (regex) ---
SKIP_CLI_RE = re.compile(
    r"^(claude|cursor|aider|copilot|cline|windsurf|continue|git|gh|npm|npx|pip|uv"
    r"|reprompt|make|cargo|docker|brew|apt|yum|sudo|ssh|scp|rsync|cd|ls|cat|pwd"
    r"|mkdir|rm|cp|mv|chmod|chown|echo|export|source|which|where|man)\b",
    re.IGNORECASE,
)

# --- Substrings that indicate system/compact noise ---
SKIP_CONTAINS = (
    "ran out of context",
    "<system-reminder>",
    "<command-name>",
    "Previous conversation summary",
    "\u23fa Bash(",
    "\n  \u23bf ",
    "PreToolUse:",
    "PostToolUse:",
    "hook blocking error",
    "hook success",
    "SessionStart:",
    "GITHUB_STEP_SUMMARY",
)


def should_keep_prompt(text: str) -> bool:
    """Filter out noise prompts — short messages, exact matches, prefixes, CLI commands."""
    text = text.strip()
    if len(text) < MIN_PROMPT_LENGTH:
        return False
    if text in SKIP_EXACT:
        return False
    if any(text.startswith(p) for p in SKIP_PREFIXES):
        return False
    if any(s in text for s in SKIP_CONTAINS):
        return False
    # Must contain at least one letter (Latin or CJK)
    if not re.search(r"[a-zA-Z\u4e00-\u9fff]", text):
        return False
    if SKIP_CLI_RE.match(text):
        return False
    return True
