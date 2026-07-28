# Release guide — caramello-web

Canonical flow for publishing a new version of the web image: closing the version, building and containerizing (via GitHub Actions) and, at the end, how to run the published container. What happens after that — where the image runs — is a procedure of the publisher's environment, outside this repository.

The build is done by GitHub Actions ([`.github/workflows/release-ghcr.yml`](../../../.github/workflows/release-ghcr.yml)), triggered by a **GitHub release**, never by a bare tag.

**Versions are paired across modules** (see "Paired versions" in the root [`docs/architecture.md`](../../../docs/architecture.md)): every release bumps `apps/web/package.json` and `apps/api/pyproject.toml` to the same `X.Y.Z`, even when only one of them changed, and the single `vX.Y.Z` release publishes BOTH images. The workflow asserts both manifests against the tag before building anything. The api counterpart of this flow is [`../../api/docs/release.md`](../../api/docs/release.md).

## Preconditions

- `main` up to date and a clean working tree.
- Tests, lint, typecheck and build passing:

```bash
cd apps/web
npm test && npm run lint && npm run typecheck
APP_BASE_PATH=/caramello npm run build   # plus the auth variables, see docs/dev-setup.md
```

- The login flow verified manually or by the root E2E scripts (`e2e/`), as described in [`dev-setup.md`](dev-setup.md#verifying-the-login-flow) — at minimum: a successful login, a denied login, and `GET /api/auth/session` leaking no token.
- Because the same release publishes the api image, the preconditions in [`../../api/docs/release.md`](../../api/docs/release.md) must hold too.
- `npm audit` is informational here: the remaining advisories are transitive inside Next.js's and ESLint's own trees and have no fix at these pins. A **direct** dependency advisory, on the other hand, blocks the release.

## Canonical checklist

```bash
# From the repository root. Versions are paired: bump BOTH modules to the same
# X.Y.Z, even if only one of them changed.

# 1. Bump the version
#    - apps/web/package.json (+ lockfile) and this module's README.md badge:
(cd apps/web && npm version X.Y.Z --no-git-tag-version)
#    - apps/api/pyproject.toml ([project].version) and the api's README.md
#      badge, by hand.

# 2. Commit and tag
git add apps/web/package.json apps/web/package-lock.json apps/web/README.md \
        apps/api/pyproject.toml apps/api/README.md
git commit -m "chore: prepare release vX.Y.Z"
git tag vX.Y.Z
git push origin main --follow-tags

# 3. Create the release (this is what triggers the workflow)
gh release create vX.Y.Z --generate-notes
```

## Traceability check

1. Follow the workflow in Actions until it completes: `prepare`, then `publish-api` and `publish-web` in parallel.
2. Confirm the `vX.Y.Z` and `latest` tags at `ghcr.io/henricos/caramello-web` — and at `ghcr.io/henricos/caramello-api`, published by the same release.
3. After putting the new version live, run the [verification](#verification) below.

## How to run the image

Guidance for running the published image in any environment. [`compose.example.yaml`](../../../compose.example.yaml) at the repository root is the reference example for the full stack (web + api).

**Image**: `ghcr.io/henricos/caramello-web` — `vX.Y.Z` and `latest` tags. `APP_BASE_PATH` (`/caramello`) is **baked at build time**; changing the base path requires a new release, not an environment change.

### Prerequisites

- The web's own OIDC client registered in Keycloak, `caramello-web`, with redirect URI `https://exemplo.com/caramello/api/auth/callback/oidc` and an **audience mapper** adding the api's audience (`caramello-api`) to the access tokens. Without the mapper the api rejects every login — see the api's release guide.
- The api published and reachable at `API_URL`.
- The shared `/data` directory on the host, owned by the `PUID`/`PGID` pair used across the stack.

### Environment variables

The semantics of every runtime variable of this image live here and only here (one image, one page).

| Variable | Required | Description |
|---|---|---|
| `AUTH_SECRET` | yes | Secret that signs and encrypts the session cookie. Generate with `openssl rand -base64 33`; at least 32 characters, and never the dev value |
| `AUTH_OIDC_ISSUER` | yes | Full realm URL in Keycloak, e.g. `https://keycloak.exemplo.com/realms/caramello`. A trailing slash is stripped automatically |
| `AUTH_OIDC_CLIENT_ID` | yes | The web's own OIDC client, `caramello-web` |
| `AUTH_OIDC_CLIENT_SECRET` | yes | That client's secret |
| `API_URL` | yes | URL of the api as this container reaches it — by default the same public URL every consumer uses (e.g. `https://exemplo.com/caramello-api`); `http://<SERVER_IP>:8000` is an optional latency optimization. No version prefix |
| `AUTH_TRUST_HOST` | yes | `true` behind a reverse proxy or tunnel, so Auth.js accepts the forwarded host |
| `AUTH_URL` | yes | Public URL of the auth handler, including the baked base path, e.g. `https://exemplo.com/caramello/api/auth` |
| `PUID` / `PGID` | yes | UID/GID of the `/data` owner on the host — the SAME pair used by the api. `0` (root) is rejected at startup |
| `APP_BASE_PATH` | no | Already set in the image to the value baked at build time. Overriding it only desynchronizes the runtime from the compiled assets |
| `PORT` / `HOSTNAME` | no | Default to `3000` and `0.0.0.0` |

### Volumes and network

- `/data`: the data folder shared with the api, mounted **read-only** here (the api is the writer). Align the host directory's owner with `PUID`/`PGID`; the entrypoint deliberately does not `chown` a read-only mount.
- Port `3000` published on the host: the tunnel's ingress rules point at `<SERVER_IP>:3000`, and any direct addressing uses the server's IP and the published port, never the container name — see `compose.example.yaml`.

### Verification

1. Open the public URL with no session — it must redirect to the Keycloak login screen.
2. Log in with an authorized e-mail — it must land on the home page with the family list loaded.
3. Log in with an e-mail outside the allowlist — it must land on "Acesso não autorizado".
4. `GET https://exemplo.com/caramello/api/auth/session` must not contain `accessToken`, `idToken` or `refreshToken`.
5. `GET https://exemplo.com/caramello/health` must answer `{"status":"ok"}`.
6. Click "Sair" and confirm that access requires logging in again.

```bash
docker exec caramello-web id -u app
# expected: the configured PUID
```

### Known pitfalls

- **Redirect loop, or a callback pointing at the wrong host** — `AUTH_TRUST_HOST` or `AUTH_URL` missing behind the reverse proxy.
- **Assets 404** — the `APP_BASE_PATH` baked into the image does not match the public path the proxy serves. It is a rebuild, not an environment fix.
- **Login accepted by Keycloak but denied by the app** — the e-mail is outside the api's allowlist, or `email_verified=false` in Keycloak.
- **`invalid_token` on every login** — the realm's audience mapper is missing, so the access token does not carry `caramello-api`.
- **Container exits at startup with `Invalid PUID/PGID`** — a non-numeric value, or `0`.
- **Container exits with `Invalid environment variable ...`** — a required variable is missing or malformed; the message names it.
