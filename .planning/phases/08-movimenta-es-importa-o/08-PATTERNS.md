# Phase 8: Movimentações + Importação - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 7 new/modified files
**Analogs found:** 6 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `dsl/entities/movement.yaml` | config | transform | `dsl/entities/account.yaml` | role-match |
| `src/caramello/finances/models.py` | model | CRUD | `src/caramello/finances/models.py` (current `Movement` class) | exact (self-ref — regenerated) |
| `src/caramello/finances/operations.py` | controller | request-response + file-I/O | `src/caramello/finances/operations.py` (existing endpoints) | exact |
| `src/caramello/finances/services.py` | service | file-I/O + batch + transform | `src/caramello/families/services.py` | role-match |
| `alembic/versions/0003_movement_schema_update.py` | migration | CRUD | `alembic/versions/0002_finances_schema.py` | exact |
| `tests/test_finances_operations.py` | test | request-response | `tests/test_finances_operations.py` (existing tests) | exact |
| `tests/test_services/test_finances_service.py` | test | transform + batch | `tests/test_services/test_family_service.py` | role-match |

---

## Pattern Assignments

### `dsl/entities/movement.yaml` (config, transform)

**Analog:** `dsl/entities/movement.yaml` (current — edit in place)

**What to change** — remove two fields, update one description:

Fields to **remove** from the `fields:` list (D-01, D-02):
```yaml
  # REMOVE THIS ENTIRE BLOCK:
  - name: type
    type: str
    max_length: 10
    nullable: false
    description: "Tipo da movimentação: credito ou debito."

  # REMOVE THIS ENTIRE BLOCK:
  - name: is_duplicate
    type: bool
    default: false
    nullable: false
    description: "Indica se a movimentação foi marcada como duplicata (MOV-05)."
```

**Updated `amount` description** to reflect signed convention (D-01):
```yaml
  - name: amount
    type: Decimal
    nullable: false
    description: "Valor com sinal: positivo=crédito, negativo=débito. NUMERIC(15,2)."
```

**Retained fields** (no change): `id`, `uuid`, `account_id`, `date`, `description`, `import_hash`, `created_at`, `updated_at`, `filters`.

---

### `src/caramello/finances/models.py` (model, CRUD)

**Analog:** `src/caramello/finances/models.py` lines 58-112 (current `Movement` class)

**Generated via DSL — do not edit directly.** After editing `movement.yaml` and running `bin/generate_code`, the file will be regenerated. The resulting `Movement` ORM class must:
- Drop `type: str` field (lines 68, 85, 98, 108 in current file)
- Drop `is_duplicate: bool` field (lines 73, 90, 100, 112 in current file)
- Retain `import_hash: str | None = Field(unique=True, default=None)` (line 72)
- Retain `amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))` (line 70)

**Current Movement ORM pattern to preserve** (`src/caramello/finances/models.py` lines 58-79):
```python
class Movement(SQLModel, table=True):
    __tablename__ = "movement"
    __table_args__ = (Index("ix_movement_account_id", "account_id"),)

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    account_id: int = Field(foreign_key="account.id", nullable=False)
    date: datetime = Field(nullable=False)
    amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))
    description: str = Field(max_length=255, nullable=False)
    import_hash: str | None = Field(unique=True, default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
```

---

### `src/caramello/finances/operations.py` (controller, request-response + file-I/O)

**Analog:** `src/caramello/finances/operations.py` (same file — extend, do not replace)

**Imports pattern to add** (at top of file, after existing imports, lines 1-25):
```python
# Additional imports for Phase 8 Movement endpoints
from decimal import Decimal
from typing import Any

from fastapi import File, Query, UploadFile

from caramello.finances.models import Movement
from caramello.finances.services import import_movements
```

**Schema pattern** (copy structure from `AccountReadPublic`, lines 42-51):
```python
class MovementCreatePublic(BaseModel):
    date: str  # ISO 8601 or DD/MM/YYYY — parsed by service layer
    amount: Decimal
    description: str


class MovementReadPublic(BaseModel):
    uuid: UUID
    date: datetime
    amount: Decimal
    description: str
    import_hash: str | None = None  # D-16: optional, for debug
    created_at: datetime
    updated_at: datetime


class ImportResultPublic(BaseModel):
    inserted: int
    duplicates_skipped: int
    potential_duplicates: list[dict[str, Any]]
    error_lines: list[dict[str, Any]]
    movements: list[MovementReadPublic]


class ConfirmImportPublic(BaseModel):
    hashes: list[str]  # SHA-256 hashes the user confirmed as non-duplicates
```

**Auth + account resolution pattern** (copy from `get_account`, lines 183-211):
```python
# Pattern: account_uuid path param → resolve Account → _require_family_access
result = await session.exec(select(Account).where(Account.uuid == account_uuid))
db_account = result.first()
if db_account is None:
    raise HTTPException(status_code=404, detail="Conta não encontrada")
await _require_family_access(db_account.family_id, current_user, session)
```

**POST individual movement pattern** (adapt from `create_account`, lines 99-142):
```python
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
    # 1. Resolve account + check access (pattern above)
    # 2. Compute hash
    # 3. 409 if hash exists (D-17)
    # 4. session.add + commit + refresh (same as create_account lines 127-141)
```

**409 Conflict pattern** (new — from RESEARCH.md Padrão 7):
```python
existing = await session.exec(
    select(Movement).where(Movement.import_hash == computed_hash)
)
dup = existing.first()
if dup is not None:
    raise HTTPException(
        status_code=409,
        detail={"message": "Movimentação já existe", "existing_uuid": str(dup.uuid)},
    )
```

**GET list with pagination pattern** (adapt from `list_accounts`, lines 145-180):
```python
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
    # Pattern: resolve account, check access, then session.execute() for filtered query
    # Use session.execute() (not session.exec()) for queries with limit/offset/filters
```

**File upload pattern** (new — from RESEARCH.md Padrão 1):
```python
@router.post("/accounts/{account_uuid}/movements/import")
async def import_movements_endpoint(
    account_uuid: UUID,
    file: UploadFile = File(...),
    format: Literal["csv", "ofx", "xlsx"] = Query(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportResultPublic:
    content: bytes = await file.read()
    # Resolve account, check access, then call services.import_movements()
```

**session.execute() for batch hash pre-check** (from `shared/auth.py` lines 192-199 — same pg_insert pattern):
```python
# For batch pre-check — use session.execute(), NOT session.exec()
result = await session.execute(
    select(Movement.import_hash).where(Movement.import_hash.in_(all_hashes))
)
existing_hashes = {row[0] for row in result.fetchall()}
```

**updated_at manual pattern** (copy from `update_account`, line 247):
```python
db_movement.updated_at = datetime.now(timezone.utc)
```

---

### `src/caramello/finances/services.py` (service, file-I/O + batch + transform)

**Analog:** `src/caramello/families/services.py` (structure) + RESEARCH.md patterns

**File header pattern** (copy from `src/caramello/families/services.py` lines 1-14):
```python
"""Serviços de domínio para finances — lógica pura, sem dependências FastAPI.

Funções recebem AsyncSession e parâmetros diretos (não via Depends),
tornando-as reutilizáveis em testes e outros callers sem framework.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
```

**ParsedRow dataclass pattern** (new — no direct analog, modeled on stdlib dataclass):
```python
@dataclass
class ParsedRow:
    date: datetime
    amount: Decimal
    description: str
    fitid: str | None = None  # OFX FITID — used as direct hash (D-04)
```

**Hash computation pattern** (from RESEARCH.md Code Examples):
```python
def _normalize_description(desc: str) -> str:
    return re.sub(r'\s+', ' ', desc.strip().lower())  # D-06

def _compute_hash(account_id: int, row: ParsedRow) -> str:
    if row.fitid:
        # D-04: OFX — FITID is the canonical hash
        raw = f"fitid:{row.fitid}"
    else:
        # D-07: CSV/XLSX — compound hash
        norm_desc = _normalize_description(row.description)
        raw = f"{account_id}|{row.date.date().isoformat()}|{row.amount}|{norm_desc}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Date parsing pattern** (from RESEARCH.md Code Examples):
```python
def _parse_date(value: str, line: int) -> datetime:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):  # D-12: ISO first, BR fallback
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Linha {line}: data inválida {value!r}")
```

**CSV parser pattern** (from RESEARCH.md Padrão 2):
```python
def _parse_csv(content: bytes) -> list[ParsedRow]:
    text = content.decode("utf-8", errors="replace")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:1024])  # D-10: auto-detect ; or ,
    except csv.Error:
        dialect = csv.excel  # D-07 Pitfall: fallback to comma
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    # D-11: headers case-insensitive, by name not position
```

**OFX parser pattern** (from RESEARCH.md Padrão 3):
```python
def _parse_ofx(content: bytes) -> list[ParsedRow]:
    try:
        from ofxparse import OfxParser
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception:
        # Pitfall 6: BR banks with ISO-8859-1 encoding
        text = content.decode("iso-8859-1", errors="replace")
        ofx = OfxParser.parse(io.StringIO(text))
    # txn.id is FITID (D-04), txn.amount already Decimal-compatible
```

**XLSX parser pattern** (from RESEARCH.md Padrão 4):
```python
def _parse_xlsx(content: bytes) -> list[ParsedRow]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    try:
        ws = wb.active
        # ... iterate, parse date/amount/description
    finally:
        wb.close()  # Pitfall 5: MANDATORY in read_only mode
```

**Batch hash pre-check pattern** (from RESEARCH.md Padrão 5, `session.execute()` from `shared/auth.py`):
```python
async def _existing_hashes(session: AsyncSession, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    result = await session.execute(
        select(Movement.import_hash).where(Movement.import_hash.in_(hashes))
    )
    return {row[0] for row in result.fetchall()}
```

**on_conflict_do_nothing safety net** (from `shared/auth.py` lines 192-199, same `pg_insert` import):
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = (
    pg_insert(Movement.__table__)
    .values([...])
    .on_conflict_do_nothing(index_elements=["import_hash"])
)
await session.execute(stmt)
await session.commit()
```

**Error threshold abort pattern** (new — no analog, from D-13):
```python
# D-13: abort if >50% of rows fail
if len(error_lines) / total_rows > 0.5:
    raise ValueError(
        f"Mais de 50% das linhas falharam ({len(error_lines)}/{total_rows}). "
        "Verificar formato do arquivo."
    )
```

**import_movements public interface** (service function signature):
```python
async def import_movements(
    content: bytes,
    format: str,  # "csv" | "ofx" | "xlsx"
    account_id: int,
    session: AsyncSession,
) -> dict[str, Any]:
    """Parseia arquivo de extrato, deduplica e persiste movimentações.

    Retorna dict com shape D-14: inserted, duplicates_skipped,
    potential_duplicates[], error_lines[], movements[].
    """
```

---

### `alembic/versions/0003_movement_schema_update.py` (migration, CRUD)

**Analog:** `alembic/versions/0002_finances_schema.py` (full file)

**File header pattern** (copy from `0002_finances_schema.py` lines 1-24):
```python
"""0003_movement_schema_update

Remove colunas obsoletas da tabela movement:
- DROP COLUMN type (D-01: substituído por amount com sinal)
- DROP COLUMN is_duplicate (D-02: substituído por potential_duplicates[] na resposta)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"  # D-03: aponta para 0002
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**upgrade() pattern** (adapt from `0002_finances_schema.py` lines 27-147 — use `op.drop_column`):
```python
def upgrade() -> None:
    op.drop_column("movement", "type")
    op.drop_column("movement", "is_duplicate")
    # Note: NUMERIC(15,2) already accepts negative values — no ALTER needed
```

**downgrade() pattern** (adapt from `0002_finances_schema.py` lines 150-171 — use `op.add_column`):
```python
def downgrade() -> None:
    op.add_column(
        "movement",
        sa.Column("type", sa.String(length=10), nullable=False, server_default="credito"),
    )
    op.add_column(
        "movement",
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
    )
```

---

### `tests/test_finances_operations.py` (test, request-response)

**Analog:** `tests/test_finances_operations.py` (same file — extend, do not replace)

**Test file header pattern** (copy from existing file lines 1-23 — already `from __future__ import annotations`):
```python
# Same module-level imports — already present in existing file
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
```

**TestClient + dependency_overrides pattern** (copy from `test_create_account_returns_uuid`, lines 117-200):
```python
# Standard setup for all Movement tests:
from fastapi.testclient import TestClient
from caramello.main import app
from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session

fake_user = _make_fake_user()  # existing helper, line 43
mock_session = AsyncMock()
mock_session.exec.side_effect = _exec  # call_count pattern
mock_session.execute = AsyncMock()     # needed for hash pre-check (session.execute)
mock_session.add = MagicMock()
mock_session.commit = AsyncMock()
mock_session.refresh = AsyncMock()

def _session_override():
    yield mock_session

app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_session] = _session_override
try:
    client = TestClient(app)
    # ... assertions
finally:
    app.dependency_overrides.clear()  # always clean up
```

**call_count mock pattern for multi-step endpoints** (copy from lines 148-163):
```python
call_count = [0]

async def _exec(_stmt):
    r = MagicMock()
    call_count[0] += 1
    if call_count[0] == 1:
        r.first.return_value = fake_account  # resolve account by uuid
    elif call_count[0] == 2:
        r.first.return_value = MagicMock()   # membership check (non-None = member)
    else:
        r.first.return_value = None
    r.all.return_value = []
    return r
```

**File upload test pattern** (new — TestClient multipart):
```python
# For POST /accounts/{uuid}/movements/import
import io
response = client.post(
    f"/finances/accounts/{account_uuid}/movements/import?format=csv",
    files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
)
```

**Auth test pattern** (copy from `test_accounts_require_auth` and `test_accounts_403_non_member`, lines 275-368):
```python
# 401: do NOT override get_current_user — HTTPBearer raises 401 automatically
# 403: override get_current_user but make FamilyMember query return None (call_count[2])
```

---

### `tests/test_services/test_finances_service.py` (test, transform + batch)

**Analog:** `tests/test_services/test_family_service.py` (full file)

**File header pattern** (copy from `test_family_service.py` lines 1-10):
```python
"""Testes unitários de src/caramello/finances/services.py.

Testa parsers e lógica de deduplicação sem banco real (unit puro).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
```

**@pytest.mark.asyncio pattern** (copy from `test_family_service.py` lines 43-64):
```python
@pytest.mark.asyncio
async def test_parse_csv_detects_semicolon_separator():
    from caramello.finances.services import _parse_csv  # private function

    csv_content = b"date;amount;description\n2026-01-15;-100.00;PIX FULANO"
    rows = _parse_csv(csv_content)
    assert len(rows) == 1
    assert rows[0].amount == Decimal("-100.00")
```

**AsyncMock session pattern for service tests** (copy from `test_family_service.py` lines 54-63):
```python
mock_result = MagicMock()
mock_result.all.return_value = []

mock_session = AsyncMock()
mock_session.exec.return_value = mock_result
mock_session.execute = AsyncMock()  # for hash pre-check
mock_session.add = MagicMock()
mock_session.commit = AsyncMock()
```

**Pure unit test pattern** (for parser functions — no session needed, from RESEARCH.md Validation Architecture):
```python
# Parser tests are pure unit (no session mock needed):
def test_parse_csv_error_lines():
    from caramello.finances.services import _parse_csv
    # Line with invalid amount — should appear in error_lines[], not raise
    csv_content = b"date,amount,description\n2026-01-15,R$ 100,PIX"
    # ... assert error handling
```

---

## Shared Patterns

### Authentication + Account Resolution
**Source:** `src/caramello/finances/operations.py` lines 183-211 (get_account handler)
**Apply to:** All four Movement endpoint handlers
```python
result = await session.exec(select(Account).where(Account.uuid == account_uuid))
db_account = result.first()
if db_account is None:
    raise HTTPException(status_code=404, detail="Conta não encontrada")
await _require_family_access(db_account.family_id, current_user, session)
```

### session.execute() for Non-ORM Queries
**Source:** `src/caramello/shared/auth.py` lines 192-199
**Apply to:** `operations.py` (hash pre-check), `services.py` (hash batch lookup, pg_insert)
```python
# Use session.execute() — NOT session.exec() — for IN queries and pg_insert
await session.execute(insert_stmt)
result = await session.execute(select(Movement.import_hash).where(...))
```

### pg_insert + on_conflict_do_nothing
**Source:** `src/caramello/shared/auth.py` lines 191-199
**Apply to:** `services.py` import_movements (safety net after pre-check)
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = (
    pg_insert(Movement.__table__)
    .values([...])
    .on_conflict_do_nothing(index_elements=["import_hash"])
)
await session.execute(stmt)
await session.commit()
```

### Public Schema Pattern (no internal IDs)
**Source:** `src/caramello/finances/operations.py` lines 35-92 (all *Public classes)
**Apply to:** `MovementCreatePublic`, `MovementReadPublic`, `ImportResultPublic`
- Use `BaseModel` (not `SQLModel`)
- Expose `uuid` (not `id`)
- Expose FK as `*_uuid` (but for Movement: account_uuid omitted — it's in the URL per D-16)

### updated_at Manual Set
**Source:** `src/caramello/finances/operations.py` line 247
**Apply to:** Any endpoint that modifies a Movement
```python
db_movement.updated_at = datetime.now(timezone.utc)
```

### from __future__ import annotations
**Source:** `src/caramello/finances/operations.py` line 9
**Apply to:** All new/modified Python files in this phase

### Test Cleanup Pattern
**Source:** `tests/test_finances_operations.py` lines 179-200
**Apply to:** All new Movement tests in `test_finances_operations.py`
```python
app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_session] = _session_override
try:
    client = TestClient(app)
    # ... test body
finally:
    app.dependency_overrides.clear()
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `pyproject.toml` (add `ofxparse`, `openpyxl`) | config | — | Simple dependency addition — no analog needed; pattern is to add to `[project] dependencies` list (lines 6-19), then run `uv add ofxparse>=0.21 openpyxl>=3.1.5` |

---

## Key Anti-Patterns (from RESEARCH.md — enforce in all new code)

| Anti-Pattern | Where it bites | Correct pattern |
|---|---|---|
| `float` for monetary values | `_parse_csv`, `_parse_xlsx` parsers | `Decimal(str(cell_value))` always |
| `session.exec()` with `.in_()` | hash pre-check query | `session.execute()` instead |
| Editing `models.py` directly | `finances/models.py` | Edit `dsl/entities/movement.yaml`, run `bin/generate_code` |
| `import_hash` non-NULL on `/import/confirm` | Confirmed duplicates insert | Set `import_hash=None` on confirmed rows |
| Missing `wb.close()` on openpyxl | `_parse_xlsx` parser | `try/finally: wb.close()` |
| `down_revision` wrong in migration 0003 | alembic graph | Must be `"0002"` — verify with `alembic history --verbose` |

---

## Metadata

**Analog search scope:** `src/caramello/`, `tests/`, `alembic/versions/`, `dsl/entities/`
**Files scanned:** 18 Python files + 9 YAML files
**Pattern extraction date:** 2026-06-02
