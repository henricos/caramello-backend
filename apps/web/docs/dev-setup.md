# Development setup — caramello-web

How to bring the web up locally from scratch. Everything runs at `http://localhost:3000/caramello` — the application deliberately lives under the same base path production uses, never at the origin root.

## Prerequisites

- Node.js 22+ (the container image is `node:22-bookworm-slim`; matching the major locally avoids surprises).
- The api running locally at `http://localhost:8000` — see [`../../api/docs/dev-setup.md`](../../api/docs/dev-setup.md). The home page consumes `GET /users/me` and `GET /families/families`, and the login itself depends on `POST /auth/verify`.
- An OIDC provider reachable from this machine (next section).

## The OIDC provider in development

The web never authenticates anyone itself: it delegates to an OIDC provider, and the api decides whether that identity may use the system. In development there are two options.

**Local mock provider (intended default).** A minimal OIDC provider on `http://localhost:8790` that approves instantly, with no screen, and signs real RS256 tokens carrying the api's audience (`caramello-api`). It is the same issuer the api's `.env.development` points at. The mock belongs to the E2E harness (`e2e/` at the repository root); until that harness lands, use a real Keycloak as described below.

**A real Keycloak realm.** Point `AUTH_OIDC_ISSUER` at the realm URL (for example `https://keycloak.exemplo.com/realms/caramello`) and use the `caramello-web` client's id and secret. The realm must carry the audience mapper that stamps `caramello-api` into access tokens, otherwise every login is refused by the api even though Keycloak accepted it. Register `http://localhost:3000/caramello/api/auth/callback/oidc` as a valid redirect URI for local work.

Either way, the e-mail of the logged-in identity must be on the api's allowlist — the api is what refuses an unknown address, with `not_allowlisted`.

## Installation

```bash
cd apps/web
npm install
```

## Configuration

There is nothing to copy: `.env.development` is committed and `next dev` loads it automatically (Next.js's own convention — unlike the api, there is no `set -a && source` step). Read its header comment; what matters is that the loader is not a shell, so only plain `${VAR}` indirection works there, and that defaults live in `src/lib/env.ts`. Full rule in "Configuration and environment variables" in the root [`AGENTS.md`](../../../AGENTS.md).

Values that come from the committed file, already correct for local work:

| Variable | Value in `.env.development` |
|---|---|
| `APP_BASE_PATH` | `/caramello` |
| `API_URL` | `http://localhost:8000` |
| `AUTH_TRUST_HOST` | `true` |

Variables the file only references as `${VAR}`, and that **you must export in your own shell profile, `direnv` or secret manager** before starting the dev server:

| Variable | How to obtain it |
|---|---|
| `AUTH_OIDC_ISSUER` | `http://localhost:8790` for the mock, or your Keycloak realm URL |
| `AUTH_OIDC_CLIENT_ID` | `caramello-web` (any value works with the mock, which requires no registration) |
| `AUTH_OIDC_CLIENT_SECRET` | the client secret from Keycloak (any value works with the mock) |
| `AUTH_SECRET` | `openssl rand -base64 33` — at least 32 characters, never reused between dev and production |

If one of them is missing, the server fails at boot naming the variable (`src/lib/env.ts`), instead of failing later as a mysteriously broken login.

## Running the dev server

```bash
cd apps/web
npm run dev
```

Then open `http://localhost:3000/caramello`. The origin root (`http://localhost:3000/`) answers 404 on purpose: the app is mounted under the base path.

## Verifying the login flow

1. Open `http://localhost:3000/caramello` without a session. You are redirected to the provider and come back logged in (the mock has no screen; Keycloak shows its own).
2. The home page shows the logged-in name and e-mail plus the families you belong to (empty until you create one through the api).
3. Confirm no token leaked to the browser: `http://localhost:3000/caramello/api/auth/session` must return the session with no `accessToken`, `idToken` or `refreshToken` field.
4. `http://localhost:3000/caramello/health` must answer `{"status":"ok"}` with no session at all.
5. Click "Sair" and confirm that reaching the home page requires logging in again.

## Tests

```bash
cd apps/web
npm test           # unit tests (Vitest)
npm run test:watch # the same, in watch mode
npm run lint       # ESLint
npm run typecheck  # TypeScript
npm run build      # production build (needs the same variables as the dev server)
```

The unit tests cover the pure, security-sensitive helpers: base-path normalization, the i18n accessor, the redirect guard and the env validator. Functional verification is E2E, from `e2e/` at the repository root — see the root [`docs/testing.md`](../../../docs/testing.md).

## Troubleshooting

Keyed by the literal message you see.

- **`Missing required environment variable AUTH_SECRET (...)`**, or any other name — the variable is not exported in your shell, so the `${VAR}` indirection in `.env.development` resolved to an empty string. Export it and restart the dev server. The file itself must never receive the literal value.
- **`Invalid environment variable AUTH_SECRET: at least 32 characters required.`** — generate a real one with `openssl rand -base64 33`.
- **`Invalid environment variable AUTH_OIDC_ISSUER: expected an absolute URL, got ""`** — same cause: the exported variable is empty.
- **`Invalid APP_BASE_PATH: the value must start with "/".`** — `APP_BASE_PATH` was overridden in your shell with something like `caramello`. It must be `/caramello`.
- **`API indisponível`** on the home page — the api is not answering at `API_URL`, or it rejected the token. Check the api's log: `invalid_token` usually means the access token lacks the `caramello-api` audience (missing audience mapper in the realm).
- **`Acesso não autorizado`** (`not_allowlisted`) — the logged-in e-mail is not on the api's allowlist. Authorize it with the api's `scripts/seed_allowed_email.py`.
- **`Sua sessão expirou`** — the silent refresh failed. With the mock provider this usually means it was restarted and its signing key changed; sign in again.
- **Redirect loop back to the provider** — `AUTH_OIDC_ISSUER` does not match the issuer inside the tokens, or the provider is not running.
- **`redirect_uri` rejected by Keycloak** — the client's valid redirect URIs must include the base path: `http://localhost:3000/caramello/api/auth/callback/oidc`.
- **Every page 404s while the assets load (or the reverse)** — `APP_BASE_PATH` changed without restarting `next dev`. The value is read at startup and baked into the build.
- **`npm audit` reports advisories** — the remaining entries are transitive, inside Next.js's and ESLint's own dependency trees, with no fix available at these pins (see [`release.md`](release.md)). Do not "fix" them by downgrading Next.
