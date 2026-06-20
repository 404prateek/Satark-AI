"""
WHOIS data fetcher for domain age and registrar information.

Domain age is the single most reliable free signal for phishing:
the vast majority of phishing domains are registered hours to days
before the campaign, whereas legitimate banking/government domains
have existed for years.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import whois  # python-whois

logger = logging.getLogger(__name__)


def _parse_date(value) -> Optional[datetime]:
    """Normalise whois date fields which can be str, datetime, or list."""
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0]
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def get_domain_age_days(domain: str) -> Optional[int]:
    """
    Returns the age of a domain in days from its WHOIS creation date.

    Returns:
        int:  Age in days (0+ means registered today or later).
        None: WHOIS lookup failed, timed out, or creation date not available.
    """
    try:
        w = whois.whois(domain)
        created = _parse_date(w.creation_date)
        if created is None:
            return None
        age = (datetime.now(timezone.utc) - created).days
        return max(age, 0)
    except Exception as exc:
        logger.debug(f"WHOIS age lookup failed for '{domain}': {exc}")
        return None


def get_whois_info(domain: str) -> dict:
    """
    Returns a structured WHOIS summary for a domain.

    Returns a dict with keys: registrar, country, created, updated.
    Any field that cannot be resolved is None.
    """
    result: dict = {
        "registrar": None,
        "country": None,
        "created": None,
        "updated": None,
    }

    try:
        w = whois.whois(domain)

        registrar = w.get("registrar")
        if isinstance(registrar, list):
            registrar = registrar[0]
        result["registrar"] = str(registrar).strip() if registrar else None

        country = w.get("country")
        if isinstance(country, list):
            country = country[0]
        result["country"] = str(country).strip() if country else None

        created = _parse_date(w.creation_date)
        result["created"] = created.isoformat() if created else None

        updated = _parse_date(w.updated_date)
        result["updated"] = updated.isoformat() if updated else None

    except Exception as exc:
        logger.debug(f"WHOIS full lookup failed for '{domain}': {exc}")

    return result
