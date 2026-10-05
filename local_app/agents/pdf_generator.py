"""ATS Resume PDF Generator using ReportLab.
Renders clean, single-page ATS-compliant resumes matching Abinesh's layout template.
"""

import io
import os
import re
import json
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors

from local_app.agents.common import generate_llm


DEFAULT_ABINESH_DATA = {
    "name": "ABINESH J S",
    "contact": {
        "linkedin": "JSabinesh",
        "github": "JSabinesh",
        "email": "jsabinesh74@gmail.com",
        "phone": "+91 9789273654"
    },
    "profile": (
        "Motivated and detail-oriented student specializing in Artificial Intelligence and Machine Learning. "
        "Proficient in front-end technologies including HTML, CSS, and React, with a solid foundation in programming "
        "languages such as Python, Java, and C. Demonstrates strong analytical thinking with a growing interest in "
        "machine learning and data-driven solutions. Passionate about building real-world applications and continuously "
        "improving technical skills. Eager to contribute to innovative projects and collaborate within dynamic development teams."
    ),
    "education": [
        {
            "institution": "AMALA MATRIC HIGHER SECONDARY SCHOOL",
            "location": "KanyaKumari, India",
            "degree": "Senior High School 10th and 12th    12th Percentage - 86.33(StateBoard)",
            "period": "2020 - 2023"
        },
        {
            "institution": "RAJALAKSHMI ENGINEERING COLLEGE",
            "location": "Chennai, India",
            "degree": "B.Tech in ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING    CGPA - 8.08",
            "period": "2023 - 2027"
        }
    ],
    "skills_summary": {
        "Languages": "Python, C, Java, HTML, CSS, React.js, SQL",
        "Frameworks": "NumPy, Pandas, Flask, GIT, Streamlit, Scikit-learn",
        "Tools": "Jupyter Notebook, Visual Studio Code",
        "Soft Skills": "Problem Solving, Time Management, Team Collaboration",
        "Databases": "MongoDB, SupaBase, PostgreSQL"
    },
    "projects": [
        {
            "title": "House Price Prediction Model",
            "stack": "Python, Flask, Pandas, Scikit-learn, HTML/CSS, Jinja2, Joblib",
            "bullets": [
                "Built and optimized a machine learning model using Scikit-learn to predict house prices based on area, BHK, location, and property status, incorporating data cleaning, feature encoding, and model tuning.",
                "Deployed the trained model in a Flask web application featuring a clean, responsive UI, enabling users to generate real-time predictions through an intuitive, user-friendly interface."
            ]
        },
        {
            "title": "CityMitra",
            "stack": "React Native (Expo), TypeScript, Supabase, PostgreSQL, Maps, Camera, GPS",
            "bullets": [
                "Developed a cross-platform civic issue reporting system using React Native (Expo) and Supabase, enabling citizens to submit issues with photos, GPS location, and real-time status updates, supported by secure role-based authentication.",
                "Implemented contractor assignment via a round-robin algorithm, interactive map views, and complete issue lifecycle management, creating an efficient, scalable solution for streamlined municipal problem resolution."
            ]
        }
    ],
    "additional_information": {
        "Languages": "Tamil (Native), English (Fluent), Hindi (Conversational)",
        "Personal Traits": "Fast Learner, Self-motivated, Highly Adaptable",
        "Hackathons / Events": "Smart India Internal Hackathon Winner"
    }
}


def build_ats_resume_pdf(data: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """Renders data into a single-page ATS-formatted PDF matching the user's template."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=24,
        bottomMargin=24
    )

    # Styles
    title_style = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=18, leading=20, alignment=TA_CENTER)
    contact_style = ParagraphStyle('C', fontName='Helvetica', fontSize=8.5, leading=11, alignment=TA_CENTER)
    sec_head_style = ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=9.5, leading=11.5, alignment=TA_CENTER)
    body_style = ParagraphStyle('B', fontName='Helvetica', fontSize=8.2, leading=10.5, alignment=TA_JUSTIFY)
    left_bold = ParagraphStyle('LB', fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, alignment=TA_LEFT)
    left_reg = ParagraphStyle('LR', fontName='Helvetica', fontSize=8.2, leading=10.5, alignment=TA_LEFT)
    right_bold = ParagraphStyle('RB', fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, alignment=TA_RIGHT)
    right_reg = ParagraphStyle('RR', fontName='Helvetica', fontSize=8.2, leading=10.5, alignment=TA_RIGHT)
    bullet_style = ParagraphStyle('BL', fontName='Helvetica', fontSize=8.2, leading=10.5, leftIndent=8)

    def hr():
        return HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#222222'), spaceBefore=2.5, spaceAfter=3.5)

    story = []

    # 1. Header
    name = data.get("name", "ABINESH J S")
    story.append(Paragraph(name, title_style))
    story.append(Spacer(1, 2))

    contact = data.get("contact", {})
    linkedin = contact.get("linkedin", "JSabinesh")
    github = contact.get("github", "JSabinesh")
    email = contact.get("email", "jsabinesh74@gmail.com")
    phone = contact.get("phone", "+91 9789273654")
    contact_line = f"<b>LinkedIn:</b> {linkedin} &nbsp;&nbsp;|&nbsp;&nbsp; <b>GitHub:</b> {github} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Email:</b> {email} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Phone:</b> {phone}"
    story.append(Paragraph(contact_line, contact_style))

    # 2. PROFILE
    story.append(hr())
    story.append(Paragraph("PROFILE", sec_head_style))
    story.append(Spacer(1, 1.5))
    profile_text = data.get("profile", DEFAULT_ABINESH_DATA["profile"])
    story.append(Paragraph(profile_text, body_style))

    # 3. EDUCATION
    story.append(hr())
    story.append(Paragraph("EDUCATION", sec_head_style))
    story.append(Spacer(1, 1.5))
    edu_list = data.get("education", DEFAULT_ABINESH_DATA["education"])
    edu_data = []
    for item in edu_list:
        inst = item.get("institution", "")
        loc = item.get("location", "")
        deg = item.get("degree", "")
        period = item.get("period", "")
        edu_data.append([Paragraph(inst, left_bold), Paragraph(loc, right_bold)])
        edu_data.append([Paragraph(deg, left_reg), Paragraph(period, right_reg)])

    if edu_data:
        t_edu = Table(edu_data, colWidths=[395, 145])
        t_edu.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 0.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0.5)
        ]))
        story.append(t_edu)

    # 4. SKILLS SUMMARY
    story.append(hr())
    story.append(Paragraph("SKILLS SUMMARY", sec_head_style))
    story.append(Spacer(1, 1.5))
    skills_map = data.get("skills_summary", DEFAULT_ABINESH_DATA["skills_summary"])
    for cat, val in skills_map.items():
        val_str = ", ".join(val) if isinstance(val, list) else str(val)
        story.append(Paragraph(f"&bull; <b>{cat}:</b> {val_str}", bullet_style))

    # 5. PROJECTS
    story.append(hr())
    story.append(Paragraph("PROJECTS", sec_head_style))
    story.append(Spacer(1, 1.5))
    projects = data.get("projects", DEFAULT_ABINESH_DATA["projects"])
    for i, proj in enumerate(projects):
        title = proj.get("title", "")
        stack = proj.get("stack", "")
        header_line = f"<b>{title} | {stack}</b>" if stack else f"<b>{title}</b>"
        story.append(Paragraph(header_line, left_reg))
        for b in proj.get("bullets", []):
            clean_b = re.sub(r"^[•\-\*]\s*", "", b)
            story.append(Paragraph(f"&bull; {clean_b}", bullet_style))
        if i < len(projects) - 1:
            story.append(Spacer(1, 2))

    # 6. ADDITIONAL INFORMATION
    story.append(hr())
    story.append(Paragraph("ADDITIONAL INFORMATION", sec_head_style))
    story.append(Spacer(1, 1.5))
    add_info = data.get("additional_information", DEFAULT_ABINESH_DATA["additional_information"])
    for k, v in add_info.items():
        v_str = ", ".join(v) if isinstance(v, list) else str(v)
        story.append(Paragraph(f"<b>{k}:</b> {v_str}", left_reg))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes


def tailor_resume_data(
    job_role: str,
    company: str,
    job_description: str,
    job_skills: list,
    candidate_profile_override: Optional[str] = None
) -> Dict[str, Any]:
    """Tailors Abinesh's resume profile, skills ordering, and project highlights for the target role."""
    base_data = json.loads(json.dumps(DEFAULT_ABINESH_DATA))

    skills_joined = ", ".join(job_skills) if job_skills else "General software development"
    prompt = (
        "You are an expert ATS Resume Tailor. Tailor the candidate's resume specifically for this job opening.\n\n"
        f"TARGET JOB ROLE: {job_role}\n"
        f"COMPANY: {company}\n"
        f"JOB DESCRIPTION:\n{job_description[:1500]}\n"
        f"KEY REQUIRED SKILLS: {skills_joined}\n\n"
        "CANDIDATE BASE EVIDENCE:\n"
        f"Profile: {base_data['profile']}\n"
        f"Skills: {json.dumps(base_data['skills_summary'])}\n"
        f"Projects: {json.dumps(base_data['projects'])}\n\n"
        "INSTRUCTIONS:\n"
        "1. Write a tailored 'profile' (3-4 sentences, max 85 words) emphasizing relevant strengths for this role and company without fabricating background.\n"
        "2. Re-prioritize 'skills_summary' so the skills most relevant to this JD appear first in each category.\n"
        "3. For the 2 projects, adjust the 2 bullet points each to highlight techniques, keywords, and metrics that align with this JD, keeping verified facts.\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "profile": "...",\n'
        '  "skills_summary": {\n'
        '    "Languages": "...",\n'
        '    "Frameworks": "...",\n'
        '    "Tools": "...",\n'
        '    "Soft Skills": "...",\n'
        '    "Databases": "..."\n'
        '  },\n'
        '  "projects": [\n'
        '    {\n'
        '      "title": "House Price Prediction Model",\n'
        '      "stack": "Python, Flask, Pandas, Scikit-learn, HTML/CSS, Jinja2, Joblib",\n'
        '      "bullets": ["...", "..."]\n'
        '    },\n'
        '    {\n'
        '      "title": "CityMitra",\n'
        '      "stack": "React Native (Expo), TypeScript, Supabase, PostgreSQL, Maps, Camera, GPS",\n'
        '      "bullets": ["...", "..."]\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    try:
        raw = generate_llm(prompt, system_instruction="ATS Resume Tailor. Return valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        parsed = json.loads(raw.strip())
        if "profile" in parsed:
            base_data["profile"] = parsed["profile"]
        if "skills_summary" in parsed and isinstance(parsed["skills_summary"], dict):
            base_data["skills_summary"].update(parsed["skills_summary"])
        if "projects" in parsed and isinstance(parsed["projects"], list) and len(parsed["projects"]) >= 2:
            base_data["projects"] = parsed["projects"][:2]
    except Exception as e:
        print(f"[Warning] LLM tailoring failed, using base template: {e}")

    return base_data
