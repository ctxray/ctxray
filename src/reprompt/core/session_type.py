"""Session type detection for adaptive distillation weights."""

from __future__ import annotations

import re
from enum import Enum

from reprompt.core.conversation import Conversation

# Short confirmation patterns
CONFIRMATION_PATTERNS = re.compile(
    r"^(yes|yeah|yep|ok|okay|sure|right|good|fine|lgtm|looks good|"
    r"\u597d\u7684|\u597d|\u53ef\u4ee5|\u884c|\u5bf9|\u55ef|\u6ca1\u95ee\u9898|\u7ee7\u7eed)\s*[!.?]*$",
    re.IGNORECASE,
)


class SessionType(Enum):
    DEBUGGING = "debugging"
    IMPLEMENTATION = "implementation"
    EXPLORATORY = "exploratory"
    REVIEW = "review"


def detect_session_type(conversation: Conversation) -> SessionType | None:
    """Classify a conversation into one of 4 types, or None if ambiguous.

    Requires assistant turn data for meaningful classification.
    Adapters without parse_conversation() will always return None.
    """
    turns = conversation.turns
    if not turns:
        return None

    user_turns = [t for t in turns if t.role == "user"]
    asst_turns = [t for t in turns if t.role == "assistant"]

    if not user_turns:
        return None

    # Need assistant data for classification
    if not asst_turns:
        return None

    # Compute ratios
    error_rate = sum(1 for t in asst_turns if t.has_error) / len(asst_turns)
    tool_trigger_rate = (
        sum(1 for t in asst_turns if t.tool_calls > 0) / len(asst_turns) if asst_turns else 0.0
    )
    question_ratio = sum(1 for t in user_turns if t.text.rstrip().endswith("?")) / len(user_turns)
    avg_user_turn_length = sum(len(t.text) for t in user_turns) / len(user_turns)
    confirmation_ratio = sum(
        1 for t in user_turns if CONFIRMATION_PATTERNS.match(t.text.strip())
    ) / len(user_turns)

    # Compute avg semantic shift (TF-IDF cosine distance between adjacent user turns)
    from reprompt.core.distill import _compute_semantic_signals

    user_texts = [t.text for t in user_turns]
    shifts, _ = _compute_semantic_signals(user_texts)
    avg_semantic_shift = sum(shifts) / len(shifts) if shifts else 0.0

    # Rule-based classification (ordered by specificity)
    if error_rate > 0.30:
        return SessionType.DEBUGGING
    if tool_trigger_rate > 0.40 and avg_user_turn_length > 50:
        return SessionType.IMPLEMENTATION
    if question_ratio > 0.30 and avg_semantic_shift > 0.60:
        return SessionType.EXPLORATORY
    if confirmation_ratio > 0.40 and tool_trigger_rate < 0.15:
        return SessionType.REVIEW

    return None


def get_weights_for_type(session_type: SessionType | None) -> dict[str, float]:
    """Return signal weights for a session type.

    Returns DEFAULT_WEIGHTS for None (ambiguous).
    """
    from reprompt.core.distill import DEFAULT_WEIGHTS

    if session_type is None:
        return dict(DEFAULT_WEIGHTS)

    weights = dict(DEFAULT_WEIGHTS)

    if session_type == SessionType.DEBUGGING:
        weights["error_recovery"] = 0.25
        weights["tool_trigger"] = 0.15
        weights["position"] = 0.10

    elif session_type == SessionType.IMPLEMENTATION:
        weights["tool_trigger"] = 0.30
        weights["semantic_shift"] = 0.10

    elif session_type == SessionType.EXPLORATORY:
        weights["semantic_shift"] = 0.30
        weights["uniqueness"] = 0.20
        weights["length"] = 0.05
        weights["tool_trigger"] = 0.15

    elif session_type == SessionType.REVIEW:
        weights["position"] = 0.25
        weights["tool_trigger"] = 0.10

    # Runtime safety check
    assert abs(sum(weights.values()) - 1.0) < 0.001, (
        f"Weights for {session_type} sum to {sum(weights.values())}, not 1.0"
    )

    return weights
