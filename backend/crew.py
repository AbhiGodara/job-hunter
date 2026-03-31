"""
CrewAI pipeline — refactored from app.py for use with Flask backend.
Handles job extraction, matching, and prep guide generation.
"""

import os
import re
import json
import time
from typing import List, Dict, Optional
from crewai import Crew, Agent, Task, LLM
from backend.rate_limiter import RateLimiter, retry_with_backoff

# Import tools for company research
try:
    from tools import company_web_search_tool
except ImportError:
    company_web_search_tool = None

MODEL_NAME = "groq/llama-3.3-70b-versatile"

rate_limiter = RateLimiter()


def get_llm() -> LLM:
    """Get an LLM instance with the next available API key."""
    key = rate_limiter.get_next_key()
    return LLM(model=MODEL_NAME, api_key=key)


def extract_json_from_text(text: str):
    """Extract JSON array or object from LLM text output."""
    # Try markdown code blocks first
    code_block = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON
    for pattern in [r"(\[.*\])", r"(\{.*\})"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return None


def _load_yaml_config(filename: str) -> dict:
    """Load a YAML config file."""
    import yaml
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", filename)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_extraction(
    raw_job_data: str,
    level: str,
    position: str,
    location: str,
    resume_text: str,
    on_progress=None,
) -> str:
    """
    Run the job extraction crew — parses raw scraped data into structured jobs.
    Returns raw text output (JSON string).
    """
    if on_progress:
        on_progress("AI is extracting job details...", 0.5)

    agents_config = _load_yaml_config("agents.yaml")
    tasks_config = _load_yaml_config("tasks.yaml")

    llm = get_llm()

    search_agent = Agent(
        role=agents_config["job_search_agent"]["role"],
        goal=agents_config["job_search_agent"]["goal"],
        backstory=agents_config["job_search_agent"]["backstory"],
        llm=llm,
        verbose=True,
    )

    extraction_task_config = tasks_config["job_extraction_task"]
    description = extraction_task_config["description"].format(
        raw_job_data=raw_job_data,
        level=level,
        position=position,
        location=location,
        resume_text=resume_text,
    )

    extraction_task = Task(
        description=description,
        expected_output=extraction_task_config["expected_output"],
        agent=search_agent,
    )

    extraction_crew = Crew(
        agents=[search_agent],
        tasks=[extraction_task],
        verbose=True,
    )

    result = extraction_crew.kickoff()
    rate_limiter.mark_key_used(os.environ.get("GROQ_API_KEY", ""))

    if on_progress:
        on_progress("Job extraction complete!", 0.6)

    return result.raw


def run_matching(
    extracted_jobs_text: str,
    resume_text: str,
    on_progress=None,
) -> List[Dict]:
    """
    Run the job matching crew — scores jobs against resume.
    Returns list of ranked job dicts.
    """
    if on_progress:
        on_progress("AI is ranking jobs against your resume...", 0.75)

    # Wait for rate limit cooldown
    wait_time = rate_limiter.get_wait_time()
    if wait_time > 0:
        if on_progress:
            on_progress(f"Rate limit cooldown: {int(wait_time)}s remaining...", 0.7)
        time.sleep(wait_time + 2)

    agents_config = _load_yaml_config("agents.yaml")
    tasks_config = _load_yaml_config("tasks.yaml")

    llm = get_llm()

    matching_agent = Agent(
        role=agents_config["job_matching_agent"]["role"],
        goal=agents_config["job_matching_agent"]["goal"],
        backstory=agents_config["job_matching_agent"]["backstory"],
        llm=llm,
        verbose=True,
    )

    matching_task_config = tasks_config["job_matching_task"]
    description = matching_task_config["description"].format(
        raw_job_data=extracted_jobs_text,
        resume_text=resume_text,
    )

    matching_task = Task(
        description=description,
        expected_output=matching_task_config["expected_output"],
        agent=matching_agent,
    )

    matching_crew = Crew(
        agents=[matching_agent],
        tasks=[matching_task],
        verbose=True,
    )

    result = matching_crew.kickoff()
    rate_limiter.mark_key_used(os.environ.get("GROQ_API_KEY", ""))

    if on_progress:
        on_progress("Job ranking complete!", 0.9)

    parsed = extract_json_from_text(result.raw)
    return parsed if parsed else []


def run_prep(
    selected_job_json: str,
    resume_text: str,
    on_progress=None,
) -> Dict[str, str]:
    """
    Run the prep crew — generates tailored resume, company research, and interview prep.
    Returns dict with keys: resume, research, interview_prep.
    """
    agents_config = _load_yaml_config("agents.yaml")
    tasks_config = _load_yaml_config("tasks.yaml")

    results = {}
    task_names = [
        ("resume_rewriting_task", "resume_optimization_agent", "Tailoring your resume..."),
        ("company_research_task", "company_research_agent", "Researching the company..."),
        ("interview_prep_task", "interview_prep_agent", "Preparing interview guide..."),
    ]

    for i, (task_key, agent_key, progress_msg) in enumerate(task_names):
        if on_progress:
            on_progress(progress_msg, (i + 1) / len(task_names))

        # Wait for rate limit cooldown
        wait_time = rate_limiter.get_wait_time()
        if wait_time > 0:
            if on_progress:
                on_progress(f"Rate limit cooldown: {int(wait_time)}s...", 0)
            time.sleep(wait_time + 2)

        llm = get_llm()

        agent_conf = agents_config[agent_key]
        tools = [company_web_search_tool] if agent_key == "company_research_agent" and company_web_search_tool else []

        prep_agent = Agent(
            role=agent_conf["role"],
            goal=agent_conf["goal"],
            backstory=agent_conf["backstory"],
            llm=llm,
            verbose=True,
            tools=tools,
        )

        task_conf = tasks_config[task_key]
        # Build context from previous results for interview prep
        context_text = ""
        if task_key == "interview_prep_task":
            context_text = f"\n\nTailored Resume:\n{results.get('resume', '')}\n\nCompany Research:\n{results.get('research', '')}"

        description = task_conf["description"].format(
            selected_job_json=selected_job_json,
            resume_text=resume_text + context_text,
        )

        prep_task = Task(
            description=description,
            expected_output=task_conf["expected_output"],
            agent=prep_agent,
        )

        if task_conf.get("output_file"):
            prep_task.output_file = task_conf["output_file"]

        prep_crew = Crew(
            agents=[prep_agent],
            tasks=[prep_task],
            verbose=True,
        )

        result = prep_crew.kickoff()
        rate_limiter.mark_key_used(os.environ.get("GROQ_API_KEY", ""))

        # Map results
        if task_key == "resume_rewriting_task":
            results["resume"] = result.raw
        elif task_key == "company_research_task":
            results["research"] = result.raw
        elif task_key == "interview_prep_task":
            results["interview_prep"] = result.raw

    return results
