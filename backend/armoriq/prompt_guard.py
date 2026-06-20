"""
ArmorIQ Prompt Guard

Sanitises user-supplied text before it is embedded into an LLM prompt.
The goal is NOT to filter the user's message (that's the intent verifier's
job) but to *neutralise* any residual injection material so that if a
crafted string somehow passes intent verification, it still cannot hijack
the system prompt when interpolated.

Security design decisions:
  1. Strip HTML / XML tags — prevents closing a <USER> tag and opening a
     <SYSTEM> tag inside the user message.
  2. Remove known injection phrases — belt-and-suspenders after the intent
     check; even if detection missed an obfuscated variant, stripping the
     literal phrase limits damage.
  3. Collapse whitespace but preserve newlines — phishing SMS messages
     legitimately contain newlines, so we must not flatten them.
  4. Unicode normalisation to NFKC — converts lookalike characters
     (e.g. Cyrillic 'а' U+0430 → Latin 'a') so regex patterns match
     obfuscated homoglyph attacks.
  5. Wrapping in XML-like delimiters at injection time (done in the router,
     not here) ensures the sanitised text is always structurally separated
     from system instructions.
"""

from __future__ import annotations

import html
import re
import unicodedata


# ── Patterns to strip outright ────────────────────────────────────────────────

_INJECTION_PHRASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), ""),
    (re.compile(r"\bsystem\s*:", re.I),                              "[system]"),
    (re.compile(r"\[INST\]",      re.I),                             ""),
    (re.compile(r"\bact\s+as\b",  re.I),                             "pretend to be"),
    (re.compile(r"\byou\s+are\s+now\b", re.I),                       ""),
    (re.compile(r"\bnew\s+persona\b",   re.I),                       ""),
    (re.compile(r"forget\s+everything", re.I),                       ""),
    (re.compile(r"disregard\s+(all\s+)?(prior|previous)", re.I),     ""),
    (re.compile(r"override\s+(safety|guidelines|rules)", re.I),       ""),
    (re.compile(r"\bdo\s+anything\s+now\b", re.I),                   ""),
    (re.compile(r"<\|.*?\|>",     re.DOTALL),                        ""),   # control tokens
    (re.compile(r"\{\{.*?\}\}",   re.DOTALL),                        ""),   # template inject
    (re.compile(r"###\s*instruction", re.I),                         ""),
]

_HTML_TAG_RE = re.compile(r"<[^>]{0,200}>")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def sanitize(text: str) -> str:
    """
    Sanitises user text for safe interpolation into an LLM prompt.

    Pipeline (in order):
      1. Unicode normalisation (NFKC) — neutralise homoglyphs.
      2. Unescape HTML entities — reveal hidden payloads like &lt;SYSTEM&gt;.
      3. Strip HTML/XML tags — prevent structural prompt injection.
      4. Replace known injection phrases with harmless equivalents.
      5. Collapse redundant whitespace.
      6. Truncate to hard limit (safety net if caller skips intent check).

    Args:
        text: Raw user-supplied text.

    Returns:
        Sanitised text safe for LLM prompt interpolation.
    """
    if not text:
        return ""

    # 1. NFKC normalisation
    text = unicodedata.normalize("NFKC", text)

    # 2. Unescape HTML entities so downstream regex sees plain text
    text = html.unescape(text)

    # 3. Strip HTML / XML tags
    text = _HTML_TAG_RE.sub("", text)

    # 4. Remove / replace injection phrases
    for pattern, replacement in _INJECTION_PHRASES:
        text = pattern.sub(replacement, text)

    # 5. Collapse whitespace (but keep single newlines)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    # 6. Hard-limit truncation (4 000 chars ≈ 1 000 tokens for Groq)
    text = text[:4_000]

    return text.strip()
