"""Tests for OpenAI embedding backend (mocked API)."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture()
def _mock_openai():
    """Mock the openai package so OpenAIEmbedder can be imported without the real package."""
    mock_module = MagicMock()
    with patch.dict(sys.modules, {"openai": mock_module}):
        yield mock_module


@pytest.fixture()
def _openai_embedder_cls(_mock_openai):
    """Import OpenAIEmbedder with mocked openai."""
    mod_key = "ctxray.embeddings.openai_embed"
    sys.modules.pop(mod_key, None)
    from ctxray.embeddings.openai_embed import OpenAIEmbedder

    return OpenAIEmbedder


def _make_mock_response(embeddings: list[list[float]]) -> MagicMock:
    """Helper to create a mock OpenAI embeddings response."""
    mock_data = []
    for emb in embeddings:
        mock_emb = MagicMock()
        mock_emb.embedding = emb
        mock_data.append(mock_emb)
    mock_response = MagicMock()
    mock_response.data = mock_data
    return mock_response


def test_embed_returns_correct_shape(_openai_embedder_cls, _mock_openai):
    embedder = _openai_embedder_cls(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _make_mock_response([[0.1, 0.2, 0.3]])
    _mock_openai.OpenAI.return_value = mock_client
    result = embedder.embed(["hello world"])
    assert result.shape == (1, 3)


def test_embed_multiple_texts(_openai_embedder_cls, _mock_openai):
    embedder = _openai_embedder_cls(api_key="sk-test")
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _make_mock_response(
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    )
    _mock_openai.OpenAI.return_value = mock_client
    result = embedder.embed(["hello", "world"])
    assert result.shape == (2, 3)


def test_embed_calls_api_with_correct_params(_openai_embedder_cls, _mock_openai):
    embedder = _openai_embedder_cls(model="text-embedding-3-small", api_key="sk-test")
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _make_mock_response([[0.1, 0.2]])
    _mock_openai.OpenAI.return_value = mock_client
    embedder.embed(["test text"])
    mock_client.embeddings.create.assert_called_once_with(
        input=["test text"], model="text-embedding-3-small"
    )


def test_default_model(_openai_embedder_cls):
    embedder = _openai_embedder_cls(api_key="sk-test")
    assert embedder.model == "text-embedding-3-small"


def test_custom_model(_openai_embedder_cls):
    embedder = _openai_embedder_cls(model="text-embedding-ada-002", api_key="sk-test")
    assert embedder.model == "text-embedding-ada-002"


def test_api_key_from_env_var(_openai_embedder_cls):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-from-env"}):
        embedder = _openai_embedder_cls()
        assert embedder.api_key == "sk-from-env"


def test_api_key_explicit_overrides_env(_openai_embedder_cls):
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-from-env"}):
        embedder = _openai_embedder_cls(api_key="sk-explicit")
        assert embedder.api_key == "sk-explicit"


def test_no_api_key_raises_value_error(_openai_embedder_cls):
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _openai_embedder_cls()


def test_embed_empty_list(_openai_embedder_cls):
    embedder = _openai_embedder_cls(api_key="sk-test")
    result = embedder.embed([])
    assert result.size == 0


def test_inherits_cosine_similarity(_openai_embedder_cls):
    embedder = _openai_embedder_cls(api_key="sk-test")
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert embedder.cosine_similarity(a, b) == 0.0

    c = np.array([1.0, 0.0])
    d = np.array([1.0, 0.0])
    assert abs(embedder.cosine_similarity(c, d) - 1.0) < 1e-6


def test_import_error_when_not_installed():
    """When openai is not installed, ImportError should be helpful."""
    mod_key = "ctxray.embeddings.openai_embed"
    sys.modules.pop(mod_key, None)

    with patch.dict(sys.modules, {"openai": None}):
        from ctxray.embeddings.openai_embed import OpenAIEmbedder

        embedder = OpenAIEmbedder(api_key="sk-test")
        with pytest.raises(ImportError, match="pip install ctxray\\[openai\\]"):
            embedder.embed(["test"])

    # Clean up
    sys.modules.pop(mod_key, None)
