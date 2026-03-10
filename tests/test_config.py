"""Tests for reprompt configuration module."""
from reprompt.config import Settings


def test_default_settings():
    s = Settings()
    assert s.embedding_backend == "tfidf"
    assert s.dedup_threshold == 0.85
    assert s.library_min_frequency == 3
    assert "reprompt" in str(s.db_path).lower()


def test_env_override(monkeypatch):
    monkeypatch.setenv("REPROMPT_EMBEDDING_BACKEND", "ollama")
    s = Settings()
    assert s.embedding_backend == "ollama"


def test_db_path_expanduser():
    s = Settings()
    assert "~" not in str(s.db_path)
