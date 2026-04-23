"""
scoring.py — Compute digital-presence score and lead quality score for each lead.

Digital Presence Score (higher = weaker digital presence = better lead for outreach)
────────────────────────────────────────────────────────────────────────────────────
+3  No website found
+2  Only Linktree / link-in-bio page
+2  Simple/broken website (heuristic)
+1  WhatsApp-only contact method
+2  Poor portfolio signal (no email, no phone)
-5  Strong professional website detected

Lead Quality Score (higher = more actionable)
─────────────────────────────────────────────
+2  Has Instagram URL
+2  Has phone / WhatsApp
+2  Has email
+1  Has website URL
+3  Has both phone AND email
+2  High digital presence score (≥ 5)
-1  No contact info at all
"""

from utils import is_shallow_site, is_valid_url, get_logger

logger = get_logger("scoring")

# ─── Digital Presence Score ───────────────────────────────────────────────────

def digital_presence_score(lead: dict) -> int:
    """
    Return a score representing how *weak* the lead's digital presence is.
    Higher score → easier target for simple digital-services outreach.
    """
    score = 0

    has_website = bool(lead.get("website_url"))
    has_ig      = bool(lead.get("instagram_url"))
    has_phone   = bool(lead.get("phone"))
    has_email   = bool(lead.get("email"))
    website_url = lead.get("website_url", "")
    shallow     = lead.get("is_shallow_site", False) or (
        has_website and is_shallow_site(website_url)
    )

    # ─ No website
    if not has_website:
        score += 3

    # ─ Only Linktree / shallow bio page
    if shallow:
        score += 2

    # ─ Simple website heuristic: has_website but very short domain or
    #   ends with known page-builder slugs
    if has_website and not shallow:
        low = website_url.lower()
        simple_signals = ["wixsite.com", "weebly.com", "carrd.co", "webflow.io",
                          "sites.google.com", "godaddysites.com", "squarespace.com"]
        if any(s in low for s in simple_signals):
            score += 2

    # ─ WhatsApp-only contact (phone but no email)
    if has_phone and not has_email:
        score += 1

    # ─ Poor portfolio: no email and no phone
    if not has_email and not has_phone:
        score += 2

    # ─ Strong professional website penalty
    if has_website and not shallow and has_email and has_phone:
        score -= 5

    return max(score, 0)


# ─── Lead Quality Score ───────────────────────────────────────────────────────

def lead_quality_score(lead: dict, dp_score: int) -> int:
    """
    Return a score representing how actionable / high-quality this lead is.
    Higher score → better lead worth reaching out to.
    """
    score = 0

    if lead.get("instagram_url"):
        score += 2
    if lead.get("phone"):
        score += 2
    if lead.get("email"):
        score += 2
    if lead.get("website_url"):
        score += 1
    if lead.get("phone") and lead.get("email"):
        score += 3   # bonus for full contact info
    if dp_score >= 5:
        score += 2   # weak digital presence is a sales opportunity
    if not lead.get("phone") and not lead.get("email") and not lead.get("instagram_url"):
        score -= 1

    return max(score, 0)


# ─── Follower Filter ──────────────────────────────────────────────────────────

def passes_follower_filter(lead: dict, min_f: int = 0, max_f: int = 99_999_999) -> bool:
    """Return True if the lead's follower count (if known) is within the range."""
    fa = lead.get("followers_approx")
    if fa is None:
        return True   # unknown → don't exclude
    return min_f <= fa <= max_f


# ─── Score All Leads ─────────────────────────────────────────────────────────

def score_leads(leads: list[dict]) -> list[dict]:
    """Add dp_score and quality_score keys to every lead dict in-place."""
    for lead in leads:
        dp   = digital_presence_score(lead)
        qual = lead_quality_score(lead, dp)
        lead["dp_score"]      = dp
        lead["quality_score"] = qual
    logger.info("Scored %d leads.", len(leads))
    return leads


# ─── Apply Filters ────────────────────────────────────────────────────────────

def apply_filters(
    leads: list[dict],
    must_have_instagram: bool = False,
    must_have_contact:   bool = False,
    weak_presence_only:  bool = False,
    min_followers: int = 0,
    max_followers: int = 99_999_999,
) -> list[dict]:
    """Filter scored leads based on user-selected criteria."""
    filtered = []
    for lead in leads:
        if must_have_instagram and not lead.get("instagram_url"):
            continue
        if must_have_contact and not lead.get("phone") and not lead.get("email"):
            continue
        if weak_presence_only and lead.get("dp_score", 0) < 3:
            continue
        if not passes_follower_filter(lead, min_followers, max_followers):
            continue
        filtered.append(lead)

    logger.info(
        "Filters applied: %d/%d leads passed.", len(filtered), len(leads)
    )
    return filtered
