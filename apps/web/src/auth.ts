/**
 * Auth.js v5 configuration (`next-auth@5.0.0-beta.31`, pinned exactly) for the
 * full OAuth2/OIDC Authorization Code flow: Keycloak in production, a local
 * mock provider in development.
 *
 * The web is a consumer of the api like any other (see "Authentication model"
 * in the root `docs/architecture.md`): it has its OWN client
 * (`caramello-web`), and the access token it receives is accepted by the api
 * because the provider's audience mapper stamps the api's audience
 * (`caramello-api`) into it, not because the caller is "the web".
 *
 * Every variable this module needs is validated once, by name, in
 * `src/lib/env.ts` — `env()` throws at server boot if anything is missing.
 */
import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";

import { env } from "@/lib/env";
import { resolveAuthRedirect } from "@/lib/safe-redirect";

declare module "next-auth" {
  interface Session {
    /**
     * Token refresh error flag (e.g. "RefreshTokenError"), NEVER the token
     * itself — see the `session()` callback below.
     */
    error?: string;
  }
}

/**
 * Local `JWT` extension with the OIDC token fields persisted by the `jwt()`
 * callback. The ambient augmentation of `next-auth/jwt` does not resolve under
 * `moduleResolution: "bundler"`, so the extension is a local interface plus
 * casts, never a mutation of the package's global `JWT` type.
 */
interface OidcToken extends JWT {
  /**
   * Raw OIDC provider tokens, kept ONLY inside Auth.js's encrypted JWT — never
   * passed through to the public session object.
   */
  idToken?: string;
  accessToken?: string;
  refreshToken?: string;
  expiresAt?: number;
  error?: string;
}

const {
  appBasePath: configuredBasePath,
  apiUrl,
  oidcIssuer,
  oidcClientId,
  oidcClientSecret,
  authSecret,
} = env();

/**
 * Auth.js does NOT inherit Next's basePath: its own `basePath` must carry the
 * app prefix so every generated URL (signin form action, callbacks, session
 * endpoint) stays inside the mount point. Next strips the prefix from the URL
 * before route handlers run, so `app/api/auth/[...nextauth]/route.ts` re-adds
 * it before delegating — the two pieces work as a pair. This is read at
 * RUNTIME, hence the `ENV APP_BASE_PATH` in the Dockerfile's runner stage and
 * not only the build ARG.
 */
export const appBasePath = configuredBasePath;

/**
 * `token_endpoint` from the provider's discovery document, cached in module
 * memory. Never hardcode Keycloak's specific path: the refresh must stay
 * portable to any standard OIDC provider, including the dev mock.
 */
let cachedTokenEndpoint: string | undefined;

/**
 * Every outbound hop gets this timeout. A hang here would otherwise hold the
 * login callback (`signIn`) or the silent refresh (`jwt`) for the runtime's
 * multi-minute default.
 */
const AUTH_FETCH_TIMEOUT_MS = 10_000;

/**
 * Denial reasons the api's `POST /auth/verify` documents. The value is echoed
 * into a query string, so it is narrowed to this fixed set before use and
 * anything unexpected collapses to "unknown" (the error page falls back).
 */
const KNOWN_VERIFY_REASONS = new Set([
  "missing_token",
  "invalid_token",
  "expired_token",
  "email_not_verified",
  "not_allowlisted",
]);

async function getTokenEndpoint(): Promise<string> {
  if (cachedTokenEndpoint) {
    return cachedTokenEndpoint;
  }
  const response = await fetch(`${oidcIssuer}/.well-known/openid-configuration`, {
    signal: AbortSignal.timeout(AUTH_FETCH_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(
      `Failed to fetch the OIDC provider's discovery document (status ${response.status})`,
    );
  }
  const discovery = (await response.json()) as { token_endpoint: string };
  cachedTokenEndpoint = discovery.token_endpoint;
  return cachedTokenEndpoint;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  basePath: `${appBasePath}/api/auth`,
  // Auth.js would pick `AUTH_SECRET` up on its own; passing it explicitly keeps
  // a single validated source and guarantees the same value reaches
  // `getToken()` in `lib/api-client.ts`.
  secret: authSecret,
  providers: [
    {
      // Generic OIDC provider through discovery: the same configuration serves
      // Keycloak and the dev mock, with only the issuer changing.
      id: "oidc",
      name: "OIDC",
      type: "oidc",
      issuer: oidcIssuer,
      clientId: oidcClientId,
      clientSecret: oidcClientSecret,
      authorization: { params: { scope: "openid email profile" } },
      // PKCE + state declared explicitly — CSRF/replay mitigation on the OAuth
      // callback, independent of provider defaults.
      checks: ["pkce", "state"],
      // Without this, Auth.js's built-in signin page guesses a logo at
      // authjs.dev/img/providers/oidc.svg, which 404s for a custom provider id
      // and renders as a broken image.
      style: { logo: "" },
    },
  ],
  pages: {
    // No custom signIn page: the product has a single identity provider, so the
    // built-in page is a redirect stop, never a screen the user reads. Only the
    // error surface is ours.
    error: `${appBasePath}/auth/error`,
  },
  callbacks: {
    async redirect({ url, baseUrl }) {
      // Auth.js's baseUrl is the bare origin — its default post-login
      // destination ("/") would land OUTSIDE the app's mount point. Keep every
      // redirect on the app's own origin and inside the base path, falling back
      // to the app home (see lib/safe-redirect.ts).
      return resolveAuthRedirect(url, baseUrl, appBasePath);
    },
    async jwt({ token, account }) {
      const oidcToken = token as OidcToken;

      if (account) {
        // First login: persists the raw tokens only inside Auth.js's encrypted
        // JWT — never in the public session object.
        return {
          ...oidcToken,
          idToken: account.id_token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at,
        };
      }

      if (oidcToken.expiresAt && Date.now() < oidcToken.expiresAt * 1000) {
        // Still valid, no refresh needed.
        return oidcToken;
      }

      if (!oidcToken.refreshToken) {
        return { ...oidcToken, error: "RefreshTokenError" };
      }

      try {
        const tokenEndpoint = await getTokenEndpoint();
        const response = await fetch(tokenEndpoint, {
          method: "POST",
          signal: AbortSignal.timeout(AUTH_FETCH_TIMEOUT_MS),
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            client_id: oidcClientId,
            client_secret: oidcClientSecret,
            grant_type: "refresh_token",
            refresh_token: oidcToken.refreshToken,
          }),
        });
        const refreshed = (await response.json()) as {
          id_token?: string;
          access_token?: string;
          refresh_token?: string;
          expires_in?: number;
        };
        if (!response.ok) {
          throw refreshed;
        }
        return {
          ...oidcToken,
          idToken: refreshed.id_token,
          accessToken: refreshed.access_token,
          expiresAt: Math.floor(Date.now() / 1000 + (refreshed.expires_in ?? 0)),
          refreshToken: refreshed.refresh_token ?? oidcToken.refreshToken,
          // Clears a previous failure once a refresh succeeds again.
          error: undefined,
        };
      } catch (error) {
        // Never tears the session down here — `proxy.ts` is what decides to
        // force a new login when it sees `session.error === "RefreshTokenError"`.
        console.error("Failed to refresh the OIDC token", error);
        return { ...oidcToken, error: "RefreshTokenError" };
      }
    },
    async session({ session, token }) {
      // NEVER copy idToken/accessToken/refreshToken into the session: this
      // object is served by `GET /api/auth/session`, readable by ANY script on
      // the page (legitimate or XSS). The raw tokens are only read server-side
      // via `next-auth/jwt`'s `getToken()` (`lib/api-client.ts`).
      session.error = (token as OidcToken).error;
      return session;
    },
    async signIn({ account }) {
      if (!account?.access_token) {
        // Should never happen with a correctly configured OIDC provider, but
        // fail closed.
        return false;
      }

      // The api is the real gatekeeper: signature, audience, `email_verified`
      // and the e-mail allowlist are decided there (and the `users` row is
      // upserted on success) — this callback only relays the verdict. The
      // ACCESS token is what the api accepts: its `aud` carries the api's
      // audience via the provider's audience mapper.
      const response = await fetch(`${apiUrl}/auth/verify`, {
        method: "POST",
        signal: AbortSignal.timeout(AUTH_FETCH_TIMEOUT_MS),
        headers: { Authorization: `Bearer ${account.access_token}` },
      });
      if (response.ok) {
        return true;
      }

      const body: unknown = await response.json().catch(() => null);
      const rawReason = (body as { detail?: { reason?: string } } | null)?.detail?.reason;
      const reason = rawReason && KNOWN_VERIFY_REASONS.has(rawReason) ? rawReason : "unknown";
      // A fixed relative URL, built only from the constant above (never from
      // provider or user input), cancels the sign-in and redirects there — no
      // open redirect, and the human-readable text is resolved from the pt-BR
      // catalog by the error page.
      return `${appBasePath}/auth/error?reason=${reason}`;
    },
  },
});
