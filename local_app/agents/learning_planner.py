"""learning-planner agent: structures resources into comprehensive 7/14/30-day roadmaps connected to verifiable evidence projects and interview battlecards."""

import re
import json
from typing import Dict, Any, List
from local_app.agents.common import generate_llm


def run_learning_planner(gaps: List[Dict[str, Any]], resources: Dict[str, List]) -> Dict[str, Any]:
    """Builds comprehensive 7-day, 14-day, and 30-day roadmaps with explicit evidence demonstration goals and interview prep."""
    if not gaps:
        return {"plans": {}}

    gap_list = json.dumps(gaps[:4], indent=2)
    res_list = json.dumps(resources, indent=2)[:3000]

    prompt = (
        f"You are `learning-planner`. Generate an elite, actionable engineering mastery roadmap for each of these skills:\n"
        f"{gap_list}\n\n"
        f"Curated Resources:\n{res_list}\n\n"
        "For each topic, produce an actionable roadmap with:\n"
        "1. evidence_goal: Concrete production project the candidate will build and put on their resume/GitHub.\n"
        "2. phase_7_day: Foundation & Core Mechanics (4 milestone blocks: Day 1-2, Day 3-4, Day 5-6, Day 7 with focus, tasks, deliverable).\n"
        "3. phase_14_day: Applied Frameworks & Real-world Stack (4 milestone blocks: Day 8-9, Day 10-11, Day 12-13, Day 14 with focus, tasks, deliverable).\n"
        "4. phase_30_day: Production Mastery, Scale & Architecture (4 milestone blocks: Day 15-18, Day 19-22, Day 23-26, Day 27-30 with focus, tasks, deliverable).\n"
        "5. interview_battlecard: 4 critical technical questions interviewers ask with key answers/insights.\n\n"
        "Return valid JSON only in this exact format:\n"
        '{\n'
        '  "plans": {\n'
        '    "<topic name>": {\n'
        '      "evidence_goal": "<project description>",\n'
        '      "phase_7_day": {\n'
        '        "title": "7-Day Foundation & Core Mechanics",\n'
        '        "description": "<summary of phase>",\n'
        '        "milestones": [\n'
        '          {"day": "Day 1-2", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 3-4", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 5-6", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 7", "focus": "...", "tasks": "...", "deliverable": "..."}\n'
        '        ]\n'
        '      },\n'
        '      "phase_14_day": {\n'
        '        "title": "14-Day Applied Frameworks & Real-World Stack",\n'
        '        "description": "<summary of phase>",\n'
        '        "milestones": [\n'
        '          {"day": "Day 8-9", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 10-11", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 12-13", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 14", "focus": "...", "tasks": "...", "deliverable": "..."}\n'
        '        ]\n'
        '      },\n'
        '      "phase_30_day": {\n'
        '        "title": "30-Day Production Scale & Architecture Mastery",\n'
        '        "description": "<summary of phase>",\n'
        '        "milestones": [\n'
        '          {"day": "Day 15-18", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 19-22", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 23-26", "focus": "...", "tasks": "...", "deliverable": "..."},\n'
        '          {"day": "Day 27-30", "focus": "...", "tasks": "...", "deliverable": "..."}\n'
        '        ]\n'
        '      },\n'
        '      "interview_battlecard": [\n'
        '        {"question": "...", "key_points": "..."}\n'
        '      ]\n'
        '    }\n'
        '  }\n'
        '}'
    )
    try:
        raw = generate_llm(prompt, system_instruction="Staff Engineer and Learning Planner. Output valid JSON only.")
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        parsed = json.loads(raw.strip())
        if isinstance(parsed, dict) and "plans" in parsed and parsed["plans"]:
            return parsed
    except Exception as e:
        print(f"[Warning] learning-planner error: {e}")

    # Robust high quality fallback generator
    plans = {}
    for g in gaps:
        topic = g["name"]
        is_java = "java" in topic.lower() or "spring" in topic.lower()

        if is_java:
            plans[topic] = {
                "evidence_goal": "Build and deploy a Production Multi-Tenant REST API using Java 21, Spring Boot 3, PostgreSQL, Redis caching, and JUnit 5 test suite.",
                "phase_7_day": {
                    "title": "7-Day Foundation & Core Mechanics",
                    "description": "Master core syntax, JVM execution lifecycle, OOP principles, Collections, and Stream API.",
                    "milestones": [
                        {"day": "Day 1-2", "focus": "Modern Java Syntax & JVM Mechanics", "tasks": "Java 21 setup, Records, Pattern Matching, Stack vs Heap memory model", "deliverable": "CLI data parser utility"},
                        {"day": "Day 3-4", "focus": "OOP Design & Collections Framework", "tasks": "Generics, HashMap collision resolution, ArrayList vs LinkedList, SOLID principles", "deliverable": "In-memory caching collection"},
                        {"day": "Day 5-6", "focus": "Functional Java, Stream API & Concurrency", "tasks": "Lambdas, Stream pipelines, CompletableFuture, Virtual Threads (Project Loom)", "deliverable": "Parallel web scraping engine"},
                        {"day": "Day 7", "focus": "Testing & Build Tools", "tasks": "JUnit 5, AssertJ, Maven/Gradle build lifecycle", "deliverable": "Fully tested core Java project with 90%+ code coverage"}
                    ]
                },
                "phase_14_day": {
                    "title": "14-Day Applied Frameworks & Enterprise Stack",
                    "description": "Build production-ready services with Spring Boot, Spring Data JPA, and REST security.",
                    "milestones": [
                        {"day": "Day 8-9", "focus": "Spring Boot 3 Core & IoC Container", "tasks": "Dependency Injection, Component Scanning, Application Properties & Profiles", "deliverable": "Spring Boot microservice scaffold"},
                        {"day": "Day 10-11", "focus": "Data Persistence with JPA & Hibernate", "tasks": "Entity mappings, Spring Data Repositories, handling N+1 queries, @Transactional", "deliverable": "PostgreSQL-backed CRUD engine"},
                        {"day": "Day 12-13", "focus": "REST API Architecture & Spring Security", "tasks": "DTO mappings, global exception handling, JWT authentication & RBAC", "deliverable": "Secure authenticated API endpoints"},
                        {"day": "Day 14", "focus": "Integration Testing & Docker Containerization", "tasks": "Testcontainers, MockMvc, Dockerfile multi-stage builds", "deliverable": "Containerized service running in Docker"}
                    ]
                },
                "phase_30_day": {
                    "title": "30-Day Production Mastery & System Scale",
                    "description": "Architect distributed microservices, event streaming with Kafka, and JVM performance tuning.",
                    "milestones": [
                        {"day": "Day 15-18", "focus": "Event-Driven Architecture & Messaging", "tasks": "Apache Kafka producer/consumer integration, idempotency, dead-letter queues", "deliverable": "Asynchronous order processing pipeline"},
                        {"day": "Day 19-22", "focus": "Distributed Caching & Resiliency", "tasks": "Redis caching strategies (Cache-Aside, Write-Through), Resilience4j circuit breakers", "deliverable": "High-throughput cached API with fault tolerance"},
                        {"day": "Day 23-26", "focus": "JVM Internals & Performance Tuning", "tasks": "Garbage Collection algorithms (G1, ZGC), heap dump analysis, JProfiler/VisualVM", "deliverable": "Benchmark report under simulated load"},
                        {"day": "Day 27-30", "focus": "Portfolio Evidence Deployment & Interview Drills", "tasks": "Deploy to AWS/Render with CI/CD, README documentation, System design mocks", "deliverable": "Live production project link & interview battlecard ready"}
                    ]
                },
                "interview_battlecard": [
                    {"question": "How does HashMap work internally in Java 8+?", "key_points": "Bucket array + linked list transitioning to Red-Black tree when bucket size exceeds 8 (TREEIFY_THRESHOLD). Uses hashCode() and equals()."},
                    {"question": "What is the difference between Virtual Threads and Platform Threads?", "key_points": "Platform threads map 1:1 to OS kernel threads (~1MB stack). Virtual threads (Loom) are lightweight (~few KB), managed by JVM, multiplexed on carrier threads."},
                    {"question": "How do you resolve the N+1 select problem in Hibernate?", "key_points": "Use JOIN FETCH in JPQL/Criteria, @EntityGraph, or BatchSize. Avoid lazy loading inside loops."},
                    {"question": "Explain the Java Memory Model (JMM) and the 'volatile' keyword.", "key_points": "Volatile guarantees memory visibility (flushes CPU cache) and prevents instruction reordering (happens-before), but does not ensure atomicity."}
                ]
            }
        else:
            plans[topic] = {
                "evidence_goal": f"Build and publish a production-grade demonstration project showcasing mastery of {topic}.",
                "phase_7_day": {
                    "title": "7-Day Foundation & Core Mechanics",
                    "description": f"Master the fundamental abstractions, runtime mechanics, and idioms of {topic}.",
                    "milestones": [
                        {"day": "Day 1-2", "focus": "Core Architecture & Mental Models", "tasks": f"Setup environment and study core primitives of {topic}", "deliverable": "Basic prototype script"},
                        {"day": "Day 3-5", "focus": "Intermediate API & Data Flows", "tasks": f"Implement business logic, error handling, and state management in {topic}", "deliverable": "Modular feature service"},
                        {"day": "Day 6-7", "focus": "Automated Testing & Linting", "tasks": "Unit testing and code quality checks", "deliverable": "Verified test suite"}
                    ]
                },
                "phase_14_day": {
                    "title": "14-Day Applied Real-World Engineering",
                    "description": f"Integrate {topic} into real-world production stacks and persistence engines.",
                    "milestones": [
                        {"day": "Day 8-10", "focus": "Enterprise Integration & Frameworks", "tasks": f"Connect {topic} with databases, caching, and background workers", "deliverable": "Full-stack integration branch"},
                        {"day": "Day 11-14", "focus": "Security, Monitoring & Docker", "tasks": "Authentication, logging, health probes, Docker packaging", "deliverable": "Deployable container image"}
                    ]
                },
                "phase_30_day": {
                    "title": "30-Day Production Mastery & Scale",
                    "description": f"Solve advanced distributed edge cases, scaling bottlenecks, and interview scenarios in {topic}.",
                    "milestones": [
                        {"day": "Day 15-22", "focus": "Performance Profiling & Bottlenecks", "tasks": "Load testing, latency reduction, caching optimizations", "deliverable": "Performance benchmark dossier"},
                        {"day": "Day 23-30", "focus": "Production Deployment & Interview Drills", "tasks": "CI/CD automation, open-source portfolio artifact, mock interview questions", "deliverable": "Production GitHub showcase"}
                    ]
                },
                "interview_battlecard": [
                    {"question": f"What are the top architectural trade-offs when implementing {topic}?", "key_points": f"Balancing complexity vs performance, operational maintenance, and scalability bottlenecks in {topic}."},
                    {"question": f"How do you troubleshoot high latency or memory leaks in {topic}?", "key_points": "Use profiling tools, inspect thread/heap dumps, trace network hops, and check slow queries."}
                ]
            }

    return {"plans": plans}
