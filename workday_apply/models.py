from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    current: bool = False
    description: str = ""


class Education(BaseModel):
    school: str = ""
    degree: str = ""
    field_of_study: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class ApplicationProfile(BaseModel):
    """Persistent applicant data reused across Workday tenants."""

    email: str = "amansingh985077@gmail.com"
    password: str = ""  # stored locally only; set via `profile set-password`
    first_name: str = "Aman"
    last_name: str = "Singh"
    phone: str = "+32 495321838"
    alternate_email: str = "amansingh95077@gmail.com"
    linkedin_url: str = "https://linkedin.com/in/aman-singh-545319122/"
    country: str = ""
    address_line1: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    work_authorization: str = ""
    requires_sponsorship: str = ""  # Yes / No
    veteran_status: str = ""
    disability_status: str = ""
    gender: str = ""
    ethnicity: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    custom_answers: dict[str, str] = Field(default_factory=dict)
    resume_path: str = ""
    cover_letter_path: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()

    def get_answer(self, key: str, default: str = "") -> str:
        k = key.strip().lower()
        for ck, cv in self.custom_answers.items():
            if ck.strip().lower() == k:
                return cv
        return default


class ProfileStore(BaseModel):
    profile: ApplicationProfile = Field(default_factory=ApplicationProfile)
    applied_jobs: list[dict[str, Any]] = Field(default_factory=list)
