"""NextRole FastAPI Server.
Full multi-agent architecture with supervisor, 3 specialist subagents, parallel execution,
workspace file storage, and artifact-routed follow-up chat.
"""

import os
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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

SESSIONS: Dict[str, Dict[str, Any]] = {}


def get_session(session_id: Optional[str]) -> tuple[str, Dict[str, Any]]:
    if not session_id or session_id not in SESSIONS:
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = {
            "id": session_id,
            "stage": "AWAITING_INTAKE",
            "files": {},  # Maps virtual path -> content string
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
            raise HTTPException(status_code=400, detail="Could not extract text from uploaded resume.")

        session["files"]["/processed/resume.md"] = parsed_text
        session["resume_filename"] = file.filename

        has_jd = "/processed/jd.md" in session["files"]

        if not has_jd:
            session["stage"] = "AWAITING_JD"
            msg = (
                f"📄 **Resume Processed:** Saved to `/processed/resume.md` ({len(parsed_text)} chars).\n\n"
                f"👉 **Next Step:** I need your target **Job Description (JD)**. Paste a job link (URL) or text to initiate web recon & tailoring."
            )
            pipeline_result = None
        else:
            session["stage"] = "PIPELINE_RUNNING"
            msg = f"📄 **Resume Processed:** Both CV and JD are now ready! Spawning specialist subagents in parallel..."
            pipeline_result = await agent.execute_full_pipeline_async(session)
            if pipeline_result.get("summary"):
                msg += f"\n\n{pipeline_result['summary']}"

        session["history"].append({"role": "user", "content": f"Uploaded resume: {file.filename}"})
        session["history"].append({"role": "assistant", "content": msg})

        return {
            "session_id": sid,
            "stage": session["stage"],
            "filename": file.filename,
            "files": session["files"],
            "ai_msg": msg,
            "pipeline": pipeline_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    target_agent, reply, updated_files = agent.handle_followup_turn(msg, session)
    session["files"] = updated_files
    session["history"].append({"role": "user", "content": msg})
    session["history"].append({"role": "assistant", "content": reply})

    return {
        "session_id": sid,
        "stage": session["stage"],
        "routed_agent": target_agent,
        "reply": reply,
        "files": session["files"],
        "history": session["history"]
    }


@app.put("/api/workspace/save")
async def save_file(payload: FileSaveRequest):
    sid, session = get_session(payload.session_id)
    session["files"][payload.path] = payload.content
    return {"status": "saved", "path": payload.path}


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
