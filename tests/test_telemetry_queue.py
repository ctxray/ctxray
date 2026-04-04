"""Tests for telemetry event queue (SQLite-backed)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ctxray.telemetry.queue import TelemetryQueue


@pytest.fixture
def queue(tmp_path: Path) -> TelemetryQueue:
    return TelemetryQueue(tmp_path / "telemetry.db")


class TestTelemetryQueueInit:
    def test_creates_db_file(self, tmp_path: Path):
        TelemetryQueue(tmp_path / "new.db")
        assert (tmp_path / "new.db").exists()

    def test_creates_parent_dirs(self, tmp_path: Path):
        TelemetryQueue(tmp_path / "sub" / "dir" / "t.db")
        assert (tmp_path / "sub" / "dir" / "t.db").exists()


class TestEnqueue:
    def test_enqueue_single_event(self, queue: TelemetryQueue):
        payload = {"install_id": "a" * 64, "score_total": 72.0}
        queue.enqueue(json.dumps(payload))
        assert queue.pending_count() == 1

    def test_enqueue_multiple_events(self, queue: TelemetryQueue):
        for i in range(5):
            queue.enqueue(json.dumps({"i": i}))
        assert queue.pending_count() == 5


class TestDequeue:
    def test_dequeue_returns_batch(self, queue: TelemetryQueue):
        for i in range(10):
            queue.enqueue(json.dumps({"i": i}))
        batch = queue.dequeue(limit=5)
        assert len(batch) == 5

    def test_dequeue_returns_oldest_first(self, queue: TelemetryQueue):
        queue.enqueue(json.dumps({"order": "first"}))
        queue.enqueue(json.dumps({"order": "second"}))
        batch = queue.dequeue(limit=1)
        assert len(batch) == 1
        data = json.loads(batch[0][1])  # (id, payload)
        assert data["order"] == "first"

    def test_dequeue_respects_limit(self, queue: TelemetryQueue):
        for i in range(100):
            queue.enqueue(json.dumps({"i": i}))
        batch = queue.dequeue(limit=50)
        assert len(batch) == 50

    def test_dequeue_empty_queue(self, queue: TelemetryQueue):
        batch = queue.dequeue(limit=10)
        assert batch == []


class TestAcknowledge:
    def test_ack_removes_events(self, queue: TelemetryQueue):
        for i in range(5):
            queue.enqueue(json.dumps({"i": i}))
        batch = queue.dequeue(limit=5)
        ids = [row[0] for row in batch]
        queue.acknowledge(ids)
        assert queue.pending_count() == 0

    def test_ack_partial(self, queue: TelemetryQueue):
        for i in range(5):
            queue.enqueue(json.dumps({"i": i}))
        batch = queue.dequeue(limit=3)
        ids = [row[0] for row in batch]
        queue.acknowledge(ids)
        assert queue.pending_count() == 2


class TestFlushOld:
    def test_flush_old_removes_expired_events(self, queue: TelemetryQueue):
        # Insert event with old timestamp directly
        conn = sqlite3.connect(str(queue.path))
        old_ts = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        conn.execute(
            "INSERT INTO telemetry_queue (payload, created_at) VALUES (?, ?)",
            ('{"old": true}', old_ts),
        )
        conn.commit()
        conn.close()

        queue.enqueue(json.dumps({"new": True}))
        removed = queue.flush_old(max_age_days=30)
        assert removed == 1
        assert queue.pending_count() == 1

    def test_flush_old_keeps_recent(self, queue: TelemetryQueue):
        for i in range(3):
            queue.enqueue(json.dumps({"i": i}))
        removed = queue.flush_old(max_age_days=30)
        assert removed == 0
        assert queue.pending_count() == 3
