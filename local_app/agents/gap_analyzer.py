"""gap-analyzer agent: unifies evidence gaps, JD requirements, and mock interview weaknesses into prioritized learning goals."""

import re
import json
from typing import Dict, Any, List, Optional
from local_app.agents.common import get_evidence_store, generate_llm


def run_gap_analyzer(session: Dict[str, Any], target_topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Identifies learning priorities across target topic, Job Match gaps, JD requirements, and Interview Simulator weaknesses."""
    # 1. Direct Target Topic Request (e.g., "Java", "Kubernetes", "System Design")
    if target_topic and target_topic.strip() and target_topic.strip().lower() != "run":
        cleaned_topic = target_topic.strip()
        prompt = (
            f"You are `gap-analyzer`. A software engineer wants to master: '{cleaned_topic}'.\n"
            f"Break this skill down into 3-4 structured, prioritized sub-competency learning gaps necessary for senior/staff level industry mastery.\n"
            f"Return valid JSON array only:\n"
            f'[\n'
            f'  {{"name": "<Sub-skill name, e.g. Core Java 21 & JVM Internals>", "desc": "<Specific technical areas to master>", "sev": "high"}},\n'
            f'  {{"name": "<Sub-skill name, e.g. Spring Boot 3 & Enterprise Microservices>", "desc": "<Frameworks and production patterns>", "sev": "high"}},\n'
            f'  {{"name": "<Sub-skill name, e.g. Concurrency, Virtual Threads & JMM>", "desc": "<Advanced asynchronous and memory models>", "sev": "medium"}}\n'
            f']'
        )
        try:
            raw = generate_llm(prompt, system_instruction="Technical skill gap analyzer. Return valid JSON only.")
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            parsed = json.loads(raw.strip())
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed[:5]
        except Exception as e:
            print(f"[Warning] gap-analyzer direct topic LLM error: {e}")
            return [
                {"name": f"{cleaned_topic} - Core Language & Runtime Architecture", "desc": f"Master core syntax, internals, memory management, and idiomatic idioms in {cleaned_topic}.", "sev": "high"},
                {"name": f"{cleaned_topic} - Ecosystem, Frameworks & API Engineering", "desc": f"Enterprise patterns, RESTful services, database persistence, and testing in {cleaned_topic}.", "sev": "high"},
                {"name": f"{cleaned_topic} - High Throughput, Concurrency & Production Scale", "desc": f"Performance profiling, multi-threading, asynchronous processing, and cloud deployment.", "sev": "medium"}
            ]

    # 2. Extract from Career Evidence Store / Job Match
    store       = get_evidence_store(session)
    match_gaps  = store.get("gaps", [])
    sim_history = store.get("sim_history", [])

    sim_weaknesses = []
    for turn in sim_history:
        ev = turn.get("evaluation") or {}
        scores = ev.get("scores", {})
        for dim, score in scores.items():
            if isinstance(score, (int, float)) and score < 65:
                sim_weaknesses.append(dim)

    combined_gaps = list(match_gaps[:5]) if match_gaps else []
    for w in set(sim_weaknesses):
        combined_gaps.append({
            "name": w.replace("_", " ").title(),
            "desc": "Weakness identified during interview simulation",
            "sev": "medium"
        })

    # 3. If no gaps yet, check JD vs Resume in session files
    if not combined_gaps:
        files = session.get("files", {})
        jd_text = files.get("/processed/jd.md", "")
        resume_text = files.get("/processed/resume.md", "")

        if jd_text:
            prompt = (
                f"You are `gap-analyzer`. Analyze this Job Description and candidate Resume (if available) to identify top 3-4 key technical competencies and skills the candidate must strengthen to ace this role.\n\n"
                f"Job Description (first 2500 chars):\n{jd_text[:2500]}\n\n"
                f"Candidate Resume (first 2500 chars):\n{resume_text[:2500] if resume_text else 'None uploaded'}\n\n"
                f"Return valid JSON array only:\n"
                f'[\n'
                f'  {{"name": "<Skill Name, e.g. Java & Spring Framework>", "desc": "<Why it matters for this job and what to master>", "sev": "high"}}\n'
                f']'
            )
            try:
                raw = generate_llm(prompt, system_instruction="Technical skill gap extractor. Return valid JSON only.")
                raw = re.sub(r"```json\s*", "", raw)
                raw = re.sub(r"```\s*", "", raw)
                parsed = json.loads(raw.strip())
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed[:5]
            except Exception as e:
                print(f"[Warning] gap-analyzer JD extractor error: {e}")

    # 4. Default fallback competencies if nothing uploaded yet
    if not combined_gaps:
        return [
            {"name": "Java & Enterprise Backend Architecture", "desc": "Modern Java 21, Spring Boot, microservices architecture, and clean OOP design.", "sev": "high"},
            {"name": "System Design & Distributed Scalability", "desc": "High availability, distributed caching, database sharding, and message queues (Kafka).", "sev": "high"},
            {"name": "Cloud Native & Container Orchestration", "desc": "Docker, Kubernetes, CI/CD automation, and production observability.", "sev": "medium"}
        ]

    return combined_gaps[:8]
