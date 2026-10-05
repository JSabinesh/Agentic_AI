"""Job Interview Guide & Gap Analyzer Agent.
Generates role-specific interview prep guides, STAR stories, and precise gap analysis
comparing the candidate's current resume against discovered job postings.
"""

import re
import json
from typing import Dict, Any, List
from local_app.agents.common import generate_llm
from local_app.agents.pdf_generator import DEFAULT_ABINESH_DATA


def generate_job_interview_guide(
    job_role: str,
    company: str,
    job_description: str,
    job_skills: List[str],
    candidate_resume_text: str = ""
) -> Dict[str, Any]:
    """Analyzes candidate gaps vs the JD and creates a comprehensive interview preparation dossier."""
    candidate_profile = candidate_resume_text.strip() or json.dumps(DEFAULT_ABINESH_DATA)

    prompt = (
        "You are an Elite Interview Coach and ATS Career Analyst in NextRole.\n"
        "Your mission is to perform an in-depth gap analysis between the candidate's resume and target job,\n"
        "and generate a Day-of Interview Battlecard.\n\n"
        f"TARGET ROLE: {job_role}\n"
        f"TARGET COMPANY: {company}\n"
        f"JOB DESCRIPTION:\n{job_description[:1600]}\n"
        f"REQUIRED SKILLS: {', '.join(job_skills) if job_skills else 'Software Engineering'}\n\n"
        f"CANDIDATE PROFILE & EVIDENCE:\n{candidate_profile[:2000]}\n\n"
        "TASK 1: GAP ANALYSIS\n"
        "- Matched Strengths (skills/experience directly supported by candidate evidence)\n"
        "- Partial Gaps (skills adjacent or partially met, with talking-point bridge)\n"
        "- Critical Gaps (must-know requirements not in resume, with 3-day crash prep action)\n"
        "- ATS Match Score (0-100% realistic score)\n\n"
        "TASK 2: INTERVIEW GUIDE\n"
        "- 60-second Elevator Pitch customized for this role\n"
        "- 4 High-Probability Technical Questions with model answers referencing candidate's projects\n"
        "- 2 Probing/Scenario Questions challenging edge cases or tradeoffs\n"
        "- 2 STAR Behavioral Stories tailored to company culture\n"
        "- 4 Strategic Reverse Questions to ask the interviewer\n\n"
        "OUTPUT FORMAT: Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "match_score": 85,\n'
        '  "summary_verdict": "Strong fit for ML/Python; address cloud deployment proactively.",\n'
        '  "matched_strengths": [\n'
        '    {"skill": "Python & ML", "evidence": "Built Scikit-learn house price model with feature engineering"}\n'
        '  ],\n'
        '  "partial_gaps": [\n'
        '    {"skill": "REST API Architecture", "bridge": "Emphasize Flask web backend integration & Supabase auth"}\n'
        '  ],\n'
        '  "critical_gaps": [\n'
        '    {"skill": "Cloud / Docker", "action": "Demonstrate containerization concepts & Supabase cloud hosting"}\n'
        '  ],\n'
        '  "elevator_pitch": "...",\n'
        '  "technical_qa": [\n'
        '    {"question": "...", "answer_strategy": "..."}\n'
        '  ],\n'
        '  "scenario_probes": [\n'
        '    {"scenario": "...", "response_guide": "..."}\n'
        '  ],\n'
        '  "star_stories": [\n'
        '    {"situation": "...", "task": "...", "action": "...", "result": "..."}\n'
        '  ],\n'
        '  "reverse_questions": [\n'
        '    "..."\n'
        '  ]\n'
        "}"
    )

    try:
        raw = generate_llm(
            prompt,
            system_instruction="Career strategist. Return valid JSON only, no markdown wrapping."
        )
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        data = json.loads(raw.strip())
        return data
    except Exception as e:
        print(f"[Warning] Interview guide generation failed: {e}")
        return {
            "match_score": 80,
            "summary_verdict": f"Competitive candidate for {job_role} at {company}.",
            "matched_strengths": [
                {"skill": "Python & Machine Learning", "evidence": "Hands-on model building with Scikit-learn and Flask UI"},
                {"skill": "Mobile & Web Full-Stack", "evidence": "React Native, Supabase, PostgreSQL civic app (CityMitra)"}
            ],
            "partial_gaps": [
                {"skill": "Enterprise Cloud CI/CD", "bridge": "Discuss git workflows and modular architecture"}
            ],
            "critical_gaps": [
                {"skill": "Production Monitoring", "action": "Review application telemetry and logging best practices"}
            ],
            "elevator_pitch": f"I am an Artificial Intelligence and Machine Learning engineer passionate about building data-driven systems and responsive applications, with direct experience deploying ML models and developing scalable platforms.",
            "technical_qa": [
                {"question": f"How do you handle feature selection and model evaluation for {job_role} tasks?", "answer_strategy": "Anchor answer in the House Price Prediction project detailing data cleaning, BHK encoding, and train-test splits."}
            ],
            "scenario_probes": [
                {"scenario": "What would you do if your model's accuracy drops in production?", "response_guide": "Discuss data drift, feature re-indexing, and monitoring pipelines."}
            ],
            "star_stories": [
                {"situation": "CityMitra required handling civic reports in real-time.", "task": "Distribute contractor assignments efficiently.", "action": "Implemented a round-robin routing algorithm with Supabase auth.", "result": "Streamlined municipal ticket resolution."}
            ],
            "reverse_questions": [
                f"What are the biggest technical challenges the {job_role} team is solving this quarter?",
                "How does the engineering team balance rapid prototyping with production reliability?"
            ]
        }
