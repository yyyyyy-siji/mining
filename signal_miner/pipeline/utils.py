"""Pipeline utility functions."""

import re


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from LLM response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()
