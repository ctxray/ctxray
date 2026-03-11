# Reddit Posts

## r/ClaudeAI (POSTED — Day 0)

**Title:** I built a tool to analyze my Claude Code prompt history — turns out 32% were near-duplicates

**Status:** Posted. Editing body + author comment with conversational style.

### Body（复制粘贴到 Reddit 编辑框）

I've been using Claude Code daily for months and at some point I got curious — am I actually getting better at prompting, or just repeating myself?

So I built a tool to find out. It scans your Claude Code session files and figures out which prompts you keep rewriting in slightly different ways. Turns out... a lot of them.

The thing that surprised me most: my debug prompts ("fix the bug", "why is this failing") are way shorter than my implementation prompts — and they lead to longer, messier sessions. Once I saw that pattern, I started being more specific and it actually helped.

You can try it without your own data — \`reprompt demo\` generates sample sessions so you can see the analysis:

    pipx install reprompt-cli
    reprompt demo

Works with Claude Code, OpenClaw, and Cursor. Everything stays local.

GitHub: https://github.com/reprompt-dev/reprompt

Anyone else noticed patterns in how they prompt? Curious what your most repeated prompt is.

---

### 作者评论（复制粘贴替换现有评论）

Author here. The weirdest finding was that I kept rewriting the same prompts in slightly different ways without realizing it. "Fix the auth bug" one day, "fix the authentication issue" the next — basically the same thing.

After tracking for a week I started keeping a note of prompts that worked well and just reusing them. Sounds obvious in hindsight but you don't notice the pattern until you see the data.

If you try it: \`reprompt demo\` works without any real sessions, or \`reprompt scan\` if you want to analyze your actual Claude Code history.

> **注意：** Reddit 代码块用 4 个空格缩进（不是三个反引号）。上面 pipx 那两行已用正确格式。复制时 backtick 会正常显示。

---

## r/programming (Day 1-2)

**Angle:** r/programming 偏好技术洞察和观点，不是工具广告。标题要像技术博客标题，body 像跟同事聊技术。

**Title:** Why TF-IDF still beats transformers for deduplicating short text — lessons from analyzing 1,200 AI coding prompts

### Body（复制粘贴到 Reddit）

I've been using AI coding assistants daily and ended up with thousands of prompts across hundreds of session files. I wanted to deduplicate them, so I tried the obvious approaches and learned a few things.

First attempt: SHA-256 hashing. Fast, but only catches exact copies. "Fix the auth bug" and "fix the authentication issue" are obviously the same intent, but hash dedup misses them completely.

Second attempt: sentence-transformers (all-MiniLM-L6-v2). Works great... but requires a model download, takes 2+ seconds to embed a batch, and is overkill for prompts that average 15 tokens.

What actually worked: TF-IDF with bigram/trigram extraction and cosine similarity at threshold 0.85. For short text, the term overlap between "fix the auth bug" and "fix the authentication issue" is already high enough that TF-IDF catches it without needing semantic understanding. Below 0.8 you get false positives ("add auth" matching "add tests"). Above 0.9 you miss obvious dupes.

The counterintuitive part: TF-IDF's weakness (no semantic understanding) is actually fine here because coding prompts share a constrained vocabulary. "Refactor the database connection pool" and "refactor the db connection pooling" have enough n-gram overlap that you don't need embeddings to match them.

I packaged this into a CLI called reprompt. The dedup is one piece — it also does K-means clustering to group prompts into themes, and tracks how prompt specificity evolves over time (composite of length, vocabulary breadth, category entropy across sliding windows).

    pipx install reprompt-cli
    reprompt demo

The \`demo\` command generates sample data so you can see the analysis without your own sessions. Or point it at your Claude Code / Cursor / OpenClaw sessions with \`reprompt scan\`.

Curious if anyone's benchmarked other similarity metrics for short text dedup. Jaccard on token sets was my third attempt — faster than TF-IDF but worse precision on prompts with shared stop-heavy phrases.

https://github.com/reprompt-dev/reprompt

---

### 作者评论

Author here. One thing I didn't expect: the most useful output isn't the dedup stats, it's seeing which prompt *patterns* correlate with productive sessions.

My debug prompts ("fix the bug", "why is this failing") average 8 tokens. My implementation prompts ("add pagination to the search results using offset/limit with a default page size of 20") average 25 tokens. The short ones correlate with longer, messier sessions. Makes sense in retrospect — vague input, vague output.

The \`recommend\` command surfaces this. It's basically: "hey, your debug prompts are 3x shorter than your implement prompts and your debug sessions are less effective. Try including the filename, function, and expected behavior."

---

## r/LocalLLaMA (Day 3-5)

**Angle:** r/LocalLLaMA 关心的是：隐私、硬件参数、Ollama 具体配置、诚实结果、反商业。这个社区对"伪装成个人项目的商业工具"很敏感，所以要强调 MIT + 个人项目 + 没有付费版。

**Title:** I wanted to analyze my AI coding prompts without sending them anywhere — built a local-first CLI, default is TF-IDF (no model needed), optional Ollama embeddings

### Body（复制粘贴到 Reddit）

Quick context: I use AI coding tools daily (Claude Code, Cursor). After a few months I had hundreds of session files with thousands of prompts scattered across them. I wanted to understand my patterns — which prompts I keep repeating, which ones actually work well — but every analytics tool I found wanted to upload data somewhere.

So I built reprompt. It's a CLI that runs entirely on your machine. No cloud, no telemetry, no account needed.

Why I care about local: my prompts contain file paths, function names, error messages, internal API endpoints. That's basically a map of my codebase. Not sending that anywhere.

The default embedding backend is TF-IDF (scikit-learn). Zero config, no model downloads, no GPU. For short text like coding prompts (~15 tokens average) it works surprisingly well for dedup and clustering.

If you want better embeddings and you're already running Ollama:

    # ~/.config/reprompt/config.toml
    [embedding]
    backend = "ollama"
    model = "nomic-embed-text"

That's it. It talks to your local Ollama at localhost:11434. Also supports sentence-transformers if you prefer that.

What it actually does once your prompts are indexed:

- Finds prompts you keep rewriting in different words (SHA-256 exact + cosine similarity)
- Groups similar prompts into clusters (K-means)
- Builds a personal prompt library sorted by task type (debug/implement/test/refactor)
- Tracks if your prompts are getting more specific over time
- \`reprompt recommend\` tells you which patterns correlate with good sessions

    pipx install reprompt-cli
    reprompt demo       # built-in sample data, see the analysis immediately
    reprompt scan       # point at your real sessions

Tested on M2 Mac. TF-IDF backend processes ~1200 prompts in under 2 seconds. Ollama backend depends on your setup but adds maybe 10 seconds for the embedding step.

MIT licensed, personal project, no company behind it, no paid tier, no plans for one. 284 tests.

https://github.com/reprompt-dev/reprompt

Anyone running local analytics on their own data? Curious what embedding models you've found work best for short text.

---

### 作者评论

Author here. Built this on an M2 MacBook. Honest results:

The TF-IDF backend catches most duplicates for coding prompts because the vocabulary is constrained. "Fix the auth bug" and "fix the authentication issue" have enough token overlap that you don't need semantic embeddings. For longer, more nuanced prompts, Ollama with nomic-embed-text does noticeably better at clustering.

The feature I use most is \`reprompt library\` — after a few weeks of scanning it builds a personal collection of prompts organized by what you were doing (debugging, implementing, testing). It's like a prompt cookbook built from what you actually typed, not from someone's blog post. I keep reusing prompts from it instead of writing new ones from scratch.

Storage is plain SQLite. You can query it directly if you want. No lock-in.
