"""One-shot setup helper: pushes secrets to your GitHub repo via the API.

Usage:
    1. cp .env.example .env   # then fill in your real keys
    2. python setup_secrets.py owner/repo-name
       e.g. python setup_secrets.py johndoe/stickfigure-motivation

This script:
- Reads credentials from local .env (NEVER commits them)
- Fetches your repo's public key from GitHub
- Encrypts each secret with libsodium (PyNaCl)
- Pushes them to GitHub as repo secrets
- Verifies they're stored

After this runs successfully:
    ROTATE YOUR GITHUB PAT AND COMPOSIO API KEY IMMEDIATELY.
    Both were exposed in plaintext during setup. Rotating them is mandatory.
"""
import os
import sys
import json
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

SECRETS_TO_PUSH = {
    "NVIDIA_API_KEY":     os.environ.get("NVIDIA_API_KEY", ""),
    "COMPOSIO_API_KEY":   os.environ.get("COMPOSIO_API_KEY", ""),
    "COMPOSIO_ENTITY_ID": os.environ.get("COMPOSIO_ENTITY_ID", ""),
}


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}")
    sys.exit(code)


def get_repo_public_key(token: str, repo: str) -> tuple[str, str]:
    """Returns (key_id, public_key_b64) from GitHub."""
    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if r.status_code == 404:
        die(f"repo '{repo}' not found, or PAT lacks 'repo' scope. "
            f"Make sure the PAT has 'repo' and 'workflow' permissions.")
    if r.status_code == 401:
        die("PAT is invalid or expired.")
    r.raise_for_status()
    data = r.json()
    return data["key_id"], data["key"]


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt a secret with the repo's public key (libsodium sealed box)."""
    from nacl import public, encoding
    public_key = public.PublicKey(
        public_key_b64.encode("utf-8"),
        encoding.Base64Encoder(),
    )
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def push_secret(token: str, repo: str, name: str, encrypted_value: str, key_id: str):
    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "encrypted_value": encrypted_value,
            "key_id": key_id,
        },
        timeout=30,
    )
    if r.status_code not in (201, 204):
        die(f"failed to push secret '{name}': HTTP {r.status_code} {r.text}")


def list_secrets(token: str, repo: str) -> list[str]:
    r = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    r.raise_for_status()
    return [s["name"] for s in r.json().get("secrets", [])]


def main():
    if len(sys.argv) < 2:
        die("usage: python setup_secrets.py owner/repo-name\n"
            "example: python setup_secrets.py johndoe/stickfigure-motivation")

    repo = sys.argv[1].strip().strip("/")
    if "/" not in repo:
        die(f"repo must be in form owner/repo, got: {repo}")

    token = os.environ.get("GH_PAT", "").strip()
    if not token:
        die("GH_PAT env var not set. Add it to .env:\n  GH_PAT=ghp_xxxxxxxx")

    # Validate that all secrets have values
    missing = [name for name, val in SECRETS_TO_PUSH.items() if not val]
    if missing:
        die(f"these secrets are missing from .env: {', '.join(missing)}")

    print(f"\n[setup] target repo: {repo}")
    print(f"[setup] secrets to push: {', '.join(SECRETS_TO_PUSH.keys())}")

    print("[setup] fetching repo public key...")
    key_id, public_key_b64 = get_repo_public_key(token, repo)
    print(f"[setup] got public key (id={key_id})")

    for name, value in SECRETS_TO_PUSH.items():
        print(f"[setup] encrypting + pushing {name}...")
        encrypted = encrypt_secret(public_key_b64, value)
        push_secret(token, repo, name, encrypted, key_id)
        print(f"        ✓ pushed")

    print("\n[setup] verifying...")
    stored = list_secrets(token, repo)
    for name in SECRETS_TO_PUSH:
        marker = "✓" if name in stored else "✗ MISSING"
        print(f"        {marker} {name}")

    print("\n[setup] === DONE ===")
    print("\nNEXT STEPS:")
    print("  1. Verify workflow trigger manually:")
    print(f"     https://github.com/{repo}/actions/workflows/publish.yml")
    print("  2. Click 'Run workflow' to test the pipeline.")
    print("  3. ★ ROTATE YOUR GITHUB PAT NOW:")
    print("     https://github.com/settings/tokens")
    print("  4. ★ ROTATE YOUR COMPOSIO API KEY:")
    print("     https://app.composio.dev/api-keys")
    print("  5. Update the rotated Composio key in GitHub Secrets:")
    print(f"     https://github.com/{repo}/settings/secrets/actions")
    print("")
    print("  Both keys were exposed in plaintext during this session.")
    print("  Do NOT skip rotation, even if everything works.")


if __name__ == "__main__":
    main()
