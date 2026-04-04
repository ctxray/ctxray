"""Session-level quality metrics — composite scoring + frustration detection.

Combines prompt quality, agent efficiency, distill focus, and outcome
into a single 0-100 session score. All analysis is rule-based (zero LLM, <1ms).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ctxray.core.agent import AgentReport
from ctxray.core.conversation import Conversation, ConversationTurn, DistillResult

# ---------------------------------------------------------------------------
# Component weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "prompt_quality": 0.30,
    "efficiency": 0.30,
    "focus": 0.20,
    "outcome": 0.20,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FrustrationSignals:
    """Frustration indicators detected from conversation turns."""

    abandonment: bool = False  # Last 3+ assistant turns all have errors
    escalation: bool = False  # Error rate in second half > first half * 1.5
    stall_turns: int = 0  # Assistant turns with 0 tool calls and <50 chars


@dataclass
class SessionQuality:
    """Composite session quality report."""

    session_id: str
    quality_score: float  # 0-100 composite
    prompt_quality: float | None = None  # 0-100
    efficiency: float | None = None  # 0-100
    focus: float | None = None  # 0-100
    outcome: float | None = None  # 0-100
    frustration: FrustrationSignals = field(default_factory=FrustrationSignals)
    session_type: str | None = None
    insight: str = ""
    components_available: int = 0


# ---------------------------------------------------------------------------
# Frustration detection
# ---------------------------------------------------------------------------


def _detect_frustration(turns: list[ConversationTurn]) -> FrustrationSignals:
    """Detect frustration signals from conversation turns."""
    asst_turns = [t for t in turns if t.role == "assistant"]

    if not asst_turns:
        return FrustrationSignals()

    # Abandonment: last 3+ assistant turns all have errors
    abandonment = False
    if len(asst_turns) >= 3:
        last_three = asst_turns[-3:]
        abandonment = all(t.has_error for t in last_three)

    # Escalation: error rate in second half > first half * 1.5
    escalation = False
    if len(asst_turns) >= 4:
        mid = len(asst_turns) // 2
        first_half = asst_turns[:mid]
        second_half = asst_turns[mid:]
        first_rate = sum(1 for t in first_half if t.has_error) / len(first_half)
        second_rate = sum(1 for t in second_half if t.has_error) / len(second_half)
        escalation = second_rate > first_rate * 1.5 and second_rate > 0.2

    # Stall turns: assistant turns with no tool calls and short text
    stall_turns = sum(1 for t in asst_turns if t.tool_calls == 0 and len(t.text.strip()) < 50)

    return FrustrationSignals(
        abandonment=abandonment,
        escalation=escalation,
        stall_turns=stall_turns,
    )


# ---------------------------------------------------------------------------
# Insight generation
# ---------------------------------------------------------------------------


def _generate_insight(quality: SessionQuality) -> str:
    """Generate a one-line insight from quality metrics (priority order)."""
    f = quality.frustration

    if f.abandonment:
        return "Ended with unresolved errors"

    if f.escalation:
        return "Errors escalated through session"

    if f.stall_turns >= 5:
        return f"{f.stall_turns} stall turns detected"

    if quality.efficiency is not None and quality.efficiency < 50:
        return "Low efficiency (error loops)"

    score = quality.quality_score
    if score >= 80:
        return "Focused session"
    if score >= 60:
        return "Solid session"
    if score >= 40:
        return "Room for improvement"
    return "Rough session"


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------


def score_session(
    conversation: Conversation,
    *,
    agent_report: AgentReport | None = None,
    distill_result: DistillResult | None = None,
    effectiveness_score: float | None = None,
    avg_prompt_score: float | None = None,
) -> SessionQuality:
    """Compute composite session quality score (0-100).

    Components (weighted average of available inputs):
    - prompt_quality (30%): avg overall_score from prompt features
    - efficiency (30%): productive_ratio from agent analysis
    - focus (20%): retention_ratio from distill
    - outcome (20%): effectiveness_score

    When a component is unavailable, its weight redistributes proportionally.
    """
    components: dict[str, float] = {}

    # Prompt quality: already 0-100
    if avg_prompt_score is not None:
        components["prompt_quality"] = max(0.0, min(100.0, avg_prompt_score))

    # Efficiency: productive_ratio is 0-1
    if agent_report is not None:
        ratio = agent_report.efficiency.productive_ratio
        components["efficiency"] = max(0.0, min(100.0, ratio * 100))

    # Focus: retention_ratio is 0-1
    if distill_result is not None:
        ratio = distill_result.stats.retention_ratio
        components["focus"] = max(0.0, min(100.0, ratio * 100))

    # Outcome: effectiveness_score is 0-1
    if effectiveness_score is not None:
        components["outcome"] = max(0.0, min(100.0, effectiveness_score * 100))

    # Compute weighted average with weight redistribution
    if components:
        available_weights = {k: DEFAULT_WEIGHTS[k] for k in components}
        weight_sum = sum(available_weights.values())
        normalized = {k: w / weight_sum for k, w in available_weights.items()}
        quality_score = sum(components[k] * normalized[k] for k in components)
    else:
        quality_score = 0.0

    quality_score = round(max(0.0, min(100.0, quality_score)), 1)

    # Frustration detection
    frustration = _detect_frustration(conversation.turns)

    # Session type
    session_type_str: str | None = None
    if agent_report is not None and agent_report.efficiency.session_type is not None:
        session_type_str = agent_report.efficiency.session_type

    quality = SessionQuality(
        session_id=conversation.session_id,
        quality_score=quality_score,
        prompt_quality=components.get("prompt_quality"),
        efficiency=components.get("efficiency"),
        focus=components.get("focus"),
        outcome=components.get("outcome"),
        frustration=frustration,
        session_type=session_type_str,
        components_available=len(components),
    )

    quality.insight = _generate_insight(quality)

    return quality
