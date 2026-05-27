@AGENTS.md

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Caramello API**

Backend Python/FastAPI do sistema Caramello — plataforma pessoal e familiar para centralizar agenda, finanças, listas de compras, saúde e entretenimento. Serve um grupo fechado de 1 a 5 usuários (membros da família), com autenticação via Keycloak e dados organizados por domínios de negócio. Destinado a ser consumido por um frontend React/Capacitor (mobile-first) e por agentes de IA via MCP.

**Core Value:** Um backend sólido, seguro e extensível onde cada novo domínio de negócio (financeiro, agenda, compras…) pode ser adicionado sem tocar no que já existe.

### Constraints

- **Stack**: Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL obrigatório — não há suporte a SQLite
- **Auth**: Keycloak com OIDC/JWT — clients de dev e prod já configurados na infra existente
- **DB naming**: `caramello` (prod), `caramello_dev` (dev) — convenção definida em `docs/apps-platform.md` §5
- **Código gerado**: arquivos em `src/caramello/domains/*/` gerados pelo DSL **não devem ser editados diretamente** — editar o YAML e regenerar
- **Escopo do repo**: apenas Grupo Família — sem tabelas compartilhadas com outros grupos
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Language & Runtime
- **Python 3.10+** (runtime environment is Python 3.12.3; `pyproject.toml` requires `>=3.10`)
- No `.python-version` file pinning the version
## Frameworks & Libraries
- `fastapi` 0.118.0 — HTTP framework; auto-generates OpenAPI spec; entry point at `src/caramello/main.py`
- `uvicorn` 0.37.0 — ASGI server; started via `uv run uvicorn caramello.main:app --reload`
- `sqlmodel` 0.0.25 — ORM built on SQLAlchemy + Pydantic; models live in `src/caramello/models/`; session managed at `src/caramello/database/session.py`
- `alembic` 1.16.5 — schema migration tool; config at `alembic.ini`; migrations at `alembic/versions/`; DB URL injected dynamically from `src/caramello/core/config.py`
- `pydantic` 2.11.10 — data validation and serialization; schemas at `src/caramello/schemas/`
- `pydantic-settings` — settings management via env vars; `Settings` class at `src/caramello/core/config.py`
- `email-validator` >=2.2.0 — validates `EmailStr` fields used in Pydantic schemas
- `pyyaml` — parses DSL entity definitions from `dsl/entities/*.yaml` during code generation
- `psycopg2-binary` 2.9.11 — PostgreSQL adapter; SQLite is explicitly not supported
## Build & Package Management
- **Package manager:** `uv` (astral.sh) — lockfile at `uv.lock`; install with `uv pip install -e .`
- **Build backend:** `setuptools>=61.0` — configured in `pyproject.toml` `[build-system]`
- **Package source:** `src/caramello` (src-layout, configured as `packages = [{ include = "caramello", from = "src" }]`)
- `uv.lock` is present and committed — ensures reproducible installs
## Development Tools
- `datamodel-code-generator` — generates Pydantic models from YAML DSL definitions; listed under `[project.optional-dependencies] dev`
- Custom scripts: `bin/generate_code` (shell wrapper for `scripts/generate_code.py`), `bin/validate_generation` (validates generated output)
- `pytest` 9.0.1 — test runner; tests at `tests/`
- `httpx` 0.28.1 — async HTTP client used for FastAPI test client in integration tests
- Run with: `uv run pytest`
- `black` 25.9.0 — present in `uv.lock` as a resolved dependency; not yet configured as a pyproject dev tool entry
- `bin/setup_db` — creates PostgreSQL user and database from `.env` vars
- `bin/manage_db` — wraps Alembic commands (`init`, `migrate`, `reset`, `upgrade`)
## Infrastructure
- Docker Compose deployment described in `docs/deploy.md`
- Published image: `ghcr.io/henricos/caramello-api:latest` (GitHub Container Registry)
- Docker/docker-compose files **do not yet exist** in the repository (noted as gap in `docs/pivot-point.md`)
- Self-hosted server running Docker Engine with `docker compose`
- PostgreSQL database must be external/accessible to the container
- `.env.example` present; `.env` is gitignored
- Required vars: `ENVIRONMENT`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `DATABASE_URL` is constructed programmatically in `src/caramello/core/config.py` — not read from env
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming
- `User` — ORM/table model (SQLModel with `table=True`)
- `UserRead` — response schema
- `UserCreate` — creation payload schema
- `UserUpdate` — partial update payload schema (all fields `Optional`)
- All entities expose `id` (int, internal PK) and `uuid` (UUID, public identifier)
- External URLs and API responses use `uuid`, never `id`
## Code Style
## Module Patterns
## Error Handling
## Documentation
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Overview
## Design Pattern
```text
```
## Core Data Flow
### HTTP Request Path
### Code Generation Flow
## Key Abstractions
- Defined in `dsl/entities/*.yaml`
- Fields use Python-style types (`str`, `int`, `UUID`, `EmailStr`, `datetime`, `list[T]`)
- Standard required fields: `id` (int, PK), `uuid` (UUID, public identifier), `created_at`, `updated_at`
- Link models (M:M join tables) use `is_link_model: true` and omit `id`/`uuid`
- One file per entity in `src/caramello/models/`
- Each file exports four classes: `<Entity>` (table), `<Entity>Read`, `<Entity>Create`, `<Entity>Update`
- Relationships use SQLModel `Relationship()` with `back_populates` and optional `link_model`
- Located in `src/caramello/api/generated/<entity>_router.py`
- Prefix: `/<table_name>` (singular snake_case, e.g. `/user`, `/family`)
- Tag: PascalCase entity name
- Exposes: `POST /`, `GET /`, `GET /{uuid}`, `PATCH /{uuid}`, `DELETE /{uuid}`
- Lookups always use the public `uuid` field, never the internal integer `id`
- `pydantic-settings` `BaseSettings` subclass
- Reads `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` from environment
- Constructs `DATABASE_URL` at startup via `model_post_init`
- `.env` file supported for local development
- Module-level `engine` singleton using synchronous `psycopg2-binary`
- `get_session()` generator injected into routers via FastAPI `Depends`
## Code Generation
- `map_type_to_python(dsl_type)` — maps DSL types to Python/SQLModel types, wraps entity names as forward references
- `get_field_definition(field)` — renders a `Field(...)` annotation line
- `generate_relationships(relationships, entity_name)` — renders `Relationship(...)` lines
- `generate_models(entity_data)` — produces the full `*`, `*Read`, `*Create`, `*Update` class block
- `generate_router(entity_data)` — produces a complete CRUD router module as a string
- `generate_test(entity_data)` — produces basic create/read/list test functions
## API Design
- `/user` — `src/caramello/api/generated/user_router.py`
- `/family` — `src/caramello/api/generated/family_router.py`
- `/family_member` — `src/caramello/api/generated/familymember_router.py`
- `/family_invitation` — `src/caramello/api/generated/familyinvitation_router.py`
## Domain Model
| Entity | Table | Type | Key Relations |
|---|---|---|---|
| `User` | `user` | Full entity | Many families via `FamilyMember`; many sent invitations |
| `Family` | `family` | Full entity | Many members via `FamilyMember`; many invitations |
| `FamilyMember` | `family_member` | Link model (M:M) | `user.id` + `family.id` composite PK; `role` field |
| `FamilyInvitation` | `family_invitation` | Full entity | FK to `family.id` and `user.id` (inviter) |
## Target Architecture (Planned — not yet implemented)
```
```
## Architectural Constraints
- **Sync driver:** `psycopg2-binary` is synchronous. The target architecture requires `asyncpg` and SQLAlchemy async session. All current router code is sync and must be rewritten when async is adopted.
- **No auth layer:** Zero authentication or authorization exists. All endpoints are publicly accessible.
- **Global `engine` singleton:** `src/caramello/database/session.py` creates a module-level `engine` at import time, requiring a valid `DATABASE_URL` environment variable at startup.
- **Generated code is overwritten:** Never edit files under `src/caramello/models/`, `src/caramello/api/generated/`, `tests/generated/` — they are fully replaced on each generation run.
- **Manual router registration:** After generating a new entity, the router import and `app.include_router()` call in `src/caramello/main.py` must be added by hand.
## Error Handling
- 404: resource not found after `session.exec(...).first()` returns `None`
- Validation errors: handled automatically by Pydantic/FastAPI (422 Unprocessable Entity)
- No global exception handlers registered
## Anti-Patterns
### Direct DB access in routers
### Sync driver with async framework
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
