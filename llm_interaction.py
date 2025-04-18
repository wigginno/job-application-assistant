import os
import re
import json
import logging

from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# --- Configure OpenRouter API ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY not found in environment variables.")
    raise ValueError(
        "OPENROUTER_API_KEY not found in environment variables. Ensure it's set in your .env file."
    )

# --- Application Info for OpenRouter ---
APP_NAME = "Job Application Helper"
APP_URL = "https://github.com/wigginno/job-app-helper"

# --- Initialize OpenAI client to use OpenRouter ---
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": APP_URL,
        "X-Title": APP_NAME,
    },
)

# --- Model Configuration ---
MODEL_NAME = "gpt-4.1-2025-04-14"

# --- Structured Output Examples ---
PARSED_RESUME_OUTPUT_EXAMPLE = """{
    \"Sections\": [
        {
            \"title\": \"Education\",
            \"subsections\": [
                {
                    \"title\": \"University of Florida\",
                    \"entries\": [
                        \"Bachelor of Science in Computer Science\"
                    ]
                }
            ],
            \"entries\": []
        },
        {
            \"title\": \"Experience\",
            \"subsections\": [
                {
                    \"title\": \"Bob's Company - Data Engineer\",
                    \"entries\": [
                        \"Architected a data pipeline for real-time analytics improving team productivity by 20%\",
                        \"Led a team of 5 engineers in the development of a new data platform\",
                        \"Developed a custom reporting tool for sales analytics\"
                    ]
                }
            ],
            \"entries\": []
        },
        {
            \"title\": \"Certifications\",
            \"subsections\": [],
            \"entries\": [
                \"Cisco Certified Network Associate (CCNA)\",
                \"Oracle Certified Professional, Java SE 11 Developer\"
            ]
        }
    ],
    \"skills\": [
        \"FastAPI\",
        \"Django\",
        \"Python\",
        \"SQL\",
        \"Git\"
    ]
}"""
PARSED_RESUME_OUTPUT_EXAMPLE = re.sub(
    r"\n +", "", PARSED_RESUME_OUTPUT_EXAMPLE
).replace("\n", "")


# Pydantic models
class Subsection(BaseModel):
    title: str
    entries: list[str]


class Section(BaseModel):
    title: str
    subsections: list[Subsection]
    entries: list[str]


class ResumeData(BaseModel):
    sections: list[Section]
    skills: list[str]


class JobRanking(BaseModel):
    score: float
    explanation: str


class TailoringSuggestions(BaseModel):
    suggestions: list[str]


async def call_llm_for_resume_parsing(resume_text: str) -> ResumeData:
    """Call LLM for structured resume parsing."""

    system_prompt = f"""You are a resume parser. Your task is to extract structured information from the provided resume text.
Example output: {PARSED_RESUME_OUTPUT_EXAMPLE}
Major sections may vary based on the resume, as will the subsections, bullets, and nested structure.
You'll notice there is some flexibility in the format to accommodate this kind of variation.
If the resume has a dedicated section for skills, use that section's content for the skills array (and don't include the section in the \"Sections\" array).
If the resume DOES NOT have a dedicated section for skills, infer the skills from the content of the resume."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": resume_text},
    ]

    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=messages,
        response_format=ResumeData,
    )
    resume_data = response.choices[0].message.parsed
    return resume_data


async def call_llm_for_job_ranking(
    job_description: str, applicant_profile: str
) -> JobRanking:
    """Call LLM for job ranking."""

    system_prompt = """You are a job ranking assistant. Your task is to analyze the provided job description and applicant profile to determine the relevance of the applicant's profile to the job.

    You will output a job ranking score between 0.0 and 10.0, where 0.0 means no match at all and 10.0 means perfect match.
    You will also provide a brief explanation of your reasoning.
    """

    user_prompt = f"""Please analyze this job description and applicant profile and provide a match score and explanation:

    # Job Description
    {job_description}

    # Applicant Profile
    {applicant_profile}

    Format your response as a JSON object with 'score' (a float between 0.0 and 10.0) and 'explanation' (a string).
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=messages,
        response_format=JobRanking,
    )
    job_ranking = response.choices[0].message.parsed
    return job_ranking

async def call_llm_for_resume_tailoring(
    job_description: str, applicant_profile: str
) -> TailoringSuggestions:
    """Call LLM for resume tailoring."""

    system_prompt = """You are a resume tailoring assistant. Your task is to generate tailored content for a job application based on the provided job description and applicant profile.
Consider the applicant's qualifications and experiences in relation to the job description/requirements.
Provide a list of 3-5 specific, actionable suggestions on how to tailor the profile snippet to better match the job description.
Focus on incorporating keywords, highlighting relevant skills/experience, and using quantifiable achievements where possible.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Job Description: {job_description}\nApplicant Profile: {applicant_profile}",
        },
    ]

    response = client.beta.chat.completions.parse(
        model=MODEL_NAME,
        messages=messages,
        response_format=TailoringSuggestions,
    )
    tailoring_suggestions = response.choices[0].message.parsed
    return tailoring_suggestions
