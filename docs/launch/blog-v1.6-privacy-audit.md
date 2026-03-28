# Blog Post: I Audited What I Sent to AI Coding Tools

## Target Platforms
- dev.to (primary — SEO value + developer audience)
- Medium (secondary)
- Personal blog / getreprompt.dev/blog

## SEO Keywords
ai privacy, ai coding tools security, claude code privacy, cursor privacy, api key leak ai, prompt analysis

---

## Title

I Audited 1,000+ Prompts I Sent to AI Coding Tools. Here's What I Found.

## Subtitle

API keys, JWT tokens, internal file paths, and error loops — all hiding in my conversation history.

---

## Body

I've been using AI coding tools daily for about a year. Claude Code, Cursor, Codex CLI, sometimes Aider. By rough estimate, I've sent over a thousand prompts to various AI services.

Last month I built a tool to answer a simple question: **what exactly did I send?**

The answer was uncomfortable.

### Finding 1: Leaked Credentials

Running `reprompt privacy --deep` on my prompt history surfaced:

- **3 API keys** (OpenAI, GitHub, one internal service)
- **1 JWT token** (from a debugging session)
- **12 email addresses** (from log outputs I pasted)
- **47 internal file paths** (including home directory paths)

None of these were pasted intentionally. They were in error messages, stack traces, and log outputs that I copy-pasted when asking the AI for help debugging. The typical pattern:

```
"Fix this error: AuthenticationError: Invalid API key 'sk-proj-...' for model gpt-4"
```

That prompt just sent my API key to whatever service processes it.

### Finding 2: Agent Error Loops

`reprompt agent` analyzes Claude Code and Codex CLI sessions for workflow efficiency. It fingerprints each tool call (tool name + target file + error flag) and detects when the agent gets stuck in a loop.

**My error loop rate: 35%.**

That means in over a third of my agent sessions, the AI got stuck retrying the same failing approach three or more times. The most common pattern: `Bash(test.py):error -> Edit(auth.py) -> Bash(test.py):error` — edit a file, run the test, fail, edit, test, fail.

The agent burned tokens and time on approaches that clearly weren't working. Knowing this changed how I intervene in agent sessions.

### Finding 3: Most Conversation Turns Are Filler

`reprompt distill` scores every conversation turn using 6 signals (position, length, tool trigger, error recovery, topic shift, vocabulary uniqueness).

Result: **50-70% of my turns carry near-zero information.**

"ok try that", "continue", "looks good", "hmm interesting" — these are the prompting equivalent of "um" and "uh." They don't guide the AI in any useful direction. The actually productive turns — the ones that specify files, constraints, and context — typically make up only 15-20 turns out of a 100-turn session.

### The Privacy Angle

The EU AI Act took effect in August 2025. Organizations are increasingly required to understand what data flows to AI services. But most developers have no visibility into what they've actually sent.

`reprompt privacy` shows a per-tool breakdown: which adapter (Claude Code, Cursor, ChatGPT) received which types of content. `reprompt privacy --deep` goes further and scans for 12 categories of sensitive content: API keys (OpenAI, AWS, GitHub, Anthropic, Stripe), JWT tokens, emails, IP addresses, password assignments, environment secrets, and home directory paths.

All detection is regex-based. Zero network calls. Your prompts never leave your machine.

### How It Works

reprompt reads session files that AI tools already store locally:

| Tool | Format | Location |
|------|--------|----------|
| Claude Code | JSONL | `~/.claude/projects/` |
| Codex CLI | JSONL | `~/.codex/sessions/` |
| Cursor | SQLite | `~/.cursor/` |
| Aider | Markdown | `.aider.chat.history.md` |
| Gemini CLI | JSON | `~/.gemini/tmp/` |

No instrumentation required. No code changes. Just:

```bash
pip install reprompt-cli
reprompt scan
reprompt privacy --deep
```

The scoring engine is calibrated against 4 NLP research papers. The agent analyzer builds tool call fingerprints and detects repetition patterns. The distiller uses TF-IDF cosine similarity for topic shift detection. Everything runs in <50ms for a typical session.

### What I Changed

After two months of running reprompt:

1. I stopped copy-pasting full error messages with credentials. Instead, I redact API keys before pasting.
2. I intervene earlier in agent sessions when I see the same test failing twice.
3. My debug prompts went from averaging 31/100 to 52/100 — not from trying harder, just from seeing the score.

### Try It

```bash
pip install reprompt-cli
reprompt scan                     # discover sessions from installed AI tools
reprompt                          # see your dashboard
reprompt privacy --deep           # scan for leaked credentials
reprompt agent --last 5           # analyze recent agent sessions
reprompt distill --last 3         # extract important turns
```

1,494 tests. MIT license. Zero network calls. Supports 9 AI tools.

GitHub: [reprompt-dev/reprompt](https://github.com/reprompt-dev/reprompt)

---

*What would your numbers look like?*
