"""Session-level metadata extraction for effectiveness scoring."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionMeta:
    """Metadata about an AI coding session."""

    session_id: str
    source: str
    project: str
    start_time: str
    end_time: str
    duration_seconds: int
    prompt_count: int
    tool_call_count: int
    error_count: int
    final_status: str  # "success" | "error" | "unknown"
    avg_prompt_length: float
