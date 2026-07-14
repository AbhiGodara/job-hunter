"""
CrewAI Multi-Agent System for Job Hunter.

Three specialized AI agents collaborate to prepare a candidate:
  1. Resume Tailor Agent  — Rewrites resume to match the JD
  2. Company Researcher   — Researches the company via web search
  3. Interview Coach      — Creates a strategic interview prep guide

Each agent receives structured context and produces Markdown output.
The Crew orchestrates execution in sequential order.
"""
import logging
import os
from textwrap import dedent
from crewai import Agent, Task, Crew, Process, LLM
from backend.config import GROQ_API_KEYS, LLM_MODELS

log = logging.getLogger(__name__)


def _build_llm() -> LLM:
    """Build a CrewAI-compatible LLM using Groq."""
    api_key = GROQ_API_KEYS[0] if GROQ_API_KEYS else os.getenv("GROQ_API_KEY_1", "")
    model = LLM_MODELS[0] if LLM_MODELS else "llama-3.3-70b-versatile"

    return LLM(
        model=f"groq/{model}",
        api_key=api_key,
        temperature=0.3,
        max_tokens=3500,
    )


# ── Agent Definitions ────────────────────────────────────────────────

def _create_resume_agent(llm: LLM) -> Agent:
    return Agent(
        role="Resume Tailor",
        goal="Rewrite the candidate's resume to perfectly match the target job description",
        backstory=dedent("""\
            You are a senior resume consultant with 15 years of experience helping 
            candidates land roles at top tech companies. You understand ATS parsing, 
            keyword optimization, and how to present experience compellingly.
            You NEVER fabricate experience — you only reorganize, emphasize, and 
            add relevant keywords from the JD naturally."""),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def _create_researcher_agent(llm: LLM) -> Agent:
    return Agent(
        role="Company Researcher",
        goal="Provide deep, actionable intelligence about the target company",
        backstory=dedent("""\
            You are an expert career intelligence analyst. You synthesize public 
            information about companies including their tech stack, culture, recent 
            news, and interview processes. You help candidates walk into interviews 
            feeling like insiders."""),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def _create_interview_agent(llm: LLM) -> Agent:
    return Agent(
        role="Interview Coach",
        goal="Prepare the candidate to ace their interview with tailored questions and strategies",
        backstory=dedent("""\
            You are an elite interview coach who has prepared thousands of 
            candidates for technical interviews at FAANG and top-tier companies. 
            You create personalized prep guides based on the candidate's actual 
            experience and the specific role requirements."""),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


# ── Task Definitions ────────────────────────────────────────────────

def _create_resume_task(agent: Agent, job_info: str, resume_context: str) -> Task:
    return Task(
        description=dedent(f"""\
            Rewrite the candidate's resume to be perfectly tailored for this job.
            
            RULES:
            1. Keep all facts accurate — do NOT invent or fabricate any experience
            2. Reorder and emphasize sections that match the job requirements
            3. Add relevant keywords from the job description naturally
            4. Use clean Markdown with ## headers for sections
            5. Include: Contact Info, Professional Summary, Technical Skills, 
               Experience, Education, Projects (if relevant)
            6. Use bullet points with action verbs for experience items
            
            --- Target Job ---
            {job_info}
            
            --- Candidate Resume (retrieved via RAG, ordered by relevance) ---
            {resume_context}"""),
        expected_output="A complete, professionally formatted resume in Markdown that is tailored to the target job.",
        agent=agent,
    )


def _create_research_task(agent: Agent, company: str, title: str, search_context: str) -> Task:
    return Task(
        description=dedent(f"""\
            Create a comprehensive research report about {company} for the role: {title}.
            
            Use the web search context below AND your own knowledge to create the report.
            
            Include EXACTLY these sections:
            ## Company Overview
            ## Tech Stack
            ## Recent News
            ## Interview Process
            ## Culture & Work-Life Balance
            ## Why This Role Is Interesting
            
            If web context is sparse, rely on your knowledge and note any limitations.
            
            --- Web Search Context ---
            {search_context if search_context else "No web results available — use your knowledge."}"""),
        expected_output="A detailed, Markdown-formatted company research report with all six sections.",
        agent=agent,
    )


def _create_interview_task(agent: Agent, job_info: str, resume_context: str) -> Task:
    return Task(
        description=dedent(f"""\
            Create a comprehensive interview preparation guide for the candidate.
            
            Include EXACTLY these sections:
            ## Top 10 Interview Questions & Ideal Answers
            For each: provide the question and a tailored answer using the candidate's actual experience.
            
            ## 5 Questions to Ask the Interviewer
            Smart, role-specific questions showing genuine interest.
            
            ## Key Topics to Study
            Technical concepts, frameworks, and domain knowledge to review.
            
            ## Red Flags to Watch For
            Warning signs about the role/team/company.
            
            ## Salary Negotiation Tips
            Concrete talking points for compensation discussion.
            
            --- Target Job ---
            {job_info}
            
            --- Candidate Resume ---
            {resume_context}"""),
        expected_output="A complete interview prep guide in Markdown with all five sections, personalized to the candidate.",
        agent=agent,
    )


# ── Main Crew Runner ────────────────────────────────────────────────

def _search_web(query: str, max_results: int = 5) -> str:
    """Search the web for company info using Tavily API, fallback to DuckDuckGo."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            response = client.search(query=query, max_results=max_results, search_depth="basic")
            results_text = "\n".join(
                f"- {r.get('title', '')}: {r.get('content', '')}" for r in response.get("results", [])
            )
            if results_text:
                return results_text
        except Exception as e:
            log.warning(f"Tavily company research failed, falling back to DDG: {e}")

    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return "\n".join(
                f"- {r.get('title', '')}: {r.get('body', '')}" for r in results
            )
    except Exception:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return "\n".join(
                    f"- {r.get('title', '')}: {r.get('body', '')}" for r in results
                )
        except Exception as e:
            log.warning(f"Web search failed: {e}")
            return ""


def run_prep_crew(job: dict, resume_context: str) -> dict:
    """
    Execute the full CrewAI prep pipeline for a single job.
    
    Args:
        job: Job dict with title, company, location, description, skills, etc.
        resume_context: Resume text (ideally from RAG retrieval)
        
    Returns:
        dict with 'resume', 'research', 'interview' keys (Markdown strings)
    """
    if not GROQ_API_KEYS:
        return {
            "resume": "**Error:** No Groq API keys configured.",
            "research": "**Error:** No Groq API keys configured.",
            "interview": "**Error:** No Groq API keys configured.",
        }

    try:
        llm = _build_llm()

        # Create agents
        resume_agent = _create_resume_agent(llm)
        researcher_agent = _create_researcher_agent(llm)
        interview_agent = _create_interview_agent(llm)

        # Build job info string
        job_info = (
            f"Job Title: {job.get('title', 'N/A')}\n"
            f"Company: {job.get('company', 'N/A')}\n"
            f"Location: {job.get('location', 'N/A')}\n"
            f"Experience: {job.get('experience_level', 'Not specified')}\n"
            f"Salary: {job.get('salary_range', 'Not disclosed')}\n"
            f"Skills: {job.get('skills', 'Not specified')}\n"
            f"Description: {job.get('description', 'Not provided')}\n"
            f"Requirements: {job.get('requirements', 'Not provided')}"
        )

        # Web search for company research
        company = job.get("company", "Unknown")
        title = job.get("title", "Unknown Role")
        search_context = _search_web(
            f"{company} {title} tech stack culture news interview process",
            max_results=5,
        )

        # Create tasks
        resume_task = _create_resume_task(resume_agent, job_info, resume_context[:8000])
        research_task = _create_research_task(researcher_agent, company, title, search_context)
        interview_task = _create_interview_task(interview_agent, job_info, resume_context[:6000])

        # Assemble and run crew
        crew = Crew(
            agents=[resume_agent, researcher_agent, interview_agent],
            tasks=[resume_task, research_task, interview_task],
            process=Process.sequential,
            verbose=False,
        )

        log.info(f"Starting CrewAI prep for: {title} at {company}")
        result = crew.kickoff()

        # Extract individual task outputs
        task_outputs = result.tasks_output if hasattr(result, 'tasks_output') else []

        resume_md = str(task_outputs[0]) if len(task_outputs) > 0 else "Resume generation failed."
        research_md = str(task_outputs[1]) if len(task_outputs) > 1 else "Research generation failed."
        interview_md = str(task_outputs[2]) if len(task_outputs) > 2 else "Interview prep generation failed."

        log.info(f"CrewAI prep completed for: {title} at {company}")
        return {
            "resume": resume_md.strip(),
            "research": research_md.strip(),
            "interview": interview_md.strip(),
        }

    except Exception as e:
        log.error(f"CrewAI prep failed: {e}", exc_info=True)
        # Fallback to individual agent calls
        return _fallback_prep(job, resume_context)


def _fallback_prep(job: dict, resume_context: str) -> dict:
    """
    Fallback: run each agent individually via direct Groq calls
    if CrewAI fails (e.g., rate limit, dependency issue).
    """
    log.warning("Falling back to direct Groq calls (CrewAI failed)")
    from backend.agents.resume_writer import write_resume
    from backend.agents.researcher import research_company
    from backend.agents.interview_prep import prep_interview

    return {
        "resume": write_resume(job, resume_context),
        "research": research_company(job),
        "interview": prep_interview(job, resume_context),
    }
