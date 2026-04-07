"""Web content scraper with rate-limiting safety and HTML cleaning."""

import logging
import re
from html import unescape
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; ResearcherMan/0.1; +https://example.com)"
)

_TIMEOUT = 20  # seconds


def fetch(url: str, timeout: int = _TIMEOUT) -> Optional[str]:
    """Fetch the raw HTML for *url* and return it, or ``None`` on failure."""
    headers = {"User-Agent": _USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


def extract_text(html: str, max_length: int = 8000) -> str:
    """Strip tags, scripts, styles; return cleaned text up to *max_length*."""
    soup = BeautifulSoup(html, "lxml")

    # Remove boilerplate
    for tag in soup.find_all(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = unescape(text).strip()

    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "…"

    return text


def scrape(url: str, max_length: int = 8000) -> Optional[str]:
    """High-level helper: fetch *url* and return cleaned text."""
    html = fetch(url)
    if html is None:
        return None
    return extract_text(html, max_length=max_length)
