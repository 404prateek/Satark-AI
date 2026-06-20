"""
URL Analysis Orchestrator for Satark AI.

Score Formula
─────────────
Each sub-check contributes a weighted additive penalty to a raw score
that is finally clamped to [0.0, 1.0]:

  raw_score =
    0.40  × phishtank_hit          (binary: 1.0 if confirmed phishing)
    0.20  × typosquatting_hit      (binary: 1.0 if brand impersonation found)
    0.15  × suspicious_tld_hit     (binary: 1.0 if on abused-TLD list)
    0.15  × young_domain_penalty   (linear: 1.0 if age < 7 days, scales to 0 at 365 days)
    0.05  × redirect_penalty       (linear: min(hop_count / 5, 1.0))
    0.05  × whois_opacity_penalty  (1.0 if registrar or country is unknown)

  final_score = min(raw_score, 1.0)

Weights reflect empirical risk ordering:
  PhishTank confirmation is ground-truth evidence → highest weight.
  Typosquatting of Indian brands is a very strong signal → second highest.
  Suspicious TLD is a moderate signal (many legitimate sites use .xyz etc.).
  Young domain age and redirect chains are supporting signals.
  WHOIS opacity alone is weak (many privacy-protected legit domains).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import tldextract
import validators

from backend.url_analysis.phishtank_checker import check_phishtank
from backend.url_analysis.tld_checker import is_suspicious_tld, check_typosquatting, INDIAN_BRANDS
from backend.url_analysis.whois_checker import get_domain_age_days, get_whois_info
from backend.url_analysis.redirect_follower import follow_redirects

logger = logging.getLogger(__name__)

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class URLAnalysisResult:
    url: str
    final_url: str
    score: float                        # 0.0 = safe, 1.0 = phishing
    is_phishtank_hit: bool = False
    typosquatted_brand: Optional[str] = None
    is_suspicious_tld: bool = False
    domain_age_days: Optional[int] = None
    whois_info: dict = field(default_factory=dict)
    redirect_chain: list[str] = field(default_factory=list)
    hop_count: int = 0
    redirect_error: Optional[str] = None
    error: Optional[str] = None         # set if analysis itself failed

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "score": round(self.score, 4),
            "is_phishtank_hit": self.is_phishtank_hit,
            "typosquatted_brand": self.typosquatted_brand,
            "is_suspicious_tld": self.is_suspicious_tld,
            "domain_age_days": self.domain_age_days,
            "whois_info": self.whois_info,
            "redirect_chain": self.redirect_chain,
            "hop_count": self.hop_count,
            "redirect_error": self.redirect_error,
            "error": self.error,
        }


# ── Scorer ────────────────────────────────────────────────────────────────────

_YOUNG_DOMAIN_SAFE_AGE = 365    # days — older than this → no age penalty
_YOUNG_DOMAIN_INSTANT = 7       # days — younger than this → max age penalty


def _young_domain_penalty(age_days: Optional[int]) -> float:
    """Linear decay from 1.0 (very new) to 0.0 (1+ year old)."""
    if age_days is None:
        return 0.5                           # unknown → moderate penalty
    if age_days < _YOUNG_DOMAIN_INSTANT:
        return 1.0
    if age_days >= _YOUNG_DOMAIN_SAFE_AGE:
        return 0.0
    return 1.0 - (age_days - _YOUNG_DOMAIN_INSTANT) / (_YOUNG_DOMAIN_SAFE_AGE - _YOUNG_DOMAIN_INSTANT)


def _redirect_penalty(hop_count: int) -> float:
    return min(hop_count / 5.0, 1.0)


def _whois_opacity_penalty(whois_info: dict) -> float:
    missing = sum(1 for v in [whois_info.get("registrar"), whois_info.get("country")] if not v)
    return missing / 2.0


def _calculate_score(
    phishtank_hit: bool,
    typosquat_hit: bool,
    suspicious_tld: bool,
    domain_age: Optional[int],
    hop_count: int,
    whois_info: dict,
) -> float:
    raw = (
        0.40 * float(phishtank_hit)
        + 0.20 * float(typosquat_hit)
        + 0.15 * float(suspicious_tld)
        + 0.15 * _young_domain_penalty(domain_age)
        + 0.05 * _redirect_penalty(hop_count)
        + 0.05 * _whois_opacity_penalty(whois_info)
    )
    return min(raw, 1.0)


# ── Analyser class ────────────────────────────────────────────────────────────

class URLAnalyzer:
    """
    Orchestrates all URL sub-analysers and returns a combined phishing score.
    Instantiate once and reuse; sub-checks are stateless functions.
    """

    def __init__(self, brand_list: list[str] = INDIAN_BRANDS):
        self.brand_list = brand_list

    def analyze(self, url: str) -> URLAnalysisResult:
        """
        Runs all sub-analysers against the given URL and returns a
        URLAnalysisResult with a composite phishing score.

        Args:
            url: The URL string to analyse (must be fully qualified).

        Returns:
            URLAnalysisResult dataclass.
        """
        # ── 0. Basic URL validation ──────────────────────────────────────────
        if not validators.url(url):
            logger.warning(f"Invalid URL submitted: {url}")
            return URLAnalysisResult(
                url=url,
                final_url=url,
                score=0.0,
                error=f"Invalid URL: '{url}'",
            )

        extracted = tldextract.extract(url)
        domain = f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain

        # ── 1. Redirect following (resolve the final destination first) ──────
        logger.info(f"[URLAnalyzer] Following redirects: {url}")
        redirect_result = follow_redirects(url)
        final_url = redirect_result["final_url"]
        redirect_chain = redirect_result["redirect_chain"]
        hop_count = redirect_result["hop_count"]

        # Re-extract domain from final URL in case it redirected somewhere else
        final_extracted = tldextract.extract(final_url)
        final_domain = (
            f"{final_extracted.domain}.{final_extracted.suffix}"
            if final_extracted.suffix
            else final_extracted.domain
        )

        # ── 2. PhishTank check ───────────────────────────────────────────────
        logger.info(f"[URLAnalyzer] Checking PhishTank: {final_url}")
        phishtank_hit = check_phishtank(final_url)

        # ── 3. TLD + typosquatting ───────────────────────────────────────────
        logger.info(f"[URLAnalyzer] Checking TLD + typosquatting: {final_domain}")
        suspicious_tld = is_suspicious_tld(final_url)
        typosquatted_brand = check_typosquatting(final_domain, self.brand_list)

        # ── 4. WHOIS ─────────────────────────────────────────────────────────
        logger.info(f"[URLAnalyzer] Fetching WHOIS: {final_domain}")
        domain_age = get_domain_age_days(final_domain)
        whois_info = get_whois_info(final_domain)

        # ── 5. Score ─────────────────────────────────────────────────────────
        score = _calculate_score(
            phishtank_hit=phishtank_hit,
            typosquat_hit=typosquatted_brand is not None,
            suspicious_tld=suspicious_tld,
            domain_age=domain_age,
            hop_count=hop_count,
            whois_info=whois_info,
        )

        logger.info(
            f"[URLAnalyzer] Result — domain={final_domain} score={score:.4f} "
            f"phishtank={phishtank_hit} typosquat={typosquatted_brand} "
            f"tld={suspicious_tld} age={domain_age}d hops={hop_count}"
        )

        return URLAnalysisResult(
            url=url,
            final_url=final_url,
            score=score,
            is_phishtank_hit=phishtank_hit,
            typosquatted_brand=typosquatted_brand,
            is_suspicious_tld=suspicious_tld,
            domain_age_days=domain_age,
            whois_info=whois_info,
            redirect_chain=redirect_chain,
            hop_count=hop_count,
            redirect_error=redirect_result.get("error"),
        )
