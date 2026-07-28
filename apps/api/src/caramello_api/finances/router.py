from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.finances.models import Account, Category, FinancialEntry, Movement, Subcategory
from caramello_api.finances.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    FinancialEntryCreate,
    FinancialEntryRead,
    FinancialEntryUpdate,
    MovementCreate,
    MovementRead,
    MovementUpdate,
    SubcategoryCreate,
    SubcategoryRead,
    SubcategoryUpdate,
)
from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
from caramello_api.users.models import User

account_router = APIRouter(prefix="/finances/account", tags=["Account"])


@account_router.post("/", response_model=AccountRead)
async def create_account(
    account_in: AccountCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Account:
    db_obj = Account(**account_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@account_router.get("/", response_model=list[AccountRead])
async def read_accounts(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Account]:
    result = await session.execute(select(Account).offset(offset).limit(limit))
    return list(result.scalars().all())


@account_router.get("/{uuid}", response_model=AccountRead)
async def read_account(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Account:
    statement = select(Account).where(Account.uuid == uuid)
    result = await session.execute(statement)
    account = result.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@account_router.patch("/{uuid}", response_model=AccountRead)
async def update_account(
    uuid: UUID,
    account_in: AccountUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Account:
    statement = select(Account).where(Account.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Account not found")
    update_data = account_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@account_router.delete("/{uuid}")
async def delete_account(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(Account).where(Account.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Account not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


movement_router = APIRouter(prefix="/finances/movement", tags=["Movement"])


@movement_router.post("/", response_model=MovementRead)
async def create_movement(
    movement_in: MovementCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Movement:
    db_obj = Movement(**movement_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@movement_router.get("/", response_model=list[MovementRead])
async def read_movements(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Movement]:
    result = await session.execute(select(Movement).offset(offset).limit(limit))
    return list(result.scalars().all())


@movement_router.get("/{uuid}", response_model=MovementRead)
async def read_movement(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Movement:
    statement = select(Movement).where(Movement.uuid == uuid)
    result = await session.execute(statement)
    movement = result.scalars().first()
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    return movement


@movement_router.patch("/{uuid}", response_model=MovementRead)
async def update_movement(
    uuid: UUID,
    movement_in: MovementUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Movement:
    statement = select(Movement).where(Movement.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Movement not found")
    update_data = movement_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@movement_router.delete("/{uuid}")
async def delete_movement(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(Movement).where(Movement.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Movement not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


financialentry_router = APIRouter(prefix="/finances/financial-entry", tags=["FinancialEntry"])


@financialentry_router.post("/", response_model=FinancialEntryRead)
async def create_financialentry(
    financialentry_in: FinancialEntryCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FinancialEntry:
    db_obj = FinancialEntry(**financialentry_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@financialentry_router.get("/", response_model=list[FinancialEntryRead])
async def read_financialentrys(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[FinancialEntry]:
    result = await session.execute(select(FinancialEntry).offset(offset).limit(limit))
    return list(result.scalars().all())


@financialentry_router.get("/{uuid}", response_model=FinancialEntryRead)
async def read_financialentry(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FinancialEntry:
    statement = select(FinancialEntry).where(FinancialEntry.uuid == uuid)
    result = await session.execute(statement)
    financialentry = result.scalars().first()
    if not financialentry:
        raise HTTPException(status_code=404, detail="FinancialEntry not found")
    return financialentry


@financialentry_router.patch("/{uuid}", response_model=FinancialEntryRead)
async def update_financialentry(
    uuid: UUID,
    financialentry_in: FinancialEntryUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FinancialEntry:
    statement = select(FinancialEntry).where(FinancialEntry.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FinancialEntry not found")
    update_data = financialentry_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@financialentry_router.delete("/{uuid}")
async def delete_financialentry(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(FinancialEntry).where(FinancialEntry.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="FinancialEntry not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


category_router = APIRouter(prefix="/finances/category", tags=["Category"])


@category_router.post("/", response_model=CategoryRead)
async def create_category(
    category_in: CategoryCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Category:
    db_obj = Category(**category_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@category_router.get("/", response_model=list[CategoryRead])
async def read_categorys(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Category]:
    result = await session.execute(select(Category).offset(offset).limit(limit))
    return list(result.scalars().all())


@category_router.get("/{uuid}", response_model=CategoryRead)
async def read_category(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Category:
    statement = select(Category).where(Category.uuid == uuid)
    result = await session.execute(statement)
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@category_router.patch("/{uuid}", response_model=CategoryRead)
async def update_category(
    uuid: UUID,
    category_in: CategoryUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Category:
    statement = select(Category).where(Category.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@category_router.delete("/{uuid}")
async def delete_category(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(Category).where(Category.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Category not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


subcategory_router = APIRouter(prefix="/finances/subcategory", tags=["Subcategory"])


@subcategory_router.post("/", response_model=SubcategoryRead)
async def create_subcategory(
    subcategory_in: SubcategoryCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Subcategory:
    db_obj = Subcategory(**subcategory_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@subcategory_router.get("/", response_model=list[SubcategoryRead])
async def read_subcategorys(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Subcategory]:
    result = await session.execute(select(Subcategory).offset(offset).limit(limit))
    return list(result.scalars().all())


@subcategory_router.get("/{uuid}", response_model=SubcategoryRead)
async def read_subcategory(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Subcategory:
    statement = select(Subcategory).where(Subcategory.uuid == uuid)
    result = await session.execute(statement)
    subcategory = result.scalars().first()
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    return subcategory


@subcategory_router.patch("/{uuid}", response_model=SubcategoryRead)
async def update_subcategory(
    uuid: UUID,
    subcategory_in: SubcategoryUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Subcategory:
    statement = select(Subcategory).where(Subcategory.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    update_data = subcategory_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@subcategory_router.delete("/{uuid}")
async def delete_subcategory(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select(Subcategory).where(Subcategory.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Subcategory not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


router = APIRouter()
router.include_router(account_router)
router.include_router(movement_router)
router.include_router(financialentry_router)
router.include_router(category_router)
router.include_router(subcategory_router)
