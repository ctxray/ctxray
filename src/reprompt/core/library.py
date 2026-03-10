"""Prompt pattern extraction and categorization."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Keyword-based categorization rules (order matters -- first match wins)
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("review", ["review", "audit", "inspect", "examine"]),
    ("debug", ["fix", "debug", "error", "bug", "failing", "broken", "crash", "issue"]),
    ("test", ["test", "spec", "coverage", "assert", "mock"]),
    ("implement", ["add", "implement", "create", "build", "new", "feature", "endpoint"]),
    ("refactor", ["refactor", "restructure", "reorganize", "clean", "simplify", "extract"]),
    ("explain", ["explain", "how does", "what is", "describe", "understand", "why"]),
    ("config", ["config", "configure", "setup", "set up", "install", "deploy", "ci", "cd"]),
]


def categorize_prompt(text: str) -> str:
    """Categorize a prompt using keyword matching. Returns category string."""
    lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


def extract_patterns(
    prompts: list[str],
    min_frequency: int = 3,
    similarity_threshold: float = 0.5,
) -> list[dict]:
    """Extract high-frequency prompt patterns from a list of prompt texts.

    Groups similar prompts using TF-IDF cosine similarity, picks representative text,
    counts frequency, computes avg length, auto-categorizes.

    Returns list of pattern dicts:
    [{"pattern_text": str, "frequency": int, "avg_length": float,
      "category": str, "examples": list[str]}]
    """
    if not prompts:
        return []

    # Build TF-IDF matrix
    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(prompts)

    # Compute pairwise similarities
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Greedy clustering: assign each prompt to first sufficiently-similar group
    used: set[int] = set()
    groups: list[list[int]] = []

    for i in range(len(prompts)):
        if i in used:
            continue
        group = [i]
        used.add(i)
        for j in range(i + 1, len(prompts)):
            if j in used:
                continue
            if sim_matrix[i][j] >= similarity_threshold:
                group.append(j)
                used.add(j)
        groups.append(group)

    # Filter by min_frequency and build pattern dicts
    patterns = []
    for group in groups:
        if len(group) < min_frequency:
            continue
        group_texts = [prompts[i] for i in group]
        representative = group_texts[0]  # first occurrence as representative
        patterns.append(
            {
                "pattern_text": representative,
                "frequency": len(group),
                "avg_length": sum(len(t) for t in group_texts) / len(group_texts),
                "category": categorize_prompt(representative),
                "examples": group_texts[:5],  # keep up to 5 examples
            }
        )

    patterns.sort(key=lambda x: x["frequency"], reverse=True)
    return patterns
