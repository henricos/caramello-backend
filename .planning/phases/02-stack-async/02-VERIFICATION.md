---
phase: 02-stack-async
verified: 2026-05-25T03:00:00Z
status: human_needed
score: 13/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Execute `uv run alembic upgrade head` with a configured .env pointing to familia_dev PostgreSQL"
    expected: "Command completes without error, without hang, and without asyncpg connection-leak warnings"
    why_human: "Requires an external PostgreSQL database — cannot verify programmatically in sandbox environment"
---

# Phase 2: Stack Async — Verification Report

**Phase Goal:** Migrar toda a stack de queries de banco para async — substituir psycopg2-binary por asyncpg, criar shared/database.py async, migrar alembic para async, regenerar todos os routers como async.
**Verified:** 2026-05-25T03:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | asyncpg is the DB driver — psycopg2-binary removed | VERIFIED | `pyproject.toml` line 15: `"asyncpg>=0.31.0"`. No psycopg2 anywhere in pyproject.toml or uv.lock. |
| 2 | `grep -r "create_engine" src/` returns empty | VERIFIED | Grepped src/ + scripts/ + alembic/: only `create_async_engine` found; zero sync `create_engine` occurrences. |
| 3 | `shared/database.py` uses `create_async_engine` + `async_sessionmaker` + `AsyncSession` | VERIFIED | File at `src/caramello/shared/database.py` imports `create_async_engine`, `async_sessionmaker` from `sqlalchemy.ext.asyncio` and `AsyncSession` from `sqlmodel.ext.asyncio.session` (correct per PLAN — SQLModel's AsyncSession provides `session.exec()` async). |
| 4 | `alembic/env.py` uses `async_engine_from_config` with NullPool | VERIFIED | `alembic/env.py` has `async_engine_from_config` (imported from `sqlalchemy.ext.asyncio`), `poolclass=pool.NullPool`, `asyncio.run(run_async_migrations())`, `await connectable.dispose()`. ruff passes. |
| 5 | DSL generator produces routers with `async def` | VERIFIED | `scripts/generate_code.py::generate_router()` (lines 256–329) emits `async def` for all 5 CRUD endpoints, `await session.exec/commit/refresh/delete`, `AsyncSession` from sqlmodel, `get_session` from `caramello.shared.database`. |
| 6 | All 4 generated routers are in async mode | VERIFIED | `user_router.py`, `family_router.py`, `familyinvitation_router.py`, `familymember_router.py` all use `async def`, `AsyncSession`, `await session.exec`. Total `async def` count in generated/: 17 (correct — familymember is a link model with 2 endpoints). |
| 7 | `src/caramello/database/session.py` does not exist | VERIFIED | File is gone. Only a `__pycache__/` directory remains inside `src/caramello/database/` — stale .pyc files with no corresponding .py. Python cannot auto-load these without matching source files. |
| 8 | No .py file in the project imports from `caramello.database` | VERIFIED | `grep -rn "from caramello.database" src/ scripts/` returns empty (exit 1). |
| 9 | `config.py` DATABASE_URL uses `postgresql+asyncpg://` prefix | VERIFIED | `src/caramello/core/config.py` line 33: `f"postgresql+asyncpg://{self.DB_USER}..."`. Exactly one occurrence, no plain `postgresql://` remaining. |
| 10 | `shared/database.py` exposes `engine`, `async_session_factory`, `get_session()` async generator | VERIFIED | All three symbols defined. `get_session()` typed as `AsyncGenerator[AsyncSession, None]`. `expire_on_commit=False` and `echo=False` present. |
| 11 | `src/caramello/main.py` does not import from `caramello.database.session` | VERIFIED | main.py imports only from `caramello.api.generated`, `caramello.core.config`. No reference to `database.session` or `create_db_and_tables`. 4 `include_router` calls present. |
| 12 | ruff check src/ passes | VERIFIED | `uv run ruff check src/` — "All checks passed!" |
| 13 | mypy src/ passes | VERIFIED | `uv run mypy src/` — "Success: no issues found in 9 source files" |
| 14 | `alembic upgrade head` completes without error against familia_dev | UNCERTAIN | Requires external PostgreSQL database. Cannot verify without live DB connection. |

**Score:** 13/14 truths verified (1 uncertain — requires human verification)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | asyncpg present, psycopg2 absent, sqlmodel>=0.0.38 | VERIFIED | `asyncpg>=0.31.0` on line 15; `sqlmodel>=0.0.38` on line 8; psycopg2-binary absent |
| `uv.lock` | asyncpg in lockfile, psycopg2 absent, sqlmodel 0.0.38 | VERIFIED | asyncpg 0.31.0 present; psycopg2-binary absent; sqlmodel 0.0.38 present |
| `src/caramello/shared/__init__.py` | Empty marker file | VERIFIED | File exists, 0 bytes |
| `src/caramello/shared/database.py` | engine + async_session_factory + get_session async | VERIFIED | All three symbols present with correct types and patterns |
| `src/caramello/core/config.py` | DATABASE_URL with `postgresql+asyncpg://` | VERIFIED | Line 33 uses correct prefix |
| `alembic/env.py` | async_engine_from_config, NullPool, asyncio.run, dispose | VERIFIED | All required patterns present, ruff passes |
| `scripts/generate_code.py` | generate_router() emits async template | VERIFIED | Lines 256–329: full async template with all required patterns |
| `src/caramello/api/generated/user_router.py` | async def create_user | VERIFIED | All 5 CRUD endpoints async |
| `src/caramello/api/generated/family_router.py` | async def create_family | VERIFIED | All 5 CRUD endpoints async |
| `src/caramello/api/generated/familymember_router.py` | async def | VERIFIED | 2 endpoints (GET list, GET by id) — correct for link model |
| `src/caramello/api/generated/familyinvitation_router.py` | async def | VERIFIED | All 5 CRUD endpoints async |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pyproject.toml` | `uv.lock` | uv sync resolve | VERIFIED | uv.lock contains asyncpg 0.31.0, sqlmodel 0.0.38, no psycopg2 |
| `shared/database.py` | `core/config.py` | `from caramello.core.config import settings` | VERIFIED | Line 6 of shared/database.py |
| `shared/database.py` | `sqlmodel.ext.asyncio.session.AsyncSession` | import on line 4 | VERIFIED | `from sqlmodel.ext.asyncio.session import AsyncSession` |
| `alembic/env.py` | `core/config.py` | `settings.DATABASE_URL` for sqlalchemy.url | VERIFIED | Line 65: `configuration["sqlalchemy.url"] = settings.DATABASE_URL` |
| `alembic/env.py` | `src/caramello/models/` | `from caramello.models import *` | VERIFIED | Line 22: `from caramello.models import *  # noqa: E402, F403` |
| `src/caramello/api/generated/*_router.py` | `shared/database.py` | `Depends(get_session)` | VERIFIED | All 4 routers import `from caramello.shared.database import get_session` |
| `src/caramello/api/generated/*_router.py` | `sqlmodel.ext.asyncio.session.AsyncSession` | type hint in Depends | VERIFIED | All 4 routers: `session: AsyncSession = Depends(get_session)` |
| `src/caramello/main.py` | `src/caramello/api/generated/*_router.py` | app.include_router | VERIFIED | 4 include_router calls present |

### Data-Flow Trace (Level 4)

Not applicable — this phase migrates infrastructure (driver, session layer, code generator). No user-facing data rendering components were created. The routers handle data flow but are generated/infrastructure code.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| asyncpg in uv.lock | `grep "^name = \"asyncpg\"" uv.lock` | Found (line 107) | PASS |
| psycopg2 absent from lockfile | `grep "^name = \"psycopg2-binary\"" uv.lock` | Empty (exit 1) | PASS |
| No sync create_engine in project | `grep -rn "create_engine\b" src/ \| grep -v create_async_engine` | Empty (exit 1) | PASS |
| ruff check src/ | `uv run ruff check src/` | All checks passed | PASS |
| mypy src/ | `uv run mypy src/` | 0 issues in 9 files | PASS |
| ruff check alembic/env.py | `uv run ruff check alembic/env.py` | All checks passed | PASS |
| generate_code.py syntax | `ast.parse(...)` | ok | PASS |
| alembic/env.py syntax | `ast.parse(...)` | ok | PASS |
| async def count in generated routers | `grep -rn "async def" src/caramello/api/generated/ \| wc -l` | 17 | PASS (17 >= 5 min; familymember link model has 2) |
| async_engine_from_config in alembic | `grep -c "async_engine_from_config" alembic/env.py` | 2 (import + use) | PASS |
| AsyncSession count in shared/database.py | `grep -c "AsyncSession" src/caramello/shared/database.py` | 3 | PASS |
| alembic upgrade head against live DB | Requires PostgreSQL | Not run | SKIP — human verification required |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-01 | 02-01, 02-02, 02-03, 02-04 | Todas as queries ao banco executadas de forma assíncrona via asyncpg | SATISFIED | asyncpg driver installed; shared/database.py uses async engine + AsyncSession; all routers use async def + await session.exec; alembic configured for async. Event loop blocking eliminated. |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `tests/generated/test_user.py` etc | Uses `Session` sync + `TestClient` | Info | Generated test files (tests/generated/) use legacy sync patterns. Documented in SUMMARY as intentional — Phase 5 handles test migration. tests/generated/ is excluded from ruff/mypy scope. Not a blocker. |
| `src/caramello/database/` | Directory still exists (only `__pycache__/` inside) | Warning | Plan acceptance criteria stated `test -d src/caramello/database` should exit 1. Directory remains with stale .pyc files. No Python source files (.py) inside. Python will not auto-import stale .pyc without corresponding .py — functionally harmless but cosmetically incomplete. |

### Human Verification Required

#### 1. Alembic upgrade head against live database

**Test:** With a `.env` file configured to point to a running `familia_dev` PostgreSQL instance, run:
```bash
uv run alembic upgrade head
```
**Expected:** Command completes without error, without hang, and without asyncpg connection-leak warnings (no "Future exception was never retrieved" or similar asyncpg teardown messages).
**Why human:** Requires an external PostgreSQL database (familia_dev). Cannot verify programmatically in sandbox. The PLAN explicitly notes this as a manual gate — "Phase gate (manual, executado no Plan 04 ou após): `uv run alembic upgrade head` contra `familia_dev` com `.env` configurado conclui sem hang e sem warning de connection-leak do asyncpg".

### Gaps Summary

No blocking gaps found. All codebase-verifiable must-haves pass.

**Minor cosmetic incompleteness:** The `src/caramello/database/` directory still exists with only a `__pycache__/` subdirectory containing stale `.pyc` files from the deleted `session.py` and `__init__.py`. The PLAN acceptance criteria required `test -d src/caramello/database` to exit 1. This is not a functional gap — Python will not load `.pyc` files without corresponding `.py` sources, and no code in the project imports from `caramello.database`. However, to fully satisfy the acceptance criteria, `rmdir src/caramello/database/__pycache__ && rmdir src/caramello/database` can be run.

**ROADMAP SC#2 note:** The ROADMAP states `AsyncSession de sqlalchemy.ext.asyncio`, but the implementation correctly uses `AsyncSession` from `sqlmodel.ext.asyncio.session`. This is the right choice — the PLAN (02-02-PLAN.md) explicitly mandates the SQLModel version because it provides `session.exec()` for SQLModel queries. The SQLAlchemy-only `AsyncSession` lacks `exec()`. Intent satisfied; ROADMAP wording was imprecise.

**Generated tests (tests/generated/):** These files use sync `Session` and `TestClient`. Documented in SUMMARY as intentional — test migration is Phase 5's responsibility. Not a Phase 2 gap.

---

_Verified: 2026-05-25T03:00:00Z_
_Verifier: Claude (gsd-verifier)_
