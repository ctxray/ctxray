# reprompt compress — Prompt Compression Design

**Date:** 2026-03-22
**Version:** v1.2.x (after Phase 4 extension release)
**Status:** Approved (updated with research findings)

## Summary

Rule-based prompt compression that removes filler words, simplifies phrases, normalizes characters, and cleans LLM output formatting — no LLM required. First step from "analyze your prompts" toward "improve your prompts."

Informed by: LLMLingua (Microsoft), CompactPrompt, TSC, metawake/prompt_compressor, clean-text/ftfy, sanitext, stopwords-iso/zh, goto456/stopwords, and academic hedging/discourse marker research. Full research reports in `.claude/cache/agents/oracle/output-2026-03-22-*.md`.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Input | CLI argument only (`reprompt compress "text"`) | Start simple; --file / stdin / --last N deferred |
| Approach | jieba + 4-layer rule engine | Research validated: rule-based achieves 20-35% compression without ML (TSC reports 40-60%, metawake 22%) |
| Storage | Not stored to DB | Ad-hoc tool; dashboard stats derived from prompt_dna compressibility field |
| Compression level | Medium | Filler removal + phrase simplification + structure cleanup; no sentence rewriting |
| No spaCy/ML deps | Curated word lists instead of POS tagging | Zero-config principle; spaCy adds 300MB+ |

## Architecture

### New file: `src/reprompt/core/compress.py`

Four-layer pipeline:

```
Input text
  → lang_detect() (reuse core/lang_detect.py)
  → Detect mixed language (zh_ratio 0.2–0.8 → "mixed")
  → Mark protected zones (code blocks, file paths, URLs, error messages)
  → Layer 0: Character normalization (lossless, always-on)
  → Layer 2: Phrase simplification (runs before Layer 1)
  → Layer 1: Filler word deletion (jieba segmentation + phrase table)
  → Layer 3: Structure cleanup (markdown, whitespace, LLM output artifacts)
  → Restore protected zones
  → Return CompressResult
```

**Why Layer 2 before Layer 1:** Layer 2's replacement table contains phrases that overlap with Layer 1's deletion list. Running simplification first ensures meaningful replacements ("帮我看看" → "检查") take priority over blind deletion. Layer 1 then only removes remaining filler words that Layer 2 did not match.

**Table deduplication rule:** Phrases in `*_PHRASE_SIMPLIFY` must NOT also appear in `*_FILLER_PHRASES`. Layer 1 tables contain only words not covered by Layer 2.

### Data model

```python
@dataclass
class CompressResult:
    original: str           # Input text
    compressed: str         # Compressed output
    original_tokens: int    # Estimated token count (see Token Counting below)
    compressed_tokens: int  # Compressed token count
    savings_pct: float      # 1 - compressed/original
    changes: list[str]      # Per-layer summaries
    language: str           # Detected language (zh/en/mixed)
```

**`changes` field contract:** Each entry is a per-layer summary string with count and layer name. Examples:
- `"normalized 3 characters"` (Layer 0)
- `"simplified 2 phrases"` (Layer 2)
- `"removed 5 filler words"` (Layer 1)
- `"cleaned 4 markdown artifacts"` (Layer 3)

Terminal output joins these with `, `. No per-match detail — keep it human-readable.

### Token counting

- Chinese-dominant text (zh_ratio > 0.5): count characters (excluding whitespace and punctuation)
- English-dominant text (zh_ratio <= 0.5): count whitespace-separated words
- Mixed text uses the dominant language's method based on zh_ratio threshold

### Protected zones

Regions that must not be compressed:

- Fenced code blocks (``` ... ```)
- Inline code (`...`)
- File paths (`/path/to/file`, `file.py`)
- URLs (`http://...`, `https://...`)
- Stack traces / error message patterns
- Named entities (code identifiers, function names, variable names)

Implementation: regex-replace with numbered placeholders before compression, restore after.
Reuse detection patterns from `extractors.py` `_compute_specificity`.

---

## Layer 0 — Character Normalization (lossless, always-on)

Source: ftfy, sanitext, llm-textfix research.

Fixes common LLM output character problems without changing meaning:

```python
CHAR_NORMALIZE = {
    # Curly quotes → straight
    "\u201c": '"', "\u201d": '"',   # " " → "
    "\u2018": "'", "\u2019": "'",   # ' ' → '
    # Dashes
    "\u2014": "-",   # em dash → hyphen
    "\u2013": "-",   # en dash → hyphen
    # Spaces
    "\u00a0": " ",   # non-breaking space → space
    "\u200b": "",    # zero-width space → remove
    "\u200c": "",    # zero-width non-joiner → remove
    "\u200d": "",    # zero-width joiner → remove
    "\ufeff": "",    # BOM / zero-width no-break space → remove
    "\u00ad": "",    # soft hyphen → remove
    # Full-width → half-width (common in CJK text)
    # Applied via unicodedata.normalize('NFKC', text)
}
```

Also applies Unicode NFKC normalization (full-width Ａ → A, ﬁ ligature → fi, etc.).

---

## Layer 2 — Phrase Simplification (runs first)

Replacement tables. Longer patterns matched first to avoid partial matches.

### Chinese — Polite Request Prefixes (remove entirely)

Source: FluentU, HanyuAce, spoken Chinese corpus research, prompt optimization guides.

```python
ZH_PHRASE_SIMPLIFY = {
    # Polite request prefixes → remove
    "不好意思打扰一下": "",
    "冒昧问一下": "",
    "能不能帮我": "",
    "可不可以帮我": "",
    "可以帮我...吗": "",
    "你能帮我...吗": "",
    "麻烦你帮我": "",
    "麻烦帮忙": "",
    "我想请你": "",
    "我想请问": "",
    "我想问一下": "",
    "我需要你帮我": "",
    "请你帮我": "",
    "是否可以": "",
    "如果可以的话": "",
    "如果方便的话": "",
    "如果不麻烦的话": "",
    # Verbose action phrases → concise verbs
    "帮我检查一下": "检查",
    "帮我看看": "检查",
    "帮我看一下": "检查",
    "帮我分析一下": "分析",
    "帮我写一个": "写",
    "帮我写一下": "写",
    "帮我改一下": "修改",
    "帮我修改一下": "修改",
    "帮我解释一下": "解释",
    "帮我翻译一下": "翻译",
    "帮我总结一下": "总结",
    "帮我优化一下": "优化",
    "帮我生成一个": "生成",
    "帮我想想": "建议",
    "帮我想一下": "建议",
    # Verbose expressions → concise
    "有没有什么办法": "如何",
    "有没有什么好的方法": "最佳方法",
    "有没有什么": "有哪些",
    "能不能给我一些建议": "建议",
    "你有什么建议吗": "建议",
    "我现在遇到了一个问题": "",  # state problem directly
    "我想知道": "",
    "我想要你": "",
    "我希望你能": "",
    # Verbose expressions
    "在...方面": "关于",
    "关于...这个问题": "关于",
    "在这种情况下": "此时",
    # Redundant intensifiers
    "非常非常": "非常",
    "特别特别": "非常",
    "尽可能地": "尽量",
}
```

### English — Verbose Requests & Phrasing

Source: TSC, metawake/prompt_compressor, Portkey token optimization, IBM prompt engineering, academic hedging research.

```python
EN_PHRASE_SIMPLIFY = {
    # Polite request prefixes → remove (zero-information per TSC)
    "I was wondering if you could": "",
    "Could you please provide me with": "provide",
    "I would like you to create a list of": "list",
    "Can you help me understand": "explain",
    "Could you possibly provide": "provide",
    "Would you be able to": "",
    "Can you go ahead and": "",
    "I want you to help me with": "",
    "What I'd like is for you to": "",
    "I want you to": "",
    "I need you to": "",
    "I would like you to": "",
    "Could you please": "",
    "Can you help me": "",
    "Go ahead and": "",
    "Feel free to": "",
    "Please make sure that": "ensure",
    # Preamble phrases → remove
    "I'm working on a project and": "",
    "so basically what I need is": "",
    "I have a question about": "",
    "my question is": "",
    "let me explain": "",
    "here's what I need": "",
    "what I need is": "",
    "what I'm looking for is": "",
    "I'm looking for": "",
    "I'm trying to": "",
    "I'd like to ask": "",
    # Verbose phrasing → concise (per CompactPrompt/TSC)
    "in order to": "to",
    "due to the fact that": "because",
    "for the purpose of": "to",
    "with regard to": "about",
    "with respect to": "about",
    "in terms of": "regarding",
    "as a result of": "because",
    "in the event that": "if",
    "in the case that": "if",
    "at this point in time": "now",
    "at the present time": "now",
    "prior to": "before",
    "subsequent to": "after",
    "a large number of": "many",
    "the vast majority of": "most",
    "a wide variety of": "various",
    # Periphrastic verbs → simple verbs
    "take into consideration": "consider",
    "take into account": "consider",
    "come to the conclusion": "conclude",
    "give an explanation of": "explain",
    "provide a description of": "describe",
    "make a decision": "decide",
    "conduct an analysis of": "analyze",
    "perform a review of": "review",
    "is able to": "can",
    "has the ability to": "can",
    # Redundant pairs
    "each and every": "every",
    "first and foremost": "first",
    "any and all": "all",
    "completely and totally": "completely",
    "various different": "various",
}
```

---

## Layer 1 — Filler Word Deletion (runs second)

Categorized by information density (Prompt Report arXiv:2406.06608 taxonomy):
- **Zero-information:** Always removable (politeness, tag questions, emotional fillers)
- **Low-information:** Removable in most contexts (discourse fillers, hedges, vague enumerators)

### Chinese Filler Phrases

Source: FluentU, HanyuAce, Frontiers corpus study, stopwords-iso/zh, goto456/stopwords.

```python
ZH_FILLER_PHRASES = [
    # Discourse fillers (话语填充词) — hesitation/stalling
    "嗯", "呃", "哦", "嘛", "啦", "喽", "呗",
    # Verbal tics (口头禅)
    "然后呢", "就是说", "那个", "那么", "那什么",
    "你知道吗", "你知道", "你看", "我跟你说", "怎么说呢",
    # Hedge/softening (语气缓和)
    "基本上", "其实", "反正", "总之", "所以说",
    "说实话", "老实说", "说白了", "毕竟", "其实就是",
    # Temporal fillers
    "的时候", "的话", "到时候",
    # Vague enumerators
    "之类的", "什么的", "啥的", "诸如此类",
    # Tag questions (seeking agreement — zero information to LLM)
    "对吧", "对不对", "是不是", "是吧", "好吧", "行吧",
    "这样子", "就这样",
    # Particles (zero-info in prompt context)
    "一下", "一些",
    # Preambles (state the question/task directly instead)
    "我想问", "请问一下",
]
```

### English Filler Phrases

Source: Wikipedia discourse markers, Cambridge filler words, Enago/SJSU hedging research, Portkey token optimization.

```python
EN_FILLER_PHRASES = [
    # Discourse fillers
    "basically", "actually", "essentially", "literally",
    "honestly", "you know", "I mean", "like",
    "well", "anyway", "right", "okay so",
    "the thing is", "here's the thing",
    "as a matter of fact", "at the end of the day",
    "to be honest", "to be frank", "in my opinion",
    # Hedging language (per academic hedging research — Enago, SJSU)
    "it seems like", "it appears that", "apparently",
    "presumably", "to some extent", "to a certain degree",
    "more or less", "roughly", "arguably",
    "I believe", "I suppose", "I assume",
    "not sure but", "I'm not entirely sure but",
    # Politeness markers (zero-info per TSC)
    "please", "kindly",
    "I would appreciate if", "I would really appreciate",
    "thank you", "thanks in advance", "thank you so much",
    "if you don't mind", "I'd be grateful if",
    "it would be great if", "I was wondering if",
    "would it be possible to",
    # Sentence-initial fillers (only when at start of sentence)
    "so",  # when sentence-initial filler, not conjunction
]
```

---

## Layer 3 — Structure Cleanup (enhanced with LLM output patterns)

Source: budparr markdown regex, strip-markdown, sanitext, llm-textfix, clean-text.

Three sub-layers:

### 3A. Whitespace normalization
```python
text = re.sub(r'\n{3,}', '\n\n', text)          # Collapse 3+ newlines → 2
text = re.sub(r'[ \t]+\n', '\n', text)           # Trailing whitespace on lines
text = re.sub(r'\n[ \t]+\n', '\n\n', text)       # Lines with only whitespace
text = re.sub(r' {2,}', ' ', text)               # Multiple spaces → single
```

### 3B. Markdown/LLM output cleanup
```python
# Header normalization (LLM outputs often have excessive depth)
text = re.sub(r'^#{5,}\s', '#### ', text, flags=re.M)  # Cap at H4

# Strip formatting markers (common in pasted LLM output context)
text = re.sub(r'\*{3}([^*]+)\*{3}', r'\1', text)  # ***bold italic*** → text
text = re.sub(r'\*{2}([^*]+)\*{2}', r'\1', text)  # **bold** → text
text = re.sub(r'\*([^*]+)\*', r'\1', text)          # *italic* → text

# Remove decorative elements
text = re.sub(r'^---+$', '', text, flags=re.M)      # Horizontal rules
text = re.sub(r'^===+$', '', text, flags=re.M)      # Alt horizontal rules

# Normalize bullet markers (inconsistent formatting from LLM)
text = re.sub(r'^[\*\-\+]\s', '- ', text, flags=re.M)

# Remove decorative emoji and symbols
text = re.sub(r'[\U0001F600-\U0001F9FF]', '', text)  # Emoji block
text = re.sub(r'[✓✗✘✔✕★☆●○■□▸▹►▻▪▫]', '', text)  # Decorative symbols
```

### 3C. Punctuation and conjunction cleanup
```python
# Merge duplicate punctuation
text = re.sub(r'，{2,}', '，', text)     # ，，→ ，
text = re.sub(r'。{2,}', '。', text)     # 。。→ 。
text = re.sub(r',{2,}', ',', text)       # ,, → ,
text = re.sub(r'\.{4,}', '...', text)   # .... → ...

# Remove dangling conjunctions at sentence start (artifact of phrase deletion)
ZH_DANGLING = ["然后", "而且", "并且", "所以", "因为", "但是", "不过"]
EN_DANGLING = ["and", "but", "so", "then", "also", "however", "therefore"]
# Match at line/sentence start after prior deletions

# Remove empty lines left by deletions
text = re.sub(r'\n{3,}', '\n\n', text)  # Final pass
```

---

## Language Handling

- `lang_detect()` from `core/lang_detect.py` returns `LanguageInfo` with a single `lang` value (zh/en/ja/ko)
- **Mixed detection:** `compress.py` computes `zh_ratio` from `LanguageInfo.script_ratios["cjk"]`. If zh_ratio is between 0.2 and 0.8, treat as "mixed" for `CompressResult.language`. `lang_detect` itself never returns "mixed".
- Chinese (zh_ratio > 0.5): jieba segmentation → word-level matching → phrase replacement
- English (zh_ratio <= 0.2): whitespace tokenization → phrase replacement
- Mixed (0.2 < zh_ratio <= 0.5): segment by sentence, apply Chinese rules to Chinese sentences and English rules to English sentences

## jieba Graceful Degradation

If jieba is not installed, fall back to character-level substring matching for Chinese text, consistent with `extractors_zh.py`. Compression quality degrades (less precise word boundaries) but does not error.

## CLI Command

```
reprompt compress "text"
```

**Options:**
- `--json` — JSON output (CompressResult as dict)
- `--copy` — Copy compressed result to clipboard (reuse `sharing/clipboard.py`). If `copy_to_clipboard()` returns False, print warning: "Could not copy to clipboard (xclip/xsel not found)"

**Terminal output (Rich):**

```
  Original:    帮我看看这个文件的时候，我们需要检查一下错误处理的部分
  Compressed:  检查此文件错误处理部分

  Tokens:  28 → 11  (61% saved)
  Changes: simplified 1 phrase, removed 3 filler words
```

**New file: `src/reprompt/output/compress_terminal.py`** — Rich rendering for compress results.

## Dashboard Integration

### prompt_dna: new `compressibility` field

In `extractors.py` `extract_features()`, add:

```python
compressibility: float  # 0.0 - 1.0, computed via lightweight compress pass
```

Calculated during scan by running Layer 0 + Layer 2 + Layer 1 on the prompt text and measuring `1 - (compressed_len / original_len)`. Stored in prompt_dna alongside existing features.

**`feature_vector()` audit:** Adding `compressibility` to `PromptDNA` changes the length of `feature_vector()` output. Before merging, audit `scorer.py` and any other consumer of `feature_vector()` to confirm they do not depend on positional indexing. The scorer uses named field access (`dna.context_specificity`), not vector positions, so this should be safe — but must be verified during implementation.

### Terminal report (`reprompt report`)

Add one line in the insights section:

```
Compressibility:  avg 23% — your prompts could be ~23% shorter without losing information
```

### HTML dashboard (`reprompt report --html`)

Add compressibility stats to `report_data["overview"]` dict (computed in `pipeline.py` alongside existing overview stats). The HTML template renders a new card:
- Average compressibility percentage + visual bar
- Top 3 most compressible prompts (hover shows before/after)

### `reprompt insights`

Add compressibility insight using the existing dict shape:

```python
{
    "category": "verbosity",
    "finding": f"You: {avg_compress:.0%} avg compressible content",
    "optimal": "Research-optimal: <15%",
    "action": "Remove filler phrases, be more direct with instructions",
    "impact": "medium",
}
```

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `core/compress.py` | **Create** | 4-layer compression engine + CompressResult |
| `output/compress_terminal.py` | **Create** | Rich terminal rendering |
| `cli.py` | Modify | Add `compress` command |
| `core/extractors.py` | Modify | Add `compressibility` field to extract_features |
| `core/prompt_dna.py` | Modify | Add `compressibility` to PromptDNA (audit `feature_vector()`) |
| `core/insights.py` | Modify | Add compressibility insight |
| `core/pipeline.py` | Modify | Compute avg compressibility for report_data["overview"] |
| `output/terminal.py` | Modify | Add compressibility line to report |
| `output/html_report.py` | Modify | Add compressibility card using report_data["overview"] |

## Testing

- Unit tests for each compression layer (0, 1, 2, 3) with zh + en
- Layer execution order test (Layer 2 before Layer 1, no overlapping matches)
- Character normalization tests (curly quotes, zero-width chars, full-width)
- Markdown cleanup tests (excessive newlines, bold/italic strip, header cap, emoji removal)
- Protected zone tests (code blocks, URLs, file paths not compressed)
- Edge cases: empty input, pure code, pure English, pure Chinese, mixed zh/en
- jieba-absent fallback test (character-level matching still works)
- CompressResult correctness (savings_pct matches actual, changes list format)
- Token counting: zh-dominant vs en-dominant vs mixed
- CLI integration test (--json output format, --copy with clipboard failure)
- Compressibility field in prompt_dna (scan pipeline)
- `feature_vector()` length stability test

## Research References

| Source | Used For |
|--------|----------|
| [LLMLingua (Microsoft)](https://arxiv.org/abs/2310.05736) | Information density taxonomy (not used for ML, only for categorization) |
| [CompactPrompt](https://arxiv.org/abs/2510.18043) | Self-information taxonomy: zero/low/compressible/context-dependent tokens |
| [TSC](https://developer-service.blog/telegraphic-semantic-compression-tsc-a-semantic-compression-method-for-llm-contexts/) | Grammar filtering rules, preserve list (nouns, verbs, numbers, entities, negations) |
| [metawake/prompt_compressor](https://github.com/metawake/prompt_compressor) | YAML rule engine pattern, 22% avg compression benchmark |
| [stopwords-iso/zh](https://github.com/stopwords-iso/stopwords-zh) | 1,892 Chinese stop words |
| [goto456/stopwords](https://github.com/goto456/stopwords) | HIT/Baidu/SCU Chinese stop word lists |
| [ftfy](https://github.com/rspeer/python-ftfy) | Character normalization patterns |
| [sanitext](https://github.com/panispani/sanitext) | Zero-width char removal, homoglyph mapping |
| [clean-text](https://github.com/jfilter/clean-text) | URL/email stripping, Unicode normalization |
| [Prompt Report (arXiv:2406.06608)](https://arxiv.org/abs/2406.06608) | Prompt taxonomy for categorizing compression rules |
| [Enago: Hedging in Academic Writing](https://www.enago.com/academy/hedging-in-academic-writing/) | English hedging language list |
| [FluentU Chinese Filler Words](https://www.fluentu.com/blog/chinese/chinese-filler-words/) | Chinese filler word categories |
| [Frontiers: ni zhidao corpus](https://www.frontiersin.org/articles/10.3389/fpsyg.2021.716791) | Chinese pragmatic marker research |

## Not in Scope (deferred)

- `--file` / stdin / `--last N` input modes
- Custom filler word config via config.toml / YAML (inspired by metawake pattern)
- LLM-powered semantic compression (`reprompt suggest`, v1.3)
- Sentence rewriting / paraphrasing
- spaCy POS tagging (TSC approach — too heavy for zero-config)
- N-gram alias compression (CompactPrompt/TokenSpan — needs repeated phrases, better for long docs)
