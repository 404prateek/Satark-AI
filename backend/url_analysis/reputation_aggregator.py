"""
Multi-source URL reputation aggregator for Satark AI.

Why weighted fusion instead of a single source
───────────────────────────────────────────────
No single reputation source is complete:

  PhishTank:            High precision but slow to update (~hours lag).
                        Misses brand-new campaign domains entirely.

  Google Safe Browsing: Broadest coverage, fast updates, high trust.
                        Still blocklist-based; fresh domains evade it.

  VirusTotal:           Aggregates 70+ AV engines. Best coverage, but
                        slow (free tier 4 req/min) and also blocklist-based.

  Domain age heuristic: The only source that catches what blocklists CAN'T —
                        a domain registered hours before the campaign launch.
                        Lower precision (legitimate startups also have new
                        domains), but fills a critical blind spot.

Weighted voting with short-circuit agreement
────────────────────────────────────────────
  SOURCE_WEIGHTS encodes empirical reliability.
  Two or more independent "malicious" verdicts short-circuit to ≥0.90
  because corroboration across independent data sources is stronger than
  any individual weighted score — this is the key insight that makes
  ensemble methods outperform single-source lookups.

"Insufficient data" is not "clean"
────────────────────────────────────
  When ALL sources return "unknown" (brand-new domain, all APIs
  rate-limited/timed out), we flag insufficient_data=True rather than
  defaulting to "clean".  An unverifiable domain should be treated with
  elevated caution, not assumed safe — this is exactly the blind spot
  phishing campaigns exploit by registering fresh domains.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.url_analysis.reputation_sources import (
    check_phishtank,
    check_google_safe_browsing,
    check_virustotal,
    check_domain_age_heuristic,
)

logger = logging.getLogger(__name__)

# ── Source weights ────────────────────────────────────────────────────────────
# Must sum to 1.0.  Weights reflect relative precision/coverage, not speed.
SOURCE_WEIGHTS: dict[str, float] = {
    "phishtank":            0.30,
    "google_safe_browsing": 0.30,
    "virustotal":           0.25,
    "domain_age_heuristic": 0.15,
}

# ── Per-source timeout ────────────────────────────────────────────────────────
# Each source gets 3 seconds max.  A timeout is treated as "unknown" — the
# aggregator continues with the remaining sources rather than failing.
_PER_SOURCE_TIMEOUT = 3.0  # seconds

# Verdict → numeric phishing score mapping used in weighted averaging
_VERDICT_SCORE: dict[str, float] = {
    "malicious":  1.0,
    "suspicious": 0.55,
    "clean":      0.0,
    "unknown":    0.15,   # small non-zero: unknown ≠ safe
}

# Short-circuit threshold: ≥2 independent "malicious" verdicts
_MALICIOUS_AGREEMENT_THRESHOLD = 2


async def _safe_check(coro, source_name: str) -> dict:
    """
    Wraps a reputation check coroutine with a per-source timeout.
    Returns an "unknown" result if the call times out or raises.
    """
    try:
        return await asyncio.wait_for(coro, timeout=_PER_SOURCE_TIMEOUT)
    except asyncio.TimeoutError:
        logger.info("Reputation source '%s' timed out after %.1fs", source_name, _PER_SOURCE_TIMEOUT)
        return {
            "source":     source_name,
            "verdict":    "unknown",
            "confidence": 0.0,
            "raw":        {"error": f"timed out after {_PER_SOURCE_TIMEOUT}s"},
        }
    except Exception as exc:
        logger.warning("Reputation source '%s' raised: %s", source_name, exc)
        return {
            "source":     source_name,
            "verdict":    "unknown",
            "confidence": 0.0,
            "raw":        {"error": str(exc)},
        }


async def get_combined_reputation(url: str) -> dict:
    """
    Queries all 4 reputation sources concurrently, then fuses their verdicts
    into a single combined score using weighted voting with short-circuit logic.

    Args:
        url: A fully-qualified URL string.

    Returns:
        {
            "combined_score":    float,   # 0.0–1.0 phishing risk
            "verdict":           str,     # "malicious" | "suspicious" | "clean" | "unknown"
            "sources_checked":   list[str],
            "sources_agreeing":  int,     # count of sources saying "malicious"
            "insufficient_data": bool,    # True if ALL sources returned "unknown"
            "source_results":    list[dict],  # raw per-source results for transparency
        }
    """
    # ── Run all sources concurrently ──────────────────────────────────────────
    results = await asyncio.gather(
        _safe_check(check_phishtank(url),             "phishtank"),
        _safe_check(check_google_safe_browsing(url),  "google_safe_browsing"),
        _safe_check(check_virustotal(url),            "virustotal"),
        _safe_check(check_domain_age_heuristic(url),  "domain_age_heuristic"),
    )

    sources_checked = [r["source"] for r in results]
    verdicts = {r["source"]: r["verdict"] for r in results}

    # ── Short-circuit: strong independent agreement ───────────────────────────
    malicious_sources = [s for s, v in verdicts.items() if v == "malicious"]
    sources_agreeing  = len(malicious_sources)

    if sources_agreeing >= _MALICIOUS_AGREEMENT_THRESHOLD:
        # At least 2 independent sources confirm malicious — very high confidence.
        # Boost to 0.90 + small premium for each additional corroborating source.
        combined_score = min(0.90 + (sources_agreeing - 2) * 0.04, 0.98)
        verdict = "malicious"
        logger.info(
            "URL %s: %d sources agree malicious → short-circuit score=%.3f",
            url, sources_agreeing, combined_score,
        )
        return {
            "combined_score":    round(combined_score, 4),
            "verdict":           verdict,
            "sources_checked":   sources_checked,
            "sources_agreeing":  sources_agreeing,
            "insufficient_data": False,
            "source_results":    results,
        }

    # ── Weighted vote ─────────────────────────────────────────────────────────
    weighted_score = 0.0
    total_weight   = 0.0

    for result in results:
        source  = result["source"]
        verdict = result["verdict"]
        conf    = result["confidence"]
        weight  = SOURCE_WEIGHTS.get(source, 0.0)

        # Score contribution: verdict score weighted by source weight AND confidence
        verdict_score = _VERDICT_SCORE.get(verdict, 0.15)

        # For "clean" from a high-confidence source, apply a small negative
        # correction so multi-source clean pushes score down.
        if verdict == "clean":
            contribution = verdict_score * weight  # will be 0.0 * weight = 0
        else:
            contribution = verdict_score * conf * weight

        weighted_score += contribution
        total_weight   += weight

    # Normalise (total_weight should = 1.0 since we have all 4 sources)
    if total_weight > 0:
        combined_score = min(weighted_score / total_weight if total_weight < 0.95 else weighted_score, 1.0)
    else:
        combined_score = 0.0

    # ── Insufficient data check ───────────────────────────────────────────────
    all_unknown = all(r["verdict"] == "unknown" for r in results)
    if all_unknown:
        # All sources are blind to this URL — treat with elevated caution.
        # Don't return clean; return a modest non-zero score to flag the gap.
        combined_score    = 0.25   # elevated caution for unverifiable domains
        combined_verdict  = "unknown"
        insufficient_data = True
        logger.info("URL %s: all sources unknown → insufficient_data=True", url)
    else:
        insufficient_data = False
        if combined_score >= 0.65:
            combined_verdict = "malicious"
        elif combined_score >= 0.35:
            combined_verdict = "suspicious"
        else:
            combined_verdict = "clean"

    logger.info(
        "URL %s: combined_score=%.3f verdict=%s sources=%s",
        url, combined_score, combined_verdict,
        {r["source"]: r["verdict"] for r in results},
    )

    return {
        "combined_score":    round(combined_score, 4),
        "verdict":           combined_verdict,
        "sources_checked":   sources_checked,
        "sources_agreeing":  sources_agreeing,
        "insufficient_data": insufficient_data,
        "source_results":    results,
    }
