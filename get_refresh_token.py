#!/usr/bin/env python3
"""
get_refresh_token.py
====================
One-time local script to obtain a Gmail API refresh token for the dashboard.

Run this ONCE on your local machine before setting up GitHub Actions.
It will open a browser, ask you to authorize Gmail access, and print the
refresh token to add as a GitHub Secret named GMAIL_REFRESH_TOKEN.

Prerequisites:
  1. You have a Google Cloud project with Gmail API enabled.
  2. You've created OAuth 2.0 credentials of type "Desktop app".
  3. You've downloaded the credentials as credentials.json into this folder.

Install:
  pip install google-auth-oauthlib google-api-python-client

Run:
  python get_refresh_token.py
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_PATH = Path(__file__).parent / "credentials.json"

def main():
    if not CREDS_PATH.exists():
        print(f"ERROR: {CREDS_PATH} not found.")
        print("Download your OAuth 2.0 client credentials from Google Cloud Console:")
        print("  APIs & Services → Credentials → Create → OAuth client ID → Desktop app")
        print(f"Save the JSON file as: {CREDS_PATH}")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True)

    # Extract the values needed for GitHub Actions
    client_data = json.loads(CREDS_PATH.read_text())
    client_info = client_data.get("installed") or client_data.get("web") or {}

    print("\n" + "=" * 70)
    print("SUCCESS — ADD THESE AS GITHUB SECRETS:")
    print("=" * 70)
    print(f"GMAIL_CLIENT_ID      = {client_info.get('client_id', '(not found)')}")
    print(f"GMAIL_CLIENT_SECRET  = {client_info.get('client_secret', '(not found)')}")
    print(f"GMAIL_REFRESH_TOKEN  = {creds.refresh_token}")
    print("=" * 70)
    print("\nGo to:  https://github.com/DianaM242/MeteorFocus/settings/secrets/actions")
    print("Click 'New repository secret' and add each of the 3 secrets above.")
    print("\n⚠️  KEEP THESE PRIVATE — do NOT commit credentials.json to git.")

if __name__ == "__main__":
    main()
