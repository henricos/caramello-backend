# Release Guide — api

Canonical flow for publishing a new version of the api image. The release covers the artifact's full cycle: closing the version, build and containerization (via GitHub Actions) and, finally, the guidance on how to run the published container. What happens after that (where and how the image runs) is a procedure of the publisher's environment, outside this repository.

The build is done by GitHub Actions (`.github/workflows/release-ghcr.yml`), triggered by a **GitHub release** — never by a bare tag. The workflow asserts that the release commit is an ancestor of `main` and that `apps/api/pyproject.toml`'s `[project].version` matches the tag without its leading `v`.

**Versions are paired across modules** (see "Paired versions" in the root `docs/architecture.md`): every release bumps all runnable modules to the same `X.Y.Z`, even when only one of them changed, and the single `vX.Y.Z` release publishes every image. Right now `apps/api` is the only runnable module in the repository, so this release publishes exactly one image; when `apps/web` lands, its manifest assertion and its `publish-web` job must be added to the workflow and its own `docs/release.md` becomes part of this flow.

## Preconditions

- `main` branch up to date and a clean working tree.
- Tests and lint passing, from `apps/api`: `uv run pytest && uv run ruff check .`
- Root E2E tests passing (`e2e/` at the repository root), for every journey that has a script — UAT is always E2E, see the root `docs/testing.md`.
- The version in `apps/api/pyproject.toml` is the exact version being released (the workflow fails the release otherwise).

## Canonical checklist

```bash
# From the repository root. Versions are paired: when more than one runnable
# module exists, bump ALL of them to the same X.Y.Z, even if only one changed.

# 1. Bump the version by hand in apps/api/pyproject.toml ([project].version)

# 2. Commit and tag
git add apps/api/pyproject.toml
git commit -m "chore: prepara release vX.Y.Z"
git tag vX.Y.Z
git push origin main --follow-tags

# 3. Create the release (this is what triggers the workflow)
gh release create vX.Y.Z --generate-notes
```

A published pre-release (`gh release create vX.Y.Z-rc1 --prerelease`) ships only its own tag: `latest` never moves off the newest stable release.

## Traceability check

1. Follow the workflow in Actions until it completes.
2. Confirm the `vX.Y.Z` and `latest` tags at `ghcr.io/henricos/caramello-api`.
3. After putting the new version live, run the [verification](#verification) below.

## How to run the image

Guidance for running the published image, in any environment. The `compose.example.yaml` at the repository root is the reference example for the full stack.

**Image**: `ghcr.io/henricos/caramello-api` — `vX.Y.Z` and `latest` tags. Migrations run automatically at boot (`alembic upgrade head` in the entrypoint), so upgrading to a new version is just swapping the image tag — and keep a **single replica** of the api, since two replicas starting together would race for the migration (see "Automatic migrations at boot" in the root `docs/architecture.md`).

### Prerequisites

- An existing PostgreSQL on the publisher's network (the stack does not provision a database). The role in `DATABASE_URL` must be able to create and alter tables, because the container migrates at boot.
- In Keycloak (realm `caramello`): a `caramello-api` client (the api's identity as audience; no login flow enabled, no secret needed) and, in the client of EACH consumer, an **audience mapper** that adds `caramello-api` to the `aud` of the access tokens (Client scopes → dedicated → Add mapper → Audience).
- A data directory on the host, mounted at `/data` with read and write access, owned by the UID/GID passed as `PUID`/`PGID`.

### Environment variables

Single home for the semantics of every runtime variable of this image (the compose example only encodes the stack topology).

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | Async SQLAlchemy DSN (`postgresql+asyncpg://user:password@host:5432/caramello`) of the production Postgres. No default — the service fails loudly at startup without it |
| `AUTH_OIDC_ISSUER` | yes | Full realm URL of the OIDC provider (e.g. `https://keycloak.exemplo.com/realms/caramello`). A trailing slash is stripped automatically. Discovery and JWKS are derived from it, never hardcoded |
| `AUTH_OIDC_AUDIENCE` | yes | The api's own audience (e.g. `caramello-api`), required in the `aud` claim of incoming access tokens |
| `APP_ENV` | no — default `development` | One of `development`, `test`, `production`. Set it to `production`: that is what disables `/docs` and `/openapi.json`. An invalid value fails at startup instead of silently falling back |
| `PUID` / `PGID` | no — default `1000` | UID/GID the container's `app` user is adjusted to, matching the owner of `/data` on the host. `0` (root) and non-numeric values are rejected by the entrypoint before anything is touched |
| `APP_BASE_PATH` | no — default empty | FastAPI's `root_path` when the api sits behind a reverse proxy under a prefix (e.g. `/caramello-api`). It only affects generated OpenAPI URLs; it does not rewrite routes. Must start with `/`, no trailing or duplicated slashes |
| `DATA_DIR` | no — default `/data` | Shared data folder. Leave it at the default in a container: `/data` is the fixed in-image path and mapping it to a host folder is the deploy's job. It exists for local development, where `/data` is usually not writable |
| `CARAMELLO_API_HOST` | no — default `0.0.0.0` | Bind address of the uvicorn process |
| `CARAMELLO_API_PORT` | no — default `8000` | Bind port. If you change it, also change the `ports:` mapping and the healthcheck URL in the compose file — `EXPOSE 8000` in the Dockerfile is documentation only |
| `CARAMELLO_API_LOG_LEVEL` | no — default `info` | Log level applied to both the application loggers and uvicorn's access/error logs |

The service reads the process environment only; it never loads a dotenv file on its own (see "Configuration comes from the process environment" in the root `docs/architecture.md`).

### Volumes and network

- `/data`: shared data folder, mounted with **read and write** access in this module (the api is the writer; a future web mounts the same label read-only). Align the directory owner on the host with `PUID`/`PGID`.
- Port `8000` published on the host: the Cloudflare Tunnel's ingress rules point at `<SERVER_IP>:8000`, and any application addressing the api directly uses the server's IP and the published port, never the container name — see `compose.example.yaml`.

### User authorization

There is no HTTP route and no CLI script for granting access, and the image deliberately carries no `scripts/` directory (that is development tooling). Authorization has two layers, both driven by data already in the database:

- **Identity**: a user record is provisioned just-in-time on the first authenticated request, from the verified token's claims. Whoever can obtain a token from the configured realm — and is a member of a family — can use the system.
- **Family membership**: every business read and write is scoped to the caller's family. A brand-new user with no family sees nothing until they create one (`POST /families/registry`, which makes the caller its owner) or are added to an existing one by its owner.

So "authorizing a person" means, in practice: give them a client/login in the realm whose access tokens carry `AUTH_OIDC_AUDIENCE`, then have a family owner add them to the family.

### MCP clients (Claude Desktop, agents)

The api mounts its MCP transport at `/mcp`, behind the same bearer-token validation as the REST routes, and exposes a curated subset of operations as tools. An MCP client must present an `access_token` from the same realm, issued to its own client and carrying the api's audience — the api never starts an OAuth flow itself, so the client (or the operator configuring it) is responsible for obtaining the token. The human behind that token still needs to be a member of a family for any business tool to return data.

### Verification

```bash
curl -s https://exemplo.com/caramello-api/health
# expected: {"status":"ok","checks":{"database":true,"data_dir":true}}

curl -s -o /dev/null -w '%{http_code}' https://exemplo.com/caramello-api/users/me
# expected: 401 (protected route)

docker exec caramello-api id -u app
# expected: the configured PUID

docker logs caramello-api | grep -i alembic
# expected: the migration run from the entrypoint, before uvicorn starts
```

### Known pitfalls

- **`/docs` or `/openapi.json` reachable in production**: `APP_ENV` is not set to `production`.
- **Container exits immediately with "Invalid PUID/PGID"**: `PUID`/`PGID` was set to `0` or to a non-numeric value; the entrypoint rejects both by design.
- **Permission error on `/data`**: the directory owner on the host does not match `PUID`/`PGID`. The healthcheck reports it as `"data_dir": false` and the endpoint answers 503.
- **401 on every request**: the audience mapper is missing on the consumer's client (the access token's `aud` does not contain `AUTH_OIDC_AUDIENCE`), or `AUTH_OIDC_ISSUER` does not match the token's `iss`.
- **Migrations not applied / container fails at boot**: the container must reach the database at boot with a role allowed to change the schema; check `DATABASE_URL` and the network.
- **Empty responses for an authenticated user**: the user belongs to no family — authentication succeeded, family scoping returned nothing.
- **The release workflow never ran**: only a *published GitHub release* triggers it; pushing a bare tag builds nothing.
