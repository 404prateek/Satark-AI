"""
Risk aggregation engine — combines NLP, URL, behavioral, and OCR scores
into a single 0-100 risk score and SAFE / SUSPICIOUS / PHISHING verdict.

Weight rationale
─────────────────
  NLP score (45%):  The TF-IDF + MultinomialNB classifier trained on labeled
                    phishing/ham data is the single strongest signal.

  Behavioral (25%): Indian phishing messages use specific urgency/fear/prize
                    patterns that a general NLP model may underweight.

  URL score (25%):  When a URL is present, its analysis (PhishTank, WHOIS age,
                    TLD, redirects) is highly reliable evidence.

  OCR score (5%):   OCR is used only when input comes from a screenshot;
                    EasyOCR confidence ×  NLP score provides a modest uplift.

Verdict thresholds
──────────────────
  0  – 39   → SAFE
  40 – 69   → SUSPICIOUS
  70 – 100  → PHISHING
"""

from __future__ import annotations

from typing import Optional

_WEIGHT_NLP        = 0.45
_WEIGHT_BEHAVIORAL = 0.25
_WEIGHT_URL        = 0.25
_WEIGHT_OCR        = 0.05

_THRESHOLD_PHISHING   = 70
_THRESHOLD_SUSPICIOUS = 40


def calculate_risk(
    *,
    nlp_score: float,                      # 0.0 – 1.0  P(phishing) from MultinomialNB
    behavioral_score: float,               # 0.0 – 1.0  from behavioral_service
    url_score: float = 0.0,               # 0.0 – 1.0  from URLAnalyzer (includes insuf. bump)
    ocr_score: float = 0.0,               # 0.0 – 1.0  (nlp_score × ocr_confidence)
    has_url: bool = False,
    has_image: bool = False,
    url_insufficient_data: bool = False,   # True when all reputation sources blind
    text_length: int = 0,                  # used for certainty metric
    language: str = "en",                  # used for certainty metric
) -> dict:
    """
    Returns a dict with:
        risk_score        int     0–100
        verdict           str     SAFE | SUSPICIOUS | PHISHING
        component_scores  dict    per-signal scores (for UI display)
    """
    # Redistribute URL weight if no URL was found, or OCR weight if no image
    url_weight = _WEIGHT_URL        if has_url   else 0.0
    ocr_weight = _WEIGHT_OCR        if has_image else 0.0

    # Give the unallocated weight to NLP (it's the most reliable fallback)
    nlp_weight = 1.0 - _WEIGHT_BEHAVIORAL - url_weight - ocr_weight
    nlp_weight = max(nlp_weight, 0.1)  # always keep at least 10% on NLP

    raw = (
        nlp_weight        * nlp_score
        + _WEIGHT_BEHAVIORAL * behavioral_score
        + url_weight         * url_score
        + ocr_weight         * ocr_score
    )

    risk_score = min(round(raw * 100), 100)

    if risk_score >= _THRESHOLD_PHISHING:
        verdict = "PHISHING"
    elif risk_score >= _THRESHOLD_SUSPICIOUS:
        verdict = "SUSPICIOUS"
    else:
        verdict = "SAFE"

    # ── Certainty Calculation ─────────────────────────────────────────────────
    certainty = "high"
    
    # 1. Borderline cases (within 5 points of a boundary)
    if (35 <= risk_score <= 45) or (65 <= risk_score <= 75):
        certainty = "medium"
        
    # 2. Extreme lengths relative to training distribution
    if text_length < 20 or text_length > 2000:
        certainty = "medium" if certainty == "high" else "low"
        
    # 3. Unsupported languages (model was trained on en/hi/hinglish)
    if language.lower() not in {"en", "hi", "hinglish"}:
        certainty = "low"

    # Actual effective weights after redistribution
    beh_weight = _WEIGHT_BEHAVIORAL

    # Contributions (rounded to 1 dp for UI display)
    def _contrib(score: float, weight: float) -> float:
        return round(score * weight * 100, 1)

    return {
        "risk_score": risk_score,
        "verdict":    verdict,
        "certainty":  certainty,
        "component_scores": {
            "nlp": {
                "score":        round(nlp_score * 100),
                "weight":       round(nlp_weight, 2),
                "contribution": _contrib(nlp_score, nlp_weight),
            },
            "behavioral": {
                "score":        round(behavioral_score * 100),
                "weight":       round(beh_weight, 2),
                "contribution": _contrib(behavioral_score, beh_weight),
            },
            "url": {
                "score":              round(url_score * 100) if has_url else None,
                "weight":             round(url_weight, 2),
                "contribution":       _contrib(url_score, url_weight) if has_url else None,
                "insufficient_data":  url_insufficient_data,
            } if has_url else None,
            "ocr": {
                "score":        round(ocr_score * 100) if has_image else None,
                "weight":       round(ocr_weight, 2),
                "contribution": _contrib(ocr_score, ocr_weight) if has_image else None,
            } if has_image else None,
        },
    }
