"""
Language detector for Satark AI.

Strategy:
  1. Count Devanagari characters (Unicode U+0900–U+097F).
  2. Count Latin script characters (a-z / A-Z).
  3. If both are significantly present → "hinglish".
  4. If only Devanagari → "hi".
  5. Else → use langdetect as a fallback, default to "en" on failure.

Why regex-first?
  langdetect is probabilistic and can misclassify short Hinglish phrases
  (e.g. "SBI ka link click karo") as English. The Unicode range check is
  deterministic and never wrong about script presence.
"""

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

# Devanagari Unicode block letters only (U+0900–U+0965, U+0970–U+097F)
# Intentionally excludes Devanagari digits U+0966–U+096F (०-९) because OCR'd
# images with Hindi price figures (e.g. "२०K") should still count as English.
_DEVANAGARI_RE = re.compile(r"[\u0900-\u0965\u0970-\u097F]")

# Basic Latin letters
_LATIN_RE = re.compile(r"[a-zA-Z]")

# Minimum character counts to be considered "significant presence".
# _MIN_DEVANAGARI is intentionally high (10) to avoid a handful of OCR-misread
# Rupee symbols (र U+0930) from flipping an English document to "hinglish".
# Additionally, Devanagari must form ≥5% of total script chars (ratio guard).
_MIN_DEVANAGARI = 10
_MIN_LATIN = 5
_DEVANAGARI_RATIO_THRESHOLD = 0.05  # 5% of (devanagari + latin) chars


def detect_language(text: str) -> Literal["en", "hi", "hinglish"]:
    """
    Detects whether text is English, Hindi, or Hinglish (code-switched).

    Args:
        text: Raw input string (SMS, email body, URL text, etc.)

    Returns:
        "en"       — Primarily English / Latin script.
        "hi"       — Primarily Hindi / Devanagari script.
        "hinglish" — Mix of Devanagari and Latin scripts.
    """
    if not text or not text.strip():
        return "en"

    devanagari_count = len(_DEVANAGARI_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    total_script = devanagari_count + latin_count

    # Must meet both absolute count AND ratio thresholds to avoid false positives
    # from a few OCR-misread ₹ symbols appearing in English-primary text.
    deva_ratio = devanagari_count / total_script if total_script > 0 else 0.0
    has_devanagari = (
        devanagari_count >= _MIN_DEVANAGARI
        and deva_ratio >= _DEVANAGARI_RATIO_THRESHOLD
    )
    has_latin = latin_count >= _MIN_LATIN

    if has_devanagari and has_latin:
        return "hinglish"

    if has_devanagari:
        return "hi"

    # For purely Latin text use langdetect as a secondary signal
    try:
        from langdetect import detect, LangDetectException  # type: ignore
        detected = detect(text)
        if detected == "hi":
            return "hi"
    except Exception as exc:
        logger.debug(f"langdetect failed: {exc}")

    return "en"
