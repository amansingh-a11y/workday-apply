# Workday Apply Assistant

Local CLI that helps you apply on **Workday** (`*.myworkdayjobs.com`) job sites:

- **Sign up / sign in** with your email (browser session is saved for the next application)
- **Verify email** via **Gmail OAuth** (`--gmail`) or by pasting the message Workday sends
- **Import your resume** (`.tex` or `.pdf`) into a **persistent profile**
- **Re-use** name, phone, experience, education, and custom answers on the next job
- **Ask you** for one-off questions (EEO, sponsorship, etc.) and **remember** the answers

Data is stored only on your machine: `~/.config/workday-apply/` (override with `WORKDAY_APPLY_HOME`).

> Workday forms differ per employer. This tool automates the boring fields and navigation; you still review and submit, and handle CAPTCHAs manually.

## Setup

```bash
cd workday-apply
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## First-time profile

```bash
workday-apply init --resume ~/work/resume/resume.tex
# PDF: workday-apply init --resume ~/path/to/resume.pdf
```

Default email: `amansingh985077@gmail.com` (override with `--email`).

## Gmail auto-verify (optional)

```bash
workday-apply gmail-setup    # prints where to put OAuth JSON
workday-apply gmail-auth     # one-time browser consent
workday-apply verify-email --gmail
```

Full steps: [docs/gmail-setup.md](docs/gmail-setup.md).

## Create account on a company's Workday site

```bash
workday-apply signup "https://company.wd1.myworkdayjobs.com/en-US/External/job/..."
```

Complete any CAPTCHA in the browser. When Workday emails you:

```bash
workday-apply verify-email --gmail
# or paste: workday-apply verify-email
```

## Apply to a job

```bash
workday-apply apply "https://company.wd1.myworkdayjobs.com/en-US/External/job/..."
```

The browser stays open so you can fix dropdowns Workday renders oddly, then **Submit**.

## Profile maintenance

```bash
workday-apply profile
workday-apply profile --set city=Bengaluru
workday-apply profile --set requires_sponsorship=No
workday-apply import-resume ~/work/resume/resume.tex
workday-apply set-password
```

Custom question text from a previous application is stored under `custom_answers` in `profile.json`.

## Security

- Password, Gmail tokens, and profile JSON are **local**; never commit `~/.config/workday-apply`.
- Use a **unique password** for Workday (not your Gmail password).
- Gmail scope is **read-only** (`gmail.readonly`).

## Limitations

- PDF parsing is heuristic (LaTeX gives the best structure).
- Heavy React dropdowns (country, school name) may need a manual click.
- Does not bypass bot detection; use honestly and review each submission.
