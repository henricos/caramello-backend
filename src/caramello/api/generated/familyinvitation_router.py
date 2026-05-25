from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.familyinvitation import FamilyInvitation, FamilyInvitationRead, FamilyInvitationCreate, FamilyInvitationUpdate

router = APIRouter(prefix="/family_invitation", tags=["FamilyInvitation"])


@router.post("/", response_model=FamilyInvitationRead)
async def create_familyinvitation(familyinvitation_in: FamilyInvitationCreate, session: AsyncSession = Depends(get_session)):
    db_obj = FamilyInvitation.model_validate(familyinvitation_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[FamilyInvitationRead])
async def read_familyinvitations(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select(FamilyInvitation).offset(offset).limit(limit))
    return result.all()


@router.get("/{uuid}", response_model=FamilyInvitationRead)
async def read_familyinvitation(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    familyinvitation = result.first()
    if not familyinvitation:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")
    return familyinvitation


@router.patch("/{uuid}", response_model=FamilyInvitationRead)
async def update_familyinvitation(uuid: UUID, familyinvitation_in: FamilyInvitationUpdate, session: AsyncSession = Depends(get_session)):
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")

    hero_data = familyinvitation_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)

    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{uuid}")
async def delete_familyinvitation(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(FamilyInvitation).where(FamilyInvitation.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FamilyInvitation not found")

    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}
