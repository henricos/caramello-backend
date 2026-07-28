# Context and Guidelines — caramello-web

Repository-wide rules (language, commits, configuration and environment variables, monorepo scope) live in the root `AGENTS.md` and must never be duplicated here. Stack, commands and environment belong to `docs/dev-setup.md`; decisions and their rationale to `docs/architecture.md`. What follows are the code standards and invariants of this module.

## Invariants

- **Tokens never reach the browser.** `access_token`, `id_token` and `refresh_token` live only inside Auth.js's encrypted `httpOnly` cookie. The `session()` callback copies `session.error` and nothing else, because `GET /api/auth/session` is readable by any script on the page. Server-side reads go through `getToken()` in `src/lib/api-client.ts` — never through `auth()`/`session()`, which do not expose those fields, and never by adding them to the session "just for debugging".
- **The browser never calls the api.** Every api call is a Server Action or a Server Component render. There is no `fetch` to `API_URL` from client code, and no api URL is embedded in a `NEXT_PUBLIC_*` variable.
- **`src/proxy.ts`, never `middleware.ts`.** Next 16 renamed the file; `middleware.ts` is simply not picked up. The proxy is a UX gate only — it is not the security guarantee, which is the api revalidating the token on every request. Never move an authorization rule into the proxy.
- **`/data` is read-only for this module.** The shared data folder is mounted `:ro` (see `compose.example.yaml`) and `entrypoint.sh` deliberately does not `chown` it. Any code that writes to `/data` is a bug: the api is the writer.
- **Every user-visible string comes from the catalog.** `messages/pt-BR.json` plus `t()` from `@/i18n`, with compile-time-checked keys. A literal in a component, a `metadata.title`, an `aria-label` or an error message is a policy violation, even as a temporary step. Codes coming from the api (`not_allowlisted`, `expired_token`, ...) are mapped to catalog keys at the presentation layer and never rendered raw.
- **Environment variables are read in one place.** `src/lib/env.ts` validates and normalizes them, failing with the variable's name. Do not read `process.env` elsewhere — the two deliberate exceptions are `next.config.ts` (must load without the auth credentials) and `env.ts` itself.
- **`APP_BASE_PATH` is structural, not decorative.** It is baked into the assets at build time and read again at runtime by Auth.js, whose `basePath` does not inherit Next's. `src/app/api/auth/[...nextauth]/route.ts` re-adds the prefix Next strips; the two files change together or the callback breaks.

## Code standards

- Server Components by default. Add `"use client"` only for genuine interactivity, and never in a file that touches tokens or the api client.
- `src/lib/api-client.ts` is the only outbound path to the api: a single private `apiFetch` with `cache: "no-store"`, an explicit timeout and the `{detail}` unwrapping. New endpoints get a thin typed wrapper there, never an inline `fetch` in a page.
- Response types mirror the api's Pydantic schemas field by field, in **snake_case**. Do not camelCase them: the point is that a contract drift shows up as an obvious diff. Public identifiers are `uuid` — integer ids never appear.
- Every outbound hop carries `AbortSignal.timeout(...)`. A request without a timeout can hold a page for minutes.
- Security-sensitive logic lives in a pure function in `src/lib/` with unit tests (`resolveAuthRedirect`, `normalizeBasePath`, `readEnv`), never inline inside a callback.
- Redirect targets are compared as parsed `URL.origin` values, never with `startsWith` on a string, and must sit inside the base path.
- Values that come from a query string or from the api are looked up in fixed maps with `Object.hasOwn`, and only the mapped catalog text is rendered.
- Tailwind v4 is CSS-first: design tokens go in the `@theme` block of `src/app/globals.css`. Do not add a `tailwind.config.js`. The current token values are placeholders, not the product's identity.
- Dependencies follow `~X.Y.Z` (patch floats only); `next-auth` is the pre-release exception, pinned exactly. Bumping it is a deliberate act — see `docs/architecture.md`.
