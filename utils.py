"""
utils.py — Shared helpers: rate limiting, text cleaning, phone/email extraction,
URL validation, deduplication, and logging setup.
"""

import re
import time
import logging
import hashlib
from urllib.parse import urlparse
from typing import Optional

import phonenumbers
import validators

# ─── Logging ────────────────────────────────────────────────────────────────

def get_logger(name: str = "lead_scraper") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = get_logger()

# ─── Rate Limiting ───────────────────────────────────────────────────────────

_last_call_times: dict[str, float] = {}


def rate_limit(key: str = "default", min_gap_seconds: float = 1.5) -> None:
    """Block until at least `min_gap_seconds` have elapsed since the last call
    for the given `key`."""
    now = time.monotonic()
    last = _last_call_times.get(key, 0.0)
    wait = min_gap_seconds - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_call_times[key] = time.monotonic()


# ─── Text Cleaning ───────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Strip excessive whitespace and control characters."""
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def truncate(text: str, max_len: int = 300) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


# ─── Phone Extraction ────────────────────────────────────────────────────────

# Matches common phone formats including WhatsApp links
_PHONE_PATTERNS = [
    r"(?:(?:\+|00)91[-\s]?)?[789]\d{9}",     # Indian mobile
    r"\+?\d[\d\s\-\(\)]{8,14}\d",             # Generic international
    r"wa\.me/(\d{10,15})",                    # WhatsApp short-link
    r"api\.whatsapp\.com/send\?phone=(\d+)",  # WhatsApp API link
]

_PHONE_REGEX = re.compile("|".join(_PHONE_PATTERNS))


def extract_phones(text: str, default_region: str = "IN") -> list[str]:
    """Return a deduplicated list of E.164-formatted phone numbers found in `text`."""
    found: list[str] = []
    seen: set[str] = set()

    for match in _PHONE_REGEX.finditer(text):
        raw = match.group(0).strip()
        # Pull group from whatsapp patterns if needed
        for g in match.groups():
            if g:
                raw = g
                break
        raw = re.sub(r"[\s\-\(\)]", "", raw)
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
                if e164 not in seen:
                    seen.add(e164)
                    found.append(e164)
        except Exception:
            pass
    return found


# ─── Email Extraction ────────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}"
)

_EMAIL_BLOCKLIST = {
    "sentry.io", "example.com", "yourdomain.com", "domain.com",
    "email.com", "noreply", "no-reply",
}


def extract_emails(text: str) -> list[str]:
    """Return a deduplicated list of valid-looking email addresses."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _EMAIL_REGEX.finditer(text):
        email = m.group(0).lower()
        domain = email.split("@")[-1]
        if any(b in domain for b in _EMAIL_BLOCKLIST):
            continue
        if validators.email(email) and email not in seen:
            seen.add(email)
            found.append(email)
    return found


# ─── Instagram URL Extraction ────────────────────────────────────────────────

_IG_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{1,30})/?",
    re.IGNORECASE,
)

_IG_RESERVED = {
    "p", "reel", "reels", "explore", "accounts", "stories",
    "tv", "live", "tags", "locations", "direct",
}


def extract_instagram_url(text: str) -> Optional[str]:
    """Return the first valid Instagram *profile* URL found in `text`."""
    for m in _IG_REGEX.finditer(text):
        handle = m.group(1).lower()
        if handle and handle not in _IG_RESERVED:
            return f"https://www.instagram.com/{handle}/"
    return None


# ─── URL Helpers ─────────────────────────────────────────────────────────────

_SOCIAL_DOMAINS = {
    "instagram.com", "facebook.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "linktr.ee", "linktree.com",
    "threads.net", "t.me", "wa.me",
}

_SHALLOW_SITE_DOMAINS = {"linktr.ee", "linktree.com", "bio.link", "beacons.ai"}


def is_valid_url(url: str) -> bool:
    return bool(validators.url(url))


def is_social_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == sd or host.endswith("." + sd) for sd in _SOCIAL_DOMAINS)
    except Exception:
        return False


def is_shallow_site(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == sd or host.endswith("." + sd) for sd in _SHALLOW_SITE_DOMAINS)
    except Exception:
        return False


def normalise_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


# ─── Deduplication ───────────────────────────────────────────────────────────

def fingerprint(name: str, city: str, instagram_url: str = "") -> str:
    """Create a stable hash for a lead to detect duplicates."""
    key = f"{name.lower().strip()}|{city.lower().strip()}|{instagram_url.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate_leads(leads: list[dict]) -> list[dict]:
    """Remove duplicate leads by fingerprint, keeping the one with more data."""
    seen: dict[str, dict] = {}
    for lead in leads:
        fp = fingerprint(
            lead.get("name", ""),
            lead.get("city", ""),
            lead.get("instagram_url", ""),
        )
        if fp not in seen:
            seen[fp] = lead
        else:
            # Keep whichever has more non-empty fields
            existing_score = sum(1 for v in seen[fp].values() if v)
            new_score = sum(1 for v in lead.values() if v)
            if new_score > existing_score:
                seen[fp] = lead
    return list(seen.values())
