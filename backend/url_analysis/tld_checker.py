"""
TLD suspicion checker and typosquatting detector for Indian brands.

Typosquatting detection uses Levenshtein edit distance to catch common tricks:
  - Character substitution : sbi-bank.xyz → "sbi" is the brand
  - Brand-prefix domains   : sbi-secure-login.com
  - Brand-suffix domains   : login-sbi.com
  - Hyphen insertion       : s-b-i.com
"""

import logging
import re
from typing import Optional

import tldextract

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

SUSPICIOUS_TLDS = {
    ".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".pw",
    ".top", ".click", ".link", ".work", ".loan", ".win",
    ".racing", ".download", ".party", ".stream",
}

# Canonical brand tokens — must all be lowercase
INDIAN_BRANDS = [
    "sbi", "hdfc", "icici", "irctc", "aadhaar", "aadhar",
    "npci", "paytm", "bhim", "upi", "phonepe", "googlepay",
    "nsdl", "incometax", "uidai", "epfo",
]

# Maximum edit distance to be flagged as typosquatting
_LEVENSHTEIN_THRESHOLD = 1


def _levenshtein(s1: str, s2: str) -> int:
    """Standard dynamic-programming Levenshtein distance."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if len1 < len2:
        s1, s2, len1, len2 = s2, s1, len2, len1
    row = list(range(len2 + 1))
    for i, c1 in enumerate(s1, 1):
        new_row = [i]
        for j, c2 in enumerate(s2, 1):
            new_row.append(min(row[j] + 1, new_row[j - 1] + 1,
                               row[j - 1] + (c1 != c2)))
        row = new_row
    return row[-1]


def _tokenise_domain(domain: str) -> list[str]:
    """Split a domain label on hyphens and digits to extract brand tokens."""
    return [t for t in re.split(r"[-_0-9]", domain.lower()) if len(t) >= 3]


def is_suspicious_tld(url: str) -> bool:
    """
    Returns True if the URL's effective TLD is on the free-abuse-TLD list.

    Args:
        url: Fully-qualified URL string.

    Returns:
        bool: True → suspicious TLD detected.
    """
    try:
        extracted = tldextract.extract(url)
        # suffix includes only the TLD portion: "co.in", "xyz", etc.
        tld = f".{extracted.suffix}" if extracted.suffix else ""
        return tld.lower() in SUSPICIOUS_TLDS
    except Exception as exc:
        logger.debug(f"TLD check failed for '{url}': {exc}")
        return False


def check_typosquatting(
    domain: str,
    brand_list: list[str] = INDIAN_BRANDS,
) -> Optional[str]:
    """
    Checks whether a domain name is typosquatting a known Indian brand.

    Strategy:
      1. Split the domain's registered-name label into tokens.
      2. For each token, compute Levenshtein distance against every brand.
      3. Flag if distance ≤ threshold OR if the token contains a brand as
         a sub-string (catches brand-prefix/suffix patterns).

    Args:
        domain:     Bare domain name or full URL (tldextract handles both).
        brand_list: List of canonical brand names to check against.

    Returns:
        str:  The impersonated brand name if detected, e.g. "sbi".
        None: No typosquatting detected.
    """
    try:
        extracted = tldextract.extract(domain)
        registered_name = extracted.domain.lower()  # e.g. "sbi-secure-login"

        tokens = _tokenise_domain(registered_name)

        for brand in brand_list:
            brand = brand.lower()

            # Direct sub-string check catches "sbionline", "sbi-login", etc.
            if brand in registered_name:
                logger.debug(f"Brand substring match: '{brand}' in '{registered_name}'")
                return brand

            # Levenshtein check on each token
            for token in tokens:
                # Only compare tokens whose length is within ±2 of the brand
                if abs(len(token) - len(brand)) <= 2:
                    dist = _levenshtein(token, brand)
                    if dist <= _LEVENSHTEIN_THRESHOLD:
                        logger.debug(
                            f"Typosquat: token='{token}' brand='{brand}' dist={dist}"
                        )
                        return brand

    except Exception as exc:
        logger.debug(f"Typosquatting check failed for '{domain}': {exc}")

    return None
