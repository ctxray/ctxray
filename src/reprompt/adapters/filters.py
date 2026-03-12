"""Shared prompt filtering logic for all adapters.

Filters out noise: short messages, CLI commands, system messages,
slash commands, tool invocations, and other non-prompt content.

Covers: Claude Code, Cursor, Aider, Gemini CLI, Cline, OpenClaw,
GitHub Copilot Chat, Continue.dev, Windsurf.
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
    "/",  # slash commands from all tools
    "!",  # Gemini CLI shell escape prefix
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
    "[ERROR]",
    # Aider status messages
    "Aider v",
    "Main model:",
    "Weak model:",
    "Editor model:",
    "Git repo:",
    "Repo-map:",
    "Tokens:",
    # Gemini CLI status
    "Gemini CLI v",
    "Using model:",
    "Tools available:",
    "MCP servers:",
    "Session duration:",
)

# --- CLI tool commands (regex) ---
# Matches lines that start with a known CLI tool name.
SKIP_CLI_RE = re.compile(
    r"^(claude|cursor|aider|copilot|cline|windsurf|continue|cn"
    r"|git|gh|npm|npx|pip|uv|pipx|pipenv|poetry|pdm|conda"
    r"|reprompt|make|cargo|docker|docker-compose|podman"
    r"|brew|apt|yum|dnf|pacman|sudo"
    r"|ssh|scp|rsync|wget|curl"
    r"|cd|ls|cat|pwd|mkdir|rm|cp|mv|chmod|chown"
    r"|echo|export|source|which|where|man|env"
    r"|python|python3|node|ruby|go|java|rustc|gcc|clang)\b",
    re.IGNORECASE,
)

# --- Aider file management patterns ---
_AIDER_FILE_RE = re.compile(r"^(Added |Removed ).+ (to|from) the chat\.$")

# --- Aider commit output ---
_AIDER_COMMIT_RE = re.compile(r"^Commit [a-f0-9]+ ")

# --- Cline tool invocation XML blocks ---
_CLINE_TOOL_RE = re.compile(
    r"<(write_to_file|read_file|replace_in_file|search_files|list_files"
    r"|list_code_definition_names|execute_command|browser_action"
    r"|use_mcp_tool|access_mcp_resource|ask_followup_question"
    r"|attempt_completion|plan_mode_respond)\b"
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
    # Cline system error
    "You did not use a tool in your previous response",
    # Skill/workflow invocations (meta-commands, not domain prompts)
    "superpowers:",
    "feature-dev:",
    "code-simplifier:",
    "claude-md-management:",
)


def should_keep_prompt(text: str) -> bool:
    """Filter out noise prompts — short messages, exact matches, prefixes, CLI commands.

    This is the shared filter used by all adapters. It catches:
    - Short/empty messages
    - Acknowledgments (ok, yes, done, etc.)
    - Slash commands from all tools (/help, /commit, /add, etc.)
    - CLI tool invocations (git, npm, docker, etc.)
    - System status messages (Aider banners, Gemini stats, etc.)
    - Tool invocation XML (Cline tool blocks)
    - Gemini shell escapes (!command)
    - System noise substrings
    """
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
    # Aider-specific patterns
    if _AIDER_FILE_RE.match(text):
        return False
    if _AIDER_COMMIT_RE.match(text):
        return False
    # Cline tool invocation blocks
    if _CLINE_TOOL_RE.search(text):
        return False
    return True
