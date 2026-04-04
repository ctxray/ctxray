"""Prompt builder — assemble a well-structured prompt from components.

Takes a task description and optional context, files, errors, constraints,
and examples, then assembles a prompt that maximizes the scoring dimensions.
Scoring-aware: structures the output to hit clarity, context, and position.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BuildResult:
    """Result of building a prompt from components."""

    prompt: str
    score: float = 0.0
    tier: str = ""
    components_used: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def build_prompt(
    task: str,
    *,
    context: str = "",
    files: list[str] | None = None,
    error: str = "",
    constraints: list[str] | None = None,
    examples: str = "",
    output_format: str = "",
    role: str = "",
    model: str = "",
) -> BuildResult:
    """Build a well-structured prompt from components.

    Returns the assembled prompt with its score and suggestions
    for components the user could still add.
    """
    parts: list[str] = []
    components: list[str] = []

    # Role (if provided) — goes first
    if role:
        parts.append(f"You are {role}.")
        components.append("role")

    # Task — always present, imperative form, at the front (position bias)
    task_text = _ensure_imperative(task.strip())
    if task_text and task_text[-1] not in ".!?":
        task_text += "."
    parts.append(task_text)
    components.append("task")

    # File references — high context value
    if files:
        if len(files) == 1:
            parts.append(f"File: {files[0]}")
        else:
            file_list = ", ".join(files)
            parts.append(f"Files: {file_list}")
        components.append("files")

    # Error context — critical for debug prompts
    if error:
        parts.append(f"Error: {error}")
        components.append("error")

    # Context — background information
    if context:
        parts.append(f"Context: {context}")
        components.append("context")

    # Examples
    if examples:
        parts.append(f"Example:\n{examples}")
        components.append("examples")

    # Constraints
    if constraints:
        if len(constraints) == 1:
            parts.append(f"Constraint: {constraints[0]}")
        else:
            constraint_lines = "\n".join(f"- {c}" for c in constraints)
            parts.append(f"Constraints:\n{constraint_lines}")
        components.append("constraints")

    # Output format
    if output_format:
        parts.append(f"Output format: {output_format}")
        components.append("output_format")

    # Model-specific formatting
    prompt = _format_for_model(parts, model)

    # Score the assembled prompt
    from ctxray.core.extractors import extract_features
    from ctxray.core.scorer import get_tier, score_prompt

    dna = extract_features(prompt, source="build", session_id="")
    score_result = score_prompt(dna)

    # Determine tier
    tier = get_tier(score_result.total)

    # Generate suggestions for missing components
    suggestions = _missing_suggestions(components)

    return BuildResult(
        prompt=prompt,
        score=score_result.total,
        tier=tier,
        components_used=components,
        suggestions=suggestions,
    )


def _ensure_imperative(task: str) -> str:
    """Strip filler prefixes to get an imperative task statement."""
    import re

    # Remove common polite/filler prefixes
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|i need you to\s+|"
        r"i want you to\s+|i would like you to\s+|help me\s+|"
        r"i was wondering if you could\s+)",
        "",
        task,
        flags=re.IGNORECASE,
    )
    # Capitalize first letter
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _format_for_model(parts: list[str], model: str) -> str:
    """Format prompt parts with model-appropriate structure."""
    if model == "claude":
        return _format_xml(parts)
    elif model == "gpt":
        return _format_markdown(parts)
    else:
        # Default: clean plain text with double newlines
        return "\n\n".join(parts)


def _format_xml(parts: list[str]) -> str:
    """Format with XML tags (preferred by Claude)."""
    if len(parts) <= 2:
        # Short prompts don't need XML
        return "\n\n".join(parts)

    sections: list[str] = []
    for part in parts:
        lower = part.lower()
        if lower.startswith("you are "):
            sections.append(part)
        elif lower.startswith("context:"):
            content = part[len("Context:") :].strip()
            sections.append(f"<context>\n{content}\n</context>")
        elif lower.startswith("error:"):
            content = part[len("Error:") :].strip()
            sections.append(f"<context>\n{content}\n</context>")
        elif lower.startswith("constraint"):
            content = part.split(":", 1)[1].strip() if ":" in part else part
            sections.append(f"<constraints>\n{content}\n</constraints>")
        elif lower.startswith("example"):
            content = part.split(":", 1)[1].strip() if ":" in part else part
            content = part.split("\n", 1)[1].strip() if "\n" in part else content
            sections.append(f"<examples>\n{content}\n</examples>")
        elif lower.startswith("output format:"):
            content = part[len("Output format:") :].strip()
            sections.append(f"<output>\n{content}\n</output>")
        else:
            sections.append(part)

    return "\n\n".join(sections)


def _format_markdown(parts: list[str]) -> str:
    """Format with markdown headers (preferred by GPT)."""
    if len(parts) <= 2:
        return "\n\n".join(parts)

    sections: list[str] = []
    for part in parts:
        lower = part.lower()
        if lower.startswith("you are "):
            sections.append(part)
        elif lower.startswith("context:"):
            content = part[len("Context:") :].strip()
            sections.append(f"## Context\n{content}")
        elif lower.startswith("error:"):
            content = part[len("Error:") :].strip()
            sections.append(f"## Error\n{content}")
        elif lower.startswith("constraint"):
            content = part.split(":", 1)[1].strip() if ":" in part else part
            sections.append(f"## Constraints\n{content}")
        elif lower.startswith("example"):
            content = part.split(":", 1)[1].strip() if ":" in part else part
            content = part.split("\n", 1)[1].strip() if "\n" in part else content
            sections.append(f"## Examples\n{content}")
        elif lower.startswith("output format:"):
            content = part[len("Output format:") :].strip()
            sections.append(f"## Output Format\n{content}")
        else:
            sections.append(part)

    return "\n\n".join(sections)


def _missing_suggestions(components: list[str]) -> list[str]:
    """Suggest components the user could add to improve the prompt."""
    suggestions: list[str] = []

    if "files" not in components:
        suggestions.append("Add --file to reference specific files (+6 pts)")
    if "error" not in components:
        suggestions.append("Add --error with the actual error message (+6 pts)")
    if "constraints" not in components:
        suggestions.append("Add --constraint to set boundaries (+5 pts)")
    if "context" not in components:
        suggestions.append("Add --context for background information (+4 pts)")
    if "examples" not in components:
        suggestions.append("Add --example with expected input/output (+3 pts)")
    if "role" not in components:
        suggestions.append("Add --role to set the AI's perspective (+3 pts)")
    if "output_format" not in components:
        suggestions.append("Add --output-format to specify response structure (+2 pts)")

    return suggestions
