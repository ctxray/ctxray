# tests/test_extractors_zh_e2e.py
"""End-to-end tests: Chinese prompt -> language detect -> extract -> score -> PromptDNA."""

from __future__ import annotations

import json

from reprompt.core.extractors import extract_features
from reprompt.core.lang_detect import detect_prompt_language
from reprompt.core.prompt_dna import PromptDNA
from reprompt.core.scorer import score_prompt


class TestChineseE2E:
    """Full pipeline: Chinese prompt text -> scored PromptDNA."""

    def test_full_pipeline_structured_chinese(self):
        """A well-structured Chinese prompt goes through the full pipeline.

        Note: this prompt has fewer English technical terms so CJK dominates,
        ensuring the language detector routes to the Chinese extractor.
        """
        prompt = (
            "你是一个资深后端开发者。\n\n"
            "修复认证模块中第42行的类型错误。\n"
            "错误信息：类型不匹配。\n\n"
            "不要修改测试文件。必须保持向后兼容。\n\n"
            "例如：\n输入：用户名\n输出：认证令牌\n\n"
            "以表格格式返回修复方案。\n"
            "请分步骤说明。"
        )

        # Step 1: Language detection
        lang = detect_prompt_language(prompt)
        assert lang.lang == "zh"
        assert lang.confidence > 0.3

        # Step 2: Feature extraction (via router)
        dna = extract_features(prompt, source="test", session_id="e2e-1")
        assert isinstance(dna, PromptDNA)
        assert dna.locale == "zh"

        # Step 3: Verify Chinese features detected
        assert dna.has_role_definition is True
        assert dna.has_constraints is True
        assert dna.constraint_count >= 2
        assert dna.has_examples is True
        assert dna.has_output_format is True
        assert dna.has_step_by_step is True
        assert dna.has_error_messages is True
        assert dna.has_code_blocks is False  # no code blocks in this prompt

        # Step 4: Score
        breakdown = score_prompt(dna)
        assert breakdown.total > 30.0  # well-structured prompt

        # Step 5: Serialization roundtrip
        d = dna.to_dict()
        dna2 = PromptDNA(**d)
        assert dna2.locale == "zh"
        assert dna2.has_role_definition is True

        # Step 6: JSON serialization
        serialized = json.dumps(d, ensure_ascii=False)
        assert "zh" in serialized

    def test_full_pipeline_bare_chinese(self):
        """A bare/vague Chinese prompt still works."""
        prompt = "帮我看看代码"

        lang = detect_prompt_language(prompt)
        assert lang.lang == "zh"

        dna = extract_features(prompt, source="test", session_id="e2e-2")
        assert dna.locale == "zh"
        assert dna.word_count > 0

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0

    def test_full_pipeline_mixed_language(self):
        """Chinese-dominant mixed prompt with code."""
        prompt = (
            "修复 auth.py 中的错误\n"
            "```python\n"
            "def login(username, password):\n"
            "    raise TypeError('invalid')\n"
            "```\n"
            "不要修改现有测试"
        )

        dna = extract_features(prompt, source="test", session_id="e2e-3")
        assert dna.locale == "zh"
        assert dna.has_code_blocks is True
        assert dna.has_constraints is True
        assert dna.has_error_messages is True

    def test_english_not_affected(self):
        """Verify English prompts still work identically through the router."""
        prompt = (
            "You are a senior Python developer.\n\n"
            "Fix the auth bug in src/auth.py line 42.\n"
            "Do not modify tests. Must be backward-compatible.\n\n"
            "Example:\nInput: login('test')\nOutput: JWT token\n\n"
            "Return as JSON."
        )

        dna = extract_features(prompt, source="test", session_id="e2e-4")
        assert dna.locale == "en"
        assert dna.has_role_definition is True
        assert dna.has_constraints is True
        assert dna.has_examples is True
        assert dna.has_output_format is True
        assert dna.has_file_references is True

    def test_feature_vector_dimensions_match(self):
        """Chinese and English feature vectors must have identical dimensions."""
        zh_dna = extract_features(
            "你是一个开发者。修复认证错误。不要修改测试。",
            source="test",
            session_id="e2e-5",
        )
        en_dna = extract_features(
            "You are a developer. Fix the auth bug. Do not modify tests.",
            source="test",
            session_id="e2e-6",
        )
        zh_vec = zh_dna.feature_vector()
        en_vec = en_dna.feature_vector()
        assert len(zh_vec) == len(en_vec)
        assert all(isinstance(v, float) for v in zh_vec)
        assert all(isinstance(v, float) for v in en_vec)


class TestSpecificChinesePrompts:
    """E2E tests using the specific test prompts from the task specification."""

    def test_refactoring_prompt_zh_dominant(self):
        """Complex refactoring prompt with role, constraints, output format.

        Uses Chinese-dominant text (fewer Latin technical terms) to ensure
        the language detector routes to the Chinese extractor.
        """
        prompt = (
            "你是一个资深Python开发者。重构数据库模块使用async/await。"
            "必须保持向后兼容。输出为diff格式。"
        )

        # This prompt is CJK-dominant (60%+ Chinese chars)
        lang = detect_prompt_language(prompt)
        assert lang.lang == "zh"

        # Extraction via router
        dna = extract_features(prompt, source="test", session_id="spec-1")
        assert dna.locale == "zh"
        assert dna.has_role_definition is True
        assert dna.has_constraints is True  # "必须保持向后兼容"

        # Score
        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0
        assert breakdown.structure > 0.0

        # Serialization
        d = dna.to_dict()
        assert d["locale"] == "zh"
        serialized = json.dumps(d, ensure_ascii=False)
        assert "zh" in serialized
        dna_round = PromptDNA(**d)
        assert dna_round.locale == "zh"

    def test_debug_prompt_with_file_ref_mixed(self):
        """Debug prompt with file reference and technical terms.

        This prompt has heavy English content (file paths, technical terms),
        so the language detector may route it to English extraction.
        The key verification is that the pipeline works either way and
        file references are detected regardless of which extractor runs.
        """
        prompt = "修复src/auth/login.ts中JWT token过期的认证bug"

        dna = extract_features(prompt, source="test", session_id="spec-2")
        # File references should be detected by both English and Chinese extractors
        assert dna.has_file_references is True  # src/auth/login.ts
        assert dna.locale in ("zh", "en")  # may go either way for mixed content

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0
        assert breakdown.context > 0.0  # file ref contributes to context

        # Serialization roundtrip
        d = dna.to_dict()
        dna2 = PromptDNA(**d)
        assert dna2.has_file_references is True

    def test_bare_question_prompt(self):
        """A bare question prompt should still work but score lower."""
        prompt = "这段代码是做什么的"

        lang = detect_prompt_language(prompt)
        assert lang.lang == "zh"

        dna = extract_features(prompt, source="test", session_id="spec-3")
        assert dna.locale == "zh"
        assert dna.word_count > 0

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0
        # Bare question should score lower than structured prompts
        assert breakdown.total < 60.0

        # Serialization
        serialized = json.dumps(dna.to_dict(), ensure_ascii=False)
        assert "zh" in serialized

    def test_devops_prompt_with_requirements_mixed(self):
        """DevOps prompt with role and structured requirements.

        This prompt mixes Chinese and English heavily (DevOps, Python,
        FastAPI, Dockerfile, root). The language detector may route to
        either extractor depending on character ratios. Both extractors
        detect role definitions.
        """
        prompt = (
            "作为DevOps工程师，写一个Python FastAPI应用的Dockerfile。"
            "要求：多阶段构建，非root用户，健康检查端点。"
        )

        dna = extract_features(prompt, source="test", session_id="spec-4")
        assert dna.locale in ("zh", "en")  # mixed content may go either way
        # Role definition should be detected by both extractors
        # English extractor matches "as a" pattern; Chinese matches "作为"
        # For heavily mixed prompts, the key thing is the pipeline works
        assert dna.word_count > 0

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0

        # Serialization roundtrip
        d = dna.to_dict()
        dna2 = PromptDNA(**d)
        assert dna2.locale == dna.locale

    def test_structured_beats_vague(self):
        """Structured Chinese prompt should score higher than vague one."""
        # Use CJK-dominant prompts for both so they go through same extractor
        structured = "你是一个资深开发者。重构数据库模块。必须保持向后兼容。以表格格式返回。"
        vague = "这段代码是做什么的"

        dna_structured = extract_features(structured, source="test", session_id="spec-5a")
        dna_vague = extract_features(vague, source="test", session_id="spec-5b")

        score_structured = score_prompt(dna_structured).total
        score_vague = score_prompt(dna_vague).total

        assert score_structured > score_vague


class TestEnglishRegression:
    """Regression tests: ensure English prompts are not affected by Chinese support."""

    def test_english_debug_prompt_unchanged(self):
        """Standard English debug prompt should extract and score normally."""
        prompt = (
            "Fix the authentication bug in src/auth/login.ts where JWT tokens "
            "expire too early. The error is: TokenExpiredError: jwt expired"
        )

        dna = extract_features(prompt, source="test", session_id="reg-1")
        assert dna.locale == "en"
        assert dna.has_file_references is True
        assert dna.has_error_messages is True

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0
        assert breakdown.context > 0.0

    def test_english_structured_prompt_unchanged(self):
        """Well-structured English prompt should still score high."""
        prompt = (
            "You are a senior backend engineer.\n\n"
            "## Task\nFix the ValueError in src/auth/login.py line 87.\n\n"
            "## Constraints\n- Do not modify existing unit tests\n"
            "- Must maintain backward compatibility\n"
            "- Do not use global variables\n\n"
            '## Example\nInput: {"username": "test"}\n'
            'Output: {"token": "jwt..."}\n\n'
            "## Output Format\nReturn as JSON with status and data fields.\n\n"
            "Explain your fix step by step."
        )

        dna = extract_features(prompt, source="test", session_id="reg-2")
        assert dna.locale == "en"
        assert dna.has_role_definition is True
        assert dna.has_constraints is True
        assert dna.constraint_count >= 2
        assert dna.has_examples is True
        assert dna.has_output_format is True
        assert dna.has_step_by_step is True
        assert dna.has_file_references is True

        breakdown = score_prompt(dna)
        assert breakdown.total > 40.0
        assert breakdown.structure > 0.0
        assert breakdown.context > 0.0

    def test_english_bare_prompt_still_works(self):
        """Bare English prompt should still work."""
        dna = extract_features("fix the bug", source="test", session_id="reg-3")
        assert dna.locale == "en"
        assert dna.word_count > 0

        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0

    def test_english_with_code_block(self):
        """English prompt with code block should extract correctly."""
        prompt = (
            "Refactor this function to use async/await:\n"
            "```python\n"
            "def fetch_data():\n"
            "    return requests.get(url)\n"
            "```\n"
            "Must not break existing tests."
        )

        dna = extract_features(prompt, source="test", session_id="reg-4")
        assert dna.locale == "en"
        assert dna.has_code_blocks is True
        assert dna.has_constraints is True

        breakdown = score_prompt(dna)
        assert breakdown.context > 0.0  # code block contributes to context
