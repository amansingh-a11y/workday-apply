# Gmail OAuth (auto verification)

Workday verification links can be pulled from Gmail so you do not have to paste emails.

## 1. Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or pick an existing one).
3. **APIs & Services → Library** → enable **Gmail API**.
4. **APIs & Services → OAuth consent screen** → External → add your Gmail as a test user.
5. **Credentials → Create credentials → OAuth client ID** → type **Desktop app**.
6. Download JSON and save as:

   `~/.config/workday-apply/gmail-credentials.json`

   (Or copy from `gmail-credentials.json.example` after `workday-apply gmail-setup`.)

## 2. Authorize this tool

```bash
workday-apply gmail-auth
```

A browser opens; sign in with the Gmail inbox that receives Workday mail (`amansingh985077@gmail.com`).

Token is stored only at `~/.config/workday-apply/gmail-token.json`.

## 3. Auto-verify after signup

```bash
workday-apply verify-email --gmail
```

This searches recent Workday-related messages, extracts the confirmation URL, and opens it in the saved Chromium profile.

## Scopes

- `gmail.readonly` — list and read message bodies only; no send or delete.
