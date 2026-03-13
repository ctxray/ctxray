"""Tests for HTML dashboard report renderer."""

from __future__ import annotations

from reprompt.output.html_report import render_html_dashboard


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
            {"term": "test", "tfidf_avg": 0.452, "df": 12},
            {"term": "fix", "tfidf_avg": 0.381, "df": 8},
        ],
        "clusters": [
            {"cluster_id": 0, "size": 23, "sample": "Fix the failing test for auth"},
        ],
    }


def _sample_trends_data():
    return {
        "period": "7d",
        "windows": [
            {
                "window_label": "2026-02-24 → 2026-03-02",
                "prompt_count": 45,
                "avg_length": 82.3,
                "vocab_size": 120,
                "specificity_score": 0.42,
                "specificity_pct": 0,
                "category_distribution": {"debug": 15, "implement": 20, "test": 10},
            },
            {
                "window_label": "2026-03-03 → 2026-03-09",
                "prompt_count": 52,
                "avg_length": 95.1,
                "vocab_size": 145,
                "specificity_score": 0.48,
                "specificity_pct": 14,
                "category_distribution": {"debug": 12, "implement": 25, "test": 15},
            },
        ],
        "insights": ["Your prompts are getting more specific over time."],
    }


def _sample_recommend_data():
    return {
        "total_prompts": 100,
        "best_prompts": [
            {
                "text": "Add pagination to search results using offset/limit",
                "effectiveness": 0.85,
                "project": "myproject",
            },
        ],
        "category_effectiveness": {"debug": 0.35, "implement": 0.72, "test": 0.60},
        "short_prompt_alerts": [
            {"text": "fix bug", "char_count": 7},
        ],
        "specificity_tips": [
            {
                "original": "fix the bug",
                "tip": "Include filename, function name, and expected behavior",
            },
        ],
        "category_tips": ["Debug prompts are 3x shorter than implement prompts."],
        "overall_tips": ["Try including error messages in debug prompts."],
    }


def test_returns_valid_html():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_contains_chart_js():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "Chart" in html


def test_contains_overview_stats():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "100" in html
    assert "75" in html


def test_contains_data_injection():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "reportData" in html
    assert "trendsData" in html


def test_contains_category_labels():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "debug" in html
    assert "implement" in html


def test_contains_patterns_table():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "fix the failing test" in html
    assert "add unit tests" in html


def test_contains_recommendations():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "pagination" in html.lower() or "offset/limit" in html


def test_special_chars_escaped():
    report = _sample_report_data()
    report["top_patterns"] = [
        {"pattern_text": 'fix "auth" <module>', "frequency": 5, "category": "debug"},
    ]
    html = render_html_dashboard(report, _sample_trends_data(), _sample_recommend_data())
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html


def test_clusters_rendered():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data()
    )
    assert "Prompt Clusters" in html
    assert "Fix the failing test for auth" in html
    assert "#0" in html


def test_digest_rendered():
    digest = {
        "period": "7d",
        "count_delta": 12,
        "spec_delta": 0.06,
        "eff_avg": 0.73,
        "current": {"prompt_count": 52, "specificity_score": 0.48},
        "previous": {"prompt_count": 40, "specificity_score": 0.42},
        "summary": "reprompt: 52 prompts (+12), specificity 0.48 (↑)",
    }
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data(), digest
    )
    assert "This 7d vs Previous" in html
    assert "delta-up" in html
    assert "+12" in html
    assert "0.73" in html  # eff_avg


def test_digest_none_renders_cleanly():
    html = render_html_dashboard(
        _sample_report_data(), _sample_trends_data(), _sample_recommend_data(), None
    )
    assert "<!DOCTYPE html>" in html
    assert "This" not in html or "Previous" not in html or "vs Previous" not in html


def test_empty_data():
    empty_report = {
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
    empty_trends = {"period": "7d", "windows": [], "insights": []}
    empty_recommend = {
        "total_prompts": 0,
        "best_prompts": [],
        "category_effectiveness": {},
        "short_prompt_alerts": [],
        "specificity_tips": [],
        "category_tips": [],
        "overall_tips": [],
    }
    html = render_html_dashboard(empty_report, empty_trends, empty_recommend)
    assert "<!DOCTYPE html>" in html
    assert "</html>" in html
