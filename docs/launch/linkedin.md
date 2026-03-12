# LinkedIn Posts

## Post 1 (POSTED — 原始版，已发出，不修改)

I've been using AI coding tools (Claude Code, Cursor, etc.) daily for months. One question kept nagging me: which of my prompts actually work well, and which ones waste time?

So I built reprompt — an open-source CLI that analyzes your AI coding prompt history.

What I learned from my own data:
→ My debug prompts are 3x shorter than implement prompts — and significantly less effective
→ "Fix the bug" performs measurably worse than naming the file, function, and expected behavior
→ After a week of tracking, I naturally started writing better prompts

[...rest of original post]

---

## Post 2 — v0.7 更新版（带截图，发时机：距 Post 1 两周以上）

**发帖策略:**
- 不更新 Post 1 正文（改了没人看，而且失去时效感）
- Post 2 是全新角度：从"我做了个工具"变成"我发现了关于自己的数据"
- 必须带截图：HTML dashboard 图 + score 对比截图，否则 LinkedIn reach 减半
- 配图建议：左边 `reprompt score "fix the bug"` (23分)，右边 `reprompt score "具体的prompt"` (89分) 的 terminal 截图并排

---

**Post 2 正文:**

I've been tracking my AI coding prompt quality for 3 weeks. Here's what the data actually showed.

I built a tool that scores every prompt I type to AI coding tools on a 0-100 scale — based on features from 4 NLP research papers (specificity, position bias, vocabulary entropy, repetition). When I saw my own results, I went quiet for a minute.

My debug prompts: average 38/100. "Fix the bug." "It's not working." "Why is this failing." All variations on the same vague request, all scoring in the 15-30 range. I'd typed some version of "fix the bug" hundreds of times.

My implementation prompts: average 63/100. Longer, more context, specific files and expected behaviors. The AI responses were noticeably better — not because the AI got smarter, but because I told it what I actually wanted.

The tool is called reprompt. After 3 weeks of tracking, two things changed: I stopped writing "fix the bug" (I now default to file + line + expected behavior + error message), and I started keeping a library of prompts that worked well so I don't rewrite them from scratch.

It runs entirely locally — session files never leave your machine. Supports Claude Code, Cursor, Aider, Gemini CLI, Cline, and OpenClaw.

`pipx install reprompt-cli` → `reprompt scan` → `reprompt insights`

Open source, MIT, free forever: github.com/reprompt-dev/reprompt

What's your most-used prompt to AI coding tools? (I'd guess it's something with "fix" in it.)

#OpenSource #AI #DeveloperTools #Python #PromptEngineering

---

**配图指南（发帖前准备）:**

截图 1 — score 对比（最高优先级）:
```
$ reprompt score "fix the bug"
Prompt Quality Score: 23/100
──────────────────────────────
Specificity     ████░░░░░░  8/40
Position bias   ███░░░░░░░  6/25
Repetition      ██████████  0/15  ← no penalty
Perplexity      ██░░░░░░░░  9/20

Verdict: Vague — no file, no error, no expected outcome
Tip: Add file path, function name, and what "correct" looks like

$ reprompt score "fix the NPE in auth.service.ts:47 — token null when session expires, should throw AuthException"
Prompt Quality Score: 89/100
──────────────────────────────
Specificity     ██████████  38/40
Position bias   █████████░  22/25
Repetition      ██████████  0/15
Perplexity      █████████░  29/20 → capped at 20
```

截图 2 — HTML dashboard categories chart
截图 3 — `reprompt digest` 周对比输出

**发帖时机:** 周二或周三上午 9-10 点（LinkedIn 最高活跃窗口）
