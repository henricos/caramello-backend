from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.finances.models import (
    Account,
    AccountCreate,
    AccountRead,
    AccountUpdate,
    Category,
    CategoryCreate,
    CategoryRead,
    CategoryUpdate,
    FinancialEntry,
    FinancialEntryCreate,
    FinancialEntryRead,
    FinancialEntryUpdate,
    Movement,
    MovementCreate,
    MovementRead,
    MovementUpdate,
    Subcategory,
    SubcategoryCreate,
    SubcategoryRead,
    SubcategoryUpdate,
)
from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.users.models import User

account_router = APIRouter(prefix="/finances/account", tags=["Account"])


@account_router.post("/", response_model=AccountRead)
async def create_account(
    account_in: AccountCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Account:
    db_obj = Account.model_validate(account_in)
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
    result = await session.exec(select(Account).offset(offset).limit(limit))
    return list(result.all())


@account_router.get("/{uuid}", response_model=AccountRead)
async def read_account(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Account:
    statement = select(Account).where(Account.uuid == uuid)
    result = await session.exec(statement)
    account = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    db_obj = Movement.model_validate(movement_in)
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
    result = await session.exec(select(Movement).offset(offset).limit(limit))
    return list(result.all())


@movement_router.get("/{uuid}", response_model=MovementRead)
async def read_movement(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Movement:
    statement = select(Movement).where(Movement.uuid == uuid)
    result = await session.exec(statement)
    movement = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Movement not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}


financialentry_router = APIRouter(
    prefix="/finances/financial-entry", tags=["FinancialEntry"]
)


@financialentry_router.post("/", response_model=FinancialEntryRead)
async def create_financialentry(
    financialentry_in: FinancialEntryCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FinancialEntry:
    db_obj = FinancialEntry.model_validate(financialentry_in)
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
    result = await session.exec(select(FinancialEntry).offset(offset).limit(limit))
    return list(result.all())


@financialentry_router.get("/{uuid}", response_model=FinancialEntryRead)
async def read_financialentry(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> FinancialEntry:
    statement = select(FinancialEntry).where(FinancialEntry.uuid == uuid)
    result = await session.exec(statement)
    financialentry = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    db_obj = Category.model_validate(category_in)
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
    result = await session.exec(select(Category).offset(offset).limit(limit))
    return list(result.all())


@category_router.get("/{uuid}", response_model=CategoryRead)
async def read_category(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Category:
    statement = select(Category).where(Category.uuid == uuid)
    result = await session.exec(statement)
    category = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    db_obj = Subcategory.model_validate(subcategory_in)
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
    result = await session.exec(select(Subcategory).offset(offset).limit(limit))
    return list(result.all())


@subcategory_router.get("/{uuid}", response_model=SubcategoryRead)
async def read_subcategory(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Subcategory:
    statement = select(Subcategory).where(Subcategory.uuid == uuid)
    result = await session.exec(statement)
    subcategory = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
    result = await session.exec(statement)
    db_obj = result.first()
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
