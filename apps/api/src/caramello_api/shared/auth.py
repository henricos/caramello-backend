"""OIDC authentication and authorization layer for Caramello.

This is the api's single real authorization boundary. Caramello is a standard
OAuth2 **resource server**: it never starts an OAuth flow, it independently
revalidates the `access_token` any consumer presents (`apps/web`, another
application, an MCP agent) and it only trusts a token whose `aud` carries this
api's own audience. See "Authentication model: the api as a standard OAuth2
resource server, with its own audience" in the root `docs/architecture.md`.

Authorization has two layers, and both live behind `get_current_user`:

  - the **e-mail allowlist** (`allowed_emails`) decides whether an identity may
    use the system at all;
  - **family membership** (`require_family_access`, plus the per-family
    filters in each domain) decides which data that identity may reach.

Provides:
  - fetch_jwks(): called from the FastAPI lifespan to warm the provider cache
  - get_discovery_document(): the provider's metadata, for the OAuth discovery
    endpoints MCP clients consume
  - get_current_user(): FastAPI dependency validating the JWT, applying both
    authorization checks and provisioning the user just-in-time
  - http_bearer: HTTPBearer instance used to extract the Authorization header

Usage pattern in routers:
    from caramello_api.shared.auth import get_current_user
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)) -> User:
        return user

Every human-readable message returned from here comes from the i18n catalog
via `_error_detail()`: the response carries a machine-readable `reason` code as
the contract plus a localized `message` for display. No error body ever carries
the caller's e-mail — `not_allowlisted` in particular must not reveal whether
an address exists anywhere.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.core.config import get_settings
from caramello_api.i18n import translate
from caramello_api.shared.database import get_session
from caramello_api.shared.models import AllowedEmail

if TYPE_CHECKING:
    from caramello_api.users.models import User

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Module state — analogous to the `engine` singleton in shared/database.py
# ----------------------------------------------------------------------

# A 1h TTL keeps token validation from depending on the provider's
# availability on every request. Discovery and JWKS are always fetched
# together, so a fresh JWKS implies a fresh discovery document.
_JWKS_TTL_SECONDS = 3600

# The token's `kid` is read WITHOUT verifying the signature, so it is fully
# controlled by whoever sends the token. The cooldown is armed only when a
# forced refresh WAS attempted and STILL did not resolve the kid — never on the
# success path — so a real key rotation is never penalized while a forged `kid`
# cannot amplify traffic against the provider.
_FORCED_REFRESH_COOLDOWN_SECONDS = 5.0

# In-memory JWKS cache: kid -> RSA public key (an opaque pyjwt object).
# Populated by fetch_jwks() at startup; re-populated by get_current_user when
# an unknown kid shows up (key rotation).
_jwks_cache: dict[str, Any] = {}

# Companion state for the same fetch cycle: the provider's discovery document
# and the timestamps that drive the TTL and the forced-refresh cooldown. A dict
# rather than module-level scalars so the helpers below can mutate it without
# `global`.
_provider_cache: dict[str, Any] = {
    "discovery": None,
    "fetched_at": 0.0,
    "last_failed_forced_refresh_at": 0.0,
}

# Serializes refreshes: N concurrent requests hitting a cold or expired cache
# must produce ONE fetch against the provider, not N.
_refresh_lock = asyncio.Lock()

# Bearer token extractor with auto_error=False so we can raise 401 instead of
# the default 403. RFC 7235 §3.1: 401 for a missing credential.
_http_bearer_extractor = HTTPBearer(auto_error=False)


def _error_detail(reason: str) -> dict[str, str]:
    """Build an error detail pairing a stable code with its localized text.

    `reason` is the contract consumers branch on; `message` is display text
    resolved from the i18n catalog and may change without breaking anyone.
    """
    return {"reason": reason, "message": translate(f"auth.{reason}")}


def _www_authenticate_header() -> dict[str, str]:
    """`WWW-Authenticate` for 401 responses (RFC 6750 + the MCP auth spec).

    `resource_metadata` points MCP clients at the Protected Resource Metadata
    endpoint (`shared/oauth_discovery.py`) so they can run the OAuth flow on
    their own instead of failing opaquely. Only 401s carry it: a 403 means the
    credential was understood and rejected, so re-authenticating changes
    nothing.
    """
    metadata_url = f"{get_settings().public_url}/.well-known/oauth-protected-resource"
    return {"WWW-Authenticate": f'Bearer resource_metadata="{metadata_url}"'}


async def http_bearer(request: Request) -> HTTPAuthorizationCredentials:
    """Extract the Bearer token, raising 401 (not 403) when it is absent.

    A header that is missing, empty or carrying a different scheme all land
    here: from the caller's perspective no usable credential was presented.
    """
    credentials = await _http_bearer_extractor(request)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("missing_token"),
            headers=_www_authenticate_header(),
        )
    return credentials


# ----------------------------------------------------------------------
# Provider metadata — discovery document + JWKS, one cache cycle
# ----------------------------------------------------------------------


async def _fetch_discovery_document(client: httpx.AsyncClient) -> dict[str, Any]:
    # `auth_oidc_issuer` is already normalized (no trailing slash) by Settings,
    # so this URL and the `iss` claim validation always agree.
    url = f"{get_settings().auth_oidc_issuer}/.well-known/openid-configuration"
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def _fetch_jwks_document(client: httpx.AsyncClient, jwks_uri: str) -> dict[str, Any]:
    response = await client.get(jwks_uri)
    response.raise_for_status()
    return response.json()


def _cache_is_fresh() -> bool:
    if _provider_cache["fetched_at"] <= 0.0:
        return False
    return (time.monotonic() - _provider_cache["fetched_at"]) < _JWKS_TTL_SECONDS


async def fetch_jwks(force_refresh: bool = False) -> None:
    """Refresh the provider cache (discovery document + JWKS keys).

    Called at startup (lifespan) as a warm-up, on a cache miss/expiry, and
    again by get_current_user with `force_refresh=True` when an unknown kid
    shows up (key rotation).

    The JWKS URI is resolved from the provider's discovery document instead of
    a hardcoded suffix, so nothing provider-specific is baked into this module.

    PyJWT's own JWKS client uses synchronous urllib and would block the event
    loop, hence httpx.AsyncClient here.
    """
    if not force_refresh and _cache_is_fresh():
        return

    requested_at = time.monotonic()
    async with _refresh_lock:
        # Double-check after acquiring the lock: a coroutine that waited here
        # piggybacks on the refresh the lock holder just completed (which also
        # satisfies `force_refresh` — the cache IS newer than the request)
        # instead of fetching again.
        if _provider_cache["fetched_at"] >= requested_at:
            return
        if not force_refresh and _cache_is_fresh():
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            discovery = await _fetch_discovery_document(client)
            jwks = await _fetch_jwks_document(client, discovery["jwks_uri"])

        new_cache: dict[str, Any] = {}
        for key_data in jwks.get("keys", []):
            kid = key_data.get("kid")
            if not kid:
                continue
            # RSAAlgorithm.from_jwk accepts either a dict or a JSON string
            new_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

        # Atomic cache swap (avoids an intermediate state under concurrency)
        _jwks_cache.clear()
        _jwks_cache.update(new_cache)
        _provider_cache["discovery"] = discovery
        _provider_cache["fetched_at"] = time.monotonic()


async def get_discovery_document() -> dict[str, Any]:
    """Return the provider's discovery document, reusing the JWKS cache cycle.

    Used by the OAuth discovery endpoints (`shared/oauth_discovery.py`).
    Raises whatever the fetch raises (transport error, HTTP status), which the
    endpoint translates into a 503.
    """
    await fetch_jwks()
    discovery = _provider_cache["discovery"]
    if discovery is None:
        raise RuntimeError("The OIDC provider's discovery document is unavailable.")
    return discovery


# ----------------------------------------------------------------------
# Allowlist — the first authorization layer
# ----------------------------------------------------------------------


async def is_email_allowlisted(session: AsyncSession, email: str) -> bool:
    """Check whether `email` is on the `allowed_emails` allowlist.

    Normalization contract: the stored value is always `.strip().lower()` (see
    `shared/models.py`), and Postgres compares strings case-sensitively, so the
    argument is normalized here as well. Callers are expected to pass an
    already-normalized address — normalizing again is a cheap guarantee that
    the contract can never be broken by a new call site.
    """
    normalized = email.strip().lower()
    result = await session.execute(select(AllowedEmail).where(AllowedEmail.email == normalized))
    return result.scalars().first() is not None


# ----------------------------------------------------------------------
# get_current_user — dependency injected into every protected endpoint
# ----------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate the Bearer token, authorize the caller and return the User.

    Ordered checks — cheap, in-memory ones first, so an unauthorized caller
    never reaches the database:

      1. Missing/malformed `Authorization` header -> 401 `missing_token`
         (raised by the `http_bearer` dependency above).
      2. Unreadable header, unknown `kid`, bad signature -> 401
         `invalid_token` / `missing_kid` / `unknown_kid`; an unknown kid buys
         exactly ONE forced JWKS refresh, cooldown-guarded, for key rotation.
      3. `iss`, `aud`, `exp`, `sub` and `email` are validated as ESSENTIAL
         claims against Settings -> 401 `expired_token` / `invalid_token`.
         `aud` must contain this api's own audience, which is what makes a
         token minted for another service unusable here.
      4. `email_verified` missing or falsy -> 403 `email_not_verified`,
         checked BEFORE any database query: a claim that is not trustworthy
         yet must cost no query and leak no allowlist timing.
      5. E-mail not on the allowlist -> 403 `not_allowlisted`, with a generic
         message that never echoes the address back.
      6. JIT provisioning: INSERT ... ON CONFLICT DO NOTHING on `idp_sub`
         (race-safe) followed by the SELECT that reads the row back.
      7. AUTO-JOIN: a pending FamilyInvitation for this e-mail creates a
         FamilyMember(role="member") and flips the invitation to "joined".

    Family membership is NOT checked here — it is the data-scope layer, applied
    per operation (`require_family_access` and the per-family filters).
    """
    # Lazy import of User to avoid a circular import
    # (TYPE_CHECKING resolves it statically)
    from caramello_api.users.models import User

    token = credentials.credentials
    settings = get_settings()

    # 1. Read the kid from the header without validating (needed for the lookup)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("invalid_token"),
            headers=_www_authenticate_header(),
        ) from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("missing_kid"),
            headers=_www_authenticate_header(),
        )

    # 2. Look the key up in the cache; force ONE JWKS refresh on an unknown
    # kid. The cooldown keeps a forged kid from turning every request into a
    # network call against the provider, and is armed only after a refresh that
    # still failed to resolve the kid.
    public_key = _jwks_cache.get(kid)
    if public_key is None:
        cooldown_remaining = _FORCED_REFRESH_COOLDOWN_SECONDS - (
            time.monotonic() - _provider_cache["last_failed_forced_refresh_at"]
        )
        if cooldown_remaining <= 0:
            try:
                await fetch_jwks(force_refresh=True)
            except Exception:  # noqa: BLE001 — a provider outage is a 401, never a 500
                logger.warning("Could not refresh the JWKS cache.", exc_info=True)
            public_key = _jwks_cache.get(kid)
            if public_key is None:
                # A refresh WAS attempted and the kid still does not resolve —
                # only now is the cooldown armed, never on the success path.
                _provider_cache["last_failed_forced_refresh_at"] = time.monotonic()
        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_error_detail("unknown_kid"),
                headers=_www_authenticate_header(),
            )

    # 3. Validate the JWT. `algorithms` is explicit (blocking an algorithm
    # downgrade), `aud`/`iss` are checked against Settings and every claim the
    # code below reads is REQUIRED here — a token missing one fails as a 401
    # instead of raising a KeyError deeper down.
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.auth_oidc_audience,
            issuer=settings.auth_oidc_issuer,
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "require": ["exp", "iss", "aud", "sub", "email"],
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("expired_token"),
            headers=_www_authenticate_header(),
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("invalid_token"),
            headers=_www_authenticate_header(),
        ) from exc

    # 4. email_verified — BEFORE any database access. A missing claim counts as
    # False (deny), never defaulted to True.
    if not payload.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail("email_not_verified"),
        )

    # 5. Extract the claims. `require` above guarantees PRESENCE, never type:
    # a misconfigured claim mapper at the provider must surface as a 401, not
    # as an AttributeError-turned-500.
    email_claim = payload.get("email")
    if not isinstance(email_claim, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("invalid_token"),
            headers=_www_authenticate_header(),
        )
    email = email_claim.strip().lower()

    idp_sub_value = payload.get("sub")
    if not idp_sub_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("missing_sub"),
            headers=_www_authenticate_header(),
        )
    idp_sub: str = str(idp_sub_value)
    name: str = str(payload.get("name") or payload.get("preferred_username") or "")

    # 6. Allowlist — the first authorization layer, and the first query.
    if not await is_email_allowlisted(session, email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail("not_allowlisted"),
        )

    # 7. JIT provisioning with ON CONFLICT DO NOTHING.
    # Race-condition-safe: concurrent requests for the same user never duplicate.
    insert_stmt = (
        pg_insert(User.__table__)  # type: ignore[attr-defined]
        .values(idp_sub=idp_sub, email=email, name=name)
        .on_conflict_do_nothing(index_elements=["idp_sub"])
    )
    await session.execute(insert_stmt)
    await session.commit()

    # 8. SELECT — ON CONFLICT DO NOTHING does not return the row
    result = await session.execute(select(User).where(User.idp_sub == idp_sub))
    user = result.scalars().first()
    if user is None:
        # Unexpected state: the insert happened but the select found nothing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail("provisioning_failed"),
        )

    # 9. AUTO-JOIN: if a pending FamilyInvitation exists for this e-mail, add the
    # user automatically as FamilyMember(role="member").
    # Lazy import to avoid a cycle between shared/ and families/.
    from caramello_api.families.models import (  # noqa: PLC0415
        FamilyInvitation,
        FamilyMember,
    )

    inv_result = await session.execute(
        select(FamilyInvitation).where(
            FamilyInvitation.email == email,
            FamilyInvitation.status == "pending_login",
        )
    )
    pending_inv = inv_result.scalars().first()
    if pending_inv is not None:
        new_member = FamilyMember(
            user_id=user.id,
            family_id=pending_inv.family_id,
            role="member",
        )
        session.add(new_member)
        pending_inv.status = "joined"
        session.add(pending_inv)
        await session.commit()

    return user


# ----------------------------------------------------------------------
# require_family_access — reusable per-family access-control helper
# ----------------------------------------------------------------------


async def require_family_access(
    family_id: int,
    current_user: User,
    session: AsyncSession,
) -> None:
    """Assert that current_user is a member of family_id; raise 403 otherwise.

    FamilyMember is imported lazily to avoid a shared/ <-> families/ cycle
    (same pattern as get_current_user above).
    """
    from caramello_api.families.models import FamilyMember  # noqa: PLC0415

    result = await session.execute(
        select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if result.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail("not_family_member"),
        )
