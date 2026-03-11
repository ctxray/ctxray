# Show HN Post

## Title

Show HN: Reprompt – I analyzed 1,200+ AI coding prompts and found 32% were duplicates

## URL

https://github.com/reprompt-dev/reprompt

## First Comment (post within 5 minutes)

Hi HN, I'm Chris. I built reprompt because I realized I was asking Claude Code the same things over and over — "fix the failing test," "add unit tests for X," "refactor Y to use Z" — without ever learning from the pattern.

reprompt scans your AI coding session files (Claude Code, OpenClaw, soon Codex CLI), deduplicates them using SHA-256 + TF-IDF cosine similarity, and surfaces insights:

**What it does:**
- Two-layer dedup: exact hash + semantic similarity (catches "fix the auth bug" ≈ "fix the authentication issue")
- Extracts high-frequency prompt patterns and auto-categorizes them (debug/implement/test/review/refactor)
- Tracks how your prompting evolves over time (specificity score, vocabulary breadth)
- MCP server so Claude Code/Continue.dev can query your prompt library mid-session

**Technical details:**
- Python, scikit-learn for TF-IDF + K-means, SQLite for storage
- Zero config — `pipx install reprompt-cli && reprompt scan && reprompt report`
- ~260 tests, strict mypy, MIT licensed

**What surprised me:**
- 32% of my prompts were near-duplicates
- My "debug" prompts are 3x shorter than "implement" prompts (and less effective)
- After a week of tracking, I naturally started writing more specific prompts

The insight that changed my workflow: seeing which prompt *patterns* actually led to productive sessions vs. which ones led to 2-hour debugging spirals.

Would love feedback on what metrics you'd find useful. What would make you check your prompt analytics daily?

---

## Tips for Posting

- Post Tuesday 8:00 AM EST
- Be online for 2-4 hours responding to every comment
- Technical depth wins — if someone asks about the dedup algorithm, explain the TF-IDF cosine threshold
- Don't be defensive about criticism
- If someone says "I could do this with grep", acknowledge it and explain what the semantic layer adds
