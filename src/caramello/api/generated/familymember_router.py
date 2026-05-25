from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.familymember import FamilyMember

router = APIRouter(prefix="/family_member", tags=["FamilyMember"])


@router.get("/", response_model=list[FamilyMember])
async def read_familymembers(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select(FamilyMember).offset(offset).limit(limit))
    return result.all()


@router.get("/{user_id}", response_model=FamilyMember)
async def read_familymember(user_id: int, session: AsyncSession = Depends(get_session)):
    statement = select(FamilyMember).where(FamilyMember.user_id == user_id)
    result = await session.exec(statement)
    familymember = result.first()
    if not familymember:
        raise HTTPException(status_code=404, detail="FamilyMember not found")
    return familymember
