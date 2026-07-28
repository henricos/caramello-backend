"use strict";

/**
 * REAL fake OIDC provider for the E2E scripts — never an unsigned
 * "always approves" mock, and never a bypass of the api's own validation.
 * `OAuth2Server` generates a genuine RS256 key pair, publishes it on a real
 * JWKS document and signs real tokens, so `shared/auth.py` runs exactly the
 * code path production runs: discovery, JWKS fetch, `kid` lookup, RS256
 * signature check, `iss`/`aud`/`exp` validation.
 *
 * `startMockOidc({ port, email, emailVerified, name, sub, audience })` starts
 * the server at `http://localhost:<port>`, exposing the standard OIDC
 * endpoints:
 *   - `/.well-known/openid-configuration` (real discovery document)
 *   - `/jwks` (real JWKS, freshly generated RS256 key)
 *   - `/authorize` (no login screen — redirects straight to the callback,
 *     matching the expected dev behavior: login is instantaneous)
 *   - `/token` (code/refresh exchange, signing with the generated key)
 *
 * The `BeforeTokenSigning` hook injects the claims Caramello's authorization
 * depends on (`email`, `email_verified`, `name`) plus, optionally, `sub`.
 * `sub` matters because `oauth2-mock-server` hardcodes `sub: "johndoe"` for
 * the `authorization_code` grant: the api provisions users keyed on `idp_sub`
 * (`shared/auth.py`), so two E2E identities sharing that constant would
 * collapse into ONE user row and the family-scoping scenario could not be
 * written at all. Overriding it makes each simulated person a distinct
 * identity at the provider.
 *
 * `audience` is injected into the `aud` of ACCESS tokens ONLY — mirroring
 * Keycloak's audience mapper, which is what makes the api accept the token.
 * The discriminator relies on oauth2-mock-server internals: the id_token
 * payload is born with `aud = client_id`, while the access token is born
 * WITHOUT `aud`, so only the latter gets the audience (the id_token keeps the
 * `aud` that Auth.js/openid-client validates against the client_id).
 *
 * For direct HTTP calls to the api without a browser, see
 * `fetch-access-token.js`.
 */

const { OAuth2Server, Events } = require("oauth2-mock-server");

async function startMockOidc({
  port,
  email,
  emailVerified = true,
  name = "Usuário E2E",
  sub,
  audience,
}) {
  const server = new OAuth2Server();

  await server.issuer.keys.generate("RS256");

  server.service.on(Events.BeforeTokenSigning, (token) => {
    token.payload.email = email;
    token.payload.email_verified = emailVerified;
    token.payload.name = name;
    if (sub) {
      token.payload.sub = sub;
    }
    if (audience && token.payload.aud === undefined) {
      token.payload.aud = audience;
    }
  });

  // Bind explicitly to 127.0.0.1, never to the name "localhost": Node resolves
  // that name to the IPv6 loopback first here, so the server would listen only
  // on `::1` while every client in this harness (Node's `fetch`, the api's
  // `httpx`, Chromium) connects to `127.0.0.1` and gets ECONNREFUSED. The
  // discovery document still advertises `http://localhost:<port>` — which is
  // what `AUTH_OIDC_ISSUER` and the `iss` claim must agree on.
  await server.start(port, "127.0.0.1");

  return {
    server,
    issuerUrl: server.issuer.url,
    close: () => server.stop(),
  };
}

module.exports = { startMockOidc };
