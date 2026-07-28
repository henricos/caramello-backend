from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.families.models import Family
from caramello_api.families.schemas import FamilyCreate, FamilyRead, FamilyUpdate
from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
from caramello_api.users.models import User

family_router = APIRouter(prefix="/families/family", tags=["Family"])


@family_router.post("/", response_model=FamilyRead)
async def create_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    db_obj = Family(**family_in.model_dump(exclude_unset=True))
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
    result = await session.execute(select(Family).offset(offset).limit(limit))
    return list(result.scalars().all())


@family_router.get("/{uuid}", response_model=FamilyRead)
async def read_family(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.execute(statement)
    family = result.scalars().first()
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
    result = await session.execute(statement)
    db_obj = result.scalars().first()
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
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


router = APIRouter()
router.include_router(family_router)
