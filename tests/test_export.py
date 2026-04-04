"""Tests for the export markdown formatter."""

from __future__ import annotations

from ctxray.core.conversation import (
    Conversation,
    ConversationTurn,
    DistillResult,
    DistillStats,
)


def _make_turn(
    role: str,
    text: str,
    idx: int,
    importance: float = 0.5,
    signal_scores: dict | None = None,
    tool_calls: int = 0,
    has_error: bool = False,
    tool_use_paths: list | None = None,
) -> ConversationTurn:
    t = ConversationTurn(
        role=role,
        text=text,
        timestamp="2026-03-24T10:00:00Z",
        turn_index=idx,
        importance=importance,
        tool_calls=tool_calls,
        has_error=has_error,
        tool_use_paths=tool_use_paths or [],
    )
    if signal_scores:
        t.signal_scores = signal_scores
    return t


def _make_result(
    user_texts: list[str],
    signal_scores_list: list[dict] | None = None,
    importances: list[float] | None = None,
    project: str = "myproject",
    files_changed: list[str] | None = None,
    threshold: float = 0.3,
    duration: int = 2700,
) -> DistillResult:
    """Build a DistillResult with interleaved user/assistant turns."""
    default_scores = {
        "position": 0.5,
        "length": 0.5,
        "tool_trigger": 0.5,
        "error_recovery": 0.0,
        "semantic_shift": 0.5,
        "uniqueness": 0.5,
    }
    turns = []
    filtered = []
    idx = 0
    for i, text in enumerate(user_texts):
        scores = signal_scores_list[i] if signal_scores_list else default_scores
        imp = importances[i] if importances else 0.5
        user = _make_turn("user", text, idx, imp, scores)
        turns.append(user)
        idx += 1
        asst = _make_turn(
            "assistant",
            f"Done: {text}",
            idx,
            imp,
            tool_calls=2,
            tool_use_paths=["src/foo.py"],
        )
        turns.append(asst)
        idx += 1
        if imp >= threshold:
            filtered.extend([user, asst])

    conv = Conversation(
        session_id="test-123",
        source="claude-code",
        project=project,
        turns=turns,
        duration_seconds=duration,
    )
    return DistillResult(
        conversation=conv,
        filtered_turns=filtered,
        threshold=threshold,
        files_changed=files_changed if files_changed is not None else ["src/foo.py", "src/bar.py"],
        stats=DistillStats(
            total_turns=len(turns),
            kept_turns=len(filtered),
            retention_ratio=len(filtered) / len(turns) if turns else 0.0,
            total_duration_seconds=duration,
        ),
    )


class TestExportBasic:
    def test_export_contains_header(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Fix the bug", "Add tests", "Deploy"])
        output = generate_export(result)
        assert "# Session Context: myproject" in output
        assert "claude-code" in output

    def test_export_contains_goal(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Implement authentication system", "Add tests"])
        output = generate_export(result)
        assert "## Goal" in output
        assert "authentication" in output.lower()

    def test_export_contains_current_state(self):
        from ctxray.output.export import generate_export

        result = _make_result(
            ["Start work", "Middle work", "Final state of the session"],
            importances=[0.8, 0.5, 0.7],
        )
        output = generate_export(result)
        assert "## Current State" in output

    def test_export_contains_files_changed(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Do work"], files_changed=["a.py", "b.py"])
        output = generate_export(result)
        assert "## Files Changed" in output
        assert "`a.py`" in output

    def test_export_contains_token_estimate(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Do work"])
        output = generate_export(result)
        assert "~" in output and "tokens" in output

    def test_export_is_markdown(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Fix bug", "Add feature"])
        output = generate_export(result)
        assert output.startswith("# Session Context:")


class TestExportSections:
    def test_key_decisions_uses_semantic_shift(self):
        from ctxray.output.export import generate_export

        high_shift = {
            "position": 0.5,
            "length": 0.5,
            "tool_trigger": 0.1,
            "error_recovery": 0.0,
            "semantic_shift": 0.9,
            "uniqueness": 0.5,
        }
        low_shift = {
            "position": 0.5,
            "length": 0.5,
            "tool_trigger": 0.1,
            "error_recovery": 0.0,
            "semantic_shift": 0.1,
            "uniqueness": 0.5,
        }
        result = _make_result(
            ["Start", "Changed direction to new approach", "Continue same"],
            signal_scores_list=[low_shift, high_shift, low_shift],
            importances=[0.5, 0.7, 0.5],
        )
        output = generate_export(result)
        assert "## Key Decisions" in output
        assert "direction" in output.lower() or "approach" in output.lower()

    def test_what_was_done_uses_tool_trigger(self):
        from ctxray.output.export import generate_export

        high_tool = {
            "position": 0.5,
            "length": 0.5,
            "tool_trigger": 0.9,
            "error_recovery": 0.0,
            "semantic_shift": 0.1,
            "uniqueness": 0.5,
        }
        low_tool = {
            "position": 0.5,
            "length": 0.5,
            "tool_trigger": 0.1,
            "error_recovery": 0.0,
            "semantic_shift": 0.1,
            "uniqueness": 0.5,
        }
        result = _make_result(
            ["Start", "Implement the auth module now", "Think about design"],
            signal_scores_list=[low_tool, high_tool, low_tool],
            importances=[0.5, 0.7, 0.5],
        )
        output = generate_export(result)
        assert "## What Was Done" in output

    def test_no_duplicate_turns_across_sections(self):
        from ctxray.output.export import generate_export

        scores = {
            "position": 0.9,
            "length": 0.5,
            "tool_trigger": 0.9,
            "error_recovery": 0.0,
            "semantic_shift": 0.9,
            "uniqueness": 0.5,
        }
        result = _make_result(
            ["Only turn in session"],
            signal_scores_list=[scores],
            importances=[0.9],
        )
        output = generate_export(result)
        lines = output.split("\n")
        turn_text_count = sum(1 for line in lines if "only turn" in line.lower())
        assert turn_text_count <= 1


class TestExportCurrentState:
    def test_current_state_omitted_for_single_turn(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Only one turn"])
        output = generate_export(result)
        assert "## Current State" not in output

    def test_current_state_uses_last_important_turn(self):
        from ctxray.output.export import generate_export

        result = _make_result(
            ["Start", "Middle", "All tests passing, ready to deploy"],
            importances=[0.8, 0.4, 0.7],
        )
        output = generate_export(result)
        assert "## Current State" in output


class TestExportResume:
    def test_resume_detected_with_forward_keyword(self):
        from ctxray.output.export import generate_export

        result = _make_result(
            ["Start work", "Do stuff", "Next we need to add integration tests"],
            importances=[0.8, 0.5, 0.7],
        )
        output = generate_export(result)
        assert "## Resume" in output
        assert "integration tests" in output.lower()

    def test_resume_omitted_without_forward_keyword(self):
        from ctxray.output.export import generate_export

        result = _make_result(
            ["Start work", "Do stuff", "Thanks that looks good"],
            importances=[0.8, 0.5, 0.7],
        )
        output = generate_export(result)
        assert "## Resume" not in output

    def test_resume_detects_chinese_keywords(self):
        from ctxray.output.export import generate_export

        zh_next = "\u63a5\u4e0b\u6765\u9700\u8981\u52a0\u6d4b\u8bd5"
        result_zh = _make_result(
            ["\u5f00\u59cb", "\u5904\u7406\u4e2d", zh_next],
            importances=[0.8, 0.5, 0.7],
        )
        output = generate_export(result_zh)
        assert "## Resume" in output


class TestExportFull:
    def test_full_mode_includes_assistant_summary(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Fix the bug", "Add tests"])
        output = generate_export(result, full=True)
        assert "**Result:**" in output

    def test_default_mode_excludes_assistant(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Fix the bug", "Add tests"])
        output = generate_export(result, full=False)
        assert "**Result:**" not in output


class TestExportEdgeCases:
    def test_empty_filtered_turns_fallback(self):
        from ctxray.output.export import generate_export

        result = _make_result(
            ["Start", "Middle", "End"],
            importances=[0.1, 0.1, 0.1],
            threshold=0.9,
        )
        result.filtered_turns = []
        output = generate_export(result)
        assert "## Goal" in output
        assert "threshold" in output.lower()

    def test_no_project_name(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Do work"], project=None)
        result.conversation.project = None
        output = generate_export(result)
        assert "# Session Context" in output

    def test_no_files_changed(self):
        from ctxray.output.export import generate_export

        result = _make_result(["Do work"], files_changed=[])
        output = generate_export(result)
        assert "## Files Changed" not in output

    def test_files_changed_capped_at_10(self):
        from ctxray.output.export import generate_export

        files = [f"file{i}.py" for i in range(20)]
        result = _make_result(["Do work"], files_changed=files)
        output = generate_export(result)
        assert "file9.py" in output
        assert "file10.py" not in output
