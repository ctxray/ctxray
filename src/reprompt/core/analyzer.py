"""TF-IDF analysis and K-means clustering."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import Normalizer

# Generic terms that saturate coding prompt corpora and carry no analytical signal.
# Derived from: arXiv:2303.10439 (SE stop words), prompt engineering guides,
# and analysis of AI coding assistant interaction patterns.
_CODING_STOP_WORDS: frozenset[str] = frozenset(
    {
        # --- Generic instruction verbs (appear in nearly every coding prompt) ---
        "write",
        "create",
        "implement",
        "build",
        "make",
        "generate",
        "produce",
        "develop",
        "add",
        "update",
        "modify",
        "change",
        "fix",
        "refactor",
        "rewrite",
        "convert",
        "check",
        "verify",
        "test",
        "debug",
        "review",
        "analyze",
        "optimize",
        "improve",
        "remove",
        "delete",
        "replace",
        "rename",
        "setup",
        "configure",
        # --- Generic programming structure nouns ---
        "function",
        "method",
        "class",
        "object",
        "module",
        "package",
        "library",
        "variable",
        "constant",
        "parameter",
        "argument",
        "attribute",
        "property",
        "field",
        "type",
        "interface",
        "struct",
        "trait",
        "protocol",
        # --- Generic data type nouns ---
        "string",
        "integer",
        "float",
        "boolean",
        "number",
        "char",
        "byte",
        "null",
        "nil",
        "none",
        "undefined",
        "void",
        # --- Generic collection nouns ---
        "array",
        "list",
        "dict",
        "dictionary",
        "map",
        "set",
        "tuple",
        "vector",
        # --- Generic code/project structure ---
        "code",
        "file",
        "directory",
        "folder",
        "path",
        "project",
        "repo",
        "codebase",
        "script",
        "program",
        "source",
        "line",
        "block",
        "scope",
        # --- Generic I/O and execution verbs ---
        "run",
        "execute",
        "call",
        "invoke",
        "return",
        "output",
        "print",
        "display",
        "render",
        "parse",
        "process",
        "handle",
        "validate",
        "transform",
        "load",
        "save",
        "store",
        "fetch",
        "retrieve",
        "send",
        "receive",
        "read",
        "import",
        "export",
        # --- LeetCode / algorithm template words ---
        "given",
        "input",
        "output",
        "expected",
        "constraints",
        "assume",
        "ascending",
        "descending",
        "sorted",
        "optimal",
        "brute",
        # --- AI assistant interaction boilerplate ---
        "please",
        "thanks",
        "help",
        "explain",
        "provide",
        "ensure",
        "following",
        "example",
        "basically",
        "simply",
        "just",
        "actually",
        # --- High-frequency SE terms (arXiv:2303.10439) ---
        "use",
        "using",
        "used",
        "want",
        "work",
        "working",
        "need",
        "try",
        "like",
        "get",
        "know",
        "new",
        "possible",
        "specific",
        "simple",
        "right",
        "correct",
        "good",
        "better",
        "best",
        "sure",
        # --- Shell tools and package managers ---
        "cd",
        "uv",
        "pip",
        "npm",
        "yarn",
        "pnpm",
        "brew",
        "apt",
        "git",
        "bash",
        "sh",
        "zsh",
        "python",
        "python3",
        "node",
        "pytest",
        "make",
        "docker",
        "kubectl",
        "curl",
        "wget",
        "ssh",
        "sudo",
    }
)

# Merged stop word set: English + coding domain
STOP_WORDS: frozenset[str] = ENGLISH_STOP_WORDS | _CODING_STOP_WORDS


def _is_noise_phrase(term: str) -> bool:
    """Filter out path fragments, usernames, year numbers, and other noise from TF-IDF results."""
    import re

    noise_tokens = {"users", "chris", "projects", "home", "usr", "var", "tmp", "src", "py"}
    words = set(term.lower().split())
    # Skip if majority of words are path/noise tokens
    if len(words & noise_tokens) >= len(words) * 0.5:
        return True
    # Skip phrases that are purely year numbers (e.g. "2025 2026")
    if all(re.fullmatch(r"20\d\d", w) for w in term.split()):
        return True
    # Skip phrases composed entirely of shell/tool stop words
    shell_words = {"cd", "uv", "pip", "pytest", "git", "bash", "python", "python3", "npm"}
    if words <= shell_words:
        return True
    return False


def compute_tfidf_stats(texts: list[str], top_n: int = 20) -> list[dict[str, Any]]:
    """Compute TF-IDF stats on meaningful phrases (unigrams through trigrams).

    Uses unigrams + bigrams + trigrams with English and coding domain stop words removed.
    sublinear_tf dampens high-frequency terms; max_df=0.8 auto-removes corpus-ubiquitous words.

    Returns list of dicts: [{"term": str, "count": int, "df": int, "tfidf_avg": float}]
    """
    if not texts:
        return []

    # Pre-process: strip file paths and year numbers to avoid noise n-grams
    import re

    path_re = re.compile(r"[~/][\w./-]{10,}")
    year_re = re.compile(r"\b20\d\d\b")
    cleaned = [year_re.sub("", path_re.sub("", t)) for t in texts]

    # Try n-grams first (meaningful phrases), fall back to unigrams for small datasets
    min_df = 2 if len(cleaned) >= 10 else 1
    try:
        vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            stop_words=list(STOP_WORDS),
            min_df=min_df,
            sublinear_tf=True,
            max_df=0.8,
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
            sublinear_tf=True,
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


def _best_k(X: Any, max_k: int = 15) -> int:
    """Select optimal K for K-means via silhouette score sweep (K=3..max_k).

    Returns the K with the highest average silhouette score.
    Falls back to K=3 if the dataset is too small to evaluate.
    """
    n = X.shape[0] if hasattr(X, "shape") else len(X)
    k_min = 3
    k_max = min(max_k, n - 1)
    if k_min > k_max:
        return max(2, n - 1)

    best_k, best_score = k_min, -1.0
    for k in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=k, random_state=42, n_init=5).fit_predict(X)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(X, labels, sample_size=min(1000, n)))
        if score > best_score:
            best_k, best_score = k, score
    return best_k


def cluster_prompts(texts: list[str], n_clusters: int | None = None) -> dict[int, list[str]]:
    """Cluster prompts using LSA-reduced TF-IDF vectors with K-means.

    When n_clusters is None (default), automatically selects the optimal K using a
    silhouette score sweep over K=3..15. Pass an explicit integer to override.

    Applies TruncatedSVD (LSA) + L2 normalization before K-means to avoid the
    single-dominant-cluster problem caused by sparse high-dimensional TF-IDF vectors
    on short text. See: scikit-learn text clustering example (plot_document_clustering).

    Returns {cluster_id: [texts]}
    """
    if not texts:
        return {}

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words=list(STOP_WORDS),
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    # LSA: reduce to 50 dims + L2-normalize for cosine-friendly K-means
    n_components = min(50, tfidf_matrix.shape[1] - 1, len(texts) - 1)
    if n_components >= 2:
        lsa = make_pipeline(TruncatedSVD(n_components=n_components, random_state=42), Normalizer())
        X: Any = lsa.fit_transform(tfidf_matrix)
    else:
        X = tfidf_matrix

    k = _best_k(X) if n_clusters is None else min(n_clusters, len(texts))

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)

    clusters: dict[int, list[str]] = {}
    for text, label in zip(texts, labels):
        clusters.setdefault(int(label), []).append(text)

    return clusters
