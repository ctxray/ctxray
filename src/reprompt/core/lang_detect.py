"""Unicode-range language detection for prompts.

Detects the dominant script in a prompt using Unicode character range counting.
Supports: Chinese (zh), Japanese (ja), Korean (ko), English (en) as default.

Zero external dependencies -- pure regex on Unicode code points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Unicode ranges for CJK scripts
_CJK_UNIFIED = re.compile(r"[\u4e00-\u9fff]")  # CJK Unified Ideographs
_CJK_EXT_A = re.compile(r"[\u3400-\u4dbf]")  # CJK Unified Ideographs Extension A
_CJK_COMPAT = re.compile(r"[\uf900-\ufaff]")  # CJK Compatibility Ideographs
_HIRAGANA = re.compile(r"[\u3040-\u309f]")  # Hiragana
_KATAKANA = re.compile(r"[\u30a0-\u30ff]")  # Katakana
_HANGUL = re.compile(r"[\uac00-\ud7af]")  # Hangul Syllables
_HANGUL_JAMO = re.compile(r"[\u1100-\u11ff\u3130-\u318f]")  # Hangul Jamo + Compat Jamo
_LATIN = re.compile(r"[a-zA-Z]")

# Strip code blocks before language detection
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


@dataclass(frozen=True)
class LanguageInfo:
    """Result of language detection."""

    lang: str  # ISO 639-1: "zh", "ja", "ko", "en"
    confidence: float  # 0.0 to 1.0
    script_ratios: dict[str, float] = field(default_factory=dict)

    @property
    def is_cjk(self) -> bool:
        """Whether the detected language uses CJK characters."""
        return self.lang in ("zh", "ja", "ko")


def detect_prompt_language(text: str) -> LanguageInfo:
    """Detect the dominant language of a prompt.

    Strategy:
    1. Strip code blocks (code is language-neutral).
    2. Count characters in each Unicode script range.
    3. Dominant script determines language.
    4. CJK characters shared by zh/ja -- disambiguate by Hiragana/Katakana presence.

    Returns LanguageInfo with lang, confidence, and script ratios.
    """
    if not text or not text.strip():
        return LanguageInfo(lang="en", confidence=0.0, script_ratios={})

    # Strip code blocks to avoid code biasing detection
    clean = _CODE_BLOCK_RE.sub("", text)
    if not clean.strip():
        return LanguageInfo(lang="en", confidence=0.0, script_ratios={})

    # Count script characters
    cjk_count = (
        len(_CJK_UNIFIED.findall(clean))
        + len(_CJK_EXT_A.findall(clean))
        + len(_CJK_COMPAT.findall(clean))
    )
    hiragana_count = len(_HIRAGANA.findall(clean))
    katakana_count = len(_KATAKANA.findall(clean))
    hangul_count = len(_HANGUL.findall(clean)) + len(_HANGUL_JAMO.findall(clean))
    latin_count = len(_LATIN.findall(clean))

    total_script = cjk_count + hiragana_count + katakana_count + hangul_count + latin_count

    if total_script == 0:
        return LanguageInfo(lang="en", confidence=0.0, script_ratios={})

    # Compute ratios
    ratios: dict[str, float] = {
        "cjk": cjk_count / total_script,
        "hiragana": hiragana_count / total_script,
        "katakana": katakana_count / total_script,
        "hangul": hangul_count / total_script,
        "latin": latin_count / total_script,
    }

    # Japanese: has Hiragana or Katakana (unique to Japanese)
    japanese_score = ratios["hiragana"] + ratios["katakana"]
    if japanese_score > 0.1:
        confidence = min(japanese_score + ratios["cjk"], 1.0)
        return LanguageInfo(lang="ja", confidence=round(confidence, 4), script_ratios=ratios)

    # Korean: Hangul characters present
    if ratios["hangul"] > 0.1:
        confidence = ratios["hangul"]
        return LanguageInfo(lang="ko", confidence=round(confidence, 4), script_ratios=ratios)

    # Chinese: CJK characters dominant (no Hiragana/Katakana/Hangul)
    if ratios["cjk"] > ratios["latin"]:
        confidence = ratios["cjk"]
        return LanguageInfo(lang="zh", confidence=round(confidence, 4), script_ratios=ratios)

    # Default: English
    confidence = ratios["latin"]
    return LanguageInfo(lang="en", confidence=round(confidence, 4), script_ratios=ratios)
