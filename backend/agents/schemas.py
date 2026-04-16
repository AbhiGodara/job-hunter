"""
Pydantic schemas for structured LLM output.
Ensures type-safe, validated responses from AI agents.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class TailoredResume(BaseModel):
    """Structured output from the Resume Tailor agent."""
    contact_info: str = Field(description="Name, email, phone, LinkedIn, GitHub")
    professional_summary: str = Field(description="2-3 sentence tailored summary")
    technical_skills: List[str] = Field(description="List of relevant technical skills")
    experience: List[dict] = Field(description="List of work experiences with company, role, duration, bullets")
    education: List[dict] = Field(description="List of education entries")
    projects: List[dict] = Field(default_factory=list, description="Relevant projects")
    certifications: List[str] = Field(default_factory=list, description="Certifications if any")


class CompanyResearch(BaseModel):
    """Structured output from the Company Researcher agent."""
    overview: str = Field(description="Company overview paragraph")
    tech_stack: List[str] = Field(description="Technologies used at the company")
    recent_news: str = Field(description="Recent company news and developments")
    interview_process: str = Field(description="What to expect in their interview")
    culture: str = Field(description="Company culture and work-life balance info")
    why_interesting: str = Field(description="Why this role is interesting")


class InterviewQuestion(BaseModel):
    """Single interview question with a tailored answer."""
    question: str
    ideal_answer: str


class InterviewPrep(BaseModel):
    """Structured output from the Interview Coach agent."""
    top_questions: List[InterviewQuestion] = Field(description="Top 10 interview questions with answers")
    questions_to_ask: List[str] = Field(description="5 smart questions to ask the interviewer")
    key_topics: List[str] = Field(description="Technical topics to study")
    red_flags: List[str] = Field(description="Red flags to watch for")
    salary_tips: List[str] = Field(description="Salary negotiation talking points")


class JobDescription(BaseModel):
    """Structured job description extracted from ATS data."""
    title: str = ""
    company: str = ""
    location: str = ""
    salary_range: Optional[str] = None
    experience_level: Optional[str] = None
    employment_type: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    responsibilities: str = ""
    requirements: str = ""
    description: str = ""
    benefits: Optional[str] = None
    apply_url: str = ""
