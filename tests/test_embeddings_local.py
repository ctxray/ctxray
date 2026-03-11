"""Tests for local sentence-transformers embedding backend (mocked)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture()
def _mock_sentence_transformers():
    """Mock sentence_transformers so LocalEmbedder can be imported without the real package."""
    mock_module = MagicMock()
    with patch.dict(sys.modules, {"sentence_transformers": mock_module}):
        yield mock_module


@pytest.fixture()
def _local_embedder_cls(_mock_sentence_transformers):
    """Import LocalEmbedder with mocked sentence_transformers."""
    # Force reimport so the module picks up the mock
    mod_key = "reprompt.embeddings.local_embed"
    sys.modules.pop(mod_key, None)
    from reprompt.embeddings.local_embed import LocalEmbedder

    return LocalEmbedder


def test_embed_returns_correct_shape(_local_embedder_cls, _mock_sentence_transformers):
    embedder = _local_embedder_cls(model_name="all-MiniLM-L6-v2")
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
    _mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    result = embedder.embed(["hello world"])
    assert result.shape == (1, 3)


def test_embed_multiple_texts(_local_embedder_cls, _mock_sentence_transformers):
    embedder = _local_embedder_cls()
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    _mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    result = embedder.embed(["hello", "world"])
    assert result.shape == (2, 3)
    mock_model.encode.assert_called_once_with(["hello", "world"])


def test_embed_passes_texts_to_model(_local_embedder_cls, _mock_sentence_transformers):
    embedder = _local_embedder_cls()
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2]])
    _mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    embedder.embed(["test text"])
    mock_model.encode.assert_called_once_with(["test text"])


def test_default_model_name(_local_embedder_cls):
    embedder = _local_embedder_cls()
    assert embedder.model_name == "all-MiniLM-L6-v2"


def test_custom_model_name(_local_embedder_cls):
    embedder = _local_embedder_cls(model_name="paraphrase-MiniLM-L6-v2")
    assert embedder.model_name == "paraphrase-MiniLM-L6-v2"


def test_embed_empty_list(_local_embedder_cls):
    embedder = _local_embedder_cls()
    result = embedder.embed([])
    assert result.size == 0


def test_inherits_cosine_similarity(_local_embedder_cls):
    embedder = _local_embedder_cls()
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert embedder.cosine_similarity(a, b) == 0.0

    c = np.array([1.0, 0.0])
    d = np.array([1.0, 0.0])
    assert abs(embedder.cosine_similarity(c, d) - 1.0) < 1e-6


def test_model_loaded_lazily(_local_embedder_cls, _mock_sentence_transformers):
    """Model should be loaded on first embed(), not on __init__."""
    _mock_sentence_transformers.SentenceTransformer.reset_mock()
    embedder = _local_embedder_cls()
    _mock_sentence_transformers.SentenceTransformer.assert_not_called()

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1]])
    _mock_sentence_transformers.SentenceTransformer.return_value = mock_model
    embedder.embed(["test"])
    _mock_sentence_transformers.SentenceTransformer.assert_called_once_with("all-MiniLM-L6-v2")


def test_import_error_when_not_installed():
    """When sentence_transformers is not installed, ImportError should be helpful."""
    # Remove any cached import of the module
    mod_key = "reprompt.embeddings.local_embed"
    sys.modules.pop(mod_key, None)

    with patch.dict(sys.modules, {"sentence_transformers": None}):
        from reprompt.embeddings.local_embed import LocalEmbedder

        embedder = LocalEmbedder()
        with pytest.raises(ImportError, match="pip install reprompt-cli\\[local\\]"):
            embedder.embed(["test"])

    # Clean up
    sys.modules.pop(mod_key, None)
