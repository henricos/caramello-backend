<!-- refreshed: 2026-05-23 -->
# Structure

_Last updated: 2026-05-23_

## Directory Layout

```
caramello-api/
├── AGENTS.md                    # Normative AI agent instructions (source of truth)
├── CLAUDE.md                    # Claude Code pointer to AGENTS.md
├── README.md                    # Human-facing overview
├── pyproject.toml               # Python project metadata + dependencies (uv)
├── uv.lock                      # Locked dependency tree
├── alembic.ini                  # Alembic configuration
│
├── bin/                         # Operational shell scripts (run via uv)
│   ├── generate_code            # Runs scripts/generate_code.py
│   ├── validate_generation      # Runs scripts/validate_generation.py
│   ├── manage_db                # Alembic wrapper (init/migrate/upgrade/reset)
│   └── setup_db                 # Initial DB setup helper
│
├── scripts/                     # Python automation scripts
│   ├── generate_code.py         # DSL → code generator (main generator)
│   └── validate_generation.py   # Validates generated output
│
├── dsl/                         # DSL definitions (source of truth for entities)
│   ├── manifest.yaml            # Ordered list of entity files to process
│   ├── schema.yaml              # JSON Schema for validating entity YAML files
│   └── entities/                # One YAML file per entity
│       ├── user.yaml
│       ├── family.yaml
│       ├── family_member.yaml   # is_link_model: true
│       └── family_invitation.yaml
│
├── src/
│   └── caramello/               # Main Python package
│       ├── __init__.py
│       ├── main.py              # FastAPI app definition + router registration
│       ├── exceptions.py        # Custom exceptions (empty placeholder)
│       ├── http_errors.py       # HTTP error helpers (empty placeholder)
│       │
│       ├── core/
│       │   └── config.py        # pydantic-settings Settings class (DB_HOST/PORT/USER/PASSWORD/NAME)
│       │
│       ├── database/
│       │   └── session.py       # SQLModel engine + get_session() dependency
│       │
│       ├── models/              # GENERATED — SQLModel table classes (do not edit)
│       │   ├── __init__.py
│       │   ├── user.py          # User, UserRead, UserCreate, UserUpdate
│       │   ├── family.py        # Family, FamilyRead, FamilyCreate, FamilyUpdate
│       │   ├── familymember.py  # FamilyMember, FamilyMemberRead, FamilyMemberCreate, FamilyMemberUpdate
│       │   └── familyinvitation.py
│       │
│       ├── api/
│       │   ├── generated/       # GENERATED — FastAPI routers (do not edit)
│       │   │   ├── __init__.py
│       │   │   ├── user_router.py
│       │   │   ├── family_router.py
│       │   │   ├── familymember_router.py
│       │   │   └── familyinvitation_router.py
│       │   └── v1/              # Handwritten router skeleton (currently empty)
│       │       ├── __init__.py
│       │       ├── routes.py    # Empty — intended aggregation point for v1
│       │       └── users.py     # Empty — intended handwritten user routes
│       │
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── user.py          # Handwritten user schemas (empty placeholder)
│       │   └── generated/
│       │       └── api_schemas.py  # GENERATED — Pydantic-only models from OpenAPI spec
│       │
│       ├── repositories/        # Data access layer (empty placeholders)
│       │   ├── __init__.py
│       │   └── user.py          # Empty placeholder
│       │
│       └── services/            # Business logic layer (empty placeholders)
│           ├── __init__.py
│           └── user.py          # Empty placeholder
│
├── alembic/                     # Database migrations
│   ├── env.py                   # Alembic env — imports all models, reads settings.DATABASE_URL
│   ├── README
│   ├── script.py.mako           # Migration file template
│   └── versions/
│       └── 20260104-1044-e667565d64eb-fix_relationships.py  # Single consolidation migration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── generated/               # GENERATED — auto-generated integration tests (do not edit)
│   │   ├── __init__.py
│   │   ├── test_user.py
│   │   ├── test_family.py
│   │   └── test_familyinvitation.py
│   ├── test_generated_api.py    # Handwritten tests for generated API surface
│   ├── test_api/
│   │   ├── __init__.py
│   │   └── test_user_router.py  # Handwritten router tests
│   └── test_services/
│       ├── __init__.py
│       └── test_user_service.py # Handwritten service tests
│
├── docs/                        # Normative project documentation
│   ├── apps-platform.md         # Platform architecture decisions (authoritative)
│   ├── pivot-point.md           # Current state vs. target; gap analysis
│   ├── dsl_rules.md             # DSL authoring rules
│   ├── dev.md                   # Developer setup and workflow
│   ├── deploy.md                # Docker deployment guide
│   ├── release.md               # Release procedure
│   ├── prd_core.md              # PRD: auth, families, invitations
│   ├── prd_agenda.md            # PRD: agenda domain
│   ├── project_vision.md        # Product vision
│   ├── quality_rules.md         # Code quality rules
│   ├── security_rules.md        # Security rules
│   └── style_guide.md           # Style guide
│
├── .planning/                   # GSD planning artifacts
│   └── codebase/                # Codebase maps (this directory)
│
└── .agents/
    └── skills/                  # GSD skill definitions
```

## Module Organization

**`src/caramello/` is organized by technical layer**, not by business domain. This is the current state — the target architecture (per `docs/apps-platform.md`) reorganizes this into a `domains/` structure.

| Layer | Path | Purpose |
|---|---|---|
| App shell | `src/caramello/main.py` | FastAPI instance, router registration |
| Config | `src/caramello/core/config.py` | Environment-driven settings |
| Database | `src/caramello/database/session.py` | Engine + session factory |
| Models | `src/caramello/models/` | SQLModel ORM table classes + Pydantic I/O variants |
| Routers | `src/caramello/api/generated/` | HTTP route handlers |
| Schemas | `src/caramello/schemas/` | Standalone Pydantic schemas (mostly unused today) |
| Repositories | `src/caramello/repositories/` | DB query layer (placeholder only) |
| Services | `src/caramello/services/` | Business logic layer (placeholder only) |

## Generated vs. Handwritten Code

### Generated — do NOT edit directly

These files are overwritten every time `bin/generate_code` runs:

| Path | Generator | What it contains |
|---|---|---|
| `src/caramello/models/*.py` | `scripts/generate_code.py` | SQLModel table class + Read/Create/Update per entity |
| `src/caramello/api/generated/*_router.py` | `scripts/generate_code.py` | Full CRUD FastAPI router per entity |
| `tests/generated/test_*.py` | `scripts/generate_code.py` | Basic create/read/list integration tests per entity |
| `src/caramello/schemas/generated/api_schemas.py` | External tool (datamodel-codegen) | Pydantic-only models from OpenAPI spec |

To change generated code, edit the entity YAML in `dsl/entities/` (or the generator itself at `scripts/generate_code.py`) and re-run `bin/generate_code`.

### Handwritten — safe to edit

| Path | Purpose |
|---|---|
| `src/caramello/main.py` | App instantiation; manually import new routers here |
| `src/caramello/core/config.py` | Settings class — extend for new env vars |
| `src/caramello/database/session.py` | Engine + session — update for async migration |
| `src/caramello/api/v1/` | Future handwritten route layer (currently empty) |
| `src/caramello/repositories/user.py` | Data access (currently empty placeholder) |
| `src/caramello/services/user.py` | Business logic (currently empty placeholder) |
| `src/caramello/exceptions.py` | Custom exceptions (currently empty) |
| `src/caramello/http_errors.py` | HTTP error helpers (currently empty) |
| `tests/conftest.py` | Pytest fixtures |
| `tests/test_api/` | Handwritten router tests |
| `tests/test_services/` | Handwritten service tests |
| `dsl/entities/*.yaml` | Entity definitions — the primary author surface |
| `dsl/manifest.yaml` | Entity file registry |
| `alembic/versions/` | Migration files |
| `scripts/generate_code.py` | Generator script itself |
| `docs/*.md` | Documentation |

## Configuration Files

| File | Purpose |
|---|---|
| `pyproject.toml` | Python package metadata, dependencies, uv configuration |
| `uv.lock` | Pinned dependency lockfile (commit this) |
| `alembic.ini` | Alembic configuration pointing to `alembic/env.py` |
| `dsl/schema.yaml` | JSON Schema for validating `dsl/entities/*.yaml` files |
| `.env` (not committed) | Local environment variables: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `ENVIRONMENT` |

## Where to Add New Code

### New domain entity (DSL-driven path)

1. Create `dsl/entities/<entity_name>.yaml` — follow rules in `docs/dsl_rules.md`
2. Add the filename to `dsl/manifest.yaml` under `x-caramello-entities`
3. Run `bin/generate_code`
4. In `src/caramello/main.py`, add import and `app.include_router()` call
5. Run `bin/manage_db migrate "add <entity_name>"` to create a migration

### New handwritten service or business logic

- Service file: `src/caramello/services/<domain>.py`
- Repository file: `src/caramello/repositories/<domain>.py`
- Handwritten route: `src/caramello/api/v1/<domain>.py`, registered in `src/caramello/api/v1/routes.py`

### New migration

```bash
bin/manage_db migrate "description of change"
```

### New tests

- Integration tests for routers: `tests/test_api/test_<entity>_router.py`
- Service unit tests: `tests/test_services/test_<entity>_service.py`
- Fixtures: `tests/conftest.py`

### New configuration variable

Add to `src/caramello/core/config.py` as a typed field on the `Settings` class. It will be read from the environment (or `.env` file) automatically.

---

*Structure analysis: 2026-05-23*
