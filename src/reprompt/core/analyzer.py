"""TF-IDF analysis and K-means clustering."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

# Generic terms that saturate coding prompt corpora and carry no analytical signal.
# Derived from: arXiv:2303.10439 (SE stop words), prompt engineering guides,
# and analysis of AI coding assistant interaction patterns.
_CODING_STOP_WORDS: frozenset[str] = frozenset(
    {
        # --- Generic instruction verbs (appear in nearly every coding prompt) ---
        "write", "create", "implement", "build", "make", "generate", "produce", "develop",
        "add", "update", "modify", "change", "fix", "refactor", "rewrite", "convert",
        "check", "verify", "test", "debug", "review", "analyze", "optimize", "improve",
        "remove", "delete", "replace", "rename", "setup", "configure",
        # --- Generic programming structure nouns ---
        "function", "method", "class", "object", "module", "package", "library",
        "variable", "constant", "parameter", "argument", "attribute", "property", "field",
        "type", "interface", "struct", "trait", "protocol",
        # --- Generic data type nouns ---
        "string", "integer", "float", "boolean", "number", "char", "byte",
        "null", "nil", "none", "undefined", "void",
        # --- Generic collection nouns ---
        "array", "list", "dict", "dictionary", "map", "set", "tuple", "vector",
        # --- Generic code/project structure ---
        "code", "file", "directory", "folder", "path", "project", "repo", "codebase",
        "script", "program", "source", "line", "block", "scope",
        # --- Generic I/O and execution verbs ---
        "run", "execute", "call", "invoke", "return", "output", "print", "display",
        "render", "parse", "process", "handle", "validate", "transform",
        "load", "save", "store", "fetch", "retrieve", "send", "receive",
        "read", "import", "export",
        # --- LeetCode / algorithm template words ---
        "given", "input", "output", "expected", "constraints", "assume",
        "ascending", "descending", "sorted", "optimal", "brute",
        # --- AI assistant interaction boilerplate ---
        "please", "thanks", "help", "explain", "provide", "ensure",
        "following", "example", "basically", "simply", "just", "actually",
        # --- High-frequency SE terms (arXiv:2303.10439) ---
        "use", "using", "used", "want", "work", "working", "need", "try",
        "like", "get", "know", "new", "possible", "specific", "simple",
        "right", "correct", "good", "better", "best", "sure",
    }
)

# Merged stop word set: English + coding domain
STOP_WORDS: frozenset[str] = ENGLISH_STOP_WORDS | _CODING_STOP_WORDS


def _is_noise_phrase(term: str) -> bool:
    """Filter out path fragments, usernames, and other noise from TF-IDF results."""
    noise_tokens = {"users", "chris", "projects", "home", "usr", "var", "tmp", "src", "py"}
    words = set(term.lower().split())
    # Skip if majority of words are path/noise tokens
    if len(words & noise_tokens) >= len(words) * 0.5:
        return True
    return False


def compute_tfidf_stats(texts: list[str], top_n: int = 20) -> list[dict[str, Any]]:
    """Compute TF-IDF stats on meaningful multi-word phrases.

    Uses bigrams and trigrams (2-3 word phrases) with English stop words removed,
    so results like "unit tests" or "fix authentication bug" appear instead of
    single words like "the" or "fix".

    Returns list of dicts: [{"term": str, "count": int, "df": int, "tfidf_avg": float}]
    """
    if not texts:
        return []

    # Pre-process: strip file paths from texts to avoid path fragment n-grams
    import re

    path_re = re.compile(r"[~/][\w./-]{10,}")
    cleaned = [path_re.sub("", t) for t in texts]

    # Try n-grams first (meaningful phrases), fall back to unigrams for small datasets
    min_df = 2 if len(cleaned) >= 10 else 1
    try:
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(2, 3),
            stop_words=list(STOP_WORDS),
            min_df=min_df,
        )
        tfidf_matrix = vectorizer.fit_transform(cleaned)
        feature_names = vectorizer.get_feature_names_out()
    except ValueError:
        feature_names = np.array([])

    if len(feature_names) == 0:
        # Fallback to unigrams if not enough data for n-grams
        vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words=list(STOP_WORDS),
        )
        tfidf_matrix = vectorizer.fit_transform(cleaned)
        feature_names = vectorizer.get_feature_names_out()

    # Average TF-IDF score per term across all documents
    avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

    # Document frequency (number of docs containing each term)
    df = np.asarray((tfidf_matrix > 0).sum(axis=0)).flatten()

    # Sum of TF-IDF weights (approximate count)
    count = np.asarray(tfidf_matrix.sum(axis=0)).flatten()

    results = []
    for i, term in enumerate(feature_names):
        if _is_noise_phrase(term):
            continue
        results.append(
            {
                "term": term,
                "count": int(count[i] * len(texts)),
                "df": int(df[i]),
                "tfidf_avg": float(avg_scores[i]),
            }
        )

    results.sort(key=lambda x: x["tfidf_avg"], reverse=True)
    return results[:top_n]


def cluster_prompts(texts: list[str], n_clusters: int = 5) -> dict[int, list[str]]:
    """Cluster prompts using K-means on TF-IDF vectors.

    Returns {cluster_id: [texts]}
    """
    if not texts:
        return {}

    n_clusters = min(n_clusters, len(texts))

    vectorizer = TfidfVectorizer(max_features=5000, stop_words=list(STOP_WORDS))
    tfidf_matrix = vectorizer.fit_transform(texts)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(tfidf_matrix)

    clusters: dict[int, list[str]] = {}
    for text, label in zip(texts, labels):
        clusters.setdefault(int(label), []).append(text)

    return clusters
