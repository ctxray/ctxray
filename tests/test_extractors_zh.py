# tests/test_extractors_zh.py
"""Tests for Chinese feature extraction."""

from __future__ import annotations

from reprompt.core.extractors_zh import extract_features_zh


class TestChineseBasicMetrics:
    """Test basic counting features for Chinese text."""

    def test_line_count(self):
        dna = extract_features_zh(
            "修复认证模块的错误\n确保测试通过", source="test", session_id="s1"
        )
        assert dna.line_count == 2

    def test_sentence_count_chinese_punctuation(self):
        dna = extract_features_zh(
            "修复错误。添加测试。部署到生产环境。",
            source="test",
            session_id="s1",
        )
        assert dna.sentence_count == 3

    def test_sentence_count_mixed_punctuation(self):
        dna = extract_features_zh(
            "修复错误！为什么不工作？请检查日志。",
            source="test",
            session_id="s1",
        )
        assert dna.sentence_count == 3

    def test_word_count_with_jieba(self):
        """Word count should use jieba segmentation when available."""
        dna = extract_features_zh("修复认证模块中的错误", source="test", session_id="s1")
        assert dna.word_count > 0

    def test_empty_prompt(self):
        dna = extract_features_zh("", source="test", session_id="s1")
        assert dna.word_count == 0
        assert dna.locale == "zh"

    def test_locale_is_zh(self):
        dna = extract_features_zh("修复认证模块的错误", source="test", session_id="s1")
        assert dna.locale == "zh"


class TestChineseStructureDetection:
    """Test Chinese prompt structure feature extraction."""

    def test_role_definition_ni_shi(self):
        dna = extract_features_zh(
            "你是一个资深Python开发者。\n\n修复认证模块的错误。",
            source="test",
            session_id="s1",
        )
        assert dna.has_role_definition is True

    def test_role_definition_zuowei(self):
        dna = extract_features_zh(
            "作为数据库专家，请优化这条查询。",
            source="test",
            session_id="s1",
        )
        assert dna.has_role_definition is True

    def test_role_definition_banyan(self):
        dna = extract_features_zh(
            "扮演一个产品经理，帮我分析需求。",
            source="test",
            session_id="s1",
        )
        assert dna.has_role_definition is True

    def test_role_definition_absent(self):
        dna = extract_features_zh("修复这个错误", source="test", session_id="s1")
        assert dna.has_role_definition is False

    def test_constraints_detected(self):
        dna = extract_features_zh(
            "添加登录接口。不要修改现有路由。必须返回201状态码。禁止使用全局变量。",
            source="test",
            session_id="s1",
        )
        assert dna.has_constraints is True
        assert dna.constraint_count >= 3

    def test_constraints_bixu(self):
        dna = extract_features_zh("必须保证向后兼容", source="test", session_id="s1")
        assert dna.has_constraints is True

    def test_constraints_qingwu(self):
        dna = extract_features_zh("请勿删除任何现有文件", source="test", session_id="s1")
        assert dna.has_constraints is True

    def test_examples_detected_liru(self):
        dna = extract_features_zh(
            "转换日期格式。例如：输入：三月五日，输出：2026-03-05",
            source="test",
            session_id="s1",
        )
        assert dna.has_examples is True

    def test_examples_detected_biru(self):
        dna = extract_features_zh(
            "列出所有API端点，比如GET /users、POST /auth这样的。",
            source="test",
            session_id="s1",
        )
        assert dna.has_examples is True

    def test_output_format_json(self):
        dna = extract_features_zh(
            "列出所有端点。输出为JSON格式，包含path和method字段。",
            source="test",
            session_id="s1",
        )
        assert dna.has_output_format is True

    def test_output_format_table(self):
        dna = extract_features_zh(
            "查询结果以表格格式返回。",
            source="test",
            session_id="s1",
        )
        assert dna.has_output_format is True

    def test_step_by_step_fenbuzhou(self):
        dna = extract_features_zh(
            "请分步骤说明如何部署这个服务。",
            source="test",
            session_id="s1",
        )
        assert dna.has_step_by_step is True

    def test_step_by_step_ordered(self):
        dna = extract_features_zh(
            "第一步：安装依赖。第二步：配置环境。第三步：运行测试。",
            source="test",
            session_id="s1",
        )
        assert dna.has_step_by_step is True

    def test_step_by_step_xian_ranhou(self):
        dna = extract_features_zh(
            "先备份数据库，然后执行迁移，最后验证数据完整性。",
            source="test",
            session_id="s1",
        )
        assert dna.has_step_by_step is True

    def test_section_detection_chinese_numbering(self):
        text = "一、需求分析\n内容\n\n二、技术方案\n内容\n\n三、测试计划\n内容"
        dna = extract_features_zh(text, source="test", session_id="s1")
        assert dna.section_count >= 3

    def test_section_detection_markdown(self):
        text = "# 概述\n内容\n\n## 详情\n内容"
        dna = extract_features_zh(text, source="test", session_id="s1")
        assert dna.section_count >= 2


class TestChineseContextDensity:
    """Test context density features work with Chinese text."""

    def test_code_blocks_detected(self):
        text = "修复这个函数\n```python\ndef foo():\n    pass\n```"
        dna = extract_features_zh(text, source="test", session_id="s1")
        assert dna.has_code_blocks is True
        assert dna.code_block_count == 1

    def test_file_references(self):
        dna = extract_features_zh(
            "修复 src/auth.py 中第42行的错误",
            source="test",
            session_id="s1",
        )
        assert dna.has_file_references is True

    def test_error_messages_english_in_chinese(self):
        dna = extract_features_zh(
            "运行时报错：TypeError: cannot unpack",
            source="test",
            session_id="s1",
        )
        assert dna.has_error_messages is True

    def test_error_messages_chinese_keywords(self):
        dna = extract_features_zh(
            "这个函数执行失败，抛出异常",
            source="test",
            session_id="s1",
        )
        assert dna.has_error_messages is True


class TestChineseAmbiguity:
    """Test ambiguity detection for Chinese vague words."""

    def test_vague_words_detected(self):
        dna = extract_features_zh(
            "帮我改一下那个东西",
            source="test",
            session_id="s1",
        )
        assert dna.ambiguity_score > 0.0

    def test_specific_prompt_low_ambiguity(self):
        dna = extract_features_zh(
            "修复 src/auth.py 第42行的 TypeError，不要修改测试文件",
            source="test",
            session_id="s1",
        )
        dna_vague = extract_features_zh(
            "帮我改一下那个东西",
            source="test",
            session_id="s1",
        )
        assert dna.ambiguity_score < dna_vague.ambiguity_score


class TestChinesePromptDNAShape:
    """Ensure Chinese extraction produces same PromptDNA shape as English."""

    def test_feature_vector_same_length(self):
        from reprompt.core.extractors import extract_features

        en_dna = extract_features("Fix the bug in auth.py", source="test", session_id="s1")
        zh_dna = extract_features_zh("修复 auth.py 中的错误", source="test", session_id="s1")
        assert len(en_dna.feature_vector()) == len(zh_dna.feature_vector())

    def test_all_fields_populated(self):
        dna = extract_features_zh(
            "你是一个资深开发者。\n修复认证模块的错误。不要修改测试。\n"
            "例如：输入用户名，输出token。\n以JSON格式返回。",
            source="test",
            session_id="s1",
        )
        assert dna.prompt_hash != ""
        assert dna.task_type != ""
        assert dna.locale == "zh"
        assert dna.word_count > 0
        assert dna.sentence_count > 0

    def test_to_dict_roundtrip(self):
        from reprompt.core.prompt_dna import PromptDNA

        dna = extract_features_zh("修复认证模块中的错误", source="test", session_id="s1")
        d = dna.to_dict()
        dna2 = PromptDNA(**d)
        assert dna2.locale == "zh"
        assert dna2.word_count == dna.word_count


class TestChineseOpeningQuality:
    """Test opening quality scoring for Chinese prompts."""

    def test_action_verb_opening(self):
        dna = extract_features_zh(
            "修复认证模块中第42行的TypeError错误",
            source="test",
            session_id="s1",
        )
        assert dna.opening_quality > 0.0

    def test_weak_opening(self):
        dna = extract_features_zh(
            "嗯。。。",
            source="test",
            session_id="s1",
        )
        assert dna.opening_quality == 0.0


class TestChineseComplexity:
    """Test complexity scoring for Chinese prompts."""

    def test_simple_prompt(self):
        dna = extract_features_zh("修复错误", source="test", session_id="s1")
        assert dna.complexity_score < 0.5

    def test_complex_prompt(self):
        text = (
            "# 需求\n"
            "重构整个认证模块。不要破坏现有API。必须支持OAuth2.0。\n\n"
            "# 约束\n"
            "不能修改数据库表结构。必须保持向后兼容。\n\n"
            "# 步骤\n"
            "第一步：分析现有代码。第二步：设计新架构。"
            "第三步：实施迁移。第四步：编写测试。第五步：部署。\n\n"
            "```python\nclass Auth:\n    def login(self):\n        pass\n```\n"
        )
        dna = extract_features_zh(text, source="test", session_id="s1")
        assert dna.complexity_score > 0.3


class TestChineseRepetition:
    """Test keyword repetition detection for Chinese text."""

    def test_no_repetition(self):
        dna = extract_features_zh("修复错误", source="test", session_id="s1")
        assert dna.keyword_repetition_freq == 0.0

    def test_with_repetition(self):
        dna = extract_features_zh(
            "修复认证模块的错误。认证模块需要重构。认证模块的测试也要更新。",
            source="test",
            session_id="s1",
        )
        assert dna.keyword_repetition_freq > 0.0


class TestChineseSpecificity:
    """Test context specificity for Chinese prompts."""

    def test_specific_with_code(self):
        text = "修复这个函数\n```python\ndef foo():\n    pass\n```"
        dna = extract_features_zh(text, source="test", session_id="s1")
        assert dna.context_specificity > 0.0

    def test_vague_prompt_low_specificity(self):
        dna = extract_features_zh("改一下", source="test", session_id="s1")
        assert dna.context_specificity == 0.0


class TestChineseScoring:
    """Verify the scorer works correctly with Chinese PromptDNA."""

    def test_chinese_prompt_scores(self):
        """A well-structured Chinese prompt should produce valid scores."""
        from reprompt.core.scorer import score_prompt

        dna = extract_features_zh(
            "你是一个资深Python开发者。\n"
            "修复 auth.py 中第42行的 TypeError。\n"
            "不要修改测试文件。必须保持向后兼容。\n"
            "例如：输入用户名，输出JWT token。\n"
            "以JSON格式返回结果。",
            source="test",
            session_id="s1",
        )
        breakdown = score_prompt(dna)
        assert 0.0 <= breakdown.total <= 100.0
        assert breakdown.structure > 0.0  # has role, constraints, examples, output format
        assert breakdown.context > 0.0  # has file refs, error type

    def test_bare_chinese_prompt_low_score(self):
        """A vague Chinese prompt should score low."""
        from reprompt.core.scorer import score_prompt

        dna = extract_features_zh(
            "帮我改一下那个东西",
            source="test",
            session_id="s1",
        )
        breakdown = score_prompt(dna)
        assert breakdown.total < 50.0  # vague prompt should score low

    def test_structured_chinese_prompt_high_score(self):
        """A richly structured Chinese prompt should score high."""
        from reprompt.core.scorer import score_prompt

        dna = extract_features_zh(
            "你是一个资深后端工程师。\n\n"
            "## 任务\n修复 src/auth/login.py 第87行的 ValueError。\n\n"
            "## 约束\n- 不要修改现有的单元测试\n- 必须保持API向后兼容\n- 禁止使用全局变量\n\n"
            '## 示例\n输入：{"username": "test"}\n输出：{"token": "jwt..."}\n\n'
            "## 输出格式\n以JSON格式返回，包含status和data字段。\n\n"
            "请分步骤说明修复方案。",
            source="test",
            session_id="s1",
        )
        breakdown = score_prompt(dna)
        assert breakdown.total > 40.0  # well-structured -> higher score

    def test_score_breakdown_has_suggestions(self):
        """A bare Chinese prompt should receive improvement suggestions."""
        from reprompt.core.scorer import score_prompt

        dna = extract_features_zh("改一下代码", source="test", session_id="s1")
        breakdown = score_prompt(dna)
        assert len(breakdown.suggestions) > 0  # should suggest improvements

    def test_score_specific_chinese_prompts_from_spec(self):
        """Score the specific Chinese test prompts from the task spec."""
        from reprompt.core.scorer import score_prompt

        # Complex refactoring prompt with role + constraints + output format
        dna1 = extract_features_zh(
            "你是一个资深Python开发者。重构数据库模块使用async/await。"
            "必须保持向后兼容。输出为diff格式。",
            source="test",
            session_id="s1",
        )
        b1 = score_prompt(dna1)
        assert 0.0 <= b1.total <= 100.0
        assert b1.structure > 0.0  # role + constraints + output format

        # Debug prompt with file reference
        dna2 = extract_features_zh(
            "修复src/auth/login.ts中JWT token过期的认证bug",
            source="test",
            session_id="s1",
        )
        b2 = score_prompt(dna2)
        assert 0.0 <= b2.total <= 100.0
        assert b2.context > 0.0  # file reference

        # Bare question (vague)
        dna3 = extract_features_zh(
            "这段代码是做什么的",
            source="test",
            session_id="s1",
        )
        b3 = score_prompt(dna3)
        assert 0.0 <= b3.total <= 100.0
        assert b3.total < b1.total  # vague should score lower than structured

        # DevOps prompt with role + constraints + structured requirements
        dna4 = extract_features_zh(
            "作为DevOps工程师，写一个Python FastAPI应用的Dockerfile。"
            "要求：多阶段构建，非root用户，健康检查端点。",
            source="test",
            session_id="s1",
        )
        b4 = score_prompt(dna4)
        assert 0.0 <= b4.total <= 100.0
        assert b4.structure > 0.0  # role + constraints
