"""Tests for prompt pattern extraction and categorization."""
from reprompt.core.library import extract_patterns, categorize_prompt


def test_extract_patterns_groups_similar():
    prompts = [
        "fix the failing test in auth",
        "fix the broken test in payments",
        "fix the failing test in users",
        "deploy to production",
        "deploy to staging",
    ]
    patterns = extract_patterns(prompts, min_frequency=2)
    assert len(patterns) >= 1  # at least one pattern group


def test_extract_patterns_has_fields():
    prompts = ["fix test A", "fix test B", "fix test C"]
    patterns = extract_patterns(prompts, min_frequency=2)
    if patterns:
        p = patterns[0]
        assert "pattern_text" in p
        assert "frequency" in p
        assert "avg_length" in p
        assert "category" in p


def test_categorize_debug():
    assert categorize_prompt("fix the failing test") == "debug"
    assert categorize_prompt("debug the authentication issue") == "debug"


def test_categorize_implement():
    assert categorize_prompt("add a new endpoint for users") == "implement"
    assert categorize_prompt("implement the search feature") == "implement"
    assert categorize_prompt("create a new component") == "implement"


def test_categorize_review():
    assert categorize_prompt("review this code for security issues") == "review"


def test_categorize_test():
    assert categorize_prompt("write unit tests for the auth module") == "test"
    assert categorize_prompt("add tests for the parser") == "test"


def test_categorize_refactor():
    assert categorize_prompt("refactor the database layer") == "refactor"


def test_categorize_explain():
    assert categorize_prompt("explain how the auth system works") == "explain"


def test_categorize_config():
    assert categorize_prompt("configure the CI pipeline") == "config"
    assert categorize_prompt("set up the deployment") == "config"


def test_categorize_unknown():
    assert categorize_prompt("random gibberish text here") == "other"


def test_extract_empty():
    patterns = extract_patterns([], min_frequency=2)
    assert patterns == []
