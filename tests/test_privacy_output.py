"""Tests for render_privacy terminal output."""

from __future__ import annotations

import re

from ctxray.output.terminal import render_privacy

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes for assertion clarity."""
    return _ANSI_RE.sub("", text)


def _empty_data() -> dict:
    return {
        "total_prompts": 0,
        "cloud_prompts": 0,
        "local_prompts": 0,
        "training_exposed": 0,
        "training_safe": 0,
        "sources": [],
    }


def _basic_data() -> dict:
    return {
        "total_prompts": 150,
        "cloud_prompts": 80,
        "local_prompts": 70,
        "training_exposed": 20,
        "training_safe": 130,
        "sources": [
            {
                "name": "Claude Code",
                "count": 70,
                "cloud": False,
                "retention": "Local only",
                "training": "none",
                "note": "Local tool",
            },
            {
                "name": "ChatGPT",
                "count": 50,
                "cloud": True,
                "retention": "30 days",
                "training": "opt-out",
                "note": "Cloud service",
            },
            {
                "name": "Claude.ai",
                "count": 30,
                "cloud": True,
                "retention": "90 days",
                "training": "opt-in",
                "note": "Web chat",
            },
        ],
    }


def _no_training_exposure_data() -> dict:
    return {
        "total_prompts": 50,
        "cloud_prompts": 0,
        "local_prompts": 50,
        "training_exposed": 0,
        "training_safe": 50,
        "sources": [
            {
                "name": "Claude Code",
                "count": 50,
                "cloud": False,
                "retention": "Local only",
                "training": "none",
                "note": "Local tool",
            },
        ],
    }


class TestRenderPrivacyEmpty:
    """Test rendering with no prompt data."""

    def test_empty_data_shows_no_data_message(self):
        output = render_privacy(_empty_data())
        assert "No prompt data yet" in output

    def test_empty_data_does_not_show_header(self):
        output = render_privacy(_empty_data())
        assert "Privacy Exposure" not in output


class TestRenderPrivacyHeader:
    """Test the header and totals section."""

    def test_shows_header(self):
        output = render_privacy(_basic_data())
        assert "Privacy Exposure" in output

    def test_shows_total_prompts(self):
        output = render_privacy(_basic_data())
        assert "150" in output

    def test_shows_cloud_count(self):
        output = render_privacy(_basic_data())
        assert "80" in output

    def test_shows_local_count(self):
        output = render_privacy(_basic_data())
        assert "70" in output

    def test_shows_cloud_percentage(self):
        output = _strip_ansi(render_privacy(_basic_data()))
        # 80/150 = 53%
        assert "53%" in output

    def test_shows_local_percentage(self):
        output = _strip_ansi(render_privacy(_basic_data()))
        # 70/150 = 47%
        assert "47%" in output


class TestRenderPrivacyTrainingWarning:
    """Test the training exposure warning."""

    def test_training_warning_when_exposed(self):
        output = render_privacy(_basic_data())
        # training_exposed = 20, should show a warning
        assert "20" in output
        assert "training" in output.lower()

    def test_no_training_warning_when_safe(self):
        output = render_privacy(_no_training_exposure_data())
        # Should not contain a training warning line
        # We check that the word "warning" or "may train" style message is absent
        assert "may train" not in output.lower()


class TestRenderPrivacyTable:
    """Test the per-tool breakdown table."""

    def test_shows_tool_names(self):
        output = render_privacy(_basic_data())
        assert "Claude Code" in output
        assert "ChatGPT" in output
        assert "Claude.ai" in output

    def test_shows_retention(self):
        output = render_privacy(_basic_data())
        assert "Local only" in output
        assert "30 days" in output
        assert "90 days" in output

    def test_shows_cloud_indicator(self):
        output = render_privacy(_basic_data())
        # Cloud tools should have cloud icon, local should have house icon
        assert "\u2601" in output or "\u2601\ufe0f" in output or "cloud" in output.lower()

    def test_shows_training_status(self):
        output = render_privacy(_basic_data())
        assert "opt-out" in output
        assert "opt-in" in output


class TestRenderPrivacyFooter:
    """Test the disclaimer footer."""

    def test_shows_footer_disclaimer(self):
        output = render_privacy(_basic_data())
        assert "March 2026" in output or "vendor docs" in output.lower()


class TestRenderPrivacyReturnType:
    """Test that the function returns a string."""

    def test_returns_string(self):
        result = render_privacy(_basic_data())
        assert isinstance(result, str)

    def test_empty_returns_string(self):
        result = render_privacy(_empty_data())
        assert isinstance(result, str)
