"""resume-tailor agent: executive resume editor generating RenderCV YAML and Markdown without hallucination."""

from typing import Tuple, Optional
from local_app.agents.common import generate_llm


def run_resume_agent(
    resume_text: str,
    jd_text: str,
    research_report: str,
    update_request: Optional[str] = None,
    existing_yaml: Optional[str] = None,
    replan_feedback: Optional[str] = None
) -> Tuple[str, str]:
    """Generates or updates RenderCV YAML and Markdown tailored to the role and evidence."""
    sys_prompt = (
        "You are the `resume-agent` (resume-tailor) in NextRole.\n"
        "Role: Senior executive resume editor powered by Evidence DB.\n"
        "Rules: No fabrication. Highlight real achievements with STAR metrics.\n"
        "Output BOTH valid RenderCV YAML AND formatted Markdown."
    )
    fp = f"\n\nCRITIC FEEDBACK:\n{replan_feedback}" if replan_feedback else ""

    if update_request and existing_yaml:
        prompt = (
            f'UPDATE MODE: "{update_request}"{fp}\n\n'
            f"Existing YAML:\n{existing_yaml}\n\n"
            f"JD:\n{jd_text}\n\n"
            f"Resume:\n{resume_text}"
        )
    else:
        prompt = (
            f"CREATE MODE:{fp}\n\nResume:\n{resume_text}\n\nJD:\n{jd_text}\n\n"
            "Evidence DB:\n" + research_report + "\n\n"
            "SECTION 1: ```yaml\ncv:\n  name: <Name>\n  headline: <Role>\n  sections:\n"
            "    summary:\n      - <3-sentence summary>\n    skills:\n      - name: Tech\n        details: ...\n"
            "    experience:\n      - company: ...\n        highlights:\n          - <STAR bullet>\n```\n\n"
            "SECTION 2: Full Markdown resume preview."
        )

    raw = generate_llm(prompt, system_instruction=sys_prompt)
    yaml_content = ""
    if "```yaml" in raw:
        yaml_content = raw.split("```yaml")[1].split("```")[0].strip()
    elif "```" in raw:
        yaml_content = raw.split("```")[1].strip()
    if not yaml_content:
        yaml_content = "cv:\n  summary:\n    - Tailored for target position\n"
    return yaml_content, raw
