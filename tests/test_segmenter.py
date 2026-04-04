"""Tests for prompt segmentation."""

from __future__ import annotations

from ctxray.core.segmenter import segment_prompt


class TestSegmentPrompt:
    """Test three-pass prompt segmentation."""

    def test_simple_instruction(self):
        result = segment_prompt("Fix the bug in auth.py")
        assert len(result) == 1
        assert result[0].segment_type == "instruction"

    def test_role_plus_instruction(self):
        text = "You are a senior Python engineer.\n\nFix the bug in auth.py"
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "system_role" in types
        assert "instruction" in types

    def test_instruction_with_code_block(self):
        text = """Fix the TypeError in this function:

```python
def process(data):
    return data.strip()
```"""
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "instruction" in types
        assert "context" in types

    def test_constraints_detected(self):
        text = "Add a login endpoint. Do not modify the existing routes. Must return 201."
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "constraint" in types

    def test_output_format_detected(self):
        text = "List all API endpoints. Return as JSON with fields: path, method, description."
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "output_format" in types

    def test_example_detected(self):
        text = """Convert dates to ISO format.

Example:
Input: "March 5, 2026"
Output: "2026-03-05"
"""
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "example" in types

    def test_empty_prompt(self):
        result = segment_prompt("")
        assert result == []

    def test_multiline_context_block(self):
        text = """Debug the auth failure.

The error is:
```
Traceback (most recent call last):
  File "auth.py", line 42, in validate
    raise TokenExpired()
TokenExpired: token has expired
```

The token should be refreshed automatically."""
        result = segment_prompt(text)
        types = [s.segment_type for s in result]
        assert "instruction" in types
        assert "context" in types

    def test_segment_has_text_and_position(self):
        text = "You are an expert.\n\nFix the bug."
        result = segment_prompt(text)
        for seg in result:
            assert isinstance(seg.text, str)
            assert len(seg.text) > 0
            assert 0.0 <= seg.start_pos <= 1.0
            assert 0.0 <= seg.end_pos <= 1.0
            assert seg.start_pos <= seg.end_pos
