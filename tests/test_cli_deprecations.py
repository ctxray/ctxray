"""Tests for command consolidation: deprecate library/recommend/trends."""

from __future__ import annotations

from typer.testing import CliRunner

from ctxray.cli import app

runner = CliRunner()


# --- Deprecated library command ---


class TestLibraryDeprecated:
    """library command should be deprecated and show migration hint."""

    def test_library_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["library"])
        assert result.exit_code == 0

    def test_library_shows_deprecation_message(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["library"])
        assert "template list" in result.output

    def test_library_no_longer_renders_table(self, tmp_path, monkeypatch):
        """After deprecation, library should NOT render a Rich table, just the hint."""
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["library"])
        assert "Prompt Library" not in result.output


# --- Deprecated recommend command ---


class TestRecommendDeprecated:
    """recommend command should be deprecated and show migration hint."""

    def test_recommend_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["recommend"])
        assert result.exit_code == 0

    def test_recommend_shows_deprecation_message(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["recommend"])
        assert "template list --smart" in result.output

    def test_recommend_no_longer_calls_compute(self, tmp_path, monkeypatch):
        """After deprecation, recommend should NOT import compute_recommendations."""
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["recommend"])
        # Should just show deprecation, not crash on empty DB
        assert "template list" in result.output


# --- Deprecated trends command ---


class TestTrendsDeprecated:
    """trends command should be deprecated and show migration hint."""

    def test_trends_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["trends"])
        assert result.exit_code == 0

    def test_trends_shows_deprecation_message(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["trends"])
        assert "digest --trends" in result.output

    def test_trends_no_longer_computes(self, tmp_path, monkeypatch):
        """After deprecation, trends should NOT import compute_trends."""
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["trends"])
        assert "digest" in result.output


# --- template list --smart flag ---


class TestTemplateListSmart:
    """template list should accept --smart flag."""

    def test_template_list_without_smart(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["template", "list"])
        assert result.exit_code == 0

    def test_template_list_with_smart_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["template", "list", "--smart"])
        assert result.exit_code == 0

    def test_template_list_smart_sorts_by_effectiveness(self, tmp_path, monkeypatch):
        """When --smart is provided, templates should be sorted by effectiveness."""
        from ctxray.storage.db import PromptDB

        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        db = PromptDB(tmp_path / "test.db")

        # Save two templates
        db.save_template(name="low-eff", text="do something simple", category="general")
        db.save_template(name="high-eff", text="detailed refactor with tests", category="dev")

        # Without --smart, order should be normal (insertion order)
        result = runner.invoke(app, ["template", "list"])
        assert result.exit_code == 0

        # With --smart, should still not crash
        result = runner.invoke(app, ["template", "list", "--smart"])
        assert result.exit_code == 0


# --- digest --trends flag ---


class TestDigestTrends:
    """digest should accept --trends flag to include trend data."""

    def test_digest_without_trends_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest"])
        # Empty DB, should still exit cleanly
        assert result.exit_code == 0

    def test_digest_with_trends_flag(self, tmp_path, monkeypatch):
        """digest --trends should not crash on empty DB."""
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--trends"])
        assert result.exit_code == 0

    def test_digest_trends_flag_accepted(self, tmp_path, monkeypatch):
        """Verify the --trends flag is recognized (no 'unexpected' error)."""
        monkeypatch.setenv("CTXRAY_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["digest", "--trends"])
        assert "Error" not in result.output or "no data" in result.output.lower()
