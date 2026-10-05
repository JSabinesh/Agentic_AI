"""interviewer agent: conducts interactive, adaptive mock interviews with role-specific questioning.
Progresses from regular introductory icebreaker to deep resume-grounded project drills.
"""

import re
from typing import Optional
from local_app.agents.common import generate_llm

INTERVIEW_ROUND_SYSTEM = {
    "behavioral": "You are a seasoned Engineering Director conducting a Behavioral STAR mock interview. You are supportive yet rigorous.",
    "system-design": "You are a Principal Systems Architect conducting a System Design drill focused on architecture, trade-offs, and scalability.",
    "technical": "You are a Lead Software Engineer conducting a deep technical interview on architecture, libraries, databases, and problem solving.",
    "hiring-manager": "You are a VP of Engineering conducting a hiring manager interview on culture, collaboration, leadership, and drive.",
}


def run_interviewer_question(
    round_type: str,
    resume_text: str,
    jd_text: str,
    prior_answer: Optional[str] = None,
    prior_question: Optional[str] = None,
    turn_index: int = 1,
) -> str:
    """Generates an opening icebreaker, resume-anchored project question, or progressive follow-up."""
    sys = INTERVIEW_ROUND_SYSTEM.get(round_type, INTERVIEW_ROUND_SYSTEM["behavioral"])

    # Clean prior answer
    prior_ans_clean = (prior_answer or "").strip()

    # Turn 1: Regular conversational icebreaker
    if turn_index == 1 or (not prior_ans_clean and not prior_question):
        if round_type == "behavioral":
            return (
                "Hello and welcome! Thank you for taking the time to speak with me today. "
                "To kick things off, could you please tell me about yourself, walk me through your background, "
                "and share what motivated you to pursue this role?"
            )
        elif round_type == "system-design":
            return (
                "Welcome to the System Design interview round! To start off, could you briefly introduce yourself, "
                "give an overview of the most complex systems you've worked on, and highlight the technical domains you enjoy most?"
            )
        elif round_type == "technical":
            return (
                "Welcome! Great to have you for this technical deep-dive. To get us started, could you introduce yourself "
                "and share a high-level summary of your core technical stack and recent hands-on projects?"
            )
        else:
            return (
                "Welcome! Thank you for meeting with me today. To get started, could you please tell me about yourself, "
                "your professional journey so far, and what excites you about this specific opportunity?"
            )

    # Turn 2: Direct Resume Project Anchor
    if turn_index == 2:
        prompt = (
            f"You are conducting a professional mock interview.\n\n"
            f"CANDIDATE RESUME:\n{resume_text[:2800] if resume_text else 'No resume provided.'}\n\n"
            f"TARGET JOB DESCRIPTION:\n{jd_text[:1200] if jd_text else 'Software Engineering Role'}\n\n"
            f"PREVIOUS QUESTION: '{prior_question or 'Tell me about yourself'}'\n"
            f"CANDIDATE'S INTRO ANSWER: '{prior_ans_clean}'\n\n"
            "TASK:\n"
            "Transition directly to their RESUME. Identify ONE specific, major project, technical accomplishment, "
            "or role explicitly highlighted in their resume (e.g. mention the exact project name, system, or company).\n"
            "Formulate ONE sharp, realistic interview question asking them to explain:\n"
            "1. The core architecture and purpose of that project,\n"
            "2. Their specific individual contribution,\n"
            "3. The primary technical hurdle they had to solve.\n\n"
            "Address the candidate naturally (e.g., 'Thank you for that introduction. Looking at your resume, you worked on [Project/Role]...').\n"
            "Return ONLY the question text without markdown headers, bullet lists, or meta commentary."
        )
        q = generate_llm(prompt, system_instruction=sys).strip()
        q = re.sub(r'^["\']|["\']$', '', q)
        return q or "Looking at your resume, could you walk me through your most significant technical project, your specific role in building it, and the biggest engineering challenge you encountered?"

    # Turn 3: Technical Deep-Dive & Metrics / Trade-offs from Resume
    if turn_index == 3:
        prompt = (
            f"You are conducting a professional mock interview.\n\n"
            f"CANDIDATE RESUME:\n{resume_text[:2500] if resume_text else ''}\n\n"
            f"PREVIOUS QUESTION: '{prior_question}'\n"
            f"CANDIDATE'S PREVIOUS ANSWER: '{prior_ans_clean}'\n\n"
            "TASK:\n"
            "Follow up on their technical response by digging into engineering decisions, trade-offs, and measurable outcomes.\n"
            "Ask about:\n"
            "- Specific technologies or frameworks from their resume used in this solution,\n"
            "- Trade-offs considered (e.g. performance vs complexity, SQL vs NoSQL, synchronous vs async),\n"
            "- Or concrete impact metrics (latency, throughput, accuracy, user scale).\n\n"
            "Ask ONE concise, probing technical question. Return ONLY the question text."
        )
        q = generate_llm(prompt, system_instruction=sys).strip()
        q = re.sub(r'^["\']|["\']$', '', q)
        return q or "What key trade-offs did you evaluate when selecting that technical approach, and how did you measure its performance or reliability under stress?"

    # Turn 4+: Situational, System Fit & Edge Cases
    prompt = (
        f"You are conducting a {round_type} mock interview.\n\n"
        f"CANDIDATE RESUME:\n{resume_text[:2200] if resume_text else ''}\n\n"
        f"TARGET JOB POSTING:\n{jd_text[:1400] if jd_text else ''}\n\n"
        f"PREVIOUS QUESTION: '{prior_question}'\n"
        f"CANDIDATE'S ANSWER: '{prior_ans_clean}'\n\n"
        f"TASK:\n"
        f"Ask ONE progressive, realistic {round_type} question. Connect their demonstrated experience from earlier "
        f"with real-world challenges or requirements of the target role (e.g., edge cases, team conflicts, production incidents, scalability, or prioritization).\n"
        "Return ONLY the question text."
    )
    q = generate_llm(prompt, system_instruction=sys).strip()
    q = re.sub(r'^["\']|["\']$', '', q)
    return q or "Can you describe a situation where things didn't go according to plan in production or during deployment, and how you diagnosed and resolved the issue?"
