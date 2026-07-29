# Context and Guidelines — caramello-api

Repository-wide rules (language, commits, configuration and environment variables, monorepo scope) live in the root `AGENTS.md` and must never be duplicated here. Stack, commands and setup belong to `docs/dev-setup.md`; decisions and their rationale to `docs/architecture.md`. What follows are the code standards and invariants of this module.

## DSL first

The DSL under `dsl/` is **always the origin of the code**. Never hand-write generated code.

### Entities (`dsl/entities/*.yaml`)

These files are **generated** — never edit them:

- `src/caramello_api/{domain}/models.py`
- `src/caramello_api/{domain}/schemas.py`
- `src/caramello_api/{domain}/router.py`

Mandatory flow: edit the YAML, run `bin/generate_code`, then validate with `bin/validate_generation`.

Detailed authoring rules: [`docs/dsl-rules.md`](docs/dsl-rules.md).

### Generated CRUD is opt-out per entity

An entity may declare `generate_router: false` to **not** receive the generic CRUD router. When every entity of a domain declines, the generator writes no `router.py` — and deletes the file if a previous generation left one behind. The generator is the source of truth about what exists; never create or delete those files by hand.

Decline the router when the generic CRUD cannot be published as-is:

- **`finances` (every entity)** — the domain's public contract is hand-written in `finances/operations.py`, with `*Public` schemas that resolve UUID to internal id and check family membership. The generated CRUD would publish `AccountRead`, `MovementRead` and friends, which carry the internal integer foreign keys.
- **`FamilyInvitation`** — the invitation's lifecycle belongs to `POST /api/v1/families/families/{family_uuid}/pre-register`, which is where the owner check lives.

Known limitation: the generated CRUD cannot handle `expose_as_uuid`. The generated `Read` gains an `x_uuid` field that is not an attribute of the table, and the generated `Create` would pass `x_uuid` to the model constructor. Therefore **an entity using `expose_as_uuid` requires `generate_router: false`** plus a business operation that assembles the schema field by field (see `pre_register_member`).

### Business routes are versioned

The version prefix (`/api/v1`) is applied **at registration**, in `main.py`; each router declares only its resource prefix (`/users`, `/families`, `/finances`). Never put `/api/v1` inside a router or in a DSL path. `GET /health`, `POST /auth/verify`, the `.well-known/*` documents and `GET /` are deliberately **unversioned**: a monitoring URL and a spec-defined URL must not move when the api's version changes.

### Business operations (`dsl/operations/{domain}.yaml`)

Business endpoints in `{domain}/operations.py` follow DSL-first too — **no exceptions**.

Mandatory flow for any new endpoint:

1. Declare the operation in `dsl/operations/{domain}.yaml`
2. Run `bin/generate_code`, which creates a stub raising `NotImplementedError`
3. Implement the stub

Never add an endpoint straight into `operations.py` without going through the DSL. A file marked `# CARAMELLO-GENERATED: implemented` is not a licence to add routes without the DSL — it only authorizes editing implementations that the DSL already declares.

## Public identifiers

- Every entity exposes `id` (integer, internal primary key) and `uuid` (the public identifier).
- URLs and API responses use **`uuid` always**, never `id`.
- The DSL's `expose_as_uuid` flag controls this for entity references: the table keeps its integer column while the three schemas (`Read`/`Create`/`Update`) expose `x_uuid: UUID` instead. It swaps a field between schemas — it is **not** a database change and therefore generates no migration.
- Every foreign key that appears in a public schema needs the flag. That includes `FamilyInvitation.family_id` and `FamilyInvitation.inviter_id`, because `FamilyInvitationRead` is the response of the pre-register route.
- The integer foreign keys that **remain** in the generated `finances` schemas (`AccountRead.family_id`, `MovementRead.account_id`, `FinancialEntryRead.movement_id` and `subcategory_id`, `CategoryRead.family_id`, `SubcategoryRead.category_id`) do not leak, because no route serves them: the domain declines the generated CRUD and answers only with its `*Public` schemas. Should those schemas ever be published, each foreign key needs the flag first.
- When using the flag, assemble the response field by field in the operation: the `x_uuid` attribute does not exist on the ORM instance, so `model_validate(orm_obj)` would fail.

## Authentication and authorization

- Authentication is OIDC/JWT against **Keycloak**. The `dev` and `prod` clients are already provisioned; do not create new ones without alignment.
- The api is an **OAuth2 resource server**: it validates any consumer's `access_token` on its own (JWKS/RS256, `iss`, `exp`, and `aud` carrying the api's own audience). Never accept a token without validating `aud`.
- Authorization has **two layers**, both behind `get_current_user` in `shared/auth.py`: the e-mail allowlist (`allowed_emails` — may this identity use the system at all?) and family membership (which data may it reach?).
- The **order** of the checks is invariant: `email_verified` is checked **before any database query** (no query cost, and no timing signal about the allowlist), and no error body may ever contain the caller's e-mail address.
- `allowed_emails` is infrastructure, not a business entity: it lives in `shared/models.py`, outside the DSL generator's reach, has no `uuid` and no route. Administration goes through `scripts/seed_allowed_email.py` and `scripts/remove_allowed_email.py`.
- Generated CRUD endpoints are **not** public: the generator injects `Depends(get_current_user)` into all five of them. Authentication is the floor, not something to remember to add — but note that authentication alone does not scope data, so any route touching family-owned rows must also call `require_family_access`.

## Module structure

Each business domain is an isolated package directly under `src/caramello_api/` (`users/`, `families/`, `finances/`). A domain must not import another domain's internals; use schemas as contracts, or shared services.

Layers inside a domain:

- `models.py` — SQLAlchemy tables (generated)
- `schemas.py` — Pydantic DTOs (generated)
- `router.py` — generic CRUD (generated, opt-out per entity)
- `operations.py` — business endpoints (stub generated, implementation by hand)
- `services.py` — pure domain logic, no FastAPI imports, taking an `AsyncSession` and plain parameters so it stays reusable from MCP, tests and scripts. Present only where a domain has logic worth separating from its handlers.

Cross-domain infrastructure lives in `shared/`, configuration and error handling in `core/`, message catalogs in `i18n/`.

## Invariants to preserve

- The database driver is **`asyncpg`** and every session is a SQLAlchemy `AsyncSession`. Never mix in a synchronous driver or a synchronous session.
- Queries go through `session.execute(...)`, with `.scalars()` on single-entity selects only. `session.exec(...)` does not exist here — it was SQLModel's, and mixing the two styles is what used to produce row-wrapping type errors.
- `DATABASE_URL` is read directly from the environment by `core/config.py`; it is never composed from individual host, port and credential variables.
- `Settings` reads only the process environment and sets no `env_file`. Never make the application load a dotenv file on its own.
- Schema changes always go through Alembic. Never alter the database directly, and never edit a revision that has already been applied — those files are historical records and are excluded from ruff for that reason.
- Money is `Decimal` end to end and `NUMERIC(15, 2)` in the database. No `float` ever appears in a monetary path.
- Every user-facing string is resolved from `i18n/pt_br.py`. The api answers a machine-readable `reason` plus a localized `message`; a literal `detail="..."` in a domain module is a policy violation.
- **Business rules keep unit coverage, and mocking the session there is correct.** This module is where the business logic lives, so it is where the breadth of test coverage belongs — see the pyramid in the root `docs/testing.md`. The `finances` domain in particular must keep its unit tests: money correctness, the import and deduplication rules, the parsing thresholds, the reconciliation constraint, the balance and report aggregations. E2E exists to prove the layers connect over a few representative journeys and is not a substitute for any of it; never delete or weaken a unit test on the grounds that "E2E covers it".
- **A test that cannot fail is not coverage.** When adding or changing one, break the implementation on purpose and confirm the test goes red. The patterns that produced fake coverage here, all since removed, were: accepting a failure status alongside the success one (`in (200, 404)`), hiding assertions behind `if response.status_code == 200:`, asserting only that a key exists rather than what it holds, and alternating over several mutually exclusive contracts so that any of them passed.
- Repository scope is the **Família group** only — no tables shared with other application groups.
