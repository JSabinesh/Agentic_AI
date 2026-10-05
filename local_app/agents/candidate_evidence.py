"""candidate-evidence agent: rigorously matches candidate resume to JD requirements with zero fabrication."""

import re
import json
from typing import Dict, Any
from local_app.agents.common import generate_llm


def run_candidate_evidence(resume_text: str, jd_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Finds actual textual evidence in the resume for each JD requirement."""
    all_skills = jd_analysis.get("required_skills", []) + jd_analysis.get("preferred_skills", [])
    skills_str = ", ".join(all_skills[:20])
    prompt = (
        f"You are `candidate-evidence`. For each skill/requirement, find real evidence in the resume.\n"
        f"Zero fabrication: only cite what is explicitly written.\n\n"
        f"Skills to evaluate: {skills_str}\n\nResume:\n{resume_text[:5000]}\n\n"
        'Return JSON ONLY: {"evidence_map": {"<skill>": {"strength": "strong|partial|gap|unknown", "evidence": "<quote or empty>"}}, '
        '"overlaps": ["<proven strength statement>"], "gaps": [{"name": "<skill>", "desc": "<why missing>", "sev": "high|medium|low"}]}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Zero-fabrication evidence extractor. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[Warning] candidate-evidence parse error: {e}")
        return {"evidence_map": {}, "overlaps": [], "gaps": []}
