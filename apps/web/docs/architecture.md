# Architecture — caramello-web

## Overview

Server-rendered Next.js application (App Router) and the single interface the family group uses. It drives the OAuth2/OIDC login through Auth.js, keeps the tokens exclusively in the encrypted session cookie and forwards the `access_token` server-side as a Bearer token on every api call — no token ever reaches browser JavaScript.

The web is a consumer of the api like any other (see "Authentication model" in the root [`docs/architecture.md`](../../../docs/architecture.md)): it has its own OIDC client, `caramello-web`, and its access token is accepted because the provider's audience mapper stamps the api's audience (`caramello-api`) into it, not because the caller happens to be the web. All authorization decisions — the e-mail allowlist and family membership — belong to the api.

The module currently covers the authenticated shell: login, the denial surface, the health probe and a home page that shows who is logged in and which families that person belongs to. The product domains (schedule, finances, shopping lists, health, entertainment) grow on top of this shell, one at a time.

## Main components

- `src/auth.ts` — Auth.js configuration: generic OIDC provider via discovery, explicit PKCE and state, silent refresh against the discovered `token_endpoint`, and the `signIn` callback that asks the api's `POST /auth/verify` for a verdict before a session exists.
- `src/proxy.ts` — UX gate over every App Router request; without a usable session it redirects to login (Next 16 name — never `middleware.ts`).
- `src/app/api/auth/[...nextauth]/route.ts` — re-exports the Auth.js handlers, re-adding the base path Next strips before route handlers run.
- `src/lib/api-client.ts` — `"use server"` module: reads the access token from the encrypted cookie and calls the api with `Authorization: Bearer`; `getMe()` and `listMyFamilies()` are its typed wrappers.
- `src/lib/env.ts` — validates and normalizes every environment variable once, failing with the variable's name.
- `src/lib/base-path.ts` — `APP_BASE_PATH` normalization, mirroring the api's `normalize_app_base_path`.
- `src/lib/safe-redirect.ts` — `resolveAuthRedirect`, the open-redirect guard used by the Auth.js `redirect` callback.
- `src/i18n/index.ts` + `messages/pt-BR.json` — catalog and accessor for every user-facing string.
- `src/app/layout.tsx` — document shell: `lang` and title from the catalog, global stylesheet.
- `src/app/page.tsx` — home page: the logged-in user and their families, with an inline sign-out Server Action.
- `src/app/auth/error/page.tsx` — the single login-denial surface, mapping the api's reason codes to catalog text.
- `src/app/health/route.ts` — public `GET /health`, used by the container healthcheck.
- `src/app/globals.css` — Tailwind entry point and the `@theme` design tokens (placeholders).
- `Dockerfile` + `entrypoint.sh` — four-stage build on `node:22-bookworm-slim` and the PUID/PGID privilege drop.

## Relevant decisions

Decisions local to this module. Cross-cutting ones (authentication model, paired versions, PUID/PGID, configuration) live in the root [`docs/architecture.md`](../../../docs/architecture.md) and are not repeated here.

**User-facing strings live in the message catalog, resolved via `t()`.** The repository is English-only and the product is multilanguage with pt-BR as the implemented locale (language policy in the root `AGENTS.md`). The structural guarantee is `src/i18n/`: every string the end user reads is a key in `messages/pt-BR.json`, resolved through `t()` with compile-time-checked keys (`MessageKey`), so a hardcoded string in a component is a visible pattern violation and a typo in a key fails `tsc`. A dependency-free catalog was chosen deliberately over a framework (next-intl): with a single locale there is no negotiation, routing or plural logic to buy, and the catalog already follows the `messages/<locale>.json` convention, so adopting a library later reuses the same file. Machine-readable codes from the api (`not_allowlisted`, `expired_token`) are mapped to catalog keys at the presentation layer, never displayed raw.

**OIDC tokens never exposed to the browser.** The raw `access_token`, `id_token` and `refresh_token` live exclusively inside Auth.js's encrypted `httpOnly` cookie; the `session()` callback copies only `session.error`, so `GET /api/auth/session` — readable by any script on the page, legitimate or injected — carries no api credential. Reads happen only server-side, through `getToken()` inside the Server Actions module, and the token goes straight to the api in an `Authorization` header. There is deliberately no browser fetch to the api, which is also why no `NEXT_PUBLIC_*` variable points at it. This property is the reason native packaging was rejected for the product (see the root architecture document): a static bundle would have to hold the tokens on the device.

**`next-auth` v5 in pre-release, pinned exactly.** Auth.js v5 is the only line designed for the App Router (handlers in `route.ts`, `auth()` in Server Components and in the proxy); the stable v4 assumes the Pages Router. Depending on a pre-release in a security-critical piece is a conscious risk, mitigated by the exact pin — `5.0.0-beta.32`, the pre-release exception provided for in `docs/monorepo.md` §5 — and by the login flows that the release checklist verifies before every publish. The pin is `5.0.0-beta.32` and not the earlier `beta.31` on purpose: `beta.31` ships `@auth/core` 0.41.2, which carries three published advisories that hit exactly the paths this module uses (unbound PKCE/state/nonce cookies, and `getToken()` throwing on a malformed `Authorization` header). `package.json` cannot carry the justification itself (JSON has no comments), so it lives here. Bumping the pre-release is a deliberate act: edit the pin, run the unit tests and re-verify the login flows end to end, commit with the lockfile.

**`proxy.ts` is a UX gate, not the security boundary.** It exists so a protected page is never rendered for a visitor with no session, and it treats `session.error === "RefreshTokenError"` as "no session" so a dead token forces a fresh login instead of a page full of api errors. It is not, and must never become, the authorization layer: the api revalidates the token on every single request (JWKS/RS256, issuer, expiry, audience) and re-checks the allowlist and family membership. The public-path list is matched with an explicit segment boundary, so a crafted `/api/auth-evil` does not inherit `/api/auth`'s exemption.

**`APP_BASE_PATH` is baked at build time, and Auth.js needs it again at runtime.** Unlike the api, which applies its prefix at runtime through `root_path`, Next embeds `basePath` in the generated assets — so the image is built with `--build-arg APP_BASE_PATH=/caramello` and the Dockerfile hard-fails when that argument is empty. Auth.js does not inherit Next's `basePath`, so it is configured with the prefixed value read from the runtime environment, and `src/app/api/auth/[...nextauth]/route.ts` re-adds the prefix that Next strips before route handlers run. Dev uses the same `/caramello` prefix as production, so base-path bugs surface locally instead of only in the container.

**Tailwind v4, CSS-first, no `tailwind.config.js`.** The design tokens are declared in an `@theme` block in `src/app/globals.css`, which both registers them as utilities and emits them as `:root` custom properties; the whole build is one PostCSS plugin. This keeps the styling contract in the stylesheet, where a designer can read it, instead of splitting it between a JS config and CSS. The current token values are explicitly placeholders — coherent surfaces and contrast for the first pages, not Caramello's visual identity.

**A hand-rolled typed env validator instead of Zod.** `next dev`/`next start` auto-load `.env.development`, and that loader is not a shell, so `${VAR:-default}` is unavailable and defaults must live in code. `src/lib/env.ts` is that place: six variables, three kinds of check, no new runtime dependency in a module whose only other dependencies are the framework itself. It throws naming the offending variable — the equivalent of the api's `Settings` failing loudly — and it is lazy (a memoized function, not a top-level constant), so importing it in a unit test or a tool never validates by side effect. `readEnv` takes its source as an argument and is therefore pure and unit-tested.
