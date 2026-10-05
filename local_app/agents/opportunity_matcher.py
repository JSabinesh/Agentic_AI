"""opportunity-matcher agent: scores discovered job postings against the shared Career Evidence Store."""

import re
import json
from typing import Dict, Any, List
from local_app.agents.common import generate_llm, get_evidence_store
from local_app.agents.job_normalizer import normalize_job


def run_opportunity_matcher(jobs: List[Dict[str, Any]], session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Scores each discovered job against the candidate's Career Evidence Store."""
    store       = get_evidence_store(session)
    skills_map  = store.get("skills", {})
    resume_text = session.get("files", {}).get("/processed/resume.md", "")[:2000]

    scored = []
    for job in jobs:
        job_skills = job.get("skills", [])
        strong_hits = sum(1 for s in job_skills if skills_map.get(s, {}).get("strength") == "strong")
        partial_hits = sum(1 for s in job_skills if skills_map.get(s, {}).get("strength") == "partial")
        total = len(job_skills) or 1
        base_score = min(94, int((strong_hits + partial_hits * 0.5) / total * 100))

        if not skills_map and resume_text:
            try:
                prompt = (
                    f"Score how well this candidate matches this job (0-100). Candidate:\n{resume_text}\n\nJob:\n{json.dumps(job)}\n"
                    'Return JSON: {"score": 0, "strong": [], "gaps": []}'
                )
                raw = generate_llm(prompt, system_instruction="Fast job matcher. Return valid JSON only.")
                raw = re.sub(r"```json\s*", "", raw)
                raw = re.sub(r"```\s*", "", raw)
                llm_data = json.loads(raw.strip())
                base_score = int(llm_data.get("score", 60))
                job["match_detail"] = llm_data
            except Exception:
                base_score = 60

        job["match"] = base_score
        scored.append(normalize_job(job))

    return sorted(scored, key=lambda x: x["match_score"], reverse=True)
