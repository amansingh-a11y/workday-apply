from __future__ import annotations

import re
from pathlib import Path

from workday_apply.models import ApplicationProfile, Education, WorkExperience


def parse_resume(path: Path, profile: ApplicationProfile) -> ApplicationProfile:
    suffix = path.suffix.lower()
    if suffix == ".tex":
        return parse_resume_tex(path, profile)
    if suffix == ".pdf":
        return parse_resume_pdf(path, profile)
    raise ValueError(f"Unsupported resume format: {suffix} (use .tex or .pdf)")


def _clean_tex(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", s)
    s = s.replace(r"\/", "/")
    s = s.replace(r"\&", "&")
    s = s.replace(r"\%", "%")
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textit\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_resume_tex(path: Path, profile: ApplicationProfile) -> ApplicationProfile:
    text = path.read_text(encoding="utf-8", errors="replace")

    name_match = re.search(r"\\textbf\{([A-Z][A-Z\s]+)\}", text)
    if name_match:
        parts = name_match.group(1).strip().split()
        if len(parts) >= 2:
            profile.first_name = parts[0].title()
            profile.last_name = " ".join(parts[1:]).title()

    email_match = re.search(r"mailto:([^}]+)\}", text)
    if email_match:
        profile.alternate_email = email_match.group(1).strip()

    phone_match = re.search(r"\+?\d[\d\s\-]{8,}", text)
    if phone_match:
        profile.phone = phone_match.group(0).strip()

    linkedin = re.search(r"linkedin\.com/in/[^}\s|]+", text)
    if linkedin:
        profile.linkedin_url = "https://" + linkedin.group(0).rstrip("|")

    summary_block = re.search(r"\\section\{Summary\}(.*?)\\section\{", text, re.DOTALL)
    if summary_block:
        raw = summary_block.group(1)
        raw = re.sub(r"\\small\{?", "", raw)
        raw = raw.replace("}", "")
        profile.summary = _clean_tex(raw)

    exp_section = re.search(r"\\section\{Experience\}(.*?)\\section\{Education\}", text, re.DOTALL)
    if exp_section:
        blocks = re.findall(
            r"\\resumeSubheading\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}(.*?)(?=\\resumeSubheading|\\resumeSubHeadingListEnd)",
            exp_section.group(1),
            re.DOTALL,
        )
        profile.experience = []
        for company, loc, title, dates, body in blocks:
            bullets = re.findall(r"\\resumeItem\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", body)
            desc = " ".join(_clean_tex(b) for b in bullets)
            start, end = _split_dates(dates)
            profile.experience.append(
                WorkExperience(
                    company=_clean_tex(company),
                    location=_clean_tex(loc),
                    title=_clean_tex(title),
                    start_date=start,
                    end_date=end,
                    current="present" in end.lower(),
                    description=desc,
                )
            )

    edu_section = re.search(r"\\section\{Education\}(.*?)\\section\{", text, re.DOTALL)
    if edu_section:
        blocks = re.findall(
            r"\\resumeSubheading\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}",
            edu_section.group(1),
            re.DOTALL,
        )
        profile.education = []
        for school, dates, degree, gpa in blocks:
            start, end = _split_dates(dates)
            profile.education.append(
                Education(
                    school=_clean_tex(school),
                    degree=_clean_tex(degree),
                    start_date=start,
                    end_date=end,
                    gpa=_clean_tex(gpa),
                )
            )

    skills_section = re.search(r"\\section\{Technical Skills\}(.*?)\\section\{", text, re.DOTALL)
    if skills_section:
        flat = _clean_tex(skills_section.group(1))
        profile.skills = _parse_skill_tokens(flat)

    profile.resume_path = str(path.resolve())
    return profile


def parse_resume_pdf(path: Path, profile: ApplicationProfile) -> ApplicationProfile:
    text = extract_text_from_pdf(path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    _apply_contact_heuristics(text, profile)
    _apply_name_from_lines(lines, profile)

    lower_text = text.lower()
    summary = _section_after_heading(lines, ("summary", "profile", "about"))
    if summary:
        profile.summary = summary

    exp_lines = _lines_in_section(lines, ("experience", "work experience", "employment"))
    profile.experience = _parse_pdf_experience(exp_lines) or profile.experience

    edu_lines = _lines_in_section(lines, ("education", "academic"))
    parsed_edu = _parse_pdf_education(edu_lines)
    if parsed_edu:
        profile.education = parsed_edu

    skill_lines = _lines_in_section(lines, ("technical skills", "skills", "technologies"))
    if skill_lines:
        profile.skills = _parse_skill_tokens(" ".join(skill_lines))

    if not profile.summary and "senior" in lower_text:
        for i, ln in enumerate(lines[:12]):
            if len(ln) > 80 and not re.search(r"@|http", ln):
                profile.summary = ln
                break

    profile.resume_path = str(path.resolve())
    return profile


def _apply_contact_heuristics(text: str, profile: ApplicationProfile) -> None:
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if email:
        profile.alternate_email = email.group(0)

    phone = re.search(r"\+?\d[\d\s\-()]{8,}\d", text)
    if phone:
        profile.phone = phone.group(0).strip()

    linkedin = re.search(r"(https?://)?(www\.)?linkedin\.com/in/[\w\-]+", text, re.I)
    if linkedin:
        url = linkedin.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        profile.linkedin_url = url


def _apply_name_from_lines(lines: list[str], profile: ApplicationProfile) -> None:
    for ln in lines[:5]:
        if re.search(r"@|linkedin|http|\+?\d{10}", ln, re.I):
            continue
        if re.match(r"^[A-Z][A-Za-z]+(\s+[A-Z][A-Za-z]+)+$", ln):
            parts = ln.split()
            profile.first_name = parts[0]
            profile.last_name = " ".join(parts[1:])
            return
        if re.match(r"^[A-Z][A-Z\s]{3,}$", ln) and len(ln.split()) >= 2:
            parts = ln.split()
            profile.first_name = parts[0].title()
            profile.last_name = " ".join(p.title() for p in parts[1:])
            return


def _section_after_heading(lines: list[str], headings: tuple[str, ...]) -> str:
    collected: list[str] = []
    in_section = False
    for ln in lines:
        low = ln.lower()
        if any(low == h or low.startswith(h + " ") for h in headings):
            in_section = True
            continue
        if in_section:
            if _is_section_heading(ln):
                break
            collected.append(ln)
    return " ".join(collected[:6]).strip()


def _lines_in_section(lines: list[str], headings: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    in_section = False
    for ln in lines:
        low = ln.lower()
        if any(low == h or low.startswith(h) for h in headings):
            in_section = True
            continue
        if in_section:
            if _is_section_heading(ln) and out:
                break
            out.append(ln)
    return out


def _is_section_heading(ln: str) -> bool:
    low = ln.lower()
    known = (
        "experience",
        "education",
        "skills",
        "projects",
        "summary",
        "achievements",
        "certifications",
    )
    return low in known or (len(ln) < 40 and ln.isupper())


def _parse_pdf_experience(lines: list[str]) -> list[WorkExperience]:
    if not lines:
        return []
    entries: list[WorkExperience] = []
    date_re = re.compile(
        r"(\d{1,2}/\d{4}|\d{4})\s*[-–]\s*(\d{1,2}/\d{4}|\d{4}|present|current)",
        re.I,
    )
    i = 0
    while i < len(lines):
        ln = lines[i]
        dm = date_re.search(ln)
        if dm:
            title = lines[i - 1] if i > 0 else ""
            company = lines[i - 2] if i > 1 else title
            if date_re.search(company):
                company = title
                title = ""
            start, end = dm.group(1), dm.group(2)
            desc_parts: list[str] = []
            j = i + 1
            while j < len(lines) and not date_re.search(lines[j]) and not _is_section_heading(lines[j]):
                desc_parts.append(lines[j])
                j += 1
                if len(desc_parts) >= 4:
                    break
            entries.append(
                WorkExperience(
                    company=company.strip(),
                    title=title.strip() if title != company else "",
                    start_date=start,
                    end_date=end,
                    current=end.lower() in ("present", "current"),
                    description=" ".join(desc_parts),
                )
            )
            i = j
            continue
        i += 1
    return entries[:8]


def _parse_pdf_education(lines: list[str]) -> list[Education]:
    if not lines:
        return []
    out: list[Education] = []
    for ln in lines[:6]:
        gpa = ""
        gm = re.search(r"CGPA[:\s]*[\d.]+|GPA[:\s]*[\d.]+", ln, re.I)
        if gm:
            gpa = gm.group(0)
        if any(k in ln.lower() for k in ("bachelor", "master", "b.e", "b.tech", "university", "institute")):
            out.append(Education(school=ln, degree=ln, gpa=gpa))
    return out[:3]


def _parse_skill_tokens(flat: str) -> list[str]:
    skills: list[str] = []
    for token in re.split(r"[,;|•]", flat):
        t = re.sub(r"^(languages|backend|data|cloud|ai|practices)\s*:\s*", "", token, flags=re.I).strip()
        if t and 1 < len(t) < 48 and not t.startswith("\\"):
            skills.append(t)
    return skills[:60]


def _split_dates(raw: str) -> tuple[str, str]:
    raw = _clean_tex(raw)
    if " - " in raw:
        a, b = raw.split(" - ", 1)
        return a.strip(), b.strip()
    return raw, ""


def extract_text_from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
