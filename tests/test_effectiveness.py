"""Tests for effectiveness scoring and session metadata."""

from __future__ import annotations

from reprompt.core.effectiveness import (
    compute_effectiveness,
    detect_final_status,
    effectiveness_stars,
)
from reprompt.core.session_meta import SessionMeta


def _make_meta(**overrides: object) -> SessionMeta:
    defaults = {
        "session_id": "test-001",
        "source": "claude-code",
        "project": "myproject",
        "start_time": "2026-03-10T10:00:00Z",
        "end_time": "2026-03-10T11:00:00Z",
        "duration_seconds": 3600,
        "prompt_count": 10,
        "tool_call_count": 20,
        "error_count": 2,
        "final_status": "success",
        "avg_prompt_length": 150.0,
    }
    defaults.update(overrides)
    return SessionMeta(**defaults)  # type: ignore[arg-type]


class TestComputeEffectiveness:
    def test_perfect_session(self):
        meta = _make_meta(
            final_status="success",
            duration_seconds=1800,
            tool_call_count=30,
            error_count=0,
        )
        score = compute_effectiveness(meta, prompt_specificity=1.0)
        assert score == 1.0

    def test_zero_session(self):
        meta = _make_meta(
            final_status="error",
            duration_seconds=60,
            tool_call_count=0,
            error_count=0,
        )
        score = compute_effectiveness(meta, prompt_specificity=0.0)
        assert score == 0.0

    def test_moderate_session(self):
        meta = _make_meta(
            final_status="success",
            duration_seconds=1800,
            tool_call_count=10,
            error_count=2,
        )
        score = compute_effectiveness(meta, prompt_specificity=0.5)
        assert 0.3 < score < 0.9

    def test_unknown_status_partial_credit(self):
        meta = _make_meta(final_status="unknown")
        score_unknown = compute_effectiveness(meta)
        meta_success = _make_meta(final_status="success")
        score_success = compute_effectiveness(meta_success)
        assert score_unknown < score_success

    def test_long_duration_penalty(self):
        short = _make_meta(duration_seconds=1800)
        long = _make_meta(duration_seconds=10000)
        assert compute_effectiveness(short) > compute_effectiveness(long)

    def test_score_capped_at_1(self):
        meta = _make_meta()
        score = compute_effectiveness(meta, prompt_specificity=2.0)
        assert score <= 1.0

    def test_high_error_ratio_penalizes(self):
        clean = _make_meta(tool_call_count=20, error_count=0)
        messy = _make_meta(tool_call_count=20, error_count=15)
        assert compute_effectiveness(clean) > compute_effectiveness(messy)


class TestDetectFinalStatus:
    def test_clean_exit(self):
        entries = [
            {"message": {"role": "assistant", "content": "Done! All tests pass."}},
            {"message": {"role": "assistant", "content": "The changes have been committed."}},
        ]
        assert detect_final_status(entries) == "success"

    def test_error_exit(self):
        entries = [
            {"message": {"role": "assistant", "content": "Running tests..."}},
            {"message": {"role": "assistant", "content": "Error: test_auth failed with assertion"}},
        ]
        assert detect_final_status(entries) == "error"

    def test_traceback_detected(self):
        entries = [
            {"message": {"role": "assistant", "content": "Traceback (most recent call last):"}},
        ]
        assert detect_final_status(entries) == "error"

    def test_empty_entries(self):
        assert detect_final_status([]) == "success"

    def test_only_checks_last_messages(self):
        entries = [
            {"message": {"role": "assistant", "content": "Error: old error"}},
        ] + [{"message": {"role": "assistant", "content": f"Success step {i}"}} for i in range(5)]
        assert detect_final_status(entries) == "success"


class TestEffectivenessStars:
    def test_full_stars(self):
        assert effectiveness_stars(1.0) == "\u2605\u2605\u2605\u2605\u2605"

    def test_no_stars(self):
        assert effectiveness_stars(0.0) == "\u2606\u2606\u2606\u2606\u2606"

    def test_partial(self):
        result = effectiveness_stars(0.6)
        assert result.count("\u2605") == 3
        assert result.count("\u2606") == 2

    def test_length_always_5(self):
        for v in [0.0, 0.2, 0.5, 0.8, 1.0]:
            assert len(effectiveness_stars(v)) == 5
