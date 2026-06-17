"""Smoke test for RateLimitMiddleware with Firestore-backed counters.

By default patches Firebase (no credentials needed). To test with real
Firebase, set GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_API_KEY,
FIREBASE_EMAIL and FIREBASE_PASSWORD in .env — the script fetches the
ID token automatically.

Usage (mocked Firebase):
    uv run python scripts/smoke_test_rate_limit.py

Usage (real Firebase — set vars in .env):
    GOOGLE_APPLICATION_CREDENTIALS=C:/path/serviceAccount.json
    FIREBASE_API_KEY=AIzaSy...
    FIREBASE_EMAIL=user@example.com
    FIREBASE_PASSWORD=secret
"""

import os
from typing import Any, cast
from unittest.mock import MagicMock, patch

_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
_EMAIL = os.environ.get("FIREBASE_EMAIL", "")
_PASSWORD = os.environ.get("FIREBASE_PASSWORD", "")
_GOOGLE_CREDS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
_USE_REAL_FIREBASE = bool(_API_KEY and _EMAIL and _PASSWORD and _GOOGLE_CREDS)

if not _USE_REAL_FIREBASE:
    # Patch Firebase before importing the app
    _fake_app = MagicMock(name="firebase_default_app")
    patch("firebase_admin.get_app", return_value=_fake_app).start()
    patch("firebase_admin.initialize_app", return_value=_fake_app).start()
    patch(
        "firebase_admin.auth.verify_id_token",
        return_value={"uid": "smoke-test-user", "tier": "basic"},
    ).start()

import httpx  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from src.server import app  # noqa: E402


def _fetch_firebase_token(api_key: str, email: str, password: str) -> str:
    """Sign in with email/password and return a Firebase ID token."""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    resp = httpx.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    resp.raise_for_status()
    return str(resp.json()["idToken"])


LIMIT = int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "20"))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def main() -> None:
    mode = "Real Firebase" if _USE_REAL_FIREBASE else "Mocked Firebase"
    print(f"\nMode: {mode}")
    print("Rate limit backend: Firestore")
    print(f"Tier: basic | Monthly limit: {LIMIT} req")
    print(f"Firing {LIMIT + 2} requests...\n")

    if _USE_REAL_FIREBASE:
        print("Logging in to Firebase...")
        token = _fetch_firebase_token(_API_KEY, _EMAIL, _PASSWORD)
        print("Login OK.\n")
    else:
        token = "fake-but-mocked-token"

    headers = {"Authorization": f"Bearer {token}"}

    # Use TestClient as context manager so server_lifespan runs.
    with TestClient(app, raise_server_exceptions=False) as client:
        for i in range(1, LIMIT + 3):
            resp = client.get("/mcp/", headers=headers, follow_redirects=False)
            status = resp.status_code

            if status == 429:
                retry_after = resp.headers.get("retry-after", "?")
                msg = f"  [{i:02d}] {status} BLOCKED by rate limiter (Retry-After: {retry_after}s)"
                print(colored(msg, RED))
            else:
                # Any non-429 means the request passed through the rate limiter.
                # FastMCP returns 406 for non-MCP requests — that's expected.
                print(colored(f"  [{i:02d}] {status} passed through rate limiter", GREEN))

        print("\n--- Fail-open test ---")
        print("Injecting a broken Firestore client...")

        from google.api_core import exceptions as gcp_exceptions  # noqa: E402

        import src.server as server_module  # noqa: E402

        class _BrokenDocument:
            async def set(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
                raise gcp_exceptions.GoogleAPICallError("Firestore unavailable")  # type: ignore[no-untyped-call]

        class _BrokenCollection:
            def document(self, _doc_id: str) -> _BrokenDocument:
                return _BrokenDocument()

        class _BrokenFirestore:
            def collection(self, _name: str) -> _BrokenCollection:
                return _BrokenCollection()

        original_client = server_module._firestore_client
        server_module._firestore_client = cast(Any, _BrokenFirestore())

        resp = client.get("/mcp/", headers=headers, follow_redirects=False)
        if resp.status_code != 429:
            msg = (
                f"  Fail-open OK — response: {resp.status_code} (passed through without Firestore)"
            )
            print(colored(msg, GREEN))
        else:
            msg = f"  FAILED — returned {resp.status_code} instead of passing through"
            print(colored(msg, RED))

        server_module._firestore_client = original_client

    print(colored("\nSmoke test complete.", GREEN))


if __name__ == "__main__":
    main()
