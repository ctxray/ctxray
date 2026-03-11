# Chinese Community Posts

## V2EX (/t/create — 分享创造节点)

**标题:** 开源工具 reprompt — 分析你的 AI 编程提示词，发现 32% 是重复的

**正文:**

各位 V 友好，分享一个自己做的开源 CLI 工具。

用 Claude Code 写了几个月代码后发现一个问题：我总是在重复问同样的问题 — "修一下这个失败的测试"、"给 X 加单元测试"、"把 Y 重构成 Z"。于是做了 reprompt 来量化这个现象。

**reprompt 做什么：**
- 扫描 AI 编程工具的会话文件（支持 Claude Code、OpenClaw）
- 两层去重：SHA-256 精确匹配 + TF-IDF 余弦相似度（能识别"修复登录 bug" ≈ "修一下认证的问题"）
- TF-IDF 提取高频短语（二元/三元词组，过滤停用词）
- K-means 聚类把相似的提示词归组
- 自动分类提示词模式（debug/implement/test/review/refactor）
- 追踪提示词演变趋势（具体度评分、词汇广度）
- MCP 服务器，可以在 Claude Code 中直接查询你的提示词库

**安装使用：**
```bash
pipx install reprompt-cli
reprompt scan
reprompt report
```

**有意思的发现：**
- 32% 的提示词是近似重复
- 调试类提示词比实现类短 3 倍（而且效果更差）
- 追踪一周后，自然开始写更具体的提示词

所有数据本地处理，不上传任何内容。嵌入模型支持 TF-IDF（默认，零配置）、Ollama、sentence-transformers。

MIT 协议，~260 个测试，严格 mypy。

GitHub: https://github.com/reprompt-dev/reprompt
PyPI: https://pypi.org/project/reprompt-cli/

欢迎反馈，什么样的指标会让你每天去看提示词分析？

---

## 掘金 (juejin.cn)

**标题:** 我分析了 1200+ 条 AI 编程提示词，发现 32% 是重复的 — 于是做了一个开源工具

**正文:**

## 背景

用 AI 编程工具（Claude Code、Cursor、Copilot）写代码的开发者，每周都会产生几百条提示词。它们散落在各种会话文件里，从来没有被复盘过。

我用 Claude Code 几个月后发现自己总在重复：

- "修一下这个失败的测试"
- "给这个模块加单元测试"
- "把这个函数重构成..."

于是做了 [reprompt](https://github.com/reprompt-dev/reprompt) — 一个分析 AI 编程提示词的 CLI 工具。

## 技术方案

### 两层去重

大多数去重工具只做精确匹配。但 "修复登录 bug" 和 "修一下认证的问题" 明显是同一意图。

reprompt 用两层：

1. **SHA-256 哈希** — 精确匹配，O(1) 查找
2. **TF-IDF 余弦相似度** — 语义近似匹配，阈值可配置（默认 0.85）

### 高频短语提取

单词频率分析噪音太大 — "function"、"test"、"add" 没有信息量。reprompt 用 TF-IDF 的 n-gram 提取（二元/三元词组）+ 英文停用词过滤，能提取出 "failing test fixture"、"refactor authentication middleware" 这样有意义的短语。

### 提示词模式库

提取高频模式，自动分类：

| 类别 | 示例 |
|------|------|
| debug | "fix the failing test..." |
| test | "add unit tests for..." |
| refactor | "refactor X to use..." |
| implement | "add a new endpoint for..." |

长期使用后，这就是你的个人提示词库 — 哪些提示词对哪种任务最有效。

### 趋势追踪

```bash
reprompt trends
```

- 具体度评分：你的提示词是否越来越具体？
- 词汇广度：是否使用了更多技术术语？
- 类别分布：每个时间段哪种类型的提示词最多？

### 会话效果评分

```bash
reprompt effectiveness
```

基于 5 个维度评分：干净退出、持续时间、工具调用密度、错误率、提示词具体度。

### MCP 服务器

```bash
pip install reprompt-cli[mcp]
reprompt mcp-serve
```

注册到 Claude Code 的 `.mcp.json`，AI 助手可以在编程过程中搜索你的提示词历史，推荐更好的提示词。

## 我的发现

1. **32% 重复率** — 我以为自己每次都在写新提示词，其实不是
2. **调试提示词比实现提示词短 3 倍** — "修一下" 是很差的提示词
3. **追踪改变行为** — 看了一周数据后，自然开始写更具体的提示词

## 技术栈

- Python 3.10+，scikit-learn（TF-IDF + K-means），SQLite
- ~260 个测试，严格 mypy，ruff lint/format
- 插件化适配器（Claude Code JSONL、OpenClaw JSON，易扩展）
- 嵌入后端可选：TF-IDF（默认）/ Ollama / sentence-transformers / OpenAI
- 零配置开箱即用，可选 TOML/环境变量自定义
- **所有数据本地处理**

## 快速上手

```bash
pipx install reprompt-cli
reprompt scan
reprompt report
reprompt library
reprompt trends
```

MIT 协议，欢迎 star 和贡献。

**GitHub:** https://github.com/reprompt-dev/reprompt

---

你觉得什么指标最有用？什么功能会让你每天查看提示词分析？
