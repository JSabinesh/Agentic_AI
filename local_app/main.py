"""NextRole FastAPI Server.
Full multi-agent architecture:
  Supervisor (Planner) --> Research Agent / Resume Agent / Interview Agent
  --> Critic Agents (FAIL --> Re-plan | PASS --> Judge)
  --> Judge --> Final Artifacts --> User Approval --> Career Memory
"""

import os
import re
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import local_app.agent as agent

app = FastAPI(title="NextRole Multi-Agent Copilot", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_SAMPLE_RESUME = """# Abinesh J S
Chennai, India | +91 9876543210 | abinesh@example.com | linkedin.com/in/abinesh-js

## Professional Summary
Senior AI & Full-Stack Software Engineer with 6+ years of experience designing and deploying distributed machine learning microservices, reactive frontend architectures, and high-throughput REST APIs. Proven track record in Python, FastAPI, Docker, PostgreSQL, AWS, and modern GenAI agent pipelines.

## Technical Skills
- Languages: Python, JavaScript/TypeScript, SQL, Bash
- Frameworks & Libraries: FastAPI, Flask, React, Next.js, LangChain, PyTorch, Scikit-learn
- Databases & Caching: PostgreSQL, Redis, MongoDB
- Cloud & DevOps: Docker, Kubernetes, AWS (ECS, S3, RDS), Git, CI/CD Actions
- Core Competencies: Distributed Systems, RESTful API Design, Microservices, Prompt Engineering, ATS Optimization

## Professional Experience
### Senior Software Engineer | Egonex AI Solutions (2022 - Present)
- Architected and deployed agentic career workflows serving 50,000+ monthly active requests using FastAPI, asynchronous task queues, and Google Gemini LLMs.
- Reduced API p95 latency by 42% through distributed Redis caching and query indexing on PostgreSQL.
- Spearheaded containerized microservices deployment on AWS ECS with zero-downtime rolling updates.

### Full-Stack Developer | Luna Technologies (2019 - 2022)
- Built interactive web portals and data dashboards with Next.js, React, and Python backend services.
- Implemented JWT authentication, role-based access control (RBAC), and automated unit test suites achieving 88% coverage.
- Integrated third-party search APIs and document processing pipelines parsing PDF and DOCX files.

## Education
- B.E. in Computer Science & Engineering | Anna University (2015 - 2019)
"""

DEFAULT_SAMPLE_JD = """# Senior Backend & AI Systems Engineer — NextRole Technologies
Location: Remote / Hybrid | Salary: $140,000 - $180,000 / ₹25 - ₹35 LPA

## Role Overview
We are seeking a Senior Backend & AI Systems Engineer to lead the design and implementation of high-throughput distributed microservices, agentic orchestration engines, and intelligent search systems.

## Key Responsibilities
- Architect, build, and maintain production-grade REST APIs and asynchronous pipeline workers using Python, FastAPI, and Docker.
- Integrate modern LLMs and agentic reasoning frameworks (LangChain, LangGraph) into low-latency user workflows.
- Design scalable database schemas and cache strategies using PostgreSQL and Redis.
- Collaborate with frontend engineers to deliver snappy, real-time streaming interfaces.
- Lead system reliability, code reviews, and container orchestration across cloud environments (AWS/Kubernetes).

## Required Qualifications
- 4+ years of professional backend engineering experience in Python (FastAPI, Flask, or Django).
- Hands-on expertise with relational databases (PostgreSQL) and caching (Redis).
- Proven experience with Docker containerization and cloud infrastructure (AWS or GCP).
- Strong understanding of asynchronous programming, REST APIs, and microservices architecture.
- Demonstrated experience building or integrating LLMs, vector search, or GenAI agents.

## Preferred Qualifications
- Experience with Kubernetes cluster deployment and CI/CD automation pipelines.
- Familiarity with TypeScript and modern frontend frameworks (React/Next.js).
- Background in performance profiling, observability (Prometheus/Grafana), and high-throughput systems.
"""

SESSIONS: Dict[str, Dict[str, Any]] = {}


def get_session(session_id: Optional[str]) -> tuple[str, Dict[str, Any]]:
    if not session_id or session_id not in SESSIONS:
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {
            "id": session_id,
            "stage": "AWAITING_INPUT",
            "files": {},
            "history": [],
        }
    return session_id, SESSIONS[session_id]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class JobLinkRequest(BaseModel):
    url: str
    session_id: Optional[str] = None


class FileSaveRequest(BaseModel):
    session_id: str
    path: str
    content: str


class ApproveRequest(BaseModel):
    session_id: str


@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "has_google_key": bool(os.getenv("GOOGLE_API_KEY")),
        "has_tavily_key": bool(os.getenv("TAVILY_API_KEY")),
        "has_llama_key": bool(os.getenv("LLAMA_CLOUD_API_KEY")),
        "has_anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


@app.get("/api/workspace/{session_id}")
async def get_workspace_files(session_id: str):
    sid, session = get_session(session_id)
    return {
        "session_id": sid,
        "stage": session.get("stage", "AWAITING_INTAKE"),
        "files": session.get("files", {})
    }


@app.post("/api/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None)
):
    sid, session = get_session(session_id)
    try:
        content_bytes = await file.read()
        parsed_text = agent.parse_resume_bytes(file.filename, content_bytes)
        if not parsed_text or len(parsed_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from uploaded resume. Please verify the file is a text-based PDF or Word (.docx) document."
            )

        session["files"]["/processed/resume.md"] = parsed_text
        session["resume_filename"] = file.filename

        has_jd = "/processed/jd.md" in session.get("files", {})

        if not has_jd:
            session["stage"] = "AWAITING_JD"
            msg = (
                f"**Resume Processed:** `{file.filename}` saved to `/processed/resume.md` ({len(parsed_text)} chars).\n\n"
                f"**Next Step:** Select a target role in **Job Finder** or paste a target Job Description (JD) to run match analysis & tailoring."
            )
        else:
            session["stage"] = "JD_LOADED"
            msg = (
                f"**Resume Processed:** `{file.filename}` saved to `/processed/resume.md`.\n\n"
                f"**Both CV and Target JD are ready!** You can now run **Job Match Analysis**, generate your tailored resume, or practice interview rounds."
            )

        session["history"].append({"role": "user", "content": f"Uploaded resume: {file.filename}"})
        session["history"].append({"role": "assistant", "content": msg})

        return {
            "session_id": sid,
            "stage": session["stage"],
            "filename": file.filename,
            "files": session["files"],
            "ai_msg": msg,
            "pipeline": None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Error] upload_resume: {e}")
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {str(e)}")


class RemoveResumeRequest(BaseModel):
    session_id: Optional[str] = None


@app.post("/api/remove-resume")
async def remove_resume(payload: RemoveResumeRequest):
    sid, session = get_session(payload.session_id)
    session["files"].pop("/processed/resume.md", None)
    session.pop("resume_filename", None)
    session["stage"] = "AWAITING_RESUME"
    return {
        "session_id": sid,
        "status": "removed",
        "message": "Resume removed from workspace.",
        "files": session.get("files", {})
    }


class SaveJdTextRequest(BaseModel):
    session_id: Optional[str] = None
    text: str


@app.post("/api/save-jd-text")
async def save_jd_text(payload: SaveJdTextRequest):
    sid, session = get_session(payload.session_id)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Job description text cannot be empty.")

    session["files"]["/processed/jd.md"] = text
    has_resume = "/processed/resume.md" in session["files"]
    pipeline_result = None

    if not has_resume:
        session["stage"] = "AWAITING_RESUME"
        msg = (
            f"📄 **Job Description Saved:** Stored to `/processed/jd.md`.\n\n"
            f"👉 **Next Step:** Upload your CV (`.docx` or `.pdf`) to kick off the multi-agent workflow."
        )
    else:
        session["stage"] = "PIPELINE_RUNNING"
        msg = f"📄 **Job Description Saved:** Both CV and JD loaded! Initiating multi-agent workflow..."
        try:
            pipeline_result = await agent.execute_full_pipeline_async(session)
            if pipeline_result.get("summary"):
                msg += f"\n\n{pipeline_result['summary']}"
        except Exception as pe:
            print(f"[Notice] Pipeline deferred: {pe}")
            msg += f"\n\n👉 You can ask in chat anytime to run research or tailor your materials."

    session["history"].append({"role": "user", "content": "Saved Job Description text."})
    session["history"].append({"role": "assistant", "content": msg})

    return {
        "session_id": sid,
        "stage": session["stage"],
        "files": session["files"],
        "ai_msg": msg,
        "pipeline": pipeline_result
    }


class UpdateJobTitleRequest(BaseModel):
    session_id: Optional[str] = None
    title: str
    company: Optional[str] = ""


@app.post("/api/update-job-title")
async def update_job_title(payload: UpdateJobTitleRequest):
    """Replace / update the target Job Title and Company in /processed/jd.md."""
    sid, session = get_session(payload.session_id)
    new_title = payload.title.strip()
    new_company = (payload.company or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Job title cannot be empty.")

    current_jd = session.get("files", {}).get("/processed/jd.md", "")
    lines = current_jd.split("\n") if current_jd else []

    header = f"# {new_title}"
    if new_company:
        header += f" — {new_company}"

    if lines and lines[0].startswith("#"):
        lines[0] = header
        updated_text = "\n".join(lines)
    else:
        updated_text = f"{header}\n\n" + (current_jd or "Target job requirements.")

    session["files"]["/processed/jd.md"] = updated_text
    return {
        "session_id": sid,
        "title": new_title,
        "company": new_company,
        "files": session["files"],
        "message": f"Target job title updated to '{new_title}'"
    }


class RemoveJdRequest(BaseModel):
    session_id: Optional[str] = None


@app.post("/api/remove-jd")
async def remove_jd(payload: RemoveJdRequest):
    """Clear the target Job Description from the workspace."""
    sid, session = get_session(payload.session_id)
    session["files"].pop("/processed/jd.md", None)
    return {
        "session_id": sid,
        "status": "removed",
        "message": "Job description cleared from workspace.",
        "files": session.get("files", {})
    }


@app.post("/api/extract-jd")
async def extract_job_description(payload: JobLinkRequest):
    sid, session = get_session(payload.session_id)
    url = payload.url.strip()

    # Normalize URL if user omitted protocol
    if not url.startswith("http://") and not url.startswith("https://"):
        if "." in url:
            url = "https://" + url
        else:
            raise HTTPException(status_code=400, detail="Invalid URL format. Please include http:// or https://")

    try:
        job_data = agent.extract_job_from_url(url)
        session["files"]["/processed/jd.md"] = job_data["markdown"]
        session["job_url"] = url

        has_resume = "/processed/resume.md" in session["files"]
        pipeline_result = None

        if not has_resume:
            session["stage"] = "AWAITING_RESUME"
            msg = (
                f"🔗 **Job Description Extracted:** Saved to `/processed/jd.md` via Tavily.\n\n"
                f"👉 **Next Step:** Upload your CV (`.docx` or `.pdf`) so the team of subagents can analyze the match and tailor your application."
            )
        else:
            session["stage"] = "PIPELINE_RUNNING"
            msg = f"🔗 **Job Description Extracted:** Both CV and JD ready! Multi-agent pipeline running..."
            try:
                pipeline_result = await agent.execute_full_pipeline_async(session)
                if pipeline_result.get("summary"):
                    msg += f"\n\n{pipeline_result['summary']}"
            except Exception as pe:
                print(f"[Warning] Pipeline run error: {pe}")
                msg += f"\n\n⚠️ Pipeline step warning: {pe}\nYou can ask in chat anytime to refine or regenerate artifacts."
                pipeline_result = {"status": "partial", "error": str(pe)}

        session["history"].append({"role": "user", "content": f"Target job URL: {url}"})
        session["history"].append({"role": "assistant", "content": msg})

        return {
            "session_id": sid,
            "stage": session["stage"],
            "url": url,
            "files": session["files"],
            "ai_msg": msg,
            "pipeline": pipeline_result
        }
    except Exception as e:
        print(f"[Error] /api/extract-jd: {e}")
        raise HTTPException(status_code=500, detail=f"Web extraction failed: {str(e)}")


@app.post("/api/run-pipeline")
async def run_pipeline(payload: ChatRequest):
    sid, session = get_session(payload.session_id)
    if "/processed/resume.md" not in session.get("files", {}):
        raise HTTPException(status_code=400, detail="Missing resume in /processed/resume.md")
    if "/processed/jd.md" not in session.get("files", {}):
        raise HTTPException(status_code=400, detail="Missing JD in /processed/jd.md")

    try:
        res = await agent.execute_full_pipeline_async(session)
        session["history"].append({"role": "assistant", "content": res.get("summary", "Workflow completed.")})
        return {
            "session_id": sid,
            "stage": session["stage"],
            "files": session["files"],
            "result": res
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(payload: ChatRequest):
    sid, session = get_session(payload.session_id)
    msg = payload.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # 0. Direct reset artifacts command in chat
    if msg.lower().strip() in ["reset artifacts", "/reset artifacts", "reset artifact", "/reset", "clear artifacts"]:
        artifact_paths = [
            "/research/recon_report.md",
            "/tailored_resume/resume.yaml",
            "/tailored_resume/tailored_resume.md",
            "/interview_coach/interview_prep.md",
            "/interview_battlecard/battlecard.md",
            "/supervisor/plan.json",
            "/supervisor/critic_verdicts.json",
        ]
        for path in artifact_paths:
            session.get("files", {}).pop(path, None)
        session.pop("plan", None)
        session.pop("pipeline_log", None)
        reply = "🧹 **Artifacts Reset:** All generated multi-agent reports (Company Recon, Tailored Resume, Interview Prep, Battlecard, Supervisor Plans) have been cleared. Your candidate CV and target JD are preserved."
        session["history"].append({"role": "user", "content": msg})
        session["history"].append({"role": "assistant", "content": reply})
        return {
            "session_id": sid,
            "stage": session.get("stage", "READY"),
            "reply": reply,
            "files": session.get("files", {}),
            "history": session["history"]
        }

    # 1. URL detection in chat
    urls = agent.extract_urls(msg)
    if urls and "/processed/jd.md" not in session.get("files", {}):
        target_url = urls[0]
        try:
            job_data = agent.extract_job_from_url(target_url)
            session["files"]["/processed/jd.md"] = job_data["markdown"]
            session["job_url"] = target_url

            if "/processed/resume.md" in session.get("files", {}):
                # Trigger full pipeline
                res = await agent.execute_full_pipeline_async(session)
                reply = f"🌐 **[Web Tool]:** Scraped job posting from `{target_url}`.\n\n{res.get('summary', '')}"
            else:
                reply = f"🌐 **[Web Tool]:** Scraped job posting from `{target_url}`.\n\n👉 **Next Step:** Upload your CV so the subagents can tailor your resume and prep."

            session["history"].append({"role": "user", "content": msg})
            session["history"].append({"role": "assistant", "content": reply})
            return {
                "session_id": sid,
                "stage": session["stage"],
                "reply": reply,
                "files": session["files"],
                "history": session["history"]
            }
        except Exception as e:
            print(f"[Warning] Chat url extraction error: {e}")

    # 2. Intake step check
    has_resume = "/processed/resume.md" in session.get("files", {})
    has_jd = "/processed/jd.md" in session.get("files", {})

    if not has_resume:
        reply = (
            f"👋 **Goal Acknowledged!** I am your lead `career_agent` supervisor.\n\n"
            f"To kick off the workflow, **please upload your resume** (`.docx` or `.pdf`) using the workspace on the right, or paste its text here."
        )
        session["history"].append({"role": "user", "content": msg})
        session["history"].append({"role": "assistant", "content": reply})
        return {"session_id": sid, "stage": "AWAITING_RESUME", "reply": reply, "files": session.get("files", {})}

    if not has_jd and not urls:
        reply = (
            f"Got it! I have your resume loaded in `/processed/resume.md`.\n\n"
            f"👉 To generate your tailored resume and battlecard, **please send me your target Job Description URL or text**."
        )
        session["history"].append({"role": "user", "content": msg})
        session["history"].append({"role": "assistant", "content": reply})
        return {"session_id": sid, "stage": "AWAITING_JD", "reply": reply, "files": session.get("files", {})}

    # 3. Artifact-routed surgical follow-up chat
    # Both resume and JD exist. Route to owning agent!
    target_agent, reply, updated_files, tools_used = agent.handle_followup_turn(msg, session)
    session["files"] = updated_files
    session["history"].append({"role": "user", "content": msg})
    session["history"].append({"role": "assistant", "content": reply})

    return {
        "session_id": sid,
        "stage": session["stage"],
        "routed_agent": target_agent,
        "tools_used": tools_used,
        "reply": reply,
        "files": session["files"],
        "history": session["history"]
    }


@app.post("/api/approve")
async def approve_session(payload: ApproveRequest):
    """User Approval endpoint: persists approved artifacts to Career Memory."""
    sid, session = get_session(payload.session_id)
    try:
        result = agent.approve_and_save_to_memory(session)
        return {
            "session_id": sid,
            "stage": session.get("stage"),
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ResetArtifactsRequest(BaseModel):
    session_id: Optional[str] = None
    reset_all: bool = False


@app.post("/api/reset-artifacts")
async def reset_artifacts(payload: ResetArtifactsRequest):
    """Reset multi-agent artifacts or full workspace session."""
    sid, session = get_session(payload.session_id)
    artifact_paths = [
        "/research/recon_report.md",
        "/tailored_resume/resume.yaml",
        "/tailored_resume/tailored_resume.md",
        "/interview_coach/interview_prep.md",
        "/interview_battlecard/battlecard.md",
        "/supervisor/plan.json",
        "/supervisor/critic_verdicts.json",
    ]
    for path in artifact_paths:
        session.get("files", {}).pop(path, None)

    session.pop("plan", None)
    session.pop("pipeline_log", None)

    if payload.reset_all:
        session["files"] = {}
        session["history"] = []
        session.pop("resume_filename", None)
        session.pop("job_url", None)
        session["stage"] = "AWAITING_INPUT"
        msg = "Full workspace and artifacts reset."
    else:
        has_resume = bool(session.get("files", {}).get("/processed/resume.md"))
        has_jd = bool(session.get("files", {}).get("/processed/jd.md"))
        session["stage"] = "READY" if (has_resume and has_jd) else ("AWAITING_JD" if has_resume else "AWAITING_RESUME")
        msg = "Generated artifacts (Recon, Tailored Resume, Prep, Battlecard, Supervisor Plans) reset."

    return {
        "session_id": sid,
        "status": "reset",
        "message": msg,
        "files": session.get("files", {})
    }


@app.get("/api/memory")
async def get_memory():
    """Return all career memory profiles (for debug/review)."""
    try:
        return agent.load_memory()
    except Exception as e:
        return {"error": str(e)}


@app.put("/api/workspace/save")
async def save_file(payload: FileSaveRequest):
    sid, session = get_session(payload.session_id)
    session["files"][payload.path] = payload.content
    return {"status": "saved", "path": payload.path}


# ─────────────────────────────────────────────────────────────────────────────
#  FEATURE TEAM ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class SimTurnRequest(BaseModel):
    session_id: Optional[str] = None
    round_type: str = "behavioral"
    user_answer: Optional[str] = None
    action: Optional[str] = None


class JobFinderRequest(BaseModel):
    session_id: Optional[str] = None
    query: str = ""
    company: Optional[str] = ""
    country: Optional[str] = ""
    filters: Optional[list] = []


class SelectTargetJdRequest(BaseModel):
    session_id: Optional[str] = None
    title: str
    company: str
    description: Optional[str] = ""
    skills: Optional[list] = []
    location: Optional[str] = ""
    url: Optional[str] = ""


class TailorResumePdfRequest(BaseModel):
    session_id: Optional[str] = None
    role: str
    company: str
    description: Optional[str] = ""
    skills: Optional[list] = []
    location: Optional[str] = ""


class InterviewGuideRequest(BaseModel):
    session_id: Optional[str] = None
    role: str
    company: str
    description: Optional[str] = ""
    skills: Optional[list] = []
    location: Optional[str] = ""


class CareerSwitchRequest(BaseModel):
    session_id: Optional[str] = None
    current_role: Optional[str] = "Software Developer"
    target_role: Optional[str] = "QA Tester"
    experience_level: Optional[str] = "Mid-Level (3-5 yrs)"
    currency: Optional[str] = "USD"


class JobMatchRequest(BaseModel):
    message: Optional[str] = "run"
    session_id: Optional[str] = None
    resume_text: Optional[str] = None
    resume_artifact_path: Optional[str] = None
    jd_text: Optional[str] = None
    jd_role: Optional[str] = None
    jd_url: Optional[str] = None


@app.post("/api/job-match")
async def job_match_analysis(payload: JobMatchRequest):
    """Feature Team 1 — Job Match Analysis.
    Compares candidate resume (uploaded or selected artifact) against
    target job (typed role, full description, or scraped URL).
    """
    sid, session = get_session(payload.session_id)

    # 1. Resolve Resume
    selected_resume = ""
    if payload.resume_text and payload.resume_text.strip():
        selected_resume = payload.resume_text.strip()
    elif payload.resume_artifact_path and payload.resume_artifact_path in session.get("files", {}):
        selected_resume = session["files"][payload.resume_artifact_path].strip()
    elif session.get("files", {}).get("/processed/resume.md", "").strip():
        selected_resume = session["files"]["/processed/resume.md"].strip()

    if not selected_resume:
        raise HTTPException(
            status_code=400,
            detail="No candidate resume found. Please upload a CV (.pdf, .docx, .txt) or select an artifact from the workspace."
        )
    session["files"]["/processed/resume.md"] = selected_resume

    # 2. Resolve Target Job (Role / Description / URL)
    selected_jd = ""
    if payload.jd_url and payload.jd_url.strip():
        target_url = payload.jd_url.strip()
        if not target_url.startswith("http://") and not target_url.startswith("https://"):
            target_url = "https://" + target_url
        try:
            job_data = agent.extract_job_from_url(target_url)
            selected_jd = job_data.get("markdown", "")
            session["job_url"] = target_url
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to scrape job link: {str(e)}")
    elif payload.jd_text and payload.jd_text.strip():
        selected_jd = payload.jd_text.strip()
    elif payload.jd_role and payload.jd_role.strip():
        role_title = payload.jd_role.strip()
        selected_jd = f"# {role_title}\n\n**Role Title:** {role_title}\n\nTarget benchmark competencies, requirements, and responsibilities for {role_title}."
    elif session.get("files", {}).get("/processed/jd.md", "").strip():
        selected_jd = session["files"]["/processed/jd.md"].strip()

    if not selected_jd:
        raise HTTPException(
            status_code=400,
            detail="No target job specified. Please type a job role, paste a description, or provide a job posting link."
        )
    session["files"]["/processed/jd.md"] = selected_jd

    try:
        result = await agent.run_job_match_pipeline(session)
        return {"session_id": sid, "result": result, "files": session.get("files", {})}
    except Exception as e:
        print(f"[Error] job-match pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sim-turn")
async def sim_turn(payload: SimTurnRequest):
    """Feature Team 2 — Interview Simulator.
    Runs: interviewer → interview-prober → interview-evaluator.
    """
    sid, session = get_session(payload.session_id)
    try:
        result = await asyncio.to_thread(
            agent.run_sim_turn, session, payload.round_type, payload.user_answer, payload.action
        )
        return {"session_id": sid, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resources")
async def generate_resources(payload: ChatRequest):
    """Feature Team 3 — Resources.
    Runs: gap-analyzer → resource-researcher → learning-planner.
    """
    sid, session = get_session(payload.session_id)
    topic = payload.message.strip() if payload.message else ""
    try:
        result = await agent.run_resources_pipeline(session, topic=topic)
        return {"session_id": sid, **result, "files": session.get("files", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/job-finder")
async def find_jobs(payload: JobFinderRequest):
    """Feature Team 4 — Job Finder.
    Runs: job-discovery (with role, company, country filters) → job-normalizer → opportunity-matcher.
    """
    sid, session = get_session(payload.session_id)
    if not payload.query.strip() and not (payload.company or "").strip() and not (payload.country or "").strip():
        raise HTTPException(status_code=400, detail="Please enter a role, company, or country/location to search.")
    try:
        result = await agent.run_job_finder_pipeline(
            payload.query,
            payload.filters or [],
            session,
            company=(payload.company or "").strip(),
            country=(payload.country or "").strip(),
        )
        return {"session_id": sid, **result, "files": session.get("files", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/select-target-job")
async def select_target_job(payload: SelectTargetJdRequest):
    """Sets a discovered job as the active target job description (/processed/jd.md)."""
    sid, session = get_session(payload.session_id)
    skills_formatted = "\n".join(f"- {s}" for s in payload.skills) if payload.skills else "- Core role skills"
    jd_md = (
        f"# {payload.company} — {payload.title}\n\n"
        f"- **Company:** {payload.company}\n"
        f"- **Role:** {payload.title}\n"
        f"- **Location:** {payload.location or 'Remote'}\n"
        f"- **Posting URL:** {payload.url or 'N/A'}\n\n"
        f"## Role Summary\n{payload.description or 'Target role selected from Job Finder.'}\n\n"
        f"## Required & Preferred Qualifications\n{skills_formatted}\n"
    )
    session["files"]["/processed/jd.md"] = jd_md
    session["job_url"] = payload.url or ""
    session["job_title"] = payload.title
    session["company_name"] = payload.company
    session["stage"] = "JD_LOADED"

    session["history"].append({
        "role": "user",
        "content": f"Selected target job: {payload.title} at {payload.company}."
    })
    session["history"].append({
        "role": "assistant",
        "content": f"🎯 **Target Job Loaded:** `{payload.title} at {payload.company}` has been saved into `/processed/jd.md`!\n\nYou can now run **Job Match Analysis**, tailor your resume, or practice mock interview rounds for this specific role."
    })

    return {
        "session_id": sid,
        "message": f"Target job set: {payload.title} at {payload.company}",
        "files": session["files"],
        "stage": session["stage"]
    }


@app.post("/api/career-switch")
async def career_switch_endpoint(payload: CareerSwitchRequest):
    """Feature Team 5 — Career Switch Advisor.
    Evaluates role transition, comparative salary trajectory curves, pros/cons,
    objective better option verdict, and general switching dynamics.
    """
    sid, session = get_session(payload.session_id)
    try:
        result = await agent.run_career_switch_pipeline(
            current_role=payload.current_role or "Software Developer",
            target_role=payload.target_role or "QA Tester",
            experience_level=payload.experience_level or "Mid-Level (3-5 yrs)",
            currency=payload.currency or "USD",
            session=session
        )
        return {"session_id": sid, **result}
    except Exception as e:
        print(f"[Error] career-switch pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/job-finder/tailor-resume")
async def tailor_resume_endpoint(payload: TailorResumePdfRequest):
    """Generates an ATS-tailored resume in PDF format matching Abinesh's template."""
    sid, session = get_session(payload.session_id)
    from local_app.agents.pdf_generator import tailor_resume_data, build_ats_resume_pdf

    # 1. Run LLM tailoring agent
    resume_override = session.get("files", {}).get("/processed/resume.md", "")
    tailored_data = await asyncio.to_thread(
        tailor_resume_data,
        payload.role,
        payload.company,
        payload.description or "",
        payload.skills or [],
        resume_override
    )

    # 2. Render ATS PDF
    gen_dir = os.path.join(os.path.dirname(__file__), "generated_resumes")
    os.makedirs(gen_dir, exist_ok=True)
    safe_comp = re.sub(r"[^\w\-]", "_", payload.company)[:20] or "TargetCompany"
    safe_role = re.sub(r"[^\w\-]", "_", payload.role)[:25] or "TargetRole"
    filename = f"Resume_Abinesh_{safe_comp}_{safe_role}.pdf"
    pdf_path = os.path.join(gen_dir, filename)

    await asyncio.to_thread(build_ats_resume_pdf, tailored_data, pdf_path)

    # Record activity in session history
    session["history"].append({
        "role": "assistant",
        "content": f"📄 **Tailored ATS Resume Generated:** Compiled single-page PDF for `{payload.role} at {payload.company}`."
    })

    return {
        "session_id": sid,
        "filename": filename,
        "download_url": f"/api/download-resume-pdf?filename={filename}",
        "tailored_data": tailored_data,
        "role": payload.role,
        "company": payload.company
    }


@app.get("/api/download-resume-pdf")
async def download_resume_pdf(filename: str):
    """Serves the generated ATS PDF resume."""
    clean_name = os.path.basename(filename)
    gen_dir = os.path.join(os.path.dirname(__file__), "generated_resumes")
    file_path = os.path.join(gen_dir, clean_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resume PDF not found.")
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=clean_name,
        headers={"Content-Disposition": f"inline; filename={clean_name}"}
    )


@app.post("/api/job-finder/interview-guide")
async def interview_guide_endpoint(payload: InterviewGuideRequest):
    """Performs deep gap analysis and generates a role-tailored interview battlecard."""
    sid, session = get_session(payload.session_id)
    from local_app.agents.job_interview_guide import generate_job_interview_guide

    resume_text = session.get("files", {}).get("/processed/resume.md", "")
    guide = await asyncio.to_thread(
        generate_job_interview_guide,
        payload.role,
        payload.company,
        payload.description or "",
        payload.skills or [],
        resume_text
    )

    return {
        "session_id": sid,
        "guide": guide,
        "role": payload.role,
        "company": payload.company
    }


static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>NextRole Copilot Running</h1>")


@app.get("/architecture")
@app.get("/architecture.html")
async def architecture_page():
    arch_file = os.path.join(static_dir, "architecture.html")
    if os.path.exists(arch_file):
        with open(arch_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Architecture Diagram Not Found</h1>", status_code=404)
