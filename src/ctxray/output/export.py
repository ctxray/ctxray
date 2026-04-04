"""Export formatter -- produces markdown context recovery documents.

Generates a structured markdown document from a DistillResult, optimized for
re-injection into a new AI session.  Section ordering follows Lost-in-the-Middle
research (actionable context at top and bottom, reference material in the middle).
"""

from __future__ import annotations

from ctxray.core.compress import compress_text
from ctxray.core.conversation import ConversationTurn, DistillResult

# Forward-looking keywords for Resume section detection (en + zh)
_FORWARD_KEYWORDS = [
    "next",
    "todo",
    "now let's",
    "then ",
    "after that",
    "move on",
    "\u63a5\u4e0b\u6765",  # 接下来
    "\u7136\u540e",  # 然后
    "\u4e0b\u4e00\u6b65",  # 下一步
    "\u4e4b\u540e",  # 之后
    "\u5f85\u529e",  # 待办
]


def _truncate(text: str, max_chars: int) -> str:
    """Compress and truncate text to *max_chars*."""
    compressed = compress_text(text).compressed
    if len(compressed) > max_chars:
        return compressed[:max_chars] + "..."
    return compressed


def _has_forward_intent(text: str) -> bool:
    """Check if *text* contains forward-looking keywords."""
    lower = text.lower()
    return any(kw in lower for kw in _FORWARD_KEYWORDS)


def _summarize_assistant(turn: ConversationTurn) -> str:
    """Produce a short summary of an assistant turn for ``--full`` mode."""
    if turn.tool_calls > 0 and len(turn.text.strip()) < 200:
        files = len(turn.tool_use_paths)
        return f"{turn.tool_calls} tool calls, {files} files changed"
    # First sentence
    for sep in [". ", ".\n", "\n"]:
        if sep in turn.text:
            first = turn.text.split(sep, 1)[0]
            return first[:150] + "..." if len(first) > 150 else first
    return turn.text[:150] + "..." if len(turn.text) > 150 else turn.text


def _classify_turn(turn: ConversationTurn) -> str:
    """Classify a turn as ``'decision'`` or ``'action'`` by dominant signal."""
    scores = turn.signal_scores
    if not scores:
        return "decision"
    shift = scores.get("semantic_shift", 0.0)
    tool = scores.get("tool_trigger", 0.0)
    return "decision" if shift >= tool else "action"


def _find_next_assistant(
    turns: list[ConversationTurn],
    user_turn_index: int,
) -> ConversationTurn | None:
    """Find the assistant turn immediately following a user turn.

    Only returns the turn at ``user_turn_index + 1`` if it is an assistant turn,
    matching the semantics of ``distill.py``'s ``_get_next_assistant_turn()``.
    """
    for t in turns:
        if t.turn_index == user_turn_index + 1 and t.role == "assistant":
            return t
    return None


def generate_export(result: DistillResult, *, full: bool = False) -> str:
    """Generate a markdown context recovery document from a *DistillResult*.

    Parameters
    ----------
    result:
        The distilled conversation result.
    full:
        If ``True``, include assistant response summaries.

    Returns
    -------
    str
        Markdown string optimized for AI session re-injection.
    """
    conv = result.conversation
    all_user_turns = [t for t in conv.turns if t.role == "user"]
    lines: list[str] = []

    # --- Header -----------------------------------------------------------
    project = conv.project or "unknown"
    lines.append(f"# Session Context: {project}")
    lines.append("")

    date_str = ""
    if conv.start_time:
        date_str = conv.start_time[:10]  # YYYY-MM-DD

    duration_str = ""
    if result.stats.total_duration_seconds > 0:
        mins = result.stats.total_duration_seconds // 60
        duration_str = f" | **Duration:** {mins}min"

    lines.append(f"**Source:** {conv.source} | **Date:** {date_str}{duration_str}")

    # Token count placeholder -- filled after the full document is assembled
    token_placeholder = "TOKEN_PLACEHOLDER"
    lines.append(
        f"**Turns:** {result.stats.total_turns} \u2192 {result.stats.kept_turns} key turns"
        f" | **~{token_placeholder} tokens**"
    )
    lines.append("")

    # --- Identify special turns -------------------------------------------
    goal_turn = all_user_turns[0] if all_user_turns else None

    important_user_turns = [t for t in all_user_turns if t.importance >= result.threshold]
    current_state_turn = (
        important_user_turns[-1]
        if important_user_turns
        else (all_user_turns[-1] if all_user_turns else None)
    )
    # Don't duplicate Goal as Current State
    if current_state_turn and goal_turn and current_state_turn.turn_index == goal_turn.turn_index:
        current_state_turn = None

    resume_turn: ConversationTurn | None = None
    candidates = all_user_turns[-3:] if len(all_user_turns) >= 3 else all_user_turns
    for t in reversed(candidates):
        if _has_forward_intent(t.text):
            resume_turn = t
            break

    excluded_indices: set[int] = set()
    if goal_turn:
        excluded_indices.add(goal_turn.turn_index)
    if current_state_turn:
        excluded_indices.add(current_state_turn.turn_index)
    if resume_turn:
        excluded_indices.add(resume_turn.turn_index)

    # --- Handle empty filtered_turns fallback -----------------------------
    if not result.filtered_turns and all_user_turns:
        lines.append("## Goal")
        lines.append("")
        lines.append(_truncate(all_user_turns[0].text, 200))
        lines.append("")
        if len(all_user_turns) > 1:
            lines.append("## Current State")
            lines.append("")
            lines.append(_truncate(all_user_turns[-1].text, 200))
            lines.append("")
        lines.append(
            f"*(No turns above threshold {result.threshold}. Showing first and last turns.)*"
        )
        lines.append("")
        output = "\n".join(lines)
        token_est = len(output) // 4
        return output.replace(token_placeholder, str(token_est))

    # --- Goal -------------------------------------------------------------
    if goal_turn:
        lines.append("## Goal")
        lines.append("")
        lines.append(_truncate(goal_turn.text, 200))
        if full:
            asst = _find_next_assistant(conv.turns, goal_turn.turn_index)
            if asst:
                lines.append(f"\n**Result:** {_summarize_assistant(asst)}")
        lines.append("")

    # --- Current State ----------------------------------------------------
    if current_state_turn:
        lines.append("## Current State")
        lines.append("")
        lines.append(_truncate(current_state_turn.text, 200))
        if full:
            asst = _find_next_assistant(conv.turns, current_state_turn.turn_index)
            if asst:
                lines.append(f"\n**Result:** {_summarize_assistant(asst)}")
        lines.append("")

    # --- Classify remaining turns -----------------------------------------
    remaining_user = [
        t
        for t in all_user_turns
        if t.turn_index not in excluded_indices and t.importance >= result.threshold
    ]

    decisions = sorted(
        [t for t in remaining_user if _classify_turn(t) == "decision"],
        key=lambda t: t.signal_scores.get("semantic_shift", 0.0),
        reverse=True,
    )[:5]

    decision_indices = {t.turn_index for t in decisions}
    actions = sorted(
        [
            t
            for t in remaining_user
            if t.turn_index not in decision_indices and _classify_turn(t) == "action"
        ],
        key=lambda t: t.signal_scores.get("tool_trigger", 0.0),
        reverse=True,
    )[:5]

    # --- Key Decisions ----------------------------------------------------
    if decisions:
        lines.append("## Key Decisions")
        lines.append("")
        for i, turn in enumerate(decisions, 1):
            text = _truncate(turn.text, 150)
            if full:
                asst = _find_next_assistant(conv.turns, turn.turn_index)
                if asst:
                    lines.append(f"{i}. **User:** {text}")
                    lines.append(f"   **Result:** {_summarize_assistant(asst)}")
                else:
                    lines.append(f"{i}. {text}")
            else:
                lines.append(f"{i}. {text}")
        lines.append("")

    # --- What Was Done ----------------------------------------------------
    if actions:
        lines.append("## What Was Done")
        lines.append("")
        for turn in actions:
            text = _truncate(turn.text, 150)
            if full:
                asst = _find_next_assistant(conv.turns, turn.turn_index)
                if asst:
                    lines.append(f"- **User:** {text}")
                    lines.append(f"  **Result:** {_summarize_assistant(asst)}")
                else:
                    lines.append(f"- {text}")
            else:
                lines.append(f"- {text}")
        lines.append("")

    # --- Files Changed ----------------------------------------------------
    if result.files_changed:
        lines.append("## Files Changed")
        lines.append("")
        capped = result.files_changed[:10]
        lines.append(", ".join(f"`{f}`" for f in capped))
        lines.append("")

    # --- Resume -----------------------------------------------------------
    if resume_turn:
        lines.append("## Resume")
        lines.append("")
        lines.append(_truncate(resume_turn.text, 200))
        lines.append("")

    # --- Finalize with token estimate -------------------------------------
    output = "\n".join(lines)
    token_est = len(output) // 4
    output = output.replace(token_placeholder, str(token_est))
    return output
