"""Tests for digest CLI command and render_digest()."""

from __future__ import annotations

from reprompt.output.terminal import render_digest


class TestRenderDigest:
    def test_render_digest_empty_db(self):
        """render_digest() works with zero-prompt data."""
        data = {
            "period": "7d",
            "current": {"prompt_count": 0, "specificity_score": 0.0, "avg_length": 0.0,
                        "category_distribution": {}},
            "previous": {"prompt_count": 0, "specificity_score": 0.0, "avg_length": 0.0,
                         "category_distribution": {}},
            "count_delta": 0,
            "spec_delta": 0.0,
            "summary": "reprompt: 0 prompts (+0), specificity 0.00 (→)",
        }
        output = render_digest(data)
        assert "digest" in output.lower()
        assert "0" in output

    def test_render_digest_shows_prompt_count(self):
        data = {
            "period": "7d",
            "current": {"prompt_count": 42, "specificity_score": 0.72,
                        "avg_length": 183.0, "category_distribution": {}},
            "previous": {"prompt_count": 37, "specificity_score": 0.65,
                         "avg_length": 160.0, "category_distribution": {}},
            "count_delta": 5,
            "spec_delta": 0.07,
            "summary": "reprompt: 42 prompts (+5), specificity 0.72 (↑)",
        }
        output = render_digest(data)
        assert "42" in output
        assert "+5" in output

    def test_render_digest_shows_specificity_arrow_up(self):
        data = {
            "period": "7d",
            "current": {"prompt_count": 20, "specificity_score": 0.75,
                        "avg_length": 150.0, "category_distribution": {}},
            "previous": {"prompt_count": 18, "specificity_score": 0.60,
                         "avg_length": 130.0, "category_distribution": {}},
            "count_delta": 2,
            "spec_delta": 0.15,
            "summary": "reprompt: 20 prompts (+2), specificity 0.75 (↑)",
        }
        output = render_digest(data)
        assert "↑" in output

    def test_render_digest_shows_categories(self):
        data = {
            "period": "7d",
            "current": {
                "prompt_count": 30,
                "specificity_score": 0.65,
                "avg_length": 120.0,
                "category_distribution": {"implement": 18, "debug": 12},
            },
            "previous": {
                "prompt_count": 25,
                "specificity_score": 0.60,
                "avg_length": 110.0,
                "category_distribution": {"implement": 14, "debug": 11},
            },
            "count_delta": 5,
            "spec_delta": 0.05,
            "summary": "reprompt: 30 prompts (+5), specificity 0.65 (↑)",
        }
        output = render_digest(data)
        assert "implement" in output
        assert "debug" in output

    def test_render_digest_negative_delta(self):
        data = {
            "period": "7d",
            "current": {"prompt_count": 10, "specificity_score": 0.5,
                        "avg_length": 100.0, "category_distribution": {}},
            "previous": {"prompt_count": 20, "specificity_score": 0.6,
                         "avg_length": 120.0, "category_distribution": {}},
            "count_delta": -10,
            "spec_delta": -0.10,
            "summary": "reprompt: 10 prompts (-10), specificity 0.50 (↓)",
        }
        output = render_digest(data)
        assert "-10" in output
        assert "↓" in output
