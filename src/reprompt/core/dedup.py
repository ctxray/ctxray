"""Two-layer deduplication engine.

L0: SHA-256 exact hash dedup (always runs)
L1: TF-IDF cosine similarity dedup (runs on hash-unique prompts)
"""

from __future__ import annotations

from reprompt.core.models import Prompt
from reprompt.embeddings.base import BaseEmbedder


def _get_embedder(backend: str, ollama_url: str = "http://localhost:11434") -> BaseEmbedder:
    """Factory function to create an embedder by name."""
    if backend == "tfidf":
        from reprompt.embeddings.tfidf import TfidfEmbedder

        return TfidfEmbedder()
    elif backend == "ollama":
        from reprompt.embeddings.ollama import OllamaEmbedder

        return OllamaEmbedder(url=ollama_url)
    elif backend == "local":
        from reprompt.embeddings.local_embed import LocalEmbedder

        return LocalEmbedder()
    elif backend == "openai":
        from reprompt.embeddings.openai_embed import OpenAIEmbedder

        return OpenAIEmbedder()
    else:
        raise ValueError(f"Unknown embedding backend: {backend}")


class DedupEngine:
    """Two-layer deduplication: exact hash then semantic similarity."""

    def __init__(
        self,
        backend: str = "tfidf",
        threshold: float = 0.85,
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self._backend = backend
        self._threshold = threshold
        self._ollama_url = ollama_url

    def deduplicate(self, prompts: list[Prompt]) -> tuple[list[Prompt], list[Prompt]]:
        """Deduplicate prompts using hash then semantic similarity.

        Returns:
            (unique_prompts, duplicate_prompts)
        """
        if not prompts:
            return [], []

        # L0: Exact hash dedup -- keep first occurrence per hash
        seen_hashes: dict[str, int] = {}
        hash_unique: list[Prompt] = []
        hash_dupes: list[Prompt] = []

        for prompt in prompts:
            if prompt.hash in seen_hashes:
                hash_dupes.append(prompt)
            else:
                seen_hashes[prompt.hash] = len(hash_unique)
                hash_unique.append(prompt)

        # L1: Semantic dedup on hash-unique prompts
        if len(hash_unique) < 2:
            return hash_unique, hash_dupes

        embedder = _get_embedder(self._backend, ollama_url=self._ollama_url)
        texts = [p.text for p in hash_unique]
        embeddings = embedder.embed(texts)

        if embeddings.size == 0:
            return hash_unique, hash_dupes

        # Mark semantic duplicates (later items are dupes of earlier ones)
        is_dupe = [False] * len(hash_unique)

        for i in range(len(hash_unique)):
            if is_dupe[i]:
                continue
            for j in range(i + 1, len(hash_unique)):
                if is_dupe[j]:
                    continue
                sim = embedder.cosine_similarity(embeddings[i], embeddings[j])
                if sim >= self._threshold:
                    is_dupe[j] = True

        semantic_unique: list[Prompt] = []
        semantic_dupes: list[Prompt] = []

        for idx, prompt in enumerate(hash_unique):
            if is_dupe[idx]:
                semantic_dupes.append(prompt)
            else:
                semantic_unique.append(prompt)

        all_dupes = hash_dupes + semantic_dupes
        return semantic_unique, all_dupes
