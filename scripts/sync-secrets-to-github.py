#!/usr/bin/env python3
"""
sync-secrets-to-github.py
──────────────────────────
Reads every project secret from the current Replit environment and pushes
them to the GitHub repository's encrypted Secrets store via the GitHub API.

Run this once from Replit any time you add or change a secret:
    python3 scripts/sync-secrets-to-github.py

No arguments required. The script reads GITHUB_TOKEN from the environment
and handles all encryption automatically.
"""

import sys
import os
import base64
import json
import subprocess
import urllib.request
import urllib.error

# ── Install pynacl if not already present ─────────────────────────────────────
try:
    from nacl.public import PublicKey, SealedBox
except ImportError:
    print("Installing pynacl for secret encryption...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pynacl", "-q"])
    # Re-exec so the newly installed package is visible in this process
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ── Configuration ─────────────────────────────────────────────────────────────
REPO = "choice121/property-pipeline"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

if not GITHUB_TOKEN:
    print("ERROR: GITHUB_TOKEN is not set in the environment.")
    print("       Add it as a Replit Secret and try again.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
}

# ── All secrets to sync ───────────────────────────────────────────────────────
# Keys map exactly to the names used in GitHub Actions: ${{ secrets.KEY }}
SECRETS_TO_SYNC = {
    # Supabase
    "SUPABASE_URL":               os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_ANON_KEY":          os.environ.get("SUPABASE_ANON_KEY", ""),
    "SUPABASE_SERVICE_ROLE_KEY":  os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
    "SUPABASE_ACCESS_TOKEN":      os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
    # AI
    "DEEPSEEK_API_KEY":           os.environ.get("DEEPSEEK_API_KEY", ""),
    "GEMINI_API_KEY":             os.environ.get("GEMINI_API_KEY", ""),
    # ImageKit
    "IMAGEKIT_PUBLIC_KEY":        os.environ.get("IMAGEKIT_PUBLIC_KEY", ""),
    "IMAGEKIT_PRIVATE_KEY":       os.environ.get("IMAGEKIT_PRIVATE_KEY", ""),
    "IMAGEKIT_URL_ENDPOINT":      os.environ.get("IMAGEKIT_URL_ENDPOINT", ""),
    # Mapping / Geo
    "GEOAPIFY_API_KEY":           os.environ.get("GEOAPIFY_API_KEY", ""),
    # Cloudflare
    "CLOUDFLARE_API_TOKEN":       os.environ.get("CLOUDFLARE_API_TOKEN", ""),
    # Google Apps Script
    "GOOGLE_APPS_SCRIPT_URL":     os.environ.get("GOOGLE_APPS_SCRIPT_URL", ""),
    "GOOGLE_APPS_SCRIPT_AUTH_TOKEN": os.environ.get("GOOGLE_APPS_SCRIPT_AUTH_TOKEN", ""),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def github_get(path: str) -> dict:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def github_put(path: str, data: dict) -> int:
    url = f"https://api.github.com{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code

def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    pk_bytes = base64.b64decode(public_key_b64)
    pk = PublicKey(pk_bytes)
    box = SealedBox(pk)
    encrypted = box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nSyncing secrets to GitHub repo: {REPO}")
    print("=" * 55)

    # Get the repo's public key for encrypting secrets
    try:
        key_data = github_get(f"/repos/{REPO}/actions/secrets/public-key")
    except urllib.error.HTTPError as e:
        print(f"\nERROR: Could not reach GitHub API ({e.code}).")
        print("       Check that GITHUB_TOKEN has 'repo' scope.")
        sys.exit(1)

    key_id = key_data["key_id"]
    public_key = key_data["key"]

    success, skipped, failed = [], [], []

    for name, value in SECRETS_TO_SYNC.items():
        if not value:
            skipped.append(name)
            print(f"  SKIP     {name} (not set in Replit environment)")
            continue

        encrypted = encrypt_secret(public_key, value)
        status = github_put(
            f"/repos/{REPO}/actions/secrets/{name}",
            {"encrypted_value": encrypted, "key_id": key_id},
        )

        if status in (201, 204):
            success.append(name)
            print(f"  OK       {name}")
        else:
            failed.append(name)
            print(f"  FAIL     {name} (HTTP {status})")

    print("=" * 55)
    print(f"  Synced:  {len(success)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Failed:  {len(failed)}")

    if failed:
        print(f"\nFailed secrets: {', '.join(failed)}")
        sys.exit(1)

    print("\nDone. GitHub Actions will now have access to all secrets.")
    print("You can verify at: https://github.com/choice121/property-pipeline/settings/secrets/actions\n")

if __name__ == "__main__":
    main()
