"""Smoke test for RateLimitMiddleware with a real Redis instance.

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

import asyncio
import os
from unittest.mock import MagicMock, patch

_API_KEY = os.environ.get("FIREBASE_API_KEY", "")
_EMAIL = os.environ.get("FIREBASE_EMAIL", "")
_PASSWORD = os.environ.get("FIREBASE_PASSWORD", "")
_USE_REAL_FIREBASE = bool(_API_KEY and _EMAIL and _PASSWORD and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))

if not _USE_REAL_FIREBASE:
    # Patch Firebase before importing the app
    _fake_app = MagicMock(name="firebase_default_app")
    patch("firebase_admin.get_app", return_value=_fake_app).start()
    patch("firebase_admin.initialize_app", return_value=_fake_app).start()
    patch(
        "firebase_admin.auth.verify_id_token",
        return_value={"uid": "smoke-test-user", "tier": "basic"},
    ).start()

import httpx
from starlette.testclient import TestClient  # noqa: E402

from src.server import app  # noqa: E402


def _fetch_firebase_token(api_key: str, email: str, password: str) -> str:
    """Sign in with email/password and return a Firebase ID token."""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    resp = httpx.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    resp.raise_for_status()
    return str(resp.json()["idToken"])

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
LIMIT = int(os.environ.get("RATE_LIMIT_BASIC_REQUESTS", "20"))
WINDOW = int(os.environ.get("RATE_LIMIT_BASIC_WINDOW", "60"))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def colored(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def main() -> None:
    mode = "REAL Firebase" if _USE_REAL_FIREBASE else "Firebase MOCKADO"
    print(f"\nModo: {mode}")
    print(f"Redis: {REDIS_URL}")
    print(f"Tier: basic | Limite: {LIMIT} req / {WINDOW}s")
    print(f"Disparando {LIMIT + 2} requisições...\n")

    if _USE_REAL_FIREBASE:
        print("Fazendo login no Firebase...")
        token = _fetch_firebase_token(_API_KEY, _EMAIL, _PASSWORD)
        print("Login OK.\n")
    else:
        token = "fake-but-mocked-token"

    headers = {"Authorization": f"Bearer {token}"}

    # Use TestClient as context manager so server_lifespan runs (initialises Redis pool)
    with TestClient(app, raise_server_exceptions=False) as client:
        for i in range(1, LIMIT + 3):
            resp = client.get("/mcp/", headers=headers, follow_redirects=False)
            status = resp.status_code

            if status == 429:
                retry_after = resp.headers.get("retry-after", "?")
                print(colored(f"  [{i:02d}] {status} BLOQUEADO pelo rate limiter (Retry-After: {retry_after}s)", RED))
            else:
                # Any non-429 means the request passed through the rate limiter.
                # FastMCP returns 406 for non-MCP requests — that's expected.
                print(colored(f"  [{i:02d}] {status} passou pelo rate limiter", GREEN))

        print("\n--- Verificando Redis ---")
        import redis

        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        all_keys = r.keys("rl:*")
        if not all_keys:
            print("Nenhuma chave rl:* encontrada no Redis.")
        for key in all_keys:
            count = r.zcard(key)
            entries = r.zrange(key, 0, -1, withscores=True)
            print(f"Chave Redis : {key}")
            print(f"Entradas    : {count}")
            for member, score in entries:
                print(f"  {member} -> {int(score)} ms")

        print("\n--- Teste de fail-open ---")
        print("Apontando para Redis inexistente (porta 9999)...")

        import redis.asyncio as aioredis
        import src.server as server_module

        broken_pool = aioredis.ConnectionPool.from_url(
            "redis://localhost:9999/0",
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
        )
        original_client = server_module._redis_client
        server_module._redis_client = aioredis.Redis(connection_pool=broken_pool)

        resp = client.get("/mcp/", headers=headers, follow_redirects=False)
        if resp.status_code != 429:
            print(colored(f"  Fail-open OK — resposta: {resp.status_code} (passou mesmo sem Redis)", GREEN))
        else:
            print(colored(f"  FALHOU — retornou {resp.status_code} em vez de passar", RED))

        server_module._redis_client = original_client

    print(colored("\nSmoke test concluído.", GREEN))


if __name__ == "__main__":
    main()
