#!/usr/bin/env python3
"""
update_data.py
==============
Fetches "Issue Reported" emails from Gmail and writes data.json for the dashboard.

Reads these env vars (set as GitHub Secrets in prod):
    GMAIL_CLIENT_ID       - OAuth client id
    GMAIL_CLIENT_SECRET   - OAuth client secret
    GMAIL_REFRESH_TOKEN   - Long-lived refresh token (obtained once via get_refresh_token.py)

Optional env vars:
    DAYS_BACK             - Number of days to fetch. Default: 30
    OUTPUT_PATH           - Where to write data.json. Default: ./data.json
    PUSH_TO_GIT           - If "1", auto-commit+push data.json to git after updating.
                            Useful when running locally inside a git repo. Default: off.
                            (NOT needed in GitHub Actions — the workflow does the push.)

Usage:
    python update_data.py

Usage with auto-push (local):
    PUSH_TO_GIT=1 python update_data.py
"""
import os
import json
import sys
import re
import base64
import datetime
import subprocess
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---------- Config ----------
DAYS_BACK = int(os.environ.get("DAYS_BACK", "30"))
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "./data.json")
QUERY = f'subject:"Issue Reported" newer_than:{DAYS_BACK}d'
MAX_MESSAGES = 2000  # safety cap

# ---------- Classification (keyword heuristics) ----------
# Order matters: first match wins. Uses substring matches on the Hebrew issue_text.
CLASSIFICATION_RULES = [
    ("wrong", [
        "תשובה שגוי", "שגויה", "לא נכון", "לא נכונה",
        "התשובה הנכונה היא", "התשובה צריכה", "טעות בתשובה",
        "סימן שגוי", "סימנה שגוי", "מסומן לא נכון", "סומן לא נכון",
    ]),
    ("multiple", [
        "יותר מתשובה", "שתי תשובות", "שלוש תשובות",
        "גם X וגם", "שתיהן נכונות", "שתיהן תקינות", "יכולה להיות גם",
        "שלוש נכונות", "מספר תשובות", "אין תשובה אחת",
    ]),
    ("explanation", [
        "הסבר לא ברור", "הסבר לא מובן", "ההסבר לא", "לא מבינה את ההסבר",
        "אין הסבר", "חסר הסבר", "ההסבר חסר", "הסבר חסר",
        "הסבר לא תואם", "ההסבר סותר",
    ]),
    ("phrasing", [
        "לא מובן", "לא ברור", "לא הבנתי", "קשה להבין",
        "ניסוח", "לא ברורה", "הניסוח", "השאלה לא ברורה",
        "לא מובנת", "מבלבל", "לא מבינה את השאלה",
    ]),
]

def classify_issue(text: str) -> str:
    if not text or not text.strip():
        return "empty"
    lower = text.lower()
    for label, keywords in CLASSIFICATION_RULES:
        for kw in keywords:
            if kw in lower or kw in text:
                return label
    return "other"

# ---------- Gmail client ----------
def build_gmail_service():
    client_id = os.environ["GMAIL_CLIENT_ID"]
    client_secret = os.environ["GMAIL_CLIENT_SECRET"]
    refresh_token = os.environ["GMAIL_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

# ---------- Fetching ----------
def list_message_ids(service, query):
    """Paginate through all message IDs matching the query."""
    ids = []
    page_token = None
    while True:
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=500)
            .execute()
        )
        msgs = resp.get("messages", [])
        ids.extend([m["id"] for m in msgs])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        if len(ids) >= MAX_MESSAGES:
            print(f"WARN: hit MAX_MESSAGES cap ({MAX_MESSAGES})")
            break
    return ids

def fetch_message(service, msg_id):
    """Fetch a single message, full content."""
    return (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute()
    )

def extract_plaintext_body(payload):
    """Walk MIME tree, extract first text/plain body as decoded string."""
    def decode_part(p):
        data = p.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
        return None

    if payload.get("mimeType", "").startswith("text/plain"):
        return decode_part(payload)

    for part in payload.get("parts", []) or []:
        if part.get("mimeType", "").startswith("text/plain"):
            text = decode_part(part)
            if text:
                return text
        # Recurse into multipart
        if part.get("parts"):
            text = extract_plaintext_body(part)
            if text:
                return text
    # Fallback: any body data
    return decode_part(payload)

def extract_date_iso(msg):
    """Return ISO timestamp from internalDate (ms since epoch)."""
    ts = int(msg.get("internalDate", "0")) / 1000
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat().replace("+00:00", "Z")

# ---------- Main ----------
def main():
    print(f"[{datetime.datetime.utcnow().isoformat()}Z] Starting. Query: {QUERY}")

    try:
        service = build_gmail_service()
    except KeyError as e:
        print(f"ERROR: missing env var {e}. Need GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.")
        sys.exit(1)

    try:
        ids = list_message_ids(service, QUERY)
    except HttpError as e:
        print(f"ERROR: Gmail search failed: {e}")
        sys.exit(1)

    print(f"Found {len(ids)} messages matching query.")
    if not ids:
        write_output({"fetched_at": iso_now(), "threads": []})
        return

    threads = []
    skipped_parse = 0
    skipped_fetch = 0

    for idx, msg_id in enumerate(ids, 1):
        try:
            msg = fetch_message(service, msg_id)
        except HttpError as e:
            print(f"WARN: failed to fetch {msg_id}: {e}")
            skipped_fetch += 1
            continue

        label_ids = msg.get("labelIds", []) or []
        is_unread = "UNREAD" in label_ids

        plaintext = extract_plaintext_body(msg.get("payload", {}))
        if not plaintext:
            skipped_parse += 1
            continue

        # Strip any HTML remnants and whitespace
        plaintext = plaintext.strip()

        try:
            body = json.loads(plaintext)
        except json.JSONDecodeError:
            # Some emails may have leading/trailing junk — try extracting JSON block
            match = re.search(r"\{[\s\S]*\}", plaintext)
            if not match:
                skipped_parse += 1
                continue
            try:
                body = json.loads(match.group(0))
            except json.JSONDecodeError:
                skipped_parse += 1
                continue

        date_iso = extract_date_iso(msg)
        issue_text = body.get("issue_text", "") if isinstance(body, dict) else ""
        has_extra = isinstance(body, dict) and bool(body.get("extra_details"))

        classification = classify_issue(issue_text) if has_extra else None

        threads.append({
            "id": msg.get("threadId") or msg_id,
            "messageId": msg_id,
            "date": date_iso,
            "isUnread": is_unread,
            "classification": classification,
            "body": body,
        })

        if idx % 20 == 0:
            print(f"  Processed {idx}/{len(ids)}...")

    # Sort newest-first
    threads.sort(key=lambda t: t["date"], reverse=True)

    out = {
        "fetched_at": iso_now(),
        "query": QUERY,
        "days_back": DAYS_BACK,
        "total": len(threads),
        "threads": threads,
    }

    print(
        f"Done. Wrote {len(threads)} threads. "
        f"Skipped {skipped_parse} (parse), {skipped_fetch} (fetch)."
    )
    write_output(out)

def iso_now():
    return datetime.datetime.utcnow().isoformat() + "Z"

def write_output(data):
    path = Path(OUTPUT_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    size_kb = path.stat().st_size / 1024
    print(f"→ Wrote {path} ({size_kb:.1f} KB)")

    if os.environ.get("PUSH_TO_GIT", "0") == "1":
        git_commit_and_push(path)

def git_commit_and_push(path):
    """Commit data.json and push to the current branch's remote.
    Silently skips if not in a git repo or if there are no changes.
    """
    try:
        # Confirm we're inside a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print("SKIP push: not inside a git repo.")
            return

        # Stage the file
        subprocess.run(["git", "add", str(path)], check=True)

        # Is there anything to commit?
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff.returncode == 0:
            print("No changes to data.json — nothing to commit.")
            return

        # Commit
        msg = f"data: auto-update {iso_now()}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        print(f"✓ Committed: {msg}")

        # Push
        push = subprocess.run(["git", "push"], capture_output=True, text=True)
        if push.returncode == 0:
            print("✓ Pushed to remote")
        else:
            print(f"WARN: push failed — {push.stderr.strip()}")
            print("      (the commit is still local. run 'git push' manually.)")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git command failed: {e}")
    except FileNotFoundError:
        print("SKIP push: 'git' command not found in PATH.")

if __name__ == "__main__":
    main()
