"""Local embedding backend using sentence-transformers (optional).

Requires the 'sentence-transformers' package.
Install with: pip install ctxray[local]
"""

from __future__ import annotations

import numpy as np

from .base import BaseEmbedder

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment, misc]


class LocalEmbedder(BaseEmbedder):
    """Embedding backend using sentence-transformers for local inference.

    Requires the 'sentence-transformers' package
    (install with: pip install ctxray[local]).
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts using a local sentence-transformers model."""
        if not texts:
            return np.array([])

        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is required for the local embedding backend. "
                "Install with: pip install ctxray[local]"
            )

        if self._model is None:
            self._model = SentenceTransformer(self.model_name)

        result = self._model.encode(texts)
        return np.asarray(result)
