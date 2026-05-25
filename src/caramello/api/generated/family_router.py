from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.family import Family, FamilyRead, FamilyCreate, FamilyUpdate

router = APIRouter(prefix="/family", tags=["Family"])


@router.post("/", response_model=FamilyRead)
async def create_family(family_in: FamilyCreate, session: AsyncSession = Depends(get_session)):
    db_obj = Family.model_validate(family_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[FamilyRead])
async def read_familys(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select(Family).offset(offset).limit(limit))
    return result.all()


@router.get("/{uuid}", response_model=FamilyRead)
async def read_family(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    family = result.first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.patch("/{uuid}", response_model=FamilyRead)
async def update_family(uuid: UUID, family_in: FamilyUpdate, session: AsyncSession = Depends(get_session)):
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")

    hero_data = family_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)

    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{uuid}")
async def delete_family(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")

    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}
