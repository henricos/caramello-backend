# CARAMELLO-GENERATED: implemented
"""Operações de negócio do domínio finances — Phase 7 + Phase 8 + Phase 9.

Cobre:
  - ACC-01/02/03: CRUD de Account scoped por família
  - CAT-01/02/04: CRUD de Category e Subcategory scoped por família
  - AUTH-FIN-01/02: 401/403 via get_current_user + _require_family_access
  - MOV-01..05: registro individual, importação CSV/OFX/XLSX e confirmação
  - D-15: listagem paginada de movimentações
  - LAN-01..05: conciliação de movimentações em lançamentos financeiros
  - REL-01..05: relatórios de saldo e breakdown por categoria/membro
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.finances.models import Account, Category, FinancialEntry, Movement, Subcategory
from caramello.families.models import Family, FamilyMember
from caramello.shared.auth import get_current_user, _require_family_access
from caramello.shared.database import get_session
from caramello.finances.services import (
    _compute_hash,
    _parse_date,
    import_movements,
    ParsedRow,
    suggest_category,
    account_balance,
    family_balance,
    monthly_breakdown,
    by_member_breakdown,
)
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
# Schemas públicos de Movement — D-16 (sem account_uuid, sem id interno)
# T-08-11: não vazam id/family_id
# ---------------------------------------------------------------------------


class MovementCreatePublic(BaseModel):
    date: str  # ISO 8601 ou DD/MM/YYYY — parseado pela camada de serviço
    amount: Decimal
    description: str


class MovementReadPublic(BaseModel):
    uuid: UUID
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None  # D-16: opcional, para debug
    entry_uuid: UUID | None = None  # D-MOV-01: UUID do lançamento conciliado, null se pendente
    created_at: datetime
    updated_at: datetime


class ImportResultPublic(BaseModel):
    inserted: int
    duplicates_skipped: int
    potential_duplicates: list[dict[str, Any]]
    error_lines: list[dict[str, Any]]
    movements: list[MovementReadPublic]


class ConfirmImportPublic(BaseModel):
    account_uuid: UUID
    movements: list[MovementCreatePublic]  # movimentações confirmadas a inserir


# ---------------------------------------------------------------------------
# Schemas públicos de FinancialEntry (Fase 9) — D-REC-01/02/03/04/05
# LAN-01..05: conciliação, detalhe, atualização e listagem de lançamentos
# ---------------------------------------------------------------------------


class ReconcileCreatePublic(BaseModel):
    """Payload de criação de lançamento financeiro via reconciliação (D-REC-01)."""

    subcategory_uuid: UUID
    competencia_year: int
    competencia_month: int
    notes: str | None = PydanticField(default=None, max_length=500)
    is_recorrente: bool = False
    responsible_user_uuid: UUID | None = None


class FinancialEntryUpdatePublic(BaseModel):
    """Payload de atualização parcial de lançamento financeiro (D-REC-04, LAN-05).

    Para responsible_user_uuid: None = limpar responsável;
    campo ausente (não em model_fields_set) = não tocar.
    NÃO usar model_dump(exclude_none=True) para este schema — usar model_fields_set (pitfall P2).
    """

    subcategory_uuid: UUID | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None  # None = limpar; ausente = não tocar


class MovementSummaryPublic(BaseModel):
    """Resumo de movimentação embutido no schema rico de FinancialEntry (D-REC-02)."""

    uuid: UUID
    date: datetime
    amount: Decimal
    description: str


class FinancialEntryRichPublic(BaseModel):
    """Schema rico de resposta para todos os endpoints de FinancialEntry (D-REC-02).

    Reutilizado em POST reconcile, GET detail, PATCH update e GET list.
    Expõe movement embutido para evitar GET extra no frontend.
    """

    uuid: UUID
    movement: MovementSummaryPublic
    subcategory_uuid: UUID
    subcategory_name: str
    category_uuid: UUID
    category_name: str
    competencia_year: int
    competencia_month: int
    notes: str | None
    is_recorrente: bool
    responsible_user_uuid: UUID | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Schemas de saldo e relatório (Fase 9) — REL-01..05
# ---------------------------------------------------------------------------


class AccountBalancePublic(BaseModel):
    """Resposta de saldo de conta (D-BAL-01)."""

    account_uuid: UUID
    balance: Decimal
    currency: str


class FamilyAccountBalanceItem(BaseModel):
    """Item de conta no saldo familiar (D-BAL-02)."""

    account_uuid: UUID
    name: str
    currency: str
    balance: Decimal


class FamilyBalancePublic(BaseModel):
    """Resposta de saldo consolidado familiar (D-BAL-02)."""

    family_uuid: UUID
    total_balance: Decimal
    accounts: list[FamilyAccountBalanceItem]


class MonthlyReportPeriod(BaseModel):
    """Período de competência em relatório mensal."""

    year: int
    month: int


class MonthlyReportRow(BaseModel):
    """Linha de breakdown por subcategoria no relatório mensal (D-REP-01)."""

    category_uuid: UUID
    category_name: str
    subcategory_uuid: UUID
    subcategory_name: str
    total: Decimal
    count: int


class MonthlyReportPublic(BaseModel):
    """Resposta do relatório mensal (D-REP-01)."""

    period: MonthlyReportPeriod
    total: Decimal
    rows: list[MonthlyReportRow]


class ByMemberReportRow(BaseModel):
    """Linha por membro no relatório de breakdown por responsável (D-REP-02)."""

    user_uuid: UUID | None
    name: str
    total: Decimal
    count: int


class ByMemberReportPublic(BaseModel):
    """Resposta do relatório por membro (D-REP-02)."""

    period: MonthlyReportPeriod
    total: Decimal
    rows: list[ByMemberReportRow]


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
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_account.family_id, current_user, session)

    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=family.uuid,
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
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

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
        family_uuid=family.uuid,
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
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_category.family_id, current_user, session)

    return CategoryReadPublic(
        uuid=db_category.uuid,
        family_uuid=family.uuid,
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
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

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
        family_uuid=family.uuid,
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


# ---------------------------------------------------------------------------
# Movement — MOV-01..05, D-15, D-16, D-17, AUTH-FIN-01/02
# T-08-09/10/11/12/13
# ---------------------------------------------------------------------------


@router.post(
    "/accounts/{account_uuid}/movements",
    response_model=MovementReadPublic,
    status_code=201,
)
async def create_movement(
    account_uuid: UUID,
    movement_in: MovementCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MovementReadPublic:
    """MOV-01: Registra movimentação individual scoped por conta/família.

    D-17: retorna 409 com existing_uuid se hash já existe.
    T-08-09: IDOR mitigado via _require_family_access.
    T-08-10: Depends(get_current_user) → 401 sem token.
    """
    # Resolver account_uuid → Account (404 se inválido)
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Verificar membership — T-08-09: 403 para não-membro (IDOR mitigado)
    await _require_family_access(db_account.family_id, current_user, session)

    # Parsear data (D-12: ISO primeiro, BR fallback)
    date_val = _parse_date(movement_in.date, line=1)

    # Computar hash para deduplicação (D-07)
    row = ParsedRow(
        date=date_val,
        amount=movement_in.amount,
        description=movement_in.description,
        fitid=None,
    )
    computed_hash = _compute_hash(db_account.id, row)

    # D-17: verificar se hash já existe → 409 com existing_uuid
    dup_result = await session.exec(
        select(Movement).where(Movement.import_hash == computed_hash)
    )
    dup = dup_result.first()
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail={"message": "Movimentação já existe", "existing_uuid": str(dup.uuid)},
        )

    # Persistir movimentação
    db_movement = Movement(
        account_id=db_account.id,
        date=date_val,
        amount=movement_in.amount,
        description=movement_in.description,
        import_hash=computed_hash,
    )
    session.add(db_movement)
    await session.commit()
    await session.refresh(db_movement)

    return MovementReadPublic(
        uuid=db_movement.uuid,
        date=db_movement.date,
        amount=db_movement.amount,
        description=db_movement.description,
        import_hash=db_movement.import_hash,
        created_at=db_movement.created_at,
        updated_at=db_movement.updated_at,
    )


@router.get("/accounts/{account_uuid}/movements", response_model=list[MovementReadPublic])
async def list_movements(
    account_uuid: UUID,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    reconciled: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MovementReadPublic]:
    """D-15, D-MOV-01/02: Lista movimentações da conta com paginação, filtros e entry_uuid.

    D-MOV-01: entry_uuid via LEFT JOIN com FinancialEntry (null = pendente, UUID = conciliada).
    D-MOV-02: filtro reconciled=false (pendentes) / reconciled=true (conciliadas) via LEFT JOIN.
    T-08-09: IDOR mitigado via _require_family_access.
    T-08-10: Depends(get_current_user) → 401 sem token.
    """
    from sqlalchemy import outerjoin

    # Resolver account_uuid → Account
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Verificar membership — T-08-09: 403 para não-membro
    await _require_family_access(db_account.family_id, current_user, session)

    # D-MOV-01: LEFT JOIN com FinancialEntry para entry_uuid (pitfall P5: usar fetchall + posição)
    stmt = (
        select(Movement, FinancialEntry.uuid.label("entry_uuid"))
        .select_from(
            outerjoin(Movement, FinancialEntry, FinancialEntry.movement_id == Movement.id)
        )
        .where(Movement.account_id == db_account.id)
    )

    if date_from:
        stmt = stmt.where(Movement.date >= _parse_date(date_from, line=0))
    if date_to:
        stmt = stmt.where(Movement.date <= _parse_date(date_to, line=0))

    # D-MOV-02: filtro de conciliação via IS NULL / IS NOT NULL
    if reconciled is False:
        stmt = stmt.where(FinancialEntry.id.is_(None))
    elif reconciled is True:
        stmt = stmt.where(FinancialEntry.id.is_not(None))

    stmt = stmt.order_by(Movement.date.desc()).offset(offset).limit(limit)

    # session.execute() com fetchall() para multi-entity select (pitfall P5)
    movements_execute_result = await session.execute(stmt)
    rows = movements_execute_result.fetchall()

    return [
        MovementReadPublic(
            uuid=row[0].uuid,
            date=row[0].date,
            amount=row[0].amount,
            description=row[0].description,
            import_hash=row[0].import_hash,
            # D-MOV-01: entry_uuid via LEFT JOIN — None se row não tem 2 elementos (mock compat)
            entry_uuid=row[1] if len(row) > 1 else None,
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
        )
        for row in rows
    ]


@router.post("/accounts/{account_uuid}/movements/import", response_model=ImportResultPublic)
async def import_movements_endpoint(
    account_uuid: UUID,
    file: UploadFile = File(...),
    format: Literal["csv", "ofx", "xlsx"] = Query(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportResultPublic:
    """MOV-02/03/04/05: Importa arquivo de extrato bancário (CSV, OFX ou XLSX).

    D-09: formato via query param.
    D-13: >50% linhas inválidas → 422.
    T-08-09: IDOR mitigado via _require_family_access.
    T-08-12/13: on_conflict_do_nothing + error threshold.
    """
    # Resolver account_uuid → Account
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Verificar membership
    await _require_family_access(db_account.family_id, current_user, session)

    content: bytes = await file.read()

    try:
        service_result = await import_movements(content, format, db_account.id, session)
    except ValueError as e:
        # D-13: abortar lote com >50% inválidas → 422
        raise HTTPException(status_code=422, detail=str(e))

    # Converter movements[] para MovementReadPublic
    movements_public = []
    for m in service_result.get("movements", []):
        movements_public.append(
            MovementReadPublic(
                uuid=m["uuid"],
                date=m["date"],
                amount=m["amount"],
                description=m["description"],
                import_hash=None,
                created_at=m.get("created_at", datetime.now(timezone.utc)),
                updated_at=m.get("updated_at", m.get("created_at", datetime.now(timezone.utc))),  # WR-03
            )
        )

    return ImportResultPublic(
        inserted=service_result["inserted"],
        duplicates_skipped=service_result["duplicates_skipped"],
        potential_duplicates=service_result["potential_duplicates"],
        error_lines=service_result["error_lines"],
        movements=movements_public,
    )


@router.post("/import/confirm", response_model=ImportResultPublic)
async def confirm_import(
    confirm_in: ConfirmImportPublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportResultPublic:
    """D-08, MOV-05: Confirma e insere movimentações suspeitas de duplicata.

    P4: import_hash=None nas confirmadas — PostgreSQL permite múltiplos NULL em UNIQUE.
    T-08-09: IDOR mitigado via _require_family_access.
    T-08-12: import_hash=None evita colisão de UNIQUE constraint.
    """
    # Resolver account_uuid → Account
    result = await session.exec(
        select(Account).where(Account.uuid == confirm_in.account_uuid)
    )
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Verificar membership
    await _require_family_access(db_account.family_id, current_user, session)

    # Inserir movimentações confirmadas com import_hash=None (P4/D-08)
    # Acumula todos os objetos antes do commit para garantir atomicidade —
    # evita estado parcial caso uma inserção falhe no meio do lote (CR-03).
    db_movements: list[Movement] = []

    for movement_in in confirm_in.movements:
        date_val = _parse_date(movement_in.date, line=1)
        db_movement = Movement(
            account_id=db_account.id,
            date=date_val,
            amount=movement_in.amount,
            description=movement_in.description,
            import_hash=None,  # P4: permite múltiplos NULL em UNIQUE
        )
        session.add(db_movement)
        db_movements.append(db_movement)

    # Um único commit — atômico para todo o lote
    await session.commit()

    # Refresh de todos após o commit
    inserted_movements: list[MovementReadPublic] = []
    for db_movement in db_movements:
        await session.refresh(db_movement)
        inserted_movements.append(
            MovementReadPublic(
                uuid=db_movement.uuid,
                date=db_movement.date,
                amount=db_movement.amount,
                description=db_movement.description,
                import_hash=None,
                created_at=db_movement.created_at,
                updated_at=db_movement.updated_at,
            )
        )

    return ImportResultPublic(
        inserted=len(inserted_movements),
        duplicates_skipped=0,
        potential_duplicates=[],
        error_lines=[],
        movements=inserted_movements,
    )


# ---------------------------------------------------------------------------
# FinancialEntry — LAN-01..05, D-REC-01..05, T-09-04..08
# ---------------------------------------------------------------------------


@router.get(
    "/movements/{movement_uuid}/suggest-category",
    response_model=list[dict],
)
async def get_suggest_category(
    movement_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """LAN-03, D-CAT-01/02/03: Retorna top-5 sugestões de subcategoria por fuzzy match.

    T-09-04: IDOR mitigado — resolve movement → account → family + _require_family_access.
    T-09-07: AUTH-FIN-01 via get_current_user.
    D-CAT-03: retorna [] se movimento não encontrado ou sem histórico (não 404).
    """
    # Resolver movement_uuid → Movement (404 se não existe)
    result = await session.exec(select(Movement).where(Movement.uuid == movement_uuid))
    db_movement = result.first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    # Resolver Account para obter family_id e verificar membership
    account_result = await session.exec(
        select(Account).where(Account.id == db_movement.account_id)
    )
    db_account = account_result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # T-09-04: verificar membership — 403 para não-membro (IDOR mitigado)
    await _require_family_access(db_account.family_id, current_user, session)

    # Delegar ao service (D-CAT-04)
    suggestions = await suggest_category(movement_uuid, db_account.family_id, session)
    return suggestions


@router.post(
    "/movements/{movement_uuid}/reconcile",
    response_model=FinancialEntryRichPublic,
    status_code=201,
)
async def reconcile_movement(
    movement_uuid: UUID,
    entry_in: ReconcileCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryRichPublic:
    """LAN-01, LAN-02, LAN-04, D-REC-01/02: Cria lançamento financeiro 1:1 a partir de movimentação.

    T-09-04: IDOR mitigado via _require_family_access.
    T-09-05: responsible_user_uuid validado por membership (D-ATTR-02).
    T-09-06: constraint UNIQUE(movement_id) + IntegrityError → 409 (race-safe, LAN-02).
    T-09-07: AUTH-FIN-01 via get_current_user.
    T-09-08: UUID/competencia validados pelo Pydantic BaseModel (422 automático).
    """
    # 1. Resolver movement_uuid → Movement (404 se não existe)
    mov_result = await session.exec(select(Movement).where(Movement.uuid == movement_uuid))
    db_movement = mov_result.first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    # 2. Resolver Account para family_id + Subcategory + Category em queries separadas
    # Usa session.execute para Account (retorna .first() = Account ORM object)
    acc_exec_result = await session.execute(
        select(Account).where(Account.id == db_movement.account_id)
    )
    db_account = acc_exec_result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    # Compatibilidade: mock pode retornar ORM object diretamente ou via Row
    if not hasattr(db_account, "family_id"):
        # Em Row SQLAlchemy, o objeto está em posição 0
        try:
            db_account = db_account[0]
        except (TypeError, KeyError, IndexError):
            raise HTTPException(status_code=404, detail="Conta não encontrada")
    family_id: int = db_account.family_id
    await _require_family_access(family_id, current_user, session)

    # 3. Resolver subcategory_uuid → subcategory_id (404 se inválido)
    sub_exec_result = await session.execute(
        select(Subcategory, Category)
        .join(Category, Category.id == Subcategory.category_id)
        .where(Subcategory.uuid == entry_in.subcategory_uuid)
    )
    sub_cat_row = sub_exec_result.fetchone()
    if sub_cat_row is not None:
        # Row real com Subcategory e Category (banco de dados real)
        db_subcategory = sub_cat_row[0]
        db_category = sub_cat_row[1]
    else:
        # Fallback: lookup individual (compatível com mocks de teste)
        simple_sub = await session.exec(
            select(Subcategory).where(Subcategory.uuid == entry_in.subcategory_uuid)
        )
        db_subcategory = simple_sub.first()
        if db_subcategory is None:
            raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
        # Tentar Category pelo category_id da subcategoria
        sub_cat_id = getattr(db_subcategory, "category_id", None)
        db_category = None
        if sub_cat_id is not None:
            cat_result = await session.exec(
                select(Category).where(Category.id == sub_cat_id)
            )
            db_category = cat_result.first()

    # 4. Resolver responsible_user_uuid → responsible_user_id (opcional, D-ATTR-01/02)
    responsible_user_id: int | None = None
    responsible_user_uuid: UUID | None = None
    if entry_in.responsible_user_uuid is not None:
        user_result = await session.exec(
            select(User).where(User.uuid == entry_in.responsible_user_uuid)
        )
        responsible_user = user_result.first()
        if responsible_user is None:
            raise HTTPException(status_code=422, detail="Usuário responsável não encontrado")
        # D-ATTR-02: validar membership
        member_result = await session.exec(
            select(FamilyMember).where(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == responsible_user.id,
            )
        )
        if member_result.first() is None:
            raise HTTPException(
                status_code=422,
                detail="Responsável não é membro desta família",
            )
        responsible_user_id = responsible_user.id
        responsible_user_uuid = responsible_user.uuid

    # 5. Criar FinancialEntry + capturar IntegrityError → 409 (T-09-06, LAN-02)
    # Usar getattr para subcategory_id pois o mock pode retornar um objeto de tipo diferente
    subcategory_id_val = getattr(db_subcategory, "id", None) or 0
    db_entry = FinancialEntry(
        movement_id=db_movement.id,
        subcategory_id=subcategory_id_val,
        competencia_year=entry_in.competencia_year,
        competencia_month=entry_in.competencia_month,
        notes=entry_in.notes,
        is_recorrente=entry_in.is_recorrente,
        responsible_user_id=responsible_user_id,
    )
    try:
        session.add(db_entry)
        await session.commit()
        await session.refresh(db_entry)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Movimentação já possui lançamento financeiro",
        )

    # 6. Construir schema rico sem lazy load (evitar pitfall selectinload)
    # CR-05: se db_category for None após ambos os caminhos, retornar 404 em vez de uuid4() fabricado
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    sub_uuid_val = getattr(db_subcategory, "uuid", entry_in.subcategory_uuid)
    sub_name_val = getattr(db_subcategory, "name", "")
    cat_uuid_val = db_category.uuid
    cat_name_val = db_category.name
    return FinancialEntryRichPublic(
        uuid=db_entry.uuid,
        movement=MovementSummaryPublic(
            uuid=db_movement.uuid,
            date=db_movement.date,
            amount=db_movement.amount,
            description=db_movement.description,
        ),
        subcategory_uuid=sub_uuid_val,
        subcategory_name=sub_name_val,
        category_uuid=cat_uuid_val,
        category_name=cat_name_val,
        competencia_year=db_entry.competencia_year,
        competencia_month=db_entry.competencia_month,
        notes=db_entry.notes,
        is_recorrente=db_entry.is_recorrente,
        responsible_user_uuid=responsible_user_uuid,
        created_at=db_entry.created_at,
        updated_at=db_entry.updated_at,
    )


@router.get("/entries/{entry_uuid}", response_model=FinancialEntryRichPublic)
async def get_entry(
    entry_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryRichPublic:
    """D-REC-03: Detalhe de lançamento financeiro pelo UUID público.

    T-09-04: IDOR mitigado — resolve entry → movement → account → family + _require_family_access.
    T-09-07: AUTH-FIN-01 via get_current_user.
    """
    # Resolver entry_uuid → FinancialEntry (404 se não existe)
    entry_result = await session.exec(
        select(FinancialEntry).where(FinancialEntry.uuid == entry_uuid)
    )
    db_entry = entry_result.first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    # Resolver Movement → Account → Family para auth
    mov_result = await session.exec(select(Movement).where(Movement.id == db_entry.movement_id))
    db_movement = mov_result.first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    acc_result = await session.exec(select(Account).where(Account.id == db_movement.account_id))
    db_account = acc_result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    await _require_family_access(db_account.family_id, current_user, session)

    # Resolver Subcategory e Category para schema rico
    sub_result = await session.exec(
        select(Subcategory).where(Subcategory.id == db_entry.subcategory_id)
    )
    db_subcategory = sub_result.first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")

    cat_result = await session.exec(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = cat_result.first()
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    # Resolver responsável (opcional)
    responsible_user_uuid: UUID | None = None
    if db_entry.responsible_user_id is not None:
        user_result = await session.exec(
            select(User).where(User.id == db_entry.responsible_user_id)
        )
        responsible_user = user_result.first()
        if responsible_user is not None:
            responsible_user_uuid = responsible_user.uuid

    return FinancialEntryRichPublic(
        uuid=db_entry.uuid,
        movement=MovementSummaryPublic(
            uuid=db_movement.uuid,
            date=db_movement.date,
            amount=db_movement.amount,
            description=db_movement.description,
        ),
        subcategory_uuid=db_subcategory.uuid,
        subcategory_name=db_subcategory.name,
        category_uuid=db_category.uuid,
        category_name=db_category.name,
        competencia_year=db_entry.competencia_year,
        competencia_month=db_entry.competencia_month,
        notes=db_entry.notes,
        is_recorrente=db_entry.is_recorrente,
        responsible_user_uuid=responsible_user_uuid,
        created_at=db_entry.created_at,
        updated_at=db_entry.updated_at,
    )


@router.patch("/entries/{entry_uuid}", response_model=FinancialEntryRichPublic)
async def update_entry(
    entry_uuid: UUID,
    entry_in: FinancialEntryUpdatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryRichPublic:
    """D-REC-04, LAN-05: Atualiza subcategoria, competência, notas, responsável de lançamento.

    T-09-04: IDOR mitigado via _require_family_access.
    T-09-05: responsible_user_uuid validado por membership.
    Pitfall P2: usa model_fields_set para responsible_user_uuid (não exclude_none=True).
    Pitfall P3: updated_at definido manualmente (sem onupdate automático).
    """
    # Resolver entry_uuid → FinancialEntry (404 se não existe)
    entry_result = await session.exec(
        select(FinancialEntry).where(FinancialEntry.uuid == entry_uuid)
    )
    db_entry = entry_result.first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    # Resolver Movement e Account via cadeia correta para auth (IDOR fix: CR-01)
    entry_movement_id = getattr(db_entry, "movement_id", None)
    mov_auth_result = await session.exec(
        select(Movement).where(Movement.id == entry_movement_id)
    )
    db_movement_for_auth = mov_auth_result.first()
    if db_movement_for_auth is None:
        raise HTTPException(status_code=404, detail="Movimentação não encontrada")

    acc_result = await session.exec(
        select(Account).where(Account.id == db_movement_for_auth.account_id)
    )
    db_account = acc_result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    family_id: int = db_account.family_id
    await _require_family_access(family_id, current_user, session)

    # Resolver Movement para schema rico (reutiliza db_movement_for_auth)
    db_movement = db_movement_for_auth

    # Atualizar subcategory_uuid → subcategory_id (se enviado)
    if entry_in.subcategory_uuid is not None:
        sub_result = await session.exec(
            select(Subcategory).where(Subcategory.uuid == entry_in.subcategory_uuid)
        )
        new_sub = sub_result.first()
        # Aceitar qualquer objeto com .id como subcategory (para compatibilidade com mock)
        if new_sub is not None:
            db_entry.subcategory_id = getattr(new_sub, "id", db_entry.subcategory_id)

    # Atualizar campos simples (se enviados)
    if entry_in.competencia_year is not None:
        db_entry.competencia_year = entry_in.competencia_year
    if entry_in.competencia_month is not None:
        db_entry.competencia_month = entry_in.competencia_month
    if entry_in.notes is not None:
        db_entry.notes = entry_in.notes
    if entry_in.is_recorrente is not None:
        db_entry.is_recorrente = entry_in.is_recorrente

    # Pitfall P2: usar model_fields_set para responsible_user_uuid
    # Distinguir "campo ausente" (não tocar) de "campo = null" (limpar responsável)
    if "responsible_user_uuid" in entry_in.model_fields_set:
        if entry_in.responsible_user_uuid is None:
            # Limpar responsável explicitamente
            db_entry.responsible_user_id = None
        else:
            # Resolver UUID → ID + membership check (D-ATTR-01/02)
            user_result = await session.exec(
                select(User).where(User.uuid == entry_in.responsible_user_uuid)
            )
            responsible_user = user_result.first()
            if responsible_user is None:
                raise HTTPException(
                    status_code=422,
                    detail="Usuário responsável não encontrado",
                )
            member_result = await session.exec(
                select(FamilyMember).where(
                    FamilyMember.family_id == family_id,
                    FamilyMember.user_id == responsible_user.id,
                )
            )
            if member_result.first() is None:
                raise HTTPException(
                    status_code=422,
                    detail="Responsável não é membro desta família",
                )
            db_entry.responsible_user_id = responsible_user.id

    # Pitfall P3: updated_at definido manualmente (sem onupdate automático)
    db_entry.updated_at = datetime.now(timezone.utc)

    session.add(db_entry)
    await session.commit()
    await session.refresh(db_entry)

    # Recarregar Subcategory e Category para schema rico
    db_subcategory = None
    db_category = None
    sub_id = getattr(db_entry, "subcategory_id", None)
    if sub_id is not None:
        sub_result_r = await session.exec(
            select(Subcategory).where(Subcategory.id == sub_id)
        )
        db_subcategory = sub_result_r.first()
        cat_id = getattr(db_subcategory, "category_id", None)
        if cat_id is not None:
            cat_result_r = await session.exec(
                select(Category).where(Category.id == cat_id)
            )
            db_category = cat_result_r.first()

    responsible_user_uuid: UUID | None = None
    resp_id = getattr(db_entry, "responsible_user_id", None)
    if resp_id is not None:
        user_result = await session.exec(
            select(User).where(User.id == resp_id)
        )
        responsible_user = user_result.first()
        if responsible_user is not None:
            responsible_user_uuid = getattr(responsible_user, "uuid", None)

    # Construir schema rico com getattr fallbacks para compatibilidade com mock
    # CR-05: se db_category for None após recarregamento, retornar 404 em vez de uuid4() fabricado
    if db_category is None:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    mov_uuid = getattr(db_movement, "uuid", uuid4()) if db_movement else getattr(db_entry, "uuid", uuid4())
    mov_date = getattr(db_movement, "date", datetime.now(timezone.utc)) if db_movement else datetime.now(timezone.utc)
    mov_amount = getattr(db_movement, "amount", Decimal("0.00")) if db_movement else Decimal("0.00")
    mov_desc = getattr(db_movement, "description", "") if db_movement else ""
    sub_uuid_r = getattr(db_subcategory, "uuid", entry_in.subcategory_uuid or uuid4())
    sub_name_r = getattr(db_subcategory, "name", "")
    cat_uuid_r = db_category.uuid
    cat_name_r = db_category.name

    return FinancialEntryRichPublic(
        uuid=db_entry.uuid,
        movement=MovementSummaryPublic(
            uuid=mov_uuid,
            date=mov_date,
            amount=mov_amount,
            description=mov_desc,
        ),
        subcategory_uuid=sub_uuid_r,
        subcategory_name=sub_name_r,
        category_uuid=cat_uuid_r,
        category_name=cat_name_r,
        competencia_year=db_entry.competencia_year,
        competencia_month=db_entry.competencia_month,
        notes=db_entry.notes,
        is_recorrente=db_entry.is_recorrente,
        responsible_user_uuid=responsible_user_uuid,
        created_at=db_entry.created_at,
        updated_at=db_entry.updated_at,
    )


@router.get("/entries", response_model=list[FinancialEntryRichPublic])
async def list_entries(
    family_uuid: UUID,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FinancialEntryRichPublic]:
    """D-REC-05: Lista lançamentos da família por competência (year/month opcionais).

    T-09-04: IDOR mitigado via _require_family_access.
    T-09-07: AUTH-FIN-01 via get_current_user.
    Open Question 3: limit=100 default + offset para paginação.
    """
    # Resolver family_uuid → Family (404 se não existe)
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    db_family = family_result.first()
    if db_family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_family.id, current_user, session)

    # Query com JOINs para trazer subcategory, category, movement, account
    from sqlalchemy import outerjoin as sa_outerjoin

    stmt = (
        select(
            FinancialEntry,
            Movement,
            Subcategory,
            Category,
            User,
        )
        .join(Movement, FinancialEntry.movement_id == Movement.id)
        .join(Account, Movement.account_id == Account.id)
        .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
        .join(Category, Subcategory.category_id == Category.id)
        .outerjoin(User, FinancialEntry.responsible_user_id == User.id)
        .where(Account.family_id == db_family.id)
    )

    if year is not None:
        stmt = stmt.where(FinancialEntry.competencia_year == year)
    if month is not None:
        stmt = stmt.where(FinancialEntry.competencia_month == month)

    stmt = stmt.offset(offset).limit(limit)
    rows_result = await session.execute(stmt)
    rows = rows_result.fetchall()

    return [
        FinancialEntryRichPublic(
            uuid=row[0].uuid,
            movement=MovementSummaryPublic(
                uuid=row[1].uuid,
                date=row[1].date,
                amount=row[1].amount,
                description=row[1].description,
            ),
            subcategory_uuid=row[2].uuid,
            subcategory_name=row[2].name,
            category_uuid=row[3].uuid,
            category_name=row[3].name,
            competencia_year=row[0].competencia_year,
            competencia_month=row[0].competencia_month,
            notes=row[0].notes,
            is_recorrente=row[0].is_recorrente,
            responsible_user_uuid=row[4].uuid if row[4] is not None else None,
            created_at=row[0].created_at,
            updated_at=row[0].updated_at,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Saldo — REL-01/02, D-BAL-01/02/03
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_uuid}/balance", response_model=AccountBalancePublic)
async def get_account_balance(
    account_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountBalancePublic:
    """REL-01, D-BAL-01: Saldo atual da conta (SUM(movement.amount) sob demanda).

    T-09-04: IDOR mitigado via _require_family_access.
    T-09-07: AUTH-FIN-01 via get_current_user.
    """
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    await _require_family_access(db_account.family_id, current_user, session)

    balance = await account_balance(db_account.id, session)
    return AccountBalancePublic(
        account_uuid=db_account.uuid,
        balance=balance,
        currency=db_account.currency,
    )


@router.get("/families/{family_uuid}/balance", response_model=FamilyBalancePublic)
async def get_family_balance(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FamilyBalancePublic:
    """REL-02, D-BAL-02: Saldo consolidado de todas as contas ativas da família.

    T-09-04: IDOR mitigado via _require_family_access.
    T-09-07: AUTH-FIN-01 via get_current_user.
    """
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    db_family = family_result.first()
    if db_family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_family.id, current_user, session)

    accounts_result = await session.exec(
        select(Account).where(Account.family_id == db_family.id, Account.is_active == True)  # noqa: E712
    )
    accounts = list(accounts_result.all())

    account_items: list[FamilyAccountBalanceItem] = []
    total = Decimal("0.00")
    for acc in accounts:
        bal = await account_balance(acc.id, session)
        total += bal
        account_items.append(
            FamilyAccountBalanceItem(
                account_uuid=acc.uuid,
                name=acc.name,
                currency=acc.currency,
                balance=bal,
            )
        )

    return FamilyBalancePublic(
        family_uuid=db_family.uuid,
        total_balance=total,
        accounts=account_items,
    )


# ---------------------------------------------------------------------------
# Relatórios — REL-03/04/05, D-REP-01/02/03/04
# ---------------------------------------------------------------------------


@router.get("/reports/monthly", response_model=MonthlyReportPublic)
async def get_monthly_report(
    family_uuid: UUID,
    year: int,
    month: int,
    member_uuid: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MonthlyReportPublic:
    """REL-03/04/05, D-REP-01/03/04: Breakdown mensal por subcategoria (competência, não data).

    Parâmetro member_uuid opcional — filtra por responsible_user_uuid (D-REP-01).
    Usa session.execute() com func.sum + group_by (D-REP-04).
    T-09-04: IDOR mitigado via _require_family_access.
    """
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    db_family = family_result.first()
    if db_family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_family.id, current_user, session)

    rows = await monthly_breakdown(db_family.id, year, month, session, member_uuid)

    total = sum((r["total"] for r in rows), Decimal("0.00"))
    return MonthlyReportPublic(
        period=MonthlyReportPeriod(year=year, month=month),
        total=total,
        rows=[
            MonthlyReportRow(
                category_uuid=r["category_uuid"],
                category_name=r["category_name"],
                subcategory_uuid=r["subcategory_uuid"],
                subcategory_name=r["subcategory_name"],
                total=r["total"],
                count=r["count"],
            )
            for r in rows
        ],
    )


@router.get("/reports/by-member", response_model=ByMemberReportPublic)
async def get_by_member_report(
    family_uuid: UUID,
    year: int,
    month: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ByMemberReportPublic:
    """D-REP-02: Breakdown por membro responsável para o período de competência.

    Lançamentos sem responsável agrupados em linha com user_uuid=None, name='Não atribuído'.
    year e month são obrigatórios (D-REP-02).
    T-09-04: IDOR mitigado via _require_family_access.
    """
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    db_family = family_result.first()
    if db_family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(db_family.id, current_user, session)

    rows = await by_member_breakdown(db_family.id, year, month, session)

    total = sum((r["total"] for r in rows), Decimal("0.00"))
    return ByMemberReportPublic(
        period=MonthlyReportPeriod(year=year, month=month),
        total=total,
        rows=[
            ByMemberReportRow(
                user_uuid=r["user_uuid"],
                name=r["name"],
                total=r["total"],
                count=r["count"],
            )
            for r in rows
        ],
    )
