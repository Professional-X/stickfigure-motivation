"""One-time YouTube OAuth setup — run this on YOUR computer, not on GitHub.

This connects your Google account to the automation so video uploads and
thumbnail uploads run on YOUR quota (10,000 units/day) with Composio kept
as the automatic fallback.

You already have the credentials file:
    client_secret_935573441346-k2msc5sgv119ipa5v5phcb8r208aease.apps.googleusercontent.com.json

=== STEP 1 — rename the file ===
Put it in this folder renamed to:   client_secret.json

=== STEP 2 — add the localhost redirect URI (one minute) ===
The client is type "web", so Google requires an explicit redirect URI:
  1. Open https://console.cloud.google.com/apis/credentials
     (project: elite-ceremony-515507-f5)
  2. Click the OAuth 2.0 Client ID (the ...k2msc5sgv119... one)
  3. Under "Authorized redirect URIs" click ADD URI and enter:
         http://localhost:8080
  4. Save.
  5. Also open APIs & Services -> OAuth consent screen and make sure the
     Google email that owns the @StickVerse channel is listed under
     "Test users" (or the app publishing status is "In production"),
     otherwise consent is blocked.

=== STEP 3 — run ===
    pip install google-auth-oauthlib
    python get_youtube_oauth.py

A browser opens -> sign in with the channel's Google account -> Allow.
The script prints the refresh token. Add it as the third GitHub secret
(YOUTUBE_REFRESH_TOKEN) at:
    https://github.com/Professional-X/stickfigure-motivation/settings/secrets/actions

YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are ALREADY stored as repo
secrets — only the refresh token is missing.

From the next scheduled run (Mon/Wed/Fri 17:00 UTC): video upload AND
thumbnail upload both use your own OAuth. If the thumbnail call ever
fails, the workflow automatically falls back to Composio.
"""
import json
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Install the dependency first:  pip install google-auth-oauthlib")
    sys.exit(1)

# youtube.upload covers both videos.insert (uploads) and thumbnails.set
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT_PORT = 8080  # must match the "Authorized redirect URI" from STEP 2


def main():
    if not os.path.exists("client_secret.json"):
        print("ERROR: client_secret.json not found in the current folder.")
        print("Rename client_secret_935573441346-...apps.googleusercontent.com.json")
        print("to client_secret.json and run this script from that folder.")
        sys.exit(1)

    with open("client_secret.json") as f:
        cfg = json.load(f)
    kind = "web" if "web" in cfg else "installed"
    client = cfg.get(kind, {})
    print(f"client_secret.json OK — type: {kind}, project: {client.get('project_id', '?')}")
    if kind == "web":
        uris = client.get("redirect_uris", [])
        want = f"http://localhost:{REDIRECT_PORT}"
        if want not in uris:
            print(f"\nNOTE: '{want}' is not in this client's registered redirect URIs ({uris or 'none'}).")
            print("Add it in Google Cloud Console -> Credentials -> this client ->")
            print("'Authorized redirect URIs', or the consent page will show redirect_uri_mismatch.")
            print("Continuing anyway — set it up if the browser shows redirect_uri_mismatch.\n")

    print(f"\nOpening browser for consent on http://localhost:{REDIRECT_PORT} ...")
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=REDIRECT_PORT)

    print("\n=== SUCCESS ===")
    print("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are already stored as")
    print("GitHub repo secrets. Add ONLY this one:")
    print()
    print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    print("Add it at: https://github.com/Professional-X/stickfigure-motivation/settings/secrets/actions")
    print("From the next scheduled run, uploads + thumbnails run on your own OAuth quota.")
    print("\nSECURITY: delete client_secret.json from this folder now. Never commit it.")


if __name__ == "__main__":
    main()
