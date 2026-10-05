"""judge agent: final quality synthesis authority compiling the Day-of Interview Battlecard."""

from typing import Dict
from local_app.agents.common import generate_llm


def run_judge(resume_text: str, jd_text: str, session_files: Dict[str, str]) -> str:
    """Synthesizes verified specialist outputs into the definitive Day-of Battlecard."""
    recon  = session_files.get("/research/recon_report.md", "")
    tailor = session_files.get("/tailored_resume/tailored_resume.md", "")
    prep   = session_files.get("/interview_coach/interview_prep.md", "")
    prompt = (
        "You are the JUDGE agent - final authority in the NextRole multi-agent system.\n"
        "All specialist agents passed Critic QA. Synthesize their outputs into the definitive Battlecard.\n\n"
        f"Resume:\n{resume_text[:2000]}\n\nJD:\n{jd_text[:2000]}\n\n"
        f"Research:\n{recon[:2000]}\n\nTailored Resume:\n{tailor[:1500]}\n\nInterview Prep:\n{prep[:2000]}\n\n"
        "Produce `# Day-of Interview Battlecard` with:\n"
        "- Company & Role, Core Narrative, Judge Confidence Score\n"
        "- Quick Pitch (60s), Round-by-round cheat sheets (Recruiter/HM/Technical)\n"
        "- Top 3 questions to ask, Watch-Out flags (critical gaps)"
    )
    return generate_llm(prompt, system_instruction="Final Judge. Synthesize elite, high-density interview battlecards.")
