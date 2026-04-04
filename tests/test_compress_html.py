from ctxray.output.html_report import render_html_dashboard


def test_html_dashboard_shows_compressibility():
    report_data = {
        "overview": {
            "total_prompts": 100,
            "unique_prompts": 80,
            "sessions_scanned": 10,
            "sources": ["claude_code"],
            "date_range": ("2026-01-01", "2026-03-22"),
            "avg_compressibility": 0.23,
        },
        "top_patterns": [],
        "projects": {},
        "categories": {},
        "top_terms": [],
        "clusters": [],
        "privacy": {"tools": [], "cloud_count": 0, "local_count": 0, "training_risk_count": 0},
    }
    html = render_html_dashboard(report_data, {}, {})
    assert "compressib" in html.lower()
    assert "23%" in html


def test_html_dashboard_no_compressibility_when_zero():
    report_data = {
        "overview": {
            "total_prompts": 100,
            "unique_prompts": 80,
            "sessions_scanned": 10,
            "sources": ["claude_code"],
            "date_range": ("2026-01-01", "2026-03-22"),
            "avg_compressibility": 0.0,
        },
        "top_patterns": [],
        "projects": {},
        "categories": {},
        "top_terms": [],
        "clusters": [],
        "privacy": {"tools": [], "cloud_count": 0, "local_count": 0, "training_risk_count": 0},
    }
    html = render_html_dashboard(report_data, {}, {})
    # Should still render without error, but no compressibility card
    assert isinstance(html, str)
    assert 'class="compress-fill"' not in html
