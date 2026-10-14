from __future__ import annotations

import re


WORKDAY_LINK_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]*myworkdayjobs\.com[^\s\"'<>]*", re.I),
    re.compile(r"https?://[^\s\"'<>]*workday\.com[^\s\"'<>]*", re.I),
    re.compile(r"https?://[^\s\"'<>]*wd\d+\.myworkdayjobs\.com[^\s\"'<>]*", re.I),
]


def extract_verification_urls(email_body: str) -> list[str]:
    urls: list[str] = []
    for pattern in WORKDAY_LINK_PATTERNS:
        urls.extend(pattern.findall(email_body))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.rstrip(").,;]")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def pick_best_verification_url(urls: list[str]) -> str | None:
    if not urls:
        return None
    for u in urls:
        low = u.lower()
        if any(k in low for k in ("verify", "activate", "confirm", "registration", "email")):
            return u
    return urls[0]
