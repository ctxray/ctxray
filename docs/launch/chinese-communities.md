# Chinese Community Posts

## V2EX (/t/create — 分享创造节点)

**标题:** 开源工具 reprompt — 分析你的 AI 编程提示词，用 4 篇 NLP 论文给你的 prompt 打分

**状态:** 需要邀请码，暂缓。内容已准备好，等邀请码后直接发。

**正文:**

各位 V 友好，分享一个自己做的开源 CLI 工具。

用 AI 编程工具写了六个月代码后，我想搞清楚一件事：我的哪些提示词真的有效，哪些只是在浪费时间。每次调试失败的 session 开头，几乎都有一句 "修一下这个 bug" 或者 "为什么这里报错"——模糊、没有文件、没有上下文。

于是做了 reprompt，扫描 AI 编程会话文件，对每条 prompt 打 0-100 的质量分。

打分基于 4 篇研究论文的 NLP 特征：
- specificity（文件路径、行号、函数名、错误信息）→ Google 2512.14982
- position bias（关键信息放在 prompt 开头 vs 埋在中间）→ Stanford 2307.03172
- repetition penalty（重复短语）→ 同上
- 词汇熵代理（vocabulary diversity 作为信息密度指标）→ SPELL EMNLP 2023

效果很直观：

    reprompt score "修一下这个 bug"
    → 18/100

    reprompt score "修复 auth.service.ts:47 的空指针 — token 在 session 过期时变 null，应该抛 AuthException 而不是返回 200"
    → 91/100

**安装使用：**
```bash
pipx install reprompt-cli
reprompt demo              # 先用内置示例数据看看
reprompt scan              # 扫你的 AI 编程会话（自动识别工具）
reprompt insights          # 和研究基准对比，看哪类 prompt 最弱
reprompt digest --quiet    # 一行输出本周 vs 上周变化（可挂 hook）
```

**支持的工具（自动识别）:**
- Claude Code, Cursor IDE, Aider, Gemini CLI, Cline, OpenClaw — 6 种，零配置

**隐私：** 所有数据本地处理，打分是纯 NLP（无 LLM 调用），可选 Ollama 嵌入。

MIT 协议，493 个测试，严格 mypy。

**GitHub:** https://github.com/reprompt-dev/reprompt

你最常用的 prompt 是什么？我猜很多人跟我一样，debug 类的最短、最模糊。

---

## 掘金 (juejin.cn) — v0.7.2 更新版

**标题:** 我用 4 篇 NLP 论文给自己的 AI 编程提示词打分——大多数不超过 30 分

**正文:**

## 背景

用 AI 编程工具（Claude Code、Cursor、Aider、Gemini CLI）写代码的开发者，每周产生几百条提示词，散落在会话文件里，从来没有被分析过。

我做了 [reprompt](https://github.com/reprompt-dev/reprompt) — 一个分析 AI 编程提示词的开源 CLI。本文重点讲最新功能：**Prompt Science Engine**，基于 4 篇 NLP 研究论文的 0-100 打分系统。

## 核心问题

"好的 prompt"到底好在哪里？

直觉上是"写清楚"，但这不可量化。研究界对此有更具体的答案：

| 研究 | 核心发现 | 量化指标 |
|------|----------|----------|
| Google arXiv:2512.14982 | 重复短语降低输出质量 | 重复率 |
| Stanford arXiv:2307.03172 | LLM 对 prompt 首尾权重更高（position bias） | 关键信息位置 |
| SPELL EMNLP 2023 | 困惑度（perplexity）可作为信息密度代理指标 | 词汇熵 |
| Prompt Report arXiv:2406.06608 | 任务分类体系（12 类） | 类别归属 |

基于这 4 篇论文，我实现了 `reprompt score`。

## 打分原理

`reprompt score "prompt"` 输出 0-100 分，分四个维度：

**Specificity（0-40 分）** — 最重要的维度。检测文件路径、行号、函数名、具体错误信息的存在。有这些信息的 prompt 给 AI 更可操作的上下文。

**Position（0-25 分）** — 关键信息是否在 prompt 开头。根据 Stanford 的 position bias 研究，LLM 对 prompt 头尾的权重远高于中间部分。把 "auth.service.ts:47" 放在最前面比放在最后好。

**Repetition（0-15 分，越低扣分越多）** — 检测 prompt 内的重复短语。

**Perplexity proxy（0-20 分）** — 用词汇多样性（Shannon 熵）近似估算信息密度。"修一下这个 bug" 和 "fix the NPE when token expires in the OAuth refresh flow" 的信息密度差距显而易见。

## 实际效果

```bash
$ reprompt score "修一下这个 bug"
Prompt Quality Score: 18/100
  Specificity     ██░░░░░░░░  5/40  — 无文件、无函数、无错误信息
  Position        ███░░░░░░░  8/25  — 上下文空洞
  Repetition      ██████████  0/15  — 无惩罚
  Perplexity      ██░░░░░░░░  5/20  — 词汇单一

$ reprompt score "修复 auth.service.ts:47 的空指针异常 — token 在 session 超时时变 null，应该抛 AuthException 而不是返回 200"
Prompt Quality Score: 91/100
  Specificity     █████████░  38/40 — 文件路径、行号、错误类型、预期行为
  Position        █████████░  22/25 — 关键信息前置
  Repetition      ██████████  0/15  — 无惩罚
  Perplexity      ██████████  20/20 — 词汇丰富
```

## 其他功能

### `reprompt compare "prompt A" "prompt B"`

逐维度对比两个提示词，帮助你理解改动带来的具体变化。

### `reprompt insights`

将你的历史 prompt 按类别（debug/implement/test/refactor 等）统计平均分，与研究论文的最优基准对比，告诉你哪类 prompt 需要优先改进。

示例输出：
```
Prompt Insights
─────────────────────────────────────────────────
debug    : avg 38/100  ██░░░░░░░░  Research: 65+  ← 重点改进
implement: avg 63/100  ██████░░░░  Research: 70+
test     : avg 71/100  ███████░░░  Research: 68   ✓
```

### `reprompt digest`

每周对比本周 vs 上周：prompt 数量、平均分变化、类别分布。
`reprompt digest --quiet` 输出单行，可挂 Claude Code Stop hook，每次 session 结束后自动显示。

```
Week of Mar 10: 156 prompts ↑12% | specificity 47→62 ↑ | debug ↓ implement ↑
```

## 去重与分析架构

打分之前，需要先把你的 prompt 历史清理干净：

**两层去重：**
- SHA-256 精确匹配 — O(1) 查找
- TF-IDF 余弦相似度（阈值 0.85）— 识别语义近似 prompt

为什么用 TF-IDF 而不是 transformer embedding？对于平均 15 个 token 的短文本，n-gram 重叠已经足够。sentence-transformers 的效果提升边际，但需要模型下载，代价不值得。当然如果你本地跑 Ollama，两行配置可以切换到向量嵌入。

**热词短语提取：**
标准英文停用词过滤不了 "write function"、"create class" 这类编程领域通用词。reprompt 加入了约 60 个编程领域停用词（instruction verbs、structure nouns、data types 等），让 TF-IDF 提取出真正有意义的短语。

## 技术栈

- Python 3.10+，scikit-learn（TF-IDF、K-means），SQLite
- 493 个测试，严格 mypy，ruff lint/format
- 6 个 Adapter：Claude Code JSONL、Cursor .vscdb、Aider Markdown、Gemini CLI JSON、Cline JSON、OpenClaw JSON
- 嵌入后端可选：TF-IDF（默认零配置）/ Ollama / sentence-transformers / OpenAI
- **所有数据本地处理，打分为纯 NLP（无 LLM 调用）**

## 快速上手

```bash
pipx install reprompt-cli

# 先用内置示例数据体验
reprompt demo

# 扫描你的真实 AI 会话
reprompt scan

# 打分与分析
reprompt score "你的 prompt"          # 单条打分
reprompt compare "旧版" "新版"         # 对比分析
reprompt insights                      # 个人弱项诊断
reprompt digest                        # 周对比报告
reprompt digest --quiet                # 一行摘要（挂 hook 用）
```

MIT 协议，欢迎 star 和贡献。

**GitHub:** https://github.com/reprompt-dev/reprompt
**PyPI:** https://pypi.org/project/reprompt-cli/

---

你调试类的 prompt 和实现类的 prompt，哪个写得更具体？我猜调试类普遍更短、更模糊——这正是 `reprompt insights` 最常发现的问题。
