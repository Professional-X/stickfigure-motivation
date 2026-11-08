"""One-time YouTube OAuth setup. Run locally to obtain a refresh token.

Run:
    pip install google-auth-oauthlib
    python get_youtube_oauth.py

This opens a browser, you sign in with the Google account that owns your
YouTube channel, authorize the app, and the script prints a refresh token.
Add that token (+ your client ID + secret) as GitHub Secrets to enable
automatic YouTube uploads.
"""
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Install dependency first: pip install google-auth-oauthlib")
    sys.exit(1)


# YouTube upload scope
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    print("""
=== YouTube OAuth Setup ===

BEFORE running this script, you need to create a Google OAuth Client ID:

1. Go to https://console.cloud.google.com/
2. Create a project (any name)
3. Enable the YouTube Data API v3:
   APIs & Services → Library → search "YouTube Data API v3" → Enable
4. Configure OAuth consent screen:
   APIs & Services → OAuth consent screen → External → Create
   Fill in app name (e.g. "stickfigure-motivation"), your email, save.
   Add yourself as a Test User (under "Test users" → Add your Google email)
5. Create OAuth Client ID:
   APIs & Services → Credentials → Create Credentials → OAuth client ID
   Application type: Desktop app
   Name: anything (e.g. "stickfigure-bot")
   Click Create, then download the JSON file
6. Save the JSON file as 'client_secret.json' in this directory

Press Enter when you've done the above...
""")
    input()

    if not os.path.exists("client_secret.json"):
        print("ERROR: client_secret.json not found in current directory.")
        print("       Download it from Google Cloud Console → Credentials.")
        sys.exit(1)

    print("\nOpening browser for OAuth consent...")
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n=== SUCCESS ===")
    print("Add these 3 values as GitHub Secrets in your repo:")
    print(f"  https://github.com/Professional-X/stickfigure-motivation/settings/secrets/actions")
    print()
    print(f"YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("After adding these, the next workflow run will auto-upload to YouTube.")
    print()
    print("SECURITY: delete client_secret.json from this directory now.")
    print("          Don't commit it. It's already in .gitignore but double-check.")


if __name__ == "__main__":
    main()
