"""Tests for the dashboard feature."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from reprompt.core.dashboard import DashboardData, build_dashboard_data


class TestZeroState:
    """Dashboard when DB has no data."""

    def test_zero_state_no_sessions_found(self):
        """No AI tools installed -> empty discoveries."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 0}
        with patch("reprompt.core.dashboard._discover_sessions") as mock_disc:
            mock_disc.return_value = []
            data = build_dashboard_data(db)
        assert data.has_data is False
        assert data.discoveries == []

    def test_zero_state_sessions_found(self):
        """AI tools found -> show discoveries."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 0}
        with patch("reprompt.core.dashboard._discover_sessions") as mock_disc:
            mock_disc.return_value = [
                {"adapter": "claude-code", "sessions": 12, "turns_estimate": 847},
                {"adapter": "cursor", "sessions": 3, "turns_estimate": 124},
            ]
            data = build_dashboard_data(db)
        assert data.has_data is False
        assert len(data.discoveries) == 2
        assert data.discoveries[0]["adapter"] == "claude-code"


class TestDataState:
    """Dashboard when DB has data."""

    def test_data_state_basic(self):
        """Shows stats from DB."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 47}
        db.get_prompts_in_range.return_value = [{"source": "claude-code"} for _ in range(47)]
        with patch("reprompt.core.dashboard._compute_avg_score") as mock_score:
            mock_score.return_value = {"overall": 52, "debug": 31, "implement": 64}
            with patch("reprompt.core.dashboard._compute_avg_compressibility") as mock_comp:
                mock_comp.return_value = 0.23
                data = build_dashboard_data(db)
        assert data.has_data is True
        assert data.prompt_count == 47
        assert data.avg_score["overall"] == 52

    def test_data_state_empty_week(self):
        """Has historical data but nothing in last 7 days."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 100}
        db.get_prompts_in_range.return_value = []
        with patch("reprompt.core.dashboard._compute_avg_score") as mock_score:
            mock_score.return_value = {"overall": 0}
            with patch("reprompt.core.dashboard._compute_avg_compressibility") as mock_comp:
                mock_comp.return_value = 0.0
                data = build_dashboard_data(db)
        assert data.has_data is True
        assert data.prompt_count == 0

    def test_session_count_from_session_ids(self):
        """Session count uses unique session_id values."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 10}
        db.get_prompts_in_range.return_value = [
            {"session_id": "s1", "source": "test"},
            {"session_id": "s1", "source": "test"},
            {"session_id": "s2", "source": "test"},
            {"session_id": "s3", "source": "test"},
        ]
        with patch("reprompt.core.dashboard._compute_avg_score") as mock_score:
            mock_score.return_value = {"overall": 50}
            with patch("reprompt.core.dashboard._compute_avg_compressibility") as mock_comp:
                mock_comp.return_value = 0.1
                data = build_dashboard_data(db)
        assert data.session_count == 3

    def test_long_sessions_counted(self):
        """Long sessions are counted from SQL query."""
        db = MagicMock()
        db.get_stats.return_value = {"total_prompts": 200}
        db.get_prompts_in_range.return_value = [
            {"session_id": "s1", "source": "test"} for _ in range(50)
        ]
        # Mock _conn for the long sessions query
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            {"session_id": "s1", "cnt": 80},
            {"session_id": "s2", "cnt": 65},
        ]
        db._conn.return_value = mock_conn
        with patch("reprompt.core.dashboard._compute_avg_score") as mock_score:
            mock_score.return_value = {"overall": 45}
            with patch("reprompt.core.dashboard._compute_avg_compressibility") as mock_comp:
                mock_comp.return_value = 0.15
                data = build_dashboard_data(db)
        assert data.long_sessions == 2


class TestComputeAvgScore:
    """Tests for _compute_avg_score."""

    def test_no_features(self):
        from reprompt.core.dashboard import _compute_avg_score

        db = MagicMock()
        db.get_all_features.return_value = []
        result = _compute_avg_score(db)
        assert result == {"overall": 0}

    def test_basic_average(self):
        from reprompt.core.dashboard import _compute_avg_score

        db = MagicMock()
        db.get_all_features.return_value = [
            {"overall_score": 60, "task_type": "debug"},
            {"overall_score": 80, "task_type": "debug"},
            {"overall_score": 40, "task_type": "implement"},
        ]
        result = _compute_avg_score(db)
        assert result["overall"] == 60  # (60+80+40)/3 = 60
        assert result["debug"] == 70  # (60+80)/2 = 70
        assert result["implement"] == 40

    def test_exception_returns_zero(self):
        from reprompt.core.dashboard import _compute_avg_score

        db = MagicMock()
        db.get_all_features.side_effect = Exception("DB error")
        result = _compute_avg_score(db)
        assert result == {"overall": 0}

    def test_uses_only_last_50(self):
        from reprompt.core.dashboard import _compute_avg_score

        db = MagicMock()
        # Return 100 features, only first 50 should be used
        db.get_all_features.return_value = [
            {"overall_score": 100, "task_type": "debug"} for _ in range(100)
        ]
        result = _compute_avg_score(db)
        # Should still work (sliced to 50)
        assert result["overall"] == 100


class TestComputeAvgCompressibility:
    """Tests for _compute_avg_compressibility."""

    def test_no_features(self):
        from reprompt.core.dashboard import _compute_avg_compressibility

        db = MagicMock()
        db.get_all_features.return_value = []
        result = _compute_avg_compressibility(db)
        assert result == 0.0

    def test_basic_average(self):
        from reprompt.core.dashboard import _compute_avg_compressibility

        db = MagicMock()
        db.get_all_features.return_value = [
            {"compressibility": 0.2},
            {"compressibility": 0.4},
        ]
        result = _compute_avg_compressibility(db)
        assert abs(result - 0.3) < 0.01

    def test_exception_returns_zero(self):
        from reprompt.core.dashboard import _compute_avg_compressibility

        db = MagicMock()
        db.get_all_features.side_effect = Exception("DB error")
        result = _compute_avg_compressibility(db)
        assert result == 0.0

    def test_skips_zero_compressibility(self):
        from reprompt.core.dashboard import _compute_avg_compressibility

        db = MagicMock()
        db.get_all_features.return_value = [
            {"compressibility": 0.0},
            {"compressibility": 0.4},
        ]
        result = _compute_avg_compressibility(db)
        # 0.0 is falsy so skipped, only 0.4
        assert abs(result - 0.4) < 0.01


class TestDiscoverSessions:
    """Tests for _discover_sessions."""

    def test_no_adapters_installed(self):
        from reprompt.core.dashboard import _discover_sessions

        with patch("reprompt.core.dashboard.get_adapters") as mock_adapters:
            adapter1 = MagicMock()
            adapter1.detect_installed.return_value = False
            mock_adapters.return_value = [adapter1]
            result = _discover_sessions()
        assert result == []

    def test_adapter_installed_with_sessions(self, tmp_path):
        from reprompt.core.dashboard import _discover_sessions

        # Create a fake session directory with files
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        (session_dir / "session1.jsonl").write_text("line1\nline2\nline3\n")
        (session_dir / "session2.jsonl").write_text("line1\n")

        with patch("reprompt.core.dashboard.get_adapters") as mock_adapters:
            adapter = MagicMock()
            adapter.name = "test-tool"
            adapter.detect_installed.return_value = True
            adapter.default_session_path = str(session_dir)
            # No discover_sessions method
            del adapter.discover_sessions
            mock_adapters.return_value = [adapter]
            result = _discover_sessions()

        assert len(result) == 1
        assert result[0]["adapter"] == "test-tool"
        assert result[0]["sessions"] == 2

    def test_adapter_with_discover_sessions(self, tmp_path):
        from reprompt.core.dashboard import _discover_sessions

        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        with patch("reprompt.core.dashboard.get_adapters") as mock_adapters:
            adapter = MagicMock()
            adapter.name = "custom-tool"
            adapter.detect_installed.return_value = True
            adapter.default_session_path = str(session_dir)
            adapter.discover_sessions.return_value = [
                session_dir / "a.json",
                session_dir / "b.json",
                session_dir / "c.json",
            ]
            mock_adapters.return_value = [adapter]
            result = _discover_sessions()

        assert len(result) == 1
        assert result[0]["adapter"] == "custom-tool"
        assert result[0]["sessions"] == 3


class TestDashboardOutput:
    """Tests for Rich terminal rendering."""

    def test_render_zero_state_no_crash(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(has_data=False, discoveries=[])
        output = render_dashboard(data)
        assert "reprompt" in output.lower()

    def test_render_zero_state_with_discoveries(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=False,
            discoveries=[
                {"adapter": "claude-code", "sessions": 12, "turns_estimate": 847},
            ],
        )
        output = render_dashboard(data)
        assert "claude-code" in output
        assert "12" in output
        assert "scan" in output.lower()

    def test_render_data_state_no_crash(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=True,
            prompt_count=47,
            session_count=12,
            avg_score={"overall": 52, "debug": 31},
            avg_compressibility=0.23,
            long_sessions=3,
        )
        output = render_dashboard(data)
        assert "47" in output

    def test_render_data_state_score_shown(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=True,
            prompt_count=20,
            session_count=5,
            avg_score={"overall": 65},
            avg_compressibility=0.15,
        )
        output = render_dashboard(data)
        assert "65" in output

    def test_render_data_state_compressibility(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=True,
            prompt_count=20,
            session_count=5,
            avg_score={"overall": 50},
            avg_compressibility=0.23,
        )
        output = render_dashboard(data)
        assert "23%" in output

    def test_render_data_state_long_sessions(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=True,
            prompt_count=100,
            session_count=8,
            avg_score={"overall": 55},
            avg_compressibility=0.1,
            long_sessions=3,
        )
        output = render_dashboard(data)
        assert "3" in output
        assert "distill" in output.lower()

    def test_render_data_state_suggestions(self):
        from reprompt.output.dashboard_terminal import render_dashboard

        data = DashboardData(
            has_data=True,
            prompt_count=30,
            session_count=4,
            avg_score={"overall": 45},
            avg_compressibility=0.2,
        )
        output = render_dashboard(data)
        assert "distill" in output.lower()
        assert "insights" in output.lower()
        assert "compress" in output.lower()


class TestDashboardDataclass:
    """Tests for DashboardData defaults."""

    def test_defaults(self):
        data = DashboardData()
        assert data.has_data is False
        assert data.discoveries == []
        assert data.prompt_count == 0
        assert data.session_count == 0
        assert data.avg_score == {}
        assert data.avg_compressibility == 0.0
        assert data.long_sessions == 0

    def test_zero_state_construction(self):
        data = DashboardData(
            has_data=False,
            discoveries=[{"adapter": "test", "sessions": 5, "turns_estimate": 100}],
        )
        assert not data.has_data
        assert len(data.discoveries) == 1

    def test_data_state_construction(self):
        data = DashboardData(
            has_data=True,
            prompt_count=50,
            session_count=10,
            avg_score={"overall": 60},
            avg_compressibility=0.25,
            long_sessions=2,
        )
        assert data.has_data
        assert data.prompt_count == 50
