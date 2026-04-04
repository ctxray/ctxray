"""Tests for telemetry event schema and bucketing helpers."""

from __future__ import annotations

import json
from datetime import date

from ctxray.telemetry.events import (
    TelemetryEvent,
    bucket_duration,
    bucket_error_ratio,
    bucket_tool_calls,
    build_event,
)


class TestBucketing:
    """Bucketing converts exact numbers to privacy-preserving ranges."""

    def test_bucket_duration_short(self):
        assert bucket_duration(30) == "<1m"

    def test_bucket_duration_medium(self):
        assert bucket_duration(300) == "1m-10m"

    def test_bucket_duration_long(self):
        assert bucket_duration(1800) == "10m-60m"

    def test_bucket_duration_very_long(self):
        assert bucket_duration(7200) == ">60m"

    def test_bucket_duration_none(self):
        assert bucket_duration(None) == "unknown"

    def test_bucket_error_ratio_zero(self):
        assert bucket_error_ratio(0.0) == "0%"

    def test_bucket_error_ratio_low(self):
        assert bucket_error_ratio(0.05) == "1-10%"

    def test_bucket_error_ratio_medium(self):
        assert bucket_error_ratio(0.30) == "10-50%"

    def test_bucket_error_ratio_high(self):
        assert bucket_error_ratio(0.75) == ">50%"

    def test_bucket_error_ratio_none(self):
        assert bucket_error_ratio(None) == "unknown"

    def test_bucket_tool_calls_zero(self):
        assert bucket_tool_calls(0) == "0"

    def test_bucket_tool_calls_few(self):
        assert bucket_tool_calls(3) == "1-5"

    def test_bucket_tool_calls_moderate(self):
        assert bucket_tool_calls(12) == "6-20"

    def test_bucket_tool_calls_many(self):
        assert bucket_tool_calls(50) == ">20"

    def test_bucket_tool_calls_none(self):
        assert bucket_tool_calls(None) == "unknown"


class TestTelemetryEvent:
    def test_event_has_required_fields(self):
        event = TelemetryEvent(
            install_id="a" * 64,
            dna_vector=[0.1] * 26,
            task_type="debug",
            source="claude_code",
            client="cli",
            score_total=72.0,
            score_structure=18.0,
            score_context=20.0,
            score_position=14.0,
            score_repetition=10.0,
            score_clarity=10.0,
            ctxray_version="0.9.1",
            timestamp_day="2026-03-15",
        )
        assert event.install_id == "a" * 64
        assert len(event.dna_vector) == 26
        assert event.client == "cli"

    def test_event_serializes_to_json(self):
        event = TelemetryEvent(
            install_id="b" * 64,
            dna_vector=[0.5] * 26,
            task_type="implement",
            source="claude_code",
            client="cli",
            score_total=60.0,
            score_structure=15.0,
            score_context=15.0,
            score_position=12.0,
            score_repetition=8.0,
            score_clarity=10.0,
            ctxray_version="0.9.1",
            timestamp_day="2026-03-15",
        )
        serialized = event.model_dump_json()
        data = json.loads(serialized)
        assert data["install_id"] == "b" * 64
        assert len(data["dna_vector"]) == 26
        assert "score_total" in data

    def test_event_optional_outcome_fields(self):
        event = TelemetryEvent(
            install_id="c" * 64,
            dna_vector=[0.0] * 26,
            task_type="other",
            source="manual",
            client="cli",
            score_total=50.0,
            score_structure=12.0,
            score_context=10.0,
            score_position=10.0,
            score_repetition=8.0,
            score_clarity=10.0,
            ctxray_version="0.9.1",
            timestamp_day="2026-03-15",
            session_duration_bucket="1m-10m",
            error_ratio_bucket="0%",
            tool_call_count_bucket="1-5",
            effectiveness_score=0.75,
            locale="en_US",
        )
        assert event.session_duration_bucket == "1m-10m"
        assert event.effectiveness_score == 0.75

    def test_event_no_prompt_text_field(self):
        """Verify no field can leak raw prompt text."""
        field_names = set(TelemetryEvent.model_fields.keys())
        dangerous = {"text", "prompt", "prompt_text", "raw_text", "content"}
        assert field_names.isdisjoint(dangerous)

    def test_event_no_file_path_field(self):
        """Verify no field can leak file paths."""
        field_names = set(TelemetryEvent.model_fields.keys())
        dangerous = {"file_path", "path", "session_path", "file"}
        assert field_names.isdisjoint(dangerous)


class TestBuildEvent:
    def test_build_event_from_dna_and_scores(self):
        from ctxray.core.prompt_dna import PromptDNA
        from ctxray.core.scorer import ScoreBreakdown

        dna = PromptDNA(
            prompt_hash="abc123",
            source="claude_code",
            task_type="debug",
            token_count=50,
            word_count=40,
            sentence_count=3,
            has_code_blocks=True,
            code_block_count=1,
            context_specificity=0.8,
        )
        scores = ScoreBreakdown(
            total=72.0,
            structure=18.0,
            context=20.0,
            position=14.0,
            repetition=10.0,
            clarity=10.0,
        )
        event = build_event(
            install_id="d" * 64,
            dna=dna,
            scores=scores,
            version="0.9.1",
        )
        assert event.install_id == "d" * 64
        assert event.task_type == "debug"
        assert event.source == "claude_code"
        assert event.score_total == 72.0
        assert len(event.dna_vector) > 0
        # Timestamp should be today's date
        assert event.timestamp_day == date.today().isoformat()

    def test_build_event_with_session_meta(self):
        from ctxray.core.prompt_dna import PromptDNA
        from ctxray.core.scorer import ScoreBreakdown

        dna = PromptDNA(prompt_hash="xyz", source="manual", task_type="implement")
        scores = ScoreBreakdown(
            total=55.0,
            structure=12.0,
            context=10.0,
            position=10.0,
            repetition=8.0,
            clarity=15.0,
        )
        event = build_event(
            install_id="e" * 64,
            dna=dna,
            scores=scores,
            version="0.9.1",
            session_duration_seconds=600,
            error_count=2,
            prompt_count=10,
            tool_call_count=15,
            effectiveness_score=0.68,
        )
        assert event.session_duration_bucket == "1m-10m"
        assert event.error_ratio_bucket == "10-50%"
        assert event.tool_call_count_bucket == "6-20"
        assert event.effectiveness_score == 0.68
