# CARAMELLO-GENERATED: implemented
"""Operações de negócio do domínio finances — Phase 7 + Phase 8.

Cobre:
  - ACC-01/02/03: CRUD de Account scoped por família
  - CAT-01/02/04: CRUD de Category e Subcategory scoped por família
  - AUTH-FIN-01/02: 401/403 via get_current_user + _require_family_access
  - MOV-01..05: registro individual, importação CSV/OFX/XLSX e confirmação
  - D-15: listagem paginada de movimentações
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.finances.models import Account, Category, Movement, Subcategory
from caramello.families.models import Family
from caramello.shared.auth import get_current_user, _require_family_access
from caramello.shared.database import get_session
from caramello.finances.services import (
    _compute_hash,
    import_movements,
    ParsedRow,
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
    from caramello.finances.services import _parse_date
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
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MovementReadPublic]:
    """D-15: Lista movimentações da conta com paginação e filtros opcionais de data.

    T-08-09: IDOR mitigado via _require_family_access.
    T-08-10: Depends(get_current_user) → 401 sem token.
    """
    # Resolver account_uuid → Account
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Verificar membership — T-08-09: 403 para não-membro
    await _require_family_access(db_account.family_id, current_user, session)

    # Construir query com filtros opcionais
    # Usar session.execute() (não session.exec()) para queries com limit/offset (P8)
    stmt = select(Movement).where(Movement.account_id == db_account.id)
    if date_from:
        from caramello.finances.services import _parse_date
        stmt = stmt.where(Movement.date >= _parse_date(date_from, line=0))
    if date_to:
        from caramello.finances.services import _parse_date
        stmt = stmt.where(Movement.date <= _parse_date(date_to, line=0))
    stmt = stmt.order_by(Movement.date.desc()).offset(offset).limit(limit)

    movements_execute_result = await session.execute(stmt)
    movements = [row[0] for row in movements_execute_result.fetchall()]

    return [
        MovementReadPublic(
            uuid=m.uuid,
            date=m.date,
            amount=m.amount,
            description=m.description,
            import_hash=m.import_hash,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in movements
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
                updated_at=m.get("created_at", datetime.now(timezone.utc)),
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
    from caramello.finances.services import _parse_date
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
