"""Input validation and safety guardrails."""

from __future__ import annotations

import re

BLOCKED_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"system\s+prompt",
    r"<\s*script",
    r"drop\s+table",
]


def validate_user_input(text: str, max_chars: int) -> tuple[bool, str]:
    cleaned = text.strip()
    if not cleaned:
        return False, "Input is empty. Please describe your PC needs."
    if len(cleaned) > max_chars:
        return False, f"Input exceeds limit of {max_chars} characters."
    lowered = cleaned.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, lowered):
            return False, "Input blocked by safety guardrail. Please rephrase your request."
    return True, cleaned


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
