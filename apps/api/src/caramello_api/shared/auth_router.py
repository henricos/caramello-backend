"""`POST /auth/verify` — the endpoint a consumer calls on its OIDC callback.

`apps/web` calls this route right after obtaining the tokens from the OIDC
provider, BEFORE any session cookie exists, forwarding the access token so the
api decides whether to accept or deny the login.

It lives in `shared/` rather than in `users/`: the module is generated code's
neighbour, not part of it (`users/router.py` and `users/schemas.py` are
rewritten by the DSL generator on every run, and `users/operations.py` is the
home of *business* operations on the user domain). The route is also not
`/users/...` — it is the authentication surface itself, so it belongs next to
`shared/auth.py`, whose `get_current_user` does all the work.

Reusing `get_current_user` via `Depends` is the whole point: signature and
audience validation, `email_verified`, the allowlist, the JIT provisioning and
the auto-join by pending invitation all happen through the exact same code path
that protects every other route — the login flow duplicates nothing.

Unversioned on purpose: no route in this project carries a version prefix yet,
and a consumer's login callback URL should not have to change when one is
introduced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from caramello_api.shared.auth import get_current_user

if TYPE_CHECKING:
    from caramello_api.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthVerifyResponse(BaseModel):
    """Identity confirmed by the api, echoed back to the calling consumer.

    Declared here instead of in `users/schemas.py` because that file is
    generated from the DSL: this is an authentication contract, not an entity
    schema. Deliberately minimal — a consumer building a session needs the
    identity, never the internal user record.
    """

    email: str = Field(description="Normalized e-mail (lowercase) of the authenticated user.")
    sub: str = Field(description="Subject claim of the token — the identity at the provider.")
    name: str | None = Field(
        default=None,
        description="Display name from the token claims; null when the provider sends none.",
    )


@router.post("/verify", response_model=AuthVerifyResponse, operation_id="verify_auth")
async def verify_auth(current_user: User = Depends(get_current_user)) -> AuthVerifyResponse:
    """Confirm that the presented access token belongs to an authorized user.

    Reaching the body means every check in `get_current_user` passed and the
    user row exists (provisioned just-in-time on a first login). The failure
    contract is `get_current_user`'s: 401 `missing_token`/`invalid_token`/
    `expired_token`, 403 `email_not_verified`/`not_allowlisted`.
    """
    # `name` is NOT NULL in the table but may legitimately be empty when the
    # provider sends no display name; the contract exposes that as null.
    return AuthVerifyResponse(
        email=current_user.email,
        sub=current_user.idp_sub,
        name=current_user.name or None,
    )
