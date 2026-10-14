from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from workday_apply.browser.session import browser_context
from workday_apply.browser.workday import complete_verification, run_apply_flow, run_signup_flow
from workday_apply.models import ApplicationProfile
from workday_apply.gmail_oauth import (
    credentials_configured,
    fetch_recent_workday_email_bodies,
    run_gmail_auth,
    write_credentials_template,
)
from workday_apply.resume_parser import parse_resume
from workday_apply.store import CONFIG_DIR, load_store, save_store
from workday_apply.verify import extract_verification_urls, pick_best_verification_url

app = typer.Typer(
    name="workday-apply",
    help="Apply to Workday jobs with a saved profile, resume import, and browser assist.",
    no_args_is_help=True,
)
console = Console()

_pending_answers: dict[str, str] = {}


def _ask(prompt: str) -> str:
    if prompt in _pending_answers:
        return _pending_answers[prompt]
    try:
        return console.input(f"[cyan]{prompt}[/cyan] ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""


@app.command("init")
def init_profile(
    email: str = typer.Option("amansingh985077@gmail.com", help="Workday account email"),
    import_resume: Optional[Path] = typer.Option(
        None,
        "--resume",
        help="Import from resume (.tex or .pdf path)",
    ),
) -> None:
    """Create or reset local profile storage (data stays on your machine)."""
    store = load_store()
    store.profile.email = email
    default_resume = Path.home() / "work" / "resume" / "resume.tex"
    resume_path = import_resume or (default_resume if default_resume.exists() else None)
    if resume_path and resume_path.suffix.lower() in (".tex", ".pdf"):
        store.profile = parse_resume(resume_path, store.profile)
        console.print(f"[green]Imported[/green] {resume_path}")
    elif resume_path:
        console.print("[yellow]Use .tex or .pdf for auto-parse.[/yellow]")

    pwd = getpass.getpass("Workday password (stored locally, not synced): ")
    if pwd:
        store.profile.password = pwd
    save_store(store)
    console.print(Panel(f"Profile saved under [bold]{CONFIG_DIR}[/bold]", title="Ready"))


@app.command("import-resume")
def import_resume_cmd(path: Path) -> None:
    """Parse resume.tex (or set PDF path) into your profile."""
    store = load_store()
    if path.suffix.lower() in (".tex", ".pdf"):
        store.profile = parse_resume(path, store.profile)
    else:
        store.profile.resume_path = str(path.resolve())
    save_store(store)
    console.print("[green]Profile updated from resume.[/green]")


@app.command("profile")
def show_profile(
    set_field: Optional[str] = typer.Option(None, "--set", help="field=value e.g. city=Bengaluru"),
) -> None:
    """Show profile or set a single top-level field."""
    store = load_store()
    if set_field:
        if "=" not in set_field:
            raise typer.BadParameter("Use --set field=value")
        key, val = set_field.split("=", 1)
        key = key.strip()
        if not hasattr(store.profile, key):
            store.profile.custom_answers[key] = val
        else:
            setattr(store.profile, key, val)
        save_store(store)
        console.print(f"[green]Set[/green] {key}")
        return

    p = store.profile
    table = Table(title="Application profile")
    table.add_column("Field")
    table.add_column("Value")
    for name in (
        "email",
        "first_name",
        "last_name",
        "phone",
        "linkedin_url",
        "country",
        "city",
        "work_authorization",
        "requires_sponsorship",
        "resume_path",
    ):
        table.add_row(name, str(getattr(p, name, ""))[:80])
    table.add_row("experience_count", str(len(p.experience)))
    table.add_row("education_count", str(len(p.education)))
    table.add_row("custom_answers", str(len(p.custom_answers)))
    console.print(table)
    console.print(f"[dim]Storage: {CONFIG_DIR}[/dim]")


@app.command("set-password")
def set_password() -> None:
    store = load_store()
    pwd = getpass.getpass("New Workday password: ")
    store.profile.password = pwd
    save_store(store)
    console.print("[green]Password updated locally.[/green]")


def _resolve_verification_url(
    gmail: bool,
    paste_file: Optional[Path],
) -> str:
    bodies: list[str] = []
    if gmail:
        bodies = fetch_recent_workday_email_bodies()
        if not bodies:
            console.print("[red]No recent Workday emails found via Gmail.[/red]")
            raise typer.Exit(1)
    elif paste_file:
        bodies = [paste_file.read_text(encoding="utf-8", errors="replace")]
    else:
        console.print(
            "Paste the full Workday email below, then press Ctrl-D (Mac) or Ctrl-Z Enter (Windows):"
        )
        bodies = [sys.stdin.read()]

    for body in bodies:
        urls = extract_verification_urls(body)
        url = pick_best_verification_url(urls)
        if url:
            return url
    console.print("[red]No Workday URL found.[/red]")
    raise typer.Exit(1)


@app.command("gmail-setup")
def gmail_setup() -> None:
    """Write OAuth template path hints under your config directory."""
    write_credentials_template()
    console.print(
        Panel(
            f"1. Enable Gmail API in Google Cloud.\n"
            f"2. Save Desktop OAuth JSON as:\n   [bold]{CONFIG_DIR / 'gmail-credentials.json'}[/bold]\n"
            f"3. Run: workday-apply gmail-auth\n"
            f"See docs/gmail-setup.md",
            title="Gmail OAuth",
        )
    )


@app.command("gmail-auth")
def gmail_auth() -> None:
    """Browser OAuth for Gmail read-only (verification emails)."""
    if not credentials_configured():
        console.print("[red]Missing gmail-credentials.json — run `workday-apply gmail-setup` first.[/red]")
        raise typer.Exit(1)
    run_gmail_auth()
    console.print("[green]Gmail authorized.[/green]")


@app.command("verify-email")
def verify_email(
    paste_file: Optional[Path] = typer.Option(None, "--file", "-f", help="File containing pasted email"),
    gmail: bool = typer.Option(False, "--gmail", "-g", help="Fetch latest Workday email from Gmail"),
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Open Workday email verification link (paste, file, or --gmail)."""
    url = _resolve_verification_url(gmail=gmail, paste_file=paste_file)
    console.print(f"Opening: [link={url}]{url}[/link]")

    async def _run() -> None:
        async with browser_context(headless=headless) as ctx:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await complete_verification(page, url)
            console.print("[yellow]Complete any remaining steps in the browser, then close it.[/yellow]")
            await page.wait_for_timeout(300_000)

    asyncio.run(_run())


@app.command("signup")
def signup(
    job_url: str = typer.Argument(..., help="Any job posting URL on the company's Workday site"),
    headless: bool = typer.Option(False, "--headless"),
) -> None:
    """Open job page and walk through Create Account (you finish captcha / email in browser)."""
    store = load_store()
    if not store.profile.password:
        console.print("[red]Run `workday-apply init` or `set-password` first.[/red]")
        raise typer.Exit(1)

    async def _run() -> None:
        async with browser_context(headless=headless) as ctx:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(job_url, wait_until="domcontentloaded")
            await run_signup_flow(page, store.profile, _ask)
            save_store(store)
            console.print(
                Panel(
                    "If Workday sent a verification email, run:\n"
                    "  workday-apply verify-email --gmail\n"
                    "  # or paste: workday-apply verify-email",
                    title="Next step",
                )
            )
            await page.wait_for_timeout(600_000)

    asyncio.run(_run())


@app.command("apply")
def apply(
    job_url: str = typer.Argument(..., help="Workday job requisition URL"),
    headless: bool = typer.Option(False, "--headless"),
    auto_next: bool = typer.Option(
        True,
        "--auto-next/--manual",
        help="Click Save and Continue when possible",
    ),
) -> None:
    """Fill application from saved profile; stops before final Submit for your review."""
    store = load_store()
    if not store.profile.email:
        console.print("[red]Run `workday-apply init` first.[/red]")
        raise typer.Exit(1)

    async def _run() -> None:
        async with browser_context(headless=headless) as ctx:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await run_apply_flow(page, job_url, store.profile, _ask)
            store.applied_jobs.append({"url": job_url})
            save_store(store)
            console.print(
                "[green]Filled what it could. Review every page and click Submit in the browser.[/green]"
            )
            await page.wait_for_timeout(600_000)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
