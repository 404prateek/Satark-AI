"""
HTTP redirect follower.

Phishing pages almost always redirect through at least one URL shortener
or cloaking proxy before landing on the actual malicious page.
Following the chain lets us analyse the *final* destination rather than
the obfuscated entry point.
"""

import logging
from typing import Optional
from urllib.parse import urlparse

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_TIMEOUT_PER_HOP = 3          # seconds
_DEFAULT_MAX_HOPS = 5
_USER_AGENT = "Mozilla/5.0 (SatarkAI redirect-scanner)"


def _build_session() -> Session:
    """
    Creates a Requests session with a single retry on connection errors.
    Redirects are NOT followed automatically so we can record each hop.
    """
    session = Session()
    adapter = HTTPAdapter(max_retries=Retry(total=1, backoff_factor=0.3))
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def follow_redirects(
    url: str,
    max_hops: int = _DEFAULT_MAX_HOPS,
) -> dict:
    """
    Follows HTTP redirects manually, recording each hop in the chain.

    Args:
        url:      The initial URL to resolve.
        max_hops: Maximum number of redirects to follow (default 5).

    Returns:
        dict with keys:
          - final_url    (str):        The last URL in the chain.
          - redirect_chain (list[str]): All URLs visited, including the first.
          - hop_count    (int):        Number of redirects followed (0 = no redirect).
          - error        (str | None): Error message if traversal was cut short.
    """
    result: dict = {
        "final_url": url,
        "redirect_chain": [url],
        "hop_count": 0,
        "error": None,
    }

    if not _is_valid_url(url):
        result["error"] = f"Invalid starting URL: {url}"
        return result

    current_url = url
    session = _build_session()

    try:
        for hop in range(max_hops):
            try:
                response = session.get(
                    current_url,
                    allow_redirects=False,   # manual redirect tracking
                    timeout=_TIMEOUT_PER_HOP,
                    stream=True,             # avoid downloading large bodies
                )
                # Close body immediately — we only care about headers
                response.close()

                if response.is_redirect or response.is_permanent_redirect:
                    location: Optional[str] = response.headers.get("Location")
                    if not location:
                        break

                    # Handle relative redirect URLs
                    if location.startswith("/"):
                        parsed = urlparse(current_url)
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"

                    if not _is_valid_url(location):
                        result["error"] = f"Invalid redirect location: {location}"
                        break

                    current_url = location
                    result["redirect_chain"].append(current_url)
                    result["hop_count"] += 1
                else:
                    # Non-redirect response — we've reached the final destination
                    break

            except requests.exceptions.Timeout:
                result["error"] = f"Timeout at hop {hop + 1} for URL: {current_url}"
                break
            except requests.exceptions.TooManyRedirects:
                result["error"] = "Too many redirects"
                break
            except requests.exceptions.RequestException as exc:
                result["error"] = f"Request failed at hop {hop + 1}: {exc}"
                break
        else:
            result["error"] = f"Reached max hop limit ({max_hops})"

    finally:
        session.close()

    result["final_url"] = current_url
    return result
