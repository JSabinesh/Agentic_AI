"""job-normalizer service: deterministic schema enforcement, deduplication, and URL fallback generation."""

from typing import Dict, Any


def normalize_job(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic normalizer — converts raw job data into the NextRole standard schema."""
    company = raw.get("company", "Unknown Company")
    title   = raw.get("role") or raw.get("title", "Unknown Role")
    loc     = raw.get("location") or raw.get("country") or "Remote"

    url = raw.get("url") or raw.get("application_url", "")
    if not url or not url.startswith("http"):
        comp_q  = company.replace(" ", "+")
        title_q = title.replace(" ", "+")
        loc_q   = loc.replace(" ", "+")
        url     = f"https://www.google.com/search?q={comp_q}+{title_q}+{loc_q}+job+posting+careers"

    return {
        "company":         company,
        "title":           title,
        "location":        loc,
        "work_mode":       raw.get("work_mode") or raw.get("type", "Full-time"),
        "salary":          raw.get("salary", ""),
        "experience":      raw.get("experience", ""),
        "skills":          raw.get("tags") or raw.get("skills", []),
        "description":     raw.get("description", ""),
        "source":          raw.get("source", "Direct Posting"),
        "posted_date":     raw.get("posted") or raw.get("posted_date", "Recently"),
        "application_url": url,
        "match_score":     int(raw.get("match", 0)),
        "match_detail":    raw.get("match_detail", {}),
        "apply_options":   raw.get("apply_options", []),
    }
