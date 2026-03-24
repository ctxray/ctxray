"""Data models for conversation distillation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """A single turn in a conversation (user or assistant)."""

    role: str  # "user" | "assistant"
    text: str
    timestamp: str
    turn_index: int

    # Assistant-specific (0/False for user turns)
    tool_calls: int = 0
    has_error: bool = False
    tool_use_paths: list[str] = field(default_factory=list)

    # Enrichment (populated by distill engine, not adapter)
    score: float | None = None  # Display-only, from prompt_features
    is_duplicate: bool = False
    importance: float = 0.0  # Computed by 6-signal scoring
    signal_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class Conversation:
    """A full conversation from a session."""

    session_id: str
    source: str
    project: str | None
    turns: list[ConversationTurn]
    start_time: str | None = None
    end_time: str | None = None
    duration_seconds: int | None = None


@dataclass
class DistillStats:
    """Statistics about the distillation."""

    total_turns: int = 0
    kept_turns: int = 0
    retention_ratio: float = 0.0  # kept/total
    total_duration_seconds: int = 0


@dataclass
class DistillResult:
    """Result of distilling a conversation."""

    conversation: Conversation
    filtered_turns: list[ConversationTurn]
    threshold: float
    summary: str | None = None
    files_changed: list[str] = field(default_factory=list)
    stats: DistillStats = field(default_factory=DistillStats)
