# Twitter/X Thread

## Tweet 1 (Hook)

I analyzed 1,200+ AI coding prompts and found 32% were near-duplicates.

So I built reprompt — an open-source CLI that extracts, deduplicates, and analyzes your prompt history from Claude Code, OpenClaw, and more.

Here's what I learned (thread):

github.com/reprompt-dev/reprompt

## Tweet 2 (The Problem)

Every developer using AI coding tools generates hundreds of prompts per week.

They're scattered across session files, never reviewed, never reused.

You're probably asking the same things over and over without realizing it.

## Tweet 3 (How It Works)

reprompt uses two-layer dedup:

1. SHA-256 for exact matches
2. TF-IDF cosine similarity for semantic near-duplicates

"fix the auth bug" ≈ "fix the authentication issue" → caught.

Zero config:
```
pipx install reprompt-cli
reprompt scan
reprompt report
```

## Tweet 4 (Surprising Findings)

What surprised me:

- 32% of my prompts were near-duplicates
- My "debug" prompts are 3x shorter than "implement" prompts
- Shorter debug prompts correlate with longer debugging sessions
- After a week of tracking, I naturally started writing more specific prompts

## Tweet 5 (Features)

What you get:

- Hot phrases (TF-IDF n-grams, not just single words)
- K-means prompt clustering
- Auto-categorized prompt library (debug/implement/test/refactor)
- Trend tracking with specificity scoring
- Session effectiveness scoring
- MCP server for Claude Code integration

## Tweet 6 (Local First)

Everything runs locally. No data leaves your machine.

Default: TF-IDF (scikit-learn, zero config)
Optional: Ollama embeddings, sentence-transformers, or OpenAI

Your prompts are yours.

## Tweet 7 (CTA)

MIT licensed, ~260 tests, strict mypy, Python 3.10+.

Currently supports Claude Code + OpenClaw.
Codex CLI, Aider, Gemini CLI planned.

Try it:
```
pipx install reprompt-cli
```

What metrics would make you check your prompt analytics daily?

github.com/reprompt-dev/reprompt
