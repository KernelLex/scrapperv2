"""
search.py — Fetches search results using DuckDuckGo (100% free, no API key).

Optionally falls back to SerpAPI or Google Custom Search if keys are set.

Each function returns a list of raw result dicts:
  { "title": str, "link": str, "snippet": str }
"""

import os
import time
from typing import Optional

from utils import rate_limit, get_logger

logger = get_logger("search")

_MAX_RESULTS_PER_QUERY = 10
_REQUEST_TIMEOUT = 15


# ─── Query Builder ────────────────────────────────────────────────────────────

def build_queries(sector: str, city: str) -> list[str]:
    """
    Varied search queries to surface Instagram profiles, business cards,
    directories, and contact pages — all via public search engines.
    """
    return [
        f"{sector} {city} site:instagram.com",
        f"{sector} in {city} instagram portfolio",
        f'"{sector}" "{city}" contact phone WhatsApp',
        f"{sector} {city} email website",
        f"{sector} {city} business",
        f"best {sector} in {city}",
        f"{sector} {city} Instagram followers",
        f"{sector} {city} -justdial -sulekha contact",
    ]


# ─── DuckDuckGo (FREE — Primary) ──────────────────────────────────────────────

def search_duckduckgo(query: str, num: int = 10) -> list[dict]:
    """
    Search via DuckDuckGo using the `duckduckgo-search` library.
    Completely free — no API key, no signup, no quota.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []

    rate_limit("ddg", min_gap_seconds=1.5)
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=min(num, 20)):
                results.append({
                    "title":   r.get("title", ""),
                    "link":    r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception as e:
        logger.warning("DuckDuckGo search error for '%s': %s", query, e)
        # Back-off on rate limit
        if "ratelimit" in str(e).lower() or "202" in str(e):
            logger.info("DDG rate-limited, sleeping 10 s …")
            time.sleep(10)
    return results


# ─── SerpAPI (Optional paid fallback) ─────────────────────────────────────────

def search_serpapi(query: str, api_key: str, num: int = 10) -> list[dict]:
    import requests
    rate_limit("serpapi", min_gap_seconds=1.2)
    params = {
        "q": query, "api_key": api_key,
        "num": min(num, 10), "engine": "google",
        "safe": "active", "hl": "en",
    }
    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return [
            {"title": i.get("title", ""), "link": i.get("link", ""), "snippet": i.get("snippet", "")}
            for i in resp.json().get("organic_results", [])
        ]
    except Exception as e:
        logger.error("SerpAPI error: %s", e)
    return []


# ─── Google Custom Search (Optional paid fallback) ────────────────────────────

def search_gcse(query: str, api_key: str, cx: str, num: int = 10) -> list[dict]:
    import requests
    rate_limit("gcse", min_gap_seconds=1.0)
    params = {"q": query, "key": api_key, "cx": cx, "num": min(num, 10), "safe": "active"}
    try:
        resp = requests.get("https://www.googleapis.com/customsearch/v1",
                            params=params, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return [
            {"title": i.get("title", ""), "link": i.get("link", ""), "snippet": i.get("snippet", "")}
            for i in resp.json().get("items", [])
        ]
    except Exception as e:
        logger.error("GCSE error: %s", e)
    return []


# ─── Unified Entry Point ──────────────────────────────────────────────────────

def run_searches(
    sector: str,
    city: str,
    max_results: int = 50,
    serpapi_key: Optional[str] = None,
    gcse_key: Optional[str] = None,
    gcse_cx: Optional[str] = None,
    progress_callback=None,
) -> list[dict]:
    """
    Run all query templates and aggregate raw results.

    Search priority:
      1. SerpAPI (if SERPAPI_KEY set)
      2. Google CSE (if GCSE_API_KEY + GCSE_CX set)
      3. DuckDuckGo (always available — free fallback and default)
    """
    serpapi_key = serpapi_key or os.getenv("SERPAPI_KEY", "")
    gcse_key    = gcse_key    or os.getenv("GCSE_API_KEY", "")
    gcse_cx     = gcse_cx     or os.getenv("GCSE_CX", "")

    use_serpapi = bool(serpapi_key)
    use_gcse    = bool(gcse_key and gcse_cx)
    use_ddg     = True  # always available

    queries = build_queries(sector, city)
    all_results: list[dict] = []
    seen_links: set[str] = set()

    for i, query in enumerate(queries):
        if len(all_results) >= max_results:
            break

        if progress_callback:
            progress_callback(i / len(queries), f"🔍 Query {i+1}/{len(queries)}: {query[:65]}…")

        per_q = min(10, max_results - len(all_results))
        raw: list[dict] = []

        if use_serpapi:
            raw = search_serpapi(query, serpapi_key, num=per_q)
        elif use_gcse:
            raw = search_gcse(query, gcse_key, gcse_cx, num=per_q)
        else:
            raw = search_duckduckgo(query, num=per_q)

        for r in raw:
            link = r.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                r["query"]  = query
                r["sector"] = sector
                r["city"]   = city
                all_results.append(r)

    if progress_callback:
        progress_callback(1.0, f"✅ Search complete — {len(all_results)} raw results")

    logger.info(
        "Search done. %d unique results for '%s' in '%s'.",
        len(all_results), sector, city,
    )
    return all_results
