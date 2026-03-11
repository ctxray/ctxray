# Show HN Post

## Title

Show HN: Reprompt – TF-IDF dedup and analytics for your AI coding prompts

## URL

https://github.com/reprompt-dev/reprompt

## First Comment (post within 5 minutes)

Hi HN, I'm Chris. I built this because I noticed I kept asking Claude Code the same things — "fix the failing test," "add unit tests for X," "refactor Y to use Z" — and never learned from the pattern.

**Why I built it:** After months of daily AI coding, I had hundreds of session files with thousands of prompts scattered across them. I wanted to know: which prompts actually work? Am I just repeating myself? How are my prompting habits evolving?

**How it works:** reprompt scans your session files (Claude Code JSONL, OpenClaw JSON) and runs two-layer deduplication: SHA-256 for exact matches, then TF-IDF cosine similarity (threshold 0.85) for semantic near-duplicates. "Fix the auth bug" and "fix the authentication issue" get caught as dupes. It extracts bigram/trigram hot phrases, clusters prompts with K-means, and auto-categorizes patterns (debug/implement/test/review/refactor).

**What's different from grep + wc:** The semantic layer. Exact string matching misses ~22% of duplicates that TF-IDF catches. The trend tracking shows how your prompt specificity evolves over time — a composite score of length, vocabulary breadth, and category entropy across sliding windows.

**What surprised me:**
- 32% of my prompts were near-duplicates
- My debug prompts are 3x shorter than implement prompts (and correlate with longer sessions)
- After a week of tracking, I naturally started writing more specific prompts

Stack: Python 3.10+, scikit-learn, SQLite. ~260 tests, strict mypy. Zero config — `pipx install reprompt-cli && reprompt scan && reprompt report`. MIT licensed.

What metrics would you want to see from your AI coding sessions? Would love to hear what would make prompt analytics actually useful to your workflow.

---

## Tips for Posting

- Post Tuesday 8:00 AM EST (60% higher score vs average day)
- Link to GitHub repo directly (not landing page)
- Be online for 2-4 hours responding to every comment
- Technical depth wins — if someone asks about the dedup algorithm, explain the TF-IDF cosine threshold and n-gram range
- Don't be defensive about criticism
- If someone says "I could do this with grep", acknowledge it and explain what the semantic layer adds (22% more dupes caught)
- If the post doesn't take off, can resubmit for major milestones later (Ruff did 4+ Show HN posts)
