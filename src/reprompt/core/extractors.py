# src/reprompt/core/extractors.py
"""Tier 1 feature extractors -- regex-based, zero external dependencies.

Extracts 30+ features from prompt text in <1ms. All features are computable
without any ML model or external service.

Research basis for feature selection:
- Structure features: The Prompt Report (arXiv:2406.06608)
- Repetition: Google Research (arXiv:2512.14982)
- Position: Lost in the Middle (arXiv:2307.03172)
- Specificity: DETAIL (arXiv:2512.02246)
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from reprompt.core.cost import estimate_tokens as _estimate_tokens
from reprompt.core.lang_detect import detect_prompt_language
from reprompt.core.library import categorize_prompt
from reprompt.core.prompt_dna import PromptDNA
from reprompt.core.segmenter import PromptSegment, segment_prompt

# -- Regex patterns --

_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_FILE_REF_RE = re.compile(
    r"(?:[\w./~-]+\.(?:py|ts|js|go|rs|java|rb|cpp|c|h|jsx|tsx|vue|svelte|css|html|yaml|yml"
    r"|toml|json|sql|sh|md))"
    r"|(?:line\s+\d+)"
    r"|(?::\d+(?::\d+)?)"
)
_ERROR_RE = re.compile(
    r"(?i)(?:error|exception|traceback|TypeError|ValueError|KeyError|AttributeError"
    r"|ImportError|RuntimeError|IndexError|SyntaxError|NameError|FileNotFoundError"
    r"|ConnectionError|TimeoutError|PermissionError|OSError|IOError"
    r"|failed|FAILED|FAIL)"
)
_ROLE_RE = re.compile(r"(?i)^(?:you are|act as|as a|role:)", re.MULTILINE)
_CONSTRAINT_RE = re.compile(
    r"(?i)\b(?:do not|don't|must not|never|avoid|must|should|ensure|make sure"
    r"|only|without|except|unless)\b"
)
_EXAMPLE_RE = re.compile(
    r"(?i)(?:example|e\.g\.|for instance|input\s*:.*output\s*:|before\s*:.*after\s*:)",
    re.DOTALL,
)
_OUTPUT_FORMAT_RE = re.compile(
    r"(?i)(?:(?:return|output|format|respond)\s+(?:as|in|with)\b"
    r"|(?:json|markdown|csv|yaml|xml|table)\b.*(?:format|field|column))"
)
_STEP_BY_STEP_RE = re.compile(
    r"(?i)(?:step[- ]by[- ]step|think through|one at a time|let'?s think|chain of thought)"
)
_SECTION_RE = re.compile(r"^#{1,4}\s+\S", re.MULTILINE)
_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")

_VAGUE_WORDS = frozenset(
    {
        "something",
        "somehow",
        "maybe",
        "probably",
        "stuff",
        "things",
        "whatever",
        "anything",
        "it",
        "this",
        "that",
        "some",
    }
)
_HEDGE_WORDS = frozenset(
    {
        "maybe",
        "perhaps",
        "might",
        "could",
        "possibly",
        "somewhat",
        "kind of",
        "sort of",
        "I think",
        "I guess",
    }
)


def extract_features(
    text: str,
    *,
    source: str,
    session_id: str,
    project: str | None = None,
) -> PromptDNA:
    """Extract all Tier 1 features from a prompt and return a PromptDNA.

    Detects prompt language and routes to the appropriate locale extractor.
    This is the main entry point. Runs in <1ms for typical prompts.
    """
    stripped = text.strip()
    prompt_hash = hashlib.sha256(stripped.encode()).hexdigest() if stripped else ""

    if not stripped:
        return PromptDNA(prompt_hash=prompt_hash, source=source, task_type="other", locale="en")

    # -- Language detection and routing --
    lang_info = detect_prompt_language(stripped)

    if lang_info.lang == "zh":
        # Lazy import to avoid loading jieba for English-only users
        from reprompt.core.extractors_zh import extract_features_zh

        dna = extract_features_zh(text, source=source, session_id=session_id, project=project)
        return _attach_compressibility(dna, text)

    # -- English extraction (default path) --

    # -- Basic metrics --
    words = re.findall(r"\b\w+\b", stripped)
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
    example_count = _count_examples(stripped)
    has_output_format = bool(_OUTPUT_FORMAT_RE.search(stripped))
    has_step_by_step = bool(_STEP_BY_STEP_RE.search(stripped))
    section_count = len(_SECTION_RE.findall(stripped))

    # -- Code blocks --
    code_blocks = _CODE_BLOCK_RE.findall(stripped)
    code_block_count = len(code_blocks)
    has_code_blocks = code_block_count > 0
    code_chars = sum(len(b) for b in code_blocks)
    code_block_ratio = code_chars / len(stripped) if stripped else 0.0

    # -- File references --
    file_refs = _FILE_REF_RE.findall(stripped)
    file_reference_count = len(file_refs)
    has_file_references = file_reference_count > 0

    # -- Error messages --
    has_error_messages = bool(_ERROR_RE.search(stripped))

    # -- Research: Keyword repetition [Google 2512.14982] --
    keyword_repetition_freq, instruction_repetition = _compute_repetition(words)

    # -- Research: Instruction position [Lost in the Middle 2307.03172] --
    segments = segment_prompt(stripped)
    key_instruction_position = _find_instruction_position(segments)
    critical_info_distribution = _classify_distribution(segments)

    # -- Attention sink: Opening quality --
    opening_quality = _score_opening(stripped, has_file_references, has_error_messages)

    # -- Context specificity --
    context_specificity = _compute_specificity(
        stripped, has_code_blocks, has_file_references, has_error_messages, word_count
    )

    # -- Ambiguity --
    ambiguity_score = _compute_ambiguity(stripped, words, word_count)

    # -- Complexity --
    complexity_score = _compute_complexity(
        word_count, sentence_count, code_block_count, constraint_count, section_count
    )

    dna = PromptDNA(
        prompt_hash=prompt_hash,
        source=source,
        task_type=task_type,
        token_count=_estimate_tokens(text, "en"),
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
        locale="en",
    )
    return _attach_compressibility(dna, text)


# -- Internal helpers --


def _attach_compressibility(dna: PromptDNA, text: str) -> PromptDNA:
    """Compute and attach compressibility score (0.0-1.0)."""
    from reprompt.core.compress import compress_text

    cr = compress_text(text)
    # savings_pct is 0-100 (percentage), normalize to 0.0-1.0
    dna.compressibility = round(cr.savings_pct / 100.0, 4)
    return dna


def _count_examples(text: str) -> int:
    """Count the number of examples in the prompt."""
    count = 0
    count += len(re.findall(r"(?i)\bexample\s*\d*\s*:", text))
    count += len(re.findall(r"(?i)input\s*:.*?output\s*:", text, re.DOTALL))
    if count == 0 and re.search(r"(?i)\b(example|e\.g\.)", text):
        count = 1
    return count


def _compute_repetition(words: list[str]) -> tuple[float, bool]:
    """Compute keyword repetition frequency.

    Based on Google Research arXiv:2512.14982: repeating core prompt once
    (k=2) yields up to 76% accuracy improvement on non-reasoning tasks.
    We measure how much the user naturally repeats key content words.

    Returns (repetition_freq, instruction_repeated).
    """
    if len(words) < 4:
        return (0.0, False)

    # Filter to content words (>3 chars, not common stop words)
    stop = frozenset(
        {
            "the",
            "and",
            "for",
            "that",
            "this",
            "with",
            "from",
            "have",
            "will",
            "are",
            "was",
            "were",
            "been",
            "being",
            "has",
            "had",
            "does",
            "did",
            "but",
            "not",
            "you",
            "all",
            "can",
            "her",
            "his",
            "its",
            "our",
            "they",
            "them",
            "then",
            "than",
            "into",
            "when",
            "which",
            "there",
            "about",
            "should",
            "would",
            "could",
            "also",
            "just",
            "more",
            "some",
        }
    )
    content_words = [w.lower().strip(".,;:!?\"'()[]{}") for w in words if len(w) > 3]
    content_words = [w for w in content_words if w and w not in stop]

    if not content_words:
        return (0.0, False)

    counts = Counter(content_words)
    repeated = {w: c for w, c in counts.items() if c >= 2}

    if not repeated:
        return (0.0, False)

    # Repetition freq = fraction of content words that are repeated
    repeated_tokens = sum(c for c in repeated.values())
    rep_freq = (repeated_tokens - len(repeated)) / len(content_words)

    # Check if the first content word (likely the instruction verb) is repeated
    first_content = content_words[0] if content_words else ""
    instruction_repeated = first_content in repeated

    return (min(rep_freq, 1.0), instruction_repeated)


def _find_instruction_position(segments: list[PromptSegment]) -> float:
    """Find where the key instruction is positioned in the prompt.

    Based on Lost in the Middle (arXiv:2307.03172):
    - Position 0.0 = start (best attention ~75%)
    - Position 0.5 = middle (worst attention ~45%)
    - Position 1.0 = end (moderate attention ~65%)

    For single-segment prompts that are entirely an instruction, use position
    0.0 (start) rather than the midpoint, since the instruction *is* at the
    start -- the midpoint 0.5 is an artifact of there being only one segment
    spanning the whole text.

    Returns normalized position [0.0, 1.0].
    """
    instruction_segments = [s for s in segments if s.segment_type == "instruction"]

    if not instruction_segments:
        # No instruction found -- default to start (assume the whole thing is instruction)
        return 0.0

    # Single-segment prompt: the instruction starts at the beginning
    if len(segments) == 1 and instruction_segments[0] is segments[0]:
        return 0.0

    # Multi-segment: use the midpoint of the first instruction segment
    seg = instruction_segments[0]
    return (seg.start_pos + seg.end_pos) / 2


def _classify_distribution(segments: list[PromptSegment]) -> str:
    """Classify how critical information is distributed across the prompt."""
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


def _score_opening(text: str, has_file_refs: bool, has_errors: bool) -> float:
    """Score the quality of the prompt's opening.

    Based on ICLR 2025 Attention Sink: first tokens get disproportionate
    attention. A strong opening = better LLM comprehension.
    """
    first_line = text.split("\n")[0].strip()
    if not first_line:
        return 0.0

    score = 0.0
    first_lower = first_line.lower()

    # Starts with action verb -> strong opening
    action_verbs = {
        "fix",
        "add",
        "create",
        "implement",
        "debug",
        "explain",
        "write",
        "update",
        "remove",
        "refactor",
        "build",
        "test",
        "review",
        "deploy",
        "migrate",
        "optimize",
        "delete",
        "move",
        "rename",
        "install",
        "configure",
    }
    first_word = first_lower.split()[0] if first_lower.split() else ""
    if first_word in action_verbs:
        score += 0.4

    # First line contains specifics
    if has_file_refs and _FILE_REF_RE.search(first_line):
        score += 0.3
    if has_errors and _ERROR_RE.search(first_line):
        score += 0.2

    # Length penalty: too short = vague
    if len(first_line.split()) >= 5:
        score += 0.1

    return min(score, 1.0)


def _compute_specificity(
    text: str,
    has_code: bool,
    has_files: bool,
    has_errors: bool,
    word_count: int,
) -> float:
    """Compute context specificity score [0.0, 1.0].

    Based on DETAIL paper (arXiv:2512.02246): more specific prompts produce
    better outputs, especially for smaller models and procedural tasks.
    """
    if word_count == 0:
        return 0.0

    score = 0.0

    # Code blocks = high specificity
    if has_code:
        score += 0.3

    # File references = targeted
    if has_files:
        score += 0.25

    # Error messages = concrete problem
    if has_errors:
        score += 0.25

    # Numbers in text (line numbers, counts, versions)
    numbers = re.findall(r"\b\d+\b", text)
    if len(numbers) >= 2:
        score += 0.1
    elif len(numbers) >= 1:
        score += 0.05

    # Proper nouns / identifiers (CamelCase, snake_case)
    identifiers = re.findall(r"\b[A-Z][a-z]+[A-Z]\w*\b|\b\w+_\w+\b", text)
    if identifiers:
        score += 0.1

    return min(score, 1.0)


def _compute_ambiguity(text: str, words: list[str], word_count: int) -> float:
    """Compute ambiguity score [0.0, 1.0]. Higher = more ambiguous."""
    if word_count == 0:
        return 1.0

    lower_words = [w.lower().strip(".,;:!?\"'()[]{}") for w in words]
    score = 0.0

    # Vague words ratio
    vague_count = sum(1 for w in lower_words if w in _VAGUE_WORDS)
    score += min(vague_count / max(word_count, 1) * 3, 0.4)

    # Hedge words
    lower_text = text.lower()
    hedge_count = sum(1 for h in _HEDGE_WORDS if h in lower_text)
    score += min(hedge_count * 0.1, 0.3)

    # Very short prompts are inherently ambiguous
    if word_count < 5:
        score += 0.3
    elif word_count < 10:
        score += 0.1

    return min(score, 1.0)


def _compute_complexity(
    word_count: int,
    sentence_count: int,
    code_blocks: int,
    constraints: int,
    sections: int,
) -> float:
    """Estimate task complexity [0.0, 1.0]."""
    score = 0.0

    # Length contributes to complexity
    if word_count > 200:
        score += 0.3
    elif word_count > 100:
        score += 0.2
    elif word_count > 50:
        score += 0.1

    # Multi-sentence = more complex
    if sentence_count > 5:
        score += 0.2
    elif sentence_count > 2:
        score += 0.1

    # Code blocks = technical complexity
    score += min(code_blocks * 0.1, 0.2)

    # Constraints = more requirements
    score += min(constraints * 0.05, 0.15)

    # Sections = structured complex request
    score += min(sections * 0.05, 0.15)

    return min(score, 1.0)
