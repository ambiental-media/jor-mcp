"""OAuth 2.1 proxy API router.

RESTful endpoints backing the native MCP OAuth 2.1 flow (Dynamic Client
Registration, PKCE challenge storage, token exchange and consent approval).
These routes are mounted under the ``/api/oauth`` prefix by :mod:`src.server`
(plus the root ``/.well-known`` discovery routes) and are intentionally exempt
from Firebase authentication: they are the very mechanism through which clients
obtain Firebase tokens, so requiring a token to reach them would be circular.
"""

import asyncio
import base64
import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

import firebase_admin.exceptions
import httpx
from firebase_admin import auth
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient as FirestoreAsyncClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.config import (
    ALLOWED_USERS_COLLECTION,
    FIREBASE_WEB_API_KEY,
    IDENTITY_TOOLKIT_BASE_URL,
    OAUTH_CLIENTS_COLLECTION,
    OAUTH_CODE_TTL_SECONDS,
    OAUTH_CODES_COLLECTION,
    OAUTH_PORTAL_BASE_URL,
    OAUTH_SERVER_BASE_URL,
    SECURE_TOKEN_BASE_URL,
)
from src.http_client import get_http_client

logger = logging.getLogger(__name__)

OAUTH_PATH_PREFIX = "/api/oauth"
"""Mount prefix for the OAuth proxy router (single source of truth)."""

WELL_KNOWN_PREFIX = "/.well-known"
"""Root prefix for the OAuth discovery metadata routes."""


def is_oauth_path(path: str) -> bool:
    """Return True if *path* targets an auth-exempt OAuth route.

    Covers both the proxy router (``/api/oauth``) and the discovery metadata
    (``/.well-known``). Used by the authentication middleware to bypass Firebase
    token validation: these routes are the mechanism through which clients obtain
    Firebase tokens, so requiring one to reach them would be circular.

    Args:
        path: The request path taken from the ASGI scope.

    Returns:
        True when the path is part of the OAuth proxy or discovery surface.
    """
    return (
        path == OAUTH_PATH_PREFIX
        or path.startswith(f"{OAUTH_PATH_PREFIX}/")
        or path.startswith(f"{WELL_KNOWN_PREFIX}/")
    )


class ClientRegistrationRequest(BaseModel):
    """Validated subset of an RFC 7591 Dynamic Client Registration payload.

    Unknown fields sent by MCP clients are ignored rather than rejected.
    """

    model_config = ConfigDict(extra="ignore")

    redirect_uris: list[str] = Field(min_length=1)
    client_name: str | None = None
    token_endpoint_auth_method: str | None = None
    grant_types: list[str] | None = None
    response_types: list[str] | None = None
    scope: str | None = None

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, uris: list[str]) -> list[str]:
        """Verify redirect URIs are absolute and valid HTTP/HTTPS URLs."""
        for uri in uris:
            parts = urlsplit(uri)
            if not parts.scheme or parts.scheme not in ("http", "https"):
                raise ValueError("redirect_uris must be absolute HTTP or HTTPS URLs")
            if not parts.netloc:
                raise ValueError("redirect_uris must include a host")
        return uris


class ApproveRequest(BaseModel):
    """Validated consent-approval payload sent by the Next.js portal."""

    model_config = ConfigDict(extra="ignore")

    client_id: str = Field(min_length=1)
    code_challenge: str = Field(min_length=1)
    code_challenge_method: str = "S256"
    redirect_uri: str | None = None
    state: str | None = None


class TokenRequest(BaseModel):
    """Validated token-exchange payload (application/x-www-form-urlencoded)."""

    model_config = ConfigDict(extra="ignore")

    grant_type: str
    client_id: str | None = None
    code: str | None = None
    code_verifier: str | None = None
    redirect_uri: str | None = None
    refresh_token: str | None = None


def _error_response(error: str, description: str, status_code: int) -> JSONResponse:
    """Build a standard OAuth error JSON response."""
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status_code,
    )


def _normalize_loopback(uri: str) -> str:
    """Rewrite IPv4/IPv6 loopback hosts to ``localhost``.

    MCP clients are inconsistent about which loopback form they register versus
    redirect to; normalizing both to ``localhost`` at registration time avoids
    redirect_uri mismatches during the token exchange (Task 5).

    Args:
        uri: A redirect URI as supplied by the client.

    Returns:
        The URI with loopback hosts (127.0.0.1, [::1], ::1) replaced by
        ``localhost``; otherwise the URI unchanged.
    """
    parts = urlsplit(uri)
    if parts.hostname not in ("127.0.0.1", "[::1]", "::1"):
        return uri
    netloc = "localhost" if parts.port is None else f"localhost:{parts.port}"
    normalized: SplitResult = parts._replace(netloc=netloc)
    return urlunsplit(normalized)


def _extract_bearer_token(request: Request) -> str | None:
    """Return the Bearer token from the Authorization header, or None."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def _resolve_redirect_uri(requested: str | None, registered: list[str]) -> str | None:
    """Pick the redirect URI to use, validating it against the registered set.

    Loopback hosts are normalized before comparison. When no redirect URI is
    supplied the first registered one is used. Returns ``None`` when the
    requested URI is not registered.
    """
    if requested is None:
        return registered[0] if registered else None
    normalized = _normalize_loopback(requested)
    return normalized if normalized in registered else None


def _redirect_with_code(redirect_uri: str, code: str, state: str | None) -> str:
    """Append the authorization code (and optional state) to the redirect URI."""
    parts = urlsplit(redirect_uri)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("code", code))
    if state is not None:
        query.append(("state", state))
    return urlunsplit(parts._replace(query=urlencode(query)))


async def _is_email_allowed(db: FirestoreAsyncClient, email: str | None) -> bool:
    """Return True if *email* is whitelisted with ``status == "active"``.

    The allow-list (``allowed_users``) is curated manually by Ambiental Media;
    access is restricted to Google SSO accounts explicitly authorized there.
    """
    if not email:
        return False
    normalized_email = email.strip().lower()
    snapshot = await db.collection(ALLOWED_USERS_COLLECTION).document(normalized_email).get()
    if not snapshot.exists:
        return False
    data = snapshot.to_dict() or {}
    return data.get("status") == "active"


async def oauth_health(request: Request) -> JSONResponse:
    """Liveness probe for the OAuth proxy router."""
    return JSONResponse({"status": "ok", "service": "jor-mcp-oauth"})


async def authorization_server_metadata(request: Request) -> JSONResponse:
    """RFC 8414 Authorization Server Metadata for native MCP OAuth discovery.

    The ``authorization_endpoint`` points at the Next.js consent portal while the
    token and registration endpoints point at this Python backend.
    """
    return JSONResponse(
        {
            "issuer": OAUTH_SERVER_BASE_URL,
            "authorization_endpoint": f"{OAUTH_PORTAL_BASE_URL}/authorize",
            "token_endpoint": f"{OAUTH_SERVER_BASE_URL}{OAUTH_PATH_PREFIX}/token",
            "registration_endpoint": f"{OAUTH_SERVER_BASE_URL}{OAUTH_PATH_PREFIX}/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )


async def protected_resource_metadata(request: Request) -> JSONResponse:
    """RFC 9728 Protected Resource Metadata pointing clients at the auth server."""
    return JSONResponse(
        {
            "resource": f"{OAUTH_SERVER_BASE_URL}/mcp",
            "authorization_servers": [OAUTH_SERVER_BASE_URL],
        }
    )


async def oauth_register(request: Request) -> JSONResponse:
    """Dynamic Client Registration endpoint (RFC 7591).

    Validates the client metadata, forces the client to be public
    (``token_endpoint_auth_method = "none"``), normalizes loopback redirect URIs,
    persists the client under :data:`OAUTH_CLIENTS_COLLECTION` and returns the
    generated ``client_id``.
    """
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _error_response("invalid_request", "Request body must be valid JSON", 400)

    try:
        metadata = ClientRegistrationRequest.model_validate(payload)
    except ValidationError as exc:
        return _error_response("invalid_client_metadata", str(exc), 400)

    redirect_uris = [_normalize_loopback(uri) for uri in metadata.redirect_uris]
    client_id = str(uuid.uuid4())
    document: dict[str, Any] = {
        "client_id": client_id,
        "client_name": metadata.client_name,
        "redirect_uris": redirect_uris,
        # Business rule: MCP clients must be public regardless of what they ask for.
        "token_endpoint_auth_method": "none",  # nosec B105
        "grant_types": metadata.grant_types or ["authorization_code", "refresh_token"],
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    # Lazy import: src.server imports this module's routes at load time, so a
    # top-level `from src.server import ...` here would be a circular import.
    from src.server import get_firestore_client

    db = get_firestore_client()
    await db.collection(OAUTH_CLIENTS_COLLECTION).document(client_id).set(document)

    logger.info("Registered OAuth client", extra={"client_id": client_id})

    return JSONResponse(
        {
            "client_id": client_id,
            "client_name": metadata.client_name,
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "none",  # nosec B105
        },
        status_code=201,
    )


async def oauth_approve(request: Request) -> JSONResponse:
    """Consent approval endpoint: issue an authorization code bound to PKCE state.

    Requires a valid Firebase ID token (``Authorization: Bearer``) to prove the
    user's identity. Validates the client and redirect URI, then persists a
    short-lived authorization code plus the PKCE ``code_challenge`` and the user
    ``uid`` under :data:`OAUTH_CODES_COLLECTION` for the later token exchange.
    """
    token = _extract_bearer_token(request)
    if token is None:
        return _error_response("invalid_token", "Missing bearer token", 401)

    try:
        decoded = await asyncio.to_thread(auth.verify_id_token, token, clock_skew_seconds=60)
    except (firebase_admin.exceptions.FirebaseError, ValueError) as exc:
        logger.warning("Firebase token verification failed", extra={"error": str(exc)})
        return _error_response("invalid_token", "Invalid Firebase ID token", 401)

    uid: str = decoded["uid"]
    email: str | None = decoded.get("email")

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _error_response("invalid_request", "Request body must be valid JSON", 400)

    try:
        approval = ApproveRequest.model_validate(payload)
    except ValidationError as exc:
        return _error_response("invalid_request", str(exc), 400)

    if approval.code_challenge_method != "S256":
        return _error_response(
            "invalid_request", "Only S256 code_challenge_method is supported", 400
        )

    # Lazy import: avoids the circular import described in oauth_register.
    from src.server import get_firestore_client

    db = get_firestore_client()
    client_ref = db.collection(OAUTH_CLIENTS_COLLECTION).document(approval.client_id)
    client_snapshot = await client_ref.get()
    if not client_snapshot.exists:
        return _error_response("invalid_client", "Unknown client_id", 400)

    registered_uris: list[str] = client_snapshot.get("redirect_uris") or []
    redirect_uri = _resolve_redirect_uri(approval.redirect_uri, registered_uris)
    if redirect_uri is None:
        return _error_response(
            "invalid_request", "redirect_uri is not registered for this client", 400
        )

    if not await _is_email_allowed(db, email):
        logger.warning("User not on the allow-list", extra={"uid": uid})
        return _error_response(
            "access_denied", "User is not authorized to access this resource", 403
        )

    code = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    document: dict[str, Any] = {
        "code": code,
        "client_id": approval.client_id,
        "code_challenge": approval.code_challenge,
        "code_challenge_method": approval.code_challenge_method,
        "redirect_uri": redirect_uri,
        "uid": uid,
        "created_at": firestore.SERVER_TIMESTAMP,
        "expires_at": now + timedelta(seconds=OAUTH_CODE_TTL_SECONDS),
    }
    await db.collection(OAUTH_CODES_COLLECTION).document(code).set(document)

    logger.info(
        "Issued authorization code",
        extra={"client_id": approval.client_id, "uid": uid},
    )

    return JSONResponse(
        {
            "authorization_code": code,
            "redirect_uri": _redirect_with_code(redirect_uri, code, approval.state),
        }
    )


def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
    """Return True if the S256 PKCE transform of *code_verifier* matches.

    Computes ``BASE64URL(SHA256(ASCII(code_verifier)))`` without padding (per
    RFC 7636) and compares it to the stored challenge in constant time.
    """
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return secrets.compare_digest(computed, code_challenge)


def _is_expired(expires_at: datetime | None) -> bool:
    """Return True if *expires_at* is a datetime in the past (UTC)."""
    if not isinstance(expires_at, datetime):
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at < datetime.now(UTC)


async def _mint_firebase_tokens(uid: str) -> dict[str, Any]:
    """Mint a Firebase ID + refresh token pair for *uid* via Identity Toolkit.

    Creates a short-lived custom token with the Admin SDK and exchanges it for a
    real ID token and long-lived refresh token through the Identity Toolkit REST
    API (``accounts:signInWithCustomToken``).
    """
    custom_token = auth.create_custom_token(uid)
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode("ascii")
    response = await get_http_client().post(
        f"{IDENTITY_TOOLKIT_BASE_URL}/accounts:signInWithCustomToken",
        params={"key": FIREBASE_WEB_API_KEY},
        json={"token": custom_token, "returnSecureToken": True},
    )
    response.raise_for_status()
    data = response.json()
    return {
        "access_token": data["idToken"],
        "token_type": "Bearer",  # nosec B105
        "expires_in": int(data["expiresIn"]),
        "refresh_token": data["refreshToken"],
    }


async def _refresh_firebase_tokens(refresh_token: str) -> dict[str, Any]:
    """Exchange a Firebase refresh token for a fresh ID token via Secure Token."""
    response = await get_http_client().post(
        f"{SECURE_TOKEN_BASE_URL}/token",
        params={"key": FIREBASE_WEB_API_KEY},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    response.raise_for_status()
    data = response.json()
    return {
        "access_token": data["id_token"],
        "token_type": "Bearer",  # nosec B105
        "expires_in": int(data["expires_in"]),
        "refresh_token": data["refresh_token"],
    }


async def oauth_token(request: Request) -> JSONResponse:
    """Token endpoint (RFC 6749) completing the OAuth 2.1 flow.

    Accepts ``application/x-www-form-urlencoded``. The ``authorization_code``
    grant verifies the PKCE ``code_verifier`` against the stored ``code_challenge``,
    consumes the code (anti-replay) and mints real Firebase tokens. The
    ``refresh_token`` grant exchanges a refresh token for a fresh ID token.
    """
    try:
        form = await request.form()
    except RuntimeError:
        return _error_response(
            "invalid_request",
            "Expected application/x-www-form-urlencoded or multipart/form-data content type",
            400,
        )
    try:
        token_request = TokenRequest.model_validate(dict(form))
    except ValidationError as exc:
        return _error_response("invalid_request", str(exc), 400)

    if token_request.grant_type == "authorization_code":
        return await _handle_authorization_code(token_request)
    if token_request.grant_type == "refresh_token":
        return await _handle_refresh_token(token_request)
    return _error_response("unsupported_grant_type", "Unsupported grant_type", 400)


async def _handle_authorization_code(token_request: TokenRequest) -> JSONResponse:
    """Validate PKCE for the authorization_code grant and mint Firebase tokens."""
    if not token_request.code or not token_request.code_verifier:
        return _error_response("invalid_request", "Missing code or code_verifier", 400)

    # Lazy import: avoids the circular import described in oauth_register.
    from src.server import get_firestore_client

    db = get_firestore_client()
    code_ref = db.collection(OAUTH_CODES_COLLECTION).document(token_request.code)
    snapshot = await code_ref.get()
    if not snapshot.exists:
        return _error_response("invalid_grant", "Invalid or expired authorization code", 400)

    record: dict[str, Any] = snapshot.to_dict() or {}
    # Consume the code immediately so a failed or replayed exchange cannot reuse it.
    await code_ref.delete()

    if _is_expired(record.get("expires_at")):
        return _error_response("invalid_grant", "Authorization code expired", 400)
    if token_request.client_id and token_request.client_id != record.get("client_id"):
        return _error_response("invalid_grant", "client_id mismatch", 400)
    if token_request.redirect_uri and _normalize_loopback(token_request.redirect_uri) != record.get(
        "redirect_uri"
    ):
        return _error_response("invalid_grant", "redirect_uri mismatch", 400)
    if not _verify_pkce(token_request.code_verifier, record.get("code_challenge", "")):
        return _error_response("invalid_grant", "PKCE verification failed", 400)

    try:
        tokens = await _mint_firebase_tokens(record["uid"])
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Failed to mint Firebase tokens")
        return _error_response("server_error", "Token minting failed", 502)

    logger.info(
        "Issued tokens",
        extra={"client_id": record.get("client_id"), "uid": record.get("uid")},
    )
    return JSONResponse(tokens)


async def _handle_refresh_token(token_request: TokenRequest) -> JSONResponse:
    """Exchange a refresh token for a fresh ID token (refresh_token grant)."""
    if not token_request.refresh_token:
        return _error_response("invalid_request", "Missing refresh_token", 400)
    try:
        tokens = await _refresh_firebase_tokens(token_request.refresh_token)
    except (httpx.HTTPError, KeyError, ValueError):
        logger.exception("Failed to refresh Firebase token")
        return _error_response("invalid_grant", "Invalid refresh token", 400)
    return JSONResponse(tokens)


routes: list[Route] = [
    Route("/health", oauth_health, methods=["GET"]),
    Route("/register", oauth_register, methods=["POST"]),
    Route("/approve", oauth_approve, methods=["POST"]),
    Route("/token", oauth_token, methods=["POST"]),
]
"""Routes mounted under :data:`OAUTH_PATH_PREFIX` (``/api/oauth``)."""

well_known_routes: list[Route] = [
    Route(
        "/.well-known/oauth-authorization-server",
        authorization_server_metadata,
        methods=["GET"],
    ),
    Route(
        "/.well-known/oauth-protected-resource",
        protected_resource_metadata,
        methods=["GET"],
    ),
]
"""Discovery routes mounted at the application root by :mod:`src.server`."""
