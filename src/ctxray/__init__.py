"""ctxray — Discover, analyze, and evolve your best prompts from AI coding sessions."""

__version__ = "2.5.0"

__all__ = [
    "__version__",
    # Core analysis
    "score_prompt",
    "compare_prompts",
    "extract_features",
    # Data access
    "PromptDB",
    "Prompt",
    "PromptDNA",
]


def _grade(total: float) -> str:
    """Map 0-100 score to letter grade."""
    if total >= 85:
        return "A"
    if total >= 60:
        return "B"
    if total >= 40:
        return "C"
    if total >= 25:
        return "D"
    return "F"


def score_prompt(text: str) -> dict:
    """Score a prompt and return breakdown dict. Public API."""
    from ctxray.core.extractors import extract_features as _extract
    from ctxray.core.scorer import score_prompt as _score

    dna = _extract(text, source="api", session_id="")
    breakdown = _score(dna)
    return {
        "total": breakdown.total,
        "dimensions": {
            "structure": breakdown.structure,
            "context": breakdown.context,
            "position": breakdown.position,
            "repetition": breakdown.repetition,
            "clarity": breakdown.clarity,
        },
        "grade": _grade(breakdown.total),
    }


def compare_prompts(a: str, b: str) -> dict:
    """Compare two prompts and return comparison dict. Public API."""
    from ctxray.core.extractors import extract_features as _extract
    from ctxray.core.scorer import score_prompt as _score

    dna_a = _extract(a, source="api", session_id="")
    dna_b = _extract(b, source="api", session_id="")
    score_a = _score(dna_a)
    score_b = _score(dna_b)
    return {
        "a": score_a.total,
        "b": score_b.total,
        "winner": "a" if score_a.total >= score_b.total else "b",
    }


def extract_features(text: str):
    """Extract PromptDNA features. Public API."""
    from ctxray.core.extractors import extract_features as _extract

    return _extract(text, source="api", session_id="")


# Lazy imports for type access
def __getattr__(name):
    if name == "PromptDB":
        from ctxray.storage.db import PromptDB

        return PromptDB
    if name == "Prompt":
        from ctxray.core.models import Prompt

        return Prompt
    if name == "PromptDNA":
        from ctxray.core.prompt_dna import PromptDNA

        return PromptDNA
    raise AttributeError(f"module 'ctxray' has no attribute {name!r}")
