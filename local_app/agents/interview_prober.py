"""interview-prober agent: analyzes candidate answers for vagueness and generates targeted challenge probes."""

import re
import json
from typing import Optional
from local_app.agents.common import generate_llm


def run_interview_prober(question: str, answer: str) -> Optional[str]:
    """Probes candidate answer for vagueness, missing metrics, or passive voice and injects follow-ups."""
    prompt = (
        f"You are `interview-prober`. Analyze this candidate answer for:\n"
        f"- Specificity (are claims vague?), Evidence (were numbers/facts given?), "
        f"Personal contribution (did they use 'I' or 'we'?), Completeness\n\n"
        f"Question: {question}\nAnswer: {answer}\n\n"
        'Return JSON: {"needs_probe": true/false, "probe_question": "<follow-up or empty>", "reason": "<brief reason>"}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Strict answer prober. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        data = json.loads(raw.strip())
        return data.get("probe_question") if data.get("needs_probe") else None
    except Exception:
        return None
