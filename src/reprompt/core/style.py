"""Personal prompting style fingerprint.

Computes a statistical profile from the user's prompt history:
- Average length, length distribution
- Preferred categories
- Opening word patterns
- Specificity score (based on file refs, function names, constraints)

Pure analysis, no LLM needed.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Patterns that indicate specificity
_FILE_REF = re.compile(r"[\w/]+\.\w{1,5}")  # file.py, path/to/file.ts
_FUNC_REF = re.compile(r"\b\w+\(\)")  # function()
_CONSTRAINT = re.compile(
    r"\b(must|should|do not|don't|ensure|require|limit|max|min|only|never|always)\b",
    re.IGNORECASE,
)
_ERROR_REF = re.compile(r"\b\w*(Error|Exception|Fault|Failure|Timeout)\b")


def compute_style(prompts: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute personal prompting style from prompt history.

    Each prompt dict should have: text, category, char_count.

    Returns:
        prompt_count, avg_length, top_category, top_category_pct,
        category_distribution, opening_patterns, specificity,
        length_distribution.
    """
    if not prompts:
        return {
            "prompt_count": 0,
            "avg_length": 0,
            "top_category": "none",
            "top_category_pct": 0.0,
            "category_distribution": {},
            "opening_patterns": [],
            "specificity": 0.0,
            "length_distribution": {"short": 0, "medium": 0, "long": 0, "very_long": 0},
        }

    count = len(prompts)
    lengths = [p.get("char_count", len(p.get("text", ""))) for p in prompts]
    avg_length = sum(lengths) / count

    # Category distribution
    categories = [p.get("category", "other") for p in prompts]
    cat_counts = Counter(categories)
    top_cat, top_count = cat_counts.most_common(1)[0]

    # Opening word patterns (first word of each prompt)
    openers: list[str] = []
    for p in prompts:
        words = p.get("text", "").strip().split()
        if words:
            openers.append(words[0].lower().rstrip(",:;"))
    opener_counts = Counter(openers)
    opening_patterns = [
        {"word": word, "count": c, "pct": round(c / count, 2)}
        for word, c in opener_counts.most_common(5)
    ]

    # Specificity score: fraction of prompts with specific references
    specificity_hits = 0
    for p in prompts:
        text = p.get("text", "")
        has_specific = (
            bool(_FILE_REF.search(text))
            or bool(_FUNC_REF.search(text))
            or bool(_CONSTRAINT.search(text))
            or bool(_ERROR_REF.search(text))
            or len(text) > 60
        )
        if has_specific:
            specificity_hits += 1
    specificity = specificity_hits / count

    # Length distribution
    length_dist = {"short": 0, "medium": 0, "long": 0, "very_long": 0}
    for ln in lengths:
        if ln < 30:
            length_dist["short"] += 1
        elif ln < 80:
            length_dist["medium"] += 1
        elif ln < 200:
            length_dist["long"] += 1
        else:
            length_dist["very_long"] += 1

    return {
        "prompt_count": count,
        "avg_length": round(avg_length, 1),
        "top_category": top_cat,
        "top_category_pct": round(top_count / count, 2),
        "category_distribution": dict(cat_counts),
        "opening_patterns": opening_patterns,
        "specificity": round(specificity, 2),
        "length_distribution": length_dist,
    }
