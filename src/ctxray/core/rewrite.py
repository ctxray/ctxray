"""Rule-based prompt rewrite engine.

Transforms low-scoring prompts into better versions using research-backed
rules. No LLM required — pure regex + structural transforms.

Layers:
1. Compress — remove filler (reuse compress engine)
2. Restructure — front-load instructions (move imperative to start)
3. Reinforce — echo key requirement at end for long prompts
4. Clarity — remove hedging language
5. Task-specific — append structural scaffolding based on detected task type
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RewriteResult:
    """Result of rewriting a prompt."""

    original: str
    rewritten: str
    changes: list[str] = field(default_factory=list)
    manual_suggestions: list[str] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0
    score_delta: float = 0.0


def rewrite_prompt(text: str) -> RewriteResult:
    """Rewrite a prompt to improve its score. Returns before/after with changes."""
    from ctxray.core.compress import compress_text
    from ctxray.core.extractors import extract_features
    from ctxray.core.scorer import score_prompt
    from ctxray.core.segmenter import segment_prompt

    # Score original
    dna = extract_features(text, source="rewrite", session_id="")
    score_before = score_prompt(dna)

    result = text
    changes: list[str] = []

    # Layer 1: Compress (filler removal)
    compressed = compress_text(result)
    if compressed.savings_pct > 5:
        result = compressed.compressed
        changes.append(f"Removed filler ({compressed.savings_pct:.0f}% shorter)")

    # Layer 2: Front-load instruction (if buried in middle)
    if dna.key_instruction_position > 0.3:
        segments = segment_prompt(result)
        new_result = _front_load_instruction(result, segments)
        if new_result != result:
            result = new_result
            changes.append("Moved main instruction to front")

    # Layer 3: Echo key requirement (for long prompts with low repetition)
    current_word_count = len(result.split())
    if dna.keyword_repetition_freq < 0.15 and current_word_count > 40:
        echoed = _echo_key_requirement(result)
        if echoed != result:
            result = echoed
            changes.append("Echoed key requirement at end")

    # Layer 4: Clarity — replace hedge phrases
    cleaned = _remove_hedging(result)
    if cleaned != result:
        result = cleaned
        changes.append("Removed hedging language")

    # Layer 5: Task-specific scaffolding
    scaffolded = _apply_task_scaffold(result, dna)
    if scaffolded != result:
        result = scaffolded
        changes.append(f"Added {dna.task_type} prompt structure")

    # Score rewritten
    dna_after = extract_features(result, source="rewrite", session_id="")
    score_after = score_prompt(dna_after)

    # Generate manual suggestions for things we can't auto-fix
    manual = _generate_manual_suggestions(dna)

    return RewriteResult(
        original=text,
        rewritten=result,
        changes=changes,
        manual_suggestions=manual,
        score_before=score_before.total,
        score_after=score_after.total,
        score_delta=round(score_after.total - score_before.total, 1),
    )


def _front_load_instruction(text: str, segments: list) -> str:
    """Move the first instruction segment to the front of the prompt."""
    instruction_seg = None
    instruction_idx = -1

    for i, seg in enumerate(segments):
        if seg.segment_type == "instruction" and seg.start_pos > 0.2:
            instruction_seg = seg
            instruction_idx = i
            break

    if instruction_seg is None:
        return text

    # Extract the instruction text and rebuild
    inst_text = instruction_seg.text.strip()
    # Remove the instruction from its original position
    remaining_parts = []
    for i, seg in enumerate(segments):
        if i == instruction_idx:
            continue
        remaining_parts.append(seg.text.strip())

    remaining = "\n\n".join(p for p in remaining_parts if p)

    # Ensure instruction ends with period for clean sentence
    if inst_text and inst_text[-1] not in ".!?":
        inst_text = inst_text + "."

    return f"{inst_text}\n\n{remaining}".strip()


def _echo_key_requirement(text: str) -> str:
    """Add a reinforcement of the key requirement at the end."""
    # Extract the most important action phrase from the first sentence
    lines = text.strip().split("\n")
    first_line = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            first_line = stripped
            break

    if not first_line or len(first_line) < 10:
        return text

    # Extract the core verb+object phrase
    key_phrase = _extract_key_phrase(first_line)
    if not key_phrase or len(key_phrase) < 8:
        return text

    # Don't echo if text already ends with similar content
    last_100 = text[-100:].lower()
    if key_phrase.lower() in last_100:
        return text

    return f"{text.rstrip()}\n\nImportant: {key_phrase}."


def _extract_key_phrase(sentence: str) -> str:
    """Extract the core verb+object from a sentence."""
    # Remove leading filler
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|i need you to\s+|i want you to\s+|"
        r"i would like you to\s+|help me\s+)",
        "",
        sentence.strip(),
        flags=re.IGNORECASE,
    )
    # Take the main clause (before first comma or period)
    main = re.split(r"[,.]", cleaned)[0].strip()
    # Cap length
    if len(main) > 80:
        words = main.split()
        main = " ".join(words[:12])
    return main


_HEDGE_PATTERNS = [
    (re.compile(r"\bI was wondering if you could\b", re.IGNORECASE), ""),
    (re.compile(r"\bI think maybe\b", re.IGNORECASE), ""),
    (re.compile(r"\bif possible,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bif you don'?t mind,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bbasically,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bkind of\b", re.IGNORECASE), ""),
    (re.compile(r"\bsort of\b", re.IGNORECASE), ""),
    (re.compile(r"\bjust\s+", re.IGNORECASE), ""),
    (re.compile(r"\bmaybe\s+", re.IGNORECASE), ""),
    (re.compile(r"\bperhaps\s+", re.IGNORECASE), ""),
    (re.compile(r"\ba little bit\b", re.IGNORECASE), ""),
    (re.compile(r"\bI guess\s+", re.IGNORECASE), ""),
]


def _remove_hedging(text: str) -> str:
    """Remove hedging language that weakens the prompt."""
    result = text
    for pattern, replacement in _HEDGE_PATTERNS:
        result = pattern.sub(replacement, result)
    # Clean up double spaces
    result = re.sub(r"  +", " ", result)
    # Clean up leading spaces on lines
    lines = result.split("\n")
    result = "\n".join(line.lstrip() if line.strip() else line for line in lines)
    return result


def _apply_task_scaffold(text: str, dna: object) -> str:
    """Append task-specific structural cues based on detected task type.

    Only fires when the prompt is short (<30 words) AND missing critical
    context for the detected task type. Adds fill-in-the-blank lines so
    the user knows what to add — not generic advice, but structured slots.

    Slot design informed by:
    - fabric patterns (danielmiessler/fabric, 40k stars): IDENTITY/STEPS/OUTPUT
    - steipete/agent-rules (5.6k stars): bug-fix, analyze-issue, pr-review
    - awesome-cursorrules (38k stars): framework-specific conventions
    """
    task = getattr(dna, "task_type", "other")
    word_count = getattr(dna, "word_count", 0)

    # Only scaffold short prompts — long prompts already have context
    if word_count > 30:
        return text

    missing: list[str] = []

    if task == "debug":
        # steipete/agent-rules: bug-fix requires reproduce + expected vs actual
        if not getattr(dna, "has_error_messages", False):
            missing.append("Error: <paste the error message or stack trace>")
        if not getattr(dna, "has_file_references", False):
            missing.append("File: <which file and function>")
        # Expected vs actual is the most diagnostic slot (from bug-fix.mdc)
        missing.append("Expected: <what should happen vs what actually happens>")

    elif task == "implement":
        if not getattr(dna, "has_io_spec", False):
            missing.append("Input/Output: <what it takes and returns>")
        if not getattr(dna, "has_constraints", False):
            missing.append("Constraints: <what NOT to change>")
        if not getattr(dna, "has_edge_cases", False):
            missing.append("Edge cases: <empty input, null, zero, etc.>")

    elif task == "refactor":
        if not getattr(dna, "has_file_references", False):
            missing.append("Scope: <which files/modules to touch>")
        if not getattr(dna, "has_constraints", False):
            missing.append("Preserve: <what must NOT change (API, tests, etc.)>")
        # fabric/awesome-cursorrules: refactors benefit from target pattern
        missing.append("Goal: <readability, performance, or pattern to apply>")

    elif task == "test":
        if not getattr(dna, "has_file_references", False):
            missing.append("Target: <function or module to test>")
        if not getattr(dna, "has_edge_cases", False):
            missing.append("Edge cases: <empty, null, boundary values>")
        if not getattr(dna, "has_io_spec", False):
            missing.append("Expected: <what the correct behavior should be>")

    elif task == "review":
        # fabric review_code: 6 named axes instead of generic "focus"
        if not getattr(dna, "has_constraints", False):
            missing.append(
                "Review axes: <correctness, security, performance, readability, error handling>"
            )
        if not getattr(dna, "has_file_references", False):
            missing.append("Scope: <which files or PR to review>")

    if not missing:
        return text

    scaffold = "\n".join(missing)
    return f"{text.rstrip()}\n\n{scaffold}"


def _generate_manual_suggestions(dna: object) -> list[str]:
    """Generate suggestions for improvements that require human input."""
    suggestions: list[str] = []

    specificity = getattr(dna, "context_specificity", 1.0)
    if specificity < 0.4:
        suggestions.append("Add actual code snippets or error messages for context")

    if not getattr(dna, "has_constraints", True):
        suggestions.append('Add constraints (e.g., "Do not modify existing tests")')

    if not getattr(dna, "has_output_format", True):
        suggestions.append("Specify expected output format (e.g., JSON, code block)")

    if not getattr(dna, "has_file_references", True):
        task = getattr(dna, "task_type", "")
        if task in ("debug", "implement", "refactor", "test"):
            suggestions.append("Reference specific files or functions by name")

    if not getattr(dna, "has_examples", True):
        suggestions.append("Add an example of expected input/output")

    if not getattr(dna, "has_io_spec", True):
        task = getattr(dna, "task_type", "")
        if task in ("implement", "test"):
            suggestions.append("Specify expected input/output behavior")

    if not getattr(dna, "has_edge_cases", True):
        task = getattr(dna, "task_type", "")
        if task in ("implement", "test"):
            suggestions.append("Mention edge cases (empty input, null, zero)")

    return suggestions
