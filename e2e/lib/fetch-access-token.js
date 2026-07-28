"use strict";

/**
 * Obtains a real OAuth2 access token via the full `authorization_code` flow,
 * using only `fetch` against the mock OIDC provider — no Playwright browser.
 *
 * This is NOT an authentication bypass. The token it returns is genuinely
 * signed by the mock (RS256 key generated at runtime, published on a real
 * JWKS) and is validated end to end by `apps/api` on every single call —
 * signature, `kid`, `iss`, `aud`, `exp`, `email_verified`, allowlist. Only the
 * login TRANSPORT is direct HTTP instead of a browser; nothing about the
 * verification is skipped or stubbed.
 *
 * `grant_type=client_credentials` (service accounts) is deliberately never
 * used. Caramello's authorization model assumes a human behind every
 * consumer: access is granted to an e-mail on the `allowed_emails` allowlist
 * and scoped by family membership, so a token with no person attached has no
 * meaning in this system — and an E2E script minting one would be testing a
 * path the product does not have.
 *
 * The token's `aud` carries the api's audience because the mock's
 * `BeforeTokenSigning` hook injects it into access tokens (see
 * `mock-oidc-server.js`), mirroring Keycloak's audience mapper in production.
 * `clientId` identifies the consumer application running the flow, like each
 * consumer's own client in the real realm.
 */

const REDIRECT_URI = "http://localhost/e2e-direct-callback";

async function fetchAccessTokenViaAuthorizationCode({ issuerUrl, clientId }) {
  const authorizeUrl = new URL(`${issuerUrl}/authorize`);
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("client_id", clientId);
  authorizeUrl.searchParams.set("redirect_uri", REDIRECT_URI);
  authorizeUrl.searchParams.set("scope", "openid email profile");
  authorizeUrl.searchParams.set("state", "e2e-direct-state");
  authorizeUrl.searchParams.set("nonce", "e2e-direct-nonce");

  const authorizeResponse = await fetch(authorizeUrl, { redirect: "manual" });
  const location = authorizeResponse.headers.get("location");
  if (!location) {
    throw new Error(
      `GET /authorize on the mock OIDC (${issuerUrl}) did not respond with a redirect (status ${authorizeResponse.status})`,
    );
  }

  const code = new URL(location).searchParams.get("code");
  if (!code) {
    throw new Error(`The mock OIDC /authorize redirect did not include "code": ${location}`);
  }

  const tokenResponse = await fetch(`${issuerUrl}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: REDIRECT_URI,
      client_id: clientId,
    }),
  });
  if (!tokenResponse.ok) {
    const body = await tokenResponse.text();
    throw new Error(
      `POST /token on the mock OIDC (${issuerUrl}) failed with status ${tokenResponse.status}: ${body}`,
    );
  }

  const tokenBody = await tokenResponse.json();
  if (typeof tokenBody.access_token !== "string") {
    throw new Error(
      `The mock OIDC POST /token response did not include "access_token": ${JSON.stringify(tokenBody)}`,
    );
  }

  return tokenBody.access_token;
}

module.exports = { fetchAccessTokenViaAuthorizationCode };
