"""job-analyzer agent: extracts structured requirements, seniority, and domain criteria from JDs."""

import re
import json
from typing import Dict, Any
from local_app.agents.common import generate_llm


def run_job_analyzer(jd_text: str) -> Dict[str, Any]:
    """Extracts structured requirements from the Job Description."""
    prompt = (
        f"You are `job-analyzer`. Extract structured requirements from this JD.\n\n"
        f"JD:\n{jd_text[:5000]}\n\n"
        'Return JSON ONLY:\n'
        '{"role":"","seniority":"","required_skills":[],"preferred_skills":[],'
        '"responsibilities":[],"domain_knowledge":[],"leadership_expected":false,'
        '"years_experience":0,"implied_requirements":[]}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Strict JD parser. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[Warning] job-analyzer parse error: {e}")
        return {
            "role": "Target Role",
            "seniority": "Senior",
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "domain_knowledge": [],
            "leadership_expected": False,
            "years_experience": 3,
            "implied_requirements": []
        }
