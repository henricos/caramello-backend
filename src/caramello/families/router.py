from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.families.models import (
    Family,
    FamilyCreate,
    FamilyInvitation,
    FamilyInvitationCreate,
    FamilyInvitationRead,
    FamilyInvitationUpdate,
    FamilyRead,
    FamilyUpdate,
)
from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.users.models import User

family_router = APIRouter(prefix="/families/family", tags=["Family"])


@family_router.post("/", response_model=FamilyRead)
async def create_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    db_obj = Family.model_validate(family_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@family_router.get("/", response_model=list[FamilyRead])
async def read_familys(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Family]:
    result = await session.exec(select(Family).offset(offset).limit(limit))
    return list(result.all())


@family_router.get("/{uuid}", response_model=FamilyRead)
async def read_family(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    family = result.first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@family_router.patch("/{uuid}", response_model=FamilyRead)
async def update_family(
    uuid: UUID,
    family_in: FamilyUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")
    update_data = family_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@family_router.delete("/{uuid}")
async def delete_family(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


familyinvitation_router = APIRouter(
    prefix="/families/family-invitation", tags=["FamilyInvitation"]
)


@familyinvitation_router.post("/", response_model=FamilyInvitationRead)
async def create_familyinvitation(
    familyinvitation_in: FamilyInvitationCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FamilyInvitation:
    db_obj = FamilyInvitation.model_validate(familyinvitation_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@familyinvitation_router.get("/", response_model=list[FamilyInvitationRead])
async def read_familyinvitations(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[FamilyInvitation]:
    result = await session.exec(select(FamilyInvitation).offset(offset).limit(limit))
    return list(result.all())


@familyinvitation_router.get("/{uuid}", response_model=FamilyInvitationRead)
async def read_familyinvitation(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FamilyInvitation:
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    familyinvitation = result.first()
    if not familyinvitation:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")
    return familyinvitation


@familyinvitation_router.patch("/{uuid}", response_model=FamilyInvitationRead)
async def update_familyinvitation(
    uuid: UUID,
    familyinvitation_in: FamilyInvitationUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FamilyInvitation:
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")
    update_data = familyinvitation_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@familyinvitation_router.delete("/{uuid}")
async def delete_familyinvitation(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


router = APIRouter()
router.include_router(family_router)
router.include_router(familyinvitation_router)
