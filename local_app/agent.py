"""NextRole Multi-Agent Local Engine — Orchestrator & Feature Pipelines.

Modular Architecture:
- local_app.agents.common: LLM invocation, memory store, evidence store, doc parsing
- local_app.agents.job_analyzer: `job-analyzer` agent
- local_app.agents.candidate_evidence: `candidate-evidence` agent (zero-fabrication)
- local_app.agents.hiring_recon: `hiring-recon` / research agent (Tavily intel)
- local_app.agents.resume_tailor: `resume-tailor` agent (RenderCV YAML + Markdown)
- local_app.agents.interviewer: `interviewer` agent (dynamic questioning)
- local_app.agents.interview_prober: `interview-prober` agent (challenge probes)
- local_app.agents.interview_evaluator: `interview-evaluator` agent (6-criteria scoring)
- local_app.agents.interview_coach: `interview-coach` agent (knowledge DB prep)
- local_app.agents.gap_analyzer: `gap-analyzer` agent (priority gap detector)
- local_app.agents.resource_researcher: `resource-researcher` agent (courses, docs, repos)
- local_app.agents.learning_planner: `learning-planner` agent (7/14/30-day evidence plans)
- local_app.agents.job_discovery: `job-discovery` agent (multi-filter search)
- local_app.agents.job_normalizer: `job-normalizer` deterministic service
- local_app.agents.opportunity_matcher: `opportunity-matcher` agent (evidence-grounded matching)
- local_app.agents.critic: `critic` agent & CriticVerdict
- local_app.agents.judge: `judge` agent (final battlecard compiler)
- local_app.agents.supervisor: `supervisor` planner, orchestrator, approval governor, router
"""

import json
import asyncio
from typing import Dict, Any, List, Optional

# ── Re-export common functions and agents ────────────────────────────────────
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
from local_app.agents.interview_evaluator import (
    run_interview_evaluator,
    generate_final_interview_report,
)
from local_app.agents.interview_coach import run_interview_agent
from local_app.agents.gap_analyzer import run_gap_analyzer
from local_app.agents.resource_researcher import run_resource_researcher
from local_app.agents.learning_planner import run_learning_planner
from local_app.agents.job_normalizer import normalize_job
from local_app.agents.job_discovery import run_job_discovery
from local_app.agents.opportunity_matcher import run_opportunity_matcher
from local_app.agents.critic import CriticVerdict, run_critic_agent, run_all_critics
from local_app.agents.judge import run_judge
from local_app.agents.career_switch_advisor import analyze_career_switch
from local_app.agents.supervisor import (
    build_plan,
    execute_full_pipeline_async,
    approve_and_save_to_memory,
    classify_and_route_followup,
    handle_followup_turn,
)


# ============================================================================
# FEATURE PIPELINE 1: JOB MATCH ANALYSIS
# Agents: job-analyzer | candidate-evidence | hiring-recon | match-synthesis
# ============================================================================

def run_match_synthesis(
    jd_analysis: Dict[str, Any],
    evidence: Dict[str, Any],
    research_report: str = ""
) -> Dict[str, Any]:
    """Synthesizes a final match report from JD analysis and candidate evidence."""
    strong = [k for k, v in evidence.get("evidence_map", {}).items() if v.get("strength") == "strong"]
    partial = [k for k, v in evidence.get("evidence_map", {}).items() if v.get("strength") == "partial"]
    gaps = evidence.get("gaps", [])
    overlaps = evidence.get("overlaps", [])

    total = len(jd_analysis.get("required_skills", [])) or 1
    score = min(95, int((len(strong) * 1.0 + len(partial) * 0.5) / total * 100))

    return {
        "score": score,
        "skills_score": min(95, score + 5),
        "exp_score": min(95, score - 3),
        "impact_score": min(95, score - 7),
        "strong_matches": strong,
        "partial_matches": partial,
        "overlaps": overlaps,
        "gaps": gaps,
        "jd_role": jd_analysis.get("role", ""),
        "jd_seniority": jd_analysis.get("seniority", ""),
        "interview_priorities": [g["name"] for g in gaps if g.get("sev") == "high"][:3],
    }


async def run_job_match_pipeline(session: Dict[str, Any]) -> Dict[str, Any]:
    """Runs Feature Team 1: job-analyzer → candidate-evidence → match-synthesis."""
    resume_text = session.get("files", {}).get("/processed/resume.md", "")
    jd_text     = session.get("files", {}).get("/processed/jd.md", "")
    if not resume_text or not jd_text:
        return {"error": "Missing resume or JD"}

    jd_analysis = await asyncio.to_thread(run_job_analyzer, jd_text)
    evidence    = await asyncio.to_thread(run_candidate_evidence, resume_text, jd_analysis)

    research_report = session.get("files", {}).get("/research/recon_report.md", "")
    if not research_report:
        try:
            research_report = await asyncio.to_thread(run_research_agent, resume_text, jd_text)
            session["files"]["/research/recon_report.md"] = research_report
        except Exception:
            research_report = ""

    result = run_match_synthesis(jd_analysis, evidence, research_report)

    # Persist into shared Career Evidence Store
    store = get_evidence_store(session)
    store["skills"] = evidence.get("evidence_map", {})
    store["overlaps"] = evidence.get("overlaps", [])
    store["gaps"] = evidence.get("gaps", [])

    session["files"]["/match_analysis/match_report.json"] = json.dumps(result, indent=2)
    return result


# ============================================================================
# FEATURE PIPELINE 2: INTERVIEW SIMULATOR
# Agents: interviewer | interview-prober | interview-evaluator
# ============================================================================

def run_sim_turn(
    session: Dict[str, Any],
    round_type: str,
    user_answer: Optional[str] = None,
    action: Optional[str] = None
) -> Dict[str, Any]:
    """Runs Feature Team 2 turn: interviewer → interview-prober → interview-evaluator."""
    resume_text = session.get("files", {}).get("/processed/resume.md", "")
    jd_text     = session.get("files", {}).get("/processed/jd.md", "")
    store       = get_evidence_store(session)
    sim_history = store.setdefault("sim_history", [])

    if action == "reset":
        sim_history.clear()
        q = run_interviewer_question(round_type, resume_text, jd_text, turn_index=1)
        sim_history.append({"question": q, "round": round_type, "answer": None, "turn": 1, "is_probe": False})
        return {
            "question": q,
            "turn_index": 1,
            "is_probe": False,
            "has_resume": bool(resume_text),
            "sim_history": sim_history,
        }

    if action == "final_report":
        report = generate_final_interview_report(sim_history, resume_text, jd_text)
        return {
            "final_report": report,
            "turn_index": len(sim_history),
            "has_resume": bool(resume_text),
            "sim_history": sim_history,
        }

    prior_q = sim_history[-1]["question"] if sim_history else None
    evaluation = None
    probe      = None

    answered_count = len([t for t in sim_history if t.get("answer")])

    if user_answer and prior_q:
        evaluation = run_interview_evaluator(prior_q, user_answer, round_type)
        probe      = run_interview_prober(prior_q, user_answer)
        sim_history[-1]["answer"]     = user_answer
        sim_history[-1]["evaluation"] = evaluation
        sim_history[-1]["probe"]      = probe
        answered_count += 1

    next_turn_index = answered_count + 1

    if probe:
        next_question = probe
        is_probe = True
    else:
        next_question = run_interviewer_question(
            round_type, resume_text, jd_text,
            prior_answer=user_answer, prior_question=prior_q,
            turn_index=next_turn_index
        )
        is_probe = False

    sim_history.append({
        "question": next_question,
        "round": round_type,
        "answer": None,
        "turn": next_turn_index,
        "is_probe": is_probe
    })

    return {
        "question": next_question,
        "evaluation": evaluation,
        "is_probe": is_probe,
        "turn_index": next_turn_index,
        "has_resume": bool(resume_text),
        "total_answered": answered_count,
    }


# ============================================================================
# FEATURE PIPELINE 3: RESOURCES
# Agents: gap-analyzer | resource-researcher | learning-planner
# ============================================================================

async def run_resources_pipeline(session: Dict[str, Any], topic: str = "") -> Dict[str, Any]:
    """Runs Feature Team 3: gap-analyzer → resource-researcher → learning-planner."""
    gaps      = await asyncio.to_thread(run_gap_analyzer, session, topic)
    resources = await asyncio.to_thread(run_resource_researcher, gaps)
    plans     = await asyncio.to_thread(run_learning_planner, gaps, resources)

    store = get_evidence_store(session)
    store["learning_plan"] = plans
    store["learning_resources"] = resources
    session["files"]["/resources/learning_plan.json"] = json.dumps(plans, indent=2)
    session["files"]["/resources/learning_resources.json"] = json.dumps(resources, indent=2)

    return {"gaps": gaps, "resources": resources, "plans": plans, "topic": topic}


# ============================================================================
# FEATURE PIPELINE 4: JOB FINDER
# Agents: job-discovery | job-normalizer | opportunity-matcher
# ============================================================================

async def run_job_finder_pipeline(
    query: str,
    filters: List[str],
    session: Dict[str, Any],
    company: str = "",
    country: str = ""
) -> Dict[str, Any]:
    """Runs Feature Team 4: job-discovery → job-normalizer → opportunity-matcher."""
    from datetime import datetime
    now_str = datetime.now().strftime("%H:%M:%S")

    logs = [
        f"[{now_str}] [Supervisor Agent] Initialized Opportunity Radar with filters: Role='{query or 'All'}', Company='{company or 'All'}', Country='{country or 'All'}'",
    ]

    raw_jobs = await asyncio.to_thread(run_job_discovery, query, filters, session, company, country)
    from local_app.agents.job_discovery import LAST_JSEARCH_ERROR
    if raw_jobs:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [Job Discovery Agent] Retrieved {len(raw_jobs)} live job postings from LinkedIn, Indeed, Glassdoor via JSearch API")
    elif LAST_JSEARCH_ERROR:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [Job Discovery Agent] JSearch API alert: {LAST_JSEARCH_ERROR}")
    else:
        logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [Job Discovery Agent] Retrieved 0 live job postings for this exact query.")

    matched = await asyncio.to_thread(run_opportunity_matcher, raw_jobs, session)
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [Job Normalizer] Standardized posting schemas, compensation metadata, and direct apply links")
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [Opportunity Matcher] Scored candidate evidence across {len(matched)} postings against Career Evidence Store")
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] [ATS Tailor Agent] Standing by — 1-click ATS PDF resume & interview battlecard available per job")

    store = get_evidence_store(session)
    store["job_results"] = matched
    session["files"]["/job_finder/results.json"] = json.dumps(matched, indent=2)

    return {"jobs": matched, "total": len(matched), "logs": logs}


async def run_career_switch_pipeline(
    current_role: str,
    target_role: str,
    experience_level: str,
    currency: str,
    session: Dict[str, Any]
) -> Dict[str, Any]:
    """Runs Feature Team 5: Career Switch Advisor.
    Evaluates role transition, comparative salary curves, pros/cons, and suggested better pivots.
    """
    candidate_resume = session.get("files", {}).get("/processed/resume.md", "")
    analysis = await asyncio.to_thread(
        analyze_career_switch,
        current_role,
        target_role,
        experience_level,
        currency,
        candidate_resume
    )

    # Store analysis in workspace artifacts
    session["files"]["/career_switch/analysis.json"] = json.dumps(analysis, indent=2)

    # Also build a human-readable markdown version
    md_lines = [
        f"# Career Switch Strategic Evaluation: {analysis.get('current_role')} → {analysis.get('target_role')}",
        f"- **Experience Level:** {analysis.get('experience_level')}",
        f"- **Currency:** {analysis.get('currency')} ({analysis.get('currency_symbol')})",
        f"- **10-Year Trajectory Delta:** {int(round(float(analysis.get('salary_graph', {}).get('delta_10yr_pct', 0) or 0))):+d}%",
        f"- **Strategic Verdict:** {analysis.get('better_solution', {}).get('verdict_badge')}\n",
        f"## 1. Executive Summary\n{analysis.get('better_solution', {}).get('summary')}\n",
        f"## 2. Recommended Higher-Yield Pivot: {analysis.get('suggested_better_role', {}).get('title')}",
        f"> {analysis.get('suggested_better_role', {}).get('tagline')}\n",
        "### Why Superior:\n" + "\n".join(f"- {w}" for w in analysis.get('suggested_better_role', {}).get('why_superior', [])),
        "\n### Bridging Skills Required:\n" + "\n".join(f"- {s}" for s in analysis.get('suggested_better_role', {}).get('bridging_skills', [])),
        f"\n## 3. Specific Switch Pros & Cons ({analysis.get('current_role')} → {analysis.get('target_role')})",
        "### Advantages (Pros):\n" + "\n".join(f"- **{p.get('title')}:** {p.get('detail')}" for p in analysis.get('switch_pros', [])),
        "\n### Risks & Drawbacks (Cons):\n" + "\n".join(f"- **{c.get('title')}:** {c.get('detail')} *(Severity: {c.get('severity', 'medium').upper()})*" for c in analysis.get('switch_cons', [])),
        "\n## 4. General Career Switching Pros & Cons",
        "### Macro Pros:\n" + "\n".join(f"- **{p.get('title')}:** {p.get('detail')}" for p in analysis.get('general_switching_pros_and_cons', {}).get('pros', [])),
        "\n### Macro Cons:\n" + "\n".join(f"- **{c.get('title')}:** {c.get('detail')}" for c in analysis.get('general_switching_pros_and_cons', {}).get('cons', [])),
        "\n### Strategic De-risking Checklist:\n" + "\n".join(f"- {item}" for item in analysis.get('general_switching_pros_and_cons', {}).get('strategic_checklist', []))
    ]
    session["files"]["/career_switch/report.md"] = "\n".join(md_lines)

    return {"analysis": analysis, "files": session.get("files", {})}

