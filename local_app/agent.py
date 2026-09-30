"""NextRole Multi-Agent Local Engine.
Implements the authentic 5-stage supervisor + 3 specialist subagents architecture:
1. Intake & Document Processing (LlamaParse / python-docx / pypdf)
2. Web JD Extraction (Tavily)
3. Pre-Interview Reconnaissance (hiring-recon subagent via Tavily web search)
4. Parallel Resume Tailoring (resume-tailor) & Interview Coaching (interview-coach)
5. Day-of Interview Battlecard (Supervisor synthesis)
6. Artifact-Routed Follow-Up Chat (Surgical edit routing to the owning agent)
"""

import os
import re
import io
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash"]


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in .env")
    return genai.Client(api_key=api_key)


def generate_llm(prompt: str, system_instruction: Optional[str] = None) -> str:
    """Invokes Gemini with automatic model failover and retries."""
    client = get_genai_client()
    models = [PRIMARY_MODEL] + FALLBACK_MODELS
    last_err = None

    for m in models:
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction
            ) if system_instruction else None

            resp = client.models.generate_content(
                model=m,
                contents=prompt,
                config=config,
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            print(f"[Model attempt failed] {m}: {e}")
            # If quota exhausted or model unavailable, immediately try the next model!
            if "quota" in err_str or "resource_exhausted" in err_str or "404" in err_str or "not_found" in err_str:
                continue
            time.sleep(0.5)

    raise RuntimeError(f"All LLM models failed. Last error: {last_err}")


# ============================================================================
# DOCUMENT PROCESSING (Stage 2)
# ============================================================================

def extract_docx_bytes(file_bytes: bytes) -> str:
    """Extract all text, paragraphs, and tables from DOCX binary."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        sections = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                sections.append(txt)
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                dedup = []
                for c in cells:
                    if not dedup or dedup[-1] != c:
                        dedup.append(c)
                if dedup:
                    sections.append(" | ".join(dedup))
        combined = "\n\n".join(sections)
        if combined.strip():
            return combined.strip()
    except Exception as e:
        print(f"[Warning] python-docx error: {e}")

    # Fallback zipfile XML
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for p in tree.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                texts = [node.text for node in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if node.text]
                if texts:
                    val = "".join(texts).strip()
                    if val:
                        paragraphs.append(val)
            if paragraphs:
                return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"[Warning] docx xml fallback error: {e}")

    return ""


def parse_resume_bytes(filename: str, file_bytes: bytes) -> str:
    """Parse resume binary into clean Markdown."""
    lower_name = filename.lower()
    text = ""

    if lower_name.endswith(".docx") or lower_name.endswith(".doc"):
        text = extract_docx_bytes(file_bytes)
        if not text.strip() and LLAMA_CLOUD_API_KEY:
            try:
                from llama_parse import LlamaParse
                parser = LlamaParse(api_key=LLAMA_CLOUD_API_KEY, result_type="markdown", verbose=False)
                documents = parser.load_data(file_bytes, extra_info={"file_name": filename})
                if documents:
                    text = "\n\n".join([d.text for d in documents])
            except Exception as e:
                print(f"[Warning] LlamaParse DOCX error: {e}")

    elif lower_name.endswith(".pdf"):
        if LLAMA_CLOUD_API_KEY:
            try:
                from llama_parse import LlamaParse
                parser = LlamaParse(api_key=LLAMA_CLOUD_API_KEY, result_type="markdown", verbose=False)
                documents = parser.load_data(file_bytes, extra_info={"file_name": filename})
                if documents:
                    text = "\n\n".join([d.text for d in documents])
            except Exception as e:
                print(f"[Warning] LlamaParse PDF error: {e}")

        if not text.strip():
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages = []
                for i, page in enumerate(reader.pages):
                    t = page.extract_text() or ""
                    if t.strip():
                        pages.append(f"## Page {i+1}\n\n{t}")
                text = "\n\n".join(pages)
            except Exception as e:
                print(f"[Warning] pypdf error: {e}")

    if not text.strip():
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

    return text.strip()


def extract_job_from_url(url: str) -> Dict[str, Any]:
    """Extract job description text and metadata from URL using Tavily."""
    if not TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY is missing in .env")

    from tavily import TavilyClient
    client = TavilyClient(api_key=TAVILY_API_KEY)
    raw_text = ""

    try:
        if hasattr(client, "extract"):
            res = client.extract(urls=[url])
            if res and "results" in res and len(res["results"]) > 0:
                raw_text = res["results"][0].get("raw_content", "")
    except Exception as e:
        print(f"[Notice] Tavily extract: {e}")

    if not raw_text:
        search_res = client.search(query=f"job opening details {url}", max_results=3)
    if not raw_text.strip():
        raw_text = f"Job listing extracted from {url}. Review the web source at {url}."

    prompt = f"""You are an expert technical recruiter and job analyst.
Extract and structure the following raw job description into clean Markdown.

Raw content:
\"\"\"
{raw_text[:9000]}
\"\"\"

Format with:
# <Company Name> — <Role Title>
- **Location:** <Location> (<Remote/Hybrid/Onsite>)
- **Employment Type:** <Full-time/Contract>
- **Target Level:** <Senior/Staff/Lead/Mid>

## Role Summary
<2-3 concise sentences>

## Key Responsibilities
- ...

## Required Qualifications & Must-Have Skills
- ...

## Preferred Qualifications
- ...

## Tech Stack & Tools
- ...
"""
    try:
        structured_markdown = generate_llm(prompt, system_instruction="You extract accurate, actionable job posting information.")
    except Exception as e:
        print(f"[Warning] LLM structuring error for JD ({e}); using direct markdown fallback.")
        structured_markdown = f"# Target Job Posting\n\n**Source URL:** {url}\n\n## Job Description\n\n{raw_text[:7000]}"

    return {
        "url": url,
        "markdown": structured_markdown
    }


def extract_urls(text: str) -> List[str]:
    pattern = r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)"
    return re.findall(pattern, text)


# ============================================================================
# SPECIALIST SUBAGENT 1: hiring-recon
# ============================================================================

def run_hiring_recon(resume_text: str, jd_text: str, update_request: Optional[str] = None, existing_report: Optional[str] = None) -> str:
    """Pre-interview reconnaissance analyst subagent.
    Gathers company intel, financial & hiring signals, culture, salary range, and match analysis.
    """
    company_name = "Target Company"
    first_lines = jd_text.split("\n")[:5]
    for line in first_lines:
        if "—" in line:
            company_name = line.split("—")[0].replace("#", "").strip()
            break
        elif "-" in line:
            company_name = line.split("-")[0].replace("#", "").strip()
            break

    # Live web research via Tavily
    web_intel = ""
    if TAVILY_API_KEY:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=TAVILY_API_KEY)
            q1 = f"{company_name} company overview business model tech stack"
            q2 = f"{company_name} layoffs funding revenue hiring culture glassdoor"
            r1 = client.search(q1, max_results=2)
            r2 = client.search(q2, max_results=2)
            web_intel = "\n".join([res.get("content", "") for res in r1.get("results", []) + r2.get("results", [])])
        except Exception as e:
            print(f"[Warning] Tavily recon search error: {e}")

    sys_prompt = """You are the `hiring-recon` specialist subagent in NextRole.
Your role: Pre-interview reconnaissance analyst.
You produce a rigorous, unvarnished intelligence report covering:
1. Company snapshot (stage, business model, size, recent news)
2. Financial & hiring signals (funding, headcount trends, layoffs)
3. Reputation & culture (Glassdoor themes, attrition patterns)
4. Role market context & realistic salary band
5. Match analysis:
   - Strengths to emphasize (exact alignments)
   - Critical skill gaps / mitigations (missing JD keywords or experiences)
   - Top 3-5 strategic focus areas
"""

    if update_request and existing_report:
        prompt = f"""UPDATE MODE:
The candidate requested this surgical update to the existing research report:
"{update_request}"

Existing report:
{existing_report}

Target JD:
{jd_text}

Candidate Resume:
{resume_text}

Update the relevant section while strictly preserving all other existing analysis."""
    else:
        prompt = f"""CREATE MODE:
Company Name: {company_name}

Target Job Description:
{jd_text}

Candidate Resume:
{resume_text}

Live Web Intelligence:
{web_intel[:3000]}

Generate the complete `# {company_name} Reconnaissance Report` in Markdown."""

    return generate_llm(prompt, system_instruction=sys_prompt)


# ============================================================================
# SPECIALIST SUBAGENT 2: resume-tailor
# ============================================================================

def run_resume_tailor(resume_text: str, jd_text: str, research_report: str, update_request: Optional[str] = None, existing_yaml: Optional[str] = None) -> Tuple[str, str]:
    """Resume editor subagent.
    Generates tailored RenderCV YAML and formatted Markdown tailored to the JD & recon report.
    """
    sys_prompt = """You are the `resume-tailor` specialist subagent in NextRole.
Your role: Senior executive resume editor.
You rewrite the candidate's resume tailored to this specific JD and hiring-recon report.
You DO NOT invent experiences or fake titles. You strategically highlight relevant achievements using quantifiable STAR impact metrics (e.g. 'Engineered X resulting in Y% performance improvement').
You must generate:
1. Valid, clean RenderCV YAML.
2. Formatted Markdown presentation.
"""

    if update_request and existing_yaml:
        prompt = f"""UPDATE MODE:
The user requested a surgical edit to their tailored resume:
"{update_request}"

Existing RenderCV YAML:
{existing_yaml}

Target JD:
{jd_text}

Candidate Resume:
{resume_text}

Apply the requested changes to the YAML and Markdown summary. Maintain all other experience intact."""
    else:
        prompt = f"""CREATE MODE:
Rewrite the candidate's resume tailored to the target role.

Candidate Resume:
{resume_text}

Target Job Description:
{jd_text}

Hiring Recon Report (Priority Signals & Match Gaps):
{research_report}

Generate two sections:
SECTION 1: ```yaml
cv:
  name: <Full Name>
  location: <Location>
  email: <Email>
  headline: <Target Role Headline>
  sections:
    summary:
      - <3-sentence punchy summary highlighting JD keywords>
    skills:
      - name: Core Technologies
        details: <relevant skills>
      - name: Tools & Frameworks
        details: <tools>
    experience:
      - company: <Company>
        position: <Title>
        start_date: <Start>
        end_date: <End>
        highlights:
          - <Tailored bullet with action verb and quantifiable metric>
          - <Tailored bullet addressing target JD requirements>
    education:
      - institution: <University>
        degree: <Degree>
```

SECTION 2: Detailed Markdown preview of the rewritten resume."""

    raw_output = generate_llm(prompt, system_instruction=sys_prompt)

    # Extract YAML block
    yaml_content = ""
    if "```yaml" in raw_output:
        parts = raw_output.split("```yaml")
        if len(parts) > 1:
            yaml_content = parts[1].split("```")[0].strip()
    elif "```" in raw_output:
        parts = raw_output.split("```")
        if len(parts) > 1:
            yaml_content = parts[1].strip()

    if not yaml_content:
        yaml_content = f"# Tailored RenderCV Spec\ncv:\n  summary:\n    - Tailored for target position\n"

    return yaml_content, raw_output


# ============================================================================
# SPECIALIST SUBAGENT 3: interview-coach
# ============================================================================

def run_interview_coach(resume_text: str, jd_text: str, research_report: str, update_request: Optional[str] = None, existing_prep: Optional[str] = None) -> str:
    """Interview coach subagent.
    Produces 60s/30s elevator pitches, round-by-round strategies, and STAR stories.
    """
    sys_prompt = """You are the `interview-coach` specialist subagent in NextRole.
Your role: Elite interview strategist and coach.
You prepare the candidate for high-stakes interviews with:
1. Reusable Self-Introduction:
   - 60-Second Elevator Pitch (~120 words)
   - 30-Second Short Pitch (~60 words)
2. Round-by-round interview strategy:
   - Round 1: Recruiter Screen (narrative, salary framing, role alignment)
   - Round 2: Hiring Manager Behavioral (leadership, conflict, cross-functional)
   - Round 3: Technical Deep-Dive / System Design (architecture, scale, trade-offs)
3. 3 Custom STAR Stories (Situation, Task, Action, Result) drawn directly from the candidate's resume, specifically bridging the skill gaps identified in the recon report.
4. 4 High-impact Reverse-Interview Questions to ask the interviewers.
"""

    if update_request and existing_prep:
        prompt = f"""UPDATE MODE:
The user requested this specific change to their interview prep doc:
"{update_request}"

Existing prep doc:
{existing_prep}

Target JD:
{jd_text}

Candidate Resume:
{resume_text}

Update the relevant rounds or stories, preserving all other prep intact."""
    else:
        prompt = f"""CREATE MODE:
Candidate Resume:
{resume_text}

Target Job Description:
{jd_text}

Hiring Recon Report:
{research_report}

Generate the comprehensive `# Interview Prep Doc` in Markdown."""

    return generate_llm(prompt, system_instruction=sys_prompt)


# ============================================================================
# SUPERVISOR AGENT: career_agent (Orchestrator & Battlecard Synthesis)
# ============================================================================

def run_battlecard_synthesis(resume_text: str, jd_text: str, research_report: str, prep_doc: str) -> str:
    """Assembles the final day-of interview battlecard (cheat sheet)."""
    prompt = f"""You are the `career_agent` supervisor synthesizing the final Day-of Battlecard.
Create a compact, 1-page per round cheat sheet the candidate can review 10 minutes before joining the interview call.

Candidate Resume highlights:
{resume_text[:2000]}

Target JD:
{jd_text[:2000]}

Research signals:
{research_report[:2000]}

Interview Prep doc:
{prep_doc[:3000]}

Format as a high-density, beautifully structured Markdown Battlecard with:
# ⚡ Day-of Interview Battlecard
- **Company & Role:** ...
- **Core Narrative:** 2-sentence positioning anchor

## Quick Pitch Anchor (60-sec reminder)
- Opening sentence: ...
- 2 Proof points: ...
- Closing: Why this company: ...

## Round 1 Cheat Sheet: Recruiter Screen
- 3 Questions & Bulleted Answers
- Key talking points & salary anchor

## Round 2 Cheat Sheet: Hiring Manager & Leadership
- 3 STAR Story Triggers (Situation -> Action -> Result metrics)

## Round 3 Cheat Sheet: Technical Architecture & Systems
- Key systems to cite, architecture trade-offs, metrics achieved

## 3 Critical Questions to Ask Them
1. ...
2. ...
3. ...
"""
    return generate_llm(prompt, system_instruction="You synthesize high-density, elite day-of interview cheat sheets.")


# ============================================================================
# PARALLEL PIPELINE EXECUTION
# ============================================================================

async def execute_full_pipeline_async(session: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrates the 5-stage pipeline:
    Stage 1 & 2: Resume + JD already parsed.
    Stage 3: hiring-recon subagent runs web research.
    Stage 4: resume-tailor & interview-coach run IN PARALLEL.
    Stage 5: Supervisor compiles day-of battlecard.
    """
    resume_text = session.get("files", {}).get("/processed/resume.md", "")
    jd_text = session.get("files", {}).get("/processed/jd.md", "")

    if not resume_text or not jd_text:
        return {"status": "error", "message": "Missing resume or JD in session."}

    # Stage 3: Hiring Recon
    recon_report = await asyncio.to_thread(run_hiring_recon, resume_text, jd_text)
    session["files"]["/research/recon_report.md"] = recon_report

    # Stage 4: Run resume-tailor and interview-coach in parallel!
    tailor_task = asyncio.to_thread(run_resume_tailor, resume_text, jd_text, recon_report)
    coach_task = asyncio.to_thread(run_interview_coach, resume_text, jd_text, recon_report)

    (yaml_content, tailor_preview), prep_doc = await asyncio.gather(tailor_task, coach_task)

    session["files"]["/tailored_resume/resume.yaml"] = yaml_content
    session["files"]["/tailored_resume/tailored_resume.md"] = tailor_preview
    session["files"]["/interview_coach/interview_prep.md"] = prep_doc

    # Stage 5: Supervisor Battlecard
    battlecard = await asyncio.to_thread(run_battlecard_synthesis, resume_text, jd_text, recon_report, prep_doc)
    session["files"]["/interview_battlecard/battlecard.md"] = battlecard

    session["stage"] = "COMPLETED"

    summary_text = (
        "### 🚀 Full Multi-Agent Workflow Executed!\n\n"
        "1. **🔍 `hiring-recon`:** Completed live web research on company, salary, and match gaps (`/research/recon_report.md`).\n"
        "2. **✍️ `resume-tailor`:** Re-engineered your resume and emitted RenderCV YAML (`/tailored_resume/resume.yaml`).\n"
        "3. **🎯 `interview-coach`:** Formulated self-introductions and per-round STAR stories in parallel (`/interview_coach/interview_prep.md`).\n"
        "4. **⚡ `career_agent`:** Compiled your day-of interview battlecard (`/interview_battlecard/battlecard.md`).\n\n"
        "**All artifacts are available in the Workspace on the right.** You can now iterate by chatting (e.g. *'Add Docker to skills'*, *'Add a 4th interview round'*)."
    )

    return {
        "status": "success",
        "summary": summary_text,
        "files": session["files"]
    }


# ============================================================================
# STAGE 6: SURGICAL FOLLOW-UP ROUTING
# ============================================================================

def classify_and_route_followup(user_message: str) -> str:
    """Classifies user's follow-up request to the owning agent:
    - 'resume-tailor' (resume, skills, bullets, experiences, formatting)
    - 'interview-coach' (interview, questions, pitch, rounds, STAR stories)
    - 'hiring-recon' (company, funding, culture, salaries, competitors, research)
    - 'career-agent' (battlecard, general questions, summary)
    """
    prompt = f"""Classify which specialist agent owns this user request:
User Request: "{user_message}"

Allowed outputs (reply with EXACTLY one of these four tags, nothing else):
- resume-tailor
- interview-coach
- hiring-recon
- career-agent
"""
    tag = generate_llm(prompt, system_instruction="You are a strict intent router.").strip().lower()
    for valid in ["resume-tailor", "interview-coach", "hiring-recon", "career-agent"]:
        if valid in tag:
            return valid
    return "career-agent"


def handle_followup_turn(user_message: str, session: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """Routes follow-up edit to the owning agent, performs surgical file update, and returns (agent_tag, response_msg, updated_files)."""
    target_agent = classify_and_route_followup(user_message)
    files = session.get("files", {})

    resume_text = files.get("/processed/resume.md", "")
    jd_text = files.get("/processed/jd.md", "")

    if target_agent == "resume-tailor":
        existing_yaml = files.get("/tailored_resume/resume.yaml", "")
        new_yaml, new_preview = run_resume_tailor(
            resume_text=resume_text,
            jd_text=jd_text,
            research_report=files.get("/research/recon_report.md", ""),
            update_request=user_message,
            existing_yaml=existing_yaml
        )
        files["/tailored_resume/resume.yaml"] = new_yaml
        files["/tailored_resume/tailored_resume.md"] = new_preview
        msg = f"✍️ **[Routed to `resume-tailor`]:** Updated `/tailored_resume/resume.yaml` based on: *\"{user_message}\"*\n\nReview the updated YAML and Markdown in the workspace!"
        return target_agent, msg, files

    elif target_agent == "interview-coach":
        existing_prep = files.get("/interview_coach/interview_prep.md", "")
        new_prep = run_interview_coach(
            resume_text=resume_text,
            jd_text=jd_text,
            research_report=files.get("/research/recon_report.md", ""),
            update_request=user_message,
            existing_prep=existing_prep
        )
        files["/interview_coach/interview_prep.md"] = new_prep
        msg = f"🎯 **[Routed to `interview-coach`]:** Updated `/interview_coach/interview_prep.md` with: *\"{user_message}\"*\n\nCheck the updated prep doc in the workspace."
        return target_agent, msg, files

    elif target_agent == "hiring-recon":
        existing_recon = files.get("/research/recon_report.md", "")
        new_recon = run_hiring_recon(
            resume_text=resume_text,
            jd_text=jd_text,
            update_request=user_message,
            existing_report=existing_recon
        )
        files["/research/recon_report.md"] = new_recon
        msg = f"🔍 **[Routed to `hiring-recon`]:** Updated research report `/research/recon_report.md` with additional intelligence."
        return target_agent, msg, files

    else:
        # General conversation or battlecard update
        if "battlecard" in user_message.lower():
            new_battlecard = run_battlecard_synthesis(
                resume_text=resume_text,
                jd_text=jd_text,
                research_report=files.get("/research/recon_report.md", ""),
                prep_doc=files.get("/interview_coach/interview_prep.md", "")
            )
            files["/interview_battlecard/battlecard.md"] = new_battlecard
            msg = f"⚡ **[Supervisor `career_agent`]:** Re-compiled `/interview_battlecard/battlecard.md`."
            return "career-agent", msg, files

        # Conversational reply citing current artifacts
        context = f"Resume:\n{resume_text[:1500]}\n\nJD:\n{jd_text[:1500]}\n\nResearch:\n{files.get('/research/recon_report.md', '')[:1500]}"
        prompt = f"""Candidate Question/Comment: "{user_message}"\n\nContext:\n{context}\n\nProvide an insightful, direct, supportive response:"""
        answer = generate_llm(prompt, system_instruction="You are the lead Career Agent supervisor.")
        return "career-agent", answer, files
