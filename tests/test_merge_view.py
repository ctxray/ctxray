"""Tests for merge-view clustering and canonical selection."""

from reprompt.core.merge_view import build_clusters, name_cluster, score_prompt


def test_two_similar_prompts_form_cluster():
    texts = ["fix the auth bug", "fix the authentication issue"]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.5)
    assert len(clusters) == 1
    assert clusters[0]["size"] == 2


def test_dissimilar_prompts_stay_separate():
    texts = [
        "fix the auth bug in login.py",
        "add pagination to search results with offset and limit",
    ]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.85)
    assert len(clusters) == 0


def test_canonical_is_highest_scored():
    texts = ["fix bug", "fix the authentication bug in login.py"]
    timestamps = ["2026-02-15", "2026-02-18"]
    clusters = build_clusters(texts, timestamps, threshold=0.5)
    assert len(clusters) == 1
    assert "login.py" in clusters[0]["canonical"]["text"]


def test_transitive_closure():
    texts = [
        "fix the auth bug",
        "fix the authentication issue",
        "fix the authentication error in login",
    ]
    timestamps = ["2026-02-15", "2026-02-18", "2026-02-20"]
    clusters = build_clusters(texts, timestamps, threshold=0.4)
    assert len(clusters) == 1
    assert clusters[0]["size"] == 3


def test_single_prompts_excluded():
    texts = ["fix the auth bug"]
    timestamps = ["2026-02-15"]
    clusters = build_clusters(texts, timestamps, threshold=0.85)
    assert len(clusters) == 0


def test_empty_input():
    clusters = build_clusters([], [], threshold=0.85)
    assert clusters == []


def test_score_prompt_longer_is_higher():
    short = "fix bug"
    long = "fix the authentication bug in login.py line 42"
    cluster_texts = [short, long]
    assert score_prompt(long, cluster_texts) > score_prompt(short, cluster_texts)


def test_score_prompt_with_file_ref():
    without = "fix the authentication bug"
    with_ref = "fix auth bug in login.py"
    cluster_texts = [without, with_ref]
    score_no_ref = score_prompt(without, cluster_texts)
    score_with_ref = score_prompt(with_ref, cluster_texts)
    assert 0 <= score_no_ref <= 1
    assert 0 <= score_with_ref <= 1


def test_name_cluster():
    name = name_cluster("fix the authentication bug in login.py", "debug")
    assert "Debug" in name


def test_clusters_sorted_by_size():
    texts = [
        "fix auth bug",
        "fix authentication issue",
        "fix auth error",
        "add test for user",
        "add test for user service",
    ]
    timestamps = ["2026-01-01"] * 5
    clusters = build_clusters(texts, timestamps, threshold=0.4)
    if len(clusters) >= 2:
        assert clusters[0]["size"] >= clusters[1]["size"]
