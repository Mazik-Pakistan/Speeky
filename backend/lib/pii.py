"""
Shared PII detection/redaction. Originally lived only in resume_jd_service;
reused as-is by conversation_service for (PII safety during chat) since the
patterns and "redact before it ever reaches an LLM or storage" rule are identical.
"""

import re
from typing import List, Tuple

SENSITIVE_PATTERNS = {
    "phone_number": re.compile(r"(\+?\d{1,3}[\s-]?)?\(?\d{3,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
    "cnic_or_ssn": re.compile(r"\b\d{3,5}-\d{6,7}-\d{1}\b|\b\d{3}-\d{2}-\d{4}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "card_number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
}
ADDRESS_LINE_MARKERS = ["address:", "street", "apt.", "apartment", "zip code", "postal code"]


def redact(text: str) -> Tuple[str, List[str]]:
    """Strip phone/CNIC/SSN/email/card-number + address-labeled lines.

    Returns (redacted_text, list_of_types_redacted). Conservative by design —
    over-redacting is safer than leaking PII into an LLM prompt or transcript.
    """
    redacted_types: List[str] = []
    result = text
    for label, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(result):
            redacted_types.append(label)
            result = pattern.sub("[REDACTED]", result)

    cleaned_lines = []
    address_found = False
    for line in result.split("\n"):
        if any(marker in line.lower() for marker in ADDRESS_LINE_MARKERS):
            address_found = True
            continue
        cleaned_lines.append(line)
    if address_found:
        redacted_types.append("address")
    return "\n".join(cleaned_lines), redacted_types
