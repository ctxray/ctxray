# src/reprompt/core/extractors_zh.py
"""Chinese feature extractors for PromptDNA.

Ports all 30+ Tier 1 features with Chinese-specific regex patterns.
Uses jieba for word segmentation when available, falls back to character-level.

Produces the same PromptDNA output shape as the English extractor.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from reprompt.core.library import categorize_prompt
from reprompt.core.prompt_dna import PromptDNA
from reprompt.core.segmenter import PromptSegment, segment_prompt

# -- Try importing jieba (optional) --
try:
    import jieba

    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

# -- Chinese regex patterns --

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_FILE_REF_RE = re.compile(
    r"(?:[\w./~-]+\.(?:py|ts|js|go|rs|java|rb|cpp|c|h|jsx|tsx|vue|svelte|css|html|yaml|yml"
    r"|toml|json|sql|sh|md))"
    r"|(?:(?:第|line\s+)\d+(?:行)?)"
    r"|(?::\d+(?::\d+)?)"
)
_ERROR_RE = re.compile(
    r"(?i)(?:error|exception|traceback|TypeError|ValueError|KeyError|AttributeError"
    r"|ImportError|RuntimeError|IndexError|SyntaxError|NameError|FileNotFoundError"
    r"|ConnectionError|TimeoutError|PermissionError|OSError|IOError"
    r"|failed|FAILED|FAIL)"
    r"|(?:错误|异常|报错|失败|崩溃)"
)
_ROLE_RE = re.compile(
    r"(?:^|(?<=\n))(?:你是一?个?|作为|扮演|角色[:：]|假设你是|假装你是|你现在是)",
    re.MULTILINE,
)
_CONSTRAINT_RE = re.compile(
    r"(?:不要|不能|不可以|必须|请勿|禁止|务必|确保|限制|仅|只能|除非|避免"
    r"|不得|严禁|切勿|一定要|保证|不许)"
)
_EXAMPLE_RE = re.compile(
    r"(?:例如|比如|举例|示例|像是|譬如"
    r"|输入[:：].*输出[:：]"
    r"|如[:：]|比方说)",
    re.DOTALL,
)
_OUTPUT_FORMAT_RE = re.compile(
    r"(?:(?:输出|返回|格式|响应).*(?:JSON|json|表格|列表|markdown|Markdown|csv|CSV|yaml|YAML|xml|XML)"
    r"|以.*格式(?:输出|返回|响应)"
    r"|(?:JSON|json|表格|列表|markdown|csv).*(?:格式|字段|列))"
)
_STEP_BY_STEP_RE = re.compile(
    r"(?:分步骤|逐步|一步一步|一步步"
    r"|第[一二三四五六七八九十]步"
    r"|先.*然后.*最后"
    r"|思维链|chain of thought"
    r"|step[- ]by[- ]step)"
)
_SECTION_RE = re.compile(
    r"(?:^#{1,4}\s+\S|^[一二三四五六七八九十]+[、.]\s*\S)",
    re.MULTILINE,
)
_SENTENCE_RE = re.compile(r"[。！？；!?]+")

_VAGUE_WORDS_ZH = frozenset(
    {
        "东西",
        "那个",
        "这个",
        "什么",
        "一些",
        "某些",
        "之类",
        "等等",
        "大概",
        "好像",
        "可能",
        "随便",
        "差不多",
    }
)

_HEDGE_WORDS_ZH = frozenset(
    {
        "可能",
        "也许",
        "大概",
        "或许",
        "好像",
        "似乎",
        "感觉",
        "我觉得",
        "我想",
        "我猜",
        "应该",
        "差不多",
    }
)

# Chinese action verbs for opening quality scoring
_ACTION_VERBS_ZH = frozenset(
    {
        "修复",
        "修改",
        "添加",
        "创建",
        "实现",
        "调试",
        "解释",
        "编写",
        "更新",
        "删除",
        "重构",
        "构建",
        "测试",
        "审查",
        "部署",
        "迁移",
        "优化",
        "移除",
        "重命名",
        "安装",
        "配置",
        "分析",
        "设计",
        "检查",
        "生成",
        "查找",
        "帮我",
        "请",
    }
)


def _segment_words(text: str) -> list[str]:
    """Segment Chinese text into words using jieba or character fallback."""
    if _HAS_JIEBA:
        return [w for w in jieba.cut(text) if w.strip()]
    # Fallback: split on whitespace + treat each CJK char as a word
    tokens: list[str] = []
    for part in text.split():
        if re.search(r"[\u4e00-\u9fff]", part):
            # Split CJK characters individually (crude but functional)
            for char in part:
                if "\u4e00" <= char <= "\u9fff":
                    tokens.append(char)
                elif char.strip():
                    tokens.append(char)
        else:
            tokens.append(part)
    return [t for t in tokens if t.strip()]


def extract_features_zh(
    text: str,
    *,
    source: str,
    session_id: str,
    project: str | None = None,
) -> PromptDNA:
    """Extract all Tier 1 features from a Chinese prompt.

    Produces the same PromptDNA shape as the English extractor.
    Uses Chinese-specific regex patterns and jieba word segmentation.
    """
    stripped = text.strip()
    prompt_hash = hashlib.sha256(stripped.encode()).hexdigest() if stripped else ""

    if not stripped:
        return PromptDNA(prompt_hash=prompt_hash, source=source, task_type="other", locale="zh")

    # -- Basic metrics --
    words = _segment_words(stripped)
    word_count = len(words)
    line_count = len(stripped.splitlines())
    sentences = _SENTENCE_RE.split(stripped)
    sentence_count = max(1, len([s for s in sentences if s.strip()]))

    # -- Task type (reuse existing categorizer) --
    task_type = categorize_prompt(stripped)

    # -- Structure --
    has_role = bool(_ROLE_RE.search(stripped))
    constraints = _CONSTRAINT_RE.findall(stripped)
    constraint_count = len(constraints)
    has_constraints = constraint_count > 0
    has_examples = bool(_EXAMPLE_RE.search(stripped))
    example_count = _count_examples_zh(stripped)
    has_output_format = bool(_OUTPUT_FORMAT_RE.search(stripped))
    has_step_by_step = bool(_STEP_BY_STEP_RE.search(stripped))
    section_count = len(_SECTION_RE.findall(stripped))

    # -- Code blocks (same as English -- code is universal) --
    code_blocks = _CODE_BLOCK_RE.findall(stripped)
    code_block_count = len(code_blocks)
    has_code_blocks = code_block_count > 0
    code_chars = sum(len(b) for b in code_blocks)
    code_block_ratio = code_chars / len(stripped) if stripped else 0.0

    # -- File references (same patterns + Chinese line refs) --
    file_refs = _FILE_REF_RE.findall(stripped)
    file_reference_count = len(file_refs)
    has_file_references = file_reference_count > 0

    # -- Error messages (English patterns + Chinese keywords) --
    has_error_messages = bool(_ERROR_RE.search(stripped))

    # -- Research: Keyword repetition [Google 2512.14982] --
    keyword_repetition_freq, instruction_repetition = _compute_repetition_zh(words)

    # -- Research: Instruction position [Lost in the Middle 2307.03172] --
    segments = segment_prompt(stripped)
    key_instruction_position = _find_instruction_position(segments)
    critical_info_distribution = _classify_distribution(segments)

    # -- Attention sink: Opening quality --
    opening_quality = _score_opening_zh(stripped, has_file_references, has_error_messages)

    # -- Context specificity --
    context_specificity = _compute_specificity_zh(
        stripped, has_code_blocks, has_file_references, has_error_messages, word_count
    )

    # -- Ambiguity --
    ambiguity_score = _compute_ambiguity_zh(stripped, words, word_count)

    # -- Complexity --
    complexity_score = _compute_complexity(
        word_count, sentence_count, code_block_count, constraint_count, section_count
    )

    return PromptDNA(
        prompt_hash=prompt_hash,
        source=source,
        task_type=task_type,
        token_count=word_count,  # approximate
        word_count=word_count,
        sentence_count=sentence_count,
        line_count=line_count,
        has_role_definition=has_role,
        has_examples=has_examples,
        example_count=example_count,
        has_constraints=has_constraints,
        constraint_count=constraint_count,
        has_output_format=has_output_format,
        has_step_by_step=has_step_by_step,
        section_count=section_count,
        has_code_blocks=has_code_blocks,
        code_block_count=code_block_count,
        code_block_ratio=round(code_block_ratio, 4),
        has_file_references=has_file_references,
        file_reference_count=file_reference_count,
        has_error_messages=has_error_messages,
        context_specificity=round(context_specificity, 4),
        keyword_repetition_freq=round(keyword_repetition_freq, 4),
        instruction_repetition=instruction_repetition,
        key_instruction_position=round(key_instruction_position, 4),
        critical_info_distribution=critical_info_distribution,
        opening_quality=round(opening_quality, 4),
        complexity_score=round(complexity_score, 4),
        ambiguity_score=round(ambiguity_score, 4),
        extractor_tier=1,
        locale="zh",
    )


# -- Internal helpers --


def _count_examples_zh(text: str) -> int:
    """Count examples in Chinese text."""
    count = 0
    count += len(re.findall(r"(?:示例|例子|例)\s*\d*\s*[:：]", text))
    count += len(re.findall(r"输入[:：].*?输出[:：]", text, re.DOTALL))
    if count == 0 and re.search(r"(?:例如|比如|举例|示例|譬如)", text):
        count = 1
    return count


def _compute_repetition_zh(words: list[str]) -> tuple[float, bool]:
    """Compute keyword repetition for Chinese words.

    Chinese stop words differ from English. Uses jieba-segmented words.
    """
    if len(words) < 4:
        return (0.0, False)

    stop_zh = frozenset(
        {
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这",
            "他",
            "她",
            "它",
            "被",
            "从",
            "把",
            "那",
            "里",
            "让",
            "用",
            "中",
            "为",
            "地",
            "得",
            "对",
            "以",
            "与",
        }
    )
    content_words = [w for w in words if len(w) >= 2 and w not in stop_zh]
    # Also include single-char content words that aren't stop words
    content_words += [
        w for w in words if len(w) == 1 and w not in stop_zh and re.match(r"[\u4e00-\u9fff]", w)
    ]

    if not content_words:
        return (0.0, False)

    counts = Counter(content_words)
    repeated = {w: c for w, c in counts.items() if c >= 2}

    if not repeated:
        return (0.0, False)

    repeated_tokens = sum(c for c in repeated.values())
    rep_freq = (repeated_tokens - len(repeated)) / len(content_words)

    first_content = content_words[0] if content_words else ""
    instruction_repeated = first_content in repeated

    return (min(rep_freq, 1.0), instruction_repeated)


def _find_instruction_position(segments: list[PromptSegment]) -> float:
    """Find instruction position (reuses same logic as English)."""
    for seg in segments:
        if seg.segment_type == "instruction":
            return (seg.start_pos + seg.end_pos) / 2
    return 0.0


def _classify_distribution(segments: list[PromptSegment]) -> str:
    """Classify critical info distribution (reuses same logic as English)."""
    if not segments:
        return "unknown"

    critical_types = {"instruction", "constraint", "output_format"}
    positions: list[float] = []
    for seg in segments:
        if seg.segment_type in critical_types:
            positions.append((seg.start_pos + seg.end_pos) / 2)

    if not positions:
        return "unknown"

    avg_pos = sum(positions) / len(positions)
    if avg_pos < 0.3:
        return "front-loaded"
    if avg_pos > 0.7:
        return "end-loaded"
    if len(positions) >= 2 and max(positions) - min(positions) > 0.5:
        return "distributed"
    return "middle-buried"


def _score_opening_zh(text: str, has_file_refs: bool, has_errors: bool) -> float:
    """Score opening quality for Chinese prompts."""
    first_line = text.split("\n")[0].strip()
    if not first_line:
        return 0.0

    score = 0.0

    # Starts with Chinese action verb or keyword
    for verb in _ACTION_VERBS_ZH:
        if first_line.startswith(verb):
            score += 0.4
            break

    # First line contains file references
    if has_file_refs and _FILE_REF_RE.search(first_line):
        score += 0.3
    if has_errors and _ERROR_RE.search(first_line):
        score += 0.2

    # Length: Chinese chars are denser than English words
    # 10 Chinese chars ~ 5 English words in information density
    char_count = len(re.findall(r"[\u4e00-\u9fff]", first_line))
    if char_count >= 8 or len(first_line) >= 15:
        score += 0.1

    return min(score, 1.0)


def _compute_specificity_zh(
    text: str,
    has_code: bool,
    has_files: bool,
    has_errors: bool,
    word_count: int,
) -> float:
    """Compute context specificity for Chinese prompts."""
    if word_count == 0:
        return 0.0

    score = 0.0

    if has_code:
        score += 0.3
    if has_files:
        score += 0.25
    if has_errors:
        score += 0.25

    numbers = re.findall(r"\b\d+\b", text)
    if len(numbers) >= 2:
        score += 0.1
    elif len(numbers) >= 1:
        score += 0.05

    # CamelCase/snake_case identifiers (code identifiers in Chinese prompts)
    identifiers = re.findall(r"\b[A-Z][a-z]+[A-Z]\w*\b|\b\w+_\w+\b", text)
    if identifiers:
        score += 0.1

    return min(score, 1.0)


def _compute_ambiguity_zh(text: str, words: list[str], word_count: int) -> float:
    """Compute ambiguity score for Chinese prompts."""
    if word_count == 0:
        return 1.0

    score = 0.0

    # Vague words ratio
    vague_count = sum(1 for w in words if w in _VAGUE_WORDS_ZH)
    score += min(vague_count / max(word_count, 1) * 3, 0.4)

    # Hedge words
    hedge_count = sum(1 for h in _HEDGE_WORDS_ZH if h in text)
    score += min(hedge_count * 0.1, 0.3)

    # Very short prompts (Chinese is denser, so lower thresholds)
    if word_count < 3:
        score += 0.3
    elif word_count < 6:
        score += 0.1

    return min(score, 1.0)


def _compute_complexity(
    word_count: int,
    sentence_count: int,
    code_blocks: int,
    constraints: int,
    sections: int,
) -> float:
    """Estimate task complexity (adjusted thresholds for Chinese)."""
    score = 0.0

    # Chinese word counts are different from English (jieba yields fewer tokens)
    # Adjust thresholds: Chinese 100 words ~ English 200 words
    if word_count > 100:
        score += 0.3
    elif word_count > 50:
        score += 0.2
    elif word_count > 25:
        score += 0.1

    if sentence_count > 5:
        score += 0.2
    elif sentence_count > 2:
        score += 0.1

    score += min(code_blocks * 0.1, 0.2)
    score += min(constraints * 0.05, 0.15)
    score += min(sections * 0.05, 0.15)

    return min(score, 1.0)
