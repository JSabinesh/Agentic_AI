"""NextRole Multi-Agent Copilot — Package of Specialist Agents."""

from local_app.agents.common import (
    generate_llm,
    extract_urls,
    load_memory,
    save_memory,
    upsert_memory,
    get_memory_for_candidate,
    get_evidence_store,
    parse_resume_bytes,
    extract_job_from_url,
)
from local_app.agents.job_analyzer import run_job_analyzer
from local_app.agents.candidate_evidence import run_candidate_evidence
from local_app.agents.hiring_recon import run_research_agent
from local_app.agents.resume_tailor import run_resume_agent
from local_app.agents.interviewer import run_interviewer_question
from local_app.agents.interview_prober import run_interview_prober
from local_app.agents.interview_evaluator import run_interview_evaluator
from local_app.agents.interview_coach import run_interview_agent
from local_app.agents.gap_analyzer import run_gap_analyzer
from local_app.agents.resource_researcher import run_resource_researcher
from local_app.agents.learning_planner import run_learning_planner
from local_app.agents.job_normalizer import normalize_job
from local_app.agents.job_discovery import run_job_discovery
from local_app.agents.opportunity_matcher import run_opportunity_matcher
from local_app.agents.critic import CriticVerdict, run_critic_agent, run_all_critics
from local_app.agents.judge import run_judge
from local_app.agents.supervisor import (
    build_plan,
    execute_full_pipeline_async,
    approve_and_save_to_memory,
    classify_and_route_followup,
    handle_followup_turn,
)
from local_app.agents.pdf_generator import (
    build_ats_resume_pdf,
    tailor_resume_data,
    DEFAULT_ABINESH_DATA,
)
from local_app.agents.job_interview_guide import generate_job_interview_guide

__all__ = [
    "generate_llm",
    "extract_urls",
    "load_memory",
    "save_memory",
    "upsert_memory",
    "get_memory_for_candidate",
    "get_evidence_store",
    "parse_resume_bytes",
    "extract_job_from_url",
    "run_job_analyzer",
    "run_candidate_evidence",
    "run_research_agent",
    "run_resume_agent",
    "run_interviewer_question",
    "run_interview_prober",
    "run_interview_evaluator",
    "run_interview_agent",
    "run_gap_analyzer",
    "run_resource_researcher",
    "run_learning_planner",
    "normalize_job",
    "run_job_discovery",
    "run_opportunity_matcher",
    "CriticVerdict",
    "run_critic_agent",
    "run_all_critics",
    "run_judge",
    "build_plan",
    "execute_full_pipeline_async",
    "approve_and_save_to_memory",
    "classify_and_route_followup",
    "handle_followup_turn",
    "build_ats_resume_pdf",
    "tailor_resume_data",
    "DEFAULT_ABINESH_DATA",
    "generate_job_interview_guide",
]
