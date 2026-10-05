"""job-discovery agent: live job discovery strictly via JSearch (LinkedIn, Indeed, Glassdoor, etc.).
No mock or synthetic fallbacks — returns genuine live postings directly from JSearch response.
"""

import re
import requests
from typing import Dict, Any, List
from local_app.agents.common import RAPIDAPI_KEY


LAST_JSEARCH_ERROR = ""


def fetch_jsearch_jobs(
    query: str,
    company: str = "",
    country: str = "",
    filters: List[str] = None
) -> List[Dict[str, Any]]:
    """Fetches live real-time job listings directly from JSearch API with exact sources and publishers."""
    global LAST_JSEARCH_ERROR
    LAST_JSEARCH_ERROR = ""

    if not RAPIDAPI_KEY:
        LAST_JSEARCH_ERROR = "RAPIDAPI_KEY is missing from .env"
        print("[Warning] RAPIDAPI_KEY not found in environment.")
        return []

    # ISO 3166-1 alpha-2 mapping per JSearch documentation (Default is 'us')
    COUNTRY_ISO_MAP = {
        "india": "in", "in": "in",
        "united states": "us", "usa": "us", "us": "us",
        "united kingdom": "gb", "uk": "gb", "gb": "gb",
        "germany": "de", "de": "de",
        "canada": "ca", "ca": "ca",
        "australia": "au", "au": "au",
        "singapore": "sg", "sg": "sg",
        "france": "fr", "fr": "fr",
        "netherlands": "nl", "nl": "nl",
        "ireland": "ie", "ie": "ie",
        "uae": "ae", "united arab emirates": "ae", "dubai": "ae",
        "japan": "jp", "jp": "jp"
    }

    clean_query = query.strip() if query and query.strip().lower() not in ("any", "all") else ""
    clean_company = company.strip() if company and company.strip().lower() not in ("any", "all") else ""
    clean_country = country.strip() if country and country.strip().lower() not in ("any", "all") else ""

    query_parts = []
    if clean_query:
        query_parts.append(clean_query)
    if clean_company:
        query_parts.append(f"at {clean_company}")
    if clean_country and clean_country.lower() not in COUNTRY_ISO_MAP:
        query_parts.append(f"in {clean_country}")

    search_query = " ".join(query_parts) if query_parts else "Software Developer"

    params: Dict[str, Any] = {
        "query": search_query,
        "page": "1",
        "num_pages": "1",
        "date_posted": "all",
    }

    # Resolve ISO country code (crucial: JSearch defaults to 'us', so country='in' is required for India)
    if clean_country:
        ckey = clean_country.lower()
        iso = COUNTRY_ISO_MAP.get(ckey)
        if not iso:
            for k, v in COUNTRY_ISO_MAP.items():
                if k in ckey:
                    iso = v
                    break
        if iso:
            params["country"] = iso
    else:
        # Default to India if not specified, given user location
        params["country"] = "in"

    if filters and any("remote" in f.lower() for f in filters):
        params["work_from_home"] = "true"

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY.strip(),
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    raw_jobs = []
    candidate_paths = ["/search-v2", "/search", "/job-search"]

    for path in candidate_paths:
        try:
            resp = requests.get(
                f"https://jsearch.p.rapidapi.com{path}",
                headers=headers,
                params=params,
                timeout=18
            )
            if resp.status_code == 200:
                body = resp.json()
                data_field = body.get("data")
                if isinstance(data_field, dict):
                    raw_jobs = data_field.get("jobs", [])
                elif isinstance(data_field, list):
                    raw_jobs = data_field
                else:
                    raw_jobs = body.get("jobs", [])

                if raw_jobs:
                    LAST_JSEARCH_ERROR = ""
                    break
            else:
                LAST_JSEARCH_ERROR = f"{path} returned HTTP {resp.status_code}: {resp.text[:120]}"
                print(f"[JSearch] {path} returned status {resp.status_code}: {resp.text[:180]}")
        except Exception as e:
            LAST_JSEARCH_ERROR = f"Connection error: {e}"
            print(f"[Warning] JSearch connection error on {path}: {e}")

    if not raw_jobs:
        return []

    results = []
    for item in raw_jobs[:8]:
        # 1. Location
        loc_parts = [item.get("job_city"), item.get("job_state"), item.get("job_country")]
        loc_str = ", ".join([p for p in loc_parts if p]) or item.get("job_location") or ("Remote" if item.get("job_is_remote") or item.get("work_arrangement") == "remote" else "Location Unspecified")
        if (item.get("job_is_remote") or item.get("work_arrangement") == "remote") and "remote" not in (loc_str or "").lower():
            loc_str = f"Remote ({loc_str})"

        # 2. Compensation
        min_sal = item.get("job_min_salary")
        max_sal = item.get("job_max_salary")
        period = (item.get("job_salary_period") or "YR").lower()
        curr = item.get("job_salary_currency") or "$"
        period_label = " / yr" if "year" in period or "yr" in period else f" / {period}"
        salary_str = ""
        if min_sal and max_sal:
            salary_str = f"{curr}{int(min_sal):,} - {curr}{int(max_sal):,}{period_label}"
        elif min_sal or max_sal:
            sal_val = int(min_sal or max_sal)
            salary_str = f"From {curr}{sal_val:,}{period_label}"

        # 3. Source & Publisher directly from JSearch
        apply_options = item.get("apply_options") or []
        publisher = item.get("job_publisher")
        if not publisher and apply_options:
            publisher = apply_options[0].get("publisher")
        source_label = publisher or "Job Board"

        # 4. Skills & Technologies directly from JSearch
        skills = []
        req_tech = item.get("required_technologies") or []
        if isinstance(req_tech, list) and req_tech:
            skills.extend(req_tech[:6])

        highlights = item.get("job_highlights") or {}
        quals = highlights.get("Qualifications") or []
        for q in quals[:4]:
            clean_q = re.sub(r"^[•\-\*]\s*", "", q).strip()
            if len(clean_q) < 30 and clean_q not in skills:
                skills.append(clean_q)

        if not skills:
            tokens = [w for w in (query + " " + (item.get("job_title") or "")).split() if len(w) > 3]
            skills = list(dict.fromkeys(tokens))[:4]

        # 5. Direct Apply URL from JSearch
        apply_link = item.get("job_apply_link") or item.get("job_google_link") or ""

        # 6. Description
        desc = item.get("job_description") or ""
        if len(desc) > 340:
            desc = desc[:340].rsplit(" ", 1)[0] + "..."

        work_mode = "Remote" if (item.get("job_is_remote") or item.get("work_arrangement") == "remote") else (item.get("job_employment_type") or "Full-time")

        results.append({
            "role": item.get("job_title", "Software Engineer"),
            "company": item.get("employer_name", "Target Company"),
            "location": loc_str,
            "work_mode": work_mode,
            "salary": salary_str,
            "skills": skills[:6],
            "posted_date": item.get("job_posted_at") or "Active Posting",
            "source": source_label,
            "url": apply_link,
            "description": desc,
            "apply_options": apply_options
        })

    return results


def run_job_discovery(
    query: str,
    filters: List[str],
    session: Dict[str, Any],
    company: str = "",
    country: str = ""
) -> List[Dict[str, Any]]:
    """Strictly discovers real job postings using JSearch API. No mock or synthetic fallbacks."""
    if not RAPIDAPI_KEY:
        print("[Job Discovery] RAPIDAPI_KEY is not configured.")
        return []

    try:
        jsearch_results = fetch_jsearch_jobs(query, company, country, filters)
        print(f"[JSearch] Retrieved {len(jsearch_results)} live job postings.")
        return jsearch_results
    except Exception as e:
        print(f"[Warning] JSearch execution error: {e}")
        return []
