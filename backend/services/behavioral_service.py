"""
Behavioral rule engine — detects social-engineering patterns in message text.

These rules fire on Indian phishing patterns that TF-IDF may miss because
they are low-frequency or appear only in Indian-language scams.  The engine
is intentionally simple (regex + keyword matching) to be fast and explainable.

Each rule contributes a small additive score (0.05–0.25).  The combined
behavioral_score is capped at 1.0 and fed into the risk aggregation formula
in risk_engine.py.
"""

from __future__ import annotations

import re

# ── Rule definitions ──────────────────────────────────────────────────────────
# Each entry: (pattern_or_keywords, weight, trigger_label)

_URGENCY_PATTERNS = [
    (r"\burgent\b",              0.10, "urgency_urgent"),
    (r"\bimmediately\b",         0.08, "urgency_immediately"),
    (r"\b24\s*hours?\b",         0.10, "urgency_24h_deadline"),
    (r"\bexpires?\s*(today|now)", 0.12, "urgency_expiry"),
    (r"\babhi\b",                0.10, "urgency_abhi"),       # Hindi: right now
    (r"\btatkal\b",              0.10, "urgency_tatkal"),     # Hindi: urgent
    (r"\bturant\b",              0.08, "urgency_turant"),     # Hindi: immediately
]

_FEAR_PATTERNS = [
    (r"\bsuspended?\b",          0.12, "fear_suspended"),
    (r"\bblocked?\b",            0.08, "fear_blocked"),
    (r"\bclosed?\b",             0.06, "fear_closed"),
    (r"\bband\s*ho\b",           0.12, "fear_band_ho"),       # Hindi: will be closed
    (r"\bdeactivated?\b",        0.10, "fear_deactivated"),
    (r"\blegal\s*action\b",      0.15, "fear_legal_action"),
    (r"\bfir\b",                 0.10, "fear_fir"),           # Indian police complaint
    (r"\barrest\b",              0.15, "fear_arrest"),
]

_PRIZE_PATTERNS = [
    (r"\bwon\b",                 0.10, "prize_won"),
    (r"\bwinne?r\b",             0.10, "prize_winner"),
    (r"\bjeet[ae]?\b",           0.10, "prize_jeeta"),       # Hindi: won
    (r"\bcongratulations?\b",    0.08, "prize_congratulations"),
    (r"\blucky\s*draw\b",        0.15, "prize_lucky_draw"),
    (r"\bprize\b",               0.08, "prize_prize"),
    (r"\binaam\b",               0.10, "prize_inaam"),        # Hindi: prize
    (r"\bgift\b",                0.06, "prize_gift"),
    (r"\bcashback\b",            0.06, "prize_cashback"),
    (r"₹\s*[\d,]+\s*(?:lakh|cr|crore)?", 0.08, "prize_money_amount"),
    (r"\brs\.?\s*\d+", 0.06, "prize_rs_amount"),
]

_CREDENTIAL_PATTERNS = [
    (r"\bkyc\b",                 0.15, "cred_kyc"),
    (r"\bverif(?:y|ication)\b",  0.08, "cred_verify"),
    (r"\botp\b",                 0.06, "cred_otp"),           # low alone, context-dependent
    (r"\bpassword\b",            0.12, "cred_password"),
    (r"\bpin\b",                 0.10, "cred_pin"),
    (r"\bpan\b",                 0.10, "cred_pan_card"),
    (r"\baadhaar\b",             0.10, "cred_aadhaar"),
    (r"\baccount\s*number\b",    0.15, "cred_account_number"),
    (r"\bcvv\b",                 0.20, "cred_cvv"),
    (r"\bcard\s*(?:number|details?)\b", 0.18, "cred_card_details"),
    (r"\bdard(?:z|j)?\s*karo\b", 0.10, "cred_darz_karo"),    # Hindi: enter/fill
]

_LINK_PATTERNS = [
    (r"bit\.ly/",                0.08, "link_bitly"),
    (r"t\.co/",                  0.06, "link_tco"),
    (r"tiny(?:url)?\.com/",      0.06, "link_tinyurl"),
    (r"(?:\.xyz|\.tk|\.ml|\.pw|\.top|\.cc|\.icu)\b", 0.15, "link_suspicious_tld"),
    (r"\bclick\s*here\b",        0.08, "link_click_here"),
    (r"\blink\s*(?:par|pe)\b",   0.10, "link_link_par"),     # Hindi: on the link
    (r"http://",                 0.05, "link_http_not_https"),
]

_ALL_RULES = _URGENCY_PATTERNS + _FEAR_PATTERNS + _PRIZE_PATTERNS + _CREDENTIAL_PATTERNS + _LINK_PATTERNS

# Pre-compile for speed
_COMPILED: list[tuple[re.Pattern, float, str]] = [
    (re.compile(pat, re.IGNORECASE), weight, label)
    for pat, weight, label in _ALL_RULES
]


# ── Public API ────────────────────────────────────────────────────────────────

def score_behavior(text: str) -> dict:
    """
    Runs all behavioral rules against the text and returns a combined score.

    Returns:
        {
            "behavioral_score": float,  # 0.0–1.0
            "triggers": list[str],      # human-readable trigger labels that fired
        }
    """
    if not text:
        return {"behavioral_score": 0.0, "triggers": []}

    raw_score = 0.0
    triggers: list[str] = []

    for pattern, weight, label in _COMPILED:
        if pattern.search(text):
            raw_score += weight
            triggers.append(label)

    # Multiple urgency+fear = compound amplifier (scammers stack them)
    urgency_count = sum(1 for t in triggers if t.startswith("urgency_"))
    fear_count    = sum(1 for t in triggers if t.startswith("fear_"))
    if urgency_count >= 2 and fear_count >= 1:
        raw_score *= 1.2   # 20% amplifier for stacked social-engineering

    behavioral_score = min(raw_score, 1.0)
    return {"behavioral_score": round(behavioral_score, 4), "triggers": triggers}
