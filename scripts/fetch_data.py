#!/usr/bin/env python3
"""Fetch feedback emails from Gmail via IMAP and write data.json.

Env:
    GMAIL_ADDRESS        Gmail address (e.g. meteorfocus@gmail.com)
    GMAIL_APP_PASSWORD   16-char app password from myaccount.google.com/apppasswords
"""

import email
import hashlib
import html as html_lib
import imaplib
import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


KEYWORDS = {
    "wrong": [
        "תשובה שגוי", "שגויה", "לא נכון", "לא נכונה",
        "התשובה הנכונה היא", "טעות בתשובה", "סימן שגוי",
        "מסומן לא נכון", "סומן לא נכון",
    ],
    "multiple": [
        "יותר מתשובה", "שתי תשובות", "שלוש תשובות",
        "שתיהן נכונות", "שתיהן תקינות", "יכולה להיות גם",
        "מספר תשובות", "אין תשובה אחת",
    ],
    "explanation": [
        "הסבר לא ברור", "הסבר לא מובן", "ההסבר לא",
        "לא מבינה את ההסבר", "אין הסבר", "חסר הסבר",
        "ההסבר חסר", "ההסבר סותר",
    ],
    "phrasing": [
        "לא מובן", "לא ברור", "לא הבנתי", "קשה להבין",
        "ניסוח", "לא ברורה", "הניסוח", "השאלה לא ברורה",
        "לא מובנת", "מבלבל", "לא מבינה את השאלה",
    ],
}

CLASSIFY_ORDER = ("wrong", "multiple", "explanation", "phrasing")


def classify(issue_text):
    text = (issue_text or "").lower()
    if not text.strip():
        return "other"
    for cat in CLASSIFY_ORDER:
        for kw in KEYWORDS[cat]:
            if kw.lower() in text:
                return cat
    return "other"


def extract_json(text):
    """Find the first valid JSON object in free-form text."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\" and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def strip_html(content):
    content = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", content,
                     flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r"<[^>]+>", " ", content)
    return html_lib.unescape(content)


def decode_part(part):
    charset = part.get_content_charset() or "utf-8"
    try:
        return part.get_payload(decode=True).decode(charset, errors="replace")
    except Exception:
        return ""


def get_body_text(msg):
    plain, rich = None, None
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disp:
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain" and plain is None:
                plain = decode_part(part)
            elif ctype == "text/html" and rich is None:
                rich = decode_part(part)
    else:
        plain = decode_part(msg)
    return plain or "", rich or ""


def parse_message(raw):
    msg = email.message_from_bytes(raw)
    plain, rich = get_body_text(msg)

    payload = extract_json(plain)
    if payload is None and rich:
        payload = extract_json(strip_html(rich))
    if payload is None:
        return None

    date_str = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        iso_date = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        iso_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    mid = (msg.get("Message-ID") or msg.get("Message-Id") or "").strip()
    if mid:
        thread_id = hashlib.md5(mid.encode("utf-8")).hexdigest()[:16]
    else:
        thread_id = hashlib.md5(raw).hexdigest()[:16]

    if isinstance(payload, dict) and payload.get("extra_details"):
        classification = classify(payload.get("issue_text", ""))
    else:
        classification = None

    return {
        "id": thread_id,
        "date": iso_date,
        "classification": classification,
        "body": payload,
    }


def fetch_all(mail):
    status, data = mail.search(None, "ALL")
    if status != "OK":
        raise RuntimeError(f"IMAP search failed: {status}")
    return data[0].split()


def main():
    email_addr = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not email_addr or not password:
        sys.exit("Missing GMAIL_ADDRESS or GMAIL_APP_PASSWORD")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(email_addr, password)
    try:
        mail.select("INBOX", readonly=True)
        uids = fetch_all(mail)

        threads = []
        unread_count = 0
        skipped = 0

        for uid in reversed(uids):
            status, msg_data = mail.fetch(uid, "(RFC822 FLAGS)")
            if status != "OK" or not msg_data:
                skipped += 1
                continue

            flags_raw = b""
            raw = b""
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2:
                    flags_raw = part[0]
                    raw = part[1]
                    break
            if not raw:
                skipped += 1
                continue

            is_unread = b"\\Seen" not in flags_raw

            rec = parse_message(raw)
            if rec is None:
                skipped += 1
                continue

            ordered = {
                "id": rec["id"],
                "date": rec["date"],
                "isUnread": is_unread,
                "classification": rec["classification"],
                "body": rec["body"],
            }
            threads.append(ordered)
            if is_unread:
                unread_count += 1
    finally:
        try:
            mail.close()
        except Exception:
            pass
        mail.logout()

    threads.sort(key=lambda t: t["date"], reverse=True)

    out = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_count": len(threads),
        "unread_count": unread_count,
        "threads": threads,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(threads)} threads ({unread_count} unread); "
          f"skipped {skipped} non-JSON messages")


if __name__ == "__main__":
    main()
