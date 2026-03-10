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
