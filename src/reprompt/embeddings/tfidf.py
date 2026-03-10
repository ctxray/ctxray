"""TF-IDF embedding backend using scikit-learn."""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .base import BaseEmbedder


class TfidfEmbedder(BaseEmbedder):
    """TF-IDF vectorizer that converts texts to dense numpy arrays."""

    def __init__(self, max_features: int = 5000) -> None:
        self._vectorizer = TfidfVectorizer(max_features=max_features)

    def embed(self, texts: list[str]) -> np.ndarray:
        """Fit and transform texts into TF-IDF vectors."""
        if not texts:
            return np.array([])
        return self._vectorizer.fit_transform(texts).toarray()
