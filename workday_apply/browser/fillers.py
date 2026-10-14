from __future__ import annotations

import re
from typing import Callable

from playwright.async_api import Locator, Page

from workday_apply.models import ApplicationProfile


async def fill_visible_inputs(page: Page, profile: ApplicationProfile, ask: Callable[[str], str]) -> int:
    """Best-effort fill for Workday and similar forms. Returns count of fields touched."""
    filled = 0
    filled += await _fill_by_label(page, profile, ask)
    filled += await _fill_by_placeholder(page, profile)
    filled += await _fill_by_name_heuristics(page, profile)
    return filled


async def _fill_by_label(page: Page, profile: ApplicationProfile, ask: Callable[[str], str]) -> int:
    filled = 0
    labels = page.locator("label:visible")
    count = await labels.count()
    for i in range(min(count, 80)):
        label = labels.nth(i)
        text = (await label.inner_text()).strip()
        if not text:
            continue
        value = _value_for_label(text, profile, ask)
        if not value:
            continue
        control = await _control_for_label(page, label)
        if control is None:
            continue
        if await _set_control(control, value):
            filled += 1
    return filled


async def _control_for_label(page: Page, label: Locator) -> Locator | None:
    for_id = await label.get_attribute("for")
    if for_id:
        return page.locator(f"#{for_id}")
    parent = label.locator("xpath=..")
    inp = parent.locator("input, textarea, select").first
    if await inp.count():
        return inp
    return None


async def _set_control(control: Locator, value: str) -> bool:
    try:
        tag = await control.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            await control.select_option(label=value)
            return True
        input_type = await control.get_attribute("type") or "text"
        if input_type in ("checkbox", "radio"):
            return False
        current = await control.input_value()
        if current.strip():
            return False
        await control.fill(value)
        return True
    except Exception:
        return False


def _value_for_label(label: str, profile: ApplicationProfile, ask: Callable[[str], str]) -> str:
    key = label.strip()
    low = key.lower()
    mapping = [
        (("first name", "given name"), profile.first_name),
        (("last name", "family name", "surname"), profile.last_name),
        (("email", "e-mail"), profile.email),
        (("phone", "mobile", "telephone"), profile.phone),
        (("linkedin",), profile.linkedin_url),
        (("address", "street"), profile.address_line1),
        (("city", "town"), profile.city),
        (("state", "province", "region"), profile.state),
        (("zip", "postal"), profile.postal_code),
        (("country",), profile.country),
    ]
    for needles, val in mapping:
        if any(n in low for n in needles) and val:
            return val
    if "sponsor" in low and profile.requires_sponsorship:
        return profile.requires_sponsorship
    if "authorized" in low and "work" in low and profile.work_authorization:
        return profile.work_authorization
    stored = profile.get_answer(key)
    if stored:
        return stored
    # defer unknown required fields to user once
    if any(w in low for w in ("required", "*")) or True:
        pass
    return ""


async def _fill_by_placeholder(page: Page, profile: ApplicationProfile) -> int:
    filled = 0
    pairs = [
        ("first", profile.first_name),
        ("last", profile.last_name),
        ("email", profile.email),
        ("phone", profile.phone),
    ]
    for needle, val in pairs:
        if not val:
            continue
        loc = page.locator(f"input[placeholder*='{needle}' i]:visible")
        if await loc.count():
            try:
                el = loc.first
                if not (await el.input_value()).strip():
                    await el.fill(val)
                    filled += 1
            except Exception:
                pass
    return filled


async def _fill_by_name_heuristics(page: Page, profile: ApplicationProfile) -> int:
    filled = 0
    selectors = [
        ("input[name*='email' i]", profile.email),
        ("input[type='email']", profile.email),
        ("input[name*='first' i]", profile.first_name),
        ("input[name*='last' i]", profile.last_name),
        ("input[name*='phone' i]", profile.phone),
    ]
    for sel, val in selectors:
        if not val:
            continue
        loc = page.locator(sel)
        if await loc.count():
            try:
                el = loc.first
                if not (await el.input_value()).strip():
                    await el.fill(val)
                    filled += 1
            except Exception:
                pass
    return filled


async def upload_resume_if_present(page: Page, resume_path: str) -> bool:
    if not resume_path:
        return False
    file_inputs = page.locator("input[type='file']")
    if not await file_inputs.count():
        return False
    try:
        await file_inputs.first.set_input_files(resume_path)
        return True
    except Exception:
        return False


async def click_apply_or_sign_in(page: Page) -> None:
    for text in ("Apply", "Apply Manually", "Apply for this job", "Sign In", "Create Account"):
        btn = page.get_by_role("button", name=re.compile(text, re.I))
        if await btn.count():
            await btn.first.click(timeout=3000)
            return
        link = page.get_by_role("link", name=re.compile(text, re.I))
        if await link.count():
            await link.first.click(timeout=3000)
            return
