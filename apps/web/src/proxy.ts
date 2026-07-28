/**
 * `proxy.ts` (Next.js 16 — this file is NEVER named `middleware.ts`; that is
 * the pre-16 name and Next 16 does not pick it up): intercepts every App Router
 * request except the public ones and redirects straight to login when there is
 * no usable session.
 *
 * This is only a UX optimization (it avoids rendering a protected page that has
 * no session behind it) and NEVER the security guarantee. The guarantee stays
 * with the api, which revalidates the access token on every single request
 * (JWKS/RS256, issuer, expiry, audience) and re-checks the allowlist and family
 * membership. A session cookie being "present" here says nothing about whether
 * the api still accepts the token inside it.
 */
import { auth } from "@/auth";
import { env } from "@/lib/env";

/**
 * Paths reachable without a session:
 * - `/auth/error` — the denial surface, which by definition renders after a
 *   sign-in was refused.
 * - `/api/auth` — Auth.js's own routes (signin, callback, session, signout).
 * - `/health` — the container healthcheck and external uptime monitoring.
 */
const PUBLIC_PATHS = ["/auth/error", "/api/auth", "/health"];

// Next is inconsistent about basePath here: the production server strips it
// (`nextUrl.basePath` filled, `pathname` without the prefix), while `next dev`
// delivers the RAW path (`basePath` empty, `pathname` including the prefix).
// Normalize both shapes from the same variable the build used.
const CONFIGURED_BASE_PATH = env().appBasePath;

function splitBasePath(req: { nextUrl: { pathname: string; basePath: string } }) {
  if (req.nextUrl.basePath) {
    return { basePath: req.nextUrl.basePath, pathname: req.nextUrl.pathname };
  }
  const raw = req.nextUrl.pathname;
  if (
    CONFIGURED_BASE_PATH &&
    (raw === CONFIGURED_BASE_PATH || raw.startsWith(`${CONFIGURED_BASE_PATH}/`))
  ) {
    return {
      basePath: CONFIGURED_BASE_PATH,
      pathname: raw.slice(CONFIGURED_BASE_PATH.length) || "/",
    };
  }
  return { basePath: "", pathname: raw };
}

export const proxy = auth((req) => {
  const { basePath, pathname } = splitBasePath(req);

  // Explicit segment boundary instead of a raw textual prefix: only the exact
  // route or one of its subpaths (`${path}/...`) is public, so a crafted
  // `/api/auth-evil` does NOT inherit `/api/auth`'s exemption.
  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );

  if (isPublic) {
    return;
  }

  // `session.error === "RefreshTokenError"` is equivalent to "no session": the
  // silent refresh already failed, so the token behind the cookie is dead.
  // Forces a new login early instead of leaving the user inside a session the
  // api would reject anyway.
  const hasValidSession = Boolean(req.auth) && req.auth?.error !== "RefreshTokenError";

  if (!hasValidSession) {
    // The redirect must stay inside the app's mount point — a bare
    // "/api/auth/signin" would escape the base path. `callbackUrl` brings the
    // user back to the page originally requested after the login.
    const signInUrl = new URL(`${basePath}/api/auth/signin`, req.nextUrl.origin);
    signInUrl.searchParams.set(
      "callbackUrl",
      `${basePath}${pathname}${req.nextUrl.search}`,
    );
    return Response.redirect(signInUrl);
  }
});

export const config = {
  // Excludes Next.js static assets from the proxy. The bare "/" entry is
  // deliberate: under a basePath, the catch-all pattern alone does not match
  // the root request (e.g. GET /caramello), which would leave the home page
  // outside the proxy.
  matcher: ["/", "/((?!_next/static|_next/image|favicon.ico).*)"],
};
