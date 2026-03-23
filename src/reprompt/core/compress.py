"""Four-layer rule-based prompt compression engine.

Compresses prompts while preserving technical content (code, URLs, paths).
Protected zones are marked before compression and restored after.

Layer architecture:
  - Layer 0: Whitespace normalization
  - Layer 1: Filler/hedge word deletion
  - Layer 2: Phrase simplification
  - Layer 3: Structural deduplication

# IMPORTANT: Layer 2 (simplification) runs BEFORE Layer 1 (deletion) per spec
# Execution order: Layer 0 -> Layer 2 -> Layer 1 -> Layer 3
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from reprompt.core.lang_detect import detect_prompt_language

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


# -- Compression layers (all stubs for now) --


def _layer0_whitespace(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 0: Whitespace normalization. (STUB)"""
    return text, []


def _layer1_deletion(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 1: Filler/hedge word deletion. (STUB)"""
    return text, []


def _layer2_simplification(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 2: Phrase simplification. (STUB)"""
    return text, []


def _layer3_dedup(text: str, zh_ratio: float) -> tuple[str, list[str]]:
    """Layer 3: Structural deduplication. (STUB)"""
    return text, []


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

    working_text, changes = _layer0_whitespace(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer2_simplification(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer1_deletion(working_text, zh_ratio)
    all_changes.extend(changes)

    working_text, changes = _layer3_dedup(working_text, zh_ratio)
    all_changes.extend(changes)

    # Restore protected zones
    compressed = _restore_protected_zones(working_text, zones)

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
