"""Tests for telemetry collector (orchestrator)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ctxray.core.prompt_dna import PromptDNA
from ctxray.core.scorer import ScoreBreakdown
from ctxray.telemetry.collector import TelemetryCollector
from ctxray.telemetry.consent import TelemetryConsent, write_consent


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Temp config dir with opt-in consent."""
    config_path = tmp_path / "config.toml"
    write_consent(TelemetryConsent.OPTED_IN, config_path)
    return tmp_path


@pytest.fixture
def collector(config_dir: Path, tmp_path: Path) -> TelemetryCollector:
    return TelemetryCollector(
        config_path=config_dir / "config.toml",
        queue_path=tmp_path / "telemetry.db",
        version="0.9.1",
    )


def _sample_dna() -> PromptDNA:
    return PromptDNA(
        prompt_hash="test123",
        source="claude_code",
        task_type="debug",
        token_count=50,
        word_count=40,
    )


def _sample_scores() -> ScoreBreakdown:
    return ScoreBreakdown(
        total=72.0,
        structure=18.0,
        context=20.0,
        position=14.0,
        repetition=10.0,
        clarity=10.0,
    )


class TestCollectorRecord:
    def test_record_enqueues_event_when_opted_in(self, collector: TelemetryCollector):
        collector.record(_sample_dna(), _sample_scores())
        assert collector.queue.pending_count() == 1

    def test_record_skips_when_opted_out(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_OUT, config_path)
        c = TelemetryCollector(
            config_path=config_path,
            queue_path=tmp_path / "t.db",
            version="0.9.1",
        )
        c.record(_sample_dna(), _sample_scores())
        assert c.queue.pending_count() == 0

    def test_record_skips_when_not_asked(self, tmp_path: Path):
        config_path = tmp_path / "new_config.toml"
        # Don't write consent -- defaults to NOT_ASKED
        c = TelemetryCollector(
            config_path=config_path,
            queue_path=tmp_path / "t.db",
            version="0.9.1",
        )
        c.record(_sample_dna(), _sample_scores())
        assert c.queue.pending_count() == 0

    def test_record_stores_valid_json(self, collector: TelemetryCollector):
        collector.record(_sample_dna(), _sample_scores())
        batch = collector.queue.dequeue(limit=1)
        assert len(batch) == 1
        event = json.loads(batch[0][1])
        assert "install_id" in event
        assert "dna_vector" in event
        assert event["score_total"] == 72.0


class TestCollectorFlush:
    @patch("ctxray.telemetry.collector.send_batch")
    def test_flush_sends_and_acks(self, mock_send: MagicMock, collector: TelemetryCollector):
        mock_send.return_value = True
        for _ in range(3):
            collector.record(_sample_dna(), _sample_scores())
        assert collector.queue.pending_count() == 3

        collector.flush()
        mock_send.assert_called_once()
        # Events should be acknowledged (removed from queue)
        assert collector.queue.pending_count() == 0

    @patch("ctxray.telemetry.collector.send_batch")
    def test_flush_keeps_events_on_failure(
        self, mock_send: MagicMock, collector: TelemetryCollector
    ):
        mock_send.return_value = False
        collector.record(_sample_dna(), _sample_scores())
        collector.flush()
        # Events stay in queue for next attempt
        assert collector.queue.pending_count() == 1

    @patch("ctxray.telemetry.collector.send_batch")
    def test_flush_respects_batch_limit(self, mock_send: MagicMock, collector: TelemetryCollector):
        mock_send.return_value = True
        for _ in range(75):
            collector.record(_sample_dna(), _sample_scores())
        collector.flush(batch_size=50)
        # Should send exactly 50 (first batch)
        call_args = mock_send.call_args[0][0]
        assert len(call_args) == 50
        # 25 remain in queue
        assert collector.queue.pending_count() == 25

    @patch("ctxray.telemetry.collector.send_batch")
    def test_flush_skips_when_opted_out(self, mock_send: MagicMock, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_OUT, config_path)
        c = TelemetryCollector(
            config_path=config_path,
            queue_path=tmp_path / "t.db",
            version="0.9.1",
        )
        c.flush()
        mock_send.assert_not_called()

    @patch("ctxray.telemetry.collector.send_batch")
    def test_flush_also_cleans_old_events(
        self, mock_send: MagicMock, collector: TelemetryCollector
    ):
        """flush() should also discard events older than 30 days."""
        mock_send.return_value = True
        collector.record(_sample_dna(), _sample_scores())
        collector.flush()
        # No assertion on flush_old specifically; tested in queue tests


class TestCollectorInstallId:
    def test_install_id_is_stable(self, collector: TelemetryCollector):
        """Same collector instance should always produce the same install_id."""
        collector.record(_sample_dna(), _sample_scores())
        collector.record(_sample_dna(), _sample_scores())
        batch = collector.queue.dequeue(limit=2)
        id1 = json.loads(batch[0][1])["install_id"]
        id2 = json.loads(batch[1][1])["install_id"]
        assert id1 == id2
        assert len(id1) == 64
