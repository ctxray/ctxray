"""Merge View — group similar prompts into clusters with canonical selection."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from reprompt.core.library import categorize_prompt

_FILE_REF_RE = re.compile(r"\w+\.\w{1,4}\b")
_FUNC_REF_RE = re.compile(r"\w+\(\)")
_LINE_REF_RE = re.compile(r"line\s+\d+", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")


def _normalize_text(text: str) -> str:
    """Stem words to 4-char prefixes, preserving file references."""
    words = _WORD_RE.findall(text.lower())
    return " ".join(w if "." in w or len(w) <= 4 else w[:4] for w in words)


def _compute_similarity_matrix(texts: list[str]) -> np.ndarray:
    """Compute blended similarity: 60% TF-IDF cosine on stemmed text + 40% containment."""
    normed = [_normalize_text(t) for t in texts]
    vectorizer = TfidfVectorizer(max_features=5000, sublinear_tf=True)
    tfidf_matrix = vectorizer.fit_transform(normed)
    cos_sim = sklearn_cosine(tfidf_matrix)

    n = len(texts)
    enhanced: np.ndarray = cos_sim.copy()
    for i in range(n):
        for j in range(i + 1, n):
            words_i = set(normed[i].split())
            words_j = set(normed[j].split())
            shorter = words_i if len(words_i) <= len(words_j) else words_j
            longer = words_j if len(words_i) <= len(words_j) else words_i
            containment = len(shorter & longer) / len(shorter) if shorter else 0.0
            blended = 0.6 * cos_sim[i][j] + 0.4 * containment
            enhanced[i][j] = blended
            enhanced[j][i] = blended

    return enhanced


def score_prompt(
    text: str,
    cluster_texts: list[str],
    effectiveness: float = 0.5,
) -> float:
    """Score a prompt for canonical selection.

    Composite: 50% normalized length + 30% specific refs + 20% effectiveness.
    """
    lengths = [len(t) for t in cluster_texts]
    min_len = min(lengths)
    max_len = max(lengths)
    if max_len == min_len:
        len_score = 1.0
    else:
        len_score = (len(text) - min_len) / (max_len - min_len)

    ref_score = 0.0
    if _FILE_REF_RE.search(text):
        ref_score += 0.5
    if _FUNC_REF_RE.search(text):
        ref_score += 0.3
    if _LINE_REF_RE.search(text):
        ref_score += 0.2

    return 0.5 * len_score + 0.3 * ref_score + 0.2 * effectiveness


def name_cluster(canonical_text: str, category: str) -> str:
    """Auto-generate a cluster name from category + key terms."""
    cat_label = category.capitalize()
    stop = {"the", "a", "an", "in", "on", "to", "for", "is", "it", "and", "or", "of", "with"}
    words = [w for w in canonical_text.lower().split() if w not in stop and len(w) > 2]
    key_words = " ".join(words[:3]).title()
    return f"{cat_label}: {key_words}" if key_words else cat_label


def build_clusters(
    texts: list[str],
    timestamps: list[str],
    threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Build similarity clusters from prompt texts.

    Returns list of cluster dicts sorted by size descending.
    """
    if len(texts) < 2:
        return []

    sim_matrix = _compute_similarity_matrix(texts)

    adj: dict[int, set[int]] = {i: set() for i in range(len(texts))}
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if sim_matrix[i][j] >= threshold:
                adj[i].add(j)
                adj[j].add(i)

    visited: set[int] = set()
    components: list[list[int]] = []
    for i in range(len(texts)):
        if i in visited or not adj[i]:
            continue
        component: list[int] = []
        queue = [i]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= 2:
            components.append(sorted(component))

    clusters: list[dict[str, Any]] = []
    for cid, component in enumerate(components):
        cluster_texts = [texts[i] for i in component]
        cluster_timestamps = [timestamps[i] for i in component]

        scored = []
        for t, ts in zip(cluster_texts, cluster_timestamps):
            s = score_prompt(t, cluster_texts)
            scored.append({"text": t, "timestamp": ts, "score": round(s, 2)})

        scored.sort(key=lambda x: -x["score"])
        canonical = scored[0]
        category = categorize_prompt(canonical["text"])

        clusters.append(
            {
                "id": cid,
                "name": name_cluster(canonical["text"], category),
                "size": len(component),
                "canonical": {"text": canonical["text"], "score": canonical["score"]},
                "members": scored[1:],
            }
        )

    clusters.sort(key=lambda c: -c["size"])
    for i, c in enumerate(clusters):
        c["id"] = i

    return clusters
