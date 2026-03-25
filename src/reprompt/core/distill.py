"""Conversation distillation engine.

Scores conversation turns by importance using 6 weighted signals,
filters by threshold, and produces distilled output.

Signals (user turns):
  - position (0.15): first=1.0, last=0.8, middle=recency-based
  - length (0.15): normalized by median
  - tool_trigger (0.20): tool_calls on following assistant turn
  - error_recovery (0.15): 1.0 if previous assistant had error
  - semantic_shift (0.20): TF-IDF cosine distance from previous user turn
  - uniqueness (0.15): 1.0 - max similarity to earlier turns

Assistant turns get derived score = avg of adjacent user turns.
"""

from __future__ import annotations

import re
import statistics

from reprompt.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)

# Signal weights
DEFAULT_WEIGHTS: dict[str, float] = {
    "position": 0.15,
    "length": 0.15,
    "tool_trigger": 0.20,
    "error_recovery": 0.15,
    "semantic_shift": 0.20,
    "uniqueness": 0.15,
}

# Keep module-level aliases for backward compatibility with internal references
W_POSITION = DEFAULT_WEIGHTS["position"]
W_LENGTH = DEFAULT_WEIGHTS["length"]
W_TOOL_TRIGGER = DEFAULT_WEIGHTS["tool_trigger"]
W_ERROR_RECOVERY = DEFAULT_WEIGHTS["error_recovery"]
W_SEMANTIC_SHIFT = DEFAULT_WEIGHTS["semantic_shift"]
W_UNIQUENESS = DEFAULT_WEIGHTS["uniqueness"]

# Patterns for false-positive suppression in position and error_recovery signals
GREETING_PATTERNS = re.compile(
    r"^(hey|hi|hello|sup|yo)\b"
    r"|^(你好|嗨|哈喽)"
    r"|^(good morning|good afternoon|good evening)",
    re.IGNORECASE,
)

SIGNOFF_PATTERNS = re.compile(
    r"^(thanks|thank you|thx|ty)\b"
    r"|^(bye|goodbye|see you|cya)\b"
    r"|^(谢谢|拜拜|再见|辛苦了|收工)"
    r"|^(lgtm|looks good|perfect|great)\s*[!.]*$",
    re.IGNORECASE,
)

LOW_INFO_RECOVERY = re.compile(
    r"^(ok|okay|sure|yes|yeah|yep|right)\b"
    r"|^(try again|retry|再试|继续|好的|可以|行)\s*$"
    r"|^(do it|go ahead|proceed)\s*$",
    re.IGNORECASE,
)


def _score_position(turn_idx: int, total_user_turns: int) -> float:
    """Score based on position: first=1.0, last=0.8, middle=recency-based."""
    if total_user_turns <= 1:
        return 1.0
    if turn_idx == 0:
        return 1.0
    last_idx = total_user_turns - 1
    if turn_idx == last_idx:
        return 0.8
    recency = turn_idx / last_idx
    return 0.3 + 0.2 * recency


def _score_position_with_text(turn_idx: int, total_user_turns: int, text: str) -> float:
    """Position score that skips greetings (first turn) and sign-offs (last turn)."""
    if total_user_turns <= 1:
        return 1.0
    last_idx = total_user_turns - 1
    stripped = text.strip()
    if turn_idx == 0 and GREETING_PATTERNS.match(stripped):
        return 0.0
    if turn_idx == last_idx and SIGNOFF_PATTERNS.match(stripped):
        return 0.0
    return _score_position(turn_idx, total_user_turns)


def _score_length(char_count: int, median_length: float, role: str = "user") -> float:
    """Score based on length relative to median. Only scores user turns."""
    if role != "user":
        return 0.0
    if median_length <= 0:
        return 1.0
    return min(char_count / median_length, 1.0)


def _score_tool_trigger(tool_calls: int) -> float:
    """Score based on how many tool calls the assistant made. 5+ = 1.0."""
    return min(tool_calls / 5, 1.0)


def _score_error_recovery(prev_assistant_has_error: bool) -> float:
    """1.0 if previous assistant turn had an error, else 0.0."""
    return 1.0 if prev_assistant_has_error else 0.0


def _score_error_recovery_with_text(prev_assistant_has_error: bool, text: str) -> float:
    """Error recovery score that filters low-information responses."""
    if not prev_assistant_has_error:
        return 0.0
    stripped = text.strip()
    if len(stripped) < 20 and LOW_INFO_RECOVERY.match(stripped):
        return 0.0
    return 1.0


def _compute_semantic_signals(
    user_texts: list[str],
) -> tuple[list[float], list[float]]:
    """Compute semantic_shift and uniqueness for all user turns.

    Returns:
        (shifts, uniqueness_scores) - both lists of floats, same length as user_texts.
    """
    n = len(user_texts)
    if n == 0:
        return [], []

    shifts: list[float] = [0.5]
    uniqueness: list[float] = [1.0]

    if n == 1:
        return shifts, uniqueness

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(user_texts)
        sim_matrix = cosine_similarity(tfidf_matrix)

        for i in range(1, n):
            shift = 1.0 - sim_matrix[i, i - 1]
            shifts.append(float(shift))
            max_sim = max(sim_matrix[i, j] for j in range(i))
            uniqueness.append(float(1.0 - max_sim))

    except (ValueError, Exception):
        shifts = [0.5] * n
        uniqueness = [1.0] * n

    return shifts, uniqueness


def _get_next_assistant_turn(
    turns: list[ConversationTurn], user_turn_index: int
) -> ConversationTurn | None:
    """Find the assistant turn immediately following a user turn by turn_index."""
    for i, t in enumerate(turns):
        if t.turn_index == user_turn_index:
            if i + 1 < len(turns) and turns[i + 1].role == "assistant":
                return turns[i + 1]
            break
    return None


def _get_prev_assistant_turn(
    turns: list[ConversationTurn], user_turn_index: int
) -> ConversationTurn | None:
    """Find the assistant turn immediately preceding a user turn by turn_index."""
    for i, t in enumerate(turns):
        if t.turn_index == user_turn_index:
            if i - 1 >= 0 and turns[i - 1].role == "assistant":
                return turns[i - 1]
            break
    return None


def _extract_files_changed(turns: list[ConversationTurn]) -> list[str]:
    """Extract and deduplicate file paths from assistant tool_use_paths."""
    paths: set[str] = set()
    for t in turns:
        for p in t.tool_use_paths:
            paths.add(p)
    return sorted(paths)


def distill_conversation(
    conversation: Conversation,
    threshold: float = 0.3,
    weights: dict[str, float] | None = None,
) -> DistillResult:
    """Score and filter conversation turns by importance.

    Each user turn is scored using 6 weighted signals. Assistant turns get
    a derived score (average of adjacent user turns). Turns below the
    threshold are filtered out.

    Args:
        conversation: The conversation to distill.
        threshold: Minimum importance score to keep a turn (0.0 - 1.0).
        weights: Optional signal weight overrides. Keys must be signal names
            (position, length, tool_trigger, error_recovery, semantic_shift,
            uniqueness). Missing keys fall back to DEFAULT_WEIGHTS.

    Returns:
        DistillResult with scored turns, filtered turns, and statistics.
    """
    turns = conversation.turns
    if not turns:
        return DistillResult(
            conversation=conversation,
            filtered_turns=[],
            threshold=threshold,
            stats=DistillStats(),
        )

    user_turns = [t for t in turns if t.role == "user"]
    n_users = len(user_turns)

    if n_users == 0:
        return DistillResult(
            conversation=conversation,
            filtered_turns=[],
            threshold=threshold,
            stats=DistillStats(total_turns=len(turns)),
        )

    # Resolve effective weights
    effective_weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    # Auto-detect session type and apply type-specific weights (only if no manual override)
    from reprompt.core.session_type import detect_session_type, get_weights_for_type

    detected_type = detect_session_type(conversation)
    if weights is None and detected_type is not None:
        effective_weights = get_weights_for_type(detected_type)

    # Store detected type on conversation for display
    conversation._detected_type = detected_type  # type: ignore[attr-defined]

    # Precompute median length and semantic signals
    lengths = [len(t.text) for t in user_turns]
    median_length = float(statistics.median(lengths)) if lengths else 0.0
    user_texts = [t.text for t in user_turns]
    shifts, uniqueness_scores = _compute_semantic_signals(user_texts)

    # Score each user turn
    for user_idx, user_turn in enumerate(user_turns):
        pos_score = _score_position_with_text(user_idx, n_users, user_turn.text)
        len_score = _score_length(len(user_turn.text), median_length, role="user")

        next_asst = _get_next_assistant_turn(turns, user_turn.turn_index)
        tool_score = _score_tool_trigger(next_asst.tool_calls if next_asst else 0)

        prev_asst = _get_prev_assistant_turn(turns, user_turn.turn_index)
        error_score = _score_error_recovery_with_text(
            prev_asst.has_error if prev_asst else False, user_turn.text
        )

        shift_score = shifts[user_idx] if user_idx < len(shifts) else 0.5
        unique_score = uniqueness_scores[user_idx] if user_idx < len(uniqueness_scores) else 1.0

        # Store per-signal scores for export classification
        user_turn.signal_scores = {
            "position": pos_score,
            "length": len_score,
            "tool_trigger": tool_score,
            "error_recovery": error_score,
            "semantic_shift": shift_score,
            "uniqueness": unique_score,
        }

        importance = (
            effective_weights["position"] * pos_score
            + effective_weights["length"] * len_score
            + effective_weights["tool_trigger"] * tool_score
            + effective_weights["error_recovery"] * error_score
            + effective_weights["semantic_shift"] * shift_score
            + effective_weights["uniqueness"] * unique_score
        )

        # Single-turn guarantee: sole user turn always gets max importance
        if n_users == 1:
            importance = 1.0

        user_turn.importance = importance

    # Score assistant turns (derived: avg of adjacent user turns)
    for turn in turns:
        if turn.role != "assistant":
            continue
        adjacent_scores: list[float] = []
        # Find preceding user turn
        for t in reversed(turns):
            if t.turn_index < turn.turn_index and t.role == "user":
                adjacent_scores.append(t.importance)
                break
        # Find following user turn
        for t in turns:
            if t.turn_index > turn.turn_index and t.role == "user":
                adjacent_scores.append(t.importance)
                break
        turn.importance = sum(adjacent_scores) / len(adjacent_scores) if adjacent_scores else 0.0

    # Filter: keep user turns above threshold + their paired assistant turns
    filtered: list[ConversationTurn] = []
    for turn in turns:
        if turn.role == "user" and turn.importance >= threshold:
            filtered.append(turn)
            next_asst = _get_next_assistant_turn(turns, turn.turn_index)
            if next_asst:
                filtered.append(next_asst)

    filtered.sort(key=lambda t: t.turn_index)

    # Extract files changed from assistant turns
    files_changed = _extract_files_changed([t for t in turns if t.role == "assistant"])

    # Build stats
    stats = DistillStats(
        total_turns=len(turns),
        kept_turns=len(filtered),
        retention_ratio=len(filtered) / len(turns) if turns else 0.0,
        total_duration_seconds=conversation.duration_seconds or 0,
    )

    return DistillResult(
        conversation=conversation,
        filtered_turns=filtered,
        threshold=threshold,
        files_changed=files_changed,
        stats=stats,
    )


def generate_summary(result: DistillResult) -> str:
    """Generate a rule-based text summary of the distilled conversation.

    Structure:
      1. Description (first user turn, compressed)
      2. Key decisions (top 5 user turns by importance, compressed)
      3. Files changed
      4. Stats line
    """
    from reprompt.core.compress import compress_text

    lines: list[str] = []
    conv = result.conversation
    user_turns = [t for t in conv.turns if t.role == "user"]

    # Description
    if user_turns:
        first_text = compress_text(user_turns[0].text).compressed
        project_str = f" ({conv.project})" if conv.project else ""
        lines.append(f"Session{project_str}: {first_text}")
    else:
        lines.append("Empty session.")

    lines.append("")

    # Key decisions (top 5 by importance)
    if user_turns:
        sorted_turns = sorted(user_turns, key=lambda t: t.importance, reverse=True)
        top_turns = sorted_turns[:5]
        lines.append("Key decisions:")
        for turn in top_turns:
            compressed = compress_text(turn.text).compressed
            truncated = compressed[:120] + "..." if len(compressed) > 120 else compressed
            lines.append(f"  - {truncated}")
        lines.append("")

    # Files changed
    if result.files_changed:
        files_str = ", ".join(result.files_changed[:10])
        lines.append(f"Files changed: {files_str}")
        lines.append("")

    # Stats
    duration_str = ""
    if result.stats.total_duration_seconds > 0:
        mins = result.stats.total_duration_seconds // 60
        duration_str = f" | {mins}min"
    lines.append(
        f"{result.stats.total_turns} turns → {result.stats.kept_turns} key turns"
        f"{duration_str} | {conv.source}"
    )

    return "\n".join(lines)
