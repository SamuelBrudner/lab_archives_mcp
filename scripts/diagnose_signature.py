"""Diagnostic script to test different signature variations for LabArchives API.

Usage:
    python scripts/diagnose_signature.py --email user@example.com --auth-code <token>
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from labarchives_mcp.auth import Credentials  # noqa: E402


async def test_signature_variant(
    credentials: Credentials,
    email: str,
    auth_code: str,
    method_string: str,
    description: str,
) -> tuple[str, bool, str]:
    """Test a single signature variant and return (description, success, detail)."""
    expires = str(int(time.time() * 1000) + 120_000)
    message = f"{credentials.akid}{method_string}{expires}".encode()
    digest = hmac.new(credentials.password.encode(), message, hashlib.sha512).digest()
    sig = base64.b64encode(digest).decode()

    params = {
        "akid": credentials.akid,
        "expires": expires,
        "sig": sig,
        "login_or_email": email,
        "password": auth_code,
    }

    url = f"{str(credentials.region).rstrip('/')}/api/users/user_access_info"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                payload = response.json()
                if payload.get("id"):
                    return (description, True, f"SUCCESS - UID: {payload['id']}")
                return (description, False, f"200 but missing UID: {response.text[:200]}")
            else:
                return (
                    description,
                    False,
                    f"HTTP {response.status_code}: {response.text[:200]}",
                )
        except Exception as exc:
            return (description, False, f"Exception: {exc}")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose LabArchives signature issues")
    parser.add_argument("--email", required=True)
    parser.add_argument("--auth-code", required=True)
    args = parser.parse_args(argv or sys.argv[1:])

    credentials = Credentials.from_file()

    print(f"Testing signature variants with AKID: {credentials.akid}\n")

    variants = [
        ("users:user_access_info", "Method with colon (current)"),
        ("user_access_info", "Method without class prefix"),
        ("users/user_access_info", "Method with slash"),
        ("usersuser_access_info", "Method concatenated"),
    ]

    results: list[tuple[str, bool, str]] = []
    for method_str, desc in variants:
        result = await test_signature_variant(
            credentials, args.email, args.auth_code, method_str, desc
        )
        results.append(result)
        print(f"[{'✓' if result[1] else '✗'}] {result[0]}")
        print(f"    {result[2]}\n")

    successful = [r for r in results if r[1]]
    if successful:
        print(f"\n🎉 Found working variant: {successful[0][0]}")
        print(f"   {successful[0][2]}")
        return 0
    else:
        print("\n❌ No variant succeeded. Next steps:")
        print("   1. Verify LABARCHIVES_PASSWORD in conf/secrets.yml")
        print("   2. Contact LabArchives support with these results")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
