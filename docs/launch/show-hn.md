# Show HN Post

## 调研发现（2026-03）

**分析了 20+ 高赞 Show HN 帖子，总结写作模式：**

成功帖子共同特征：
- 标题格式固定："Show HN: Name – one-line description"
- Post text 开头 "Hey HN" / "Hi HN" + 自我介绍
- 第一段是个人动机："I built X because I was tired of Y" / "For years I relied on Z but..."
- 用段落叙事，不用 bold headers 或 bullet-point 功能列表
- 技术深度比 Reddit 高，但不学术 — 像跟同事解释技术方案
- 没有 emoji，没有 bold 标题
- 作者第一条评论是实时更新或补充细节，不是重复帖子内容

高赞参考：
- Whispering（591↑）— "I really like dictation. For years, I relied on tools that were almost good..."
- Plandex（304↑）— "I built Plandex because I was tired of copying and pasting code..."
- Tower defense（319↑）— "I'm a software developer with 20+ years but never programmed any games..."

失败模式：
- 标题太长或像广告语
- Post text 像产品文档（feature list + bold headers）
- 作者不回复评论

---

## Title（v0.7.2 更新版）

Show HN: Reprompt – I scored my AI coding prompts using 4 NLP papers; most scored under 30

---

## URL

https://github.com/reprompt-dev/reprompt

---

## Post Text（Show HN 帖子的 body 就是第一条评论）

Hey HN, I'm Chris. After 6 months of daily AI coding I had a suspicion: some of my prompts consistently got better results, but I couldn't tell why or which ones.

The obvious answer was "just be clearer." But I wanted to measure it. Turns out there are 4 published NLP papers on what makes a prompt effective: specificity signals (Google 2512.14982), position bias effects (Stanford 2307.03172), perplexity as an informativeness proxy (SPELL EMNLP 2023), and a task taxonomy (Prompt Report 2406.06608). I built `reprompt score` to apply these to my own session history.

The scores were uncomfortable. A year of "fix the bug", "it's not working", "add tests for this" — most scored 15-30 out of 100. The same intent expressed specifically: "fix the NPE in auth.service.ts:47 — token is null when session expires without refresh, should throw AuthException not return 200" scored 87. I'd been writing the vague version for months.

reprompt does two things:

First, it extracts all your prompts from AI coding sessions and deduplicates them. Supports Claude Code, Cursor, Aider, Gemini CLI, Cline, and OpenClaw — auto-detected, no config. Two-layer dedup: SHA-256 for exact copies, then TF-IDF cosine similarity for near-dupes ("fix the auth bug" ≈ "fix the authentication issue"). I wrote about the TF-IDF choice earlier: for 15-token prompts, n-gram overlap is enough and you skip the model download. The threshold of 0.85 was empirical — below 0.8 you get false positives, above 0.9 you miss obvious dupes.

Second, `reprompt score "prompt"` runs the NLP analysis. `reprompt compare "a" "b"` shows a side-by-side feature breakdown. `reprompt insights` compares your personal distribution against research-optimal benchmarks and tells you which category of prompts (debug, implement, etc.) is pulling your average down. `reprompt digest` gives a weekly summary: did your specificity score go up or down compared to last week?

Everything runs locally. No cloud calls, no LLM — the scoring is deterministic NLP (regex + sklearn). The only optional LLM integration is Ollama for semantic embeddings instead of TF-IDF, enabled with two lines of config.

    pipx install reprompt-cli
    reprompt scan && reprompt insights

Or `reprompt demo` if you don't want to point it at real sessions yet. The project is 3 weeks old, 493 tests, strict mypy, MIT.

One finding I wasn't expecting: I discovered I use AI workflow invocations (internal automation patterns) for 8% of my sessions. That's not a bad prompt — it's a workflow trigger. The latest version classifies these as their own category so they don't pollute the analysis. Small thing, but it cleaned up the pattern library noticeably.

What would you want to know about your AI coding habits if the data were in front of you?

---

## 作者后续评论（准备好，有人问时贴）

### 如果有人问 "why not just use an LLM to score prompts"

Fair question — that's the obvious approach. Two reasons I didn't:

First, deterministic scoring matters for trend tracking. If I score this week's prompts against last week's, I want the metric to be stable, not dependent on model version or temperature. `reprompt digest` compares windows and arrows tell you direction — that only works if the score function is consistent.

Second, privacy. My prompts contain file paths, function names, internal error messages. I'm not sending those to an API to score them. The NLP approach runs entirely locally with no model download (sklearn only).

The tradeoff is that the score is a proxy, not ground truth. "Specificity" measured by file references, line numbers, error messages, and length-to-vagueness ratio correlates with quality but doesn't capture everything. I'm transparent about what each feature measures.

### 如果有人问 "why not just grep"

grep catches exact duplicates fine. But "fix the auth bug" and "fix the authentication issue" have zero string overlap beyond "fix the". TF-IDF cosine similarity catches these because the key terms (fix, auth/authentication, bug/issue) have high weight in the prompt corpus. At threshold 0.85, this captures ~22% more near-duplicates that exact matching misses entirely. If you only care about exact copies, grep is perfect.

### 如果有人问 "what about embeddings / transformers"

I tried sentence-transformers (all-MiniLM-L6-v2) early. For 15-token prompts the quality difference over TF-IDF was marginal, but it added a model download and ~2 second batch embedding overhead. TF-IDF bigram/trigram captures enough vocabulary overlap for this text length.

That said, Ollama support is built in. Two lines of config to switch to nomic-embed-text for better clustering on longer prompts.

### 如果有人问 "how is the scoring calibrated"

Each sub-score maps to specific features from the papers:
- Specificity: file path references, line numbers, error message patterns, function names — from Google 2512.14982's analysis of what makes instructions actionable
- Position: whether critical context is front-loaded or buried — from Stanford 2307.03172's position bias findings
- Repetition: phrase repetition rate within the prompt — penalized per 2512.14982
- Perplexity proxy: vocabulary richness and sentence structure entropy — from SPELL EMNLP 2023

Weights are research-informed but the calibration is empirical on my own data. I'm not claiming these weights are universal. They're a starting point.

### 如果有人问 performance / scale

M2 Mac: ~1,200 prompts scan in under 2 seconds with TF-IDF. Individual scoring (`reprompt score`) is instant — single prompt evaluation. SQLite stores everything, incremental scanning so subsequent runs only process new sessions.

### 如果有人问 "what tools does it support"

Claude Code (JSONL), Cursor IDE (.vscdb SQLite), Aider (Markdown chat history), Gemini CLI (JSON), Cline (VS Code extension JSON), OpenClaw (JSON). Each adapter is ~50 lines implementing `parse_session(path) -> list[Prompt]`. Codex CLI and GitHub Copilot Chat are on the roadmap. PRs welcome — the interface is intentionally simple.

---

## Posting Checklist

- [ ] Karma >= 20 (currently building — comment 2-3/day on technical posts)
- [ ] Post Tuesday 8:00 AM EST
- [ ] URL points to GitHub repo directly (not landing page)
- [ ] Post text is the first comment (Show HN format)
- [ ] Be online 2-4 hours responding to every comment
- [ ] Answer with technical depth — share actual numbers (threshold values, token counts, timing, paper references)
- [ ] If someone says "I could do this with grep" → acknowledge, explain semantic layer + scoring (prepared response above)
- [ ] If someone asks about LLM scoring → explain deterministic + privacy tradeoff (prepared response above)
- [ ] Don't be defensive about criticism
- [ ] Author comments should add NEW information (real-time updates, deeper technical detail), never repeat the post
- [ ] If post doesn't take off, can resubmit on next major milestone
