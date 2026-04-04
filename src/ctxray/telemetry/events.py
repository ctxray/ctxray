"""Telemetry event schema and bucketing helpers.

Privacy design:
- dna_vector is lossy feature extraction (regex counts) -- impossible to
  reconstruct the original prompt text.
- All outcome signals are bucketed (ranges, not exact numbers).
- timestamp_day is date-only (no exact time).
- No prompt text, no prompt hash, no file paths.
"""

from __future__ import annotations

import locale as _locale
from datetime import date

from pydantic import BaseModel, Field

from ctxray.core.prompt_dna import PromptDNA
from ctxray.core.scorer import ScoreBreakdown

# -- Bucketing helpers (privacy-preserving ranges) --


def bucket_duration(seconds: int | None) -> str:
    """Bucket session duration into privacy-preserving ranges."""
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return "<1m"
    if seconds <= 600:
        return "1m-10m"
    if seconds < 3600:
        return "10m-60m"
    return ">60m"


def bucket_error_ratio(ratio: float | None) -> str:
    """Bucket error ratio (errors/prompts) into ranges."""
    if ratio is None:
        return "unknown"
    if ratio == 0.0:
        return "0%"
    if ratio <= 0.10:
        return "1-10%"
    if ratio <= 0.50:
        return "10-50%"
    return ">50%"


def bucket_tool_calls(count: int | None) -> str:
    """Bucket tool call count into ranges."""
    if count is None:
        return "unknown"
    if count == 0:
        return "0"
    if count <= 5:
        return "1-5"
    if count <= 20:
        return "6-20"
    return ">20"


# -- Event model --


class TelemetryEvent(BaseModel):
    """A single anonymous telemetry event.

    Contains ONLY derived/aggregated data. Never raw prompt text.
    """

    # Identity (one-way hash, not reversible)
    install_id: str = Field(..., min_length=64, max_length=64)

    # DNA feature vector (lossy extraction -- cannot reconstruct prompt)
    dna_vector: list[float]

    # Prompt metadata
    task_type: str
    source: str
    client: str = "cli"

    # Score breakdown (5 categories + total)
    score_total: float
    score_structure: float
    score_context: float
    score_position: float
    score_repetition: float
    score_clarity: float

    # Outcome signals (all bucketed for privacy)
    session_duration_bucket: str = "unknown"
    error_ratio_bucket: str = "unknown"
    tool_call_count_bucket: str = "unknown"
    effectiveness_score: float | None = None

    # Context
    locale: str = ""
    ctxray_version: str = ""
    timestamp_day: str = ""  # YYYY-MM-DD only, no exact time


# -- Builder --


def build_event(
    *,
    install_id: str,
    dna: PromptDNA,
    scores: ScoreBreakdown,
    version: str,
    session_duration_seconds: int | None = None,
    error_count: int | None = None,
    prompt_count: int | None = None,
    tool_call_count: int | None = None,
    effectiveness_score: float | None = None,
) -> TelemetryEvent:
    """Build a TelemetryEvent from a PromptDNA and ScoreBreakdown.

    This is the single point where raw data is converted to anonymous telemetry.
    """
    # Compute error ratio from counts
    error_ratio: float | None = None
    if error_count is not None and prompt_count and prompt_count > 0:
        error_ratio = error_count / prompt_count

    # Detect locale (best-effort, empty string if unavailable)
    try:
        loc = _locale.getlocale()[0] or ""
    except Exception:
        loc = ""

    return TelemetryEvent(
        install_id=install_id,
        dna_vector=dna.feature_vector(),
        task_type=dna.task_type,
        source=dna.source,
        client="cli",
        score_total=scores.total,
        score_structure=scores.structure,
        score_context=scores.context,
        score_position=scores.position,
        score_repetition=scores.repetition,
        score_clarity=scores.clarity,
        session_duration_bucket=bucket_duration(session_duration_seconds),
        error_ratio_bucket=bucket_error_ratio(error_ratio),
        tool_call_count_bucket=bucket_tool_calls(tool_call_count),
        effectiveness_score=effectiveness_score,
        locale=loc,
        ctxray_version=version,
        timestamp_day=date.today().isoformat(),
    )
