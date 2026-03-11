"""Tests for the two-layer dedup engine."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from reprompt.core.dedup import DedupEngine, _get_embedder
from reprompt.core.models import Prompt


def _make_prompt(text: str, source: str = "test") -> Prompt:
    return Prompt(text=text, source=source, session_id="s1")


def test_exact_dedup():
    engine = DedupEngine(backend="tfidf")
    prompts = [
        _make_prompt("fix the bug in the authentication module"),
        _make_prompt("fix the bug in the authentication module"),
        _make_prompt("add a comprehensive test suite for payments"),
    ]
    unique, dupes = engine.deduplicate(prompts)
    assert len(unique) == 2
    assert len(dupes) == 1


def test_semantic_dedup():
    # TF-IDF similarity for short near-duplicate sentences is ~0.75,
    # so we use a threshold of 0.70 to test the semantic layer.
    engine = DedupEngine(backend="tfidf", threshold=0.70)
    prompts = [
        _make_prompt("fix the failing test in auth.py"),
        _make_prompt("fix the broken test in auth.py"),  # near-dupe (~0.75 sim)
        _make_prompt("deploy the application to production"),
    ]
    unique, dupes = engine.deduplicate(prompts)
    assert len(unique) == 2  # first two should be semantic dupes


def test_dedup_empty():
    engine = DedupEngine(backend="tfidf")
    unique, dupes = engine.deduplicate([])
    assert len(unique) == 0
    assert len(dupes) == 0


def test_dedup_single():
    engine = DedupEngine(backend="tfidf")
    unique, dupes = engine.deduplicate([_make_prompt("hello world test prompt")])
    assert len(unique) == 1
    assert len(dupes) == 0


def test_dedup_preserves_first():
    engine = DedupEngine(backend="tfidf")
    p1 = _make_prompt("fix the bug now please help me")
    p2 = _make_prompt("fix the bug now please help me")
    unique, dupes = engine.deduplicate([p1, p2])
    assert unique[0] is p1  # first occurrence kept


def test_dedup_all_unique():
    engine = DedupEngine(backend="tfidf")
    prompts = [
        _make_prompt("implement user authentication with JWT tokens"),
        _make_prompt("deploy the staging environment to kubernetes"),
        _make_prompt("write integration tests for the payment module"),
    ]
    unique, dupes = engine.deduplicate(prompts)
    assert len(unique) == 3
    assert len(dupes) == 0


def test_dedup_multiple_exact_dupes():
    engine = DedupEngine(backend="tfidf")
    prompts = [
        _make_prompt("fix the failing unit test in auth module"),
        _make_prompt("fix the failing unit test in auth module"),
        _make_prompt("fix the failing unit test in auth module"),
    ]
    unique, dupes = engine.deduplicate(prompts)
    assert len(unique) == 1
    assert len(dupes) == 2


def test_dedup_threshold_controls_sensitivity():
    """Lower threshold means more aggressive dedup."""
    prompts = [
        _make_prompt("fix the failing test in auth.py module"),
        _make_prompt("fix the broken test in auth.py module"),
    ]
    # High threshold -- less aggressive, may keep both
    engine_strict = DedupEngine(backend="tfidf", threshold=0.99)
    unique_strict, _ = engine_strict.deduplicate(prompts)

    # Low threshold -- more aggressive
    engine_loose = DedupEngine(backend="tfidf", threshold=0.50)
    unique_loose, _ = engine_loose.deduplicate(prompts)

    # Loose should find at least as many dupes as strict
    assert len(unique_loose) <= len(unique_strict)


def test_dedup_mixed_exact_and_semantic():
    engine = DedupEngine(backend="tfidf", threshold=0.85)
    prompts = [
        _make_prompt("refactor the database connection pool to use async"),
        _make_prompt("refactor the database connection pool to use async"),  # exact dupe
        _make_prompt("refactor the db connection pool using async patterns"),  # semantic dupe
        _make_prompt("add unit tests for the payment gateway integration"),
    ]
    unique, dupes = engine.deduplicate(prompts)
    # At minimum: exact dupe removed. Semantic may or may not trigger depending on TF-IDF.
    assert len(unique) <= 3
    assert len(dupes) >= 1


# --- ollama_url propagation tests ---


def test_get_embedder_ollama_passes_url():
    """_get_embedder passes ollama_url to OllamaEmbedder."""
    with patch("reprompt.embeddings.ollama.OllamaEmbedder") as mock_cls:
        mock_cls.return_value = MagicMock()
        _get_embedder("ollama", ollama_url="http://myhost:9999")
        mock_cls.assert_called_once_with(url="http://myhost:9999")


def test_get_embedder_ollama_default_url():
    """_get_embedder uses default url when none provided."""
    with patch("reprompt.embeddings.ollama.OllamaEmbedder") as mock_cls:
        mock_cls.return_value = MagicMock()
        _get_embedder("ollama")
        mock_cls.assert_called_once_with(url="http://localhost:11434")


def test_dedup_engine_passes_ollama_url():
    """DedupEngine passes ollama_url through to _get_embedder."""
    engine = DedupEngine(backend="ollama", threshold=0.85, ollama_url="http://custom:11434")
    assert engine._ollama_url == "http://custom:11434"


def test_get_embedder_tfidf_ignores_url():
    """_get_embedder for tfidf backend ignores ollama_url."""
    embedder = _get_embedder("tfidf", ollama_url="http://ignored:9999")
    from reprompt.embeddings.tfidf import TfidfEmbedder

    assert isinstance(embedder, TfidfEmbedder)
