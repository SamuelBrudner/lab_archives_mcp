"""Helper script to generate LabArchives API login URLs and resolve auth codes to user IDs.

Usage:
    python scripts/resolve_uid.py login-url
    python scripts/resolve_uid.py redeem --email user@example.com --auth-code ABC123

The script reads credentials from conf/secrets.yml using Credentials.from_file().
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from lxml import etree

# Import after sys.path adjustment to allow running as script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from labarchives_mcp.auth import Credentials  # noqa: E402

DEFAULT_REDIRECT_URI = "https://127.0.0.1/callback"


class UIDResolver:
    """Encapsulate helpers for generating login URLs and redeeming auth codes."""

    def __init__(self, credentials: Credentials) -> None:
        self._credentials = credentials

    def _signature(self, method: str, expires: str) -> str:
        message = f"{self._credentials.akid}{method}{expires}".encode()
        digest = hmac.new(self._credentials.password.encode(), message, hashlib.sha512).digest()
        return base64.b64encode(digest).decode()

    def login_url(self, *, redirect_uri: str = DEFAULT_REDIRECT_URI) -> str:
        method = "users:api_user_login"
        expires = str(int(time.time() * 1000) + 120_000)
        sig = self._signature(method, expires)
        base = str(self._credentials.region).rstrip("/")
        encoded_sig = urllib.parse.quote(sig, safe='')
        encoded_redirect = urllib.parse.quote(redirect_uri, safe='')
        return (
            f"{base}/apiv1/users/api_user_login?"
            f"akid={self._credentials.akid}&expires={expires}"
            f"&sig={encoded_sig}&redirect_uri={encoded_redirect}"
        )

    async def redeem(self, *, email: str, auth_code: str) -> str:
        method = "user_access_info"
        expires = str(int(time.time() * 1000) + 120_000)
        sig = self._signature(method, expires)
        base = str(self._credentials.region).rstrip("/")

        params = {
            "akid": self._credentials.akid,
            "expires": expires,
            "sig": sig,
        }
        form = {
            "login_or_email": email,
            "password": auth_code,
        }

        attempts: list[tuple[str, str, dict[str, str], dict[str, str] | None]] = [
            ("GET", f"{base}/api/users/user_access_info", params | form, None),
        ]

        async with httpx.AsyncClient() as client:
            last_not_found: tuple[str, str, str] | None = None
            for method, url, query, payload in attempts:
                request_kwargs: dict[str, Any] = {"params": query}
                if payload is not None:
                    request_kwargs["data"] = payload

                response = await client.request(method, url, **request_kwargs)
                if response.status_code == httpx.codes.NOT_FOUND:
                    last_not_found = (method, url, response.text)
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise RuntimeError(
                        "LabArchives user_access_info call failed "
                        f"({method} {url} -> {response.status_code}): {response.text}"
                    ) from exc

                break
            else:
                detail = (
                    f"last attempt {last_not_found[0]} {last_not_found[1]} responded 404:"
                    f" {last_not_found[2]}"
                    if last_not_found
                    else "no HTTP response recorded"
                )
                raise RuntimeError(
                    "LabArchives user_access_info returned 404 for all endpoint variants. " + detail
                )

        # Parse XML response
        try:
            root = etree.fromstring(response.content)
            uid_elem = root.find(".//id")
            if uid_elem is not None and uid_elem.text:
                return str(uid_elem.text)
            raise RuntimeError(f"user_access_info response missing <id>: {response.text[:200]}")
        except etree.XMLSyntaxError as exc:
            raise RuntimeError(f"Invalid XML response: {response.text[:200]}") from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve LabArchives uid via secrets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login-url", help="Print sign-in URL")
    login_parser.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)

    redeem_parser = subparsers.add_parser("redeem", help="Redeem auth code for uid")
    redeem_parser.add_argument("--email", required=True)
    redeem_parser.add_argument("--auth-code", required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    credentials = Credentials.from_file()
    resolver = UIDResolver(credentials)

    if args.command == "login-url":
        url = resolver.login_url(redirect_uri=args.redirect_uri)
        print(url)
        return 0

    if args.command == "redeem":
        uid = asyncio.run(resolver.redeem(email=args.email, auth_code=args.auth_code))
        print(uid)
        return 0

    raise ValueError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
