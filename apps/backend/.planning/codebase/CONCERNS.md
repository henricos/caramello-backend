# Concerns

_Last updated: 2026-05-23_

## Critical Gaps

These issues block any correct advancement toward production. They were catalogued in `docs/pivot-point.md` §4.1 and are confirmed by code inspection.

### G1 — User model incompatible with Logto auth strategy

The decided identity mechanism (`idp_sub` — the JWT `sub` from Logto) does not exist in the codebase. Instead the model contains `hashed_password` and `google_id`, which belong to a discarded auth design.

- Files: `dsl/entities/user.yaml` (lines 39–48), `src/caramello/models/user.py` (lines 17–18, 32, 42–43, 51–52), `src/caramello/schemas/generated/api_schemas.py` (lines 21–25), `alembic/versions/20260104-1044-e667565d64eb-fix_relationships.py` (lines 42–44)
- Impact: Every migration and schema generated from the current DSL is wrong. `UserCreate` accepts a plaintext `password: str` field that is never hashed — it would be stored as-is if a service ever reads it. The `UserRead` schema exposes `google_id` publicly.
- Fix approach: Update `dsl/entities/user.yaml` — remove `hashed_password`, `google_id`, `phone_number`, `is_active`; add `idp_sub: TEXT NOT NULL UNIQUE`. Regenerate models and schemas. Discard the existing Alembic migration and create a fresh one.

### G2 — No authentication layer whatsoever

Zero JWT validation exists. Every endpoint is fully public. `main.py` registers all four routers without any middleware or dependency guard.

- Files: `src/caramello/main.py`, `src/caramello/api/generated/user_router.py`, `src/caramello/api/generated/family_router.py`, `src/caramello/api/generated/familyinvitation_router.py`, `src/caramello/api/generated/familymember_router.py`
- Impact: Any caller can read all users, create users, modify families, accept invitations, or delete records. `shared/auth.py` (the planned JWT validator + just-in-time provisioner) does not exist.
- Fix approach: Phase 2/3 from `docs/pivot-point.md` §6 — add `python-jose` or `PyJWT`, create `src/caramello/shared/auth.py`, apply `Depends(get_current_user)` to all endpoints.

### G3 — Synchronous database driver in an async FastAPI app

`psycopg2-binary` (synchronous) is the only database driver. FastAPI is designed for async I/O; using a sync driver through SQLAlchemy's sync `Session` blocks the event loop on every query.

- Files: `pyproject.toml` (line 15), `src/caramello/database/session.py` (uses `create_engine`, `Session`, synchronous `Generator`)
- Impact: Under concurrent load the server is blocked on every DB call. The codebase claims to be FastAPI-based but gains none of the async performance benefits.
- Fix approach: Replace `psycopg2-binary` with `asyncpg`. Rewrite `session.py` to use `create_async_engine` and `AsyncSession`. Update all router functions to `async def` with `await`.

---

## Technical Debt

### Existing Alembic migration must be discarded

The single migration `alembic/versions/20260104-1044-e667565d64eb-fix_relationships.py` was generated from the wrong `user` model (contains `hashed_password`, `google_id`). It is the only migration and has `down_revision = None`, so it is the root.

- File: `alembic/versions/20260104-1044-e667565d64eb-fix_relationships.py`
- Impact: Running `alembic upgrade head` on a fresh DB produces a schema that diverges from the agreed target (`docs/apps-platform.md` §6). Any data inserted against this schema will need to be migrated again.
- Fix approach: After correcting `dsl/entities/user.yaml` and regenerating models, delete this file and run `alembic revision --autogenerate` to produce a correct initial migration.

### `datetime.utcnow` deprecated across all models

All four models use `default_factory=datetime.utcnow`, which is deprecated since Python 3.12 and will be removed in a future release.

- Files: `src/caramello/models/user.py` (lines 21–22), `src/caramello/models/family.py` (lines 17–18), `src/caramello/models/familymember.py` (line 14), `src/caramello/models/familyinvitation.py` (line 17)
- Fix approach: Replace with `datetime.now(UTC)` (Python 3.11+) or `lambda: datetime.now(timezone.utc)`. Update the DSL generator in `scripts/generate_code.py` so it emits the correct factory.

### Database name in `.env.example` diverges from convention

`.env.example` sets `DB_NAME=caramello_db`. The decided naming is `familia_dev` / `familia_prod` (documented in `docs/apps-platform.md` §5 and `docs/pivot-point.md` §3.3).

- File: `.env.example`
- Impact: New developer setups target the wrong database name, creating environment drift from production conventions.
- Fix approach: Update `.env.example` to `DB_NAME=familia_dev`.

### Flat directory structure contradicts domain architecture decision

Current layout places all models in `src/caramello/models/`, all schemas in `src/caramello/schemas/`, etc. The architectural decision (documented in `docs/apps-platform.md` §3 and `docs/pivot-point.md` §3.4) requires a domain-oriented structure: `src/caramello/domains/familia/`, `src/caramello/shared/`.

- Files: Entire `src/caramello/` tree
- Impact: Adding new domains (agenda, financeiro, lista_compras) into the flat structure will make the codebase hard to navigate and violates the stated design.
- Fix approach: Restructure per `docs/pivot-point.md` §3.4 during Phase 3 of the recommended sequence.

### DSL generator design decision unresolved

The DSL pipeline (`scripts/generate_code.py`) generates flat-layer code (one router per entity in `api/generated/`). The domain architecture requires code grouped under `domains/`. These two models are incompatible without evolving the generator.

- Files: `scripts/generate_code.py`, `dsl/entities/*.yaml`, `src/caramello/api/generated/`
- Impact: Either the generator must be rewritten to output into domain directories, or DSL-generation is abandoned in favour of manual code per domain. This decision is explicitly unresolved in `docs/pivot-point.md` §5, question 1.
- Fix approach: Explicit decision required before starting Phase 3. The simpler path for a small team is manual code per domain; the generator adds overhead without clear benefit at this scale.

### `UserCreate` accepts plaintext password, never hashes it

`UserCreate.password: str` in `src/caramello/models/user.py` (line 42) is accepted by the generated router (`user_router.py` line 11), passed through `model_validate`, and the `User` table model stores `hashed_password` without any transformation. There is no hashing step anywhere.

- Files: `src/caramello/models/user.py`, `src/caramello/api/generated/user_router.py`
- Impact: If the `/user/` POST endpoint is ever called, the password string is stored verbatim (or silently dropped since `UserCreate.password` does not map directly to `User.hashed_password`). This is both a security issue and a logic bug.
- Fix approach: Resolved as a side-effect of migrating to Logto (`idp_sub`), which removes local passwords entirely.

---

## Missing Features

### Authentication middleware (`shared/auth.py`)

The file `src/caramello/shared/auth.py` described in `docs/apps-platform.md` §3 and `docs/pivot-point.md` §3.4 does not exist. It should validate JWT tokens from Logto and perform just-in-time user provisioning.

### Service layer is entirely empty

`src/caramello/services/user.py` is a 1-line empty file. `src/caramello/repositories/user.py` is also empty. No business logic exists anywhere beyond the generated CRUD routers.

- Files: `src/caramello/services/user.py`, `src/caramello/repositories/user.py`

### Manual v1 routes are empty

`src/caramello/api/v1/routes.py` and `src/caramello/api/v1/users.py` are both 1-line empty files. The `v1` layer is scaffolded but contains no code.

- Files: `src/caramello/api/v1/routes.py`, `src/caramello/api/v1/users.py`

### Exceptions module is empty

`src/caramello/exceptions.py` is a 1-line empty file. No custom exception hierarchy exists. Error responses are currently raw `HTTPException` raises scattered through generated routers.

- File: `src/caramello/exceptions.py`

### HTTP errors module is empty

`src/caramello/http_errors.py` is a 1-line empty file. There are no structured error response schemas.

- File: `src/caramello/http_errors.py`

### Docker / docker-compose absent

No `Dockerfile` and no `docker-compose.yml` exist anywhere in the repository. The project cannot be deployed or run in a reproducible containerised environment.

- Impact: Onboarding requires manual PostgreSQL setup; no production deployment path exists.

---

## Security Concerns

### All endpoints are publicly accessible

No authentication or authorisation guards exist on any endpoint. Anyone with network access can read, create, update, or delete users, families, invitations, and family members.

- Files: All files under `src/caramello/api/generated/`
- Risk: Full data exposure. The `/user/` list endpoint returns all users with no pagination guard beyond `limit=100`.

### `UserRead` exposes `google_id`

The read schema includes `google_id` (line 32 of `src/caramello/models/user.py`) in the public response, leaking a third-party identity token in API responses.

- File: `src/caramello/models/user.py`
- Mitigation: Resolved by removing `google_id` from the model entirely when migrating to Logto.

### `FamilyMember` router returns SQLModel table model directly

`familymember_router.py` uses `response_model=FamilyMember` (the table model, not a `FamilyMemberRead` schema). This is explicitly prohibited in `docs/security_rules.md` §3: "Never return the bank entity (SQLModel Table) directly as the API response."

- File: `src/caramello/api/generated/familymember_router.py` (lines 12, 19)
- Risk: Any field added to the model in the future (including sensitive ones) would be automatically exposed.

### Database URL constructed without SSL

`src/caramello/core/config.py` (line 32) constructs `DATABASE_URL` as a plain `postgresql://` URL with no SSL parameters. Production connections to PostgreSQL should use `sslmode=require` at minimum.

- File: `src/caramello/core/config.py`

---

## Operational Concerns

### No Docker setup

No `Dockerfile` or `docker-compose.yml` exists. The project has no standardised way to run or deploy.

### No CI pipeline

No CI configuration file exists (no `.github/workflows/`, no `Makefile` with a `test` target). Tests are not automatically validated on commit.

### No monitoring or observability

No error tracking (Sentry or equivalent), no structured logging, no health-check endpoint beyond `GET /` (which returns a static message). There is no way to know if the service is broken in production.

### No CORS configuration

`main.py` does not add `CORSMiddleware`. A browser-based frontend (or Capacitor mobile app as planned in `docs/apps-platform.md` §4) will be blocked by CORS on every request.

- File: `src/caramello/main.py`

---

## Code Quality Issues

### Test infrastructure is incomplete

- `tests/conftest.py` is empty (1 line). There is no shared fixture for an in-memory or test database. Tests in `tests/generated/` use the real production database (`TestClient(app)` connects through `settings.DATABASE_URL`), making them non-deterministic and environment-dependent.
- `pytest-asyncio` is not installed; async tests cannot run. `httpx` is listed in dev dependencies but is not used in any test.
- Files: `tests/conftest.py`, `pyproject.toml`

### `test_routers_registered` in `tests/test_generated_api.py` will always fail

The test asserts paths `/users/` and `/family_invitations/` (plural). The actual registered prefixes are `/user/` (singular) and `/family_invitation/` (singular). This test has never passed.

- File: `tests/test_generated_api.py` (lines 13–16)

### Generated tests use real database, not isolated fixtures

`tests/generated/test_user.py`, `tests/generated/test_family.py`, and `tests/generated/test_familyinvitation.py` all call `TestClient(app)` which connects to the configured production database. Tests pollute live data and fail if the database is unreachable.

- Files: `tests/generated/test_user.py`, `tests/generated/test_family.py`, `tests/generated/test_familyinvitation.py`

### No test for `FamilyMember`

`tests/generated/` has no `test_familymember.py`. The FamilyMember entity has no test coverage.

### Linting and type-checking tools are specified in `docs/quality_rules.md` but not configured

`docs/quality_rules.md` requires `ruff` and `mypy`, but neither is listed in `pyproject.toml` dependencies (neither `[project.optional-dependencies].dev` nor `[dependency-groups].dev`) and there are no configuration sections for either tool in `pyproject.toml`. The tooling requirement exists only in documentation.

- Files: `pyproject.toml`, `docs/quality_rules.md`

### `schemas/generated/api_schemas.py` is a disconnected artefact

`src/caramello/schemas/generated/api_schemas.py` was generated by `datamodel-codegen` from an OpenAPI spec, not by the DSL generator. It defines its own `User`, `Family`, `FamilyMember`, `FamilyInvitation` Pydantic models that are not used by any router or service. It coexists silently with the SQLModel models in `src/caramello/models/`, creating a confusing parallel schema set.

- File: `src/caramello/schemas/generated/api_schemas.py`

---

## Known TODOs / FIXMEs

No `TODO`, `FIXME`, `HACK`, or `XXX` markers were found in any source file. Concerns are instead documented in `docs/pivot-point.md` and this file.
