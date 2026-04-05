"""Tests for cross-tool comparison."""

from __future__ import annotations

from ctxray.core.tools_comparison import (
    ToolComparison,
    ToolStats,
    _aggregate_source,
    _generate_insights,
)


class TestAggregateSource:
    def test_empty_features(self):
        result = _aggregate_source([])
        assert result["prompt_count"] == 0
        assert result["avg_words"] == 0.0
        assert result["avg_score"] == 0.0
        assert result["top_task_type"] == "-"

    def test_single_feature(self):
        features = [
            {
                "word_count": 20,
                "overall_score": 75,
                "task_type": "debug",
                "has_file_path": True,
                "has_error_message": True,
            }
        ]
        result = _aggregate_source(features)
        assert result["prompt_count"] == 1
        assert result["avg_words"] == 20.0
        assert result["avg_score"] == 75.0
        assert result["top_task_type"] == "debug"
        assert result["file_ref_rate"] == 1.0
        assert result["error_context_rate"] == 1.0

    def test_multiple_features_averages(self):
        features = [
            {"word_count": 20, "overall_score": 80, "task_type": "debug"},
            {"word_count": 30, "overall_score": 60, "task_type": "debug"},
            {"word_count": 10, "overall_score": 70, "task_type": "implement"},
        ]
        result = _aggregate_source(features)
        assert result["prompt_count"] == 3
        assert result["avg_words"] == 20.0
        assert result["avg_score"] == 70.0
        assert result["top_task_type"] == "debug"  # 2 debug vs 1 implement

    def test_error_context_rate_only_debug(self):
        """Error context rate is computed over debug prompts only."""
        features = [
            {
                "word_count": 20,
                "overall_score": 80,
                "task_type": "debug",
                "has_error_message": True,
            },
            {
                "word_count": 20,
                "overall_score": 80,
                "task_type": "debug",
                "has_error_message": False,
            },
            {"word_count": 20, "overall_score": 80, "task_type": "implement"},  # not debug
        ]
        result = _aggregate_source(features)
        assert result["error_context_rate"] == 0.5  # 1 of 2 debug prompts


class TestGenerateInsights:
    def _make_stats(self, source, score, words, file_rate=0.5, error_rate=0.5):
        return ToolStats(
            source=source,
            prompt_count=10,
            avg_words=words,
            avg_score=score,
            top_task_type="debug",
            error_context_rate=error_rate,
            file_ref_rate=file_rate,
        )

    def test_single_tool_no_insights(self):
        tools = [self._make_stats("claude-code", 70, 30)]
        insights = _generate_insights(tools)
        assert insights == []

    def test_score_gap_surfaces_insight(self):
        tools = [
            self._make_stats("claude-code", 75, 30),
            self._make_stats("cursor", 55, 20),
        ]
        insights = _generate_insights(tools)
        assert any("claude-code" in i and "highest-scoring" in i for i in insights)

    def test_no_insight_when_scores_close(self):
        tools = [
            self._make_stats("claude-code", 60, 25),
            self._make_stats("cursor", 62, 24),
        ]
        insights = _generate_insights(tools)
        # scores within 5pts, words within 8 → no insights
        assert insights == []

    def test_word_count_gap_surfaces_insight(self):
        tools = [
            self._make_stats("claude-code", 70, 40),
            self._make_stats("cursor", 68, 18),
        ]
        insights = _generate_insights(tools)
        assert any("40 words" in i and "22 more" in i for i in insights)

    def test_file_ref_gap_surfaces_insight(self):
        tools = [
            self._make_stats("claude-code", 70, 25, file_rate=0.8),
            self._make_stats("cursor", 70, 25, file_rate=0.4),
        ]
        insights = _generate_insights(tools)
        assert any("file paths" in i for i in insights)


class TestToolComparisonDataclass:
    def test_defaults(self):
        c = ToolComparison()
        assert c.tools == []
        assert c.insights == []
