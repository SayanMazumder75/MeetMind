"""
export_google_docs.py — Export meeting notes to a Google Doc.

Setup:
    1. pip install google-auth google-auth-oauthlib google-api-python-client
    2. Go to https://console.cloud.google.com/
    3. Create a project → Enable "Google Docs API" and "Google Drive API"
    4. Create OAuth 2.0 credentials → Download as credentials.json
    5. Set GOOGLE_CREDENTIALS_PATH=credentials.json in your .env
    6. On first run, a browser window will open for you to authorize.
"""

import logging
from pathlib import Path
from typing import Optional

from core.config import config
from core.transcriber import TranscriptChunk
from core.summarizer import MeetingSummary

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


def export_to_google_docs(
    session_id: str,
    transcript: list[TranscriptChunk],
    summary: Optional[MeetingSummary],
    meeting_title: str = "Meeting Notes",
) -> Optional[str]:
    """
    Create a Google Doc with the meeting notes.
    Returns the URL of the created document.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
    except ImportError:
        raise RuntimeError(
            "Google API libraries not installed.\n"
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    creds = _get_credentials()
    if not creds:
        return None

    docs_service  = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Create new document
    doc = docs_service.documents().create(body={"title": f"{meeting_title} — {session_id}"}).execute()
    doc_id  = doc["documentId"]
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

    # Build the content as a list of insert requests
    requests = _build_doc_requests(session_id, transcript, summary, meeting_title)

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    logger.info(f"Google Doc created: {doc_url}")
    return doc_url


def _get_credentials():
    """Load or request Google OAuth2 credentials."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    import pickle

    creds = None
    token_path = Path("google_token.pickle")

    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds_path = config.BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
            if not creds_path.exists():
                logger.error(f"Google credentials not found at {creds_path}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return creds


def _build_doc_requests(
    session_id: str,
    transcript: list[TranscriptChunk],
    summary: Optional[MeetingSummary],
    title: str,
) -> list[dict]:
    """Build Google Docs API insert requests to populate the document."""
    from datetime import datetime

    lines = []
    lines.append(f"{title}\n")
    lines.append(f"Session: {session_id}  |  Generated: {datetime.now().strftime('%d %b %Y %H:%M')}\n\n")

    if summary:
        lines.append("MEETING SUMMARY\n")
        lines.append(f"{summary.summary}\n\n")

        if summary.action_items:
            lines.append("ACTION ITEMS\n")
            for item in summary.action_items:
                lines.append(f"• {item}\n")
            lines.append("\n")

        if summary.key_points:
            lines.append("KEY POINTS\n")
            for point in summary.key_points:
                lines.append(f"• {point}\n")
            lines.append("\n")

    lines.append("FULL TRANSCRIPT\n")
    for chunk in transcript:
        lines.append(f"[{chunk.time_label}] {chunk.speaker}: {chunk.text}\n")

    full_text = "".join(lines)

    return [
        {
            "insertText": {
                "location": {"index": 1},
                "text": full_text,
            }
        }
    ]
