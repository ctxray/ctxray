"""End-to-end test: opt-in -> score prompt -> event queued -> batch sent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from reprompt.core.extractors import extract_features
from reprompt.core.scorer import score_prompt
from reprompt.telemetry.collector import TelemetryCollector
from reprompt.telemetry.consent import TelemetryConsent, write_consent
from reprompt.telemetry.events import TelemetryEvent


@pytest.fixture
def e2e_env(tmp_path: Path) -> dict[str, Path]:
    """Set up a complete telemetry environment."""
    config_path = tmp_path / "config.toml"
    queue_path = tmp_path / "telemetry.db"
    write_consent(TelemetryConsent.OPTED_IN, config_path)
    return {"config": config_path, "queue": queue_path}


class TestTelemetryE2E:
    def test_score_to_queue_pipeline(self, e2e_env: dict[str, Path]):
        """Score a prompt -> event is queued with correct data."""
        collector = TelemetryCollector(
            config_path=e2e_env["config"],
            queue_path=e2e_env["queue"],
            version="0.9.1",
        )

        # Score a realistic prompt
        text = (
            "You are a senior Python developer. Refactor the database module "
            "to use async/await. Must maintain backward compatibility. "
            "Output as a diff. Reference: src/reprompt/storage/db.py"
        )
        dna = extract_features(text, source="claude_code", session_id="e2e-test")
        scores = score_prompt(dna)

        # Record telemetry
        collector.record(dna, scores)

        # Verify event is queued
        assert collector.queue.pending_count() == 1
        batch = collector.queue.dequeue(limit=1)
        event_data = json.loads(batch[0][1])

        # Verify event structure
        assert len(event_data["install_id"]) == 64
        assert len(event_data["dna_vector"]) > 0
        assert event_data["task_type"] in (
            "implement",
            "refactor",
            "debug",
            "other",
            "explain",
            "test",
            "review",
            "config",
        )
        assert event_data["source"] == "claude_code"
        assert event_data["score_total"] > 0
        assert event_data["client"] == "cli"
        assert event_data["reprompt_version"] == "0.9.1"

        # Verify NO prompt text leaked
        serialized = json.dumps(event_data)
        assert "Refactor the database" not in serialized
        assert "db.py" not in serialized
        assert "backward compatibility" not in serialized

    @patch("reprompt.telemetry.collector.send_batch")
    def test_queue_to_send_pipeline(self, mock_send, e2e_env: dict[str, Path]):
        """Events are sent and acknowledged on flush."""
        mock_send.return_value = True

        collector = TelemetryCollector(
            config_path=e2e_env["config"],
            queue_path=e2e_env["queue"],
            version="0.9.1",
        )

        # Queue several events
        prompts = [
            "Fix the auth bug in src/auth/login.ts",
            "what does this code do",
            "Add unit tests for payment processing with pytest fixtures",
        ]
        for text in prompts:
            dna = extract_features(text, source="claude_code", session_id="e2e")
            scores = score_prompt(dna)
            collector.record(dna, scores)

        assert collector.queue.pending_count() == 3

        # Flush
        collector.flush()

        # Verify send was called with 3 events
        mock_send.assert_called_once()
        sent_payloads = mock_send.call_args[0][0]
        assert len(sent_payloads) == 3

        # Queue should be empty after successful send
        assert collector.queue.pending_count() == 0

    @patch("reprompt.telemetry.collector.send_batch")
    def test_failed_send_retains_events(self, mock_send, e2e_env: dict[str, Path]):
        """Failed sends keep events in queue for retry."""
        mock_send.return_value = False

        collector = TelemetryCollector(
            config_path=e2e_env["config"],
            queue_path=e2e_env["queue"],
            version="0.9.1",
        )

        dna = extract_features("Fix the auth bug", source="manual", session_id="e2e")
        scores = score_prompt(dna)
        collector.record(dna, scores)

        collector.flush()
        # Event should still be in queue
        assert collector.queue.pending_count() == 1

        # Second flush succeeds
        mock_send.return_value = True
        collector.flush()
        assert collector.queue.pending_count() == 0

    def test_opt_out_prevents_everything(self, tmp_path: Path):
        """Opted-out users generate zero telemetry."""
        config = tmp_path / "config.toml"
        write_consent(TelemetryConsent.OPTED_OUT, config)

        collector = TelemetryCollector(
            config_path=config,
            queue_path=tmp_path / "t.db",
            version="0.9.1",
        )

        dna = extract_features("Fix the bug", source="manual", session_id="e2e")
        scores = score_prompt(dna)
        collector.record(dna, scores)

        assert collector.queue.pending_count() == 0

    def test_event_validates_as_pydantic_model(self, e2e_env: dict[str, Path]):
        """Queued events must deserialize into valid TelemetryEvent models."""
        collector = TelemetryCollector(
            config_path=e2e_env["config"],
            queue_path=e2e_env["queue"],
            version="0.9.1",
        )

        dna = extract_features(
            "Debug this error: TypeError at line 42",
            source="claude_code",
            session_id="e2e-validate",
        )
        scores = score_prompt(dna)
        collector.record(dna, scores)

        batch = collector.queue.dequeue(limit=1)
        event = TelemetryEvent.model_validate_json(batch[0][1])
        assert event.install_id
        assert event.score_total == scores.total
