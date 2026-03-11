# LinkedIn Post

I've been using AI coding tools (Claude Code, Cursor, etc.) daily for months. One question kept nagging me: which of my prompts actually work well, and which ones waste time?

So I built reprompt — an open-source CLI that analyzes your AI coding prompt history.

What I learned from my own data:
→ My debug prompts are 3x shorter than implement prompts — and significantly less effective
→ "Fix the bug" performs measurably worse than naming the file, function, and expected behavior
→ After a week of tracking, I naturally started writing better prompts

The tool extracts prompts from session files, deduplicates them (SHA-256 + TF-IDF cosine similarity), and builds a personal prompt library organized by task type.

New in v0.3: `reprompt recommend` analyzes which prompt patterns correlate with productive sessions. `reprompt demo` lets you try it with built-in sample data — no setup needed.

Supports Claude Code, OpenClaw, and Cursor IDE. Everything runs locally. Python, scikit-learn, SQLite.

Try it:
```
pipx install reprompt-cli
reprompt demo
```

MIT licensed. 284 tests, strict mypy.

GitHub: https://github.com/reprompt-dev/reprompt

What would you want to know about your AI coding habits?

#OpenSource #AI #DeveloperTools #Python #PromptEngineering #MachineLearning
