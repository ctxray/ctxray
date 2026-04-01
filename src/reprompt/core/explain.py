"""Prompt explainer — explain what makes a prompt good or bad in plain English.

No LLM required. Generates educational explanations from PromptDNA features
and scoring breakdown. Designed to teach users *why* a prompt scores the way
it does and what specifically to improve.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExplainResult:
    """Result of explaining a prompt."""

    score: float = 0.0
    tier: str = ""
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)


def explain_prompt(text: str) -> ExplainResult:
    """Explain what makes a prompt good or bad."""
    from reprompt.core.extractors import extract_features
    from reprompt.core.scorer import score_prompt

    dna = extract_features(text, source="explain", session_id="")
    breakdown = score_prompt(dna)

    tier = _get_tier(breakdown.total)
    strengths: list[str] = []
    weaknesses: list[str] = []
    tips: list[str] = []

    # Analyze each dimension
    _analyze_clarity(breakdown.clarity, dna, strengths, weaknesses, tips)
    _analyze_context(breakdown.context, dna, strengths, weaknesses, tips)
    _analyze_position(breakdown.position, dna, strengths, weaknesses, tips)
    _analyze_structure(breakdown.structure, dna, strengths, weaknesses, tips)
    _analyze_repetition(breakdown.repetition, dna, strengths, weaknesses, tips)

    # Generate summary
    summary = _generate_summary(breakdown.total, tier, strengths, weaknesses)

    return ExplainResult(
        score=breakdown.total,
        tier=tier,
        summary=summary,
        strengths=strengths,
        weaknesses=weaknesses,
        tips=tips,
    )


def _analyze_clarity(score: float, dna: object, strengths: list, weaknesses: list, tips: list):
    word_count = getattr(dna, "word_count", 0)
    ambiguity = getattr(dna, "ambiguity_score", 0)

    if score >= 20:
        strengths.append("Clear and unambiguous language")
    elif score >= 12:
        if ambiguity > 0.3:
            weaknesses.append(
                f"Ambiguous wording (score {ambiguity:.1f}) — "
                "words like 'it', 'that', 'this' without clear referents"
            )
            tips.append("Replace pronouns with specific names: 'it' → 'the auth module'")
    else:
        if word_count < 10:
            weaknesses.append(
                f"Very short ({word_count} words) — too little for the AI to work with"
            )
            tips.append("Expand with what, where, and why: what to do, which file, why it matters")
        if ambiguity > 0.5:
            weaknesses.append("Highly ambiguous — the AI will have to guess what you mean")


def _analyze_context(score: float, dna: object, strengths: list, weaknesses: list, tips: list):
    has_code = getattr(dna, "has_code_blocks", False)
    has_files = getattr(dna, "has_file_references", False)
    has_errors = getattr(dna, "has_error_messages", False)
    specificity = getattr(dna, "context_specificity", 0)

    if score >= 20:
        parts = []
        if has_code:
            parts.append("code blocks")
        if has_files:
            parts.append("file references")
        if has_errors:
            parts.append("error messages")
        if parts:
            strengths.append(f"Rich context: {', '.join(parts)}")
        else:
            strengths.append("Good contextual detail")
    elif score >= 10:
        if not has_files:
            tips.append("Add file paths — the AI needs to know where to look")
        if not has_errors and getattr(dna, "task_type", "") == "debug":
            tips.append("Paste the actual error message — vague descriptions lose critical details")
    else:
        weaknesses.append("Lacks concrete context — no files, code, or error messages referenced")
        if specificity < 0.3:
            tips.append("Add specifics: which file, what error, what you've already tried")


def _analyze_position(score: float, dna: object, strengths: list, weaknesses: list, tips: list):
    pos = getattr(dna, "key_instruction_position", 0.5)

    if score >= 16:
        strengths.append("Main instruction at the start — optimal for model attention")
    elif score >= 8:
        pass  # Decent but not great, no need to comment
    else:
        if pos > 0.4:
            weaknesses.append(
                "Key instruction buried in the middle — "
                "models recall start/end instructions 2-3x better (Stanford)"
            )
            tips.append("Move your main ask to the first sentence, then add context after")


def _analyze_structure(score: float, dna: object, strengths: list, weaknesses: list, tips: list):
    has_role = getattr(dna, "has_role_definition", False)
    has_constraints = getattr(dna, "has_constraints", False)
    has_examples = getattr(dna, "has_examples", False)

    if score >= 12:
        parts = []
        if has_role:
            parts.append("role definition")
        if has_constraints:
            parts.append("constraints")
        if has_examples:
            parts.append("examples")
        if parts:
            strengths.append(f"Well-structured: {', '.join(parts)}")
    else:
        # Only suggest structure for prompts that are long enough to benefit
        word_count = getattr(dna, "word_count", 0)
        if word_count > 15:
            if not has_constraints:
                tips.append(
                    'Add boundaries: "Don\'t modify tests" or "Keep backward compatibility"'
                )


def _analyze_repetition(score: float, dna: object, strengths: list, weaknesses: list, tips: list):
    freq = getattr(dna, "keyword_repetition_freq", 0)

    if score >= 12:
        strengths.append("Good keyword reinforcement — key terms repeated for emphasis")
    elif freq > 0.3:
        weaknesses.append(
            "Excessive repetition — the same terms appear too often, which can confuse the model"
        )
        tips.append("Vary your wording or use the key term 2-3 times, not more")


def _generate_summary(total: float, tier: str, strengths: list, weaknesses: list) -> str:
    """Generate a plain-English summary of the prompt quality."""
    if total >= 85:
        return (
            "Excellent prompt. Clear instructions, rich context, and good structure. "
            "This gives the AI everything it needs to produce a strong response."
        )
    elif total >= 70:
        return (
            "Strong prompt with good foundations. "
            f"{'Minor improvements possible.' if weaknesses else 'Well-crafted overall.'}"
        )
    elif total >= 50:
        return (
            "Decent prompt that covers the basics. "
            "Adding more context or specifics would help the AI give you a better answer."
        )
    elif total >= 30:
        s_count = len(strengths)
        w_count = len(weaknesses)
        if w_count > s_count:
            return (
                "This prompt is missing key context that the AI needs. "
                "The more specific you are, the less the AI has to guess."
            )
        return (
            "Basic prompt — it tells the AI what to do but not enough about the situation. "
            "A few additions would significantly improve the response quality."
        )
    else:
        return (
            "Very minimal prompt. The AI will likely ask follow-up questions or make "
            "assumptions. Adding any context — files, errors, constraints — helps."
        )


def _get_tier(score: float) -> str:
    if score >= 85:
        return "EXPERT"
    if score >= 70:
        return "STRONG"
    if score >= 50:
        return "GOOD"
    if score >= 30:
        return "BASIC"
    return "DRAFT"
