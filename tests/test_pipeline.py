"""Tests for pipeline orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from reprompt.config import Settings
from reprompt.core.pipeline import ScanResult, build_report_data, get_adapters, run_scan


def _create_claude_session(
    root: Path, project_name: str, session_name: str, messages: list[dict]
) -> Path:
    """Helper to create a fake Claude Code session file."""
    project_dir = root / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    session_file = project_dir / f"{session_name}.jsonl"
    with open(session_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return session_file


class TestScanResult:
    def test_defaults(self):
        r = ScanResult()
        assert r.total_parsed == 0
        assert r.unique_after_dedup == 0
        assert r.duplicates == 0
        assert r.new_stored == 0
        assert r.sessions_scanned == 0
        assert r.sources == []


class TestGetAdapters:
    def test_returns_list(self):
        adapters = get_adapters()
        assert len(adapters) == 4

    def test_adapter_names(self):
        adapters = get_adapters()
        names = {a.name for a in adapters}
        assert "claude-code" in names
        assert "openclaw" in names
        assert "aider" in names


class TestRunScan:
    def test_empty_path(self, tmp_path):
        """Scan of an empty dir should return zero results."""
        settings = Settings(db_path=tmp_path / "test.db")
        result = run_scan(
            source="claude-code",
            path=str(tmp_path / "nonexistent"),
            settings=settings,
        )
        assert result.total_parsed == 0
        assert result.sessions_scanned == 0

    def test_scan_claude_sessions(self, tmp_path):
        """Scan should find and parse Claude Code session files."""
        sessions_root = tmp_path / "sessions"
        _create_claude_session(
            sessions_root,
            "-Users-test-projects-myapp",
            "session-001",
            [
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": "fix the failing test in the auth module",
                    },
                    "timestamp": "2026-01-15T10:00:00Z",
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "Let me look..."},
                    "timestamp": "2026-01-15T10:00:05Z",
                },
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": "add a new REST endpoint for user management",
                    },
                    "timestamp": "2026-01-15T10:05:00Z",
                },
            ],
        )
        settings = Settings(db_path=tmp_path / "test.db")
        result = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        assert result.sessions_scanned == 1
        assert result.total_parsed == 2  # only user messages that pass filter
        assert result.new_stored > 0
        assert "claude-code" in result.sources

    def test_incremental_scan(self, tmp_path):
        """Second scan should not re-process already-processed sessions."""
        sessions_root = tmp_path / "sessions"
        _create_claude_session(
            sessions_root,
            "-Users-test-projects-app",
            "session-001",
            [
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": "implement the search feature with full-text search",
                    },
                    "timestamp": "2026-01-15T10:00:00Z",
                },
            ],
        )
        settings = Settings(db_path=tmp_path / "test.db")

        r1 = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        assert r1.sessions_scanned == 1

        r2 = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        assert r2.sessions_scanned == 0
        assert r2.total_parsed == 0

    def test_dedup_removes_duplicates(self, tmp_path):
        """Identical prompts across sessions should be deduped."""
        sessions_root = tmp_path / "sessions"
        same_prompt = "fix the failing test in the auth module returning 401"
        for i in range(3):
            _create_claude_session(
                sessions_root,
                f"-Users-test-projects-app{i}",
                f"session-{i:03d}",
                [
                    {
                        "type": "user",
                        "message": {"role": "user", "content": same_prompt},
                        "timestamp": f"2026-01-{15 + i}T10:00:00Z",
                    },
                ],
            )
        settings = Settings(db_path=tmp_path / "test.db")
        result = run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        assert result.sessions_scanned == 3
        assert result.total_parsed == 3
        assert result.duplicates >= 2  # at least 2 exact hash dupes
        assert result.unique_after_dedup == 1

    def test_source_filter(self, tmp_path):
        """Source filter should limit to specific adapter."""
        settings = Settings(db_path=tmp_path / "test.db")
        result = run_scan(source="openclaw", path=str(tmp_path / "nonexistent"), settings=settings)
        assert result.total_parsed == 0
        # Should not have scanned claude-code


class TestBuildReportData:
    def test_empty_db(self, tmp_path):
        """Report from empty DB should return valid structure."""
        settings = Settings(db_path=tmp_path / "test.db")
        data = build_report_data(settings=settings)
        assert "overview" in data
        assert "top_patterns" in data
        assert "projects" in data
        assert "categories" in data
        assert "top_terms" in data
        assert data["overview"]["total_prompts"] == 0

    def test_report_after_scan(self, tmp_path):
        """Report after scan should contain populated data."""
        sessions_root = tmp_path / "sessions"
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": "fix the failing test in the auth module"},
                "timestamp": "2026-01-15T10:00:00Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "add comprehensive unit tests for the user service",
                },
                "timestamp": "2026-01-15T10:05:00Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "refactor the database layer to use connection pooling",
                },
                "timestamp": "2026-01-15T10:10:00Z",
            },
        ]
        _create_claude_session(sessions_root, "-Users-test-projects-app", "session-001", messages)
        settings = Settings(db_path=tmp_path / "test.db")

        run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        data = build_report_data(settings=settings)

        assert data["overview"]["total_prompts"] >= 3
        assert data["overview"]["unique_prompts"] >= 3
        assert len(data["top_terms"]) > 0
        assert len(data["categories"]) > 0

    def test_report_has_project_distribution(self, tmp_path):
        """Report should include per-project prompt counts."""
        sessions_root = tmp_path / "sessions"
        _create_claude_session(
            sessions_root,
            "-Users-test-projects-webapp",
            "session-001",
            [
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": "implement user authentication with JWT tokens",
                    },
                    "timestamp": "2026-01-15T10:00:00Z",
                },
            ],
        )
        settings = Settings(db_path=tmp_path / "test.db")
        run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        data = build_report_data(settings=settings)
        assert len(data["projects"]) > 0

    def test_report_includes_clusters_with_enough_data(self, tmp_path):
        """build_report_data should include 'clusters' key when >= 5 unique texts."""
        sessions_root = tmp_path / "sessions"
        # Use very distinct prompts to survive semantic dedup
        distinct_texts = [
            "Debug the authentication middleware failing with 403 errors",
            "Write unit tests for the payment processing module using pytest",
            "Refactor the database connection pooling to use async context managers",
            "Explain how the Kubernetes ingress controller routes traffic",
            "Add a new REST API endpoint for user profile photo uploads",
            "Review the CI pipeline configuration for security vulnerabilities",
            "Configure nginx reverse proxy with SSL termination and caching",
        ]
        messages = [
            {
                "type": "user",
                "message": {"role": "user", "content": text},
                "timestamp": f"2026-01-{15 + i}T10:00:00Z",
            }
            for i, text in enumerate(distinct_texts)
        ]
        _create_claude_session(sessions_root, "-Users-test-projects-app", "session-001", messages)
        settings = Settings(db_path=tmp_path / "test.db")
        run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        data = build_report_data(settings=settings)

        assert "clusters" in data
        assert len(data["clusters"]) > 0
        # Each cluster entry should have cluster_id, size, and sample
        for c in data["clusters"]:
            assert "cluster_id" in c
            assert "size" in c
            assert "sample" in c

    def test_report_no_clusters_with_few_texts(self, tmp_path):
        """build_report_data should return empty clusters when < 5 texts."""
        sessions_root = tmp_path / "sessions"
        _create_claude_session(
            sessions_root,
            "-Users-test-projects-app",
            "session-001",
            [
                {
                    "type": "user",
                    "message": {"role": "user", "content": "fix the auth bug"},
                    "timestamp": "2026-01-15T10:00:00Z",
                },
                {
                    "type": "user",
                    "message": {"role": "user", "content": "add a test"},
                    "timestamp": "2026-01-15T10:05:00Z",
                },
            ],
        )
        settings = Settings(db_path=tmp_path / "test.db")
        run_scan(source="claude-code", path=str(sessions_root), settings=settings)
        data = build_report_data(settings=settings)

        assert "clusters" in data
        assert data["clusters"] == []
