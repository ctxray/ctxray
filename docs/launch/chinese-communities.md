# Chinese Community Posts

## V2EX (/t/create — 分享创造节点)

**标题:** 开源工具 reprompt — 分析你的 AI 编程提示词，找出哪些有效、哪些在浪费时间

**正文:**

各位 V 友好，分享一个自己做的开源 CLI 工具。

用 AI 编程工具写了几个月代码后发现一个问题：每天产生几十条提示词，但从来没有复盘过。哪些 prompt 真正有效？哪些只是习惯性地重复？于是做了 reprompt。

**reprompt 做什么：**
- 扫描 AI 编程工具的会话文件（支持 Claude Code、OpenClaw、Cursor IDE）
- 两层去重：SHA-256 精确匹配 + TF-IDF 余弦相似度（能识别"修复登录 bug" ≈ "修一下认证的问题"）
- 提取高频短语，自动分类提示词模式（debug/implement/test/review/refactor）
- 追踪提示词演变趋势（具体度、词汇广度）
- `reprompt recommend` — 分析哪些提示词模式效果好，给出改进建议
- `reprompt demo` — 内置示例数据，无需自己的会话就能体验

**安装使用：**
```bash
pipx install reprompt-cli
reprompt demo              # 先用示例数据试试
reprompt scan              # 扫描你的 AI 会话（自动出报告）
reprompt recommend         # 看看哪些 prompt 效果好
```

**有意思的发现：**
- 调试类提示词比实现类短 3 倍 — "修一下" 是效果很差的 prompt
- 追踪一周后，自然开始写更具体的提示词
- 对比不同 prompt 风格的效果差异比预想的大

所有数据本地处理，不上传任何内容。嵌入模型支持 TF-IDF（默认，零配置）、Ollama、sentence-transformers。

MIT 协议，284 个测试，严格 mypy。

**GitHub:** https://github.com/reprompt-dev/reprompt
**PyPI:** https://pypi.org/project/reprompt-cli/

欢迎反馈 — 你最想从 AI 编程会话里看到什么数据？

---

## 掘金 (juejin.cn)

**标题:** 用 TF-IDF 分析 AI 编程提示词：你的 prompt 有多少是在重复劳动？

**正文:**

## 背景

用 AI 编程工具（Claude Code、Cursor、Copilot）写代码的开发者，每周都会产生几百条提示词。它们散落在各种会话文件里，从来没有被复盘过。

我做了 [reprompt](https://github.com/reprompt-dev/reprompt) — 一个分析 AI 编程提示词的开源 CLI 工具。

## 解决什么问题

1. **重复检测** — 你可能以为每次都在写新 prompt，但其实很多只是换了个说法
2. **效果评估** — 哪种风格的 prompt 效果好？"修一下这个 bug" vs "修复 login.py 的认证逻辑 — 过期 token 应该返回 403 而不是 401"
3. **习惯演变** — 你的提示词是否越来越具体？

## 技术方案

### 两层去重

大多数去重工具只做精确匹配。但 "修复登录 bug" 和 "修一下认证的问题" 明显是同一意图。

reprompt 用两层：

1. **SHA-256 哈希** — 精确匹配，O(1) 查找
2. **TF-IDF 余弦相似度** — 语义近似匹配，阈值可配置（默认 0.85）

为什么用 TF-IDF 而不是 transformer？对于平均 15 个 token 的短文本，TF-IDF 的效果接近 transformer 嵌入，但零配置、不需要下载模型。

### 高频短语提取

单词频率分析噪音太大 — "function"、"test"、"add" 没有信息量。reprompt 用 TF-IDF 的 n-gram 提取（二元/三元词组）+ 停用词过滤，能提取出 "refactor authentication middleware" 这样有意义的短语。

### 提示词推荐

```bash
reprompt recommend
```

分析你的提示词历史，对比不同类别的效果评分，给出具体的改进建议。比如告诉你 debug 类 prompt 普遍太短，建议加上文件名、函数名和具体错误信息。

### 体验模式

```bash
reprompt demo
```

内置 107 条真实风格的示例提示词，生成 6 周的模拟会话数据，让你不需要自己的 AI 会话就能看到完整的分析效果。

## 技术栈

- Python 3.10+，scikit-learn（TF-IDF + K-means），SQLite
- 284 个测试，严格 mypy，ruff lint/format
- 插件化适配器（Claude Code JSONL、OpenClaw JSON、Cursor IDE .vscdb）
- 嵌入后端可选：TF-IDF（默认）/ Ollama / sentence-transformers / OpenAI
- 零配置开箱即用，可选 TOML/环境变量自定义
- **所有数据本地处理**

## 快速上手

```bash
pipx install reprompt-cli
reprompt demo              # 试试看
reprompt scan              # 扫你的 AI 会话
reprompt recommend         # 看改进建议
reprompt library           # 个人提示词库
reprompt trends            # 趋势变化
```

MIT 协议，欢迎 star 和贡献。

**GitHub:** https://github.com/reprompt-dev/reprompt

---

你觉得什么指标最有用？什么功能会让你经常去看提示词分析？
