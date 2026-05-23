# Integrations

_Last updated: 2026-05-23_

## Databases

**PostgreSQL (primary and only datastore):**
- Driver: `psycopg2-binary` 2.9.11
- ORM: `sqlmodel` (SQLAlchemy under the hood)
- Connection string: constructed at runtime in `src/caramello/core/config.py` from individual env vars (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)
- Engine created at `src/caramello/database/session.py` via `create_engine(settings.DATABASE_URL)`
- SQLite is explicitly unsupported
- Schema migrations managed by Alembic; config at `alembic.ini`, migrations at `alembic/versions/`

## External APIs

None currently integrated. No outbound HTTP calls to external services exist in `src/`.

## Authentication & Authorization

**Not yet implemented.** This is a documented critical gap (`docs/pivot-point.md`).

**Planned solution (per `docs/apps-platform.md`):**
- **Logto** — OIDC/OAuth2 identity provider; to be deployed as shared infrastructure
- JWT validation: each API will validate tokens via a `shared/auth.py` module (not yet created)
- Login via Google OAuth2 (social login through Logto)
- Access control by email allowlist (configured in Logto tenant)
- Tenant for this project: `tenant-familia`
- Standards: OIDC, JWT — chosen for compatibility with MCP/AI agent tooling

## Message Queues / Event Streaming

None. Not planned.

## Other Services

**Container Registry:**
- GitHub Container Registry (`ghcr.io`) — target registry for the production Docker image (`ghcr.io/henricos/caramello-api:latest`)
- CI/CD pipeline not yet configured

**Monitoring & Logging:**
- No external monitoring or error tracking service integrated
- `alembic.ini` configures standard Python logging (`StreamHandler` to stderr) for SQLAlchemy and Alembic
- No structured logging library in use; framework defaults only

**Future: MCP (Model Context Protocol):**
- Documented intent in `docs/apps-platform.md` to expose API endpoints via MCP for AI agent consumption
- FastAPI chosen partly because it auto-generates OpenAPI specs, easing future MCP integration
- No MCP implementation exists yet
