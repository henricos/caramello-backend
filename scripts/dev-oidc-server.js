"use strict";

/**
 * Mock OIDC provider for MANUAL development — the same mechanism the E2E
 * scripts use (`e2e/lib/mock-oidc-server.js`), kept alive until Ctrl+C.
 *
 * There is no Keycloak in development (see `apps/api/docs/dev-setup.md` and
 * `apps/web/docs/dev-setup.md`): this provider approves the login instantly,
 * with no screen, while signing REAL RS256 tokens published on a real JWKS —
 * so the api validates them through exactly the code path production uses. It
 * is a stand-in for the identity provider, never a bypass of the api's own
 * authorization.
 *
 * The dependency is resolved from `e2e/node_modules`, installed on demand:
 * the E2E harness is the single place `oauth2-mock-server` is declared, and
 * the repository root deliberately has no package manifest of its own.
 *
 * Usage: node scripts/dev-oidc-server.js
 *   MOCK_OIDC_PORT      port (default 8790 — the value both modules'
 *                       `.env.development` already expects)
 *   MOCK_OIDC_EMAIL     e-mail of the logged-in identity (default
 *                       henricos@gmail.com, which the api's startup seed puts
 *                       on the allowlist automatically)
 *   MOCK_OIDC_NAME      display name (`name` claim)
 *   MOCK_OIDC_SUB       subject claim — the stable identity at the provider;
 *                       change it to simulate a different person
 *   MOCK_OIDC_AUDIENCE  audience injected into ACCESS tokens (default
 *                       caramello-api) — must match the api's
 *                       AUTH_OIDC_AUDIENCE, mirroring Keycloak's audience
 *                       mapper in production
 */

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const E2E_DIR = path.join(__dirname, "..", "e2e");
if (!fs.existsSync(path.join(E2E_DIR, "node_modules"))) {
  execFileSync("npm", ["install"], { cwd: E2E_DIR, stdio: "inherit" });
}

const { startMockOidc } = require(path.join(E2E_DIR, "lib", "mock-oidc-server.js"));

const PORT = Number(process.env.MOCK_OIDC_PORT || 8790);
const EMAIL = process.env.MOCK_OIDC_EMAIL || "henricos@gmail.com";
const NAME = process.env.MOCK_OIDC_NAME || "Henrico Scaranello";
const SUB = process.env.MOCK_OIDC_SUB || "dev-mock-sub";
const AUDIENCE = process.env.MOCK_OIDC_AUDIENCE || "caramello-api";

async function main() {
  const mock = await startMockOidc({
    port: PORT,
    email: EMAIL,
    emailVerified: true,
    name: NAME,
    sub: SUB,
    audience: AUDIENCE,
  });

  console.log(`Mock OIDC provider up: ${mock.issuerUrl}`);
  console.log(`Logins are approved as: ${NAME} <${EMAIL}> (sub: ${SUB})`);
  console.log(`Access token audience: ${AUDIENCE} (the api's AUTH_OIDC_AUDIENCE)`);
  console.log(`Set AUTH_OIDC_ISSUER=${mock.issuerUrl} for both apps/api and apps/web.`);
  console.log("Ctrl+C stops it.");

  process.on("SIGINT", async () => {
    console.log("\nStopping the mock OIDC provider...");
    await mock.close().catch(() => {});
    process.exit(0);
  });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
