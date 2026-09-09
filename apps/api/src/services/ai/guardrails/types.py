"""Types and data structures for the bi-directional AI guardrail system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GuardrailVerdict(str, Enum):
    """Outcome of guardrail evaluation."""
    PASSED = "passed"
    BLOCKED = "blocked"
    REDACTED = "redacted"
    FLAGGED = "flagged"


class GuardrailViolationType(str, Enum):
    """Categorization of detected violations."""
    PROMPT_INJECTION = "prompt_injection"
    SYSTEM_LEAK = "system_leak"
    MALICIOUS_INTENT = "malicious_intent"
    HARMFUL_CONTENT = "harmful_content"
    SENSITIVE_DATA_PII = "sensitive_data_pii"
    ACADEMIC_INTEGRITY = "academic_integrity"
    POLICY_VIOLATION = "policy_violation"


@dataclass
class GuardrailResult:
    """Result of an input or output guardrail evaluation."""
    passed: bool
    verdict: GuardrailVerdict
    violation_type: Optional[GuardrailViolationType] = None
    reason: Optional[str] = None
    sanitized_text: str = ""
    refusal_message: str = ""
    confidence: float = 1.0
    matched_patterns: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
