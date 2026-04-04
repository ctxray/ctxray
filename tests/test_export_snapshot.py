"""Snapshot tests for export format stability."""

from __future__ import annotations

import os
from pathlib import Path

from ctxray.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)
from ctxray.output.export import generate_export

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "export"


def _standard_result() -> DistillResult:
    """Build a standard DistillResult for snapshot testing."""
    turns = []
    user_data = [
        (
            "Implement the auth module with JWT support",
            0.9,
            {
                "position": 1.0,
                "length": 0.7,
                "tool_trigger": 0.3,
                "error_recovery": 0.0,
                "semantic_shift": 0.8,
                "uniqueness": 0.9,
            },
        ),
        (
            "Use bcrypt for password hashing",
            0.7,
            {
                "position": 0.4,
                "length": 0.5,
                "tool_trigger": 0.8,
                "error_recovery": 0.0,
                "semantic_shift": 0.7,
                "uniqueness": 0.6,
            },
        ),
        (
            "Switch to argon2 instead, it's more secure",
            0.8,
            {
                "position": 0.5,
                "length": 0.6,
                "tool_trigger": 0.6,
                "error_recovery": 0.0,
                "semantic_shift": 0.9,
                "uniqueness": 0.7,
            },
        ),
        (
            "Add rate limiting to the login endpoint",
            0.6,
            {
                "position": 0.5,
                "length": 0.5,
                "tool_trigger": 0.9,
                "error_recovery": 0.0,
                "semantic_shift": 0.4,
                "uniqueness": 0.5,
            },
        ),
        (
            "Next we need to add integration tests for all auth flows",
            0.7,
            {
                "position": 0.8,
                "length": 0.6,
                "tool_trigger": 0.2,
                "error_recovery": 0.0,
                "semantic_shift": 0.5,
                "uniqueness": 0.6,
            },
        ),
    ]
    idx = 0
    for text, imp, scores in user_data:
        user = ConversationTurn(
            role="user",
            text=text,
            timestamp="2026-03-24T10:00:00Z",
            turn_index=idx,
            importance=imp,
        )
        user.signal_scores = scores
        turns.append(user)
        idx += 1
        turns.append(
            ConversationTurn(
                role="assistant",
                text=f"Working on: {text[:30]}...",
                timestamp="2026-03-24T10:00:05Z",
                turn_index=idx,
                importance=imp * 0.8,
                tool_calls=3,
                tool_use_paths=["src/auth.py"],
            )
        )
        idx += 1

    conv = Conversation(
        session_id="snapshot-test",
        source="claude-code",
        project="auth-service",
        turns=turns,
        start_time="2026-03-24T10:00:00Z",
        duration_seconds=2700,
    )
    filtered = [t for t in turns if t.importance >= 0.3]
    return DistillResult(
        conversation=conv,
        filtered_turns=filtered,
        threshold=0.3,
        files_changed=["src/auth.py", "src/tokens.py", "tests/test_auth.py"],
        stats=DistillStats(
            total_turns=10,
            kept_turns=len(filtered),
            retention_ratio=len(filtered) / 10,
            total_duration_seconds=2700,
        ),
    )


def _diff(expected: str, actual: str) -> str:
    """Simple line diff for debugging."""
    exp_lines = expected.splitlines()
    act_lines = actual.splitlines()
    diffs = []
    for i, (e, a) in enumerate(zip(exp_lines, act_lines)):
        if e != a:
            diffs.append(f"  Line {i + 1}:\n    expected: {e!r}\n    actual:   {a!r}")
    if len(exp_lines) != len(act_lines):
        diffs.append(f"  Line count: expected {len(exp_lines)}, got {len(act_lines)}")
    return "\n".join(diffs[:10])


class TestExportSnapshot:
    def test_default_export_format(self):
        result = _standard_result()
        output = generate_export(result)
        fixture_path = FIXTURES_DIR / "default_export.md"

        if os.environ.get("UPDATE_SNAPSHOTS"):
            fixture_path.write_text(output)
            return

        if not fixture_path.exists():
            fixture_path.write_text(output)
            return  # First run — create fixture

        expected = fixture_path.read_text()
        assert output == expected, (
            f"Export format changed! Run with UPDATE_SNAPSHOTS=1 to update fixture.\n"
            f"Diff:\n{_diff(expected, output)}"
        )

    def test_full_export_format(self):
        result = _standard_result()
        output = generate_export(result, full=True)
        fixture_path = FIXTURES_DIR / "full_export.md"

        if os.environ.get("UPDATE_SNAPSHOTS"):
            fixture_path.write_text(output)
            return

        if not fixture_path.exists():
            fixture_path.write_text(output)
            return

        expected = fixture_path.read_text()
        assert output == expected, (
            f"Full export format changed! Run with UPDATE_SNAPSHOTS=1 to update fixture.\n"
            f"Diff:\n{_diff(expected, output)}"
        )
