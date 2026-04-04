"""OpenAI embedding backend (optional).

Requires the 'openai' package.
Install with: pip install ctxray[openai]
"""

from __future__ import annotations

import os

import numpy as np

from .base import BaseEmbedder

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]


class OpenAIEmbedder(BaseEmbedder):
    """Embedding backend using the OpenAI embeddings API.

    Requires the 'openai' package
    (install with: pip install ctxray[openai]).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
            if not self.api_key:
                raise ValueError(
                    "No API key provided. Pass api_key= or set the OPENAI_API_KEY "
                    "environment variable."
                )

    def embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts via the OpenAI embeddings API."""
        if not texts:
            return np.array([])

        if OpenAI is None:
            raise ImportError(
                "openai is required for the OpenAI embedding backend. "
                "Install with: pip install ctxray[openai]"
            )

        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(input=texts, model=self.model)
        vectors = [item.embedding for item in response.data]
        return np.array(vectors)
