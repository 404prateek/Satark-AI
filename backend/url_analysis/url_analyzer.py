"""
URL Analysis Orchestrator for Satark AI.

Score Formula (v2 — multi-source reputation)
─────────────────────────────────────────────
Each sub-check contributes a weighted additive penalty clamped to [0.0, 1.0]:

  raw_score =
    0.55  × reputation_score      (combined: PhishTank + GSB + VT + domain age)
    0.20  × typosquatting_hit     (binary: 1.0 if brand impersonation found)
    0.10  × suspicious_tld_hit    (binary: 1.0 if on abused-TLD list)
    0.10  × redirect_penalty      (linear: min(hop_count / 5, 1.0))
    0.05  × whois_opacity_penalty (1.0 if registrar or country is unknown)

  final_score = min(raw_score, 1.0)

  insufficient_data bump:
    When get_combined_reputation() returns insufficient_data=True (all sources
    blind to this URL), a +0.15 flat bonus is applied to the final score to
    reflect the elevated risk of an unverifiable/unestablished domain.
    This is smaller than a confirmed malicious signal but larger than zero —
    unknown is NOT the same as safe.

Changes from v1
───────────────
  • Replaced single PhishTank binary hit with get_combined_reputation() which
    aggregates PhishTank + Google Safe Browsing + VirusTotal + domain age via
    concurrent async calls and weighted voting.
  • The URLAnalyzer.analyze() method is now async to support the concurrent
    reputation checks without blocking the FastAPI event loop.
  • URLAnalysisResult gains: reputation, reputation_verdict, reputation_sources,
    insufficient_reputation_data — exposed in to_dict() for UI display.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import tldextract
import validators

from backend.url_analysis.reputation_aggregator import get_combined_reputation
from backend.url_analysis.tld_checker import is_suspicious_tld, check_typosquatting, INDIAN_BRANDS
from backend.url_analysis.whois_checker import get_whois_info
from backend.url_analysis.redirect_follower import follow_redirects

logger = logging.getLogger(__name__)

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class URLAnalysisResult:
    url: str
    final_url: str
    score: float                        # 0.0 = safe, 1.0 = phishing

    # Legacy fields — kept for backwards compatibility with stored scan JSON
    is_phishtank_hit: bool = False
    typosquatted_brand: Optional[str] = None
    is_suspicious_tld: bool = False
    domain_age_days: Optional[int] = None
    whois_info: dict = field(default_factory=dict)
    redirect_chain: list[str] = field(default_factory=list)
    hop_count: int = 0
    redirect_error: Optional[str] = None
    error: Optional[str] = None

    # v2 multi-source reputation fields
    reputation_score: float = 0.0
    reputation_verdict: str = "unknown"
    reputation_sources: list[str] = field(default_factory=list)
    sources_agreeing: int = 0
    insufficient_reputation_data: bool = False
    source_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url":                          self.url,
            "final_url":                    self.final_url,
            "score":                        round(self.score, 4),
            "is_phishtank_hit":             self.is_phishtank_hit,
            "typosquatted_brand":           self.typosquatted_brand,
            "is_suspicious_tld":            self.is_suspicious_tld,
            "domain_age_days":              self.domain_age_days,
            "whois_info":                   self.whois_info,
            "redirect_chain":               self.redirect_chain,
            "hop_count":                    self.hop_count,
            "redirect_error":               self.redirect_error,
            "error":                        self.error,
            # v2 reputation fields
            "reputation_score":             round(self.reputation_score, 4),
            "reputation_verdict":           self.reputation_verdict,
            "reputation_sources":           self.reputation_sources,
            "sources_agreeing":             self.sources_agreeing,
            "insufficient_reputation_data": self.insufficient_reputation_data,
            "source_results":               self.source_results,
        }


# ── Scorer helpers ────────────────────────────────────────────────────────────

_INSUFFICIENT_DATA_BUMP = 0.15   # flat bonus when all reputation sources are blind


def _redirect_penalty(hop_count: int) -> float:
    return min(hop_count / 5.0, 1.0)


def _whois_opacity_penalty(whois_info: dict) -> float:
    missing = sum(
        1 for v in [whois_info.get("registrar"), whois_info.get("country")]
        if not v
    )
    return missing / 2.0


def _calculate_score(
    reputation_score: float,
    insufficient_data: bool,
    typosquat_hit: bool,
    suspicious_tld: bool,
    hop_count: int,
    whois_info: dict,
) -> float:
    raw = (
        0.55 * reputation_score
        + 0.20 * float(typosquat_hit)
        + 0.10 * float(suspicious_tld)
        + 0.10 * _redirect_penalty(hop_count)
        + 0.05 * _whois_opacity_penalty(whois_info)
    )

    # Insufficient-data bump: unverifiable domain ≠ safe
    if insufficient_data:
        raw += _INSUFFICIENT_DATA_BUMP

    return min(raw, 1.0)


# ── Analyser class ────────────────────────────────────────────────────────────

class URLAnalyzer:
    """
    Orchestrates all URL sub-analysers and returns a combined phishing score.
    Instantiate once and reuse; sub-checks are stateless functions.

    v2: analyze() is now async to support concurrent multi-source reputation
    checks without blocking the FastAPI event loop.
    """

    def __init__(self, brand_list: list[str] = INDIAN_BRANDS):
        self.brand_list = brand_list

    async def analyze(self, url: str) -> URLAnalysisResult:
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
            logger.warning("Invalid URL submitted: %s", url)
            return URLAnalysisResult(
                url=url,
                final_url=url,
                score=0.0,
                error=f"Invalid URL: '{url}'",
            )

        extracted = tldextract.extract(url)
        domain = f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain

        # ── 1. Redirect following + TLD/typosquat + WHOIS (concurrent) ───────
        logger.info("[URLAnalyzer v2] Analysing: %s", url)

        redirect_task = asyncio.to_thread(follow_redirects, url)
        whois_task    = asyncio.to_thread(get_whois_info, domain)

        (redirect_result, whois_info) = await asyncio.gather(
            redirect_task, whois_task
        )

        final_url     = redirect_result["final_url"]
        redirect_chain = redirect_result["redirect_chain"]
        hop_count     = redirect_result["hop_count"]

        final_extracted = tldextract.extract(final_url)
        final_domain = (
            f"{final_extracted.domain}.{final_extracted.suffix}"
            if final_extracted.suffix else final_extracted.domain
        )

        # TLD / typosquatting (sync, fast)
        suspicious_tld   = is_suspicious_tld(final_url)
        typosquatted_brand = check_typosquatting(final_domain, self.brand_list)

        # ── 2. Multi-source reputation (the new core) ─────────────────────────
        logger.info("[URLAnalyzer v2] Launching reputation checks: %s", final_url)
        reputation = await get_combined_reputation(final_url)

        reputation_score   = reputation["combined_score"]
        reputation_verdict = reputation["verdict"]
        insufficient_data  = reputation["insufficient_data"]
        sources_agreeing   = reputation["sources_agreeing"]
        source_results     = reputation.get("source_results", [])

        # Back-compat: mark phishtank_hit if PhishTank specifically said malicious
        phishtank_hit = any(
            r["source"] == "phishtank" and r["verdict"] == "malicious"
            for r in source_results
        )

        # Domain age from domain_age_heuristic source result
        domain_age_days: Optional[int] = None
        for r in source_results:
            if r["source"] == "domain_age_heuristic":
                domain_age_days = r["raw"].get("age_days")
                break

        # ── 3. Final score ────────────────────────────────────────────────────
        score = _calculate_score(
            reputation_score=reputation_score,
            insufficient_data=insufficient_data,
            typosquat_hit=typosquatted_brand is not None,
            suspicious_tld=suspicious_tld,
            hop_count=hop_count,
            whois_info=whois_info,
        )

        logger.info(
            "[URLAnalyzer v2] domain=%s score=%.4f reputation=%.4f(%s) "
            "insuf=%s typosquat=%s tld=%s age=%s hops=%d",
            final_domain, score, reputation_score, reputation_verdict,
            insufficient_data, typosquatted_brand, suspicious_tld,
            domain_age_days, hop_count,
        )

        return URLAnalysisResult(
            url=url,
            final_url=final_url,
            score=score,
            is_phishtank_hit=phishtank_hit,
            typosquatted_brand=typosquatted_brand,
            is_suspicious_tld=suspicious_tld,
            domain_age_days=domain_age_days,
            whois_info=whois_info,
            redirect_chain=redirect_chain,
            hop_count=hop_count,
            redirect_error=redirect_result.get("error"),
            reputation_score=reputation_score,
            reputation_verdict=reputation_verdict,
            reputation_sources=reputation["sources_checked"],
            sources_agreeing=sources_agreeing,
            insufficient_reputation_data=insufficient_data,
            source_results=source_results,
        )
