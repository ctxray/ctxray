"""Tests for terminal and JSON output formatters."""

import json

from reprompt.output.json_out import format_json_report
from reprompt.output.terminal import render_report


def _sample_report_data():
    return {
        "overview": {
            "total_prompts": 100,
            "unique_prompts": 75,
            "sessions_scanned": 20,
            "sources": ["claude-code", "openclaw"],
            "date_range": ("2026-01-01", "2026-03-10"),
        },
        "top_patterns": [
            {"pattern_text": "fix the failing test", "frequency": 10, "category": "debug"},
            {"pattern_text": "add unit tests", "frequency": 8, "category": "test"},
        ],
        "projects": {"myproject": 50, "other": 25},
        "categories": {"debug": 30, "test": 20, "implement": 15, "other": 10},
        "top_terms": [
            {"term": "test", "tfidf_avg": 0.45},
            {"term": "fix", "tfidf_avg": 0.38},
        ],
    }


def test_render_report_contains_sections():
    data = _sample_report_data()
    output = render_report(data)
    assert "Overview" in output or "overview" in output.lower()
    assert "100" in output  # total prompts
    assert "75" in output  # unique prompts


def test_render_report_shows_patterns():
    data = _sample_report_data()
    output = render_report(data)
    assert "fix the failing test" in output
    assert "debug" in output


def test_render_report_shows_projects():
    data = _sample_report_data()
    output = render_report(data)
    assert "myproject" in output


def test_json_output_valid():
    data = _sample_report_data()
    result = format_json_report(data)
    parsed = json.loads(result)
    assert "overview" in parsed
    assert "top_patterns" in parsed


def test_json_output_has_all_keys():
    data = _sample_report_data()
    result = format_json_report(data)
    parsed = json.loads(result)
    assert parsed["overview"]["total_prompts"] == 100
    assert len(parsed["top_patterns"]) == 2


def test_render_report_empty_data():
    data = {
        "overview": {
            "total_prompts": 0,
            "unique_prompts": 0,
            "sessions_scanned": 0,
            "sources": [],
            "date_range": ("", ""),
        },
        "top_patterns": [],
        "projects": {},
        "categories": {},
        "top_terms": [],
    }
    output = render_report(data)
    assert "0" in output  # shows zero counts


def test_render_report_shows_hot_terms():
    """Hot Terms (TF-IDF) table should appear when top_terms data is present."""
    data = _sample_report_data()
    data["top_terms"] = [
        {"term": "test", "tfidf_avg": 0.452, "df": 12},
        {"term": "fix", "tfidf_avg": 0.381, "df": 8},
    ]
    output = render_report(data)
    assert "Hot Phrases" in output or "TF-IDF" in output
    assert "test" in output
    assert "0.452" in output
    assert "12" in output


def test_render_report_shows_clusters():
    """Prompt Clusters section should appear when clusters data is present."""
    data = _sample_report_data()
    data["clusters"] = [
        {"cluster_id": 0, "size": 23, "sample": "Fix the failing test for auth module"},
        {"cluster_id": 1, "size": 18, "sample": "Add unit tests for the user service"},
    ]
    output = render_report(data)
    assert "Cluster" in output
    assert "23" in output
    assert "Fix the failing test" in output


def test_render_report_no_clusters_when_absent():
    """No clusters section when clusters key is missing or empty."""
    data = _sample_report_data()
    data["clusters"] = []
    output = render_report(data)
    assert "Cluster" not in output


def test_truncated_pattern_text_has_ellipsis():
    """Pattern text truncated beyond 40 chars should end with '...'."""
    data = _sample_report_data()
    long_text = "abcdefghij" * 6  # 60 chars, longer than 40
    data["top_patterns"] = [
        {"pattern_text": long_text, "frequency": 5, "category": "debug"},
    ]
    output = render_report(data)
    # Our code adds "..." after the first 40 chars
    assert "..." in output or "\u2026" in output
