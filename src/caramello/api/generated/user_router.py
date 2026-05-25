from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.user import User, UserRead, UserCreate, UserUpdate

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/", response_model=UserRead)
async def create_user(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    db_obj = User.model_validate(user_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select(User).offset(offset).limit(limit))
    return result.all()


@router.get("/{uuid}", response_model=UserRead)
async def read_user(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{uuid}", response_model=UserRead)
async def update_user(uuid: UUID, user_in: UserUpdate, session: AsyncSession = Depends(get_session)):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")

    hero_data = user_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)

    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{uuid}")
async def delete_user(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}
