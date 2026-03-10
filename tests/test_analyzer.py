"""Tests for TF-IDF analyzer and K-means clustering."""

from reprompt.core.analyzer import cluster_prompts, compute_tfidf_stats


def test_compute_tfidf_top_terms():
    texts = [
        "fix the failing test in auth module",
        "fix the broken test in payments module",
        "deploy application to production server",
        "deploy the app to staging environment",
        "review code for security vulnerabilities",
    ]
    stats = compute_tfidf_stats(texts, top_n=5)
    assert len(stats) <= 5
    assert all("term" in s and "tfidf_avg" in s for s in stats)


def test_compute_tfidf_returns_sorted():
    texts = ["python python python", "python java", "go rust"]
    stats = compute_tfidf_stats(texts, top_n=10)
    scores = [s["tfidf_avg"] for s in stats]
    assert scores == sorted(scores, reverse=True)


def test_cluster_prompts():
    texts = [
        "fix the failing test in auth",
        "fix the broken test in payments",
        "fix test failure in users",
        "deploy to production",
        "deploy to staging",
        "deploy the application",
    ]
    clusters = cluster_prompts(texts, n_clusters=2)
    assert len(clusters) == 2
    assert all(isinstance(c, list) for c in clusters.values())
    total = sum(len(c) for c in clusters.values())
    assert total == len(texts)


def test_cluster_empty():
    clusters = cluster_prompts([], n_clusters=2)
    assert len(clusters) == 0


def test_cluster_single():
    clusters = cluster_prompts(["single prompt here"], n_clusters=1)
    assert len(clusters) == 1


def test_tfidf_empty():
    stats = compute_tfidf_stats([], top_n=5)
    assert stats == []
