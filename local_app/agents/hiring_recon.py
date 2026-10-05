"""hiring-recon agent: pre-interview reconnaissance analyst feeding the Evidence DB via live web intel."""

import json
from typing import Dict, Any, Optional
from local_app.agents.common import generate_llm, TAVILY_API_KEY


def run_research_agent(
    resume_text: str,
    jd_text: str,
    update_request: Optional[str] = None,
    existing_report: Optional[str] = None,
    prior_memory: Optional[Dict] = None
) -> str:
    """Runs hiring reconnaissance over the target company, culture, stack, and interview process."""
    company_name = "Target Company"
    for line in jd_text.split("\n")[:5]:
        if "-" in line or "\u2014" in line:
            sep = "\u2014" if "\u2014" in line else "-"
            company_name = line.split(sep)[0].replace("#", "").strip()
            break

    web_intel = ""
    if TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            tv = TavilyClient(api_key=TAVILY_API_KEY)
            q1 = tv.search(f"{company_name} company overview business model tech stack", max_results=2)
            q2 = tv.search(f"{company_name} hiring culture glassdoor layoffs funding 2024", max_results=2)
            q3 = tv.search(f"{company_name} interview process experience", max_results=2)
            web_intel = "\n".join([r.get("content", "") for r in q1.get("results", []) + q2.get("results", []) + q3.get("results", [])])
        except Exception as e:
            print(f"[Warning] Tavily recon error: {e}")

    memory_ctx = ""
    if prior_memory:
        past = prior_memory.get("latest_artifacts", {})
        memory_ctx = f"\n\nPRIOR CAREER MEMORY:\n{json.dumps(past, indent=2)[:2000]}"

    sys_prompt = (
        "You are the `research-agent` (hiring-recon) in NextRole.\n"
        "Role: Pre-interview reconnaissance analyst feeding the Evidence DB.\n"
        "Produce: 1) Company snapshot 2) Financial/hiring signals 3) Culture/reputation "
        "4) Role market context & salary band 5) Match analysis (strengths, gaps, focus areas) "
        "6) Interview process intel (rounds, LeetCode frequency, typical questions)."
    )

    if update_request and existing_report:
        prompt = (
            f'UPDATE MODE: "{update_request}"\n\n'
            f"Existing:\n{existing_report}\n\n"
            f"JD:\n{jd_text}\n\n"
            f"Resume:\n{resume_text}{memory_ctx}\n\n"
            f"Update only the relevant section."
        )
    else:
        prompt = (
            f"CREATE MODE:\nCompany: {company_name}\n\nJD:\n{jd_text}\n\n"
            f"Resume:\n{resume_text}\n\nEvidence DB (Web):\n{web_intel[:4000]}{memory_ctx}\n\n"
            f"Generate `#{company_name} Intelligence Report` in Markdown."
        )
    return generate_llm(prompt, system_instruction=sys_prompt)
