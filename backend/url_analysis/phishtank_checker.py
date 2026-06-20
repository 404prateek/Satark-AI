"""
Checks PhishTank's free community API for known phishing URLs.

Usage:
  Set PHISHTANK_API_KEY in your environment. PhishTank API keys are free:
  register at https://www.phishtank.com/api_register.php

Behaviour:
  - A simple in-memory TTL cache avoids hammering the API.
  - All network or API failures silently return False (fail-open) so
    the rest of the analysis pipeline is never blocked by this check.
"""

import hashlib
import time
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── TTL cache ─────────────────────────────────────────────────────────────────
# { url_sha256: (is_phishing: bool, expiry_timestamp: float) }
_CACHE: dict[str, tuple[bool, float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour

PHISHTANK_API_URL = "https://checkurl.phishtank.com/checkurl/"
PHISHTANK_API_KEY = os.getenv("PHISHTANK_API_KEY", "")


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _get_cached(url: str) -> Optional[bool]:
    key = _cache_key(url)
    entry = _CACHE.get(key)
    if entry is None:
        return None
    result, expiry = entry
    if time.monotonic() > expiry:
        del _CACHE[key]
        return None
    return result


def _set_cache(url: str, is_phishing: bool) -> None:
    key = _cache_key(url)
    _CACHE[key] = (is_phishing, time.monotonic() + _CACHE_TTL_SECONDS)


def check_phishtank(url: str) -> bool:
    """
    Returns True if the URL is listed as a confirmed phishing URL on PhishTank.
    Returns False on any failure (network error, API key missing, rate limit).

    Args:
        url: The fully-qualified URL to check.

    Returns:
        bool: True = confirmed phishing, False = not found / unknown.
    """
    cached = _get_cached(url)
    if cached is not None:
        logger.debug(f"PhishTank cache hit for URL hash")
        return cached

    if not PHISHTANK_API_KEY:
        logger.warning("PHISHTANK_API_KEY not set — skipping PhishTank check")
        return False

    try:
        response = requests.post(
            PHISHTANK_API_URL,
            data={
                "url": url,
                "format": "json",
                "app_key": PHISHTANK_API_KEY,
            },
            headers={"User-Agent": "SatarkAI/1.0 phishing-detector"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        # PhishTank response schema:
        # { "results": { "in_database": bool, "phish_id": str, "valid": bool, ... } }
        results = data.get("results", {})
        in_database = results.get("in_database", False)
        is_valid_phish = results.get("valid", False)
        is_phishing = bool(in_database and is_valid_phish)

        _set_cache(url, is_phishing)
        return is_phishing

    except requests.exceptions.Timeout:
        logger.warning("PhishTank API timed out — failing open")
    except requests.exceptions.RequestException as exc:
        logger.warning(f"PhishTank API error: {exc} — failing open")
    except (KeyError, ValueError) as exc:
        logger.warning(f"PhishTank malformed response: {exc} — failing open")

    return False
