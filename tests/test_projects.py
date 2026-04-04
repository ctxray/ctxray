"""Tests for ctxray projects command."""

from __future__ import annotations

from pathlib import Path

from ctxray.output.projects_terminal import render_projects_table
from ctxray.storage.db import PromptDB


def _meta(db: PromptDB, session_id: str, project: str, source: str = "claude-code", **kw):
    """Helper to insert session_meta with required fields."""
    db.upsert_session_meta(
        session_id=session_id,
        source=source,
        project=project,
        start_time=kw.get("start_time", "2026-03-15T10:00:00Z"),
        end_time=kw.get("end_time", "2026-03-15T11:00:00Z"),
        duration_seconds=kw.get("duration_seconds", 3600),
        prompt_count=kw.get("prompt_count", 10),
        tool_call_count=kw.get("tool_call_count", 5),
        error_count=kw.get("error_count", 0),
        final_status=kw.get("final_status", "completed"),
        avg_prompt_length=kw.get("avg_prompt_length", 50.0),
        effectiveness_score=kw.get("effectiveness_score", 0.7),
    )


class TestGetProjectSummary:
    def test_empty_db(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        assert db.get_project_summary() == []

    def test_single_project(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        _meta(db, "s1", "myproject", prompt_count=5)
        result = db.get_project_summary()
        assert len(result) == 1
        assert result[0]["project"] == "myproject"
        assert result[0]["session_count"] == 1
        assert result[0]["prompt_count"] == 5

    def test_multiple_projects(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        for i, proj in enumerate(["alpha", "beta", "gamma"]):
            for j in range(i + 1):
                _meta(db, f"{proj}-s{j}", proj)
        result = db.get_project_summary()
        assert len(result) == 3
        assert result[0]["project"] == "gamma"
        assert result[0]["session_count"] == 3

    def test_source_filter(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        _meta(db, "s1", "proj1", source="claude-code")
        _meta(db, "s2", "proj2", source="cursor")
        result = db.get_project_summary(source="claude-code")
        assert len(result) == 1
        assert result[0]["project"] == "proj1"

    def test_quality_scores(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        _meta(db, "s1", "myproject")
        db.upsert_session_quality(
            session_id="s1",
            quality_score=75.0,
            prompt_quality_score=70.0,
            efficiency_score=80.0,
            focus_score=85.0,
            outcome_score=65.0,
            has_abandonment=False,
            has_escalation=False,
            stall_turns=0,
            session_type="feature-dev",
            quality_insight="Good",
        )
        result = db.get_project_summary()
        assert len(result) == 1
        assert result[0]["avg_quality"] == 75.0
        assert result[0]["avg_efficiency"] == 80.0

    def test_frustration_counts(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        for i in range(3):
            _meta(db, f"s{i}", "troubled", error_count=3)
            db.upsert_session_quality(
                session_id=f"s{i}",
                quality_score=40.0,
                prompt_quality_score=35.0,
                efficiency_score=30.0,
                focus_score=45.0,
                outcome_score=40.0,
                has_abandonment=i < 2,
                has_escalation=i == 0,
                stall_turns=2,
                session_type="debug",
                quality_insight="Frustrating",
            )
        result = db.get_project_summary()
        assert result[0]["abandonment_count"] == 2
        assert result[0]["escalation_count"] == 1

    def test_excludes_empty_project(self, tmp_path: Path) -> None:
        db = PromptDB(tmp_path / "test.db")
        _meta(db, "s1", "")
        _meta(db, "s2", "real-project")
        result = db.get_project_summary()
        assert len(result) == 1
        assert result[0]["project"] == "real-project"


class TestRenderProjectsTable:
    def test_empty_projects(self) -> None:
        output = render_projects_table([])
        assert "No project data" in output

    def test_renders_table(self) -> None:
        data = [
            {
                "project": "myproject",
                "session_count": 10,
                "prompt_count": 50,
                "avg_quality": 72.0,
                "avg_efficiency": 65.0,
                "avg_focus": 80.0,
                "avg_outcome": None,
                "abandonment_count": 1,
                "escalation_count": 0,
                "sources": "claude-code",
                "earliest": None,
                "latest": None,
            }
        ]
        output = render_projects_table(data)
        assert "myproject" in output
        assert "72" in output

    def test_multiple_projects(self) -> None:
        data = [
            {
                "project": "alpha",
                "session_count": 5,
                "prompt_count": 20,
                "avg_quality": 80.0,
                "avg_efficiency": 75.0,
                "avg_focus": 85.0,
                "avg_outcome": None,
                "abandonment_count": 0,
                "escalation_count": 0,
                "sources": "claude-code",
                "earliest": None,
                "latest": None,
            },
            {
                "project": "beta",
                "session_count": 3,
                "prompt_count": 15,
                "avg_quality": 45.0,
                "avg_efficiency": 40.0,
                "avg_focus": 50.0,
                "avg_outcome": None,
                "abandonment_count": 2,
                "escalation_count": 1,
                "sources": "cursor",
                "earliest": None,
                "latest": None,
            },
        ]
        output = render_projects_table(data)
        assert "alpha" in output
        assert "beta" in output
        assert "2 projects" in output


class TestProjectsCLI:
    def test_help(self) -> None:
        from typer.testing import CliRunner

        from ctxray.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0
        assert "project" in result.output.lower()

    def test_empty_json(self, tmp_path: Path) -> None:
        import json
        import os

        from typer.testing import CliRunner

        from ctxray.cli import app

        os.environ["CTXRAY_DB_PATH"] = str(tmp_path / "test.db")
        runner = CliRunner()
        result = runner.invoke(app, ["projects", "--json"])
        del os.environ["CTXRAY_DB_PATH"]
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []
