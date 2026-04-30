"""Gmail API client for fetching AI Digest emails.

Uses OAuth (Desktop app credentials). On first run, opens a browser to consent;
the access/refresh token is cached in the configured token path.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from nextbrain import config

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass
class FetchedEmail:
    message_id: str
    subject: str
    raw_html: str


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def _service():
    """Build a Gmail API service, doing OAuth dance on first run."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Google API libraries required. Install with: "
            "pip install nextbrain[ingest]"
        ) from e

    cred_path = _expand(config.get_mail_credentials_path())
    token_path = _expand(config.get_mail_token_path())

    creds: Optional["Credentials"] = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not cred_path.exists():
                raise RuntimeError(
                    f"OAuth credentials not found at {cred_path}. Create a Desktop "
                    "OAuth client at https://console.cloud.google.com (APIs & "
                    "Services → Credentials) and save credentials.json there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_query(since_days: Optional[int] = None) -> str:
    parts: List[str] = []
    sender = config.get_mail_sender_filter()
    if sender:
        parts.append(f"from:{sender}")
    prefix = config.get_mail_subject_prefix()
    if prefix:
        parts.append(f'subject:"{prefix}"')
    if since_days is not None:
        parts.append(f"newer_than:{since_days}d")
    return " ".join(parts)


def list_digest_messages(since_days: Optional[int] = None) -> List[str]:
    """Return ALL matching message IDs, following Gmail pagination."""
    svc = _service()
    label = config.get_mail_label()
    query = _build_query(since_days=since_days)
    label_ids = [label] if label else None

    ids: List[str] = []
    page_token = None
    while True:
        kwargs = dict(userId="me", q=query, maxResults=500)
        if label_ids:
            kwargs["labelIds"] = label_ids
        if page_token:
            kwargs["pageToken"] = page_token
        resp = svc.users().messages().list(**kwargs).execute()
        ids.extend(m["id"] for m in resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return ids


def fetch_message(msg_id: str) -> FetchedEmail:
    """Fetch a message and return its decoded HTML body."""
    svc = _service()
    msg = svc.users().messages().get(userId="me", id=msg_id, format="raw").execute()
    raw_bytes = base64.urlsafe_b64decode(msg["raw"].encode("ascii"))

    import email
    from email import policy
    parsed = email.message_from_bytes(raw_bytes, policy=policy.default)
    subject = str(parsed["Subject"] or "")
    html = ""
    for part in parsed.walk():
        if part.get_content_type() == "text/html":
            html = part.get_content()
            break
    return FetchedEmail(message_id=msg_id, subject=subject, raw_html=html)


def trash_message(msg_id: str) -> None:
    """Move message to Gmail Trash (recoverable for 30 days, then auto-purged)."""
    svc = _service()
    svc.users().messages().trash(userId="me", id=msg_id).execute()


def send_email(to: str, subject: str, body: str) -> None:
    """Send an email via Gmail API.

    ``body`` is treated as Markdown: rendered to HTML if the ``markdown``
    package is available, otherwise sent as plain-text inside ``<pre>``.
    Both plain-text and HTML parts are attached (multipart/alternative).
    """
    import email.mime.multipart as _mp
    import email.mime.text as _mt

    try:
        import markdown as _md
        html_body = _md.markdown(body, extensions=["tables", "fenced_code"])
    except ImportError:
        html_body = f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{body}</pre>"

    msg = _mp.MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(_mt.MIMEText(body, "plain", "utf-8"))
    msg.attach(_mt.MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    svc = _service()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
