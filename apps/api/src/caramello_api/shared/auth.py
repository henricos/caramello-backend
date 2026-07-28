"""OIDC authentication layer for Caramello.

Provides:
  - fetch_jwks(): called from the FastAPI lifespan to populate the JWKS cache
  - get_current_user(): FastAPI dependency validating the JWT + JIT provisioning
  - http_bearer: HTTPBearer instance used to extract the Authorization header

Usage pattern in routers:
    from caramello_api.shared.auth import get_current_user
    @router.get("/me")
    async def me(user: User = Depends(get_current_user)) -> User:
        return user

Every human-readable message returned from here comes from the i18n catalog
via `_error_detail()`: the response carries a machine-readable `reason` code as
the contract plus a localized `message` for display.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello_api.core.config import get_settings
from caramello_api.i18n import translate
from caramello_api.shared.database import get_session

if TYPE_CHECKING:
    from caramello_api.users.models import User

# ----------------------------------------------------------------------
# Module state — analogous to the `engine` singleton in shared/database.py
# ----------------------------------------------------------------------

# In-memory JWKS cache: kid -> RSA public key (an opaque pyjwt object).
# Populated by fetch_jwks() at startup; re-populated by get_current_user when
# an unknown kid shows up (key rotation).
_jwks_cache: dict[str, Any] = {}

# Bearer token extractor with auto_error=False so we can raise 401 instead of
# the default 403. RFC 7235 §3.1: 401 for a missing credential.
_http_bearer_extractor = HTTPBearer(auto_error=False)


def _error_detail(reason: str) -> dict[str, str]:
    """Build an error detail pairing a stable code with its localized text.

    `reason` is the contract consumers branch on; `message` is display text
    resolved from the i18n catalog and may change without breaking anyone.
    """
    return {"reason": reason, "message": translate(f"auth.{reason}")}


async def http_bearer(request: Request) -> HTTPAuthorizationCredentials:
    """Extract the Bearer token, raising 401 (not 403) when it is absent."""
    credentials = await _http_bearer_extractor(request)
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("not_authenticated"),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


# ----------------------------------------------------------------------
# fetch_jwks — called from the FastAPI lifespan
# ----------------------------------------------------------------------


async def fetch_jwks() -> None:
    """Fetch the provider's JWKS keys and populate _jwks_cache.

    Called at startup (lifespan) and again by get_current_user when an unknown
    kid shows up (key rotation).

    PyJWT's own JWKS client uses synchronous urllib and would block the event
    loop, hence httpx.AsyncClient here.
    """
    # `auth_oidc_issuer` is the full realm URL, so the JWKS path hangs
    # directly off it. Resolving it from the discovery document
    # (`/.well-known/openid-configuration`) instead of this fixed suffix is a
    # later phase; the suffix is what the current provider serves.
    jwks_url = f"{get_settings().auth_oidc_issuer}/protocol/openid-connect/certs"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()

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


# ----------------------------------------------------------------------
# get_current_user — dependency injected into every protected endpoint
# ----------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate the Bearer token and return the User (JIT provisioning included).

    Flow:
      1. Extract the kid from the JWT header (without verifying the signature).
      2. Look it up in _jwks_cache; re-fetch the JWKS once if the kid is unknown.
      3. jwt.decode with algorithms=['RS256'] (explicitly blocks downgrade).
      4. Extract claims (sub, email, name | preferred_username).
      5. INSERT ON CONFLICT DO NOTHING — a single atomic operation.
      6. SELECT the User to return it (ON CONFLICT DO NOTHING returns no row).
      7. AUTO-JOIN: look for a pending FamilyInvitation for this e-mail; if one
         exists, create FamilyMember(role="member") and update invitation.status.

    Audience claim: validation starts disabled (verify_aud=False); enabling it
    against `auth_oidc_audience` is a later phase.
    """
    # Lazy import of User to avoid a circular import
    # (TYPE_CHECKING resolves it statically)
    from caramello_api.users.models import User

    token = credentials.credentials

    # 1. Read the kid from the header without validating (needed for the lookup)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("invalid_token"),
        ) from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("missing_kid"),
        )

    # 2. Look the key up in the cache; re-fetch the JWKS on an unknown kid
    public_key = _jwks_cache.get(kid)
    if public_key is None:
        await fetch_jwks()
        public_key = _jwks_cache.get(kid)
        if public_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=_error_detail("unknown_kid"),
            )

    # 3. Validate the JWT — explicit algorithms to block a downgrade attack
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("expired_token"),
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("invalid_token"),
        ) from exc

    # 4. Extract the claims
    idp_sub_value = payload.get("sub")
    if not idp_sub_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_detail("missing_sub"),
        )
    idp_sub: str = str(idp_sub_value)
    email: str = str(payload.get("email") or "")
    name: str = str(payload.get("name") or payload.get("preferred_username") or "")

    # 5. JIT provisioning with ON CONFLICT DO NOTHING.
    # Race-condition-safe: concurrent requests for the same user never duplicate.
    insert_stmt = (
        pg_insert(User.__table__)  # type: ignore[attr-defined]
        .values(idp_sub=idp_sub, email=email, name=name)
        .on_conflict_do_nothing(index_elements=["idp_sub"])
    )
    await session.execute(insert_stmt)
    await session.commit()

    # 6. SELECT — ON CONFLICT DO NOTHING does not return the row
    result = await session.exec(select(User).where(User.idp_sub == idp_sub))
    user = result.first()
    if user is None:
        # Unexpected state: the insert happened but the select found nothing
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_error_detail("provisioning_failed"),
        )

    # 7. AUTO-JOIN: if a pending FamilyInvitation exists for this e-mail, add the
    # user automatically as FamilyMember(role="member").
    # Lazy import to avoid a cycle between shared/ and families/.
    from caramello_api.families.models import (  # noqa: PLC0415
        FamilyInvitation,
        FamilyMember,
    )

    inv_result = await session.exec(
        select(FamilyInvitation).where(
            FamilyInvitation.email == email,
            FamilyInvitation.status == "pending_login",
        )
    )
    pending_inv = inv_result.first()
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
# _require_family_access — reusable per-family access-control helper
# ----------------------------------------------------------------------


async def _require_family_access(
    family_id: int,
    current_user: User,
    session: AsyncSession,
) -> None:
    """Assert that current_user is a member of family_id; raise 403 otherwise.

    FamilyMember is imported lazily to avoid a shared/ <-> families/ cycle
    (same pattern as get_current_user above).
    """
    from caramello_api.families.models import FamilyMember  # noqa: PLC0415

    result = await session.exec(
        select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail("not_family_member"),
        )
