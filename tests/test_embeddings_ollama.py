"""Tests for Ollama embedding backend (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

requests = pytest.importorskip("requests")

from ctxray.embeddings.ollama import OllamaEmbedder  # noqa: E402


def test_embed_calls_api():
    embedder = OllamaEmbedder(url="http://localhost:11434")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = embedder.embed(["hello world"])
        assert result.shape == (1, 3)
        mock_post.assert_called_once()


def test_embed_multiple_texts():
    embedder = OllamaEmbedder(url="http://localhost:11434")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
    with patch("requests.post", return_value=mock_resp):
        result = embedder.embed(["hello", "world"])
        assert result.shape == (2, 3)


def test_embed_sends_correct_payload():
    embedder = OllamaEmbedder(url="http://localhost:11434", model="nomic-embed-text")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [[0.1, 0.2]]}
    with patch("requests.post", return_value=mock_resp) as mock_post:
        embedder.embed(["test text"])
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "nomic-embed-text"
        assert call_args[1]["json"]["input"] == ["test text"]


def test_is_available_true():
    embedder = OllamaEmbedder(url="http://localhost:11434")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        assert embedder.is_available()


def test_is_available_false():
    embedder = OllamaEmbedder(url="http://localhost:11434")
    with patch("requests.get", side_effect=Exception("connection refused")):
        assert not embedder.is_available()


def test_embed_empty_list():
    embedder = OllamaEmbedder(url="http://localhost:11434")
    result = embedder.embed([])
    assert result.size == 0


def test_url_trailing_slash_stripped():
    embedder = OllamaEmbedder(url="http://localhost:11434/")
    assert embedder.url == "http://localhost:11434"


def test_default_model():
    embedder = OllamaEmbedder()
    assert embedder.model == "nomic-embed-text"


def test_inherits_cosine_similarity():
    embedder = OllamaEmbedder()
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert embedder.cosine_similarity(a, b) == 0.0

    c = np.array([1.0, 0.0])
    d = np.array([1.0, 0.0])
    assert abs(embedder.cosine_similarity(c, d) - 1.0) < 1e-6


def test_embed_connection_error_raises_runtime_error():
    """ConnectionError during embed() should raise RuntimeError with helpful message."""
    embedder = OllamaEmbedder(url="http://localhost:11434")
    with patch("requests.post", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            embedder.embed(["hello world"])


def test_embed_timeout_raises_runtime_error():
    """Timeout during embed() should raise RuntimeError with helpful message."""
    embedder = OllamaEmbedder(url="http://localhost:11434")
    with patch("requests.post", side_effect=requests.Timeout("timed out")):
        with pytest.raises(RuntimeError, match="Cannot connect to Ollama"):
            embedder.embed(["hello world"])
