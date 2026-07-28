from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
from caramello_api.users.models import User
from caramello_api.users.schemas import UserCreate, UserRead, UserUpdate

user_router = APIRouter(prefix="/users/user", tags=["User"])


@user_router.post("/", response_model=UserRead)
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> User:
    db_obj = User(**user_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@user_router.get("/", response_model=list[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[User]:
    result = await session.execute(select(User).offset(offset).limit(limit))
    return list(result.scalars().all())


@user_router.get("/{uuid}", response_model=UserRead)
async def read_user(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> User:
    statement = select(User).where(User.uuid == uuid)
    result = await session.execute(statement)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@user_router.patch("/{uuid}", response_model=UserRead)
async def update_user(
    uuid: UUID,
    user_in: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> User:
    statement = select(User).where(User.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@user_router.delete("/{uuid}")
async def delete_user(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(User).where(User.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


router = APIRouter()
router.include_router(user_router)
