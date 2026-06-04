---
phase: 02-stack-async
reviewed: 2026-05-25T02:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - pyproject.toml
  - src/caramello/shared/__init__.py
  - src/caramello/shared/database.py
  - src/caramello/core/config.py
  - alembic/env.py
  - scripts/generate_code.py
  - src/caramello/api/generated/user_router.py
  - src/caramello/api/generated/family_router.py
  - src/caramello/api/generated/familymember_router.py
  - src/caramello/api/generated/familyinvitation_router.py
  - src/caramello/models/user.py
  - src/caramello/models/family.py
  - src/caramello/models/familymember.py
  - src/caramello/models/familyinvitation.py
  - tests/generated/test_user.py
  - tests/generated/test_family.py
  - tests/generated/test_familyinvitation.py
findings:
  critical: 5
  warning: 7
  info: 3
  total: 15
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-25T02:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This phase migrates the stack from `psycopg2-binary` (sync) to `asyncpg` (async) across engine, session, routers, and Alembic. The async plumbing is structurally sound — `create_async_engine`, `async_sessionmaker`, `AsyncSession`, and `async_engine_from_config` are all wired correctly. However, five blockers must be resolved before this phase ships: one is a confirmed runtime crash (CORS env var), one silently breaks all generated tests, two expose or accept internal database IDs through the public API violating the project's own UUID-only convention, and one causes the code generator to fail at import time in any environment without database credentials.

---

## Critical Issues

### CR-01: `CORS_ORIGINS` lista falha ao ser lida do env var — crash em produção

**File:** `src/caramello/core/config.py:26`
**Issue:** `CORS_ORIGINS: list[str]` typed as a Python list in a `pydantic-settings` v2 `BaseSettings` class. When this variable is set as a comma-separated string in the environment (e.g. `CORS_ORIGINS=http://a.com,http://b.com`), pydantic-settings v2 raises `SettingsError: error parsing value for field "CORS_ORIGINS"` at startup — verified by running the actual code. The default value works only because it is set in Python; any real deployment that configures CORS via env var will fail to start.

**Fix:** Either declare the expected format as a JSON array in the env var (`CORS_ORIGINS='["http://a.com","http://b.com"]'`) and document it, or add a validator that accepts both forms:
```python
from pydantic import field_validator

CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

@field_validator("CORS_ORIGINS", mode="before")
@classmethod
def parse_cors_origins(cls, v: object) -> list[str]:
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",")]
    return v  # type: ignore[return-value]
```

---

### CR-02: `scripts/generate_code.py` importa `settings` sem usar — falha em CI sem credenciais de DB

**File:** `scripts/generate_code.py:5`
**Issue:** `from caramello.core.config import settings` is at module level but `settings` is never referenced anywhere in the file (grep confirms zero uses of `settings.`). Because `Settings()` is instantiated at import time and requires `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` to be present, running `uv run python scripts/generate_code.py` in any CI environment or fresh checkout without a `.env` file or exported DB credentials raises a `ValidationError` and aborts — before any code generation occurs. This is a pure dead import that breaks the development workflow.

**Fix:** Remove the unused import entirely:
```python
# Remove this line — settings is not used by the generator
# from caramello.core.config import settings
```

---

### CR-03: `familymember_router.py` expõe o modelo de tabela bruto — vaza `id` interno e aceita mutação arbitrária de PK

**File:** `src/caramello/api/generated/familymember_router.py:10,20`
**Issue:** Both endpoints use `response_model=FamilyMember` (the `table=True` SQLModel class) instead of `FamilyMemberRead`. The `FamilyMember` table model includes the composite primary key fields `user_id` and `family_id` as `Optional[int]` with `primary_key=True`. This means (a) internal integer IDs are serialized into every API response, violating the project's convention of only exposing `uuid` externally, and (b) there is no separation between read schema and table schema.

**Fix:** Change both `response_model` annotations to `FamilyMemberRead`:
```python
from caramello.models.familymember import FamilyMember, FamilyMemberRead

@router.get("/", response_model=list[FamilyMemberRead])
@router.get("/{user_id}", response_model=FamilyMemberRead)
```

---

### CR-04: `FamilyMember` e `FamilyInvitation` aceitam `user_id` / `family_id` / `inviter_id` como inteiros internos na API pública

**File:** `src/caramello/models/familymember.py:25-28`, `src/caramello/models/familyinvitation.py:33-34`
**Issue:** `FamilyMemberCreate`, `FamilyMemberUpdate`, `FamilyInvitationCreate`, and `FamilyInvitationUpdate` expose `user_id: int`, `family_id: int`, and `inviter_id: int` as direct API inputs. The project convention (documented in CLAUDE.md) is that "external URLs and API responses use `uuid`, never `id`". Accepting internal integer FKs in payloads: (1) forces callers to know internal IDs which are never returned in any UUID-based response, (2) creates a path for ID enumeration (caller can brute-force valid integer IDs), and (3) contradicts the stated design that consumers should use `uuid`.

**Fix:** Replace integer FK fields in Create/Update schemas with UUID fields, and resolve the FK lookup in the router before persisting:
```python
# In FamilyInvitationCreate:
family_uuid: UUID
inviter_uuid: UUID

# In the router POST handler, look up the integer IDs:
family = (await session.exec(select(Family).where(Family.uuid == data.family_uuid))).first()
if not family:
    raise HTTPException(status_code=404, detail="Family not found")
```

---

### CR-05: `alembic/env.py` — modo offline usa driver `asyncpg` sem event loop; migrações offline vão falhar

**File:** `alembic/env.py:44-53`
**Issue:** `run_migrations_offline()` passes `url = settings.DATABASE_URL` which is `postgresql+asyncpg://...`. Alembic offline mode does not open a real connection but does instantiate the dialect to render SQL. The `asyncpg` dialect requires an async context for some operations. More critically, `literal_binds=True` at line 48 can trigger dialect-level rendering that fails with the asyncpg dialect in a synchronous stack trace. The async path (`run_async_migrations`) is correct; the offline path is inconsistent.

**Fix:** Use `postgresql://` (psycopg2/psycopg3) for offline mode, or derive a sync-compatible URL for the offline case:
```python
def run_migrations_offline() -> None:
    url = str(settings.DATABASE_URL).replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
```
Alternatively, install `psycopg2-binary` back as a dev dependency for Alembic offline use only.

---

## Warnings

### WR-01: `updated_at` não é atualizado nas operações PATCH

**File:** `src/caramello/api/generated/user_router.py:48-54`, `family_router.py:48-54`, `familyinvitation_router.py:48-54`
**Issue:** The PATCH handler iterates over `model_dump(exclude_unset=True)` and `setattr`s each field, but never sets `updated_at`. Since `updated_at` has a `default_factory` (set only at object creation), it stays permanently at the creation timestamp. This makes audit/cache-invalidation logic based on `updated_at` incorrect from the first PATCH onward.

**Fix:** Add an explicit timestamp update in the PATCH handler template (in `generate_router` in `scripts/generate_code.py`):
```python
from datetime import datetime, timezone
# after the setattr loop:
db_obj.updated_at = datetime.now(timezone.utc)
```

---

### WR-02: `familymember_router.py` usa `user_id` inteiro como parâmetro de rota pública

**File:** `src/caramello/api/generated/familymember_router.py:20-27`
**Issue:** `GET /family_member/{user_id}` accepts an integer `user_id`. This exposes an internal PK in the URL path, directly violating the project's convention and making it impossible to look up a membership by UUID. The route also only matches by `user_id`, so if a user belongs to multiple families, it returns only the first row silently.

**Fix:** Change the route to accept a UUID and query by user.uuid (via join), or restructure as `/family_member/?user_uuid=...`. At minimum, document the ambiguity and handle the multi-family case.

---

### WR-03: Template `generate_router` usa variável `hero_data` — nome incorreto copiado de tutorial

**File:** `scripts/generate_code.py:308-309` (propagated to all three generated routers)
**Issue:** The PATCH handler uses `hero_data` as the variable name for the deserialized update dict in every generated router (`user_router.py:48`, `family_router.py:48`, `familyinvitation_router.py:48`). This is a copy-paste artifact from the FastAPI SQLModel tutorial. The code is functionally correct but the variable name refers to an unrelated domain entity ("Hero"), which makes the generated code confusing to read and violates naming consistency.

**Fix:** Change the template in `generate_code.py` line 308:
```python
    update_data = {var_name}_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
```

---

### WR-04: `FamilyMember.user` e `FamilyMember.family` Relationships sem `back_populates`

**File:** `src/caramello/models/familymember.py:16-17`
**Issue:** Both `Relationship()` calls on `FamilyMember` have no `back_populates` argument. This means SQLModel/SQLAlchemy cannot maintain bidirectional state — loading a `User` and accessing `.families` will not populate `FamilyMember.user` and vice versa. The relationships are effectively one-directional and inconsistent with the `back_populates` used in `User.families` and `Family.members`.

**Fix:**
```python
user: Optional['User'] = Relationship(back_populates='family_memberships')
family: Optional['Family'] = Relationship(back_populates='memberships')
```
(Requires adding corresponding `family_memberships` and `memberships` relationships on `User` and `Family` respectively, or using `sa_relationship_kwargs` to configure `overlaps`.)

---

### WR-05: `get_session` não faz rollback explícito em caso de exceção

**File:** `src/caramello/shared/database.py:21-23`
**Issue:** `async with async_session_factory() as session: yield session` relies on `asyncpg` and SQLAlchemy's context manager to handle cleanup. If an exception is raised inside a router after `session.add()` but before `await session.commit()`, the transaction is rolled back by the context manager. However, if `await session.commit()` itself raises (e.g., unique constraint violation, FK violation), the error propagates as an unhandled `IntegrityError` from asyncpg — there is no try/except in any router to convert this to a clean HTTP 409. Users receive a raw 500.

**Fix:** Either add a try/except in the session dependency:
```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```
Or add per-router exception handling for `sqlalchemy.exc.IntegrityError`.

---

### WR-06: Tests usam `TestClient` síncrono sem override de `get_session` — conectam ao banco real

**File:** `tests/generated/test_user.py:9-10`, `test_family.py:9-10`, `test_familyinvitation.py:9-10`
**Issue:** All three test files create `TestClient(app)` with no `app.dependency_overrides`. `TestClient` can drive async FastAPI apps but the session dependency will attempt to connect to the real database configured by `.env`. There is no in-memory test database, no fixture to override `get_session`, and the `tests/conftest.py` is empty. Any CI run without a real PostgreSQL instance fails at the first request. Tests also share global state (no teardown), so test order affects results.

**Fix:** Add a conftest that overrides `get_session` with a test database or an in-memory SQLite (note: SQLite is documented as not supported — use a test PostgreSQL container). Minimum viable fix:
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from caramello.main import app
from caramello.shared.database import get_session

@pytest.fixture
def client(test_session):
    app.dependency_overrides[get_session] = lambda: test_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

---

### WR-07: `FamilyInvitation.expires_at` sem fuso horário — comparação com `datetime.now(timezone.utc)` retorna erro

**File:** `src/caramello/models/familyinvitation.py:18`
**Issue:** `expires_at: datetime = Field(nullable=False)` has no `default_factory` and the DSL does not set `timezone=True` on the column. PostgreSQL will store it as `TIMESTAMP WITHOUT TIME ZONE`. When application code compares `expires_at` with `datetime.now(timezone.utc)` (which is timezone-aware), Python will raise `TypeError: can't compare offset-naive and offset-aware datetimes`. This is latent — no comparison logic exists yet — but it will break the first time invitation expiry is implemented.

**Fix:** Add `sa_column=Column(DateTime(timezone=True))` to the `expires_at` field, or ensure the DSL generates timezone-aware columns for all `datetime` fields.

---

## Info

### IN-01: `pyproject.toml` — `packages` declarado fora de `[tool.setuptools]`

**File:** `pyproject.toml:32`
**Issue:** `packages = [{ include = "caramello", from = "src" }]` appears at top-level in the `[project]` table section (after `[tool.alembic]`), not under `[tool.setuptools.packages.find]` or `[tool.setuptools]`. `setuptools` may silently ignore it, causing the package to not be included in a built wheel. Works in development with `pip install -e .` due to the src layout being visible, but a production build would be broken.

**Fix:**
```toml
[tool.setuptools.packages.find]
where = ["src"]
```

---

### IN-02: `List` importado mas não usado em vários models

**File:** `src/caramello/models/familymember.py:1`, `src/caramello/models/familyinvitation.py:1`
**Issue:** `from typing import Optional, List` is in all four model files but `List` is never referenced — the code uses `list[...]` (lowercase, Python 3.9+ builtin) everywhere. `EmailStr` is also imported in `familymember.py` and `familyinvitation.py` (line 5) but never used in those files.

**Fix:** Remove unused imports. Since `ruff` excludes `src/caramello/models/.*` (pyproject.toml line 52-54), this won't be caught automatically. Consider removing the ruff exclusion for the `models/` directory if linting generated code is acceptable.

---

### IN-03: `read_familys` — nome de função gerado incorreto para pluralização

**File:** `src/caramello/api/generated/family_router.py:21`
**Issue:** The list endpoint function is named `read_familys` (naive `+s` pluralization). The generator uses `f"read_{var_name}s"` with no irregular-plural handling. This is cosmetically wrong and will appear in OpenAPI documentation. (The same pattern appears in `familymember_router.py` → `read_familymembers` and `familyinvitation_router.py` → `read_familyinvitations`, which are acceptable.)

**Fix:** In `generate_router` in `scripts/generate_code.py`, apply basic pluralization rules or accept an explicit `plural_name` field in the DSL entity definition.

---

_Reviewed: 2026-05-25T02:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
