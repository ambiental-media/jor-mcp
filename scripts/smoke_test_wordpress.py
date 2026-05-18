"""Smoke test for the WordPress service layer against a real WP REST API.

Initialises a real httpx.AsyncClient (bypassing the ASGI lifespan) and calls
fetch_full_article directly — no mocks, no server, no auth middleware.

Usage:
    # Test with the default WORDPRESS_API_URL (ambiental.media):
    uv run python scripts/smoke_test_wordpress.py

    # Test against a different WordPress installation:
    WORDPRESS_API_URL=https://sua-redacao.com.br/wp-json \
        uv run python scripts/smoke_test_wordpress.py

    # Optionally override the article to fetch:
    WP_SMOKE_IDENTIFIER=1234 uv run python scripts/smoke_test_wordpress.py
    WP_SMOKE_IDENTIFIER=algum-slug uv run python scripts/smoke_test_wordpress.py
    WP_SMOKE_IDENTIFIER=https://ambiental.media/alguma-materia/ \
        uv run python scripts/smoke_test_wordpress.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src` is importable when the
# script is executed directly via `uv run python scripts/...`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

# ---------------------------------------------------------------------------
# Inject a real HTTP client before importing the service
# ---------------------------------------------------------------------------
import src.http_client as _http_client_mod

_http_client_mod._http_client = httpx.AsyncClient(timeout=15.0)

from src.config import WP_API_BASE_URL  # noqa: E402
from src.services.wordpress import (  # noqa: E402
    WordPressPostNotFoundError,
    _extract_slug,
    fetch_full_article,
)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Default: fetch the latest post (slug query returns most recent when no slug given).
# Override via WP_SMOKE_IDENTIFIER env var.
_IDENTIFIER = os.environ.get("WP_SMOKE_IDENTIFIER", "")


async def _discover_identifier() -> str:
    """Auto-discover a real post identifier from the /wp/v2/posts endpoint."""
    client = _http_client_mod._http_client
    assert client is not None
    url = f"{WP_API_BASE_URL}/wp/v2/posts"
    resp = await client.get(url, params={"_fields": "id,link", "per_page": "1"})
    resp.raise_for_status()
    posts = resp.json()
    if not posts:
        print(f"{RED}✗ No posts found at {url}{RESET}")
        sys.exit(1)
    post = posts[0]
    print(f"{YELLOW}  Auto-discovered post: id={post['id']}  link={post['link']}{RESET}")
    return str(post["id"])


async def run() -> None:
    identifier = _IDENTIFIER

    print(f"\n{CYAN}WordPress Smoke Test{RESET}")
    print(f"  API base : {WP_API_BASE_URL}")

    if not identifier:
        print("  Identifier: not set — auto-discovering latest post...")
        identifier = await _discover_identifier()

    value, is_id = _extract_slug(identifier)
    kind = "numeric ID" if is_id else "slug/URL"
    print(f"  Identifier: {identifier!r}  →  resolved as {kind} ({value!r})\n")

    # -----------------------------------------------------------------------
    # Test 1: fetch and clean the article
    # -----------------------------------------------------------------------
    print(f"[1/2] Fetching article via fetch_full_article({identifier!r})...")
    try:
        result = await fetch_full_article(identifier)
    except WordPressPostNotFoundError as exc:
        print(f"{RED}✗ Post not found: {exc}{RESET}")
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        print(f"{RED}✗ HTTP error {exc.response.status_code}: {exc}{RESET}")
        sys.exit(1)

    title = result["title"]
    date = result["date"]
    link = result["link"]
    content = result["content"]

    print(f"{GREEN}✓ Article fetched successfully{RESET}")
    print(f"  Title   : {title}")
    print(f"  Date    : {date}")
    print(f"  Link    : {link}")
    print(f"  Content : {len(content)} chars")
    print("\n--- First 500 chars of cleaned content ---")
    print(content[:500])
    print("---\n")

    # -----------------------------------------------------------------------
    # Test 2: verify cleaning — no HTML tags or shortcodes remain
    # -----------------------------------------------------------------------
    print("[2/2] Verifying content cleanliness...")
    issues: list[str] = []

    import re

    if re.search(r"<[a-zA-Z/]", content):
        issues.append("HTML tags still present")
    if re.search(r"\[/?[a-zA-Z_\-]+", content):
        issues.append("WordPress shortcodes still present")
    if "&amp;" in content or "&lt;" in content or "&gt;" in content:
        issues.append("Unescaped HTML entities still present")

    if issues:
        for issue in issues:
            print(f"{RED}✗ {issue}{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}✓ Content is clean: no HTML, no shortcodes, no entities{RESET}")

    print(f"\n{GREEN}All smoke tests passed.{RESET}\n")

    if _http_client_mod._http_client is not None:
        await _http_client_mod._http_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
