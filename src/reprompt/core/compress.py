"""Four-layer rule-based prompt compression engine.

Compresses prompts while preserving technical content (code, URLs, paths).
Protected zones are marked before compression and restored after.

Layer architecture:
  - Layer 0: Character normalization (Unicode -> ASCII, NFKC)
  - Layer 1: Filler/hedge word deletion
  - Layer 2: Phrase simplification
  - Layer 3: Structure cleanup (whitespace, markdown, punctuation)

# IMPORTANT: Layer 2 (simplification) runs BEFORE Layer 1 (deletion) per spec
# Execution order: Layer 0 -> Layer 2 -> Layer 1 -> Layer 3
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from reprompt.core.lang_detect import detect_prompt_language

# -- Optional jieba import (same pattern as extractors_zh.py) --
try:
    import jieba

    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False

# -- Protected zone patterns --

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_URL_RE = re.compile(r"https?://\S+")
_FILE_PATH_EXT_RE = re.compile(
    r"(?:[\w./\\-]+\.(?:py|js|ts|tsx|jsx|rs|go|java|cpp|c|h|md|yml|yaml|toml|json|txt|sh|css"
    r"|html|sql))\b"
)
_FILE_PATH_PREFIX_RE = re.compile(r"(?:(?:\./|/|~/)[\w./\\-]+)")

# Token counting helpers
_WHITESPACE_PUNCT_RE = re.compile(
    r"[\s\u3000\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u300a\u300b"
    r"\u201c\u201d\u2018\u2019\uff08\uff09\u3001.,!?;:()\"']+"
)


@dataclass
class CompressResult:
    """Result of prompt compression."""

    original: str
    compressed: str
    original_tokens: int
    compressed_tokens: int
    savings_pct: float
    changes: list[str] = field(default_factory=list)
    language: str = "en"


@dataclass
class _ProtectedZone:
    """A region of text that must not be modified by compression layers."""

    placeholder: str
    original: str
    start: int
    end: int


def _mark_protected_zones(text: str) -> tuple[str, list[_ProtectedZone]]:
    """Replace code blocks, inline code, URLs, and file paths with placeholders.

    Returns (text_with_placeholders, list_of_zones).
    Protected zones are replaced in priority order:
      1. Code blocks (``` ... ```)  -- highest priority, may contain URLs/paths
      2. Inline code (` ... `)
      3. URLs (https://... or http://...)
      4. File paths (extension-based and prefix-based)
    """
    zones: list[_ProtectedZone] = []
    counter = 0

    # Track which character positions are already protected
    protected_positions: set[int] = set()

    def _collect_matches(pattern: re.Pattern[str], source: str) -> list[re.Match[str]]:
        """Collect matches that don't overlap with already-protected positions."""
        matches = []
        for m in pattern.finditer(source):
            if not any(pos in protected_positions for pos in range(m.start(), m.end())):
                matches.append(m)
        return matches

    # 1. Code blocks (highest priority)
    for m in _CODE_BLOCK_RE.finditer(text):
        placeholder = f"__PROTECTED_{counter}__"
        zones.append(_ProtectedZone(placeholder, m.group(), m.start(), m.end()))
        protected_positions.update(range(m.start(), m.end()))
        counter += 1

    # 2. Inline code
    for m in _collect_matches(_INLINE_CODE_RE, text):
        placeholder = f"__PROTECTED_{counter}__"
        zones.append(_ProtectedZone(placeholder, m.group(), m.start(), m.end()))
        protected_positions.update(range(m.start(), m.end()))
        counter += 1

    # 3. URLs
    for m in _collect_matches(_URL_RE, text):
        placeholder = f"__PROTECTED_{counter}__"
        zones.append(_ProtectedZone(placeholder, m.group(), m.start(), m.end()))
        protected_positions.update(range(m.start(), m.end()))
        counter += 1

    # 4. File paths (extension-based, then prefix-based)
    for pattern in (_FILE_PATH_EXT_RE, _FILE_PATH_PREFIX_RE):
        for m in _collect_matches(pattern, text):
            placeholder = f"__PROTECTED_{counter}__"
            zones.append(_ProtectedZone(placeholder, m.group(), m.start(), m.end()))
            protected_positions.update(range(m.start(), m.end()))
            counter += 1

    # Sort zones by position (descending) so replacements don't shift indices
    zones_sorted = sorted(zones, key=lambda z: z.start, reverse=True)
    result = text
    for zone in zones_sorted:
        result = result[: zone.start] + zone.placeholder + result[zone.end :]

    return result, zones


def _restore_protected_zones(text: str, zones: list[_ProtectedZone]) -> str:
    """Restore placeholders back to original content."""
    result = text
    for zone in zones:
        result = result.replace(zone.placeholder, zone.original)
    return result


def _count_tokens(text: str, zh_ratio: float) -> int:
    """Count tokens: CJK-dominant counts chars (excl whitespace/punct), else counts words."""
    if not text or not text.strip():
        return 0
    if zh_ratio > 0.5:
        # Chinese-dominant: count characters excluding whitespace and punctuation
        cleaned = _WHITESPACE_PUNCT_RE.sub("", text)
        return len(cleaned)
    else:
        # English-dominant: count whitespace-separated words
        return len(text.split())


# -- Layer 0: Character Normalization --

CHAR_NORMALIZE: dict[str, str] = {
    "\u201c": '"',
    "\u201d": '"',  # curly double quotes
    "\u2018": "'",
    "\u2019": "'",  # curly single quotes
    "\u2014": "-",  # em dash
    "\u2013": "-",  # en dash
    "\u00a0": " ",  # non-breaking space
    "\u200b": "",  # zero-width space
    "\u200c": "",  # zero-width non-joiner
    "\u200d": "",  # zero-width joiner
    "\ufeff": "",  # BOM
    "\u00ad": "",  # soft hyphen
}

_CHAR_NORMALIZE_RE = re.compile("|".join(re.escape(k) for k in CHAR_NORMALIZE))


def _layer0_char_normalize(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 0: Character normalization.

    1. Replace curly quotes, dashes, zero-width chars with ASCII equivalents.
    2. Apply NFKC normalization (full-width -> half-width).
    """
    changes: list[str] = []
    original = text

    # Character substitution
    def _replace_char(m: re.Match[str]) -> str:
        return CHAR_NORMALIZE[m.group()]

    text = _CHAR_NORMALIZE_RE.sub(_replace_char, text)

    # NFKC normalization (full-width -> half-width, etc.)
    text = unicodedata.normalize("NFKC", text)

    if text != original:
        changes.append("layer0: character normalization")

    return text, changes


# -- Layer 2: Phrase Simplification --

ZH_PHRASE_SIMPLIFY: dict[str, str] = {
    "不好意思打扰一下": "",
    "冒昧问一下": "",
    "能不能帮我": "",
    "可不可以帮我": "",
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
    "有没有什么办法": "如何",
    "有没有什么好的方法": "最佳方法",
    "有没有什么": "有哪些",
    "能不能给我一些建议": "建议",
    "你有什么建议吗": "建议",
    "我现在遇到了一个问题": "",
    "我想知道": "",
    "我想要你": "",
    "我希望你能": "",
    "在这种情况下": "此时",
    "非常非常": "非常",
    "特别特别": "非常",
    "尽可能地": "尽量",
}

EN_PHRASE_SIMPLIFY: dict[str, str] = {
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
    "each and every": "every",
    "first and foremost": "first",
    "any and all": "all",
    "completely and totally": "completely",
    "various different": "various",
    "take a look at": "check",
    "let me know what you think about it": "",
    "let me know what you think": "",
    "let me know": "",
    "what's happening is that": "",
    "the fact that": "",
    "I need help with": "",
    "not working properly": "failing",
    "split it up into": "split into",
    "there might be some issues with": "possible issues in",
    "the way it handles": "how it handles",
    "at the same time": "simultaneously",
    "on a regular basis": "regularly",
    "as soon as possible": "ASAP",
    "the reason why": "because",
    "for better performance": "for performance",
}

# Pre-sorted by key length (descending) so longer patterns match first
_ZH_PHRASE_PAIRS: list[tuple[str, str]] = sorted(
    ZH_PHRASE_SIMPLIFY.items(), key=lambda kv: len(kv[0]), reverse=True
)
_EN_PHRASE_PAIRS: list[tuple[str, str]] = sorted(
    EN_PHRASE_SIMPLIFY.items(), key=lambda kv: len(kv[0]), reverse=True
)


def _layer2_simplification(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 2: Phrase simplification.

    Replaces verbose phrases with shorter equivalents or removes them entirely.
    Chinese rules applied when zh_ratio > 0.2, English when zh_ratio < 0.8.
    """
    changes: list[str] = []
    original = text

    # Apply Chinese phrase simplification
    if zh_ratio > 0.2:
        for pattern, replacement in _ZH_PHRASE_PAIRS:
            if pattern in text:
                text = text.replace(pattern, replacement)

    # Apply English phrase simplification (case-insensitive)
    if zh_ratio < 0.8:
        for pattern, replacement in _EN_PHRASE_PAIRS:
            # Case-insensitive replacement
            compiled = re.compile(re.escape(pattern), re.IGNORECASE)
            text = compiled.sub(replacement, text)

    if text != original:
        changes.append("layer2: phrase simplification")

    return text, changes


# -- Layer 1: Filler Word Deletion --

ZH_FILLER_PHRASES: list[str] = [
    "嗯",
    "呃",
    "哦",
    "嘛",
    "啦",
    "喽",
    "呗",
    "然后呢",
    "就是说",
    "那个",
    "那么",
    "那什么",
    "你知道吗",
    "你知道",
    "你看",
    "我跟你说",
    "怎么说呢",
    "基本上",
    "其实",
    "反正",
    "总之",
    "所以说",
    "说实话",
    "老实说",
    "说白了",
    "毕竟",
    "其实就是",
    "的时候",
    "的话",
    "到时候",
    "之类的",
    "什么的",
    "啥的",
    "诸如此类",
    "对吧",
    "对不对",
    "是不是",
    "是吧",
    "好吧",
    "行吧",
    "这样子",
    "就这样",
    "一下",
    "一些",
    "我想问",
    "请问一下",
]

EN_FILLER_PHRASES: list[str] = [
    "basically",
    "actually",
    "essentially",
    "literally",
    "honestly",
    "you know",
    "I mean",
    "well",
    "anyway",
    "okay so",
    "the thing is that",
    "here's the thing",
    "as a matter of fact",
    "at the end of the day",
    "to be honest",
    "to be frank",
    "in my opinion",
    "it seems like",
    "it appears that",
    "apparently",
    "presumably",
    "to some extent",
    "to a certain degree",
    "more or less",
    "roughly",
    "arguably",
    "I believe",
    "I suppose",
    "I assume",
    "not sure but",
    "I'm not entirely sure but",
    "please",
    "kindly",
    "I would appreciate if",
    "I would really appreciate",
    "thank you",
    "thanks in advance",
    "thank you so much",
    "if you don't mind",
    "I'd be grateful if",
    "it would be great if",
    "I was wondering if",
    "would it be possible to",
    "thanks in advance for your help",
    "I really appreciate it",
    "thank you for your time",
    "thank you for your help",
    "if that makes sense",
    "does that make sense",
    "if you know what I mean",
    "just to be clear",
    "I want to make sure that",
    "kind of",
    "sort of",
    "additionally",
    "furthermore",
    "moreover",
]

# Sort by length descending so longer patterns match first
_ZH_FILLER_SORTED: list[str] = sorted(ZH_FILLER_PHRASES, key=len, reverse=True)
_EN_FILLER_SORTED: list[str] = sorted(EN_FILLER_PHRASES, key=len, reverse=True)

# Precompile English filler regexes with word boundary awareness
_EN_FILLER_REGEXES: list[re.Pattern[str]] = []
for _phrase in _EN_FILLER_SORTED:
    # Multi-word phrases: match the whole phrase with optional trailing comma/space
    # Single-word fillers: use word boundaries to avoid partial matches
    if " " in _phrase:
        _EN_FILLER_REGEXES.append(re.compile(re.escape(_phrase) + r",?\s*", re.IGNORECASE))
    else:
        _EN_FILLER_REGEXES.append(
            re.compile(r"\b" + re.escape(_phrase) + r"\b,?\s*", re.IGNORECASE)
        )


def _layer1_deletion(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 1: Filler/hedge word deletion.

    Removes filler words and hedging phrases.
    Chinese: jieba segmentation when available, character-level substring fallback.
    English: regex-based phrase matching with word boundary awareness.
    """
    changes: list[str] = []
    original = text

    # Chinese filler deletion
    if zh_ratio > 0.2:
        if _HAS_JIEBA:
            # Jieba-based: segment, remove single-token fillers, rejoin
            words = list(jieba.cut(text))
            filler_set = set(ZH_FILLER_PHRASES)
            filtered = [w for w in words if w not in filler_set]
            text = "".join(filtered)
        # Always do substring matching for multi-char phrase fillers
        # (jieba may split "对吧" into "对"+"吧", missing the phrase)
        for filler in _ZH_FILLER_SORTED:
            text = text.replace(filler, "")

    # English filler deletion
    if zh_ratio < 0.8:
        for regex in _EN_FILLER_REGEXES:
            text = regex.sub("", text)

    if text != original:
        changes.append("layer1: filler word deletion")

    return text, changes


# -- Layer 3: Structure Cleanup --

# Dangling conjunctions at line start
_ZH_DANGLING = ["然后", "而且", "并且", "所以", "因为", "但是", "不过"]
_EN_DANGLING = ["and", "but", "so", "then", "also", "however", "therefore"]

_ZH_DANGLING_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(w) for w in _ZH_DANGLING) + r")\s*", re.MULTILINE
)
_EN_DANGLING_RE = re.compile(
    r"^\s*\b(" + "|".join(re.escape(w) for w in _EN_DANGLING) + r")\b\s*",
    re.MULTILINE | re.IGNORECASE,
)

# Emoji range pattern (supplementary multilingual plane emoticons)
_EMOJI_RE = re.compile(r"[\U0001F600-\U0001F9FF]")

# Decorative symbols
_DECORATIVE_RE = re.compile(
    r"[\u2713\u2717\u2718\u2714\u2715\u2605\u2606"
    r"\u25CF\u25CB\u25A0\u25A1\u25B8\u25B9\u25BA\u25BB"
    r"\u25AA\u25AB]"
)


def _layer3_structure(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 3: Structure cleanup.

    3A: Whitespace normalization
    3B: Markdown/LLM output cleanup
    3C: Punctuation cleanup
    """
    changes: list[str] = []
    original = text

    # -- 3A: Whitespace normalization --
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    # -- 3B: Markdown/LLM output cleanup --
    text = re.sub(r"^#{5,}\s", "#### ", text, flags=re.M)
    # Bold-italic (***text***) must come before bold (**text**)
    text = re.sub(r"\*{3}([^*]+)\*{3}", r"\1", text)
    text = re.sub(r"\*{2}([^*]+)\*{2}", r"\1", text)
    # Italic (*text*) -- careful: don't match file globs like *.py
    text = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", text)
    # Horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.M)
    text = re.sub(r"^===+$", "", text, flags=re.M)
    # Emoji
    text = _EMOJI_RE.sub("", text)
    # Decorative symbols
    text = _DECORATIVE_RE.sub("", text)

    # -- 3C: Punctuation cleanup --
    text = re.sub(r"\uff0c{2,}", "\uff0c", text)  # Chinese comma
    text = re.sub(r"\u3002{2,}", "\u3002", text)  # Chinese period
    text = re.sub(r",{2,}", ",", text)  # English comma
    text = re.sub(r"\.{4,}", "...", text)  # Excessive dots

    # Dangling conjunctions at line start
    if zh_ratio > 0.2:
        text = _ZH_DANGLING_RE.sub("", text)
    if zh_ratio < 0.8:
        text = _EN_DANGLING_RE.sub("", text)

    # Final whitespace cleanup pass
    text = re.sub(r"\n{3,}", "\n\n", text)

    if text != original:
        changes.append("layer3: structure cleanup")

    return text, changes


def compress_text(text: str) -> CompressResult:
    """Compress a prompt while preserving technical content.

    Applies four layers in order: Layer 0 -> Layer 2 -> Layer 1 -> Layer 3.
    Code blocks, inline code, URLs, and file paths are protected from modification.
    """
    if not text:
        return CompressResult(
            original=text,
            compressed="",
            original_tokens=0,
            compressed_tokens=0,
            savings_pct=0.0,
            changes=[],
            language="en",
        )

    # Detect language
    lang_info = detect_prompt_language(text)
    zh_ratio = lang_info.script_ratios.get("cjk", 0.0)
    language = lang_info.lang

    # Count original tokens
    original_tokens = _count_tokens(text, zh_ratio)

    # Mark protected zones
    working_text, zones = _mark_protected_zones(text)

    # Apply layers in spec order: 0 -> 2 -> 1 -> 3
    # IMPORTANT: Layer 2 (simplification) runs BEFORE Layer 1 (deletion) per spec
    all_changes: list[str] = []

    working_text, changes = _layer0_char_normalize(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer2_simplification(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer1_deletion(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer3_structure(working_text, zh_ratio)
    all_changes.extend(changes)

    # Restore protected zones
    compressed = _restore_protected_zones(working_text, zones)

    # -- Post-compression cleanup pass --
    # Fix 4: Remove closing pleasantry sentences (full sentences at end that are pure thanks)
    compressed = re.sub(
        r"[.!?\s]*(?:thanks|thank you|thx|ty)[\w\s,]*[.!?]?\s*$",
        "",
        compressed,
        flags=re.IGNORECASE,
    )
    # Fix 1: Whitespace and punctuation cleanup after all layers
    compressed = compressed.strip()
    compressed = re.sub(r"  +", " ", compressed)  # collapse multiple spaces
    compressed = re.sub(r"^[,;.\s]+", "", compressed).strip()  # remove leading punctuation
    compressed = re.sub(
        r"(?i)^that\s+", "", compressed
    )  # orphaned "that" at start after filler deletion
    compressed = re.sub(r"(?i)(\.\s*)that\s+", r"\1", compressed)  # orphaned "that" after period
    compressed = re.sub(r",\s*,", ",", compressed)  # collapse double commas
    # Remove orphaned conjunctions before punctuation (e.g. "and ?" from deleted phrases)
    compressed = re.sub(r"\s+(?:and|or)\s*([?!.])", r"\1", compressed)
    # Remove trailing orphaned punctuation like ". ." or "? ."
    compressed = re.sub(r"([.!?])\s*[.]+\s*$", r"\1", compressed)
    # Remove isolated trailing punctuation (e.g. lone "." at end after phrase deletion)
    compressed = re.sub(r"\s+[.!?]\s*$", "", compressed)
    compressed = compressed.strip()

    # Capitalize first letter after sentence-ending punctuation if lowercase
    def _capitalize_after_period(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2).upper()

    compressed = re.sub(r"([.!?]\s+)([a-z])", _capitalize_after_period, compressed)
    # Capitalize first letter if compression stripped a leading prefix
    # Only capitalize when the original text started with an uppercase letter
    if compressed and compressed[0].islower():
        # Find the first alphabetic character in the original text
        first_alpha = next((c for c in text if c.isalpha()), "")
        if first_alpha.isupper():
            compressed = compressed[0].upper() + compressed[1:]

    if compressed != _restore_protected_zones(working_text, zones):
        all_changes.append("post: whitespace/punctuation cleanup")

    # Count compressed tokens and compute savings
    compressed_tokens = _count_tokens(compressed, zh_ratio)
    if original_tokens > 0:
        savings_pct = round((1 - compressed_tokens / original_tokens) * 100, 1)
    else:
        savings_pct = 0.0

    return CompressResult(
        original=text,
        compressed=compressed,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        savings_pct=savings_pct,
        changes=all_changes,
        language=language,
    )
