"""
ArmorIQ Intent Verifier

Detects whether user input looks like a legitimate phishing-analysis
request or an adversarial attempt to manipulate the AI.

Security design decisions:
  1. Regex-based detection instead of a secondary LLM call — a classifier
     that calls an LLM to protect another LLM is a TOCTOU race; regex is
     synchronous, deterministic and zero-cost at inference time.
  2. Patterns are compiled at module load time (not per-request) so there
     is zero regex compilation overhead on the hot path.
  3. Oversized input is rejected *before* tokenisation — this prevents
     prompt-stuffing attacks that try to push system instructions off the
     context window.
  4. Code injection patterns (shell metacharacters, eval, exec) are flagged
     because some LLM APIs execute tool-call code in a sandbox; blocking
     these inputs at ingress is a defence-in-depth measure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar


# ── Limits ────────────────────────────────────────────────────────────────────

MAX_INPUT_CHARS = 4_000  # ~1 000 tokens; well within Groq context window
MAX_URL_LENGTH  = 2_048  # RFC 2616 practical limit


# ── Injection / manipulation patterns ────────────────────────────────────────
# Each pattern is compiled case-insensitively.  We use a flat list so a
# single re.search() scan over the combined pattern is O(n) in text length.

_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"\bsystem\s*:",                     # raw system-prompt delimiter
    r"\[INST\]",                         # Llama instruction marker
    r"\bact\s+as\b",
    r"\byou\s+are\s+now\b",
    r"\bnew\s+persona\b",
    r"forget\s+everything",
    r"disregard\s+(all\s+)?(prior|previous)",
    r"override\s+(safety|guidelines|rules)",
    r"\bdo\s+anything\s+now\b",          # DAN jailbreak root phrase
    r"\bjailbreak\b",
    r"<\|.*?\|>",                        # GPT-4 / Mistral control tokens
    r"\{\{.*?\}\}",                      # template-injection double-braces
    r"###\s*instruction",                # raw LLM section headers
    r"\bEND\s*OF\s*PROMPT\b",
]

_CODE_INJECTION_PATTERNS: list[str] = [
    r";\s*(rm|del|format|shutdown|reboot|wget|curl)\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bos\.system\s*\(",
    r"\b__import__\s*\(",
    r"`[^`]{1,100}`",                    # shell backtick substitution
    r"\$\([^)]{1,100}\)",               # $(command) substitution
]

_COMBINED_INJECTION = re.compile(
    "|".join(f"(?:{p})" for p in _INJECTION_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)
_COMBINED_CODE = re.compile(
    "|".join(f"(?:{p})" for p in _CODE_INJECTION_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class IntentVerificationResult:
    is_safe: bool
    reasons: list[str] = field(default_factory=list)


# ── Verifier ──────────────────────────────────────────────────────────────────

class IntentVerifier:
    """
    Stateless verifier — instantiate once and call verify() per request.
    All checks are O(n) in input length with fixed-size regex patterns.
    """

    _SINGLETON: ClassVar[IntentVerifier | None] = None

    @classmethod
    def get_instance(cls) -> "IntentVerifier":
        if cls._SINGLETON is None:
            cls._SINGLETON = cls()
        return cls._SINGLETON

    # ── Public ────────────────────────────────────────────────────────────────

    def verify(self, text: str) -> IntentVerificationResult:
        """
        Runs all intent checks against the user-supplied text.

        Args:
            text: The raw user input before any sanitisation.

        Returns:
            IntentVerificationResult with is_safe=False and a list of
            human-readable reasons if the input is suspicious.
        """
        reasons: list[str] = []

        # ── 1. Size guard ─────────────────────────────────────────────────────
        if len(text) > MAX_INPUT_CHARS:
            reasons.append(
                f"Input too large: {len(text)} chars (max {MAX_INPUT_CHARS}). "
                "Oversized inputs are a common prompt-stuffing vector."
            )

        # ── 2. Prompt injection patterns ──────────────────────────────────────
        match = _COMBINED_INJECTION.search(text)
        if match:
            reasons.append(
                f"Prompt injection pattern detected: '{match.group()[:60]}'"
            )

        # ── 3. Code injection ─────────────────────────────────────────────────
        match = _COMBINED_CODE.search(text)
        if match:
            reasons.append(
                f"Code injection pattern detected: '{match.group()[:60]}'"
            )

        # ── 4. Null-byte / control-character smuggling ────────────────────────
        # Control chars (except tab/newline) are used to break parsers and
        # embed invisible instructions inside otherwise-innocent text.
        suspicious_ctrl = [c for c in text if ord(c) < 32 and c not in "\t\n\r"]
        if suspicious_ctrl:
            reasons.append(
                f"Suspicious control characters found: "
                f"{[hex(ord(c)) for c in suspicious_ctrl[:5]]}"
            )

        return IntentVerificationResult(is_safe=len(reasons) == 0, reasons=reasons)
