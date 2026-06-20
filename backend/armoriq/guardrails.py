"""
ArmorIQ Output Guardrails

Validates that an LLM response is a genuine phishing analysis and not
injected content, refusals, or off-topic text.

Security design decisions:
  1. Keyword allowlist (not blocklist) — we check for expected analysis
     vocabulary; anything that lacks it is treated as off-topic.  A pure
     blocklist can always be evaded by synonyms.
  2. Maximum output length cap — prevents the LLM from being coerced into
     generating large volumes of content (e.g. a data-exfiltration dump
     disguised as an "explanation").
  3. Persona-break detection — checks if the output contains text that
     suggests the LLM abandoned its assigned role ("As an AI…", "I am
     now DAN…").
  4. Structured JSON-field validation — if the router expects a JSON
     response, guardrails verify required keys are present and of the
     correct types before the response reaches the client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Limits ────────────────────────────────────────────────────────────────────
MAX_OUTPUT_CHARS = 8_000

# ── Expected phishing-analysis vocabulary ─────────────────────────────────────
# The LLM response must contain at least MIN_KEYWORD_HITS of these terms.
_EXPECTED_KEYWORDS: list[str] = [
    "phish", "spam", "scam", "suspicious", "safe", "legit", "malicious",
    "url", "link", "domain", "sender", "urgent", "click", "verify",
    "credential", "bank", "otp", "reward", "winner", "account",
    # Hindi transliterations (common in Groq's bilingual responses)
    "नकली", "धोखा", "सुरक्षित", "फ़िशिंग",
]
_KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(k) for k in _EXPECTED_KEYWORDS),
    re.IGNORECASE,
)
MIN_KEYWORD_HITS = 1   # at least one domain-relevant term

# ── Persona-break / jailbreak output patterns ─────────────────────────────────
_PERSONA_BREAK_PATTERNS = re.compile(
    r"(as\s+(an?\s+)?ai\s+(language\s+)?model"
    r"|i\s+(am|have\s+become)\s+(now\s+)?dan"
    r"|i\s+have\s+no\s+(restrictions|limitations)"
    r"|i\s+will\s+ignore\s+(my\s+)?(guidelines|rules)"
    r"|new\s+persona"
    r"|forget\s+everything)",
    re.IGNORECASE | re.DOTALL,
)

# ── Required JSON keys for structured responses ───────────────────────────────
_REQUIRED_ANALYSIS_KEYS: set[str] = {"verdict", "risk_score", "explanation"}


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    is_valid: bool
    reasons: list[str] = field(default_factory=list)
    sanitised_output: str = ""


# ── Guard functions ───────────────────────────────────────────────────────────

def validate_llm_output(raw_output: str) -> GuardrailResult:
    """
    Validates a raw LLM text response for on-topic content and absence of
    persona-break / injection payloads.

    Args:
        raw_output: The raw string returned by the LLM API.

    Returns:
        GuardrailResult with is_valid=False and reasons if validation fails.
        On success, sanitised_output contains the (possibly truncated) text.
    """
    reasons: list[str] = []

    # ── 1. Empty response ─────────────────────────────────────────────────────
    if not raw_output or not raw_output.strip():
        return GuardrailResult(
            is_valid=False,
            reasons=["LLM returned an empty response."],
            sanitised_output="",
        )

    # ── 2. Length cap ─────────────────────────────────────────────────────────
    output = raw_output[:MAX_OUTPUT_CHARS]
    if len(raw_output) > MAX_OUTPUT_CHARS:
        reasons.append(
            f"Response truncated from {len(raw_output)} to {MAX_OUTPUT_CHARS} chars."
        )

    # ── 3. Persona-break detection ────────────────────────────────────────────
    match = _PERSONA_BREAK_PATTERNS.search(output)
    if match:
        return GuardrailResult(
            is_valid=False,
            reasons=[f"Persona-break detected in LLM output: '{match.group()[:80]}'"],
            sanitised_output="",
        )

    # ── 4. On-topic keyword check ─────────────────────────────────────────────
    hits = _KEYWORD_PATTERN.findall(output)
    if len(hits) < MIN_KEYWORD_HITS:
        return GuardrailResult(
            is_valid=False,
            reasons=[
                f"LLM output appears off-topic: no phishing-analysis vocabulary found. "
                f"(got {len(hits)} keyword hits, need ≥ {MIN_KEYWORD_HITS})"
            ],
            sanitised_output="",
        )

    return GuardrailResult(is_valid=True, reasons=reasons, sanitised_output=output.strip())


def validate_analysis_json(data: dict) -> GuardrailResult:
    """
    Validates a structured JSON analysis response for required fields and
    sane value ranges.

    Args:
        data: Parsed dict from the LLM JSON response.

    Returns:
        GuardrailResult indicating whether the structure is valid.
    """
    reasons: list[str] = []

    # ── Required keys ─────────────────────────────────────────────────────────
    missing = _REQUIRED_ANALYSIS_KEYS - set(data.keys())
    if missing:
        return GuardrailResult(
            is_valid=False,
            reasons=[f"LLM response missing required keys: {sorted(missing)}"],
        )

    # ── verdict must be one of three known values ─────────────────────────────
    verdict = data.get("verdict", "")
    if verdict not in ("SAFE", "SUSPICIOUS", "PHISHING"):
        return GuardrailResult(
            is_valid=False,
            reasons=[f"Invalid verdict value: '{verdict}'. Expected SAFE|SUSPICIOUS|PHISHING."],
        )

    # ── risk_score must be numeric 0–100 ──────────────────────────────────────
    risk_score = data.get("risk_score")
    try:
        score = float(risk_score)  # type: ignore[arg-type]
        if not (0.0 <= score <= 100.0):
            raise ValueError
    except (TypeError, ValueError):
        return GuardrailResult(
            is_valid=False,
            reasons=[f"Invalid risk_score: '{risk_score}'. Expected float 0–100."],
        )

    # ── explanation must be a non-empty string ────────────────────────────────
    explanation = data.get("explanation", "")
    if not isinstance(explanation, str) or len(explanation.strip()) < 10:
        reasons.append("Explanation is missing or too short (< 10 chars).")

    return GuardrailResult(is_valid=len(reasons) == 0, reasons=reasons)
