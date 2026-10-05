"""supervisor agent: master planner, re-plan orchestrator, approval governor, and turn router."""

import re
import json
import hashlib
import asyncio
from typing import Dict, Any, Tuple, List
from local_app.agents.common import (
    generate_llm,
    get_memory_for_candidate,
    upsert_memory,
    MAX_REPLAN_LOOPS
)
from local_app.agents.hiring_recon import run_research_agent
from local_app.agents.resume_tailor import run_resume_agent
from local_app.agents.interview_coach import run_interview_agent
from local_app.agents.critic import run_all_critics
from local_app.agents.judge import run_judge


def build_plan(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """Generates execution plan and initial priority gaps."""
    prompt = (
        "You are the SUPERVISOR planner in NextRole. Output a JSON execution plan.\n\n"
        f"Resume:\n{resume_text[:1500]}\n\nJD:\n{jd_text[:1500]}\n\n"
        'Return JSON ONLY:\n{"candidate_name":"","target_role":"","priority_gaps":[],"research_queries":[],"replan_history":[]}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Strict supervisor planner. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[Warning] Planner parse error: {e}")
        return {
            "candidate_name": "Candidate",
            "target_role": "Target Role",
            "priority_gaps": [],
            "research_queries": [],
            "replan_history": []
        }


async def execute_full_pipeline_async(session: Dict[str, Any]) -> Dict[str, Any]:
    """Full multi-agent pipeline with Critic/Re-plan/Judge loop."""
    resume_text = session.get("files", {}).get("/processed/resume.md", "")
    jd_text     = session.get("files", {}).get("/processed/jd.md", "")

    if not resume_text or not jd_text:
        return {"status": "error", "message": "Missing resume or JD."}

    candidate_id = hashlib.md5(resume_text[:500].encode()).hexdigest()[:12]
    prior_memory = get_memory_for_candidate(candidate_id)
    session["candidate_id"] = candidate_id

    # Stage 1: Planner
    plan = build_plan(resume_text, jd_text)
    session["plan"] = plan
    session["files"]["/supervisor/plan.json"] = json.dumps(plan, indent=2)
    pipeline_log = [f"**Supervisor Planner:** `{plan.get('target_role')}` | Gaps: {', '.join(plan.get('priority_gaps', [])[:3])}"]

    # Stage 2: Research Agent (hiring-recon)
    recon_report = await asyncio.to_thread(run_research_agent, resume_text, jd_text, prior_memory=prior_memory)
    session["files"]["/research/recon_report.md"] = recon_report
    pipeline_log.append("**Research Agent:** Intelligence report complete -> Evidence DB")

    # Stage 3+4: Resume + Interview parallel, then Critics (loop)
    replan_fb_resume    = None
    replan_fb_interview = None
    avg_score  = 0
    critic_summary = {}

    for loop_idx in range(MAX_REPLAN_LOOPS + 1):
        t_resume    = asyncio.to_thread(run_resume_agent,    resume_text, jd_text, recon_report, replan_feedback=replan_fb_resume)
        t_interview = asyncio.to_thread(run_interview_agent, resume_text, jd_text, recon_report, replan_feedback=replan_fb_interview)
        (yaml_content, tailor_preview), prep_doc = await asyncio.gather(t_resume, t_interview)

        session["files"]["/tailored_resume/resume.yaml"]        = yaml_content
        session["files"]["/tailored_resume/tailored_resume.md"] = tailor_preview
        session["files"]["/interview_coach/interview_prep.md"]  = prep_doc

        verdicts = await asyncio.to_thread(run_all_critics, session["files"], resume_text, jd_text)
        critic_summary = {name: v.to_dict() for name, v in verdicts.items()}
        session["files"]["/supervisor/critic_verdicts.json"] = json.dumps(critic_summary, indent=2)

        all_passed = all(v.passed for v in verdicts.values())
        avg_score  = int(sum(v.score for v in verdicts.values()) / max(len(verdicts), 1))

        if all_passed or loop_idx >= MAX_REPLAN_LOOPS:
            status = "PASS" if all_passed else "SOFT_PASS"
            pipeline_log.append(f"**Critic Agents [{loop_idx+1}/{MAX_REPLAN_LOOPS+1}]:** {status} (avg {avg_score}/100)")
            break

        failed = [n for n, v in verdicts.items() if not v.passed]
        pipeline_log.append(f"**Critic [loop {loop_idx+1}]:** FAIL -> Re-plan for {', '.join(failed)} (avg {avg_score}/100)")
        if "Tailored Resume" in verdicts and not verdicts["Tailored Resume"].passed:
            replan_fb_resume = verdicts["Tailored Resume"].recommendations
        if "Interview Prep" in verdicts and not verdicts["Interview Prep"].passed:
            replan_fb_interview = verdicts["Interview Prep"].recommendations
        plan.setdefault("replan_history", []).append({"loop": loop_idx+1, "failed": failed, "avg_score": avg_score})
        session["files"]["/supervisor/plan.json"] = json.dumps(plan, indent=2)

    # Stage 5: Judge
    battlecard = await asyncio.to_thread(run_judge, resume_text, jd_text, session["files"])
    session["files"]["/interview_battlecard/battlecard.md"] = battlecard
    pipeline_log.append(f"**Judge:** Final Battlecard compiled (confidence {avg_score}/100)")

    session["stage"] = "AWAITING_APPROVAL"
    session["pipeline_log"] = pipeline_log

    summary_text = (
        "### Multi-Agent Workflow Complete!\n\n"
        + "\n".join(f"{i+1}. {log}" for i, log in enumerate(pipeline_log))
        + "\n\n---\n**All artifacts ready in the Workspace.** "
        "Click **Approve & Save to Memory** to persist, or chat to request edits."
    )
    return {
        "status": "success",
        "summary": summary_text,
        "critic_verdicts": critic_summary,
        "avg_score": avg_score,
        "pipeline_log": pipeline_log,
        "candidate_id": candidate_id,
        "files": session["files"]
    }


def approve_and_save_to_memory(session: Dict[str, Any]) -> Dict[str, Any]:
    """Human-in-the-loop approval: commits verified artifacts to Career Memory."""
    candidate_id = session.get("candidate_id", "unknown")
    plan  = session.get("plan", {})
    files = session.get("files", {})
    upsert_memory(
        candidate_id=candidate_id,
        artifacts={
            "recon_report":    files.get("/research/recon_report.md", ""),
            "tailored_resume": files.get("/tailored_resume/tailored_resume.md", ""),
            "interview_prep":  files.get("/interview_coach/interview_prep.md", ""),
            "battlecard":      files.get("/interview_battlecard/battlecard.md", ""),
        },
        meta={"target_role": plan.get("target_role", ""), "candidate_name": plan.get("candidate_name", "")}
    )
    session["stage"] = "COMPLETED"
    name = plan.get("candidate_name", "Candidate")
    return {
        "status": "saved",
        "candidate_id": candidate_id,
        "message": f"Career artifacts approved and saved to Career Memory for {name}. Future sessions will use this memory as context."
    }


def classify_and_route_followup(user_message: str) -> str:
    """Classifies user intent to route follow-up requests to the right specialist agent."""
    prompt = (
        f'Classify which specialist agent owns: "{user_message}"\n'
        "Reply with EXACTLY one of: research-agent | resume-agent | interview-agent | supervisor"
    )
    tag = generate_llm(prompt, system_instruction="Strict intent router.").strip().lower()
    for valid in ["research-agent", "resume-agent", "interview-agent", "supervisor"]:
        if valid in tag:
            return valid
    return "supervisor"


def handle_followup_turn(user_message: str, session: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any], List[str]]:
    """Handles an interactive chat turn and delegates to the appropriate specialist agent."""
    target = classify_and_route_followup(user_message)
    files  = session.get("files", {})
    rt     = files.get("/processed/resume.md", "")
    jd     = files.get("/processed/jd.md", "")
    tools_used: List[str] = []

    if target == "resume-agent":
        tools_used = ["rendercv_schema_compiler", "ats_keyword_aligner", "evidence_db_lookup"]
        yaml_c, preview = run_resume_agent(
            rt, jd, files.get("/research/recon_report.md", ""),
            update_request=user_message,
            existing_yaml=files.get("/tailored_resume/resume.yaml", "")
        )
        files["/tailored_resume/resume.yaml"]        = yaml_c
        files["/tailored_resume/tailored_resume.md"] = preview
        msg = f"[resume-agent] Updated resume for: \"{user_message}\""

    elif target == "interview-agent":
        tools_used = ["star_story_synthesizer", "behavioral_question_generator", "knowledge_db_query"]
        new_prep = run_interview_agent(
            rt, jd, files.get("/research/recon_report.md", ""),
            update_request=user_message,
            existing_prep=files.get("/interview_coach/interview_prep.md", "")
        )
        files["/interview_coach/interview_prep.md"] = new_prep
        msg = f"[interview-agent] Updated interview prep for: \"{user_message}\""

    elif target == "research-agent":
        tools_used = ["tavily_web_search", "company_financials_scraper", "salary_benchmarking"]
        new_recon = run_research_agent(
            rt, jd,
            update_request=user_message,
            existing_report=files.get("/research/recon_report.md", "")
        )
        files["/research/recon_report.md"] = new_recon
        msg = "[research-agent] Updated intelligence report."

    else:
        if "battlecard" in user_message.lower():
            target = "judge"
            tools_used = ["judge_synthesis", "cross_artifact_auditor", "star_battlecard_compiler"]
            files["/interview_battlecard/battlecard.md"] = run_judge(rt, jd, files)
            msg = "[supervisor -> Judge] Re-compiled the Battlecard."
        else:
            tools_used = ["career_memory_lookup", "supervisor_rag_retriever"]
            ctx = f"Resume:\n{rt[:1500]}\n\nJD:\n{jd[:1500]}\n\nResearch:\n{files.get('/research/recon_report.md','')[:1500]}"
            msg = generate_llm(
                f'Question: "{user_message}"\n\nContext:\n{ctx}\n\nProvide an insightful response:',
                system_instruction="You are the lead Supervisor career agent."
            )

    return target, msg, files, tools_used
