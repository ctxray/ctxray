"""TF-IDF analysis and K-means clustering."""
from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


def compute_tfidf_stats(texts: list[str], top_n: int = 20) -> list[dict]:
    """Compute TF-IDF stats, return top N terms with scores.

    Returns list of dicts: [{"term": str, "count": int, "df": int, "tfidf_avg": float}]
    """
    if not texts:
        return []

    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    # Average TF-IDF score per term across all documents
    avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

    # Document frequency (number of docs containing each term)
    df = np.asarray((tfidf_matrix > 0).sum(axis=0)).flatten()

    # Sum of TF-IDF weights (approximate count)
    count = np.asarray(tfidf_matrix.sum(axis=0)).flatten()

    results = []
    for i, term in enumerate(feature_names):
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

    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(texts)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(tfidf_matrix)

    clusters: dict[int, list[str]] = {}
    for text, label in zip(texts, labels):
        clusters.setdefault(int(label), []).append(text)

    return clusters
