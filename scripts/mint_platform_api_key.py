#!/usr/bin/env python3
"""Mint an OmoiOS platform API key for use by the smoke test.

Flow:
    1. Try /api/v1/auth/login with (email, password). If 401, /register first.
    2. If --org-id unset, GET /api/v1/organizations and pick the first owned/member org
       (creating one if none exist and --create-org is passed).
    3. POST /api/v1/auth/api-keys with scopes=["*"] and the chosen org_id.
    4. Write OMOIOS_PLATFORM_API_KEY=<key> into backend/.env (idempotent replace).
    5. Print the key once (not retrievable later — only the prefix is stored).

The email/password args can also come from env vars OMOIOS_TEST_EMAIL /
OMOIOS_TEST_PASSWORD. Useful for unattended smoke-test runs.

Usage:
    uv run python scripts/mint_platform_api_key.py \\
        --email kevin@autoworkz.org --password '<pw>'

    # Or via env vars:
    OMOIOS_TEST_EMAIL=kevin@autoworkz.org OMOIOS_TEST_PASSWORD='<pw>' \\
        uv run python scripts/mint_platform_api_key.py

    # Pre-existing org:
    uv run python scripts/mint_platform_api_key.py --org-id 2f3d... \\
        --name "smoke-test-2026-04-24"
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import httpx


REPO = Path(__file__).resolve().parent.parent
BACKEND_ENV = REPO / "backend" / ".env"


def post(client: httpx.Client, path: str, json: dict, token: Optional[str] = None) -> httpx.Response:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(path, json=json, headers=headers)


def get(client: httpx.Client, path: str, token: str) -> httpx.Response:
    return client.get(path, headers={"Authorization": f"Bearer {token}"})


def login(client: httpx.Client, email: str, password: str) -> Optional[str]:
    """Return access_token on success, None on 401."""
    r = post(client, "/api/v1/auth/login", {"email": email, "password": password})
    if r.status_code == 200:
        return r.json().get("access_token")
    if r.status_code in (401, 404):
        return None
    sys.exit(f"login failed: {r.status_code} {r.text[:400]}")


def register(client: httpx.Client, email: str, password: str, full_name: str) -> None:
    r = post(client, "/api/v1/auth/register", {
        "email": email, "password": password, "full_name": full_name,
    })
    if r.status_code not in (200, 201):
        sys.exit(f"register failed: {r.status_code} {r.text[:400]}")
    print(f"  ✔ registered {email}")


def pick_org(client: httpx.Client, token: str, create_if_missing: bool) -> Optional[str]:
    r = get(client, "/api/v1/organizations", token)
    if r.status_code != 200:
        print(f"  ⚠ list organizations returned {r.status_code}; keying to user only")
        return None
    orgs = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if orgs:
        print(f"  ✔ found {len(orgs)} org(s); using '{orgs[0].get('name')}' ({orgs[0].get('id')})")
        return orgs[0].get("id")
    if not create_if_missing:
        print("  ⚠ no organizations owned; pass --create-org to auto-create")
        return None
    r = post(client, "/api/v1/organizations",
             {"name": "smoke-test-org", "slug": "smoke-test"}, token=token)
    if r.status_code not in (200, 201):
        print(f"  ⚠ create org failed: {r.status_code} {r.text[:200]}; falling back to user-scoped")
        return None
    org_id = r.json().get("id")
    print(f"  ✔ created org smoke-test-org ({org_id})")
    return org_id


def mint_key(client: httpx.Client, token: str, name: str, org_id: Optional[str]) -> str:
    body: dict[str, Any] = {"name": name, "scopes": ["*"]}
    if org_id:
        body["organization_id"] = org_id
    r = post(client, "/api/v1/auth/api-keys", body, token=token)
    if r.status_code not in (200, 201):
        sys.exit(f"mint api-key failed: {r.status_code} {r.text[:400]}")
    full_key = r.json().get("key")
    if not full_key or not full_key.startswith("sk_live_"):
        sys.exit(f"unexpected api-key response shape: {r.text[:300]}")
    return full_key


def write_to_env(key: str) -> None:
    """Idempotently add/replace OMOIOS_PLATFORM_API_KEY in backend/.env."""
    if not BACKEND_ENV.exists():
        sys.exit(f"{BACKEND_ENV} does not exist; refusing to create one")
    content = BACKEND_ENV.read_text()
    new_line = f"OMOIOS_PLATFORM_API_KEY={key}"
    if re.search(r"^OMOIOS_PLATFORM_API_KEY=", content, re.MULTILINE):
        content = re.sub(r"^OMOIOS_PLATFORM_API_KEY=.*$", new_line, content, flags=re.MULTILINE)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n# Platform API key for smoke-test (minted via mint_platform_api_key.py)\n"
        content += f"{new_line}\n"
    BACKEND_ENV.write_text(content)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--api-base-url",
                   default=os.environ.get("OMOIOS_API_BASE_URL", "http://localhost:18000"))
    p.add_argument("--email", default=os.environ.get("OMOIOS_TEST_EMAIL"))
    p.add_argument("--password", default=os.environ.get("OMOIOS_TEST_PASSWORD"))
    p.add_argument("--full-name", default="OmoiOS Smoke Test",
                   help="display name used if the user needs to be registered")
    p.add_argument("--org-id", help="use this org; skips org lookup")
    p.add_argument("--create-org", action="store_true",
                   help="create an org if the user has none")
    p.add_argument("--name", default="smoke-test",
                   help="display name for the API key (default: smoke-test)")
    p.add_argument("--no-write-env", action="store_true",
                   help="print the key only; don't touch backend/.env")
    args = p.parse_args()

    if not args.email:
        args.email = input("email: ").strip()
    if not args.password:
        args.password = getpass.getpass("password: ")

    print(f"▸ API: {args.api_base_url}")
    print(f"▸ user: {args.email}")

    with httpx.Client(base_url=args.api_base_url, timeout=30.0) as client:
        # Step 1: login, register if needed.
        token = login(client, args.email, args.password)
        if not token:
            print(f"  ⚠ login failed; attempting register")
            register(client, args.email, args.password, args.full_name)
            token = login(client, args.email, args.password)
            if not token:
                sys.exit("register succeeded but login still failed — "
                         "likely email verification is required. Either set "
                         "`is_email_verified=true` in the users table directly, "
                         "or configure SMTP and click the verification link.")
        print(f"  ✔ authenticated")

        # Step 2: org.
        org_id = args.org_id or pick_org(client, token, args.create_org)

        # Step 3: mint.
        key = mint_key(client, token, args.name, org_id)

    # Step 4: write.
    if not args.no_write_env:
        write_to_env(key)
        print(f"  ✔ wrote OMOIOS_PLATFORM_API_KEY to {BACKEND_ENV}")

    print()
    print("─" * 72)
    print(f"OMOIOS_PLATFORM_API_KEY={key}")
    print("─" * 72)
    print()
    print("next: source backend/.env into your shell and run the smoke test:")
    print("  set -a; source backend/.env; set +a")
    print("  uv run python scripts/smoke_agent_platform.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
