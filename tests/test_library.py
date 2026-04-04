"""Tests for prompt pattern extraction and categorization."""

from ctxray.core.library import categorize_prompt, extract_patterns


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
    assert categorize_prompt("gibberish xyz text here") == "other"


def test_extract_empty():
    patterns = extract_patterns([], min_frequency=2)
    assert patterns == []


def test_categorize_document():
    assert categorize_prompt("整理一下我们的经验教训") == "document"
    assert categorize_prompt("update the README with new instructions") == "document"
    assert categorize_prompt("记录这次的踩坑总结") == "document"


def test_categorize_run():
    assert categorize_prompt("启动我们的服务然后开始扫描") == "run"
    assert categorize_prompt("start the server and restart the worker") == "run"
    assert categorize_prompt("restart the docker container") == "run"


def test_categorize_query():
    assert categorize_prompt("是否已经保存到github了？") == "query"
    assert categorize_prompt("have we pushed to production?") == "query"


def test_categorize_generate():
    assert categorize_prompt("generate a random list of numbers") == "generate"
    assert categorize_prompt("生成一些随机数据") == "generate"


def test_categorize_plan():
    assert categorize_prompt("how should we design the auth system?") == "plan"
    assert categorize_prompt("如何规划我们的数据库架构") == "plan"


def test_categorize_write_a_function():
    # "write a" should now map to implement (was falling into "other")
    assert categorize_prompt("write a function to find the maximum") == "implement"
    assert categorize_prompt("write the parser for CSV files") == "implement"


def test_categorize_debug_extended():
    assert categorize_prompt("the auth is not working") == "debug"
    assert categorize_prompt("it fails with an exception") == "debug"


def test_categorize_skill_invocation_english():
    """Skill namespace patterns → skill_invocation category."""
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("use the superpowers:brainstorming skill") == "skill_invocation"
    assert categorize_prompt("invoke feature-dev:code-architect") == "skill_invocation"
    assert categorize_prompt("code-simplifier:simplify on this module") == "skill_invocation"
    assert categorize_prompt("claude-md-management:revise-claude-md") == "skill_invocation"
    assert (
        categorize_prompt("claude-code-setup:claude-automation-recommender") == "skill_invocation"
    )


def test_categorize_skill_invocation_chinese():
    """Chinese skill invocations are also categorized correctly."""
    from ctxray.core.library import categorize_prompt

    assert (
        categorize_prompt("请使用 superpowers:executing-plans 执行 docs/plans/foo.md")
        == "skill_invocation"
    )
    assert categorize_prompt("请使用 feature-dev:feature-dev 开始开发") == "skill_invocation"


def test_skill_invocation_does_not_match_short_patterns():
    """Short namespace:value patterns (URLs, config, git commits) are NOT skill_invocation."""
    from ctxray.core.library import categorize_prompt

    # These should fall through to other categories or 'other'
    assert categorize_prompt("fix: resolve the null pointer error") != "skill_invocation"
    assert categorize_prompt("please use Python to build this function") != "skill_invocation"
    assert categorize_prompt("node:packages need updating in the project") != "skill_invocation"
    assert categorize_prompt("user:admin has no permissions set") != "skill_invocation"


# --- New category tests (v0.9 chat AI expansion) ---


def test_categorize_research():
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("Research the latest trends in renewable energy storage") == "research"
    assert categorize_prompt("What are the current findings on intermittent fasting?") == "research"


def test_categorize_creative():
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("Write a short story about a robot who learns to paint") == "creative"
    assert categorize_prompt("Compose a haiku about autumn leaves") == "creative"


def test_categorize_summarize():
    from ctxray.core.library import categorize_prompt

    text = "Summarize this article about climate change in 3 bullet points"
    assert categorize_prompt(text) == "summarize"
    assert categorize_prompt("Give me the key takeaways from this research paper") == "summarize"


def test_categorize_translate():
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("Translate this paragraph into Japanese") == "translate"
    assert categorize_prompt("How do you say good morning in French?") == "translate"


def test_categorize_draft():
    from ctxray.core.library import categorize_prompt

    text = "Draft an email to my manager requesting time off next week"
    assert categorize_prompt(text) == "draft"
    assert categorize_prompt("Write a cover letter for a software engineering position") == "draft"


def test_categorize_analyze():
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("Analyze the pros and cons of remote work policies") == "analyze"
    assert categorize_prompt("Compare these two investment strategies") == "analyze"


def test_categorize_brainstorm():
    from ctxray.core.library import categorize_prompt

    assert categorize_prompt("Brainstorm ideas for a birthday party theme") == "brainstorm"
    assert categorize_prompt("What are some creative ways to reduce food waste?") == "brainstorm"
