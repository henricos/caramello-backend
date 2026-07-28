"use strict";

/**
 * E2E — walking skeleton: the full stack (ephemeral pgembed Postgres +
 * apps/api + apps/web + mock OIDC provider) exercised through the user's
 * normal browser journey, from login to the home page with data coming from
 * the database.
 *
 * Fail-fast on purpose (`assert`, not a failure counter): if the skeleton is
 * broken there is nothing useful left to measure, and the first broken step is
 * the diagnosis.
 *
 * Covered scenarios:
 *   1. The api's GET /health is public and responds 200.
 *   2. Visiting the home page without a session redirects into the OIDC login
 *      flow.
 *   3. An accepted login (allowlisted e-mail, email_verified=true) lands on
 *      the app home at the base path — never on /auth/error.
 *   4. The home page shows the logged-in e-mail, which proves
 *      GET /api/v1/users/me works end to end (web → api → Postgres, with the
 *      access token read server-side from the encrypted cookie).
 *   5. The home page renders the families section fed by
 *      GET /api/v1/families/families, and reports no "API indisponível".
 *   6. GET <basePath>/api/auth/session never exposes raw tokens (verified by
 *      the login helper at runtime, on every run).
 *   7. The web's GET <basePath>/health is public and responds 200 — the
 *      compose healthcheck contract.
 *
 * Environment variables (defaults isolated from any dev instance and from the
 * other E2E scripts):
 *   WEB_E2E_PORT     default 3100
 *   API_E2E_PORT     default 8100
 *   MOCK_OIDC_PORT   default 8791
 *
 * Concurrency: this script runs happily alongside `api-endpoints.js` (which
 * starts no web). It CANNOT run at the same time as `auth-flows.js`: Next.js
 * 16 permits a single `next dev` per project directory regardless of port —
 * see the note on `spawnWeb` in `lib/harness.js`.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

if (!fs.existsSync(path.join(__dirname, "node_modules"))) {
  execFileSync("npm", ["install"], { cwd: __dirname, stdio: "inherit" });
}

const { chromium } = require("playwright");
const { startMockOidc } = require("./lib/mock-oidc-server");
const { loginViaMockOidc } = require("./lib/login");
const {
  assert,
  waitForHttpStatus,
  waitUntil,
  killAndWait,
  startEphemeralPostgres,
  apiEnv,
  runMigrations,
  seedAllowedEmail,
  spawnApi,
  spawnWeb,
} = require("./lib/harness");

const WEB_PORT = Number(process.env.WEB_E2E_PORT || 3100);
const API_PORT = Number(process.env.API_E2E_PORT || 8100);
const MOCK_OIDC_PORT = Number(process.env.MOCK_OIDC_PORT || 8791);

// The same base path production uses: base-path bugs must show up here, never
// only inside the container.
const APP_BASE_PATH = process.env.APP_BASE_PATH || "/caramello";

const WEB_BASE_URL = `http://localhost:${WEB_PORT}`;
const WEB_APP_URL = `${WEB_BASE_URL}${APP_BASE_PATH}`;
const API_BASE_URL = `http://localhost:${API_PORT}`;
const MOCK_ISSUER_URL = `http://localhost:${MOCK_OIDC_PORT}`;

const OIDC_CLIENT_ID = "e2e-walking-skeleton-client";
const OIDC_CLIENT_SECRET = "e2e-walking-skeleton-secret";
// The api's own audience: the mock injects it into access tokens the same way
// Keycloak's audience mapper does in production.
const OIDC_AUDIENCE = "e2e-caramello-api";
const AUTH_SECRET = crypto.randomBytes(33).toString("base64");

// `exemplo.com.br`, not a reserved `.test`/`.example` domain: the api's
// `UserRead.email` is a pydantic `EmailStr`, which rejects special-use TLDs,
// so a `.test` address would serialize into a 500 on GET /api/v1/users/me.
const TEST_EMAIL = "caminhante.e2e@exemplo.com.br";
const TEST_NAME = "Caminhante E2E";
const TEST_SUB = "e2e-sub-caminhante";

async function run() {
  let pg = null;
  let api = null;
  let web = null;
  let mock = null;
  let browser = null;

  try {
    console.log("Starting ephemeral Postgres (pgembed)...");
    pg = await startEphemeralPostgres();

    mock = await startMockOidc({
      port: MOCK_OIDC_PORT,
      email: TEST_EMAIL,
      name: TEST_NAME,
      sub: TEST_SUB,
      emailVerified: true,
      audience: OIDC_AUDIENCE,
    });

    const env = apiEnv({
      databaseUrl: pg.databaseUrl,
      issuerUrl: MOCK_ISSUER_URL,
      audience: OIDC_AUDIENCE,
    });

    runMigrations(env);
    seedAllowedEmail(env, TEST_EMAIL);

    console.log("Starting apps/api...");
    api = spawnApi({ env, port: API_PORT });
    await waitForHttpStatus(`${API_BASE_URL}/health`, 60000, "apps/api to respond", api);

    console.log("Starting apps/web (next dev)...");
    web = spawnWeb({
      env: {
        ...process.env,
        AUTH_SECRET,
        APP_BASE_PATH,
        AUTH_TRUST_HOST: "true",
        AUTH_OIDC_ISSUER: MOCK_ISSUER_URL,
        AUTH_OIDC_CLIENT_ID: OIDC_CLIENT_ID,
        AUTH_OIDC_CLIENT_SECRET: OIDC_CLIENT_SECRET,
        API_URL: API_BASE_URL,
      },
      port: WEB_PORT,
    });
    await waitForHttpStatus(`${WEB_APP_URL}/health`, 120000, "apps/web to respond", web);

    // Scenario 1 — the api's public health probe.
    const health = await fetch(`${API_BASE_URL}/health`);
    assert(health.status === 200, `GET /health should respond 200, responded ${health.status}`);
    console.log("  ok: the api's GET /health responds 200 without authentication");

    // Scenario 7 — the web's public health probe (compose healthcheck).
    const webHealth = await fetch(`${WEB_APP_URL}/health`);
    const webHealthBody = await webHealth.json();
    assert(
      webHealth.status === 200 && webHealthBody.status === "ok",
      `The web's GET ${APP_BASE_PATH}/health should respond 200 {"status":"ok"}, responded ${webHealth.status} ${JSON.stringify(webHealthBody)}`,
    );
    console.log("  ok: the web's GET /health is public and responds 200");

    // Scenario 2 (part one) — an anonymous visitor is bounced to the login by
    // proxy.ts, before any page renders.
    const anonymous = await fetch(WEB_APP_URL, { redirect: "manual" });
    const anonymousLocation = anonymous.headers.get("location") ?? "";
    assert(
      anonymous.status >= 300 &&
        anonymous.status < 400 &&
        anonymousLocation.includes(`${APP_BASE_PATH}/api/auth/signin`),
      `An anonymous visit to ${APP_BASE_PATH} should redirect to the login, got ${anonymous.status} -> ${anonymousLocation}`,
    );
    console.log("  ok: an anonymous visitor is redirected to the login");

    browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();

    // Scenario 2 (part two) and 3 — the browser walks the whole chain
    // (proxy.ts → /api/auth/signin → provider /authorize → callback →
    // POST /auth/verify → home). Scenario 6 is checked inside the helper.
    await loginViaMockOidc(page, { webBaseUrl: WEB_APP_URL });
    const finalUrl = new URL(page.url());
    assert(
      finalUrl.pathname === APP_BASE_PATH,
      `An accepted login should land on the home page (${APP_BASE_PATH}), landed at ${page.url()}`,
    );
    console.log("  ok: an accepted OIDC login lands on the app home");

    // Scenario 4 — the home page shows the logged-in e-mail, which it can only
    // know through GET /api/v1/users/me.
    await waitUntil(
      async () => (await page.textContent("body"))?.includes(TEST_EMAIL),
      15000,
      "the home page to render the logged-in user's e-mail",
    );
    console.log("  ok: the home page shows the logged-in e-mail (GET /api/v1/users/me)");

    // Scenario 5 — the families section rendered from
    // GET /api/v1/families/families. The literals are the pt-BR UI copy from
    // apps/web/messages/pt-BR.json, so they must stay in the UI's language.
    const bodyText = (await page.textContent("body")) ?? "";
    assert(
      !bodyText.includes("API indisponível"),
      `The home page reported the api as unavailable: ${bodyText}`,
    );
    assert(
      bodyText.includes("Suas famílias"),
      `The home page should render the families section ("Suas famílias"): ${bodyText}`,
    );
    assert(
      bodyText.includes("Você ainda não participa de nenhuma família."),
      `A brand-new user should see the empty-families message: ${bodyText}`,
    );
    console.log("  ok: the home page renders the families section from the api");

    await context.close();
  } finally {
    // Reverse order of startup, stopping only what this script started.
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (mock) {
      await mock.close().catch(() => {});
    }
    await killAndWait(web);
    await killAndWait(api);
    await killAndWait(pg?.child);
  }

  console.log("\nWalking skeleton complete: login → web → api → database working.");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
