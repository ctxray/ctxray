"""Prompt pattern extraction and categorization."""

from __future__ import annotations

import re
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Keyword-based categorization rules (order matters -- first match wins)
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    # --- Non-coding categories (v0.9: Chat AI support) ---
    (
        "creative",
        [
            "write a story",
            "write a poem",
            "short story",
            "compose",
            "creative writing",
            "fiction",
            "haiku",
            "limerick",
            "song lyrics",
            "screenplay",
            "dialogue",
            "创作",
            "写诗",
            "写故事",
            "小说",
        ],
    ),
    (
        "summarize",
        [
            "summarize this",
            "summary of",
            "key takeaways",
            "main points",
            "tldr",
            "tl;dr",
            "bullet points",
            "brief overview",
            "总结这",
            "概括",
            "要点",
        ],
    ),
    (
        "research",
        [
            "research",
            "investigate",
            "look up",
            "look into",
            "find out",
            "what are the latest",
            "current findings",
            "state of the art",
            "literature",
            "调研",
            "研究",
            "查找",
        ],
    ),
    (
        "translate",
        [
            "translate",
            "translation",
            "how do you say",
            "in french",
            "in spanish",
            "in japanese",
            "in chinese",
            "in german",
            "in korean",
            "翻译",
            "翻成",
        ],
    ),
    (
        "draft",
        [
            "draft a",
            "draft an",
            "write an email",
            "write a letter",
            "write a message",
            "cover letter",
            "write a report",
            "write a proposal",
            "起草",
            "写邮件",
            "写信",
        ],
    ),
    (
        "analyze",
        [
            "analyze",
            "analyse",
            "analysis of",
            "compare these",
            "pros and cons",
            "evaluate",
            "assess",
            "critique",
            "分析",
            "对比",
            "评估",
        ],
    ),
    (
        "brainstorm",
        [
            "brainstorm",
            "ideas for",
            "suggest ways",
            "creative ways",
            "what are some",
            "help me think of",
            "come up with",
            "头脑风暴",
            "想法",
            "点子",
        ],
    ),
    ("review", ["review", "audit", "inspect", "examine", "审查", "审阅"]),
    (
        "debug",
        [
            "fix",
            "debug",
            "error",
            "bug",
            "failing",
            "broken",
            "crash",
            "issue",
            "not working",
            "doesn't work",
            "won't work",
            "fail",
            "exception",
            "traceback",
            "修复",
            "报错",
            "错误",
            "崩溃",
            "失败",
        ],
    ),
    ("test", ["test", "spec", "coverage", "assert", "mock", "测试", "单元测试"]),
    (
        "implement",
        [
            "add",
            "implement",
            "create",
            "build",
            "feature",
            "endpoint",
            "write a",
            "write the",
            "write code",
            "scaffold",
            "实现",
            "新增",
            "添加",
            "构建",
        ],
    ),
    (
        "refactor",
        [
            "refactor",
            "restructure",
            "reorganize",
            "clean",
            "simplify",
            "extract",
            "重构",
            "整理代码",
            "优化代码",
        ],
    ),
    (
        "explain",
        [
            "explain",
            "how does",
            "what is",
            "describe",
            "understand",
            "why",
            "walk me through",
            "what does",
            "how do i",
            "解释",
            "为什么",
            "怎么",
            "是什么",
        ],
    ),
    (
        "config",
        [
            "config",
            "configure",
            "setup",
            "set up",
            "install",
            "deploy",
            "ci",
            "cd",
            "environment",
            "dockerfile",
            "kubernetes",
            "helm",
            "nginx",
            "配置",
            "部署",
            "安装",
            "环境",
        ],
    ),
    (
        "document",
        [
            "document",
            "readme",
            "docs",
            "write up",
            "record",
            "note down",
            "summarize",
            "changelog",
            "wiki",
            "comment",
            "docstring",
            "文档",
            "整理",
            "记录",
            "总结",
            "笔记",
        ],
    ),
    (
        "run",
        [
            "run the",
            "start the",
            "launch",
            "restart",
            "stop the",
            "execute the",
            "kick off",
            "trigger",
            "spin up",
            "bring up",
            "启动",
            "运行",
            "执行",
            "开始扫描",
            "重启",
        ],
    ),
    (
        "generate",
        [
            "generate",
            "random",
            "sample data",
            "mock data",
            "dummy data",
            "seed",
            "fixture",
            "fabricate",
            "fake data",
            "生成",
            "随机",
        ],
    ),
    (
        "query",
        [
            "is our",
            "are we",
            "did we",
            "does it",
            "has the",
            "is it",
            "what's the status",
            "have we",
            "is this",
            "are there",
            "是否",
            "有没有",
            "状态",
            "保存到",
            "已经",
        ],
    ),
    (
        "plan",
        [
            "plan",
            "design",
            "architect",
            "strategy",
            "approach",
            "roadmap",
            "how should we",
            "best way to",
            "how to approach",
            "outline",
            "规划",
            "设计",
            "方案",
            "如何",
            "怎么做",
        ],
    ),
]


# Detects skill/workflow invocations: namespace:skill-name pattern
# Matches superpowers:brainstorming, feature-dev:code-architect, etc.
# Requires both sides to be lowercase-hyphenated identifiers (no http://, no "error: msg")
_SKILL_NAMESPACE_RE = re.compile(r"[a-z][a-z0-9-]{8,}:[a-z][a-z0-9-]{2,}")


def categorize_prompt(text: str) -> str:
    """Categorize a prompt using keyword matching. Returns category string."""
    # Skill invocations detected first — most specific signal
    if _SKILL_NAMESPACE_RE.search(text):
        return "skill_invocation"
    lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in lower:
                return category
    return "other"


def extract_patterns(
    prompts: list[str],
    min_frequency: int = 3,
    similarity_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Extract high-frequency prompt patterns from a list of prompt texts.

    Groups similar prompts using TF-IDF cosine similarity, picks representative text,
    counts frequency, computes avg length, auto-categorizes.

    Returns list of pattern dicts:
    [{"pattern_text": str, "frequency": int, "avg_length": float,
      "category": str, "examples": list[str]}]
    """
    if not prompts:
        return []

    # Build TF-IDF matrix
    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(prompts)

    # Compute pairwise similarities
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Greedy clustering: assign each prompt to first sufficiently-similar group
    used: set[int] = set()
    groups: list[list[int]] = []

    for i in range(len(prompts)):
        if i in used:
            continue
        group = [i]
        used.add(i)
        for j in range(i + 1, len(prompts)):
            if j in used:
                continue
            if sim_matrix[i][j] >= similarity_threshold:
                group.append(j)
                used.add(j)
        groups.append(group)

    # Filter by min_frequency and build pattern dicts
    patterns: list[dict[str, Any]] = []
    for group in groups:
        if len(group) < min_frequency:
            continue
        group_texts = [prompts[i] for i in group]
        representative = group_texts[0]  # first occurrence as representative
        patterns.append(
            {
                "pattern_text": representative,
                "frequency": len(group),
                "avg_length": sum(len(t) for t in group_texts) / len(group_texts),
                "category": categorize_prompt(representative),
                "examples": group_texts[:5],  # keep up to 5 examples
            }
        )

    patterns.sort(key=lambda x: x.get("frequency", 0), reverse=True)
    return patterns
