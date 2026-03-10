"""Ollama embedding backend (optional, requires requests)."""

from __future__ import annotations

import numpy as np

from .base import BaseEmbedder


class OllamaEmbedder(BaseEmbedder):
    """Embedding backend using Ollama's /api/embed endpoint.

    Requires the 'requests' package (install with: pip install reprompt[ollama]).
    """

    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts via Ollama API."""
        if not texts:
            return np.array([])

        import requests

        resp = requests.post(
            f"{self.url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return np.array(data["embeddings"])

    def is_available(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            import requests

            resp = requests.get(f"{self.url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
