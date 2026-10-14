from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from workday_apply.store import CONFIG_DIR

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = CONFIG_DIR / "gmail-credentials.json"
TOKEN_FILE = CONFIG_DIR / "gmail-token.json"

WORKDAY_GMAIL_QUERY = (
    '(from:workday OR from:myworkday OR subject:workday OR subject:"verify" subject:account) '
    "newer_than:3d"
)


def credentials_configured() -> bool:
    return CREDENTIALS_FILE.exists()


def run_gmail_auth() -> None:
    """Interactive OAuth: opens browser, stores refresh token locally."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Download OAuth client JSON from Google Cloud Console and save as:\n  {CREDENTIALS_FILE}"
        )

    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")


def _gmail_service() -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not TOKEN_FILE.exists():
        raise FileNotFoundError("Run `workday-apply gmail-auth` first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _decode_body(payload: dict[str, Any]) -> str:
    parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and mime in ("text/plain", "text/html", ""):
            raw = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            parts.append(raw)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    return "\n".join(parts)


def fetch_recent_workday_email_bodies(max_messages: int = 8) -> list[str]:
    service = _gmail_service()
    result = (
        service.users()
        .messages()
        .list(userId="me", q=WORKDAY_GMAIL_QUERY, maxResults=max_messages)
        .execute()
    )
    bodies: list[str] = []
    for item in result.get("messages") or []:
        msg = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        payload = msg.get("payload") or {}
        bodies.append(_decode_body(payload))
    return bodies


def write_credentials_template() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    template = {
        "installed": {
            "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
            "project_id": "your-project",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "YOUR_CLIENT_SECRET",
            "redirect_uris": ["http://localhost"],
        }
    }
    path = CONFIG_DIR / "gmail-credentials.json.example"
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
