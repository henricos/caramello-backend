# CARAMELLO-GENERATED: implemented
"""Operações de negócio do domínio finances — Phase 7.

Cobre:
  - ACC-01/02/03: CRUD de Account scoped por família
  - CAT-01/02/04: CRUD de Category e Subcategory scoped por família
  - AUTH-FIN-01/02: 401/403 via get_current_user + _require_family_access
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.finances.models import Account, Category, Subcategory
from caramello.families.models import Family
from caramello.shared.auth import get_current_user, _require_family_access
from caramello.shared.database import get_session
from caramello.users.models import User

router = APIRouter(prefix="/finances", tags=["Finances"])


# ---------------------------------------------------------------------------
# Schemas públicos — NÃO usam os schemas gerados (AccountRead, CategoryRead)
# porque esses expõem family_id/category_id internos.
# ---------------------------------------------------------------------------


class AccountCreatePublic(BaseModel):
    family_uuid: UUID
    name: str = PydanticField(max_length=100)
    type: Literal["corrente", "poupanca", "cartao", "investimento"]
    currency: str = PydanticField(default="BRL", max_length=3)


class AccountReadPublic(BaseModel):
    uuid: UUID
    family_uuid: UUID
    name: str
    type: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AccountUpdatePublic(BaseModel):
    name: str | None = PydanticField(default=None, max_length=100)
    type: Literal["corrente", "poupanca", "cartao", "investimento"] | None = None
    currency: str | None = PydanticField(default=None, max_length=3)
    is_active: bool | None = None


class CategoryCreatePublic(BaseModel):
    family_uuid: UUID
    name: str = PydanticField(max_length=100)


class CategoryReadPublic(BaseModel):
    uuid: UUID
    family_uuid: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class CategoryUpdatePublic(BaseModel):
    name: str | None = PydanticField(default=None, max_length=100)


class SubcategoryCreatePublic(BaseModel):
    category_uuid: UUID
    name: str = PydanticField(max_length=100)


class SubcategoryReadPublic(BaseModel):
    uuid: UUID
    category_uuid: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class SubcategoryUpdatePublic(BaseModel):
    name: str | None = PydanticField(default=None, max_length=100)


# ---------------------------------------------------------------------------
# Account — ACC-01/02/03, T-07-01/02/03/04
# ---------------------------------------------------------------------------


@router.post("/accounts", response_model=AccountReadPublic, status_code=201)
async def create_account(
    account_in: AccountCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    """ACC-01: Cria conta bancária scoped por família.

    T-07-03: payload aceita apenas family_uuid (UUID público); family_id
    é resolvido no backend. T-07-04: Depends(get_current_user) obrigatório.
    """
    # Resolver UUID público → objeto ORM (404 se não encontrado)
    family_result = await session.exec(
        select(Family).where(Family.uuid == account_in.family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    # Verificar membership — T-07-02: 403 para não-membro (IDOR mitigado)
    await _require_family_access(family.id, current_user, session)

    # Persistir com ID interno (nunca com UUID de entrada)
    db_account = Account(
        family_id=family.id,
        name=account_in.name,
        type=account_in.type,
        currency=account_in.currency,
    )
    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)

    # T-07-01: retornar schema público (sem id, sem family_id)
    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=account_in.family_uuid,
        name=db_account.name,
        type=db_account.type,
        currency=db_account.currency,
        is_active=db_account.is_active,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
    )


@router.get("/accounts", response_model=list[AccountReadPublic])
async def list_accounts(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[AccountReadPublic]:
    """ACC-02: Lista contas da família — family_uuid obrigatório como query param.

    AUTH-FIN-02: verificação de membership antes de filtrar.
    """
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    await _require_family_access(family.id, current_user, session)

    accounts_result = await session.exec(
        select(Account).where(Account.family_id == family.id)
    )
    accounts = list(accounts_result.all())
    return [
        AccountReadPublic(
            uuid=a.uuid,
            family_uuid=family_uuid,
            name=a.name,
            type=a.type,
            currency=a.currency,
            is_active=a.is_active,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in accounts
    ]


@router.get("/accounts/{account_uuid}", response_model=AccountReadPublic)
async def get_account(
    account_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    """ACC-02: Detalhe de uma conta pelo UUID público."""
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Resolver Family para obter UUID público e verificar acesso
    family_result = await session.exec(
        select(Family).where(Family.id == db_account.family_id)
    )
    family = family_result.first()
    await _require_family_access(db_account.family_id, current_user, session)

    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=family.uuid if family else account_uuid,
        name=db_account.name,
        type=db_account.type,
        currency=db_account.currency,
        is_active=db_account.is_active,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
    )


@router.patch("/accounts/{account_uuid}", response_model=AccountReadPublic)
async def update_account(
    account_uuid: UUID,
    account_in: AccountUpdatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    """ACC-02/03: Atualiza ou arquiva (is_active=false) uma conta.

    ACC-03: arquivamento via is_active=false — NÃO usa session.delete.
    Pitfall #4: updated_at definido manualmente (sem onupdate automático).
    """
    # Lookup Account por UUID público
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Resolver Family para obter UUID público
    family_result = await session.exec(
        select(Family).where(Family.id == db_account.family_id)
    )
    family = family_result.first()

    # Verificar membership
    await _require_family_access(db_account.family_id, current_user, session)

    # Aplicar apenas campos fornecidos (exclude_none)
    update_data = account_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_account, key, value)

    # Pitfall #4: updated_at não tem onupdate automático — definir manualmente
    db_account.updated_at = datetime.now(timezone.utc)

    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)

    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=family.uuid if family else account_uuid,
        name=db_account.name,
        type=db_account.type,
        currency=db_account.currency,
        is_active=db_account.is_active,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
    )


# ---------------------------------------------------------------------------
# Category — CAT-01/02/04
# ---------------------------------------------------------------------------


@router.post("/categories", response_model=CategoryReadPublic, status_code=201)
async def create_category(
    category_in: CategoryCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CategoryReadPublic:
    """CAT-01: Cria categoria de nível 1 scoped por família."""
    family_result = await session.exec(
        select(Family).where(Family.uuid == category_in.family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    await _require_family_access(family.id, current_user, session)

    db_category = Category(
        family_id=family.id,
        name=category_in.name,
    )
    session.add(db_category)
    await session.commit()
    await session.refresh(db_category)

    return CategoryReadPublic(
        uuid=db_category.uuid,
        family_uuid=category_in.family_uuid,
        name=db_category.name,
        created_at=db_category.created_at,
        updated_at=db_category.updated_at,
    )


@router.get("/categories", response_model=list[CategoryReadPublic])
async def list_categories(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CategoryReadPublic]:
    """CAT-04: Lista categorias da família — family_uuid obrigatório."""
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    await _require_family_access(family.id, current_user, session)

    categories_result = await session.exec(
        select(Category).where(Category.family_id == family.id)
    )
    categories = list(categories_result.all())
    return [
        CategoryReadPublic(
            uuid=c.uuid,
            family_uuid=family_uuid,
            name=c.name,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in categories
    ]


@router.get("/categories/{category_uuid}", response_model=CategoryReadPublic)
async def get_category(
    category_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CategoryReadPublic:
    """CAT-04: Detalhe de categoria pelo UUID público."""
    result = await session.exec(
        select(Category).where(Category.uuid == category_uuid)
    )
    db_category = result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    family_result = await session.exec(
        select(Family).where(Family.id == db_category.family_id)
    )
    family = family_result.first()
    await _require_family_access(db_category.family_id, current_user, session)

    return CategoryReadPublic(
        uuid=db_category.uuid,
        family_uuid=family.uuid if family else category_uuid,
        name=db_category.name,
        created_at=db_category.created_at,
        updated_at=db_category.updated_at,
    )



@router.patch("/categories/{category_uuid}", response_model=CategoryReadPublic)
async def update_category(
    category_uuid: UUID,
    category_in: CategoryUpdatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CategoryReadPublic:
    """CAT-04: Atualiza categoria.

    Pitfall #4: updated_at definido manualmente.
    """
    result = await session.exec(
        select(Category).where(Category.uuid == category_uuid)
    )
    db_category = result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    family_result = await session.exec(
        select(Family).where(Family.id == db_category.family_id)
    )
    family = family_result.first()

    await _require_family_access(db_category.family_id, current_user, session)

    update_data = category_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    db_category.updated_at = datetime.now(timezone.utc)

    session.add(db_category)
    await session.commit()
    await session.refresh(db_category)

    return CategoryReadPublic(
        uuid=db_category.uuid,
        family_uuid=family.uuid if family else category_uuid,
        name=db_category.name,
        created_at=db_category.created_at,
        updated_at=db_category.updated_at,
    )


# ---------------------------------------------------------------------------
# Subcategory — CAT-02/04, D-12/D-13
# ---------------------------------------------------------------------------


@router.post("/subcategory", response_model=SubcategoryReadPublic, status_code=201)
async def create_subcategory(
    subcategory_in: SubcategoryCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SubcategoryReadPublic:
    """CAT-02: Cria subcategoria de nível 2 via category_uuid.

    D-13: category_uuid é parâmetro público; backend resolve para category_id.
    Acesso verificado via category.family_id.
    """
    # Resolver category_uuid → Category (404 se inválido)
    category_result = await session.exec(
        select(Category).where(Category.uuid == subcategory_in.category_uuid)
    )
    db_category = category_result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    # Resolver Family pelo category.family_id (para obter UUID público)
    family_result = await session.exec(
        select(Family).where(Family.id == db_category.family_id)
    )
    family = family_result.first()

    # Verificar membership via category.family_id
    await _require_family_access(db_category.family_id, current_user, session)

    db_subcategory = Subcategory(
        category_id=db_category.id,
        name=subcategory_in.name,
    )
    session.add(db_subcategory)
    await session.commit()
    await session.refresh(db_subcategory)

    return SubcategoryReadPublic(
        uuid=db_subcategory.uuid,
        category_uuid=subcategory_in.category_uuid,
        name=db_subcategory.name,
        created_at=db_subcategory.created_at,
        updated_at=db_subcategory.updated_at,
    )


@router.get("/subcategory", response_model=list[SubcategoryReadPublic])
async def list_subcategories(
    category_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[SubcategoryReadPublic]:
    """CAT-04: Lista subcategorias; category_uuid obrigatório (D-12)."""
    category_result = await session.exec(
        select(Category).where(Category.uuid == category_uuid)
    )
    db_category = category_result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    await _require_family_access(db_category.family_id, current_user, session)

    subcategories_result = await session.exec(
        select(Subcategory).where(Subcategory.category_id == db_category.id)
    )
    subcategories = list(subcategories_result.all())
    return [
        SubcategoryReadPublic(
            uuid=s.uuid,
            category_uuid=category_uuid,
            name=s.name,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in subcategories
    ]


@router.get("/subcategory/{subcategory_uuid}", response_model=SubcategoryReadPublic)
async def get_subcategory(
    subcategory_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SubcategoryReadPublic:
    """CAT-04: Detalhe de subcategoria pelo UUID público."""
    result = await session.exec(
        select(Subcategory).where(Subcategory.uuid == subcategory_uuid)
    )
    db_subcategory = result.first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")

    category_result = await session.exec(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = category_result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    await _require_family_access(db_category.family_id, current_user, session)

    return SubcategoryReadPublic(
        uuid=db_subcategory.uuid,
        category_uuid=db_category.uuid,
        name=db_subcategory.name,
        created_at=db_subcategory.created_at,
        updated_at=db_subcategory.updated_at,
    )


@router.patch("/subcategory/{subcategory_uuid}", response_model=SubcategoryReadPublic)
async def update_subcategory(
    subcategory_uuid: UUID,
    subcategory_in: SubcategoryUpdatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SubcategoryReadPublic:
    """CAT-04: Atualiza subcategoria.

    Pitfall #4: updated_at definido manualmente.
    """
    result = await session.exec(
        select(Subcategory).where(Subcategory.uuid == subcategory_uuid)
    )
    db_subcategory = result.first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")

    category_result = await session.exec(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = category_result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    await _require_family_access(db_category.family_id, current_user, session)

    update_data = subcategory_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_subcategory, key, value)
    db_subcategory.updated_at = datetime.now(timezone.utc)

    session.add(db_subcategory)
    await session.commit()
    await session.refresh(db_subcategory)

    return SubcategoryReadPublic(
        uuid=db_subcategory.uuid,
        category_uuid=db_category.uuid,
        name=db_subcategory.name,
        created_at=db_subcategory.created_at,
        updated_at=db_subcategory.updated_at,
    )
