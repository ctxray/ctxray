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

## Title

Show HN: Reprompt – Prompt analytics for AI coding sessions (6 tools, zero config)

## URL

https://github.com/reprompt-dev/reprompt

## Post Text（Show HN 帖子的 body 就是第一条评论）

Hey HN, I'm Chris. I built reprompt because after months of daily AI coding I had hundreds of session files and no idea which prompts actually worked well.

The core problem: I kept rewriting the same prompts in slightly different words. "Fix the auth bug" one day, "fix the authentication issue" the next. Exact string matching catches identical copies, but misses these semantic duplicates.

reprompt does two-layer dedup: SHA-256 for exact matches, then TF-IDF cosine similarity (threshold 0.85) for near-dupes. I chose TF-IDF over sentence-transformers because coding prompts average ~15 tokens — at that length, n-gram overlap is enough and you skip the model download. The threshold of 0.85 was empirical: below 0.8 you get false positives ("add auth" matching "add tests"), above 0.9 you miss obvious dupes.

Beyond dedup, it extracts bigram/trigram hot phrases (TF-IDF with stopword filtering), clusters similar prompts with K-means, and auto-categorizes patterns into debug/implement/test/review/refactor. The \`recommend\` command analyzes which patterns correlate with effective sessions and suggests specificity upgrades. The \`effectiveness\` command scores sessions on a composite metric (tool usage, errors, specificity). And \`trends\` tracks how your prompting evolves over time across sliding windows.

What surprised me: my debug prompts average 8 tokens, my implementation prompts average 25. The short ones correlate with longer, less productive sessions. Makes sense — vague input, vague output. After a week of tracking I started being more specific and it actually helped.

There's also \`reprompt lint\` — checks prompts against quality rules (too short, too vague, debug prompts without file references) and exits non-zero on errors. Ships with a GitHub Action for teams that want prompt quality in CI.

You can try it without your own data:

    pipx install reprompt-cli
    reprompt demo

The demo generates 6 weeks of realistic sessions with built-in duplication patterns. Or point it at your real sessions with \`reprompt scan\` — auto-detects 6 tools: Claude Code, Cursor IDE, Aider, Gemini CLI, Cline, OpenClaw.

Python 3.10+, scikit-learn, SQLite. 371 tests, strict mypy. Embedding backend is pluggable — TF-IDF (default, zero config), Ollama, sentence-transformers. Everything runs locally. MIT.

What would you want to know about your AI coding habits?

---

## 作者后续评论（准备好，有人问时贴）

### 如果有人问 "why not just grep"

Good question. grep + wc catches exact duplicates. But "fix the auth bug" and "fix the authentication issue" are the same intent with zero string overlap beyond "fix the". TF-IDF cosine similarity catches these because the important terms ("fix", "auth/authentication", "bug/issue") have high TF-IDF weight in the prompt corpus. At threshold 0.85, this catches an additional ~22% near-duplicates that exact matching misses.

That said, for exact-match-only use cases, grep is perfectly fine. reprompt is for when you want the semantic layer.

### 如果有人问 "what about embeddings / transformers"

I tried sentence-transformers (all-MiniLM-L6-v2) early on. For prompts averaging 15 tokens, the quality difference over TF-IDF was marginal, but it added a model download and ~2 second embedding overhead. TF-IDF with bigram/trigram extraction captures enough of the vocabulary overlap at this text length.

That said, if you're already running Ollama locally, you can switch to embedding-based similarity with two lines of config. It gives better clustering results for longer, more complex prompts.

### 如果有人问 performance / scale

On an M2 Mac, ~1200 prompts process in under 2 seconds with the TF-IDF backend. The bottleneck is reading session files from disk, not the NLP. SQLite handles the storage, with incremental scanning so subsequent runs only process new sessions. 371 tests, ~4,700 lines of code.

### 如果有人问 "this is just for Claude Code?"

Started with Claude Code but now supports 6 tools: Claude Code (JSONL), OpenClaw (JSON), Cursor IDE (.vscdb SQLite), Aider (Markdown chat history), Gemini CLI (JSON), and Cline (Anthropic MessageParam JSON). Each adapter is ~50 lines implementing \`parse_session(path) -> list[Prompt]\`. GitHub Copilot Chat, Continue.dev, and Windsurf are on the roadmap. PRs for other tools welcome — the adapter pattern is intentionally simple.

---

## Posting Checklist

- [ ] Karma >= 20 (currently building — comment 2-3/day on technical posts)
- [ ] Post Tuesday 8:00 AM EST
- [ ] URL points to GitHub repo directly (not landing page)
- [ ] Post text is the first comment (Show HN format)
- [ ] Be online 2-4 hours responding to every comment
- [ ] Answer with technical depth — share actual numbers (threshold values, token counts, timing)
- [ ] If someone says "I could do this with grep" → acknowledge, explain semantic layer (prepared response above)
- [ ] Don't be defensive about criticism
- [ ] If post doesn't take off, can resubmit on next major milestone
- [ ] Author comments should add NEW information (real-time updates, deeper technical detail), never repeat the post
