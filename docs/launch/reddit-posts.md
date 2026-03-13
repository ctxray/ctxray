# Reddit Posts

## r/ClaudeAI (POSTED — Day 0)

**Title:** I built a tool to analyze my Claude Code prompt history — turns out 32% were near-duplicates

**Status:** Posted. Body rewritten in conversational style. Do not re-edit existing post. Post follow-up as new thread when reaching 0.8.0 milestone.

---

## r/programming (Day 1-2) — v0.7.2 更新版

**Angle:** r/programming 偏好技术洞察和观点。标题像技术博客标题，body 像跟同事聊技术。新版本把 Prompt Science Engine 融入技术叙事，不只讲 dedup。

**Title:** I applied 4 NLP papers to score my AI coding prompts — and rewrote the scoring twice when my intuition was wrong

### Body

I've been using AI coding assistants daily for 6 months. My working assumption was always that better prompts = more specific prompts. Seemed obvious. Turned out to be partially right, but not in the way I expected.

I built a tool called reprompt that scans all my AI session files and scores each prompt 0-100 using NLP features derived from published research. Here's what I learned.

The dedup part came first. I had thousands of prompts across hundreds of session files and wanted to find patterns. Exact string matching was useless — "fix the auth bug" and "fix the authentication issue" are obviously the same intent but share almost no tokens. I tried sentence-transformers (all-MiniLM-L6-v2) but for prompts averaging 15 tokens, the quality difference over TF-IDF cosine similarity was marginal and the model download wasn't worth it. TF-IDF with bigram/trigram extraction at threshold 0.85 turned out to be the right tradeoff: fast, no dependencies, catches the semantic near-dupes that matter. Below 0.8 you get false positives ("add auth" matching "add tests"). Above 0.9 you miss obvious dupes.

After dedup I had ~800 unique prompts. I wanted to know which ones were good. That's where the research came in.

Four papers I used: Google 2512.14982 studied repetition patterns in prompts and their effect on output quality. Stanford 2307.03172 documented position bias — models weight the beginning and end of a prompt more heavily, so frontloading context matters. SPELL EMNLP 2023 used perplexity as a proxy for prompt informativeness (higher perplexity = more diverse vocabulary = more informative). The Prompt Report 2406.06608 gave me a task taxonomy (debug, implement, test, refactor, explain, etc.) to normalize across categories.

From these I built a scoring function with four components: specificity (file paths, line numbers, function names, error messages), position (how much relevant context is in the first 30% of the prompt), repetition penalty, and a vocabulary entropy proxy for informativeness. The weights were research-informed but calibrated empirically on my own data.

The scores were uncomfortable. Here's a concrete example:

    reprompt score "fix the bug"
    → 23/100
      Specificity: 8  — no file, no function, no error message
      Position: 15    — context-free opening
      Repetition: 0   — none detected
      Perplexity: 0   — minimal vocabulary

    reprompt score "fix the null pointer in auth.service.ts:47 — token is null when session expires without refresh, expected AuthException not 200"
    → 89/100
      Specificity: 42 — file path, line number, error type, expected behavior
      Position: 22    — context-dense opening
      Repetition: 0   — none
      Perplexity: 25  — rich vocabulary

I rewrote the scoring logic twice. First version over-weighted length (longer prompts scored higher regardless of content). Second version fixed that but under-weighted position — I was treating the prompt as a bag of words, which is wrong. The final version uses a sliding window to evaluate where in the prompt specific signals appear.

The `reprompt compare "a" "b"` command shows feature breakdowns side-by-side. `reprompt insights` compares your personal average against research benchmarks per category — it told me my debug prompts averaged 38/100 while my implement prompts averaged 61/100. Knowing that made me change how I prompt for debugging specifically.

`reprompt digest` gives a weekly summary comparing this week vs last week: average score, specificity trend, category distribution with direction arrows. It runs as a hook at the end of every Claude Code session if you want.

Everything is local — no cloud, no LLM. The scoring is deterministic NLP. Pluggable embedding backend (TF-IDF default, Ollama optional).

6 tools supported: Claude Code, Cursor, Aider, Gemini CLI, Cline, OpenClaw. 493 tests. MIT.

https://github.com/reprompt-dev/reprompt

Curious if others have thought about what makes a coding prompt measurably good. My intuition matched the research maybe 70% of the time — position effects surprised me.

---

### 作者评论（post 后几小时发）

Author here. One thing the research angle revealed that my intuition didn't: position matters more than I expected.

I used to put context at the end ("...in the auth module, by the way the token handling is in auth.service.ts:47"). Stanford's position bias paper suggests this is worse than frontloading it: "In auth.service.ts:47, fix the null pointer when the token is missing..." The model weights the beginning and end of the prompt more heavily, so burying the specific details in the middle is a structural mistake.

`reprompt compare` makes this visible. You can paste two versions of the same prompt and see the position score differ even when the content is identical.

The other finding I didn't expect: I was using AI workflow invocations (internal automation patterns) for about 8% of my sessions. Those aren't prompts at all — they're workflow triggers. The latest version classifies these as a separate `skill_invocation` category so they don't pollute the scoring average. Small change, big improvement to signal quality.

---

## r/LocalLLaMA (Day 3-5) — v0.7.2 更新版

**Angle:** 隐私第一、全本地、Ollama 集成具体配置、无商业意图、诚实说明局限性。新增：scoring 也是 100% 本地 NLP，零 LLM 依赖。

**Title:** I wanted to score my AI coding prompts without sending them anywhere — built a local scoring tool using NLP research papers, Ollama optional

### Body

Quick context: I use AI coding tools daily — Claude Code, Cursor, Aider, Gemini CLI. After 6 months I had thousands of prompts in session files and wanted to know which ones actually worked well. Every analytics tool I found either required an account or wanted to send my data somewhere.

My prompts contain file paths, internal function names, error messages from production systems. That's essentially a map of my codebase. Not sending that to an API to get scored.

So I built reprompt. It runs entirely on your machine. Here's the privacy picture:

The default backend is TF-IDF (scikit-learn). No model downloads, no network calls, no GPU. It handles deduplication and clustering fine for short text. For prompts averaging 15 tokens, n-gram overlap captures enough semantic similarity that you don't need embeddings.

If you want better embeddings and you're already running Ollama:

    # ~/.config/reprompt/config.toml
    [embedding]
    backend = "ollama"
    model = "nomic-embed-text"

That's the entire config. It hits your local Ollama at localhost:11434 — nothing leaves the machine.

The scoring part (`reprompt score`, `reprompt compare`, `reprompt insights`) is 100% local NLP regardless of which embedding backend you choose. No LLM involved. It's based on features from 4 published papers: specificity signals (file paths, line numbers, error messages), position bias, repetition patterns, perplexity proxy. The score is deterministic — same input, same output, every time.

Worth noting: I rewrote the scoring logic twice. First version over-weighted length. Second version ignored position — treating the prompt as a bag of words. The final   version uses a sliding window to evaluate where signals appear in the prompt. I want to be honest about what the score is and isn't. It's a proxy for quality based on observable NLP features correlated with good prompts in research. It will penalize "fix the bug" (23/100) and reward "fix the NPE in auth.service.ts:47 when token expires mid-session" (87/100). Whether your specific AI tool responds better to specific prompts is something you verify empirically — the score is a starting point, not ground truth.

What I actually use daily:

`reprompt digest --quiet` runs as a hook at the end of every Claude Code session. One line: "↑ specificity 47→62 this week, 156 prompts (+12%), more debug less implement." It takes 0.2 seconds.

`reprompt library` has become a personal cookbook — high-frequency patterns from my actual sessions, organized by task type. I reuse prompts from it instead of writing from scratch.

`reprompt insights` tells me which category of prompts is dragging my average down. Mine is debug — average 38/100 because I default to "fix the bug" when I'm rushed.

Supports 6 tools auto-detected: Claude Code, Cursor IDE, Aider, Gemini CLI, Cline, OpenClaw. Everything stays in a local SQLite file you can query directly. No lock-in.

    pipx install reprompt-cli
    reprompt demo       # built-in sample data
    reprompt scan       # real sessions

M2 Mac: ~1,200 prompts process in under 2 seconds (TF-IDF). Individual scoring is instant. Ollama embedding adds ~10 seconds for the batch step depending on your hardware.

MIT, personal project, no company, no paid tier, no plans for one. 493 tests.

https://github.com/reprompt-dev/reprompt

Anyone running local analytics on their own coding sessions? Curious anyone running nomic-embed-text or mxbai-embed-large for short-text clustering? Curious if there's a meaningful quality difference over TF-IDF at this token count range(10-30 tokens).

---

### 作者评论

Author here. Built this on an M2 Mac. Honest performance notes:

TF-IDF catches most coding prompt duplicates because the vocabulary is constrained. "Fix the auth bug" and "fix the authentication issue" have enough token overlap that you don't need semantic embeddings. For clustering longer, more nuanced prompts, Ollama with nomic-embed-text noticeably improves results.

The scoring is the part I use most. After I saw my debug prompts averaging 38/100 I started deliberately adding file paths and error messages even when I thought I knew where the problem was. Sessions got shorter. Could be correlation, could be causation — hard to isolate. But the pattern is consistent over 3 weeks.

Storage is plain SQLite at `~/.local/share/reprompt/prompts.db`. You can run any query you want against it. I've been analyzing my own data with DuckDB for some deeper cuts that the CLI doesn't expose yet.
