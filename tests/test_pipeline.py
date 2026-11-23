"""Tests for the quality gate and extraction pipeline."""



from signal_miner.pipeline.prompts import build_extraction_prompt, build_quality_gate_prompt
from signal_miner.pipeline.utils import strip_code_fences


class TestPrompts:
    def test_quality_gate_prompt(self):
        prompt = build_quality_gate_prompt(source_type="manual", text="I want dark mode")
        assert "product feedback classifier" in prompt
        assert "I want dark mode" in prompt
        assert "manual" in prompt

    def test_extraction_prompt(self):
        prompt = build_extraction_prompt(
            source_type="csv",
            subject="Bug report",
            text="The export button doesn't work",
            context={"source": "test"},
            max_signals=5,
            confidence_threshold=0.5,
        )
        assert "extracting product-feedback signals" in prompt
        assert "The export button doesn't work" in prompt
        assert "Bug report" in prompt

    def test_extraction_prompt_truncation(self):
        """Test that very long text is truncated."""
        long_text = "x" * 10000
        prompt = build_extraction_prompt(
            source_type="test",
            subject="",
            text=long_text,
            context={},
        )
        assert len(prompt) < len(long_text)


class TestStripCodeFences:
    def test_strip_json_fence(self):
        text = '```json\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_strip_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_no_fence(self):
        text = '{"key": "value"}'
        assert strip_code_fences(text) == '{"key": "value"}'

    def test_with_whitespace(self):
        text = '  ```json\n{"key": "value"}\n```  '
        result = strip_code_fences(text)
        assert result == '{"key": "value"}'
