import os
import re
import time
import json
from dotenv import load_dotenv

load_dotenv(override=True)

import streamlit as st
from crewai import Crew, Agent, Task, LLM
from crewai.project import CrewBase, task, agent, crew
from tools import search_jobs, company_web_search_tool

st.set_page_config(page_title="Job Hunter Agent", layout="wide")
st.title("🎯 Autonomous Job Hunter & Interview Prep Agent")

# ============================================================
# API KEY ROTATION
# ============================================================
GROQ_KEYS = []
for key_name in ["GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
    key = os.environ.get(key_name)
    if key:
        GROQ_KEYS.append(key)
if not GROQ_KEYS:
    single = os.environ.get("GROQ_API_KEY")
    if single:
        GROQ_KEYS.append(single)

# Always set GROQ_API_KEY env var for CrewAI native provider
if GROQ_KEYS:
    os.environ["GROQ_API_KEY"] = GROQ_KEYS[0]

MODEL_NAME = "groq/llama-3.3-70b-versatile"


def get_llm(index: int) -> LLM:
    key = GROQ_KEYS[index % len(GROQ_KEYS)]
    os.environ["GROQ_API_KEY"] = key
    return LLM(model=MODEL_NAME, api_key=key)


# Sidebar
with st.sidebar:
    st.header("🔍 Search Parameters")
    level = st.text_input("Level", "Junior")
    position = st.text_input("Position", "ML Engineer")
    location = st.text_input("Location", "India")
    st.header("📄 Your Resume")
    resume_text = st.text_area("Paste your resume here...", height=300)

if not GROQ_KEYS:
    st.error("⚠️ No Groq API keys found. Set GROQ_API_KEY_1/GROQ_API_KEY_2 in .env")
else:
    st.sidebar.success(f"✅ {len(GROQ_KEYS)} API key(s) loaded")


# ============================================================
# Helper: Extract JSON from LLM text output
# ============================================================
def extract_json_from_text(text: str):
    """Finds the first JSON array or object in the text."""
    # Try to find JSON in markdown code blocks first
    code_block = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', text, re.DOTALL)
    if code_block:
        return json.loads(code_block.group(1))
    
    # Try to find raw JSON array or object
    for pattern in [r'(\[.*\])', r'(\{.*\})']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return None


@CrewBase
class JobHunterCrew:

    @agent
    def job_search_agent(self):
        return Agent(config=self.agents_config["job_search_agent"], llm=get_llm(0))

    @agent
    def job_matching_agent(self):
        return Agent(config=self.agents_config["job_matching_agent"], llm=get_llm(1))

    @agent
    def resume_optimization_agent(self):
        return Agent(config=self.agents_config["resume_optimization_agent"], llm=get_llm(0))

    @agent
    def company_research_agent(self):
        return Agent(config=self.agents_config["company_research_agent"], llm=get_llm(1), tools=[company_web_search_tool])

    @agent
    def interview_prep_agent(self):
        return Agent(config=self.agents_config["interview_prep_agent"], llm=get_llm(2 if len(GROQ_KEYS) > 2 else 0))

    # NO output_pydantic — this prevents the expensive 2nd LLM call
    @task
    def job_extraction_task(self):
        return Task(config=self.tasks_config["job_extraction_task"])

    @task
    def job_matching_task(self):
        return Task(config=self.tasks_config["job_matching_task"])

    @task
    def resume_rewriting_task(self):
        return Task(config=self.tasks_config["resume_rewriting_task"])

    @task
    def company_research_task(self):
        return Task(config=self.tasks_config["company_research_task"])

    @task
    def interview_prep_task(self):
        return Task(config=self.tasks_config["interview_prep_task"], context=[self.resume_rewriting_task(), self.company_research_task()])

    @crew
    def extraction_crew(self):
        return Crew(agents=[self.job_search_agent()], tasks=[self.job_extraction_task()], verbose=True)

    @crew
    def matching_crew(self):
        return Crew(agents=[self.job_matching_agent()], tasks=[self.job_matching_task()], verbose=True)

    @crew
    def prep_crew(self):
        return Crew(
            agents=[self.resume_optimization_agent(), self.company_research_agent(), self.interview_prep_agent()],
            tasks=[self.resume_rewriting_task(), self.company_research_task(), self.interview_prep_task()],
            verbose=True,
        )


if st.sidebar.button("🚀 Search Jobs", type="primary"):
    if not resume_text:
        st.error("Please paste your resume first!")
    elif not GROQ_KEYS:
        st.error("No API keys configured!")
    else:
        # === STEP 1: Scrape jobs in Python (deterministic, no LLM) ===
        with st.spinner("🔍 Searching the web for real job listings..."):
            query = f"{level} {position} jobs in {location}"
            scraped_results = search_jobs(query)

        if not scraped_results:
            st.error("❌ No jobs found. Try broadening your search terms.")
        else:
            st.success(f"✅ Found {len(scraped_results)} real job pages!")

            raw_job_data = ""
            for i, item in enumerate(scraped_results):
                raw_job_data += f"\n--- JOB PAGE {i+1} ---\n"
                raw_job_data += f"Title: {item['title']}\nURL: {item['url']}\nContent:\n{item['content']}\n"

            # === STEP 2: AI extracts structured jobs ===
            with st.spinner("🤖 Step 1/2: AI is extracting job details..."):
                crew1 = JobHunterCrew()
                extraction_result = crew1.extraction_crew().kickoff(
                    inputs={
                        "level": level, "position": position, "location": location,
                        "resume_text": resume_text, "raw_job_data": raw_job_data,
                    }
                )

            # === Cooldown ===
            st.info("⏳ Cooling down for Groq rate limit (65s)...")
            countdown = st.empty()
            for i in range(65, 0, -1):
                countdown.text(f"⏳ {i}s remaining...")
                time.sleep(1)
            countdown.empty()

            # === STEP 3: AI ranks jobs against resume ===
            with st.spinner("🤖 Step 2/2: AI is ranking jobs against your resume..."):
                crew2 = JobHunterCrew()
                matching_result = crew2.matching_crew().kickoff(
                    inputs={
                        "resume_text": resume_text,
                        "raw_job_data": extraction_result.raw,
                    }
                )

            # Parse the ranked results from raw text
            ranked_data = extract_json_from_text(matching_result.raw)
            if ranked_data:
                st.session_state.ranked_jobs = ranked_data
                st.session_state.resume_text = resume_text
            else:
                # Fallback: display raw text
                st.session_state.ranked_text = matching_result.raw
                st.session_state.resume_text = resume_text


if "ranked_jobs" in st.session_state:
    st.header("📋 Ranked Job Opportunities")
    for rj in st.session_state.ranked_jobs:
        job = rj.get("job", rj)
        title = job.get("job_title", rj.get("job_title", "Unknown"))
        company = job.get("company_name", rj.get("company_name", "Unknown"))
        score = rj.get("match_score", "?")
        reason = rj.get("reason", "")
        url = job.get("job_posting_url", rj.get("job_posting_url", "#"))
        summary = job.get("job_summary", rj.get("job_summary", ""))
        remote = job.get("is_remote_friendly", rj.get("is_remote_friendly", "N/A"))
        salary = job.get("compensation", rj.get("compensation", "N/A"))

        with st.expander(f"⭐ {score}/5 — {title} @ {company}"):
            st.markdown(f"**Reason:** {reason}")
            st.markdown(f"**Remote:** {remote} | **Salary:** {salary or 'N/A'}")
            st.markdown(f"**URL:** [Apply Here]({url})")
            st.markdown(f"**Summary:** {summary}")

            if st.button(f"📝 Generate Prep Guide", key=url):
                selected_job_json = json.dumps(job)
                resume = st.session_state.get("resume_text", "")

                # Cooldown before prep crew
                st.info("⏳ Cooling down (65s)...")
                cd = st.empty()
                for i in range(65, 0, -1):
                    cd.text(f"⏳ {i}s remaining...")
                    time.sleep(1)
                cd.empty()

                with st.spinner(f"Preparing for {company}..."):
                    crew3 = JobHunterCrew()
                    prep_result = crew3.prep_crew().kickoff(
                        inputs={"selected_job_json": selected_job_json, "resume_text": resume}
                    )

                st.success("✅ Preparation Complete!")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.subheader("📄 Tailored Resume")
                    try:
                        with open("output/rewritten_resume.md", "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                    except Exception:
                        st.write("No output generated.")
                with col2:
                    st.subheader("🏢 Company Research")
                    try:
                        with open("output/company_research.md", "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                    except Exception:
                        st.write("No output generated.")
                with col3:
                    st.subheader("🎤 Interview Prep")
                    try:
                        with open("output/interview_prep.md", "r", encoding="utf-8") as f:
                            st.markdown(f.read())
                    except Exception:
                        st.write("No output generated.")

elif "ranked_text" in st.session_state:
    st.header("📋 Ranked Job Opportunities")
    st.markdown(st.session_state.ranked_text)
