# Stack

_Last updated: 2026-05-23_

## Language & Runtime

- **Python 3.10+** (runtime environment is Python 3.12.3; `pyproject.toml` requires `>=3.10`)
- No `.python-version` file pinning the version

## Frameworks & Libraries

**Core API:**
- `fastapi` 0.118.0 — HTTP framework; auto-generates OpenAPI spec; entry point at `src/caramello/main.py`
- `uvicorn` 0.37.0 — ASGI server; started via `uv run uvicorn caramello.main:app --reload`

**ORM & Database:**
- `sqlmodel` 0.0.25 — ORM built on SQLAlchemy + Pydantic; models live in `src/caramello/models/`; session managed at `src/caramello/database/session.py`
- `alembic` 1.16.5 — schema migration tool; config at `alembic.ini`; migrations at `alembic/versions/`; DB URL injected dynamically from `src/caramello/core/config.py`

**Data Validation:**
- `pydantic` 2.11.10 — data validation and serialization; schemas at `src/caramello/schemas/`
- `pydantic-settings` — settings management via env vars; `Settings` class at `src/caramello/core/config.py`
- `email-validator` >=2.2.0 — validates `EmailStr` fields used in Pydantic schemas

**Utilities:**
- `pyyaml` — parses DSL entity definitions from `dsl/entities/*.yaml` during code generation

**Database Driver:**
- `psycopg2-binary` 2.9.11 — PostgreSQL adapter; SQLite is explicitly not supported

## Build & Package Management

- **Package manager:** `uv` (astral.sh) — lockfile at `uv.lock`; install with `uv pip install -e .`
- **Build backend:** `setuptools>=61.0` — configured in `pyproject.toml` `[build-system]`
- **Package source:** `src/caramello` (src-layout, configured as `packages = [{ include = "caramello", from = "src" }]`)
- `uv.lock` is present and committed — ensures reproducible installs

## Development Tools

**Code Generation (DSL pipeline):**
- `datamodel-code-generator` — generates Pydantic models from YAML DSL definitions; listed under `[project.optional-dependencies] dev`
- Custom scripts: `bin/generate_code` (shell wrapper for `scripts/generate_code.py`), `bin/validate_generation` (validates generated output)

**Testing:**
- `pytest` 9.0.1 — test runner; tests at `tests/`
- `httpx` 0.28.1 — async HTTP client used for FastAPI test client in integration tests
- Run with: `uv run pytest`

**Formatters (in lock file, not yet enforced in pyproject):**
- `black` 25.9.0 — present in `uv.lock` as a resolved dependency; not yet configured as a pyproject dev tool entry

**Database management scripts:**
- `bin/setup_db` — creates PostgreSQL user and database from `.env` vars
- `bin/manage_db` — wraps Alembic commands (`init`, `migrate`, `reset`, `upgrade`)

## Infrastructure

**Containerization:**
- Docker Compose deployment described in `docs/deploy.md`
- Published image: `ghcr.io/henricos/caramello-api:latest` (GitHub Container Registry)
- Docker/docker-compose files **do not yet exist** in the repository (noted as gap in `docs/pivot-point.md`)

**Target deployment:**
- Self-hosted server running Docker Engine with `docker compose`
- PostgreSQL database must be external/accessible to the container

**Environment configuration:**
- `.env.example` present; `.env` is gitignored
- Required vars: `ENVIRONMENT`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `DATABASE_URL` is constructed programmatically in `src/caramello/core/config.py` — not read from env
