"""Career Switch Advisor Agent — Comparative Trajectory, Pros/Cons, Salary Range & Better Path Suggester."""

import json
import re
from typing import Dict, Any, List, Optional
from local_app.agents.common import generate_llm


def _get_benchmark_fallback(
    current_role: str,
    target_role: str,
    experience_level: str,
    currency: str
) -> Dict[str, Any]:
    """Provides high-fidelity deterministic benchmarks when LLM is unavailable or offline."""
    is_inr = currency.upper() == "INR"
    curr_sym = "₹" if is_inr else "$"
    unit = "LPA" if is_inr else "k/yr"

    # Heuristic detection for common role archetypes
    c_lower = current_role.lower()
    t_lower = target_role.lower()

    if "test" in t_lower or "qa" in t_lower:
        suggested_role = "SDET (Software Development Engineer in Test)"
        suggested_tagline = "Keeps full software engineering comp and code equity while mastering automated test architecture."
        why_better = [
            "Retains full Tier-1 software engineering salary parity rather than taking a manual testing discount.",
            "High organizational leverage: building scalable automation frameworks and CI/CD pipelines instead of repetitive manual execution.",
            "Capitalizes directly on existing developer coding skills instead of letting them atrophy.",
            "High insulation from GenAI obsolescence through infrastructure and performance test engineering."
        ]
        bridging_skills = ["Playwright / Cypress", "PyTest / TestNG Framework Architecture", "Dockerized CI/CD E2E Pipelines", "Performance & Load Testing (k6 / Locust)"]
    elif "product" in t_lower or "pm" in t_lower:
        suggested_role = "Technical Product Manager (TPM)"
        suggested_tagline = "Bridges engineering depth with product strategy, unlocking executive track mobility."
        why_better = [
            "Engineers with technical depth make exceptional TPMs that engineering teams deeply respect.",
            "Higher long-term executive ceiling (VP Product, CPO) compared to individual contributor limits.",
            "Maintains top-tier tech compensation without day-to-day bug fixes or on-call pages."
        ]
        bridging_skills = ["Product Analytics & SQL", "PRD Specification & Roadmapping", "User Interview & Customer Discovery", "Agile Product Operations"]
    elif "devops" in t_lower or "cloud" in t_lower or "sre" in t_lower:
        suggested_role = "Platform / DevSecOps Engineer"
        suggested_tagline = "Massive industry demand with premium compensation across hybrid cloud ecosystems."
        why_better = [
            "Developers transitioning to DevOps bring vital software patterns (Infrastructure as Code) that pure sysadmins lack.",
            "15-25% salary premium over traditional software engineering due to specialized infrastructure skills.",
            "Mission-critical role at every scaling tech company."
        ]
        bridging_skills = ["Kubernetes & Helm", "Terraform / OpenTofu (IaC)", "CI/CD GitOps (GitHub Actions / ArgoCD)", "Observability (Prometheus, Grafana, OpenTelemetry)"]
    elif "ai" in t_lower or "ml" in t_lower:
        suggested_role = "AI Systems / Agentic Systems Engineer"
        suggested_tagline = "Fastest growing compensation tier in modern software development."
        why_better = [
            "Combines production backend stability with bleeding-edge LLM orchestration.",
            "Command 20-40% compensation premiums across AI startups and enterprise innovators.",
            "Immense demand for engineers who can move AI beyond prototypes into scalable production."
        ]
        bridging_skills = ["LangChain / LangGraph Orchestration", "Vector Databases & Hybrid RAG", "Evaluation Frameworks (Ragas / TruLens)", "Streaming API Architecture"]
    else:
        suggested_role = f"Specialized Senior {current_role}"
        suggested_tagline = "Deep domain specialization in distributed systems, security, or architecture."
        why_better = [
            "Leverages existing seniority without resetting domain equity or credibility.",
            "Fastest route to Staff/Principal compensation band.",
            "Eliminates the friction and vulnerability of a lateral entry-level pivot."
        ]
        bridging_skills = ["Distributed Systems Design", "Cloud Native Cost Optimization", "Technical Leadership & RFC Writing"]

    # Trajectory series calculations
    # Stages: 0-2 Yrs, 3-5 Yrs, 6-8 Yrs, 9-12 Yrs, 12+ Yrs
    if is_inr:
        if "test" in t_lower or "qa" in t_lower:
            current_series = [5.5, 12.0, 22.0, 36.0, 52.0]
            target_series = [4.0, 8.5, 15.0, 24.0, 34.0]
            suggested_series = [6.0, 14.0, 25.0, 40.0, 58.0]
        elif "pm" in t_lower or "product" in t_lower:
            current_series = [5.5, 12.0, 22.0, 36.0, 52.0]
            target_series = [7.0, 15.0, 28.0, 45.0, 65.0]
            suggested_series = [8.0, 17.0, 32.0, 50.0, 75.0]
        else:
            current_series = [6.0, 13.0, 24.0, 38.0, 55.0]
            target_series = [5.0, 10.0, 18.0, 28.0, 42.0]
            suggested_series = [7.0, 16.0, 28.0, 45.0, 65.0]
    else:
        if "test" in t_lower or "qa" in t_lower:
            current_series = [78, 118, 155, 192, 235]
            target_series = [58, 85, 110, 135, 160]
            suggested_series = [82, 125, 162, 205, 248]
        elif "pm" in t_lower or "product" in t_lower:
            current_series = [78, 118, 155, 192, 235]
            target_series = [85, 128, 168, 210, 265]
            suggested_series = [92, 140, 185, 230, 290]
        else:
            current_series = [80, 120, 160, 200, 245]
            target_series = [65, 95, 125, 155, 185]
            suggested_series = [88, 132, 175, 218, 265]

    delta_pct = int(round(((target_series[2] - current_series[2]) / current_series[2]) * 100))

    return {
        "current_role": current_role,
        "target_role": target_role,
        "suggested_role": suggested_role,
        "experience_level": experience_level,
        "currency": currency.upper(),
        "currency_symbol": curr_sym,
        "currency_unit": unit,
        "salary_graph": {
            "stages": ["0-2 Yrs (Junior)", "3-5 Yrs (Mid)", "6-8 Yrs (Senior)", "9-12 Yrs (Staff/Lead)", "12+ Yrs (Principal/Head)"],
            "current_role_series": current_series,
            "target_role_series": target_series,
            "suggested_role_series": suggested_series,
            "delta_10yr_pct": delta_pct,
            "verdict_summary": f"Switching from {current_role} to {target_role} yields an estimated {delta_pct:+d}% salary variance at senior milestones, whereas {suggested_role} maximizes earnings and technical leverage."
        },
        "switch_pros": [
            {
                "title": "Lower Firefighting & On-Call Pressure",
                "detail": "Test and verification cycles have more predictable deployment checkpoints compared to late-night emergency production code deployments.",
                "tag": "Work-Life Balance"
            },
            {
                "title": "Holistic Quality & System Domain Scope",
                "detail": f"Transitioning gives end-to-end visibility across whole user flows and business edge cases rather than single microservice silos.",
                "tag": "Architecture"
            },
            {
                "title": "High Technical Advantage over Pure Testers",
                "detail": f"Coming from a {current_role} background, your ability to read source code, debug stack traces, and understand database schemas puts you in the top 10% of testing teams.",
                "tag": "Competitive Edge"
            }
        ],
        "switch_cons": [
            {
                "title": "Lower Long-Term Earning Ceiling",
                "detail": f"Core engineering pathways generally maintain a 20% to 35% compensation premium over pure QA/Testing roles across global markets.",
                "severity": "high"
            },
            {
                "title": "Risk of Being Confined to Manual Execution",
                "detail": "Without strict boundaries, testing roles frequently devolve into repetitive manual checklist verifications rather than technical automation.",
                "severity": "high"
            },
            {
                "title": "High Vulnerability to Generative AI Automation",
                "detail": "Basic test case authoring, synthetic data generation, and regression scripts are being automated rapidly by AI coding agents.",
                "severity": "medium"
            },
            {
                "title": "Challenging Reverse Transition Back to Dev",
                "detail": "Recruiters and hiring managers may perceive prolonged time in QA as a decline in software implementation fluency.",
                "severity": "medium"
            }
        ],
        "friction_analysis": {
            "technical_friction": "Low (Your software lifecycle and coding background easily transfer to quality frameworks).",
            "market_value_friction": "High (Switching to traditional QA discounts your engineering equity).",
            "difficulty_score": 38
        },
        "transferable_skills": [
            "Source Code Comprehension & Profiling",
            "Git & Version Control Workflows",
            "API Protocol Fundamentals (REST, HTTP status codes, payloads)",
            "System Architecture & Data Modeling Knowledge"
        ],
        "skill_gaps": [
            "Comprehensive Test Plan & Matrix Authoring",
            "Automated E2E Testing Frameworks (Playwright, Cypress, Selenium)",
            "Load & Stress Performance Profiling (k6, Locust)",
            "Root Cause Analysis & Incident Triaging Protocols"
        ],
        "better_solution": {
            "verdict": "SUBOPTIMAL_PIVOT_EXISTS_BETTER",
            "verdict_badge": "Suboptimal Pivot — Higher-Yield Alternative Recommended",
            "summary": f"Switching directly from {current_role} to {target_role} sacrifices 20-30% of your career compensation ceiling and risks pigeonholing you into lower-leverage tasks. The superior move is to pivot to {suggested_role}.",
            "comparison": [
                {
                    "option": f"Option A: Stay in {current_role}",
                    "trajectory": "Maintains top compensation band, but doesn't resolve quality/testing interests.",
                    "status": "Viable Baseline"
                },
                {
                    "option": f"Option B: Defined Switch to {target_role}",
                    "trajectory": "Reduced pressure initially, but creates an uphill compensation battle and lower ceiling.",
                    "status": "Not Recommended"
                },
                {
                    "option": f"Option C: Recommended Pivot to {suggested_role}",
                    "trajectory": "Combines testing/quality focus with developer compensation tier and automation leverage.",
                    "status": "Optimal Strategy"
                }
            ]
        },
        "suggested_better_role": {
            "title": suggested_role,
            "tagline": suggested_tagline,
            "why_superior": why_better,
            "bridging_skills": bridging_skills
        },
        "general_switching_pros_and_cons": {
            "pros": [
                {
                    "title": "Escape Stagnation & Burnout",
                    "detail": "A deliberate career shift provides fresh cognitive challenges and breaks repetitive delivery burnout."
                },
                {
                    "title": "Multidisciplinary T-Shaped Value",
                    "detail": "Professionals who bridge two disciplines (e.g., Development + QA, or Development + Product) are uniquely influential and hard to replace."
                },
                {
                    "title": "Higher Career Resilience",
                    "detail": "Having competence across multiple functional areas insulates you during economic sector downturns."
                }
            ],
            "cons": [
                {
                    "title": "Loss of Accumulated Social Capital",
                    "detail": "Years of built trust, domain reputation, and speed within your original role do not automatically transfer to the new title."
                },
                {
                    "title": "Probationary & Market Vulnerability",
                    "detail": "New switchers in unfamiliar roles are often most vulnerable during corporate restructuring or team downsizings."
                },
                {
                    "title": "Resume Coherence Risk",
                    "detail": "Erratic or frequent role switching without a coherent narrative can signal lack of commitment or focus to hiring executives."
                }
            ],
            "strategic_checklist": [
                "1. Build proof-of-work projects in the target discipline BEFORE resigning or switching titles.",
                "2. Benchmark compensation ceilings across senior tiers in your geography to prevent blind discounts.",
                "3. Ensure the pivot moves towards high leverage and technological scarcity, rather than fleeing temporary frustration."
            ]
        }
    }


def analyze_career_switch(
    current_role: str,
    target_role: str,
    experience_level: str = "Mid-Level (3-5 yrs)",
    currency: str = "USD",
    candidate_resume: str = ""
) -> Dict[str, Any]:
    """Runs the Career Switch Advisor pipeline using Gemini with deterministic fallback."""
    current_role = current_role.strip() or "Software Developer"
    target_role = target_role.strip() or "QA Tester"
    currency = currency.strip().upper() if currency else "USD"

    prompt = f"""You are the NextRole Career Switch Advisor Agent — an elite strategic career architect, compensation analyst, and tech career strategist.

Analyze the career pivot from Current Role: "{current_role}" to Target Role: "{target_role}".
Candidate Experience Level: "{experience_level}".
Target Currency: "{currency}" (use USD thousands 'k/yr' or INR lakhs 'LPA' appropriately).
Candidate Resume Context (if any):
\"\"\"{candidate_resume[:1500]}\"\"\"

Provide an in-depth, rigorous, reality-grounded strategic analysis answering:
1. Salary progression trajectory graph data across 5 milestone stages:
   ["0-2 Yrs (Junior)", "3-5 Yrs (Mid)", "6-8 Yrs (Senior)", "9-12 Yrs (Staff/Lead)", "12+ Yrs (Principal/Head)"]
   For:
   - current_role_series (numeric values in {currency})
   - target_role_series (numeric values in {currency})
   - suggested_role_series (a superior alternative role, numeric values in {currency})
2. Specific Pros & Cons of switching from "{current_role}" to "{target_role}".
3. Better Solution analysis (what is the objectively superior career option?).
4. Suggest a BETTER job change than the user-defined switch (e.g., if Developer -> Tester, suggest SDET, DevOps/Platform Eng, or AI Quality Eng) and explain why it is vastly superior in comp, growth, and leverage.
5. General Pros & Cons of job/career switching in the modern tech market.

Respond with ONLY valid JSON strictly following this schema:
{{
  "current_role": "{current_role}",
  "target_role": "{target_role}",
  "suggested_role": "<Better Alternative Role Title>",
  "experience_level": "{experience_level}",
  "currency": "{currency}",
  "currency_symbol": "<$ or ₹>",
  "currency_unit": "<k/yr or LPA>",
  "salary_graph": {{
    "stages": ["0-2 Yrs (Junior)", "3-5 Yrs (Mid)", "6-8 Yrs (Senior)", "9-12 Yrs (Staff/Lead)", "12+ Yrs (Principal/Head)"],
    "current_role_series": [<5 numbers>],
    "target_role_series": [<5 numbers>],
    "suggested_role_series": [<5 numbers>],
    "delta_10yr_pct": <number, e.g. -28 or +15>,
    "verdict_summary": "<1-2 sentence executive summary of salary trajectory comparison>"
  }},
  "switch_pros": [
    {{"title": "...", "detail": "...", "tag": "..."}}
  ],
  "switch_cons": [
    {{"title": "...", "detail": "...", "severity": "high|medium|low"}}
  ],
  "friction_analysis": {{
    "technical_friction": "<brief assessment>",
    "market_value_friction": "<brief assessment>",
    "difficulty_score": <number 0-100>
  }},
  "transferable_skills": ["<skill1>", "<skill2>", "<skill3>", "<skill4>"],
  "skill_gaps": ["<gap1>", "<gap2>", "<gap3>", "<gap4>"],
  "better_solution": {{
    "verdict": "<SUBOPTIMAL_PIVOT_EXISTS_BETTER | HIGH_VALUE_PIVOT | LATERAL_TRADE_OFF>",
    "verdict_badge": "<Short visual badge text>",
    "summary": "<Objective evaluation comparing staying vs switching vs optimized pivot>",
    "comparison": [
      {{"option": "Option A: Stay in {current_role}", "trajectory": "...", "status": "..."}},
      {{"option": "Option B: Defined Switch to {target_role}", "trajectory": "...", "status": "..."}},
      {{"option": "Option C: Recommended Pivot to <Suggested Role>", "trajectory": "...", "status": "..."}}
    ]
  }},
  "suggested_better_role": {{
    "title": "<Better Suggested Role>",
    "tagline": "<One crisp value proposition sentence>",
    "why_superior": ["<reason 1 with numbers>", "<reason 2>", "<reason 3>", "<reason 4>"],
    "bridging_skills": ["<tool/skill 1>", "<tool/skill 2>", "<tool/skill 3>", "<tool/skill 4>"]
  }},
  "general_switching_pros_and_cons": {{
    "pros": [
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}}
    ],
    "cons": [
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}},
      {{"title": "...", "detail": "..."}}
    ],
    "strategic_checklist": [
      "<Actionable checklist item 1>",
      "<Actionable checklist item 2>",
      "<Actionable checklist item 3>"
    ]
  }}
}}
"""

    try:
        raw_resp = generate_llm(prompt)
        cleaned = re.sub(r"^```json\s*", "", raw_resp.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.rstrip("`").strip()
        data = json.loads(cleaned)
        # Validate critical keys
        if "salary_graph" in data and "switch_pros" in data and "suggested_better_role" in data:
            return data
    except Exception as e:
        print(f"[CareerSwitchAdvisor] LLM fallback engaged: {e}")

    # Fallback to robust deterministic benchmark generator
    return _get_benchmark_fallback(current_role, target_role, experience_level, currency)
