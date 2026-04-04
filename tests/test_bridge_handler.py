"""Tests for Native Messaging message handler."""

from __future__ import annotations

from pathlib import Path

from ctxray.bridge.handler import handle_message
from ctxray.storage.db import PromptDB


def test_handle_ping(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "ping"}, db)
    assert response["type"] == "pong"
    assert "version" in response


def test_handle_sync_prompts(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain how async/await works in Python",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:00:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
            {
                "text": "Show me a simple example of asyncio.gather",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:01:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
        ],
    }
    response = handle_message(msg, db)
    assert response["type"] == "sync_result"
    assert response["received"] == 2
    assert response["new_stored"] == 2
    assert response["duplicates"] == 0


def test_handle_sync_dedup(tmp_path: Path) -> None:
    """Second sync of same prompts should report duplicates."""
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain how async/await works in Python",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-15T10:00:00Z",
                "conversation_id": "conv-001",
                "conversation_title": "Python async",
            },
        ],
    }
    handle_message(msg, db)
    response = handle_message(msg, db)
    assert response["new_stored"] == 0
    assert response["duplicates"] == 1


def test_handle_sync_filters_short(tmp_path: Path) -> None:
    """Short/noise prompts should be filtered out."""
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "ok",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
            {
                "text": "yes",
                "source": "chatgpt-ext",
                "timestamp": "",
                "conversation_id": "c1",
                "conversation_title": "t",
            },
        ],
    }
    response = handle_message(msg, db)
    assert response["received"] == 2
    assert response["new_stored"] == 0


def test_handle_get_status(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    # Insert a prompt so stats are non-empty
    db.insert_prompt(
        "Test prompt for status check", source="chatgpt-ext", project="test", session_id="s1"
    )
    response = handle_message({"type": "get_status"}, db)
    assert response["type"] == "status"
    assert response["total_prompts"] >= 1
    assert "version" in response


def test_handle_unknown_type(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "unknown_xyz"}, db)
    assert response["type"] == "error"
    assert "unknown" in response["message"].lower()


def test_handle_empty_sync(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    assert response["type"] == "sync_result"
    assert response["received"] == 0
    assert response["new_stored"] == 0


# -- Insights in sync response --


def test_sync_result_includes_insights(tmp_path: Path) -> None:
    """sync_result should always include an insights dict."""
    db = PromptDB(tmp_path / "test.db")
    msg = {
        "type": "sync_prompts",
        "prompts": [
            {
                "text": "Explain the difference between threads and processes in Python",
                "source": "chatgpt-ext",
                "timestamp": "2026-03-20T10:00:00Z",
                "conversation_id": "c1",
                "conversation_title": "",
            },
        ],
    }
    response = handle_message(msg, db)
    assert "insights" in response
    insights = response["insights"]
    assert "avg_score" in insights
    assert "total_prompts" in insights
    assert "score_trend" in insights
    assert insights["score_trend"] in ("improving", "declining", "stable")


def test_sync_insights_empty_db(tmp_path: Path) -> None:
    """Empty DB sync should return zero insights with stable trend."""
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    insights = response["insights"]
    assert insights["avg_score"] == 0.0
    assert insights["total_prompts"] == 0
    assert insights["score_trend"] == "stable"
    assert insights["top_insight"] is None


def test_sync_insights_with_scored_prompts(tmp_path: Path) -> None:
    """Insights should reflect stored scores when features exist."""
    db = PromptDB(tmp_path / "test.db")
    # Insert prompts and store features to simulate scored data
    for i in range(10):
        text = f"Implement a Python decorator that caches function results variant {i}"
        db.insert_prompt(text, source="chatgpt-ext", project="test", session_id="s1")
        import hashlib

        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(h, {"overall_score": 60.0 + i, "task_type": "implement"})

    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    insights = response["insights"]
    assert insights["total_prompts"] == 10
    assert insights["avg_score"] > 0


def test_sync_insights_trend_improving(tmp_path: Path) -> None:
    """Score trend should detect improvement."""
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    # Insert 30 prompts: older ones low score, recent ones high score
    for i in range(30):
        ts = f"2026-03-{10 + i // 2:02d}T{10 + i % 24:02d}:00:00Z"
        text = f"Write a comprehensive test suite for the user auth module version {i}"
        db.insert_prompt(text, source="chatgpt-ext", project="test", session_id="s1", timestamp=ts)
        h = hashlib.sha256(text.encode()).hexdigest()
        # Older prompts (higher i = more recent timestamp) get higher scores
        score = 40.0 + i * 1.5
        db.store_features(h, {"overall_score": score, "task_type": "test"})

    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    insights = response["insights"]
    assert insights["score_trend"] == "improving"


def test_sync_insights_trend_declining(tmp_path: Path) -> None:
    """Score trend should detect decline."""
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    for i in range(30):
        ts = f"2026-03-{10 + i // 2:02d}T{10 + i % 24:02d}:00:00Z"
        text = f"Debug the authentication middleware crash in production variant {i}"
        db.insert_prompt(text, source="chatgpt-ext", project="test", session_id="s1", timestamp=ts)
        h = hashlib.sha256(text.encode()).hexdigest()
        # More recent = lower score
        score = 85.0 - i * 1.5
        db.store_features(h, {"overall_score": score, "task_type": "debug"})

    response = handle_message({"type": "sync_prompts", "prompts": []}, db)
    insights = response["insights"]
    assert insights["score_trend"] == "declining"


# -- get_insights message type --


def test_handle_get_insights_empty(tmp_path: Path) -> None:
    """get_insights on empty DB should return valid structure."""
    db = PromptDB(tmp_path / "test.db")
    response = handle_message({"type": "get_insights"}, db)
    assert response["type"] == "insights_result"
    assert response["avg_score"] == 0.0
    assert response["prompt_count"] == 0
    assert response["insights"] == []


def test_handle_get_insights_with_data(tmp_path: Path) -> None:
    """get_insights should return analysis when data exists."""
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    for i in range(10):
        text = f"Refactor the database connection pool to use async context managers v{i}"
        db.insert_prompt(
            text,
            source="claude-ext",
            project="test",
            session_id="s1",
            timestamp=f"2026-03-{15 + i}T10:00:00Z",
        )
        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(
            h,
            {
                "overall_score": 55.0 + i,
                "task_type": "refactor",
                "key_instruction_position": 0.1,
                "keyword_repetition_freq": 0.2,
                "context_specificity": 0.4,
                "has_constraints": False,
                "ambiguity_score": 0.3,
                "compressibility": 0.2,
                "source": "claude-ext",
                "token_count": 50,
            },
        )

    response = handle_message({"type": "get_insights"}, db)
    assert response["type"] == "insights_result"
    assert response["prompt_count"] == 10
    assert response["avg_score"] > 0


def test_handle_get_insights_with_source_filter(tmp_path: Path) -> None:
    """get_insights should respect source filter."""
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    # ChatGPT prompts
    for i in range(5):
        text = f"Explain Python decorators with practical examples variant {i}"
        db.insert_prompt(text, source="chatgpt-ext", project="t", session_id="s1")
        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(
            h,
            {
                "overall_score": 70.0,
                "task_type": "explain",
                "source": "chatgpt-ext",
                "token_count": 30,
            },
        )

    # Claude prompts
    for i in range(5):
        text = f"Create a REST API with FastAPI for user management variant {i}"
        db.insert_prompt(text, source="claude-ext", project="t", session_id="s2")
        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(
            h,
            {
                "overall_score": 80.0,
                "task_type": "implement",
                "source": "claude-ext",
                "token_count": 40,
            },
        )

    # Filter to chatgpt only
    response = handle_message({"type": "get_insights", "source": "chatgpt-ext"}, db)
    assert response["type"] == "insights_result"
    assert response["prompt_count"] == 5


# -- DB: get_recent_scores --


def test_get_recent_scores_empty(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    assert db.get_recent_scores() == []


def test_get_recent_scores_ordered(tmp_path: Path) -> None:
    """Scores should be returned newest-first."""
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    texts = [
        ("Oldest prompt about Python typing", "2026-03-01T10:00:00Z", 50.0),
        ("Middle prompt about async patterns", "2026-03-15T10:00:00Z", 70.0),
        ("Newest prompt about testing strategies", "2026-03-30T10:00:00Z", 90.0),
    ]
    for text, ts, score in texts:
        db.insert_prompt(text, source="test", project="p", session_id="s", timestamp=ts)
        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(h, {"overall_score": score, "task_type": "other"})

    scores = db.get_recent_scores(limit=10)
    assert len(scores) == 3
    # Newest first
    assert scores[0] == 90.0
    assert scores[-1] == 50.0


def test_get_recent_scores_respects_limit(tmp_path: Path) -> None:
    db = PromptDB(tmp_path / "test.db")
    import hashlib

    for i in range(20):
        text = f"Generate unit tests for the payment processing module variant {i}"
        db.insert_prompt(
            text,
            source="test",
            project="p",
            session_id="s",
            timestamp=f"2026-03-{i + 1:02d}T10:00:00Z",
        )
        h = hashlib.sha256(text.encode()).hexdigest()
        db.store_features(h, {"overall_score": 50.0 + i, "task_type": "test"})

    scores = db.get_recent_scores(limit=5)
    assert len(scores) == 5
