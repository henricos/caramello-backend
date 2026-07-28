# CARAMELLO-GENERATED: implemented
"""Business operations of the families domain — Phase 4.

Covers:
  - FAMILY-01: POST /families/registry (create a family, become its owner)
  - FAMILY-02: GET  /families/families (list my families)
  - FAMILY-03: GET  /families/families/{uuid} (detail when member, 403 otherwise)
  - D-07:      POST /families/families/{uuid}/pre-register (owner pre-registers an e-mail)
  - D-07:      GET  /families/families/{uuid}/members (member list, members only)
  - FAMILY-07: DELETE /families/families/{uuid}/members/{user_uuid} (owner removes)

NOT implemented in this phase (D-04 — deferred to M2):
  - FAMILY-04: POST /families/families/{uuid}/invitations (reusable invite code)
  - FAMILY-05: POST /families/invitations/{code}/join (join request)
  - FAMILY-06: PATCH /families/invitations/{id} (approve/reject)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.families.models import Family, FamilyInvitation, FamilyMember
from caramello_api.families.schemas import (
    FamilyCreate,
    FamilyInvitationRead,
    FamilyRead,
)
from caramello_api.i18n import error_detail
from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
from caramello_api.users.models import User

router = APIRouter(prefix="/families", tags=["Family"])


# ---------------------------------------------------------------------------
# Local schemas (outside DSL generation — specific to these operations)
# ---------------------------------------------------------------------------


class PreRegisterBody(BaseModel):
    """Body of POST /families/{uuid}/pre-register — the invitee's e-mail is all it takes."""

    email: EmailStr


class FamilyMemberRead(BaseModel):
    """Response of GET /families/{uuid}/members. Carries user_uuid resolved through a JOIN."""

    user_uuid: UUID
    role: str
    joined_at: datetime


# ---------------------------------------------------------------------------
# Authorization helpers (D-13 — role check)
# ---------------------------------------------------------------------------


async def _require_owner(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> tuple[Family, FamilyMember]:
    """Ensure the user is the OWNER of the family with the given uuid.

    Returns (family, member) when they are; raises 403 otherwise.
    """
    result = await session.execute(
        select(Family, FamilyMember)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
            FamilyMember.role == "owner",
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("auth.not_owner"),
        )
    family, member = row
    return family, member


async def _require_member(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> Family:
    """Ensure the user is a MEMBER (any role) of the family with the given uuid.

    Returns the Family when they are; raises 403 otherwise.
    """
    result = await session.execute(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
        )
    )
    family = result.scalars().first()
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("auth.not_family_member"),
        )
    return family


# ---------------------------------------------------------------------------
# FAMILY-01: POST /families/registry
# ---------------------------------------------------------------------------


@router.post("/registry", response_model=FamilyRead, status_code=status.HTTP_201_CREATED)
async def registry_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Family:
    """FAMILY-01: create a family and register the authenticated user as its owner."""
    # exclude_none=True so the model's own defaults are not overwritten (e.g.
    # Family.status defaults to "active", and would be None if FamilyCreate
    # omitted it).
    family_data = family_in.model_dump(exclude_none=True)
    db_family = Family(**family_data)
    session.add(db_family)
    # flush to obtain db_family.id without committing — needed for the
    # FamilyMember FK. RESOLVED (Open Question 1 of 04-RESEARCH.md):
    # session.flush() with SQLAlchemy+asyncpg is a safe way to get an
    # autoincrement PK before the commit (established pattern).
    await session.flush()

    owner_member = FamilyMember(
        user_id=current_user.id,
        family_id=db_family.id,
        role="owner",
    )
    session.add(owner_member)
    await session.commit()
    await session.refresh(db_family)
    return db_family


# ---------------------------------------------------------------------------
# FAMILY-02: GET /families/families
# ---------------------------------------------------------------------------


@router.get(
    "/families",
    response_model=list[FamilyRead],
    operation_id="list_my_families",
)
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Family]:
    """FAMILY-02: list the families the authenticated user belongs to."""
    from caramello_api.families.services import list_my_families as svc

    return await svc(session, current_user)


# ---------------------------------------------------------------------------
# FAMILY-03: GET /families/families/{family_uuid}
# ---------------------------------------------------------------------------


@router.get("/families/{family_uuid}", response_model=FamilyRead)
async def get_family_detail(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Family:
    """FAMILY-03: return the family's details when the user is a member; 403 otherwise."""
    return await _require_member(family_uuid, current_user, session)


# ---------------------------------------------------------------------------
# D-07: POST /families/families/{family_uuid}/pre-register
# ---------------------------------------------------------------------------


@router.post(
    "/families/{family_uuid}/pre-register",
    response_model=FamilyInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def pre_register_member(
    family_uuid: UUID,
    body: PreRegisterBody,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FamilyInvitationRead:
    """D-07: the owner pre-registers an e-mail for automatic joining (D-02 auto-join)."""
    family, _ = await _require_owner(family_uuid, current_user, session)

    invitation = FamilyInvitation(
        family_id=family.id,
        inviter_id=current_user.id,
        email=str(body.email),
        status="pending_login",
    )
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    # The response is built field by field instead of being validated straight
    # from the ORM instance: `FamilyInvitationRead` exposes the two foreign keys
    # as UUIDs (`expose_as_uuid` in the DSL), and those attributes exist only
    # here — the table itself keeps the integer columns.
    return FamilyInvitationRead(
        uuid=invitation.uuid,
        family_uuid=family.uuid,
        inviter_uuid=current_user.uuid,
        email=invitation.email,
        status=invitation.status,
        created_at=invitation.created_at,
    )


# ---------------------------------------------------------------------------
# D-07: GET /families/families/{family_uuid}/members
# ---------------------------------------------------------------------------


@router.get(
    "/families/{family_uuid}/members",
    response_model=list[FamilyMemberRead],
)
async def list_members(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FamilyMemberRead]:
    """D-07: list every member, provided the caller is a member of the family."""
    family = await _require_member(family_uuid, current_user, session)

    result = await session.execute(
        select(User, FamilyMember)
        .join(FamilyMember, FamilyMember.user_id == User.id)
        .where(FamilyMember.family_id == family.id)
    )
    rows = list(result.all())
    return [
        FamilyMemberRead(
            user_uuid=user.uuid,
            role=member.role,
            joined_at=member.joined_at,
        )
        for user, member in rows
    ]


# ---------------------------------------------------------------------------
# FAMILY-07: DELETE /families/families/{family_uuid}/members/{user_uuid}
# ---------------------------------------------------------------------------


@router.delete(
    "/families/{family_uuid}/members/{user_uuid}",
    status_code=status.HTTP_200_OK,
)
async def remove_member(
    family_uuid: UUID,
    user_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """FAMILY-07: the owner removes a member from the family; 403 otherwise."""
    family, _ = await _require_owner(family_uuid, current_user, session)

    # Locate the target user
    target_result = await session.execute(select(User).where(User.uuid == user_uuid))
    target_user = target_result.scalars().first()
    if target_user is None:
        raise HTTPException(status_code=404, detail=error_detail("families.user_not_found"))

    # Locate the membership
    member_result = await session.execute(
        select(FamilyMember).where(
            FamilyMember.family_id == family.id,
            FamilyMember.user_id == target_user.id,
        )
    )
    target_member = member_result.scalars().first()
    if target_member is None:
        raise HTTPException(
            status_code=404,
            detail=error_detail("families.user_not_family_member"),
        )

    await session.delete(target_member)
    await session.commit()
    return {"ok": True}
