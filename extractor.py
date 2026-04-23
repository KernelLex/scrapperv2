"""
extractor.py — Converts raw search results into structured lead dicts.

Strategy (no Selenium):
  1. Parse phone / email / Instagram URL from the snippet alone.
  2. Optionally fetch the linked page (with a polite User-Agent + timeout)
     to extract richer contact info from the HTML.
  3. Fall back gracefully if the page is unreachable.
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Optional

from utils import (
    clean_text,
    truncate,
    extract_phones,
    extract_emails,
    extract_instagram_url,
    is_valid_url,
    is_social_url,
    is_shallow_site,
    normalise_url,
    rate_limit,
    get_logger,
)

logger = get_logger("extractor")

# ─── HTTP Settings ────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LeadResearchBot/1.0; "
        "+https://github.com/yourusername/lead-research)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_PAGE_TIMEOUT  = 10   # seconds
_MAX_PAGE_SIZE = 500_000  # bytes — skip huge pages


# ─── Page Fetcher ─────────────────────────────────────────────────────────────

def fetch_page(url: str) -> Optional[str]:
    """Fetch plain HTML text for `url` respecting size and timeout limits."""
    rate_limit("http", min_gap_seconds=1.0)
    try:
        with requests.get(
            url,
            headers=_HEADERS,
            timeout=_PAGE_TIMEOUT,
            stream=True,
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return None
            chunks: list[bytes] = []
            size = 0
            for chunk in resp.iter_content(chunk_size=8192):
                chunks.append(chunk)
                size += len(chunk)
                if size > _MAX_PAGE_SIZE:
                    break
            return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Page fetch failed for %s: %s", url, e)
        return None


# ─── Contact Extractor ────────────────────────────────────────────────────────

def extract_contacts_from_html(html: str, base_url: str = "") -> dict:
    """
    Parse HTML with BeautifulSoup and extract:
      - phones, emails, instagram_url, website_url, description, has_broken_links
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style noise
    for tag in soup(["script", "style", "noscript", "meta"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    text = clean_text(text)

    phones   = extract_phones(text)
    emails   = extract_emails(text)
    ig_url   = extract_instagram_url(text)

    # Also check all <a href> tags for social links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "instagram.com" in href and not ig_url:
            ig_url = extract_instagram_url(href) or ig_url
        if "wa.me" in href or "whatsapp" in href.lower():
            phones.extend(extract_phones(href))

    # Website: look for a canonical link or the base_url itself
    canonical = soup.find("link", rel="canonical")
    website   = canonical["href"] if canonical and canonical.get("href") else base_url

    # Bio/description from meta description
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = ""
    if desc_tag and desc_tag.get("content"):
        description = clean_text(desc_tag["content"])
    if not description:
        # First non-trivial paragraph
        for p in soup.find_all("p"):
            t = clean_text(p.get_text())
            if len(t) > 40:
                description = truncate(t, 300)
                break

    return {
        "phones":      phones,
        "emails":      emails,
        "instagram_url": ig_url,
        "website_url": website,
        "description": description,
    }


# ─── Instagram Snippet Parser ──────────────────────────────────────────────────

_IG_FOLLOWERS_RE = re.compile(
    r"([\d,.]+[KkMm]?)\s*(?:Followers|followers|follower)"
)

def parse_instagram_snippet(snippet: str) -> dict:
    """Extract follower count hint from an Instagram search snippet."""
    result = {"followers_approx": None}
    m = _IG_FOLLOWERS_RE.search(snippet)
    if m:
        raw = m.group(1).replace(",", "")
        multiplier = 1
        if raw[-1].lower() == "k":
            multiplier = 1_000
            raw = raw[:-1]
        elif raw[-1].lower() == "m":
            multiplier = 1_000_000
            raw = raw[:-1]
        try:
            result["followers_approx"] = int(float(raw) * multiplier)
        except ValueError:
            pass
    return result


# ─── Name Guesser ─────────────────────────────────────────────────────────────

def guess_name(title: str, link: str, sector: str) -> str:
    """Heuristically derive a business/person name from the page title."""
    # Strip common suffixes
    name = re.sub(
        r"\s*[-|—–]\s*.*(instagram|facebook|yelp|justdial|sulekha|google).*",
        "",
        title,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\s*[\|\-–]\s*.*$", "", name).strip()

    # If the link is an Instagram profile, use the handle as fallback
    if not name and "instagram.com" in link:
        parts = urlparse(link).path.strip("/").split("/")
        if parts:
            name = parts[0].replace(".", " ").replace("_", " ").title()

    return clean_text(name) or "Unknown"


# ─── Main Lead Builder ────────────────────────────────────────────────────────

def build_lead(
    raw: dict,
    fetch_pages: bool = True,
) -> Optional[dict]:
    """
    Convert one raw search result into a lead dict.
    Returns None if the result is clearly not a useful lead.
    """
    title   = raw.get("title", "")
    link    = raw.get("link", "")
    snippet = raw.get("snippet", "")
    sector  = raw.get("sector", "")
    city    = raw.get("city", "")
    query   = raw.get("query", "")

    if not link or not is_valid_url(link):
        return None

    # Aggregate text for quick parsing
    combined_text = f"{title} {snippet}"

    phones        = extract_phones(combined_text)
    emails        = extract_emails(combined_text)
    ig_from_snippet = extract_instagram_url(combined_text)
    ig_url        = ig_from_snippet

    # Detect if the result itself IS an Instagram URL
    is_ig_result = "instagram.com" in link
    if is_ig_result:
        ig_url = ig_url or extract_instagram_url(link) or link

    website_url   = "" if is_ig_result or is_social_url(link) else link
    description   = truncate(clean_text(snippet), 300)
    followers_approx = None

    if is_ig_result:
        ig_meta = parse_instagram_snippet(snippet)
        followers_approx = ig_meta.get("followers_approx")

    # Optionally fetch the landing page for richer data
    if fetch_pages and not is_ig_result and not is_social_url(link):
        html = fetch_page(link)
        if html:
            page_data = extract_contacts_from_html(html, base_url=link)
            phones  = phones or page_data["phones"]
            emails  = emails or page_data["emails"]
            ig_url  = ig_url or page_data["instagram_url"]
            if not description and page_data["description"]:
                description = page_data["description"]
            if not website_url and page_data["website_url"]:
                website_url = page_data["website_url"]

    # Normalise
    ig_url      = normalise_url(ig_url)      if ig_url      else ""
    website_url = normalise_url(website_url) if website_url else ""
    phone_str   = ", ".join(phones)  if phones  else ""
    email_str   = ", ".join(emails)  if emails  else ""

    name = guess_name(title, link, sector)

    lead = {
        "name":              name,
        "sector":            sector,
        "city":              city,
        "instagram_url":     ig_url,
        "website_url":       website_url,
        "phone":             phone_str,
        "email":             email_str,
        "description":       description,
        "source_url":        link,
        "source_query":      query,
        "followers_approx":  followers_approx,
        "has_instagram":     bool(ig_url),
        "has_phone":         bool(phone_str),
        "has_email":         bool(email_str),
        "is_shallow_site":   is_shallow_site(link),
        "tag":               "Untagged",
    }
    return lead


# ─── Batch Extractor ──────────────────────────────────────────────────────────

def extract_leads(
    raw_results: list[dict],
    fetch_pages: bool = True,
    progress_callback=None,
) -> list[dict]:
    """Convert a list of raw search results into a list of lead dicts."""
    leads: list[dict] = []
    total = len(raw_results)

    for i, raw in enumerate(raw_results):
        if progress_callback:
            progress_callback(i / max(total, 1), f"🔎 Extracting lead {i+1}/{total} …")

        lead = build_lead(raw, fetch_pages=fetch_pages)
        if lead:
            leads.append(lead)

    if progress_callback:
        progress_callback(1.0, f"✅ Extracted {len(leads)} leads")

    logger.info("Extracted %d leads from %d raw results.", len(leads), total)
    return leads
