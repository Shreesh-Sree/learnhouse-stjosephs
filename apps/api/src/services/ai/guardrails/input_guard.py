"""Inbound (User Input) Guardrail validator."""

import logging
from typing import Any, List, Optional

from src.services.ai.guardrails.rules import (
    HARMFUL_CONTENT_PATTERNS,
    MALICIOUS_INTENT_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    deobfuscate_leetspeak,
    normalize_text,
)
from src.services.ai.guardrails.types import (
    GuardrailResult,
    GuardrailVerdict,
    GuardrailViolationType,
)

logger = logging.getLogger(__name__)

DEFAULT_REFUSALS = {
    GuardrailViolationType.PROMPT_INJECTION: (
        "I am unable to process this request as it conflicts with the educational platform's "
        "instruction safety guidelines. Please feel free to ask questions about your course material or topics."
    ),
    GuardrailViolationType.MALICIOUS_INTENT: (
        "I cannot assist with requests involving exploits, malware, destructive actions, or unauthorized "
        "system access. I would be happy to explain defensive computing or programming concepts conceptually."
    ),
    GuardrailViolationType.HARMFUL_CONTENT: (
        "I cannot fulfill this request as it involves dangerous or harmful subject matter. "
        "Please ask a question related to your academic studies."
    ),
    GuardrailViolationType.ACADEMIC_INTEGRITY: (
        "I cannot assist with requests to bypass assessment security or proctoring environments. "
        "I am here to help you study and understand the course material."
    ),
    GuardrailViolationType.SENSITIVE_DATA_PII: (
        "I cannot process requests seeking internal credentials, system configurations, or private sensitive data."
    ),
}


def _extract_text_from_input(prompt: Any) -> str:
    """Extract plain text from string or multimodal prompt structures."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, (list, tuple)):
        extracted = []
        for item in prompt:
            if isinstance(item, str):
                extracted.append(item)
            elif hasattr(item, "content") and isinstance(item.content, str):
                extracted.append(item.content)
            elif isinstance(item, dict) and "content" in item:
                extracted.append(str(item["content"]))
        return " ".join(extracted)
    return str(prompt) if prompt else ""


def validate_input(
    prompt: Any,
    history: Optional[Any] = None,
    strict: bool = True,
) -> GuardrailResult:
    """Evaluate inbound user prompt and optional history for security/safety violations.

    Returns:
        GuardrailResult indicating PASSED or BLOCKED with detailed rationale.
    """
    raw_text = _extract_text_from_input(prompt)
    if not raw_text.strip():
        return GuardrailResult(
            passed=True,
            verdict=GuardrailVerdict.PASSED,
            sanitized_text="",
        )

    clean_text = normalize_text(raw_text)
    leetspeak_text = deobfuscate_leetspeak(clean_text)

    # 1. Check Prompt Injection & Jailbreak patterns
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(clean_text) or pattern.search(leetspeak_text)
        if match:
            matched_str = match.group(0)
            logger.warning("Input guardrail blocked prompt injection: pattern='%s' match='%s'", pattern.pattern, matched_str)
            return GuardrailResult(
                passed=False,
                verdict=GuardrailVerdict.BLOCKED,
                violation_type=GuardrailViolationType.PROMPT_INJECTION,
                reason=f"Prompt injection pattern detected: {matched_str[:40]}",
                refusal_message=DEFAULT_REFUSALS[GuardrailViolationType.PROMPT_INJECTION],
                matched_patterns=[pattern.pattern],
                metadata={"matched_text": matched_str},
            )

    # 2. Check Malicious Intent (Cyberattacks, SQLi, Exploit tools, SEB bypass, credential harvest)
    for pattern in MALICIOUS_INTENT_PATTERNS:
        match = pattern.search(clean_text) or pattern.search(leetspeak_text)
        if match:
            matched_str = match.group(0)
            logger.warning("Input guardrail blocked malicious intent: pattern='%s' match='%s'", pattern.pattern, matched_str)
            
            # Specific fine-grained categorization
            m_lower = matched_str.lower()
            if any(w in m_lower for w in ("exam", "seb", "proctoring")):
                v_type = GuardrailViolationType.ACADEMIC_INTEGRITY
            elif any(w in m_lower for w in ("password", "secret", "secret_key", "ssh_key", ".env")):
                v_type = GuardrailViolationType.SENSITIVE_DATA_PII
            else:
                v_type = GuardrailViolationType.MALICIOUS_INTENT

            return GuardrailResult(
                passed=False,
                verdict=GuardrailVerdict.BLOCKED,
                violation_type=v_type,
                reason=f"Malicious pattern detected: {matched_str[:40]}",
                refusal_message=DEFAULT_REFUSALS.get(v_type, DEFAULT_REFUSALS[GuardrailViolationType.MALICIOUS_INTENT]),
                matched_patterns=[pattern.pattern],
                metadata={"matched_text": matched_str},
            )

    # 3. Check Harmful Content (Weapons, self-harm)
    for pattern in HARMFUL_CONTENT_PATTERNS:
        match = pattern.search(clean_text) or pattern.search(leetspeak_text)
        if match:
            matched_str = match.group(0)
            logger.warning("Input guardrail blocked harmful content: pattern='%s'", pattern.pattern)
            return GuardrailResult(
                passed=False,
                verdict=GuardrailVerdict.BLOCKED,
                violation_type=GuardrailViolationType.HARMFUL_CONTENT,
                reason="Harmful or dangerous content pattern detected",
                refusal_message=DEFAULT_REFUSALS[GuardrailViolationType.HARMFUL_CONTENT],
                matched_patterns=[pattern.pattern],
                metadata={"matched_text": matched_str},
            )

    # Clean input
    return GuardrailResult(
        passed=True,
        verdict=GuardrailVerdict.PASSED,
        sanitized_text=raw_text,
    )
