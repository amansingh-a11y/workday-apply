from __future__ import annotations

import asyncio
import re
from typing import Callable

from playwright.async_api import Page

from workday_apply.browser.fillers import click_apply_or_sign_in, fill_visible_inputs, upload_resume_if_present
from workday_apply.models import ApplicationProfile


async def open_job(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    await page.wait_for_timeout(1500)


async def run_signup_flow(
    page: Page,
    profile: ApplicationProfile,
    ask: Callable[[str], str],
) -> None:
    await click_apply_or_sign_in(page)
    await page.wait_for_timeout(2000)

    create = page.get_by_role("button", name=re.compile(r"create account", re.I))
    if await create.count():
        await create.first.click()
    else:
        link = page.get_by_role("link", name=re.compile(r"create account", re.I))
        if await link.count():
            await link.first.click()

    await page.wait_for_timeout(1000)
    await fill_visible_inputs(page, profile, ask)

    if profile.password:
        for sel in ("input[type='password']", "input[name*='password' i]"):
            loc = page.locator(sel)
            if await loc.count():
                for i in range(await loc.count()):
                    el = loc.nth(i)
                    if not (await el.input_value()).strip():
                        await el.fill(profile.password)
                break

    email = page.locator("input[type='email'], input[name*='email' i]")
    if await email.count() and profile.email:
        el = email.first
        if not (await el.input_value()).strip():
            await el.fill(profile.email)


async def complete_verification(page: Page, verify_url: str) -> None:
    await page.goto(verify_url, wait_until="domcontentloaded", timeout=120_000)
    await page.wait_for_timeout(3000)


async def run_apply_flow(
    page: Page,
    job_url: str,
    profile: ApplicationProfile,
    ask: Callable[[str], str],
    *,
    max_steps: int = 25,
    step_pause_sec: float = 1.5,
) -> None:
    await open_job(page, job_url)
    await click_apply_or_sign_in(page)
    await page.wait_for_timeout(2000)

    for step in range(max_steps):
        await fill_visible_inputs(page, profile, ask)
        await upload_resume_if_present(page, profile.resume_path)

        # Save answers for labels we could not map — prompt user on empty required-looking fields
        await _prompt_unknown_required(page, profile, ask)

        next_btn = page.get_by_role(
            "button",
            name=re.compile(r"save and continue|next|continue|submit application", re.I),
        )
        if await next_btn.count():
            await next_btn.first.click(timeout=5000)
            await page.wait_for_timeout(int(step_pause_sec * 1000))
            continue

        submit = page.get_by_role("button", name=re.compile(r"submit", re.I))
        if await submit.count():
            # stop before final submit — user confirms in browser
            break

        if step == 0:
            await asyncio.sleep(step_pause_sec)
        else:
            break


async def _prompt_unknown_required(
    page: Page,
    profile: ApplicationProfile,
    ask: Callable[[str], str],
) -> None:
    labels = page.locator("label:visible")
    count = await labels.count()
    for i in range(min(count, 40)):
        label = labels.nth(i)
        text = (await label.inner_text()).strip()
        if not text or profile.get_answer(text):
            continue
        low = text.lower()
        if not any(k in low for k in ("?", "required", "please", "select", "country", "sponsor", "veteran")):
            continue
        ans = ask(f"Workday asks: «{text}»")
        if ans:
            profile.custom_answers[text] = ans
