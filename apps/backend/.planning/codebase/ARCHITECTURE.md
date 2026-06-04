<!-- refreshed: 2026-05-23 -->
# Architecture

_Last updated: 2026-05-23_

## Overview

Caramello API is the Python/FastAPI backend for the "Grupo Família" platform — a monolithic REST API serving family-management domains (família, agenda, financeiro, lista de compras). Code for models, routers, and tests is **generated from YAML entity definitions** in `dsl/entities/` via `scripts/generate_code.py`, not written by hand. The database is PostgreSQL, accessed synchronously via SQLModel + SQLAlchemy.

## Design Pattern

**DSL-driven layered monolith.** The source of truth for domain entities is `dsl/entities/*.yaml`. A Python code-generator reads the manifest at `dsl/manifest.yaml` and emits SQLModel table classes, FastAPI routers, and pytest tests into designated `generated/` directories. Non-generated (handwritten) code provides the application shell (`main.py`), configuration (`core/config.py`), database session (`database/session.py`), and placeholder layers for repositories and services.

```text
┌─────────────────────────────────────────────────────────┐
│                   DSL Layer (source of truth)            │
│   dsl/entities/*.yaml  +  dsl/manifest.yaml             │
└────────────────────┬────────────────────────────────────┘
                     │ scripts/generate_code.py
                     ▼
┌─────────────────────────────────────────────────────────┐
│                Generated Code (do not edit)              │
│  src/caramello/models/          (SQLModel table classes) │
│  src/caramello/api/generated/   (FastAPI routers)        │
│  tests/generated/               (pytest integration)     │
└────────────────────┬────────────────────────────────────┘
                     │ registered in
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Application Shell (handwritten)             │
│  src/caramello/main.py          (FastAPI app + mounts)   │
│  src/caramello/core/config.py   (pydantic-settings)      │
│  src/caramello/database/session.py  (engine + session)   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                PostgreSQL Database                       │
│  familia_dev / familia_prod                              │
└─────────────────────────────────────────────────────────┘
```

## Core Data Flow

### HTTP Request Path

1. HTTP request arrives at FastAPI app — `src/caramello/main.py`
2. Request is routed to the matching generated router in `src/caramello/api/generated/`
3. Router handler validates the Pydantic input schema (e.g., `UserCreate` from `src/caramello/models/user.py`)
4. Handler calls SQLModel directly — `session.exec(select(Model)...)` — bypassing the (empty) service and repository layers
5. SQLModel/SQLAlchemy executes SQL against PostgreSQL
6. Handler returns a `*Read` model instance, serialized as JSON by FastAPI

**Note:** There is no service or repository layer in practice today. `src/caramello/services/user.py` and `src/caramello/repositories/user.py` are empty placeholder files.

### Code Generation Flow

1. Author edits or creates a YAML entity file under `dsl/entities/`
2. Updates `dsl/manifest.yaml` to register the file
3. Runs `bin/generate_code` → executes `scripts/generate_code.py`
4. Generator produces/overwrites:
   - `src/caramello/models/<entity>.py` — SQLModel table class + Read/Create/Update variants
   - `src/caramello/api/generated/<entity>_router.py` — CRUD router
   - `tests/generated/test_<entity>.py` — basic integration tests
5. New router must be manually imported and registered in `src/caramello/main.py`

## Key Abstractions

**Entity (DSL):**
- Defined in `dsl/entities/*.yaml`
- Fields use Python-style types (`str`, `int`, `UUID`, `EmailStr`, `datetime`, `list[T]`)
- Standard required fields: `id` (int, PK), `uuid` (UUID, public identifier), `created_at`, `updated_at`
- Link models (M:M join tables) use `is_link_model: true` and omit `id`/`uuid`

**SQLModel class (generated):**
- One file per entity in `src/caramello/models/`
- Each file exports four classes: `<Entity>` (table), `<Entity>Read`, `<Entity>Create`, `<Entity>Update`
- Relationships use SQLModel `Relationship()` with `back_populates` and optional `link_model`

**Generated Router (generated):**
- Located in `src/caramello/api/generated/<entity>_router.py`
- Prefix: `/<table_name>` (singular snake_case, e.g. `/user`, `/family`)
- Tag: PascalCase entity name
- Exposes: `POST /`, `GET /`, `GET /{uuid}`, `PATCH /{uuid}`, `DELETE /{uuid}`
- Lookups always use the public `uuid` field, never the internal integer `id`

**Settings (`src/caramello/core/config.py`):**
- `pydantic-settings` `BaseSettings` subclass
- Reads `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` from environment
- Constructs `DATABASE_URL` at startup via `model_post_init`
- `.env` file supported for local development

**Database session (`src/caramello/database/session.py`):**
- Module-level `engine` singleton using synchronous `psycopg2-binary`
- `get_session()` generator injected into routers via FastAPI `Depends`

## Code Generation

The generator at `scripts/generate_code.py` is a standalone Python script. It:

1. Reads `dsl/manifest.yaml` to get the entity list
2. For each entity YAML, calls `generate_models()`, `generate_router()`, `generate_test()`
3. Writes files directly to the output directories, **overwriting** any previous version
4. Skips router and test generation for `is_link_model: true` entities (e.g., `FamilyMember`)

Key generator functions:
- `map_type_to_python(dsl_type)` — maps DSL types to Python/SQLModel types, wraps entity names as forward references
- `get_field_definition(field)` — renders a `Field(...)` annotation line
- `generate_relationships(relationships, entity_name)` — renders `Relationship(...)` lines
- `generate_models(entity_data)` — produces the full `*`, `*Read`, `*Create`, `*Update` class block
- `generate_router(entity_data)` — produces a complete CRUD router module as a string
- `generate_test(entity_data)` — produces basic create/read/list test functions

Invoked via: `bin/generate_code` → `uv run python scripts/generate_code.py`

## API Design

**Protocol:** REST over HTTP, JSON body  
**Framework:** FastAPI with automatic OpenAPI/Swagger at `/docs`  
**Versioning:** No versioning prefix in production routes today; `src/caramello/api/v1/` is an empty skeleton for future use  
**Resource identifiers:** Public `uuid` (UUID v4) used in all URLs — internal integer `id` is never exposed in URLs  
**Pagination:** Offset/limit on list endpoints, default limit 100, max 100  
**Error responses:** FastAPI default `HTTPException` with `detail` string  

Current registered prefixes (all flat, no `/v1` prefix):
- `/user` — `src/caramello/api/generated/user_router.py`
- `/family` — `src/caramello/api/generated/family_router.py`
- `/family_member` — `src/caramello/api/generated/familymember_router.py`
- `/family_invitation` — `src/caramello/api/generated/familyinvitation_router.py`

## Domain Model

Four entities currently in DSL:

| Entity | Table | Type | Key Relations |
|---|---|---|---|
| `User` | `user` | Full entity | Many families via `FamilyMember`; many sent invitations |
| `Family` | `family` | Full entity | Many members via `FamilyMember`; many invitations |
| `FamilyMember` | `family_member` | Link model (M:M) | `user.id` + `family.id` composite PK; `role` field |
| `FamilyInvitation` | `family_invitation` | Full entity | FK to `family.id` and `user.id` (inviter) |

## Target Architecture (Planned — not yet implemented)

Per `docs/apps-platform.md` and `docs/pivot-point.md`, the intended structure reorganizes flat layers into domain packages:

```
src/caramello/
├── main.py
├── shared/
│   └── auth.py          # JWT validation (Logto) + just-in-time user provisioning
└── domains/
    ├── familia/
    │   ├── models.py
    │   ├── schemas.py
    │   ├── services.py
    │   └── routes.py
    ├── agenda/           # Future
    ├── financeiro/       # Future
    └── lista_compras/    # Future
```

Authentication provider: **Logto** (`tenant-familia`), JWT/OIDC. User model to be simplified to `id` (UUID PK), `idp_sub` (Logto sub), `email`, `name`, `created_at`, `updated_at`. The current `hashed_password` and `google_id` fields in `user.yaml` are **incompatible** with this target and must be corrected.

## Architectural Constraints

- **Sync driver:** `psycopg2-binary` is synchronous. The target architecture requires `asyncpg` and SQLAlchemy async session. All current router code is sync and must be rewritten when async is adopted.
- **No auth layer:** Zero authentication or authorization exists. All endpoints are publicly accessible.
- **Global `engine` singleton:** `src/caramello/database/session.py` creates a module-level `engine` at import time, requiring a valid `DATABASE_URL` environment variable at startup.
- **Generated code is overwritten:** Never edit files under `src/caramello/models/`, `src/caramello/api/generated/`, `tests/generated/` — they are fully replaced on each generation run.
- **Manual router registration:** After generating a new entity, the router import and `app.include_router()` call in `src/caramello/main.py` must be added by hand.

## Error Handling

**Strategy:** FastAPI `HTTPException` raised directly in router handlers. No custom exception hierarchy is active (the file `src/caramello/exceptions.py` exists but is empty).

**Patterns:**
- 404: resource not found after `session.exec(...).first()` returns `None`
- Validation errors: handled automatically by Pydantic/FastAPI (422 Unprocessable Entity)
- No global exception handlers registered

## Anti-Patterns

### Direct DB access in routers

**What happens:** Generated routers call `session.exec(select(Model)...)` directly — no service or repository layer.
**Why it's wrong:** Business logic cannot be reused via MCP or other callers; testability requires a real database.
**Do this instead:** Route handlers should call service functions in `services/<domain>.py`; services call repository functions; repositories own the SQLModel queries. See target structure in `docs/apps-platform.md`.

### Sync driver with async framework

**What happens:** FastAPI is used with `psycopg2-binary` (synchronous driver) and a sync SQLModel session.
**Why it's wrong:** Blocks the event loop under concurrent load; contradicts FastAPI's async design.
**Do this instead:** Replace with `asyncpg`, use `AsyncSession` from SQLAlchemy async extension, and `async def` route handlers.

---

*Architecture analysis: 2026-05-23*
