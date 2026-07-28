# Architecture — api

## Overview

`caramello-api` is a hybrid REST + MCP backend in FastAPI, designed for multiple consumers (the web, other applications, AI agents). It owns the data model and all business rules of the platform. It is an OAuth2 resource server: it independently validates the `access_token` presented by any consumer (signature via JWKS/RS256, `iss`, `exp` and its own `aud`), authorizes through a two-layer model (an e-mail allowlist, then family membership) and persists to PostgreSQL via SQLAlchemy 2 with async sessions. The same process serves the REST routes and an MCP server (`/mcp`) mounted over selected operations.

Its distinguishing property is that **the business surface is generated, not written**. Entities and business endpoints are declared in a YAML DSL under `dsl/`; tables, Pydantic schemas, CRUD routers and operation stubs are emitted from it. See [`dsl-rules.md`](dsl-rules.md) for the authoring rules and [`dev-setup.md`](dev-setup.md#the-dsl-flow) for the operational sequence.

Two business domains are implemented: `families` (the closed household group, its members and pre-registrations) and `finances` (accounts, hierarchical categories, movements with statement import, reconciliation, balances and reports). `users` holds the identity provisioned from the token. Functional requirements live in [`prd-core.md`](prd-core.md) and [`prd-agenda.md`](prd-agenda.md); the product framing is in [`project-vision.md`](project-vision.md).

Cross-cutting decisions — the authentication model, the UUID-only public contract, paired versions, automatic migrations at boot, the access pattern — are recorded in the root [`docs/architecture.md`](../../../docs/architecture.md) and are **not** repeated here.

---

## Main components

- `core/config.py` — `Settings` (pydantic-settings) behind a cached `get_settings()`. No `env_file`: reads the process environment only, and fails loudly on a missing required variable.
- `core/exceptions.py` — the `CaramelloApiError` hierarchy for domain errors.
- `core/error_handlers.py` — maps that hierarchy to `application/problem+json` (RFC 9457).
- `i18n/__init__.py`, `i18n/pt_br.py` — message catalog resolving display text for the `reason` codes the auth layer returns.
- `shared/auth.py` — the authorization boundary: `get_current_user` (token validation, allowlist, JIT provisioning, auto-join) and `_require_family_access`.
- `shared/auth_router.py` — `POST /auth/verify`, the route a consumer calls on its OIDC callback and the only write path into `users`.
- `shared/oauth_discovery.py` — `/.well-known/oauth-protected-resource` (RFC 9728) and `/.well-known/oauth-authorization-server` (RFC 8414), for MCP clients.
- `shared/health.py` — `GET /health`, the only unauthenticated route; checks a `SELECT 1` and that `DATA_DIR` is a directory.
- `shared/database.py` — async engine, `async_sessionmaker` and the `get_session` dependency.
- `shared/base.py` — the declarative `Base` all generated tables inherit.
- `shared/models.py` — `allowed_emails`, deliberately outside the DSL generator's reach (see the allowlist decision below).
- `shared/seeds.py` — idempotent reference data, written in the lifespan after the schema exists.
- `shared/pg_bootstrap.py`, `shared/db_dev_server.py` — the embedded PostgreSQL used in development and tests, so no installation is required.
- `users/`, `families/`, `finances/` — one package per domain. Each has `models.py` (generated SQLAlchemy tables), `schemas.py` (generated Pydantic DTOs) and `operations.py` (business endpoints: stub generated, then implemented). `router.py` (generated CRUD) exists only where that CRUD is actually registered — `finances` has none, since its whole surface is business operations. `services.py` appears where a domain has logic worth separating from its handlers.
- `migrations/` — Alembic environment and the zero-padded sequential revisions under `versions/` (`0001`…`0005`). The revision scripts still carry the annotations they were written with, and are deliberately left uncleaned: an applied revision is an immutable historical record, which is also why they are excluded from `ruff`.
- `main.py` — bootstrap: lifespan (JWKS warm-up, seeds), the error handler, router registration and the `fastapi-mcp` mount.

Routing shape: business routers are registered under `/api/v1`; `GET /health`, `POST /auth/verify`, `.well-known/*` and `GET /` are unversioned.

---

## Authorization flow

Authorization has two independent layers, and conflating them is the most common mistake. **The allowlist decides whether an identity may use the system at all; family membership decides which data it may reach.**

1. An e-mail is added to `allowed_emails` — by the startup seed or by `scripts/seed_allowed_email.py` — **before** any login. There is no self-service path in.
2. On its OIDC callback, the consumer calls `POST /auth/verify`. `get_current_user` validates the token (JWKS/RS256, `iss`, `exp`, `aud` containing this api's own audience), then checks `email_verified`, then the allowlist.
3. The check order is invariant: `email_verified` is evaluated **before any database query**, so a token that fails it produces no allowlist lookup and therefore no timing signal about who is on the list. No error body ever contains the caller's e-mail.
4. An e-mail outside the allowlist gets `403` with `reason: not_allowlisted` and nothing is written.
5. On success the user is provisioned just-in-time (`INSERT ... ON CONFLICT DO NOTHING` on `idp_sub`, race-safe) and any pending `FamilyInvitation` matching the e-mail is auto-joined in the same session.
6. Every business read and write additionally resolves the target's `family_id` and calls `_require_family_access`, which returns `403 not_family_member` for a non-member. This is what closes IDOR through a guessed public UUID.

Failures surface as FastAPI's `detail` shape carrying a machine-readable `reason` plus a localized `message`; the `reason` is the contract, the `message` is display text.

---

## Relevant decisions

Decisions local to this module. Cross-cutting ones are in the root [`docs/architecture.md`](../../../docs/architecture.md) and are referenced, never restated.

**`response_model` is mandatory on every endpoint, and a table object is never returned directly.** Both halves matter. Without an explicit `response_model`, FastAPI serializes whatever the handler returns, so any column added later to a table silently joins the public contract. And returning an ORM instance leaks the internal integer `id` and every foreign key alongside it. This is precisely why the `*Public` schema layer exists in `operations.py` and why the generator emits `models.py` and `schemas.py` as separate files: the table keeps the integer column, the schema never sees it. The rule is the module-level enforcement of the root document's "integer ids never leave the api"; `expose_as_uuid` in the DSL is its generated-code counterpart.

**Validation constraints belong in the DSL, not in hand-written code.** Regex, length limits, nullability and uniqueness are declared in `dsl/entities/*.yaml` so that a single edit propagates to the table column, the migration and all three schema variants at once. A constraint added by hand to a generated file is lost at the next generation; a constraint added only to a schema leaves the database accepting the value. Enumerated domains that exist purely at the API boundary (`Account.type` as a `Literal[...]` in the public create schema) are the deliberate exception, since the stored column is a plain string.

**`src/` must always be in sync with `dsl/` — DSL integrity is an invariant, not a preference.** The YAML is the source of truth; a generated file edited by hand is a defect even when it works, because the next `./bin/generate_code` silently reverts it. `./bin/validate_generation` exists to assert the correspondence and should be run before considering a DSL change finished.

**The allowlist is infrastructure, not a business entity.** `allowed_emails` lives in `shared/models.py`, outside the DSL generator's scope, has no `uuid` and no route. Administration is by script (`scripts/seed_allowed_email.py`, `scripts/remove_allowed_email.py`). Giving it an endpoint would put the gate that controls access to the system inside the surface the gate protects.

**Naming conventions worth stating once.** Table names are singular `snake_case` (`user`, `family_member`, `financial_entry`); route paths are `kebab-case` (`/api/v1/finances/financial-entry`), derived by the generator as `table_name.replace("_", "-")`. Every entity carries both an internal integer `id` and a public `uuid` — link tables with a composite primary key are the only exception. These are already normative in [`dsl-rules.md`](dsl-rules.md), which is where the authoritative version lives; they are named here only so a reader of this document knows the shape.

**"Competência" is modelled as two integer columns, not a date.** `competencia_year` and `competencia_month` on `FinancialEntry` are separate `int` fields, which makes the reporting predicate an explicit `WHERE year = ? AND month = ?` and keeps the API obvious for consumers. Every report aggregates by competência, never by `Movement.date`. Why the pt-BR term survives is recorded in the root document.

**A movement's `amount` carries its sign; there is no `type` column.** Positive is a credit, negative a debit. `SUM(amount)` is then a balance with no `CASE WHEN`, and a deduplication hash needs no type component because `-100` and `+100` already differ. `Movement.type` and `Movement.is_duplicate` were both dropped for this reason.

**Suspected duplicates are never inserted; they are returned for confirmation.** On statement import, an OFX `FITID` is a definitive identity — a hash match means a certain duplicate, dropped silently. CSV and XLSX have no bank-side id, so the hash is SHA-256 of `(account_id|date|amount|normalized_description)` and a match is only a *suspicion*: the row is withheld and returned in `potential_duplicates[]` for the user to confirm through the dedicated confirm endpoint. That endpoint inserts confirmed rows with `import_hash = NULL`, which PostgreSQL permits many of in a `UNIQUE` column — which is what makes two genuinely identical payments on the same day representable. This is why `is_duplicate` has no reason to exist: no duplicate row is ever stored.

**Category hierarchy is two tables, not a self-reference.** `Category` and `Subcategory` are separate entities, so "at most two levels" is enforced by the schema — a `Subcategory` simply has no column pointing at another `Subcategory` — instead of by business logic. It also removed the self-referential relationship that required manual post-processing of generated models.

**`FinancialEntry` stores no amount of its own.** It inherits value and sign from its `Movement` through the 1:1 relation and holds only classification metadata (`subcategory_id`, competência, `notes`, `is_recorrente`, `responsible_user_id`). The 1:1 is enforced by `UNIQUE(movement_id)` in the database, and a double reconciliation is caught as an `IntegrityError` mapped to `409` — deliberately not by a pre-insert Python check, which would be a TOCTOU race.

**Family membership is pre-registration by e-mail, not a reusable invite code.** `FamilyInvitation` was redesigned into exactly that: the owner registers an e-mail, the row sits at `status: pending_login`, and the first login matching that e-mail flips it to `joined` through the auto-join inside `get_current_user`. The alternative surface — a reusable invite code, a join request and an approve/reject step — is deliberately not implemented, because the allowlist already gates who may reach the system at all, and a code adds a second, weaker credential for the same decision.

**`"owner"` is the `FamilyMember.role` value that owner-only operations check.** Pre-registering a member and removing one both go through `_require_owner`, which resolves family plus membership in a single query and raises `403` unless `role == "owner"`. The role lives on the membership row, never in the identity provider — the provider does authentication only.

**`updated_at` is set by hand in every update handler.** The column carries no `onupdate`, so a `PATCH` that forgets it silently returns a stale timestamp. This is a standing obligation of every update endpoint in the module, not a property of the model.

**A `PATCH` on a nullable field reads `model_fields_set`, never `exclude_none`.** For `notes` and `responsible_user_uuid`, "the client did not send this field" and "the client explicitly sent null to clear it" are different requests with different outcomes, and `exclude_none` collapses them into one. The presence sentinel is what makes clearing a value expressible at all.

---

## Document provenance

`quality_rules.md`, `security_rules.md` and `style_guide.md` were retired into this document. What is not here was generic convention already covered by the root [`AGENTS.md`](../../../AGENTS.md), [`docs/monorepo.md`](../../../docs/monorepo.md) or `pyproject.toml`'s tooling configuration, and §1.8 of `docs/monorepo.md` forbids duplicating it. `style_guide.md` had also decayed into misinformation: it linked a `language_rules.md` that never existed, mandated `black` when the project formats with `ruff`, and prescribed a `repositories/` + `services/` layer split that was never built. `deploy.md` was removed outright, because "the repository ends at the release" is a recorded decision in the root architecture document. `pivot-point.md`, a 2026 handoff describing a Logto-and-`psycopg2` state with nine open gaps, was deleted once every gap had been closed; git history holds it, and the surviving `.planning/milestones/*.md` are the real audit trail.
