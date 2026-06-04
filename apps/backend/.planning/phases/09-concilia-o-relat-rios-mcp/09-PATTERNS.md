# Phase 9: Conciliação + Relatórios + MCP - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 6 (3 modified, 1 created migration, 2 modified tests)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/caramello/finances/models.py` | model | CRUD | `src/caramello/finances/models.py` (self) | exact — add column to existing model |
| `src/caramello/finances/operations.py` | controller | request-response + CRUD + batch | `src/caramello/finances/operations.py` (self — extend) | exact |
| `src/caramello/finances/services.py` | service | batch + transform + request-response | `src/caramello/finances/services.py` (self — extend) | exact |
| `alembic/versions/0004_financial_entry_responsible_user.py` | migration | CRUD | `alembic/versions/0003_movement_schema_update.py` | exact |
| `tests/test_finances_operations.py` | test | request-response | `tests/test_finances_operations.py` (self — extend) | exact |
| `tests/test_services/test_finances_service.py` | test | transform | `tests/test_services/test_finances_service.py` (self — extend) | exact |

---

## Pattern Assignments

### `src/caramello/finances/models.py` — adicionar `responsible_user_id` a `FinancialEntry`

**Analog:** `src/caramello/finances/models.py` lines 107–136 (existing `FinancialEntry`)

**Existing model declaration pattern** (lines 107–136):
```python
class FinancialEntry(SQLModel, table=True):
    __tablename__ = "financial_entry"

    __table_args__ = (
        Index("ix_financial_entry_competencia_year_competencia_month", "competencia_year", "competencia_month"),
        Index("ix_financial_entry_subcategory_id", "subcategory_id"),
    )

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    movement_id: int = Field(foreign_key="movement.id", unique=True, nullable=False)
    subcategory_id: int = Field(foreign_key="subcategory.id", nullable=False)
    competencia_year: int = Field(nullable=False)
    competencia_month: int = Field(nullable=False)
    notes: str | None = Field(max_length=500, default=None)
    is_recorrente: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
```

**New field to add** (insert after `is_recorrente`, before `created_at`):
```python
responsible_user_id: int | None = Field(
    default=None,
    foreign_key="user.id",
    nullable=True,
)
```

**Note:** Do NOT change `__table_args__` or existing fields. This is a manual edit to a file annotated `# CARAMELLO-GENERATED: implemented`.

---

### `src/caramello/finances/operations.py` — 9 new endpoints + schema extensions

**Analog:** `src/caramello/finances/operations.py` (full file — read above)

#### Imports pattern (lines 1–33):
```python
# CARAMELLO-GENERATED: implemented
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
from caramello.finances.services import (...)
from caramello.users.models import User

router = APIRouter(prefix="/finances", tags=["Finances"])
```

**New imports to add** (add to existing import block):
```python
from sqlalchemy import func, outerjoin
from sqlalchemy.exc import IntegrityError
from caramello.finances.services import (
    ...,                  # existing imports
    account_balance,
    family_balance,
    monthly_breakdown,
    by_member_breakdown,
    suggest_category,
)
```

#### Schema definition pattern — public schemas local to operations.py (lines 44–135):
All schemas are `BaseModel` (not `SQLModel`), defined before the endpoints, never exposing `id` or `family_id`. Copy this for new schemas:
```python
class ReconcileCreatePublic(BaseModel):
    subcategory_uuid: UUID
    competencia_year: int
    competencia_month: int
    notes: str | None = PydanticField(default=None, max_length=500)
    is_recorrente: bool = False
    responsible_user_uuid: UUID | None = None


class FinancialEntryUpdatePublic(BaseModel):
    subcategory_uuid: UUID | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    responsible_user_uuid: UUID | None = None  # None = limpar; ausente = não tocar


class MovementSummaryPublic(BaseModel):
    uuid: UUID
    date: datetime
    amount: Decimal
    description: str


class FinancialEntryRichPublic(BaseModel):
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
```

**Extension to `MovementReadPublic`** (lines 115–122 — add one field):
```python
class MovementReadPublic(BaseModel):
    uuid: UUID
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None
    entry_uuid: UUID | None = None   # D-MOV-01: novo campo — LEFT JOIN com FinancialEntry
    created_at: datetime
    updated_at: datetime
```

#### Auth + 404 pattern — resolve UUID → ORM object (lines 143–186):
```python
# Resolver UUID público → objeto ORM (404 se não encontrado)
result = await session.exec(select(Account).where(Account.uuid == account_uuid))
db_account = result.first()
if db_account is None:
    raise HTTPException(status_code=404, detail="Conta não encontrada")

# Verificar membership — 403 para não-membro (IDOR mitigado)
await _require_family_access(db_account.family_id, current_user, session)
```

#### Core PATCH pattern — updated_at manual (lines 260–310):
```python
update_data = account_in.model_dump(exclude_none=True)
for key, value in update_data.items():
    setattr(db_account, key, value)

# Pitfall #4: updated_at não tem onupdate automático — definir manualmente
db_account.updated_at = datetime.now(timezone.utc)

session.add(db_account)
await session.commit()
await session.refresh(db_account)
```

**PATCH with `model_fields_set` for nullable field** (D-REC-04 / pitfall P2 in RESEARCH):
```python
# Para responsible_user_uuid — distinguir "ausente" de "null explícito"
if "responsible_user_uuid" in entry_in.model_fields_set:
    if entry_in.responsible_user_uuid is None:
        db_entry.responsible_user_id = None  # limpar responsável
    else:
        # Resolver UUID → ID + membership check
        user_result = await session.exec(
            select(User).where(User.uuid == entry_in.responsible_user_uuid)
        )
        responsible_user = user_result.first()
        if responsible_user is None:
            raise HTTPException(status_code=422, detail="Usuário responsável não encontrado")
        # D-ATTR-02: validar membership
        from caramello.families.models import FamilyMember
        member_result = await session.exec(
            select(FamilyMember).where(
                FamilyMember.family_id == family_id,
                FamilyMember.user_id == responsible_user.id,
            )
        )
        if member_result.first() is None:
            raise HTTPException(status_code=422, detail="Responsável não é membro desta família")
        db_entry.responsible_user_id = responsible_user.id
```

**Note:** Do NOT use `model_dump(exclude_none=True)` for `FinancialEntryUpdatePublic` — use `model_fields_set` to handle `responsible_user_uuid=null` (clear) vs absent (no-op).

#### IntegrityError → 409 pattern (D-REC-01):
```python
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
```

#### `session.execute()` with LEFT JOIN for `entry_uuid` + `?reconciled` filter (D-MOV-01/02):
```python
# Substituir session.exec() simples em list_movements por session.execute() com outerjoin
stmt = (
    select(Movement, FinancialEntry.uuid.label("entry_uuid"))
    .select_from(
        outerjoin(Movement, FinancialEntry, FinancialEntry.movement_id == Movement.id)
    )
    .where(Movement.account_id == db_account.id)
)
if reconciled is False:
    stmt = stmt.where(FinancialEntry.id.is_(None))
elif reconciled is True:
    stmt = stmt.where(FinancialEntry.id.is_not(None))

stmt = stmt.order_by(Movement.date.desc()).offset(offset).limit(limit)
result = await session.execute(stmt)
rows = result.fetchall()
# rows[i][0] = Movement, rows[i][1] = entry_uuid (UUID | None)
```

**Note:** Use `result.fetchall()` for multi-entity select — NOT `result.scalars()` which drops extra columns (pitfall P5 in RESEARCH).

#### `session.execute()` for aggregations — saldo endpoints (D-BAL-01/02/03):
```python
# REL-01: saldo de conta
from sqlalchemy import func, select
result = await session.execute(
    select(func.sum(Movement.amount)).where(Movement.account_id == db_account.id)
)
balance = result.scalar_one_or_none()
return Decimal(balance) if balance is not None else Decimal("0.00")
```

**Note:** NEVER use `session.exec()` for aggregations — always `session.execute()` + `.scalar_one_or_none()` (pitfall P3 from STATE.md, confirmed in RESEARCH).

#### Response construction — explicit schema build (pattern throughout operations.py):
Never use `response_model_by_alias` or ORM direct serialization. Build schema explicitly:
```python
return AccountReadPublic(
    uuid=db_account.uuid,
    family_uuid=family.uuid,
    name=db_account.name,
    ...
)
```

Same for `FinancialEntryRichPublic` — build from query results explicitly, no lazy load:
```python
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
    responsible_user_uuid=responsible_user.uuid if responsible_user else None,
    created_at=db_entry.created_at,
    updated_at=db_entry.updated_at,
)
```

#### GROUP BY aggregation for monthly report (D-REP-01/03/04):
```python
# Usar session.execute() com func.sum + group_by
from sqlalchemy import func
stmt = (
    select(
        Category.uuid.label("category_uuid"),
        Category.name.label("category_name"),
        Subcategory.uuid.label("subcategory_uuid"),
        Subcategory.name.label("subcategory_name"),
        func.sum(Movement.amount).label("total"),
        func.count(FinancialEntry.id).label("count"),
    )
    .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
    .join(Category, Subcategory.category_id == Category.id)
    .join(Movement, FinancialEntry.movement_id == Movement.id)
    .join(Account, Movement.account_id == Account.id)
    .where(
        Account.family_id == family_id,
        FinancialEntry.competencia_year == year,
        FinancialEntry.competencia_month == month,
    )
    .group_by(
        Category.id, Category.uuid, Category.name,
        Subcategory.id, Subcategory.uuid, Subcategory.name,
    )
)
result = await session.execute(stmt)
rows = result.fetchall()
# rows[i] é Row com atributos nomeados via .label()
```

---

### `src/caramello/finances/services.py` — 5 new service functions

**Analog:** `src/caramello/finances/services.py` lines 310–451 (`import_movements`)

#### Module header pattern (lines 1–23):
```python
"""Serviços de domínio para finances — lógica pura, sem dependências FastAPI.

Funções recebem AsyncSession e parâmetros diretos (não via Depends),
tornando-as reutilizáveis em testes e outros callers sem framework.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
# session.execute() para agregações — nunca session.exec() (pitfall P3)
```

#### Service function signature pattern (lines 310–325):
```python
async def import_movements(
    content: bytes,
    format: str,
    account_id: int,
    session: AsyncSession,
) -> dict[str, Any]:
    """Docstring com referência ao requisito.

    Sem dependências FastAPI — não usa HTTPException, Request, Depends.
    """
```

New functions follow the same pattern — pure async, no FastAPI deps, typed params:
```python
async def account_balance(account_id: int, session: AsyncSession) -> Decimal:
    """REL-01: Calcula saldo da conta via SUM(movement.amount)."""
    from sqlalchemy import func, select as sa_select
    result = await session.execute(
        sa_select(func.sum(Movement.amount)).where(Movement.account_id == account_id)
    )
    total = result.scalar_one_or_none()
    return total if total is not None else Decimal("0.00")  # pitfall P6


async def suggest_category(
    movement_uuid: UUID,
    family_id: int,
    session: AsyncSession,
) -> list[dict]:
    """LAN-03: Top-5 sugestões de subcategoria por similaridade de descrição."""
```

#### `suggest_category` — rapidfuzz pattern (D-CAT-01/02/03/04):
```python
from rapidfuzz import fuzz

async def suggest_category(movement_uuid, family_id, session):
    # 1. Buscar Movement alvo
    result = await session.execute(
        select(Movement).where(Movement.uuid == movement_uuid)
    )
    row = result.fetchone()
    if row is None:
        return []
    target_desc = row[0].description

    # 2. Buscar histórico da família: (description, subcategory_id, subcategory_uuid,
    #    subcategory_name, category_uuid, category_name)
    stmt = (
        select(
            Movement.description,
            Subcategory.id.label("subcategory_id"),
            Subcategory.uuid.label("subcategory_uuid"),
            Subcategory.name.label("subcategory_name"),
            Category.uuid.label("category_uuid"),
            Category.name.label("category_name"),
        )
        .join(FinancialEntry, FinancialEntry.movement_id == Movement.id)
        .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
        .join(Category, Subcategory.category_id == Category.id)
        .join(Account, Movement.account_id == Account.id)
        .where(Account.family_id == family_id)
    )
    entries_result = await session.execute(stmt)
    entries = entries_result.fetchall()

    if not entries:
        return []  # D-CAT-03: sem histórico → lista vazia, sem erro

    # 3. Score por subcategoria — max score por subcategory_id
    scored: dict[int, dict] = {}
    for entry in entries:
        score = int(fuzz.token_set_ratio(target_desc, entry[0]))  # A1: cast para int
        sub_id = entry[1]
        if sub_id not in scored or score > scored[sub_id]["score"]:
            scored[sub_id] = {
                "subcategory_uuid": entry[2],
                "subcategory_name": entry[3],
                "category_uuid": entry[4],
                "category_name": entry[5],
                "score": score,
            }

    # 4. Top-5 decrescente (D-CAT-01: sem threshold mínimo)
    top5 = sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:5]
    return top5
```

**Note:** `rapidfuzz.fuzz.token_set_ratio` returns `float` — cast to `int` before returning (A1 from RESEARCH assumptions).

---

### `alembic/versions/0004_financial_entry_responsible_user.py` — migration ADD COLUMN

**Analog:** `alembic/versions/0003_movement_schema_update.py` (lines 1–38)

#### Full migration structure (copy from 0003, adapt):
```python
"""0004_financial_entry_responsible_user

Adiciona campo responsible_user_id em financial_entry.

Revision ID: 0004
Revises: 0003
Create Date: [data]
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"  # VERIFICAR: alembic history --verbose antes de usar
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_entry",
        sa.Column(
            "responsible_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("financial_entry", "responsible_user_id")
```

**Critical:** `down_revision` MUST point to `"0003"` (pitfall P4 in RESEARCH). Verify with `alembic history --verbose` before finalizing.

**Note re: `server_default`:** Unlike 0003's downgrade which uses `sa.text("'credito'")` for non-nullable columns, this ADD COLUMN is nullable — no `server_default` needed. Existing rows will have `NULL` automatically.

---

### `tests/test_finances_operations.py` — add Phase 9 stubs

**Analog:** `tests/test_finances_operations.py` lines 744–835 (`test_create_movement` — Phase 8 stub pattern)

#### Test module header + skip mechanism (lines 1–58):
```python
from __future__ import annotations
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

def _skip_if_stub() -> None:
    pytest.importorskip("caramello.finances.operations")
    ops_path = (Path(__file__).resolve().parents[1] / "src/caramello/finances/operations.py")
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0].strip()
        if "stub" in first_line:
            pytest.skip("finances/operations.py ainda é stub")
```

#### Mock session setup pattern (lines 800–815):
```python
mock_execute_result = MagicMock()
mock_execute_result.fetchall.return_value = []   # for session.execute()
mock_execute_result.scalar_one_or_none.return_value = Decimal("0.00")  # for balance queries

mock_session = AsyncMock()
mock_session.exec.side_effect = _exec          # for session.exec() (ORM object lookups)
mock_session.execute = AsyncMock(return_value=mock_execute_result)  # for aggregations + JOINs
mock_session.add = MagicMock()
mock_session.commit = AsyncMock()
mock_session.refresh = AsyncMock()
mock_session.rollback = AsyncMock()            # NEW: needed for IntegrityError test (LAN-02)
```

#### Dependency override pattern (lines 183–204):
```python
app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_session] = _session_override
try:
    client = TestClient(app)
    response = client.post("/finances/movements/{uuid}/reconcile", json={...})
    assert response.status_code == 201, response.text
    body = response.json()
    assert "uuid" in body
finally:
    app.dependency_overrides.clear()
```

#### `test_finances_router_paths` — update expected set (lines 96–112):
Add to `expected` set:
```python
expected = {
    # ... existing Phase 7/8 paths ...
    "/finances/movements/{movement_uuid}/reconcile",
    "/finances/movements/{movement_uuid}/suggest-category",
    "/finances/entries/{entry_uuid}",
    "/finances/entries",
    "/finances/accounts/{account_uuid}/balance",
    "/finances/families/{family_uuid}/balance",
    "/finances/reports/monthly",
    "/finances/reports/by-member",
}
```

---

### `tests/test_services/test_finances_service.py` — add Phase 9 stubs

**Analog:** `tests/test_services/test_finances_service.py` lines 17–45 (`test_parse_csv` — existing stub pattern)

#### Service test pattern — lazy import + pytest.importorskip (lines 17–27):
```python
def test_suggest_category_service():
    """LAN-03: suggest_category retorna top-5 com score quando há histórico."""
    services = pytest.importorskip("caramello.finances.services")
    suggest_cat = getattr(services, "suggest_category", None)
    if suggest_cat is None:
        pytest.skip("suggest_category ainda não implementada em caramello.finances.services")
    # ...
```

#### Unit test for pure functions — no session needed (lines 17–80):
Pure functions (`_parse_csv`, `_compute_hash`) are tested without mock session. Functions requiring session (`suggest_category`, `account_balance`) use `AsyncMock`:
```python
from unittest.mock import AsyncMock, MagicMock
import pytest
import asyncio
from decimal import Decimal

def test_account_balance_empty():
    """REL-01: account_balance retorna Decimal('0.00') quando não há movimentações."""
    services = pytest.importorskip("caramello.finances.services")
    account_balance = getattr(services, "account_balance", None)
    if account_balance is None:
        pytest.skip("account_balance ainda não implementada")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # SUM() sobre vazio retorna None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    balance = asyncio.get_event_loop().run_until_complete(
        account_balance(account_id=1, session=mock_session)
    )
    assert balance == Decimal("0.00"), f"Saldo vazio deve ser Decimal('0.00'); foi: {balance}"
```

---

## Shared Patterns

### Authentication — `get_current_user` + `_require_family_access`
**Source:** `src/caramello/shared/auth.py` lines 107–270
**Apply to:** All 9 new endpoints in `operations.py`

```python
# Padrão de assinatura em todos os endpoints:
async def endpoint_name(
    ...,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ResponseSchema:

# Verificação de membership após resolver family_id:
await _require_family_access(family_id, current_user, session)
```

For FinancialEntry endpoints — resolve access via movement chain:
```python
# movement_uuid → movement → account → account.family_id → _require_family_access
result = await session.exec(select(Movement).where(Movement.uuid == movement_uuid))
db_movement = result.first()
if db_movement is None:
    raise HTTPException(status_code=404, detail="Movimentação não encontrada")

account_result = await session.exec(select(Account).where(Account.id == db_movement.account_id))
db_account = account_result.first()
await _require_family_access(db_account.family_id, current_user, session)
```

For report endpoints — resolve via family_uuid:
```python
family_result = await session.exec(select(Family).where(Family.uuid == family_uuid))
family = family_result.first()
if family is None:
    raise HTTPException(status_code=404, detail="Família não encontrada")
await _require_family_access(family.id, current_user, session)
```

### Error Handling
**Source:** `src/caramello/finances/operations.py` throughout
**Apply to:** All new endpoints

| Status | When | Pattern |
|--------|------|---------|
| 404 | UUID lookup returns None | `raise HTTPException(status_code=404, detail="X não encontrado")` |
| 409 | `IntegrityError` on unique constraint | `except IntegrityError: await session.rollback(); raise HTTPException(409, ...)` |
| 422 | Pydantic validation or business rule (bad UUID, non-member) | `raise HTTPException(status_code=422, detail="mensagem clara")` |
| 403 | Non-member access | handled by `_require_family_access` |
| 401 | No token | handled by `get_current_user` |

### `updated_at` Manual Setting
**Source:** `src/caramello/finances/operations.py` line 295
**Apply to:** All PATCH endpoints (entries update)

```python
db_entry.updated_at = datetime.now(timezone.utc)
session.add(db_entry)
await session.commit()
await session.refresh(db_entry)
```

### `session.execute()` vs `session.exec()`
**Source:** `src/caramello/finances/operations.py` lines 730–731, `src/caramello/finances/services.py` lines 354–358
**Apply to:** All aggregation queries, LEFT JOIN queries, GROUP BY queries

```python
# CORRETO — usa session.execute() para agregações e JOINs multi-entidade
result = await session.execute(stmt)
rows = result.fetchall()       # para multi-entity select
scalar = result.scalar_one_or_none()  # para func.sum/count

# INCORRETO — session.exec() apenas para ORM object lookups simples
result = await session.exec(select(Movement).where(Movement.uuid == uuid))
obj = result.first()
```

### UUID Público — Nunca `id` Interno
**Source:** `src/caramello/finances/operations.py` lines 177–186 (response construction)
**Apply to:** All response schemas, all path parameters

- Path params: `{movement_uuid}`, `{entry_uuid}`, `{account_uuid}`, `{family_uuid}`
- Response schemas: expose `uuid: UUID`, never `id: int`
- Resolve chain: `public_uuid → ORM_id` at the start of each handler; use `ORM_id` for joins

### `Decimal` para Valores Monetários
**Source:** `src/caramello/finances/models.py` line 69, `src/caramello/finances/services.py` line 199
**Apply to:** All balance fields, all aggregated totals

```python
# Em modelos:
amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))

# Em schemas de resposta (Pydantic v2 serializa como string JSON "123.45"):
balance: Decimal  # sem configuração adicional

# Guard para SUM() sobre conjunto vazio (pitfall P6):
total = result.scalar_one_or_none()
return total if total is not None else Decimal("0.00")
```

---

## No Analog Found

None. All files are extensions of existing files with established patterns. No new architectural territory.

---

## Key Anti-Patterns (from RESEARCH pitfalls — enforce in planning)

| Anti-Pattern | Where it bites | Correct Approach |
|---|---|---|
| `session.exec()` for `func.sum` | `account_balance`, `monthly_breakdown` | Always `session.execute()` + `.scalar_one_or_none()` |
| `model_dump(exclude_none=True)` on PATCH | `update_entry` handler | Use `model_fields_set` for `responsible_user_uuid` |
| Missing `updated_at = datetime.now(...)` in PATCH | All PATCH handlers | Always set manually before commit |
| `down_revision = "0002"` in migration 0004 | Alembic history fork | Verify with `alembic history --verbose`; use `"0003"` |
| `result.scalars()` on multi-entity select | LEFT JOIN for `entry_uuid` | Use `result.fetchall()`, access by position |
| `float` for monetary values | balance responses | Always `Decimal`; never cast to `float` |
| Editing files in `models/` or `api/generated/` | DSL-generated code | `finances/models.py` has `# CARAMELLO-GENERATED: implemented` — manual edit allowed here only |

---

## Metadata

**Analog search scope:** `src/caramello/finances/`, `src/caramello/shared/`, `alembic/versions/`, `tests/`
**Files scanned:** 8 source files read directly
**Pattern extraction date:** 2026-06-03
