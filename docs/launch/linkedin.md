# LinkedIn Post

I've been using AI coding tools (Claude Code, Copilot, etc.) daily for months and realized something: I keep asking the same things over and over.

So I built reprompt — an open-source CLI that analyzes your AI coding session history.

What it found:
- 32% of my prompts were near-duplicates
- My debug prompts are 3x shorter than my implement prompts (and less effective)
- After a week of tracking, I naturally started writing more specific prompts

Technical approach: SHA-256 exact dedup + TF-IDF cosine similarity for semantic matching. Python, scikit-learn, SQLite. Everything runs locally.

If you use Claude Code or similar AI coding tools, give it a try:

```
pipx install reprompt-cli
reprompt scan
reprompt report
```

MIT licensed. Feedback welcome.

GitHub: https://github.com/reprompt-dev/reprompt

#OpenSource #AI #DeveloperTools #Python #PromptEngineering
