"""
Multi-source URL reputation checks for Satark AI.

Each function returns the same normalized shape:
  {
    "source":     str,                               # source identifier
    "verdict":    "malicious"|"suspicious"|"clean"|"unknown",
    "confidence": float,                             # 0.0 – 1.0
    "raw":        dict,                              # source-specific response
  }

Design principles
─────────────────
  • Every function is fully async — callers can run them concurrently.
  • Every function NEVER raises — network failures, rate limits, missing API
    keys all return verdict="unknown" with a reason in raw["error"].
  • No single function's failure blocks the pipeline.

API keys & free tier limits
────────────────────────────
  GOOGLE_SAFE_BROWSING_API_KEY:
    Free via Google Cloud Console → APIs & Services → Safe Browsing API.
    Quota: 10,000 requests/day, no per-minute rate limit documented.
    Docs: https://developers.google.com/safe-browsing/v4/lookup-api

  VIRUSTOTAL_API_KEY:
    Free via https://www.virustotal.com/gui/join-us
    Quota: 4 requests/minute, 500 requests/day.
    Implemented with an asyncio Semaphore to stay within the 4/min limit.
    Docs: https://developers.virustotal.com/reference/overview
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from typing import Optional

import httpx
import tldextract

logger = logging.getLogger(__name__)

# ── API keys ─────────────────────────────────────────────────────────────────
_GOOGLE_SB_KEY = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY", "")
_VIRUSTOTAL_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")

# VirusTotal free tier: 4 requests/minute  →  1 request per 15 seconds max.
# Semaphore(4) allows up to 4 concurrent calls; we also sleep after each call.
_VT_SEMAPHORE = asyncio.Semaphore(4)
_VT_LAST_CALL: float = 0.0

# ── TTL caches ────────────────────────────────────────────────────────────────
# { cache_key: (result_dict, expiry_timestamp) }
_CACHE_TTL = 3600  # 1 hour
_GSB_CACHE:  dict[str, tuple[dict, float]] = {}
_VT_CACHE:   dict[str, tuple[dict, float]] = {}
_AGE_CACHE:  dict[str, tuple[dict, float]] = {}


def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _cache_get(cache: dict, key: str) -> Optional[dict]:
    entry = cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    cache.pop(key, None)
    return None


def _cache_set(cache: dict, key: str, value: dict) -> None:
    cache[key] = (value, time.monotonic() + _CACHE_TTL)


# ── Source 1: PhishTank ───────────────────────────────────────────────────────

async def check_phishtank(url: str) -> dict:
    """
    Wraps the existing sync PhishTank check into the normalized result shape.
    Returns verdict="unknown" if the API key is missing or check fails.
    """
    try:
        from backend.url_analysis.phishtank_checker import (
            check_phishtank as _sync_check,
        )
        is_phishing = await asyncio.to_thread(_sync_check, url)
        return {
            "source":     "phishtank",
            "verdict":    "malicious" if is_phishing else "unknown",
            "confidence": 0.95 if is_phishing else 0.0,
            "raw":        {"in_database": is_phishing},
        }
    except Exception as exc:
        logger.debug("PhishTank wrapper error: %s", exc)
        return {
            "source":     "phishtank",
            "verdict":    "unknown",
            "confidence": 0.0,
            "raw":        {"error": str(exc)},
        }


# ── Source 2: Google Safe Browsing API v4 ─────────────────────────────────────

_GSB_API = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
_GSB_THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]
_GSB_PLATFORM_TYPES = ["ANY_PLATFORM"]
_GSB_ENTRY_TYPES    = ["URL"]


async def check_google_safe_browsing(url: str) -> dict:
    """
    Queries Google Safe Browsing Lookup API v4.
    Returns verdict="malicious" with the matched threat type if the URL
    is listed, "clean" if explicitly not found, "unknown" on failure/missing key.

    Free tier: 10,000 req/day; no rate limiting required at typical volumes.
    """
    if not _GOOGLE_SB_KEY:
        return {
            "source": "google_safe_browsing",
            "verdict": "unknown",
            "confidence": 0.0,
            "raw": {"error": "GOOGLE_SAFE_BROWSING_API_KEY not configured"},
        }

    key = _url_key(url)
    cached = _cache_get(_GSB_CACHE, key)
    if cached:
        return cached

    payload = {
        "client": {"clientId": "satark-ai", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes":      _GSB_THREAT_TYPES,
            "platformTypes":    _GSB_PLATFORM_TYPES,
            "threatEntryTypes": _GSB_ENTRY_TYPES,
            "threatEntries":    [{"url": url}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                _GSB_API,
                params={"key": _GOOGLE_SB_KEY},
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        data = resp.json()

        matches = data.get("matches", [])
        if matches:
            threat = matches[0].get("threatType", "SOCIAL_ENGINEERING")
            result = {
                "source":     "google_safe_browsing",
                "verdict":    "malicious",
                "confidence": 0.98,   # GSB is Google-curated, very high trust
                "raw":        {"matches": matches, "threat_type": threat},
            }
        else:
            result = {
                "source":     "google_safe_browsing",
                "verdict":    "clean",
                "confidence": 0.85,
                "raw":        {},
            }

        _cache_set(_GSB_CACHE, key, result)
        return result

    except Exception as exc:
        logger.debug("Google Safe Browsing error: %s", exc)
        return {
            "source":     "google_safe_browsing",
            "verdict":    "unknown",
            "confidence": 0.0,
            "raw":        {"error": str(exc)},
        }


# ── Source 3: VirusTotal ──────────────────────────────────────────────────────

_VT_SCAN_URL   = "https://www.virustotal.com/api/v3/urls"
_VT_REPORT_URL = "https://www.virustotal.com/api/v3/urls/{id}"


async def check_virustotal(url: str) -> dict:
    """
    Checks VirusTotal v3 URL scan API.

    Flow: submit URL → get analysis ID → fetch report with malicious count.
    Uses an async semaphore (4 concurrent max) to respect the 4 req/min free
    tier limit.  A 15-second delay between calls is enforced when the semaphore
    would otherwise be saturated.

    Free tier: 4 req/min, 500 req/day.
    """
    global _VT_LAST_CALL

    if not _VIRUSTOTAL_KEY:
        return {
            "source": "virustotal",
            "verdict": "unknown",
            "confidence": 0.0,
            "raw": {"error": "VIRUSTOTAL_API_KEY not configured"},
        }

    key = _url_key(url)
    cached = _cache_get(_VT_CACHE, key)
    if cached:
        return cached

    async with _VT_SEMAPHORE:
        # Rate-gate: enforce ≥15 seconds between VT calls in this process
        now = time.monotonic()
        gap = now - _VT_LAST_CALL
        if gap < 15.0 and _VT_LAST_CALL > 0:
            await asyncio.sleep(15.0 - gap)
        _VT_LAST_CALL = time.monotonic()

        try:
            headers = {
                "x-apikey": _VIRUSTOTAL_KEY,
                "Accept":   "application/json",
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                # Step 1 — Submit for scanning (or look up cached scan)
                import base64
                url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

                report_resp = await client.get(
                    _VT_REPORT_URL.format(id=url_id),
                    headers=headers,
                )

                if report_resp.status_code == 404:
                    # URL not in VT yet — submit it, then return unknown
                    # (report won't be ready immediately)
                    await client.post(
                        _VT_SCAN_URL,
                        headers=headers,
                        data={"url": url},
                    )
                    result = {
                        "source":     "virustotal",
                        "verdict":    "unknown",
                        "confidence": 0.0,
                        "raw":        {"status": "submitted_for_analysis"},
                    }
                    _cache_set(_VT_CACHE, key, result)
                    return result

                data = report_resp.json()
                stats = (
                    data.get("data", {})
                    .get("attributes", {})
                    .get("last_analysis_stats", {})
                )
                malicious  = stats.get("malicious", 0)
                suspicious = stats.get("suspicious", 0)
                harmless   = stats.get("harmless", 0)
                total      = malicious + suspicious + harmless + stats.get("undetected", 0)

                if total == 0:
                    verdict    = "unknown"
                    confidence = 0.0
                elif malicious >= 3:
                    verdict    = "malicious"
                    confidence = min(0.5 + (malicious / max(total, 1)) * 0.5, 0.99)
                elif malicious >= 1 or suspicious >= 3:
                    verdict    = "suspicious"
                    confidence = 0.55 + (malicious + suspicious * 0.5) / max(total, 1) * 0.3
                else:
                    verdict    = "clean"
                    confidence = harmless / max(total, 1) * 0.7

                result = {
                    "source":     "virustotal",
                    "verdict":    verdict,
                    "confidence": round(confidence, 3),
                    "raw":        {
                        "malicious":  malicious,
                        "suspicious": suspicious,
                        "harmless":   harmless,
                        "total":      total,
                    },
                }
                _cache_set(_VT_CACHE, key, result)
                return result

        except Exception as exc:
            logger.debug("VirusTotal error: %s", exc)
            return {
                "source":     "virustotal",
                "verdict":    "unknown",
                "confidence": 0.0,
                "raw":        {"error": str(exc)},
            }


# ── Source 4: Domain age heuristic ────────────────────────────────────────────

_YOUNG_THRESHOLD_DAYS = 30   # < 30 days → suspicious (almost always phishing)
_VERY_YOUNG_DAYS      = 7    # < 7 days  → malicious confidence, linear scale


async def check_domain_age_heuristic(url: str) -> dict:
    """
    Wraps existing WHOIS domain-age logic into the normalized shape.

    Catches what ALL blocklists can't: a brand-new domain launched hours ago
    specifically for a phishing campaign.  Phishing operators register domains
    and launch campaigns within the same day precisely because they know that
    blocklists update too slowly to catch them.

    Thresholds:
      < 7 days  → malicious  (confidence scales 0.6→0.9 with freshness)
      7–30 days → suspicious (confidence 0.4–0.6)
      ≥ 30 days → clean      (low penalty)
      None      → unknown    (WHOIS unavailable / privacy-protected)
    """
    extracted = tldextract.extract(url)
    domain = (
        f"{extracted.domain}.{extracted.suffix}"
        if extracted.suffix else extracted.domain
    )

    key = _url_key(domain)
    cached = _cache_get(_AGE_CACHE, key)
    if cached:
        return cached

    try:
        from backend.url_analysis.whois_checker import get_domain_age_days
        age_days = await asyncio.to_thread(get_domain_age_days, domain)

        if age_days is None:
            result = {
                "source":     "domain_age_heuristic",
                "verdict":    "unknown",
                "confidence": 0.0,
                "raw":        {"age_days": None, "reason": "WHOIS unavailable"},
            }
        elif age_days < _VERY_YOUNG_DAYS:
            # Very fresh domain: linear confidence 0.60 → 0.90 as age→0
            conf = 0.90 - (age_days / _VERY_YOUNG_DAYS) * 0.30
            result = {
                "source":     "domain_age_heuristic",
                "verdict":    "malicious",
                "confidence": round(conf, 3),
                "raw":        {"age_days": age_days, "threshold_days": _VERY_YOUNG_DAYS},
            }
        elif age_days < _YOUNG_THRESHOLD_DAYS:
            conf = 0.40 + (1 - age_days / _YOUNG_THRESHOLD_DAYS) * 0.20
            result = {
                "source":     "domain_age_heuristic",
                "verdict":    "suspicious",
                "confidence": round(conf, 3),
                "raw":        {"age_days": age_days, "threshold_days": _YOUNG_THRESHOLD_DAYS},
            }
        else:
            result = {
                "source":     "domain_age_heuristic",
                "verdict":    "clean",
                "confidence": min(0.1 + age_days / 365 * 0.4, 0.50),
                "raw":        {"age_days": age_days},
            }

        _cache_set(_AGE_CACHE, key, result)
        return result

    except Exception as exc:
        logger.debug("Domain age heuristic error: %s", exc)
        return {
            "source":     "domain_age_heuristic",
            "verdict":    "unknown",
            "confidence": 0.0,
            "raw":        {"error": str(exc)},
        }
