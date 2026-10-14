from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import BrowserContext, async_playwright

from workday_apply.store import BROWSER_DIR


@asynccontextmanager
async def browser_context(headless: bool = False) -> AsyncIterator[BrowserContext]:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        try:
            yield context
        finally:
            await context.close()
