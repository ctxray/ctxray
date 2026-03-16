"""Prompt template management — save and retrieve reusable prompts."""

from __future__ import annotations

from reprompt.core.library import categorize_prompt
from reprompt.storage.db import PromptDB


def generate_template_name(text: str, db: PromptDB) -> str:
    """Auto-generate a unique template name from prompt text."""
    category = categorize_prompt(text)
    stop = {"the", "a", "an", "in", "on", "to", "for", "is", "it", "and", "or", "of", "with"}
    words = [w.lower() for w in text.split() if w.lower() not in stop and len(w) > 2]
    base = "-".join(words[:3]) if words else "template"
    base = f"{category}-{base}"

    # Ensure uniqueness
    name = base
    counter = 2
    while db.template_name_exists(name):
        name = f"{base}-{counter}"
        counter += 1

    return name


def save_template(
    db: PromptDB,
    text: str,
    name: str | None = None,
    category: str | None = None,
) -> dict[str, str | int]:
    """Save a prompt as a reusable template.

    Returns dict with 'id', 'name', 'category'.
    """
    if category is None:
        category = categorize_prompt(text)

    if name is None:
        name = generate_template_name(text, db)

    template_id = db.save_template(name=name, text=text, category=category)
    return {"id": template_id, "name": name, "category": category}


def extract_variables(text: str) -> list[str]:
    """Extract {variable} placeholder names from template text."""
    import re

    return re.findall(r"\{(\w+)\}", text)


def render_template(text: str, variables: dict[str, str]) -> str:
    """Replace {variable} placeholders with provided values.

    Missing variables are left as-is (not raised as errors).
    """
    result = text
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", value)
    return result
