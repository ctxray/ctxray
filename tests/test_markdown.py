"""Tests for Markdown export of prompt library."""
from reprompt.output.markdown import export_library_markdown


def test_export_has_header():
    patterns = [
        {
            "pattern_text": "fix the failing test",
            "frequency": 10,
            "avg_length": 25.0,
            "category": "debug",
            "examples": ["fix the failing test in auth"],
        },
    ]
    md = export_library_markdown(patterns)
    assert "# " in md  # has heading
    assert "reprompt" in md.lower() or "prompt" in md.lower()


def test_export_has_pattern_table():
    patterns = [
        {
            "pattern_text": "fix the failing test",
            "frequency": 10,
            "avg_length": 25.0,
            "category": "debug",
            "examples": ["fix the failing test in auth"],
        },
        {
            "pattern_text": "add unit tests",
            "frequency": 5,
            "avg_length": 20.0,
            "category": "test",
            "examples": ["add unit tests for parser"],
        },
    ]
    md = export_library_markdown(patterns)
    assert "fix the failing test" in md
    assert "add unit tests" in md
    assert "debug" in md
    assert "test" in md


def test_export_groups_by_category():
    patterns = [
        {
            "pattern_text": "fix bug",
            "frequency": 10,
            "category": "debug",
            "avg_length": 10.0,
            "examples": [],
        },
        {
            "pattern_text": "add feature",
            "frequency": 5,
            "category": "implement",
            "avg_length": 15.0,
            "examples": [],
        },
    ]
    md = export_library_markdown(patterns)
    assert "debug" in md.lower()
    assert "implement" in md.lower()


def test_export_empty():
    md = export_library_markdown([])
    assert "No patterns" in md or "empty" in md.lower() or len(md) > 0


def test_export_includes_examples():
    patterns = [
        {
            "pattern_text": "fix the test",
            "frequency": 3,
            "category": "debug",
            "avg_length": 15.0,
            "examples": ["fix the test in auth", "fix the test in payments"],
        },
    ]
    md = export_library_markdown(patterns)
    assert "fix the test in auth" in md
