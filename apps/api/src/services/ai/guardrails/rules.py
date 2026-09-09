"""Detection rules, patterns, and normalization for bi-directional guardrails."""

import re
import unicodedata
from typing import List, Optional, Tuple
from src.services.ai.guardrails.types import GuardrailViolationType

# Leetspeak / common obfuscation character map
LEET_MAP = {
    '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't',
    '@': 'a', '$': 's', '!': 'i', '+': 't', '|': 'i', '8': 'b',
}

def normalize_text(text: str) -> str:
    """Normalize text to defeat unicode, whitespace, and zero-width obfuscation."""
    if not text:
        return ""
    # NFKD normalization decomposes accents and unusual Unicode variants
    normalized = unicodedata.normalize('NFKD', text)
    # Strip non-printable and zero-width characters
    cleaned = re.sub(r'[\u200b-\u200f\ufeff\u202a-\u202e\u2060-\u206f]', '', normalized)
    # Normalize multiple whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def deobfuscate_leetspeak(text: str) -> str:
    """Translate basic leetspeak patterns to standard ascii characters for heuristic scanning."""
    chars = [LEET_MAP.get(c, c) for c in text.lower()]
    return "".join(chars)

# ==============================================================================
# INBOUND / INPUT GUARD PATTERNS
# ==============================================================================

PROMPT_INJECTION_PATTERNS = [
    # Direct instruction override
    re.compile(r'\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|former|initial|system)\s+(?:instructions|rules|prompts|directions|guidelines|constraints)\b', re.IGNORECASE),
    re.compile(r'\bdo\s+not\s+follow\s+(?:any\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts)\b', re.IGNORECASE),
    re.compile(r'\b(?:new|updated)\s+(?:instructions|rules|system\s+prompt)\s+(?:start|begin|takes?\s+precedence)\b', re.IGNORECASE),
    re.compile(r'\b(?:from\s+now\s+on|henceforth)[,\s]+(?:ignore|disregard|forget)\b', re.IGNORECASE),
    
    # Jailbreak modes & Persona escape
    re.compile(r'\b(?:developer|dan|jailbreak|unrestricted|unfiltered|god|anarchy)\s+mode\b', re.IGNORECASE),
    re.compile(r'\bpretend\s+(?:you\s+are|to\s+be)\s+(?:an?\s+)?(?:unrestricted|evil|jailbroken|unfiltered|ruleless|dan)\b', re.IGNORECASE),
    re.compile(r'\bact\s+as\s+(?:an?\s+)?(?:unfiltered|unrestricted|jailbroken|evil|dan)\b', re.IGNORECASE),
    re.compile(r'\bdo\s+anything\s+now\b', re.IGNORECASE),
    re.compile(r'\bbypass\s+(?:all\s+)?(?:content\s+filters|safety\s+filters|guardrails|safety\s+checks|censorship)\b', re.IGNORECASE),
    re.compile(r'\b(?:ignore|bypass|disregard)\s+(?:all\s+)?(?:(?:ethical|safety|legal|moral)\s*(?:and|,)?\s*)+(?:constraints|guidelines|rules|policies|filters)\b', re.IGNORECASE),

    # System prompt / instructions extraction
    re.compile(r'\b(?:reveal|show|display|print|output|tell\s+me|repeat|echo|dump)\s+(?:your\s+|the\s+)?(?:complete\s+|full\s+|verbatim\s+|exact\s+)?(?:system\s+prompt|initial\s+prompt|hidden\s+instructions|internal\s+instructions|developer\s+prompt|system\s+instructions|base\s+instructions)\b', re.IGNORECASE),
    re.compile(r'\bwhat\s+(?:are|were)\s+(?:your|the)\s+(?:(?:initial|system|internal|hidden|original|base)\s+)*(?:instructions|prompts|rules|guidelines)\b', re.IGNORECASE),

    # Delimiter / Structural token injection
    re.compile(r'(?:\[SYSTEM\]|<<<SYSTEM>>>|<\|im_start\|>|<\|im_end\|>|<\|system\|>|BEGIN\s+INSTRUCTION\s+OVERRIDE|\[INST\]|\[/INST\])', re.IGNORECASE),

    # Obfuscated payload execution instructions
    re.compile(r'\b(?:base64\s+decode\s+and\s+(?:run|execute|follow|print|eval)|execute\s+(?:the\s+following\s+)?encoded\s+payload)\b', re.IGNORECASE),
]

MALICIOUS_INTENT_PATTERNS = [
    # Cyberattacks, malware, exploits
    re.compile(r'\b(?:write|create|generate|develop|code)\s+(?:an?\s+)?(?:keylogger|ransomware|trojan|rootkit|ddos\s+tool|botnet|reverse\s+shell|exploit\s+payload|zero-day\s+exploit)\b', re.IGNORECASE),
    re.compile(r'\b(?:bash|sh|zsh)\s+-i\s+>&?\s*/dev/tcp/', re.IGNORECASE),
    re.compile(r'\bnc\s+(?:-e|-c)\s*/bin/(?:bash|sh)\b', re.IGNORECASE),
    re.compile(r'\brm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\s+(?:/|/\*|~)(?:\s+|$)', re.IGNORECASE),
    re.compile(r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:', re.IGNORECASE),
    re.compile(r'\bmkfs\.(?:ext[234]|xfs|ntfs|vfat)\s+/dev/[a-z0-9]+\b', re.IGNORECASE),
    
    # Platform attacks & SQL injection attempts
    re.compile(r'\b(?:UNION\s+SELECT\s+(?:ALL\s+)?(?:NULL|[0-9]+|\*)|;\s*DROP\s+TABLE|;\s*DROP\s+DATABASE|OR\s+1\s*=\s*1\s*--|xp_cmdshell)\b', re.IGNORECASE),
    re.compile(r'\bhow\s+to\s+(?:hack|exploit|penetrate|attack)\s+(?:this\s+(?:server|lms|website|database)|other\s+students)\b', re.IGNORECASE),

    # Sensitive infrastructure & credentials probing
    re.compile(r'\b(?:show|give|extract|leak|find)\s+(?:me\s+)?(?:the\s+)?(?:database\s+password|jwt\s+secret|secret\s+key|\.env\s+file|server\s+ssh\s+key|root\s+password)\b', re.IGNORECASE),
    re.compile(r'\b(?:LEARNHOUSE_AUTH_JWT_SECRET_KEY|CLICKHOUSE_PASSWORD|POSTGRES_PASSWORD|DATABASE_URL)\b', re.IGNORECASE),
    re.compile(r'\b(?:show|view|dump|print)\s+(?:the\s+)?\.env\b', re.IGNORECASE),

    # Exam security circumvention (Academic Integrity)
    re.compile(r'\b(?:how\s+to\s+)?(?:bypass|circumvent|cheat|hack|disable)\s+(?:safe\s+exam\s+browser|seb|exam\s+lock|proctoring)\b', re.IGNORECASE),
]

HARMFUL_CONTENT_PATTERNS = [
    # Weapons, explosives, violence
    re.compile(r'\b(?:how\s+to\s+(?:make|build|construct|synthesize)\s+(?:a\s+)?(?:bomb|explosive|ied|molotov|nerve\s+agent|bioweapon|chemical\s+weapon))\b', re.IGNORECASE),
    # Self-harm
    re.compile(r'\b(?:how\s+to\s+(?:kill|hang|poison|harm)\s+(?:myself|yourself)|suicide\s+methods|easy\s+ways\s+to\s+die)\b', re.IGNORECASE),
]

# ==============================================================================
# OUTBOUND / OUTPUT GUARD PATTERNS (LEAK & SENSITIVE DATA REDACTION)
# ==============================================================================

SENSITIVE_LEAK_PATTERNS = [
    # Private Keys
    (re.compile(r'-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(?:RSA\s+|EC\s+|DSA\s+|OPENSSH\s+)?PRIVATE\s+KEY-----', re.IGNORECASE), "[REDACTED_PRIVATE_KEY]"),
    # JWT Tokens
    (re.compile(r'\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b'), "[REDACTED_JWT_TOKEN]"),
    # Database Connection Strings with passwords
    (re.compile(r'(?:postgresql|postgres|redis|mysql|mongodb):\/\/[^:\s\/]+:[^@\s\/]+@[^\s\/]+(?:\/[^\s]*)?', re.IGNORECASE), "[REDACTED_DATABASE_CONNECTION_URI]"),
    # Environment variable assignments with secrets
    (re.compile(r'(?:LEARNHOUSE_[A-Z0-9_]*SECRET[A-Z0-9_]*|CLICKHOUSE_PASSWORD|POSTGRES_PASSWORD|REDIS_PASSWORD|COLLAB_INTERNAL_KEY|JWT_SECRET)\s*=\s*[^\s\n]+', re.IGNORECASE), "[REDACTED_CONFIG_SECRET]"),
    # Social Security Numbers (US)
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[REDACTED_SSN]"),
    # Generic API Keys (e.g. Bearer tokens, OpenAI-like keys, vLLM keys)
    (re.compile(r'\b(?:Bearer\s+[a-zA-Z0-9_\-\.]{25,}|sk-[a-zA-Z0-9]{20,})\b', re.IGNORECASE), "[REDACTED_API_TOKEN]"),
]

def luhn_checksum_valid(card_number_str: str) -> bool:
    """Validate a credit card number string using Luhn algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) not in (13, 14, 15, 16, 19):
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = d * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += d
    return checksum % 10 == 0

CREDIT_CARD_REGEX = re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b')

def redact_credit_cards(text: str) -> Tuple[str, bool]:
    """Identify and redact real credit card numbers using regex and Luhn algorithm."""
    has_card = False
    def _replace(match):
        nonlocal has_card
        raw = match.group(0)
        digits_only = re.sub(r'\D', '', raw)
        if luhn_checksum_valid(digits_only):
            has_card = True
            return "[REDACTED_CREDIT_CARD]"
        return raw

    redacted = CREDIT_CARD_REGEX.sub(_replace, text)
    return redacted, has_card
