# Local Setup Guide — api

How to bring up `caramello-api` in a development environment from scratch. Nothing here requires an installed PostgreSQL: the database is embedded (`pgembed`) and boots on demand. An OIDC provider is the one external dependency that still has to come from somewhere — see [OIDC provider in development](#oidc-provider-in-development).

For closing a release, see [`release.md`](release.md). For the module's structure and decisions, see [`architecture.md`](architecture.md).

---

## Prerequisites

- **Python 3.12+** (`requires-python = ">=3.12"` in `pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/)** — the only package manager this module uses:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

No PostgreSQL, no Docker and no Keycloak installation is needed for the local loop.

---

## Installation

```bash
cd apps/api
uv sync
```

`uv sync` installs the runtime dependencies plus the `dev` dependency group (`pytest`, `ruff`, `mypy`, `pgembed`, `pyyaml`). `pyyaml` is a tooling dependency only — the DSL generator reads YAML, the application never does, which is why the container image builds `--no-dev`.

---

## Database (embedded dev server)

In development there is no installed PostgreSQL and no container: `pgembed` downloads a real PostgreSQL binary and runs it locally. Start it in a dedicated terminal, before anything else:

```bash
cd apps/api
uv run python -m caramello_api.shared.db_dev_server
```

The command creates (or reuses) the persistent data directory `apps/api/.pgembed-data/`, creates the `caramello_dev` database on first run, prints the DSN as a `DATABASE_URL=...` line and then blocks until `Ctrl+C`. The data survives restarts; `Ctrl+C` stops the PostgreSQL process without deleting the directory.

Copy the DSN it printed into the `DATABASE_URL` line of `apps/api/.env.development`.

> **The `DATABASE_URL` line in `.env.development` is expected to differ per machine.** The DSN embeds the absolute path of `.pgembed-data/` on the developer's filesystem, so the committed value can only ever be one machine's. A permanent, uncommitted local diff on exactly that line is normal and correct — do not "fix" it, and do not commit your own path over someone else's. The file is committed because the *shape* of the value is useful, not because the value is portable.

---

## OIDC provider in development

The api is a pure OAuth2 resource server: it validates access tokens against a provider's JWKS and never issues tokens itself. It therefore needs a reachable issuer even locally, configured through `AUTH_OIDC_ISSUER` and `AUTH_OIDC_AUDIENCE`.

There are two options:

1. **The local mock provider (the default).** Start it in a dedicated terminal, from the repository root:
   ```bash
   node scripts/dev-oidc-server.js
   ```
   It listens on `http://localhost:8790` — exactly what `.env.development` already points at, so no export is needed — approves every login instantly with no screen, and signs real RS256 tokens carrying `caramello-api` in `aud`, which the api validates through the same JWKS/signature path production uses. The script reuses `e2e/lib/mock-oidc-server.js` from the root E2E harness and installs that dependency into `e2e/node_modules` on first run. `MOCK_OIDC_PORT`, `MOCK_OIDC_EMAIL`, `MOCK_OIDC_NAME`, `MOCK_OIDC_SUB` and `MOCK_OIDC_AUDIENCE` override the defaults; the default e-mail (`henricos@gmail.com`) is the one the startup seed already places on the allowlist. `Ctrl+C` stops it.

2. **A real Keycloak realm.** Export the issuer in your own shell (never in the committed file) and let `.env.development`'s `${AUTH_OIDC_ISSUER:-...}` indirection pick it up:
   ```bash
   export AUTH_OIDC_ISSUER=https://keycloak.exemplo.com/realms/caramello
   ```
   The realm needs an audience mapper adding `caramello-api` to the `aud` claim of the access tokens it issues, otherwise every request fails `aud` validation.

Everything provider-specific is discovered from the issuer URL (`/.well-known/openid-configuration`, then JWKS); swapping providers is a change to those two variables and nothing else. Note that the api boots fine without a reachable provider — the JWKS warm-up in the lifespan is deliberately best-effort — so a provider outage surfaces as a `401` on authenticated requests, never as a server that refuses to start. `GET /health` keeps answering.

---

## Configuration

Read "Configuration and environment variables" in the root [`AGENTS.md`](../../../AGENTS.md) for the policy. What it means concretely here:

**`Settings` reads only the process environment, and fails loudly.** `core/config.py` deliberately sets **no `env_file`**. Nothing in the module ever opens a dotenv file. A missing required variable is a pydantic validation error at import time, not a silent default — so the service cannot come up pointed at the wrong database.

**Whatever launches the process is responsible for populating the environment.** In development that is your shell, sourcing the committed `apps/api/.env.development`:

```bash
cd apps/api
set -a && source .env.development && set +a
```

`set -a` marks every subsequent assignment for export, so the variables reach the child process; `set +a` turns that back off. Skipping `set -a` sets shell variables that the api will never see.

**Because a *shell* resolves the file, `${VAR:-fallback}` indirection works.** That is why lines like `AUTH_OIDC_ISSUER=${AUTH_OIDC_ISSUER:-http://localhost:8790}` are valid here: the shell expands them at `source` time, taking the value you already exported if there is one and the fallback otherwise. This is a property of the api's loading mechanism, not of dotenv files in general — `apps/web`'s file is loaded by Next.js, whose loader is not a shell, and only plain `${VAR}` works there.

**There is no `.env.example` and no `.env`**, by design. The rejected alternative (ship an example, copy it, edit the copy) produces a file nobody validates, which drifts from the code silently. The rationale is recorded in the root [`docs/architecture.md`](../../../docs/architecture.md).

### Variables

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Async SQLAlchemy DSN (`postgresql+asyncpg://...`). No default on purpose: a DSN genuinely differs per environment. Value printed by the dev server above. |
| `AUTH_OIDC_ISSUER` | yes | — | Full realm URL of the OIDC provider (the issuer). Trailing slashes are stripped automatically, because a trailing slash keeps discovery working while every token fails `iss` validation. |
| `AUTH_OIDC_AUDIENCE` | yes | — | Audience this service requires in the `aud` claim — `caramello-api`. |
| `APP_ENV` | no | `development` | One of `development`, `test`, `production`. A closed set: a typo like `prod` fails at startup instead of silently re-exposing `/docs`. |
| `PUBLIC_URL` | no | `http://localhost:8000` | Public base URL, used only to build the absolute URLs in the OAuth discovery documents MCP clients read. **Required** when `APP_ENV=production`. |
| `APP_BASE_PATH` | no | `""` | Prefix a reverse proxy strips before forwarding (FastAPI's `root_path`). Not needed in dev — with no proxy in front, no base path is correct. |
| `DATA_DIR` | no | `/data` | Shared data folder. In a container this is always `/data`; locally that path is not writable without root, so `.env.development` points at the repository's own `data/`. |
| `CARAMELLO_API_HOST` | no | `0.0.0.0` | Bind address. Prefixed, because it is specific to this service. |
| `CARAMELLO_API_PORT` | no | `8000` | Listen port. Useful to override when running two instances side by side. |
| `CARAMELLO_API_LOG_LEVEL` | no | `info` | Log level passed to `logging.basicConfig`. |

Variables shared with `apps/web` or with the deploy as a whole are read **without** the `CARAMELLO_API_` prefix, so an operator running both modules sees one name per concept. Only knobs private to this service carry the prefix.

**Which values expect something from your own shell:** only `AUTH_OIDC_ISSUER` — and only if you are aiming at a real Keycloak instead of a local mock. Every other line in `.env.development` is either a throwaway local value or already correct as committed. No secret of any kind belongs in that file; if one ever becomes necessary, it goes in as `${SOME_KEY}` indirection to a variable exported from your shell profile or secret manager.

The semantics of the same variables in **production** are documented once, in the "How to run the image" section of [`release.md`](release.md).

---

## Migrations

With the dev server running (previous section) and the environment sourced:

```bash
cd apps/api
set -a && source .env.development && set +a
./bin/manage_db upgrade
```

`bin/manage_db` loads no dotenv file either — exactly like the application — and refuses to run with an empty `DATABASE_URL`.

| Command | Effect |
|---|---|
| `./bin/manage_db upgrade` | Apply pending migrations (`alembic upgrade head`). `init` is an alias. |
| `./bin/manage_db migrate "message"` | Generate a new migration with `--autogenerate` from the current models. |
| `./bin/manage_db reset` | **Destructive**: `downgrade base` then `upgrade head`. Prompts for confirmation. |

Revision ids are zero-padded sequential (`0001`…`0005`). Applied migration files are treated as immutable historical records — `ruff` deliberately excludes `src/caramello_api/migrations/versions` for that reason. In production, `alembic upgrade head` runs automatically in the container entrypoint before the process starts.

---

## Running in development mode

```bash
cd apps/api
set -a && source .env.development && set +a
uv run python -m caramello_api --reload
```

This invokes `src/caramello_api/__main__.py`, which reads host, port and log level from `Settings` and calls `uvicorn.run(...)` — the same mechanism the container image's `CMD` uses, so a variable set here behaves identically in dev and in production.

The api comes up at `http://localhost:8000`, with Swagger UI at `/docs` and the raw schema at `/openapi.json`. Both are development affordances: `APP_ENV=production` disables them. ReDoc is off everywhere.

To run a second instance in parallel, override the port before launching:

```bash
CARAMELLO_API_PORT=8001 uv run python -m caramello_api --reload
```

---

## Verifying the flow

The probe needs no token:

```bash
curl http://localhost:8000/health
# expected: {"status":"ok","checks":{"database":true,"data_dir":true}}
```

`503` with `"status":"unavailable"` means one of the two checks failed — read which key is `false` rather than guessing.

A business route requires one, and says so in a machine-readable way:

```bash
curl -i http://localhost:8000/api/v1/users/me
# expected: HTTP/1.1 401 Unauthorized
# WWW-Authenticate: Bearer resource_metadata="http://localhost:8000/.well-known/oauth-protected-resource"
# {"detail":{"reason":"missing_token","message":"..."}}
```

`reason` is the stable contract consumers branch on; `message` is display text resolved from the pt-BR catalog in `i18n/`. The status is `401`, not `403`: a missing credential is "unauthenticated", and `shared/auth.py` wraps FastAPI's `HTTPBearer` specifically to return `401` with a `WWW-Authenticate` header rather than the `403` the bare dependency would produce (RFC 7235 §3.1). `403` is reserved for a caller who *is* authenticated but is not allowed — `email_not_verified`, `not_allowlisted`, `not_family_member`. The E2E suite asserts this distinction.

**Only the business surface is versioned.** `/api/v1/users/*`, `/api/v1/families/*` and `/api/v1/finances/*` carry the prefix; `GET /health`, `POST /auth/verify`, the `.well-known/*` discovery documents and `GET /` stay unversioned on purpose — a monitor's URL and a spec-defined URL must survive an api version bump untouched.

The full logged-in flow is verified through `apps/web` ([`../../web/docs/dev-setup.md`](../../web/docs/dev-setup.md)) or through the root E2E scripts — `node e2e/api-endpoints.js` covers this module's whole REST and MCP contract without a browser (see the root [`docs/testing.md`](../../../docs/testing.md)).

---

## The DSL flow

**The YAML in `dsl/` is the source of truth for every entity and every business endpoint.** Models, schemas, CRUD routers and operation stubs are generated from it. Editing a generated file directly is always wrong: the next generation overwrites it. Full rules in [`dsl-rules.md`](dsl-rules.md).

The sequence is mandatory and ordered:

```bash
cd apps/api
set -a && source .env.development && set +a

# 1. Edit the definitions — dsl/entities/*.yaml (entities) or
#    dsl/operations/{domain}.yaml (business endpoints).

# 2. Generate models, schemas, routers and operation stubs.
./bin/generate_code

# 3. Implement any new stub, replacing its `raise NotImplementedError`,
#    then flip its header from `# CARAMELLO-GENERATED: stub` to
#    `# CARAMELLO-GENERATED: implemented`.

# 4. Create the migration from the regenerated models.
./bin/manage_db migrate "describe the schema change"

# 5. Apply it.
./bin/manage_db upgrade

# 6. Check that src/ still matches dsl/.
./bin/validate_generation
```

Two things about step 3 are easy to get wrong. An `operations.py` already marked `implemented` is **not** a licence to add a route without a DSL entry — the marker only stops the generator from overwriting implementations it already emitted. And a generated `models.py` is never patched by hand: a wrong column is fixed in the YAML and regenerated.

---

## Tests

```bash
cd apps/api
uv run pytest              # unit tests
uv run ruff check .        # lint
uv run ruff format .       # formatting (this project uses ruff, not black)
uv run mypy src/           # type check
```

Tests marked `integration` need a real database and are skipped without one; with the dev server running and the environment sourced, `uv run pytest -m integration` picks them up.

Unit tests are not UAT. Functional verification of a feature is always end-to-end, through the scripts in the repository root's `e2e/` — see the root [`docs/testing.md`](../../../docs/testing.md).

---

## Troubleshooting

**`pydantic_core._pydantic_core.ValidationError: 3 validation errors for Settings` (or 1, or 2) listing `database_url`, `auth_oidc_issuer`, `auth_oidc_audience` as `Field required`**
The environment was not populated. `Settings` reads only the real process environment and has no defaults for these three. Run `set -a && source .env.development && set +a` in the same shell, before launching. Forgetting `set -a` produces the identical error, because unexported shell variables never reach the process.

**`Error: DATABASE_URL is not set in the environment.`**
Same cause, reported by `bin/manage_db` instead of by pydantic. The script deliberately loads no dotenv file, mirroring the application.

**`ValueError: PUBLIC_URL is required when APP_ENV=production`**
Exactly what it says: with `APP_ENV=production` the OAuth discovery metadata would otherwise advertise `localhost` URLs, so the value must be explicit. Not reachable in a normal dev run.

**`asyncpg.exceptions.InvalidCatalogNameError`, or connection refused on the DSN**
The embedded dev server is not running, or `DATABASE_URL` still holds another machine's path. Start `python -m caramello_api.shared.db_dev_server` and copy the DSN it prints.

**`relation "allowed_emails" does not exist`** (or any other missing table)
Migrations were never applied against this database. Run `./bin/manage_db upgrade`. The startup seed writes to `allowed_emails`, so this surfaces as a lifespan failure rather than a request error.

**`403` with `"reason":"not_allowlisted"`**
Authentication succeeded and authorization did not: the token's e-mail is not in `allowed_emails`. The allowlist is infrastructure, not a business entity — it has no route, and is administered by script:
```bash
uv run python scripts/seed_allowed_email.py --database-url "$DATABASE_URL" --email pessoa@exemplo.com
uv run python scripts/remove_allowed_email.py --database-url "$DATABASE_URL" --email pessoa@exemplo.com
```
The startup seed inserts one default e-mail idempotently, so a fresh database is not empty.

**`401` with `"reason":"invalid_token"` right after changing the provider**
Usually the issuer. `AUTH_OIDC_ISSUER` must be the full realm URL and must match the token's `iss` claim exactly. A less obvious variant: the provider issues tokens without `caramello-api` in `aud`, which needs an audience mapper on the provider side, not a change here.

**Health reports `"data_dir":false`**
The path in `DATA_DIR` is not an existing directory. In dev it points at the repository's `data/` folder; create it or point the variable elsewhere.

