"use strict";

/**
 * E2E — `apps/api`'s REST and MCP contract, against a fully isolated instance
 * (dedicated ephemeral pgembed Postgres + uvicorn) and a real fake OIDC
 * provider (`oauth2-mock-server`, genuine RS256) — no browser.
 *
 * Covered scenarios:
 *   1.  GET /health is public and responds 200 with the database and data_dir
 *       checks.
 *   2.  GET /api/v1/users/me without Authorization responds 401 missing_token.
 *   3.  GET /api/v1/users/me with a malformed token responds 401
 *       invalid_token.
 *   4.  POST /auth/verify with an e-mail OUTSIDE the allowlist responds 403
 *       not_allowlisted, with a generic message that never echoes the address.
 *   5.  POST /auth/verify with an allowlisted e-mail responds 200 and upserts
 *       the user; the denied identity of scenario 4 created NO users row.
 *   6.  GET /api/v1/users/me returns uuid/email/idp_sub from the validated
 *       token, and a second call is idempotent (JIT provisioning does not
 *       duplicate).
 *   7.  POST /api/v1/families/registry creates a family with the caller as
 *       owner, and GET /api/v1/families/families then lists it.
 *   8.  A SECOND authorized identity sees none of that family: its own
 *       /families/families is empty and GET /families/families/{uuid}
 *       responds 403 not_family_member — the family-scoping invariant.
 *   9.  email_verified=false responds 403 email_not_verified even for an
 *       allowlisted e-mail (mock rotation on the same port, which also proves
 *       the api's JWKS refresh on an unknown kid).
 *   10. A token whose `aud` is another service's audience is rejected with 401
 *       invalid_token (the invariant that closed deferral D-02).
 *   11. GET /.well-known/oauth-protected-resource is public and announces the
 *       resource (`<PUBLIC_URL>/mcp`) and the authorization server (the
 *       issuer) — RFC 9728, MCP spec 2025-06-18. The `/mcp` path form answers
 *       too.
 *   12. GET /.well-known/oauth-authorization-server is public and relays the
 *       provider's discovery document — RFC 8414 fallback for MCP spec
 *       2025-03-26 clients.
 *   13. POST /mcp without a token responds 401 and the response carries the
 *       `WWW-Authenticate` header pointing at the Protected Resource
 *       Metadata (MCP OAuth discovery).
 *   14. tools/list via MCP (Streamable HTTP) with a valid token exposes the
 *       whitelisted list_my_families tool — and only it.
 *   15. Removing an e-mail from the allowlist (remove_allowed_email.py)
 *       revokes it: the next /auth/verify responds 403 not_allowlisted even
 *       though the token is still cryptographically valid.
 *
 * Environment variables (defaults isolated from any dev instance and from the
 * other E2E scripts):
 *   API_E2E_PORT     default 8300
 *   MOCK_OIDC_PORT   default 8793
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

if (!fs.existsSync(path.join(__dirname, "node_modules"))) {
  execFileSync("npm", ["install"], { cwd: __dirname, stdio: "inherit" });
}

const { startMockOidc } = require("./lib/mock-oidc-server");
const { fetchAccessTokenViaAuthorizationCode } = require("./lib/fetch-access-token");
const {
  sleep,
  waitForHttpStatus,
  killAndWait,
  startEphemeralPostgres,
  apiEnv,
  runMigrations,
  seedAllowedEmail,
  removeAllowedEmail,
  spawnApi,
} = require("./lib/harness");

const API_PORT = Number(process.env.API_E2E_PORT || 8300);
const API_BASE_URL = `http://localhost:${API_PORT}`;
// 8793, not the 8790 the manual dev mock (`scripts/dev-oidc-server.js`) uses:
// an E2E run must never collide with a provider the developer left running.
const MOCK_OIDC_PORT = Number(process.env.MOCK_OIDC_PORT || 8793);
const MOCK_ISSUER_URL = `http://localhost:${MOCK_OIDC_PORT}`;

const API_V1 = "/api/v1";

const OIDC_CLIENT_ID = "e2e-api-client";
// The api's own audience: the mock injects it into access tokens the same way
// Keycloak's audience mapper does in production.
const OIDC_AUDIENCE = "e2e-caramello-api";
// Scenario 10 — a token minted for a DIFFERENT resource server.
const OTHER_AUDIENCE = "e2e-outro-servico";

const OWNER_EMAIL = "titular.e2e@exemplo.com.br";
const MEMBER_EMAIL = "outra.pessoa.e2e@exemplo.com.br";
const DENIED_EMAIL = "fora.da.lista.e2e@exemplo.com.br";

// Distinct `sub` per identity: oauth2-mock-server hardcodes `sub: "johndoe"`
// for the authorization_code grant, and the api keys users on `idp_sub`, so
// without this the two authorized identities would share one users row.
const OWNER_SUB = "e2e-sub-titular";
const MEMBER_SUB = "e2e-sub-outra-pessoa";
const DENIED_SUB = "e2e-sub-fora-da-lista";

// Sample data is pt-BR because it is content, not code (language policy in
// the root AGENTS.md).
const FAMILY_NAME = "Família Caramello E2E";
const FAMILY_DESCRIPTION = "Família criada pelo roteiro E2E de endpoints.";

async function mcpRequest(accessToken, body, sessionId) {
  return fetch(`${API_BASE_URL}/mcp`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(sessionId ? { "mcp-session-id": sessionId } : {}),
    },
    body: JSON.stringify(body),
  });
}

/**
 * Reads a response body without ever throwing. A `500` from FastAPI answers
 * `Internal Server Error` as plain text, and `await response.json()` on that
 * would abort the whole run with a `SyntaxError` instead of failing the one
 * scenario — the raw text is surfaced in the check's label instead.
 */
async function readBody(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    return { __raw: text };
  }
}

/** Extracts the JSON-RPC result from an MCP response (plain JSON or SSE). */
async function parseMcpResponse(response) {
  const text = await response.text();
  const dataLine = text.split("\n").find((line) => line.startsWith("data:"));
  return JSON.parse(dataLine ? dataLine.slice(5).trim() : text);
}

async function run() {
  let pg = null;
  let api = null;
  const state = { mock: null };
  let failures = 0;

  const check = (condition, label) => {
    if (condition) {
      console.log(`  ok: ${label}`);
    } else {
      failures += 1;
      console.error(`  FAILED: ${label}`);
    }
  };

  /**
   * Restarts the mock provider on the SAME port with different claims. The
   * api keeps its fixed AUTH_OIDC_ISSUER and absorbs the new RS256 kid
   * through its JWKS refresh — which is itself under test.
   */
  const rotateMock = async (options) => {
    if (state.mock) {
      await state.mock.close().catch(() => {});
      state.mock = null;
      await sleep(200);
    }
    state.mock = await startMockOidc({
      port: MOCK_OIDC_PORT,
      audience: OIDC_AUDIENCE,
      ...options,
    });
    return state.mock;
  };

  const tokenFor = async () =>
    fetchAccessTokenViaAuthorizationCode({
      issuerUrl: MOCK_ISSUER_URL,
      clientId: OIDC_CLIENT_ID,
    });

  const authorized = (token) => ({ Authorization: `Bearer ${token}` });

  try {
    console.log("Starting ephemeral Postgres (pgembed)...");
    pg = await startEphemeralPostgres();

    await rotateMock({ email: OWNER_EMAIL, sub: OWNER_SUB, emailVerified: true });

    const env = apiEnv({
      databaseUrl: pg.databaseUrl,
      issuerUrl: MOCK_ISSUER_URL,
      audience: OIDC_AUDIENCE,
      // PUBLIC_URL feeds the OAuth discovery metadata (scenarios 11 and 13).
      extra: { PUBLIC_URL: API_BASE_URL },
    });

    runMigrations(env);
    seedAllowedEmail(env, OWNER_EMAIL);
    seedAllowedEmail(env, MEMBER_EMAIL);

    console.log("Starting apps/api...");
    api = spawnApi({ env, port: API_PORT });
    await waitForHttpStatus(`${API_BASE_URL}/health`, 60000, "apps/api to respond", api);

    // Scenario 1 — public health with checks.
    const health = await fetch(`${API_BASE_URL}/health`);
    const healthBody = await readBody(health);
    check(health.status === 200, "GET /health responds 200 without authentication");
    check(
      healthBody.checks?.database === true && healthBody.checks?.data_dir === true,
      `health reports database and data_dir accessible (got ${JSON.stringify(healthBody)})`,
    );

    // Scenario 2 — no token.
    const noToken = await fetch(`${API_BASE_URL}${API_V1}/users/me`);
    const noTokenBody = await readBody(noToken);
    check(
      noToken.status === 401 && noTokenBody.detail?.reason === "missing_token",
      `GET ${API_V1}/users/me without Authorization responds 401 missing_token (got ${noToken.status} ${JSON.stringify(noTokenBody)})`,
    );

    // Scenario 3 — malformed token.
    const badToken = await fetch(`${API_BASE_URL}${API_V1}/users/me`, {
      headers: authorized("not-a-jwt"),
    });
    const badTokenBody = await readBody(badToken);
    check(
      badToken.status === 401 && badTokenBody.detail?.reason === "invalid_token",
      `GET ${API_V1}/users/me with a malformed token responds 401 invalid_token (got ${badToken.status} ${JSON.stringify(badTokenBody)})`,
    );

    // Scenario 4 — authenticated at the provider, but outside the allowlist.
    await rotateMock({ email: DENIED_EMAIL, sub: DENIED_SUB, emailVerified: true });
    const deniedToken = await tokenFor();
    const deniedVerify = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: authorized(deniedToken),
    });
    const deniedBody = await readBody(deniedVerify);
    check(
      deniedVerify.status === 403 && deniedBody.detail?.reason === "not_allowlisted",
      `POST /auth/verify outside the allowlist responds 403 not_allowlisted (got ${deniedVerify.status} ${JSON.stringify(deniedBody)})`,
    );
    check(
      !JSON.stringify(deniedBody).includes(DENIED_EMAIL),
      "the not_allowlisted body never echoes the requested e-mail back",
    );

    // Scenario 5 — allowlisted: verify 200 + upsert into users.
    await rotateMock({ email: OWNER_EMAIL, sub: OWNER_SUB, emailVerified: true });
    const ownerToken = await tokenFor();
    const verify = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: authorized(ownerToken),
    });
    const verifyBody = await readBody(verify);
    check(
      verify.status === 200 && verifyBody.email === OWNER_EMAIL && verifyBody.sub === OWNER_SUB,
      `POST /auth/verify allowlisted responds 200 with the identity (got ${verify.status} ${JSON.stringify(verifyBody)})`,
    );

    const users = await fetch(`${API_BASE_URL}${API_V1}/users/user/`, {
      headers: authorized(ownerToken),
    });
    const usersBody = await readBody(users);
    const createdOwner = Array.isArray(usersBody)
      ? usersBody.find((user) => user.email === OWNER_EMAIL)
      : undefined;
    check(
      users.status === 200 && Boolean(createdOwner),
      `GET ${API_V1}/users/user/ lists the user provisioned by verify`,
    );
    check(
      !Array.isArray(usersBody) || !usersBody.some((user) => user.email === DENIED_EMAIL),
      "the denied login never created a users row",
    );

    // Scenario 6 — /users/me and JIT idempotency.
    const me = await fetch(`${API_BASE_URL}${API_V1}/users/me`, {
      headers: authorized(ownerToken),
    });
    const meBody = await readBody(me);
    check(
      me.status === 200 && meBody.email === OWNER_EMAIL && meBody.idp_sub === OWNER_SUB,
      `GET ${API_V1}/users/me returns the token's identity (got ${me.status} ${JSON.stringify(meBody)})`,
    );
    const meAgain = await fetch(`${API_BASE_URL}${API_V1}/users/me`, {
      headers: authorized(ownerToken),
    });
    const meAgainBody = await readBody(meAgain);
    check(
      meAgain.status === 200 && meAgainBody.uuid === meBody.uuid,
      "a second authenticated call returns the same uuid (JIT provisioning is idempotent)",
    );

    // Scenario 7 — the family journey: create, then see it listed.
    const registry = await fetch(`${API_BASE_URL}${API_V1}/families/registry`, {
      method: "POST",
      headers: { ...authorized(ownerToken), "Content-Type": "application/json" },
      body: JSON.stringify({ name: FAMILY_NAME, description: FAMILY_DESCRIPTION }),
    });
    const registryBody = await readBody(registry);
    check(
      registry.status === 201 && registryBody.name === FAMILY_NAME && registryBody.uuid,
      `POST ${API_V1}/families/registry creates the family (got ${registry.status} ${JSON.stringify(registryBody)})`,
    );
    const familyUuid = registryBody.uuid;

    const myFamilies = await fetch(`${API_BASE_URL}${API_V1}/families/families`, {
      headers: authorized(ownerToken),
    });
    const myFamiliesBody = await readBody(myFamilies);
    check(
      myFamilies.status === 200 &&
        Array.isArray(myFamiliesBody) &&
        myFamiliesBody.some((family) => family.uuid === familyUuid),
      `GET ${API_V1}/families/families lists the family just created`,
    );

    // Scenario 8 — family scoping: another authorized identity sees nothing.
    await rotateMock({ email: MEMBER_EMAIL, sub: MEMBER_SUB, emailVerified: true });
    const memberToken = await tokenFor();
    const memberVerify = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: authorized(memberToken),
    });
    check(
      memberVerify.status === 200,
      `the second identity is allowlisted and verifies (got ${memberVerify.status})`,
    );
    const memberFamilies = await fetch(`${API_BASE_URL}${API_V1}/families/families`, {
      headers: authorized(memberToken),
    });
    const memberFamiliesBody = await readBody(memberFamilies);
    check(
      memberFamilies.status === 200 &&
        Array.isArray(memberFamiliesBody) &&
        memberFamiliesBody.length === 0,
      `the second identity's ${API_V1}/families/families is empty (got ${JSON.stringify(memberFamiliesBody)})`,
    );
    const memberDetail = await fetch(`${API_BASE_URL}${API_V1}/families/families/${familyUuid}`, {
      headers: authorized(memberToken),
    });
    const memberDetailBody = await readBody(memberDetail);
    check(
      memberDetail.status === 403 && memberDetailBody.detail?.reason === "not_family_member",
      `a non-member gets 403 not_family_member on the family detail route (got ${memberDetail.status} ${JSON.stringify(memberDetailBody)})`,
    );

    // Scenario 9 — email_verified=false denies even when allowlisted.
    await rotateMock({ email: OWNER_EMAIL, sub: OWNER_SUB, emailVerified: false });
    const unverifiedToken = await tokenFor();
    const unverified = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: authorized(unverifiedToken),
    });
    const unverifiedBody = await readBody(unverified);
    check(
      unverified.status === 403 && unverifiedBody.detail?.reason === "email_not_verified",
      `email_verified=false responds 403 email_not_verified even when allowlisted (got ${unverified.status} ${JSON.stringify(unverifiedBody)})`,
    );

    // Scenario 10 — D-02: a token minted for another resource server.
    await rotateMock({
      email: OWNER_EMAIL,
      sub: OWNER_SUB,
      emailVerified: true,
      audience: OTHER_AUDIENCE,
    });
    const wrongAudienceToken = await tokenFor();
    const wrongAudience = await fetch(`${API_BASE_URL}${API_V1}/users/me`, {
      headers: authorized(wrongAudienceToken),
    });
    const wrongAudienceBody = await readBody(wrongAudience);
    check(
      wrongAudience.status === 401 && wrongAudienceBody.detail?.reason === "invalid_token",
      `a token whose aud is "${OTHER_AUDIENCE}" is rejected with 401 invalid_token (got ${wrongAudience.status} ${JSON.stringify(wrongAudienceBody)})`,
    );

    // Back to a usable provider for the discovery and MCP scenarios.
    await rotateMock({ email: OWNER_EMAIL, sub: OWNER_SUB, emailVerified: true });
    const mcpToken = await tokenFor();

    // Scenario 11 — Protected Resource Metadata (RFC 9728), public.
    const prm = await fetch(`${API_BASE_URL}/.well-known/oauth-protected-resource`);
    const prmBody = await readBody(prm);
    check(
      prm.status === 200 &&
        prmBody.resource === `${API_BASE_URL}/mcp` &&
        Array.isArray(prmBody.authorization_servers) &&
        prmBody.authorization_servers[0] === MOCK_ISSUER_URL,
      `GET /.well-known/oauth-protected-resource announces resource and authorization server (got ${JSON.stringify(prmBody)})`,
    );
    const prmPath = await fetch(`${API_BASE_URL}/.well-known/oauth-protected-resource/mcp`);
    check(
      prmPath.status === 200,
      "GET /.well-known/oauth-protected-resource/mcp (path form) also responds",
    );

    // Scenario 12 — Authorization Server Metadata (RFC 8414), public.
    const asm = await fetch(`${API_BASE_URL}/.well-known/oauth-authorization-server`);
    const asmBody = await readBody(asm);
    check(
      asm.status === 200 &&
        typeof asmBody.authorization_endpoint === "string" &&
        asmBody.authorization_endpoint.startsWith(MOCK_ISSUER_URL) &&
        typeof asmBody.token_endpoint === "string",
      `GET /.well-known/oauth-authorization-server relays the provider's discovery (got ${asm.status})`,
    );

    // Scenario 13 — MCP enforces the same authorization, and the 401 points
    // MCP clients at the discovery metadata (WWW-Authenticate).
    const mcpNoAuth = await mcpRequest(null, {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "e2e", version: "0.0.0" },
      },
    });
    check(mcpNoAuth.status === 401, `POST /mcp without a token responds 401 (got ${mcpNoAuth.status})`);
    const wwwAuthenticate = mcpNoAuth.headers.get("www-authenticate") ?? "";
    check(
      wwwAuthenticate.startsWith("Bearer ") &&
        wwwAuthenticate.includes(
          `resource_metadata="${API_BASE_URL}/.well-known/oauth-protected-resource"`,
        ),
      `/mcp's 401 announces resource_metadata in WWW-Authenticate (got: ${wwwAuthenticate})`,
    );

    // Scenario 14 — authorized tools/list exposes only the whitelisted tool.
    const initResponse = await mcpRequest(mcpToken, {
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "e2e", version: "0.0.0" },
      },
    });
    const mcpSessionId = initResponse.headers.get("mcp-session-id");
    const initBody = await parseMcpResponse(initResponse);
    check(
      initResponse.status === 200 && Boolean(initBody.result?.serverInfo),
      `MCP initialize with a valid token responds 200 (got ${initResponse.status})`,
    );
    await mcpRequest(mcpToken, { jsonrpc: "2.0", method: "notifications/initialized" }, mcpSessionId);
    const toolsResponse = await mcpRequest(
      mcpToken,
      { jsonrpc: "2.0", id: 2, method: "tools/list" },
      mcpSessionId,
    );
    const toolsBody = await parseMcpResponse(toolsResponse);
    const toolNames = (toolsBody.result?.tools ?? []).map((tool) => tool.name);
    check(
      toolNames.length === 1 && toolNames[0] === "list_my_families",
      `tools/list exposes only list_my_families (got: ${JSON.stringify(toolNames)})`,
    );

    // Scenario 15 — allowlist removal revokes the next login (the token is
    // still cryptographically valid; authorization is what now denies it).
    removeAllowedEmail(env, OWNER_EMAIL);
    const revoked = await fetch(`${API_BASE_URL}/auth/verify`, {
      method: "POST",
      headers: authorized(mcpToken),
    });
    const revokedBody = await readBody(revoked);
    check(
      revoked.status === 403 && revokedBody.detail?.reason === "not_allowlisted",
      `an e-mail removed from the allowlist gets 403 not_allowlisted again (got ${revoked.status} ${JSON.stringify(revokedBody)})`,
    );
  } finally {
    // Reverse order of startup, stopping only what this script started.
    if (state.mock) {
      await state.mock.close().catch(() => {});
    }
    await killAndWait(api);
    await killAndWait(pg?.child);
  }

  if (failures > 0) {
    console.error(`\n${failures} scenario(s) failed.`);
    process.exit(1);
  }
  console.log("\nAll api-endpoints scenarios passed.");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
