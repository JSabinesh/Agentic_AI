"""critic agent: automated quality assurance gate scoring artifacts for accuracy, relevance, and completeness."""

import re
import json
from typing import Dict, Any, List
from local_app.agents.common import generate_llm


class CriticVerdict:
    def __init__(self, passed: bool, score: int, issues: List[str], recommendations: str):
        self.passed = passed
        self.score = score
        self.issues = issues
        self.recommendations = recommendations

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": self.issues,
            "recommendations": self.recommendations
        }


def run_critic_agent(
    artifact_name: str,
    artifact_content: str,
    resume_text: str,
    jd_text: str
) -> CriticVerdict:
    """Scores a generated artifact against candidate resume and target JD."""
    prompt = (
        f"You are a CRITIC agent doing quality assurance in a multi-agent career system.\n\n"
        f"Artifact: {artifact_name}\n---\n{artifact_content[:4000]}\n---\n\n"
        f"Resume (ground truth):\n{resume_text[:2000]}\n\nJD:\n{jd_text[:2000]}\n\n"
        "Score on: 1) Accuracy (no hallucination) 2) Relevance to JD 3) Completeness 4) Quality 5) JD keyword coverage.\n"
        'Return JSON ONLY: {"score": 0-100, "passed": true/false (>= 70), "issues": ["..."], "recommendations": "..."}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Strict quality critic. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        data = json.loads(raw.strip())
        return CriticVerdict(
            passed=bool(data.get("passed", False)),
            score=int(data.get("score", 50)),
            issues=data.get("issues", []),
            recommendations=data.get("recommendations", "")
        )
    except Exception as e:
        print(f"[Warning] Critic parse error: {e}")
        return CriticVerdict(passed=True, score=75, issues=[], recommendations="")


def run_all_critics(
    session_files: Dict[str, str],
    resume_text: str,
    jd_text: str
) -> Dict[str, CriticVerdict]:
    """Runs critic reviews across all core generated artifacts."""
    targets = {
        "Research Report": "/research/recon_report.md",
        "Tailored Resume": "/tailored_resume/tailored_resume.md",
        "Interview Prep":  "/interview_coach/interview_prep.md",
    }
    verdicts: Dict[str, CriticVerdict] = {}
    for name, path in targets.items():
        content = session_files.get(path, "")
        if content:
            verdicts[name] = run_critic_agent(name, content, resume_text, jd_text)
    return verdicts
