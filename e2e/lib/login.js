"use strict";

/**
 * Shared Playwright login helper against the mock OIDC provider.
 *
 * `apps/web` has no login screen of its own (`src/auth.ts` sets only
 * `pages.error`): navigating to any protected route without a session triggers
 * the redirect chain by itself (`proxy.ts` → `<basePath>/api/auth/signin` →
 * provider `/authorize` → callback). Auth.js without a custom `pages.signIn`
 * renders an intermediate page with a single provider button — the helper
 * clicks it when present and waits for the chain to land back on `apps/web`,
 * outside `/api/auth/*`.
 *
 * After the login, the helper proves at RUNTIME that
 * `GET <basePath>/api/auth/session` never exposes `idToken`/`accessToken`/
 * `refreshToken`. This is the single most important invariant of `apps/web`:
 * that endpoint is readable by ANY script on the page, so the guarantee of
 * `src/auth.ts`'s `session()` callback is re-verified on EVERY run and a leak
 * throws instead of being reported as a soft failure.
 */

async function loginViaMockOidc(page, { webBaseUrl, startPath = "" }) {
  // `webBaseUrl` includes the base path (e.g. http://localhost:3100/caramello);
  // the Auth.js routes live under it.
  const base = new URL(webBaseUrl);
  const basePath = base.pathname === "/" ? "" : base.pathname.replace(/\/$/, "");
  const authPrefix = `${basePath}/api/auth`;

  await page.goto(`${base.origin}${basePath}${startPath || "/"}`);

  if (new URL(page.url()).pathname === `${authPrefix}/signin`) {
    await page.locator('form button[type="submit"]').first().click();
  }

  await page.waitForURL(
    (url) => url.origin === base.origin && !url.pathname.startsWith(authPrefix),
    { timeout: 20000 },
  );

  const sessionResponse = await page.request.get(`${base.origin}${authPrefix}/session`);
  const sessionBody = await sessionResponse.json();

  // `GET /api/auth/session` responds `null` when the login was denied — the
  // leak check only makes sense when a session exists.
  const leakedFields = sessionBody
    ? ["idToken", "accessToken", "refreshToken"].filter((field) => field in sessionBody)
    : [];
  if (leakedFields.length > 0) {
    throw new Error(
      `Security regression: GET ${authPrefix}/session exposed sensitive field(s) ` +
        `${leakedFields.join(", ")} — the session() callback in apps/web/src/auth.ts ` +
        `must never pass a raw token through to the public session endpoint.`,
    );
  }
}

module.exports = { loginViaMockOidc };
