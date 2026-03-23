"""PromptDNA — research-backed prompt feature vector.

Each prompt is decomposed into 30+ computable features that capture
structure, specificity, and adherence to research-validated patterns.

This is the core data model for prompt scoring and analytics.
Features are designed to be computed WITHOUT running any LLM.

Research basis:
- Google Research 2512.14982: keyword repetition
- Stanford 2307.03172: Lost in the Middle positional effects
- EMNLP 2023 SPELL: prompt perplexity as quality signal
- The Prompt Report 2406.06608: prompting technique taxonomy
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


@dataclass
class PromptDNA:
    """Feature vector representing a prompt's structural DNA."""

    # ── Identity (required) ──
    prompt_hash: str
    source: str
    task_type: str

    # ── Basic Metrics ──
    token_count: int = 0
    word_count: int = 0
    sentence_count: int = 0
    line_count: int = 0

    # ── Structure (The Prompt Report taxonomy) ──
    has_role_definition: bool = False
    has_examples: bool = False
    example_count: int = 0
    has_constraints: bool = False
    constraint_count: int = 0
    has_output_format: bool = False
    has_step_by_step: bool = False
    section_count: int = 0

    # ── Context Density ──
    has_code_blocks: bool = False
    code_block_count: int = 0
    code_block_ratio: float = 0.0
    has_file_references: bool = False
    file_reference_count: int = 0
    has_error_messages: bool = False
    context_specificity: float = 0.0

    # ── Research-backed Scores ──
    # [Google Research 2512.14982] Repetition
    keyword_repetition_freq: float = 0.0
    instruction_repetition: bool = False

    # [Stanford 2307.03172] Lost in the Middle
    key_instruction_position: float = 0.0  # 0.0=start, 1.0=end
    critical_info_distribution: str = "unknown"

    # [ICLR 2025] Attention Sink
    opening_quality: float = 0.0

    # ── Readability ──
    flesch_reading_ease: float = 0.0
    gunning_fog: float = 0.0

    # ── Semantic ──
    complexity_score: float = 0.0
    ambiguity_score: float = 0.0

    # ── Computed Scores ──
    predicted_effectiveness: float = 0.0
    overall_score: float = 0.0
    compressibility: float = 0.0  # 0.0-1.0: how much filler can be removed

    # ── Metadata ──
    extractor_tier: int = 1  # which tier of extractors was used
    locale: str = "en"  # detected language: "en", "zh", "ja", "ko"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (for storage and transport)."""
        result: dict[str, Any] = {}
        for f in fields(self):
            result[f.name] = getattr(self, f.name)
        return result

    def feature_vector(self) -> list[float]:
        """Return numeric features as a flat list (for ML models).

        Booleans become 0.0/1.0, strings are excluded.
        """
        vec: list[float] = []
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, bool):
                vec.append(1.0 if val else 0.0)
            elif isinstance(val, int | float):
                vec.append(float(val))
            # Skip strings (hash, source, task_type, critical_info_distribution)
        return vec
