"""interview-coach agent: interview strategist building round prep docs, STAR stories, and reverse questions."""

from typing import Optional
from local_app.agents.common import generate_llm


def run_interview_agent(
    resume_text: str,
    jd_text: str,
    research_report: str,
    update_request: Optional[str] = None,
    existing_prep: Optional[str] = None,
    replan_feedback: Optional[str] = None
) -> str:
    """Generates comprehensive interview prep doc with elevator pitch, STAR stories, and round strategies."""
    sys_prompt = (
        "You are the `interview-agent` (interview-coach) in NextRole.\n"
        "Role: Elite interview strategist backed by Knowledge DB.\n"
        "Produce: 1) 60s & 30s Self-Introduction 2) Round-by-round strategy "
        "3) 3 STAR stories bridging recon gaps 4) 5 reverse-interview questions "
        "5) Technical quick-reference (DS/Algo patterns, system design vocab)."
    )
    fp = f"\n\nCRITIC FEEDBACK:\n{replan_feedback}" if replan_feedback else ""

    if update_request and existing_prep:
        prompt = (
            f'UPDATE MODE: "{update_request}"{fp}\n\n'
            f"Existing:\n{existing_prep}\n\n"
            f"JD:\n{jd_text}\n\n"
            f"Resume:\n{resume_text}"
        )
    else:
        prompt = (
            f"CREATE MODE:{fp}\n\nResume:\n{resume_text}\n\nJD:\n{jd_text}\n\n"
            f"Knowledge DB (Recon):\n{research_report}\n\nGenerate `# Interview Prep Doc` in Markdown."
        )
    return generate_llm(prompt, system_instruction=sys_prompt)
