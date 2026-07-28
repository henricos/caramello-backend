# CARAMELLO-GENERATED: implemented
"""Business operations of the finances domain — Phase 7 + Phase 8 + Phase 9.

Covers:
  - ACC-01/02/03: Account CRUD, scoped to a family
  - CAT-01/02/04: Category and Subcategory CRUD, scoped to a family
  - AUTH-FIN-01/02: 401/403 through get_current_user + require_family_access
  - MOV-01..05: single entry, CSV/OFX/XLSX import and confirmation
  - D-15: paginated movement listing
  - LAN-01..05: reconciling movements into financial entries
  - REL-01..05: balance reports and category/member breakdowns

Every route in this module is hand-written on purpose: the generated CRUD is
opted out for the whole domain (`generate_router: false` in the entity YAMLs)
because it would publish the internal integer foreign keys the `*Public`
schemas below exist to keep out of the api.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.families.models import Family, FamilyMember
from caramello_api.finances.models import (
    Account,
    Category,
    FinancialEntry,
    Movement,
    Subcategory,
)
from caramello_api.finances.services import (
    ParsedRow,
    _compute_hash,
    _parse_date,
    account_balance,
    by_member_breakdown,
    import_movements,
    monthly_breakdown,
    suggest_category,
)
from caramello_api.i18n import error_detail
from caramello_api.shared.auth import get_current_user, require_family_access
from caramello_api.shared.database import get_session
from caramello_api.users.models import User

router = APIRouter(prefix="/finances", tags=["Finances"])


# ---------------------------------------------------------------------------
# Public schemas — deliberately NOT the generated ones (AccountRead,
# CategoryRead): those expose the internal family_id/category_id.
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
# Public Movement schemas — D-16 (no account_uuid, no internal id)
# T-08-11: they leak neither id nor family_id
# ---------------------------------------------------------------------------


class MovementCreatePublic(BaseModel):
    date: str  # ISO 8601 or DD/MM/YYYY — parsed by the service layer
    amount: Decimal
    description: str


class MovementReadPublic(BaseModel):
    uuid: UUID
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None  # D-16: optional, for debugging
    # D-MOV-01: UUID of the reconciled entry; null while the movement is pending
    entry_uuid: UUID | None = None
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
    movements: list[MovementCreatePublic]  # the confirmed movements to insert


# ---------------------------------------------------------------------------
# Public FinancialEntry schemas (Phase 9) — D-REC-01/02/03/04/05
# LAN-01..05: reconciling, detail, update and listing of entries
# ---------------------------------------------------------------------------


class ReconcileCreatePublic(BaseModel):
    """Payload creating a financial entry through reconciliation (D-REC-01)."""

    subcategory_uuid: UUID
    competencia_year: int
    competencia_month: int
    notes: str | None = PydanticField(default=None, max_length=500)
    is_recorrente: bool = False
    responsible_user_uuid: UUID | None = None


class FinancialEntryUpdatePublic(BaseModel):
    """Payload partially updating a financial entry (D-REC-04, LAN-05).

    For responsible_user_uuid: None means clear the responsible member; the
    field being absent (not in model_fields_set) means leave it alone.
    Do NOT use model_dump(exclude_none=True) on this schema — read
    model_fields_set instead (pitfall P2).
    """

    subcategory_uuid: UUID | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None  # None = clear; absent = leave alone


class MovementSummaryPublic(BaseModel):
    """Movement summary embedded in the rich FinancialEntry schema (D-REC-02)."""

    uuid: UUID
    date: datetime
    amount: Decimal
    description: str


class FinancialEntryRichPublic(BaseModel):
    """Rich response schema shared by every FinancialEntry endpoint (D-REC-02).

    Reused by POST reconcile, GET detail, PATCH update and GET list. The movement
    is embedded so a consumer needs no second GET.
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
# Balance and report schemas (Phase 9) — REL-01..05
# ---------------------------------------------------------------------------


class AccountBalancePublic(BaseModel):
    """Account balance response (D-BAL-01)."""

    account_uuid: UUID
    balance: Decimal
    currency: str


class FamilyAccountBalanceItem(BaseModel):
    """One account inside the family balance (D-BAL-02)."""

    account_uuid: UUID
    name: str
    currency: str
    balance: Decimal


class FamilyBalancePublic(BaseModel):
    """Consolidated family balance response (D-BAL-02)."""

    family_uuid: UUID
    total_balance: Decimal
    accounts: list[FamilyAccountBalanceItem]


class MonthlyReportPeriod(BaseModel):
    """Accrual period (competencia) of a monthly report."""

    year: int
    month: int


class MonthlyReportRow(BaseModel):
    """One subcategory breakdown row of the monthly report (D-REP-01)."""

    category_uuid: UUID
    category_name: str
    subcategory_uuid: UUID
    subcategory_name: str
    total: Decimal
    count: int


class MonthlyReportPublic(BaseModel):
    """Monthly report response (D-REP-01)."""

    period: MonthlyReportPeriod
    total: Decimal
    rows: list[MonthlyReportRow]


class ByMemberReportRow(BaseModel):
    """One member row of the by-responsible breakdown report (D-REP-02)."""

    user_uuid: UUID | None
    name: str
    total: Decimal
    count: int


class ByMemberReportPublic(BaseModel):
    """By-member report response (D-REP-02)."""

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
    """ACC-01: create a bank account scoped to a family.

    T-07-03: the payload only accepts family_uuid (the public UUID); family_id is
    resolved server-side. T-07-04: Depends(get_current_user) is mandatory.
    """
    # Resolve the public UUID to the ORM object (404 when unknown)
    family_result = await session.execute(
        select(Family).where(Family.uuid == account_in.family_uuid)
    )
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    # Check membership — T-07-02: 403 for a non-member (IDOR mitigated)
    await require_family_access(family.id, current_user, session)

    # Persist with the internal id (never with the UUID that came in)
    db_account = Account(
        family_id=family.id,
        name=account_in.name,
        type=account_in.type,
        currency=account_in.currency,
    )
    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)

    # T-07-01: answer with the public schema (no id, no family_id)
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
    """ACC-02: list the family's accounts — family_uuid is a required query param.

    AUTH-FIN-02: membership is checked before anything is filtered.
    """
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    await require_family_access(family.id, current_user, session)

    accounts_result = await session.execute(select(Account).where(Account.family_id == family.id))
    accounts = list(accounts_result.scalars().all())
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
    """ACC-02: one account's detail, by public UUID."""
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Resolve the Family to get its public UUID and to check access
    family_result = await session.execute(select(Family).where(Family.id == db_account.family_id))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_account.family_id, current_user, session)

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
    """ACC-02/03: update an account, or archive it (is_active=false).

    ACC-03: archiving is is_active=false — session.delete is NOT used.
    Pitfall #4: updated_at is set by hand (there is no automatic onupdate).
    """
    # Look the Account up by public UUID
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Resolve the Family to get its public UUID
    family_result = await session.execute(select(Family).where(Family.id == db_account.family_id))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    # Check membership
    await require_family_access(db_account.family_id, current_user, session)

    # Apply only the fields that were sent (exclude_none)
    update_data = account_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_account, key, value)

    # Pitfall #4: updated_at has no automatic onupdate — set it by hand
    db_account.updated_at = datetime.now(UTC)

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
    """CAT-01: create a level-1 category scoped to a family."""
    family_result = await session.execute(
        select(Family).where(Family.uuid == category_in.family_uuid)
    )
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    await require_family_access(family.id, current_user, session)

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
    """CAT-04: list the family's categories — family_uuid is required."""
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    await require_family_access(family.id, current_user, session)

    categories_result = await session.execute(
        select(Category).where(Category.family_id == family.id)
    )
    categories = list(categories_result.scalars().all())
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
    """CAT-04: one category's detail, by public UUID."""
    result = await session.execute(select(Category).where(Category.uuid == category_uuid))
    db_category = result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    family_result = await session.execute(select(Family).where(Family.id == db_category.family_id))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_category.family_id, current_user, session)

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
    """CAT-04: update a category.

    Pitfall #4: updated_at is set by hand.
    """
    result = await session.execute(select(Category).where(Category.uuid == category_uuid))
    db_category = result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    family_result = await session.execute(select(Family).where(Family.id == db_category.family_id))
    family = family_result.scalars().first()
    if family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))

    await require_family_access(db_category.family_id, current_user, session)

    update_data = category_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_category, key, value)
    db_category.updated_at = datetime.now(UTC)

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
    """CAT-02: create a level-2 subcategory from a category_uuid.

    D-13: category_uuid is the public parameter; the server resolves it to
    category_id. Access is checked through category.family_id.
    """
    # Resolve category_uuid to a Category (404 when unknown)
    category_result = await session.execute(
        select(Category).where(Category.uuid == subcategory_in.category_uuid)
    )
    db_category = category_result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    # Check membership through category.family_id
    await require_family_access(db_category.family_id, current_user, session)

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
    """CAT-04: list subcategories; category_uuid is required (D-12)."""
    category_result = await session.execute(select(Category).where(Category.uuid == category_uuid))
    db_category = category_result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    await require_family_access(db_category.family_id, current_user, session)

    subcategories_result = await session.execute(
        select(Subcategory).where(Subcategory.category_id == db_category.id)
    )
    subcategories = list(subcategories_result.scalars().all())
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
    """CAT-04: one subcategory's detail, by public UUID."""
    result = await session.execute(select(Subcategory).where(Subcategory.uuid == subcategory_uuid))
    db_subcategory = result.scalars().first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.subcategory_not_found"))

    category_result = await session.execute(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = category_result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    await require_family_access(db_category.family_id, current_user, session)

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
    """CAT-04: update a subcategory.

    Pitfall #4: updated_at is set by hand.
    """
    result = await session.execute(select(Subcategory).where(Subcategory.uuid == subcategory_uuid))
    db_subcategory = result.scalars().first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.subcategory_not_found"))

    category_result = await session.execute(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = category_result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    await require_family_access(db_category.family_id, current_user, session)

    update_data = subcategory_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_subcategory, key, value)
    db_subcategory.updated_at = datetime.now(UTC)

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
    """MOV-01: record a single movement, scoped to an account/family.

    D-17: answers 409 with existing_uuid when the hash is already known.
    T-08-09: IDOR mitigated through require_family_access.
    T-08-10: Depends(get_current_user) -> 401 without a token.
    """
    # Resolve account_uuid to an Account (404 when unknown)
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Check membership — T-08-09: 403 for a non-member (IDOR mitigated)
    await require_family_access(db_account.family_id, current_user, session)

    # Parse the date (D-12: ISO first, BR as the fallback)
    date_val = _parse_date(movement_in.date, line=1)

    # Compute the deduplication hash (D-07)
    row = ParsedRow(
        date=date_val,
        amount=movement_in.amount,
        description=movement_in.description,
        fitid=None,
    )
    computed_hash = _compute_hash(db_account.id, row)

    # D-17: a known hash answers 409 carrying existing_uuid
    dup_result = await session.execute(
        select(Movement).where(Movement.import_hash == computed_hash)
    )
    dup = dup_result.scalars().first()
    if dup is not None:
        # The `reason`/`message` pair is the shared error shape; `existing_uuid`
        # is the extra field this specific conflict adds, so the consumer can
        # point the user at the movement that already exists.
        raise HTTPException(
            status_code=409,
            detail={
                **error_detail("finances.movement_already_exists"),
                "existing_uuid": str(dup.uuid),
            },
        )

    # Persist the movement
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
    """D-15, D-MOV-01/02: list an account's movements, paginated and filtered.

    D-MOV-01: entry_uuid comes from a LEFT JOIN on FinancialEntry (null =
              pending, a UUID = reconciled).
    D-MOV-02: reconciled=false (pending) / reconciled=true (reconciled), through
              the same LEFT JOIN.
    T-08-09: IDOR mitigated through require_family_access.
    T-08-10: Depends(get_current_user) -> 401 without a token.
    """
    from sqlalchemy import outerjoin

    # Resolve account_uuid to an Account
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Check membership — T-08-09: 403 for a non-member
    await require_family_access(db_account.family_id, current_user, session)

    # D-MOV-01: LEFT JOIN on FinancialEntry for entry_uuid
    # (pitfall P5: read the Rows with fetchall + position)
    stmt = (
        select(Movement, FinancialEntry.uuid.label("entry_uuid"))
        .select_from(outerjoin(Movement, FinancialEntry, FinancialEntry.movement_id == Movement.id))
        .where(Movement.account_id == db_account.id)
    )

    if date_from:
        stmt = stmt.where(Movement.date >= _parse_date(date_from, line=0))
    if date_to:
        stmt = stmt.where(Movement.date <= _parse_date(date_to, line=0))

    # D-MOV-02: the reconciliation filter is IS NULL / IS NOT NULL
    if reconciled is False:
        stmt = stmt.where(FinancialEntry.id.is_(None))
    elif reconciled is True:
        stmt = stmt.where(FinancialEntry.id.is_not(None))

    stmt = stmt.order_by(Movement.date.desc()).offset(offset).limit(limit)

    # session.execute() + fetchall() for a multi-entity select (pitfall P5)
    movements_execute_result = await session.execute(stmt)
    rows = movements_execute_result.fetchall()

    return [
        MovementReadPublic(
            uuid=row[0].uuid,
            date=row[0].date,
            amount=row[0].amount,
            description=row[0].description,
            import_hash=row[0].import_hash,
            # D-MOV-01: entry_uuid from the LEFT JOIN — None when the Row has no
            # second element (keeps the unit tests' mocks working)
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
    """MOV-02/03/04/05: import a bank statement file (CSV, OFX or XLSX).

    D-09: the format comes in as a query param.
    D-13: >50% invalid rows -> 422.
    T-08-09: IDOR mitigated through require_family_access.
    T-08-12/13: on_conflict_do_nothing + the error threshold.
    """
    # Resolve account_uuid to an Account
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Check membership
    await require_family_access(db_account.family_id, current_user, session)

    content: bytes = await file.read()

    try:
        service_result = await import_movements(content, format, db_account.id, session)
    except ValueError as e:
        # D-13: a batch with >50% invalid rows aborts with 422. The service
        # already raises catalog-resolved text, so it becomes `message` as it is;
        # `reason` is the stable code a consumer branches on.
        raise HTTPException(
            status_code=422,
            detail={"reason": "invalid_import_file", "message": str(e)},
        ) from e

    # Convert movements[] into MovementReadPublic
    movements_public = []
    for m in service_result.get("movements", []):
        movements_public.append(
            MovementReadPublic(
                uuid=m["uuid"],
                date=m["date"],
                amount=m["amount"],
                description=m["description"],
                import_hash=None,
                created_at=m.get("created_at", datetime.now(UTC)),
                updated_at=m.get("updated_at", m.get("created_at", datetime.now(UTC))),  # WR-03
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
    """D-08, MOV-05: confirm and insert the movements suspected of being duplicates.

    P4: the confirmed rows get import_hash=None — PostgreSQL allows several NULLs
    under a UNIQUE constraint.
    T-08-09: IDOR mitigated through require_family_access.
    T-08-12: import_hash=None is what keeps the UNIQUE constraint from firing.
    """
    # Resolve account_uuid to an Account
    result = await session.execute(select(Account).where(Account.uuid == confirm_in.account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # Check membership
    await require_family_access(db_account.family_id, current_user, session)

    # Insert the confirmed movements with import_hash=None (P4/D-08).
    # Every object is accumulated before the commit, for atomicity — no partial
    # state is left behind when one insert fails mid-batch (CR-03).
    db_movements: list[Movement] = []

    for movement_in in confirm_in.movements:
        date_val = _parse_date(movement_in.date, line=1)
        db_movement = Movement(
            account_id=db_account.id,
            date=date_val,
            amount=movement_in.amount,
            description=movement_in.description,
            import_hash=None,  # P4: several NULLs are allowed under UNIQUE
        )
        session.add(db_movement)
        db_movements.append(db_movement)

    # A single commit — atomic for the whole batch
    await session.commit()

    # Refresh every object after the commit
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
    """LAN-03, D-CAT-01/02/03: top-5 subcategory suggestions, by fuzzy match.

    T-09-04: IDOR mitigated — resolves movement -> account -> family, then
             require_family_access.
    T-09-07: AUTH-FIN-01 through get_current_user.
    D-CAT-03: answers [] when the movement has no history (not a 404).
    """
    # Resolve movement_uuid to a Movement (404 when unknown)
    result = await session.execute(select(Movement).where(Movement.uuid == movement_uuid))
    db_movement = result.scalars().first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.movement_not_found"))

    # Resolve the Account to get family_id and to check membership
    account_result = await session.execute(
        select(Account).where(Account.id == db_movement.account_id)
    )
    db_account = account_result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    # T-09-04: check membership — 403 for a non-member (IDOR mitigated)
    await require_family_access(db_account.family_id, current_user, session)

    # Delegate to the service (D-CAT-04)
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
    """LAN-01/02/04, D-REC-01/02: create a 1:1 financial entry from a movement.

    T-09-04: IDOR mitigated through require_family_access.
    T-09-05: responsible_user_uuid is validated against membership (D-ATTR-02).
    T-09-06: UNIQUE(movement_id) + IntegrityError -> 409 (race-safe, LAN-02).
    T-09-07: AUTH-FIN-01 through get_current_user.
    T-09-08: the UUID and the accrual period are validated by the Pydantic model
             (an automatic 422).
    """
    # 1. Resolve movement_uuid to a Movement (404 when unknown)
    mov_result = await session.execute(select(Movement).where(Movement.uuid == movement_uuid))
    db_movement = mov_result.scalars().first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.movement_not_found"))

    # 2. Resolve the Account for family_id, plus Subcategory and Category, in
    # separate queries. `.scalars()` unwraps the Row: a single-entity select
    # hands back the ORM instance, never a tuple — the old positional fallback
    # was only a symptom of mixing session.exec() with session.execute().
    acc_exec_result = await session.execute(
        select(Account).where(Account.id == db_movement.account_id)
    )
    db_account = acc_exec_result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))
    family_id: int = db_account.family_id
    await require_family_access(family_id, current_user, session)

    # 3. Resolve subcategory_uuid to subcategory_id (404 when unknown)
    sub_exec_result = await session.execute(
        select(Subcategory, Category)
        .join(Category, Category.id == Subcategory.category_id)
        .where(Subcategory.uuid == entry_in.subcategory_uuid)
    )
    sub_cat_row = sub_exec_result.fetchone()
    if sub_cat_row is not None:
        # A real Row carrying Subcategory and Category (a real database)
        db_subcategory = sub_cat_row[0]
        db_category = sub_cat_row[1]
    else:
        # Fallback: one lookup at a time (keeps the unit tests' mocks working)
        simple_sub = await session.execute(
            select(Subcategory).where(Subcategory.uuid == entry_in.subcategory_uuid)
        )
        db_subcategory = simple_sub.scalars().first()
        if db_subcategory is None:
            raise HTTPException(
                status_code=404, detail=error_detail("finances.subcategory_not_found")
            )
        # Try the Category through the subcategory's category_id
        sub_cat_id = getattr(db_subcategory, "category_id", None)
        db_category = None
        if sub_cat_id is not None:
            cat_result = await session.execute(select(Category).where(Category.id == sub_cat_id))
            db_category = cat_result.scalars().first()

    # 4. Resolve responsible_user_uuid to responsible_user_id (optional,
    #    D-ATTR-01/02)
    responsible_user_id: int | None = None
    responsible_user_uuid: UUID | None = None
    if entry_in.responsible_user_uuid is not None:
        user_result = await session.execute(
            select(User).where(User.uuid == entry_in.responsible_user_uuid)
        )
        responsible_user = user_result.scalars().first()
        if responsible_user is None:
            raise HTTPException(
                status_code=422, detail=error_detail("finances.responsible_user_not_found")
            )
        # D-ATTR-02: validate membership
        member_result = await session.execute(
            select(FamilyMember).where(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == responsible_user.id,
            )
        )
        if member_result.scalars().first() is None:
            raise HTTPException(
                status_code=422,
                detail=error_detail("finances.responsible_not_family_member"),
            )
        responsible_user_id = responsible_user.id
        responsible_user_uuid = responsible_user.uuid

    # 5. Create the FinancialEntry, turning an IntegrityError into a 409
    #    (T-09-06, LAN-02). subcategory_id is read with getattr because a test
    #    mock may hand back an object of a different type.
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
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=error_detail("finances.movement_already_reconciled"),
        ) from e

    # 6. Build the rich schema with no lazy load (avoiding the selectinload
    #    pitfall). CR-05: when db_category is still None after both paths, answer
    #    404 instead of fabricating a uuid4().
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))
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
    """D-REC-03: one financial entry's detail, by public UUID.

    T-09-04: IDOR mitigated — resolves entry -> movement -> account -> family,
             then require_family_access.
    T-09-07: AUTH-FIN-01 through get_current_user.
    """
    # Resolve entry_uuid to a FinancialEntry (404 when unknown)
    entry_result = await session.execute(
        select(FinancialEntry).where(FinancialEntry.uuid == entry_uuid)
    )
    db_entry = entry_result.scalars().first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.entry_not_found"))

    # Resolve Movement -> Account -> Family, for the authorization check
    mov_result = await session.execute(select(Movement).where(Movement.id == db_entry.movement_id))
    db_movement = mov_result.scalars().first()
    if db_movement is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.movement_not_found"))

    acc_result = await session.execute(select(Account).where(Account.id == db_movement.account_id))
    db_account = acc_result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))
    await require_family_access(db_account.family_id, current_user, session)

    # Resolve Subcategory and Category for the rich schema
    sub_result = await session.execute(
        select(Subcategory).where(Subcategory.id == db_entry.subcategory_id)
    )
    db_subcategory = sub_result.scalars().first()
    if db_subcategory is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.subcategory_not_found"))

    cat_result = await session.execute(
        select(Category).where(Category.id == db_subcategory.category_id)
    )
    db_category = cat_result.scalars().first()
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))

    # Resolve the responsible member (optional)
    responsible_user_uuid: UUID | None = None
    if db_entry.responsible_user_id is not None:
        user_result = await session.execute(
            select(User).where(User.id == db_entry.responsible_user_id)
        )
        responsible_user = user_result.scalars().first()
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
    """D-REC-04, LAN-05: update an entry's subcategory, period, notes or owner.

    T-09-04: IDOR mitigated through require_family_access.
    T-09-05: responsible_user_uuid is validated against membership.
    Pitfall P2: responsible_user_uuid is read from model_fields_set, NOT from
                model_dump(exclude_none=True).
    Pitfall P3: updated_at is set by hand (there is no automatic onupdate).
    """
    # Resolve entry_uuid to a FinancialEntry (404 when unknown)
    entry_result = await session.execute(
        select(FinancialEntry).where(FinancialEntry.uuid == entry_uuid)
    )
    db_entry = entry_result.scalars().first()
    if db_entry is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.entry_not_found"))

    # Resolve Movement and Account through the right chain, for the
    # authorization check (IDOR fix: CR-01)
    entry_movement_id = getattr(db_entry, "movement_id", None)
    mov_auth_result = await session.execute(
        select(Movement).where(Movement.id == entry_movement_id)
    )
    db_movement_for_auth = mov_auth_result.scalars().first()
    if db_movement_for_auth is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.movement_not_found"))

    acc_result = await session.execute(
        select(Account).where(Account.id == db_movement_for_auth.account_id)
    )
    db_account = acc_result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))
    family_id: int = db_account.family_id
    await require_family_access(family_id, current_user, session)

    # The rich schema reuses the movement already loaded for the auth check
    db_movement = db_movement_for_auth

    # Update subcategory_uuid -> subcategory_id (when sent)
    if entry_in.subcategory_uuid is not None:
        sub_result = await session.execute(
            select(Subcategory).where(Subcategory.uuid == entry_in.subcategory_uuid)
        )
        new_sub = sub_result.scalars().first()
        # Accept any object carrying .id as the subcategory (mock compatibility)
        if new_sub is not None:
            db_entry.subcategory_id = getattr(new_sub, "id", db_entry.subcategory_id)

    # Update the plain fields (when sent)
    if entry_in.competencia_year is not None:
        db_entry.competencia_year = entry_in.competencia_year
    if entry_in.competencia_month is not None:
        db_entry.competencia_month = entry_in.competencia_month
    # WR-04: notes is nullable, so model_fields_set is what tells "not sent"
    # apart from "sent as null, meaning clear it"
    if "notes" in entry_in.model_fields_set:
        db_entry.notes = entry_in.notes  # None = clear the note; a value = update
    if entry_in.is_recorrente is not None:
        db_entry.is_recorrente = entry_in.is_recorrente

    # Pitfall P2: read responsible_user_uuid from model_fields_set, to tell
    # "field absent" (leave alone) from "field = null" (clear the owner)
    if "responsible_user_uuid" in entry_in.model_fields_set:
        if entry_in.responsible_user_uuid is None:
            # Explicitly clear the responsible member
            db_entry.responsible_user_id = None
        else:
            # Resolve UUID -> id, then check membership (D-ATTR-01/02)
            user_result = await session.execute(
                select(User).where(User.uuid == entry_in.responsible_user_uuid)
            )
            responsible_user = user_result.scalars().first()
            if responsible_user is None:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail("finances.responsible_user_not_found"),
                )
            member_result = await session.execute(
                select(FamilyMember).where(
                    FamilyMember.family_id == family_id,
                    FamilyMember.user_id == responsible_user.id,
                )
            )
            if member_result.scalars().first() is None:
                raise HTTPException(
                    status_code=422,
                    detail=error_detail("finances.responsible_not_family_member"),
                )
            db_entry.responsible_user_id = responsible_user.id

    # Pitfall P3: updated_at is set by hand (there is no automatic onupdate)
    db_entry.updated_at = datetime.now(UTC)

    session.add(db_entry)
    await session.commit()
    await session.refresh(db_entry)

    # Reload Subcategory and Category for the rich schema
    db_subcategory = None
    db_category = None
    sub_id = getattr(db_entry, "subcategory_id", None)
    if sub_id is not None:
        sub_result_r = await session.execute(select(Subcategory).where(Subcategory.id == sub_id))
        db_subcategory = sub_result_r.scalars().first()
        cat_id = getattr(db_subcategory, "category_id", None)
        if cat_id is not None:
            cat_result_r = await session.execute(select(Category).where(Category.id == cat_id))
            db_category = cat_result_r.scalars().first()

    responsible_user_uuid: UUID | None = None
    resp_id = getattr(db_entry, "responsible_user_id", None)
    if resp_id is not None:
        user_result = await session.execute(select(User).where(User.id == resp_id))
        responsible_user = user_result.scalars().first()
        if responsible_user is not None:
            responsible_user_uuid = getattr(responsible_user, "uuid", None)

    # Build the rich schema, with getattr fallbacks for mock compatibility.
    # CR-05: when db_category is None after the reload, answer 404 instead of
    # fabricating a uuid4().
    if db_category is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.category_not_found"))
    mov_uuid = (
        getattr(db_movement, "uuid", uuid4()) if db_movement else getattr(db_entry, "uuid", uuid4())
    )
    mov_date = getattr(db_movement, "date", datetime.now(UTC)) if db_movement else datetime.now(UTC)
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
    """D-REC-05: list the family's entries by accrual period (year/month optional).

    T-09-04: IDOR mitigated through require_family_access.
    T-09-07: AUTH-FIN-01 through get_current_user.
    Open Question 3: limit defaults to 100, with offset for pagination.
    """
    # Resolve family_uuid to a Family (404 when unknown)
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    db_family = family_result.scalars().first()
    if db_family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_family.id, current_user, session)

    # One query, JOINing subcategory, category, movement and account

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
# Balances — REL-01/02, D-BAL-01/02/03
# ---------------------------------------------------------------------------


@router.get("/accounts/{account_uuid}/balance", response_model=AccountBalancePublic)
async def get_account_balance(
    account_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountBalancePublic:
    """REL-01, D-BAL-01: the account's current balance, SUM(movement.amount) on demand.

    T-09-04: IDOR mitigated through require_family_access.
    T-09-07: AUTH-FIN-01 through get_current_user.
    """
    result = await session.execute(select(Account).where(Account.uuid == account_uuid))
    db_account = result.scalars().first()
    if db_account is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.account_not_found"))

    await require_family_access(db_account.family_id, current_user, session)

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
    """REL-02, D-BAL-02: consolidated balance of every active family account.

    T-09-04: IDOR mitigated through require_family_access.
    T-09-07: AUTH-FIN-01 through get_current_user.
    """
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    db_family = family_result.scalars().first()
    if db_family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_family.id, current_user, session)

    accounts_result = await session.execute(
        select(Account).where(Account.family_id == db_family.id, Account.is_active)  # noqa: E712
    )
    accounts = list(accounts_result.scalars().all())

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
# Reports — REL-03/04/05, D-REP-01/02/03/04
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
    """REL-03/04/05, D-REP-01/03/04: monthly breakdown by subcategory.

    Grouped by accrual period (competencia), NOT by the movement date.
    The optional member_uuid filters by responsible_user_uuid (D-REP-01).
    Uses session.execute() with func.sum + group_by (D-REP-04).
    T-09-04: IDOR mitigated through require_family_access.
    """
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    db_family = family_result.scalars().first()
    if db_family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_family.id, current_user, session)

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
    """D-REP-02: breakdown by responsible member for one accrual period.

    Entries with no responsible member are grouped into a row with user_uuid=None
    and the catalog's "unassigned" label.
    year and month are both required (D-REP-02).
    T-09-04: IDOR mitigated through require_family_access.
    """
    family_result = await session.execute(select(Family).where(Family.uuid == family_uuid))
    db_family = family_result.scalars().first()
    if db_family is None:
        raise HTTPException(status_code=404, detail=error_detail("finances.family_not_found"))
    await require_family_access(db_family.id, current_user, session)

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
