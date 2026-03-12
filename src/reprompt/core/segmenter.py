"""Three-pass prompt segmentation into semantic parts.

Splits a prompt into labeled segments: instruction, context, constraint,
example, system_role, output_format, filler.

Algorithm:
  Pass 1: Structural split at blank lines, headers, code block boundaries.
  Pass 2: Pattern classification — weighted regex markers score each chunk.
  Pass 3: Context propagation — low-confidence chunks inherit from neighbors.

Zero external dependencies. <1ms per prompt.

Research basis: The Prompt Report (arXiv:2406.06608) taxonomy of 58 techniques.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Segment types in priority order
SEGMENT_TYPES = (
    "system_role",
    "instruction",
    "context",
    "constraint",
    "example",
    "output_format",
    "filler",
)

# Weighted markers: (pattern, weight) — higher weight = stronger signal
_MARKERS: dict[str, list[tuple[str, float]]] = {
    "system_role": [
        (r"(?i)^you are\b", 4.0),
        (r"(?i)^act as\b", 4.0),
        (r"(?i)^as a\b", 3.0),
        (r"(?i)\brole:\s", 3.0),
        (r"(?i)^pretend\b", 2.0),
    ],
    "instruction": [
        (
            r"(?i)^(fix|add|create|implement|debug|explain|write|update|remove|refactor"
            r"|build|test|review|deploy|migrate|optimize|delete|move|rename|install"
            r"|configure|set up)\b",
            3.0,
        ),
        (r"(?i)(please|can you|could you|i need|i want|help me)", 1.5),
        (r"(?i)(how (do|can|should|to))\b", 2.0),
        (r"\?$", 1.5),
    ],
    "context": [
        (r"```", 3.0),
        (r"(?i)(the (current|existing)|currently|right now|at the moment)", 2.0),
        (r"(?i)(the error|the output|the log|stack trace|traceback)", 2.5),
        (r"(?i)(here is|here's|this is|see below|above code)", 2.0),
        (r"(?i)(file|line \d|\.py|\.ts|\.js|\.go|\.rs)\b", 1.5),
    ],
    "constraint": [
        (r"(?i)(do not|don't|must not|never|avoid)\b", 3.0),
        (r"(?i)(must|should|ensure|make sure|always)\b", 2.0),
        (r"(?i)(only|without|except|unless|limit)\b", 1.5),
        (r"(?i)(keep|preserve|maintain|don't (change|modify|touch|break))", 2.0),
    ],
    "example": [
        (r"(?i)(example|e\.g\.|for instance|such as)\b", 3.0),
        (r"(?i)(input|output|before|after)\s*:", 2.5),
        (r"(?i)(like this|looks like|something like)", 1.5),
    ],
    "output_format": [
        (r"(?i)(return|output|format|respond)\s+(as|in|with|using)\b", 3.0),
        (r"(?i)(json|markdown|csv|yaml|xml|table|list|bullet)\b", 2.0),
        (r"(?i)(include|with) (fields?|columns?|headers?)\b", 1.5),
    ],
}

# Minimum score to assign a type (below this → "filler")
_MIN_SCORE = 1.5


@dataclass(frozen=True)
class PromptSegment:
    """A labeled section of a prompt."""

    text: str
    segment_type: str  # one of SEGMENT_TYPES
    start_pos: float  # 0.0 = start of prompt, 1.0 = end
    end_pos: float
    confidence: float  # how confident the classification is


def segment_prompt(text: str) -> list[PromptSegment]:
    """Segment a prompt into labeled parts.

    Returns list of PromptSegment ordered by position. Empty list for empty input.
    """
    if not text or not text.strip():
        return []

    total_len = len(text)

    # --- Pass 1: Structural split ---
    chunks = _structural_split(text)
    if not chunks:
        return []

    # --- Pass 2: Pattern classification ---
    classified: list[tuple[str, str, float]] = []  # (chunk_text, type, confidence)
    for chunk_text in chunks:
        seg_type, conf = _classify_chunk(chunk_text)
        classified.append((chunk_text, seg_type, conf))

    # --- Pass 3: Context propagation ---
    classified = _propagate_context(classified)

    # Build segments with positions
    segments: list[PromptSegment] = []
    current_pos = 0
    for chunk_text, seg_type, conf in classified:
        # Find this chunk's position in the original text.
        # idx == -1 should not occur because chunks come from splitting `text`,
        # but whitespace normalisation could cause a mismatch; falling back to
        # current_pos keeps start/end positions monotonically increasing.
        idx = text.find(chunk_text, current_pos)
        if idx == -1:
            idx = current_pos
        start = idx / total_len if total_len > 0 else 0.0
        end = (idx + len(chunk_text)) / total_len if total_len > 0 else 0.0
        segments.append(
            PromptSegment(
                text=chunk_text,
                segment_type=seg_type,
                start_pos=round(min(start, 1.0), 4),
                end_pos=round(min(end, 1.0), 4),
                confidence=conf,
            )
        )
        current_pos = idx + len(chunk_text)

    return segments


def _structural_split(text: str) -> list[str]:
    """Pass 1: Split text at structural boundaries."""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current.append(line)
            if not in_code_block:
                # Code block just closed — flush
                chunks.append("\n".join(current))
                current = []
            continue

        if in_code_block:
            current.append(line)
            continue

        if stripped == "" and current:
            chunks.append("\n".join(current))
            current = []
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(current))

    return [c for c in chunks if c.strip()]


def _classify_chunk(text: str) -> tuple[str, float]:
    """Pass 2: Score a chunk against all segment type markers."""
    scores: dict[str, float] = {}
    for seg_type, markers in _MARKERS.items():
        total = 0.0
        for pattern, weight in markers:
            if re.search(pattern, text, re.MULTILINE):
                total += weight
        if total > 0:
            scores[seg_type] = total

    if not scores:
        return ("filler", 0.0)

    best_type = max(scores, key=lambda k: scores[k])
    best_score = scores[best_type]

    if best_score < _MIN_SCORE:
        return ("filler", best_score)

    return (best_type, best_score)


def _propagate_context(
    classified: list[tuple[str, str, float]],
) -> list[tuple[str, str, float]]:
    """Pass 3: Low-confidence filler chunks inherit neighbor types."""
    if len(classified) <= 1:
        return classified

    result = list(classified)
    for i, (chunk_text, seg_type, conf) in enumerate(result):
        if seg_type != "filler":
            continue
        prev_type = result[i - 1][1] if i > 0 else None
        next_type = result[i + 1][1] if i < len(result) - 1 else None
        if prev_type == "context" or next_type == "context":
            result[i] = (chunk_text, "context", 0.5)
        elif prev_type and prev_type != "filler":
            result[i] = (chunk_text, prev_type, 0.3)
        elif next_type and next_type != "filler":
            result[i] = (chunk_text, next_type, 0.3)

    return result
