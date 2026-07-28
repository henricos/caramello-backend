"use strict";

/**
 * E2E — authentication and access-control flows, against a fully isolated
 * instance of apps/api + apps/web (ephemeral pgembed Postgres, dedicated
 * ports) and a real fake OIDC provider — never a real Keycloak (there is no
 * development Keycloak, by design).
 *
 * Collect-all on purpose (a failure counter, not `assert`): each scenario is
 * an independent access-control rule, and knowing that three of five broke is
 * worth more than stopping at the first.
 *
 * Covered scenarios:
 *   A. Accepted login — allowlisted e-mail + email_verified=true lands on the
 *      app home, never on /auth/error.
 *   B. Allowlist denied — an e-mail authenticated at the provider but outside
 *      the allowlist lands on /auth/error?reason=not_allowlisted with the
 *      generic access-denied copy, which never contains the address.
 *   C. email_verified=false — an e-mail ALREADY on the allowlist but
 *      unverified lands on /auth/error?reason=email_not_verified with a
 *      message DISTINCT from scenario B's.
 *   D. Backend-enforced protection — GET /api/v1/users/me without
 *      Authorization or with a malformed token responds 401; GET /health stays
 *      public. The proxy is a UX optimization; the api is the guarantee.
 *   E. proxy.ts uses segment boundaries in PUBLIC_PATHS — /api/auth-evil,
 *      which only shares the textual prefix of the public /api/auth, does NOT
 *      inherit the exemption and is redirected to the login.
 *
 * Architecture: apps/web and apps/api start ONCE with a fixed
 * AUTH_OIDC_ISSUER; each scenario tears the mock provider down and starts
 * another on the SAME port with different claims (and therefore a new RS256
 * kid) — the api (JWKS refresh on an unknown kid) and Auth.js absorb the
 * rotation without either module restarting.
 *
 * Environment variables (defaults isolated from any dev instance and from the
 * other E2E scripts):
 *   WEB_E2E_PORT     default 3200
 *   API_E2E_PORT     default 8200
 *   MOCK_OIDC_PORT   default 8792
 *
 * Concurrency: this script runs happily alongside `api-endpoints.js` (which
 * starts no web). It CANNOT run at the same time as `walking-skeleton.js`:
 * Next.js 16 permits a single `next dev` per project directory regardless of
 * port — see the note on `spawnWeb` in `lib/harness.js`.
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
  sleep,
  waitForHttpStatus,
  killAndWait,
  startEphemeralPostgres,
  apiEnv,
  runMigrations,
  seedAllowedEmail,
  spawnApi,
  spawnWeb,
} = require("./lib/harness");

const WEB_PORT = Number(process.env.WEB_E2E_PORT || 3200);
const API_PORT = Number(process.env.API_E2E_PORT || 8200);
const MOCK_OIDC_PORT = Number(process.env.MOCK_OIDC_PORT || 8792);

// The same base path production uses: base-path bugs must show up here, never
// only inside the container.
const APP_BASE_PATH = process.env.APP_BASE_PATH || "/caramello";

const WEB_BASE_URL = `http://localhost:${WEB_PORT}`;
const WEB_APP_URL = `${WEB_BASE_URL}${APP_BASE_PATH}`;
const API_BASE_URL = `http://localhost:${API_PORT}`;
const MOCK_ISSUER_URL = `http://localhost:${MOCK_OIDC_PORT}`;

const API_V1 = "/api/v1";

const OIDC_CLIENT_ID = "e2e-auth-flows-client";
const OIDC_CLIENT_SECRET = "e2e-auth-flows-secret";
// The api's own audience: the mock injects it into access tokens the same way
// Keycloak's audience mapper does in production.
const OIDC_AUDIENCE = "e2e-caramello-api";
const AUTH_SECRET = crypto.randomBytes(33).toString("base64");

// `exemplo.com.br`, not a reserved `.test`/`.example` domain — the api's
// `UserRead.email` is a pydantic `EmailStr`, which rejects special-use TLDs.
const ALLOWED_EMAIL = "liberada.e2e@exemplo.com.br";
const DENIED_EMAIL = "negada.e2e@exemplo.com.br";
const UNVERIFIED_EMAIL = "naoverificada.e2e@exemplo.com.br";

// Distinct `sub` per identity: oauth2-mock-server hardcodes `sub: "johndoe"`,
// and the api keys users on `idp_sub`.
const ALLOWED_SUB = "e2e-sub-liberada";
const DENIED_SUB = "e2e-sub-negada";
const UNVERIFIED_SUB = "e2e-sub-naoverificada";

// pt-BR copy rendered by apps/web — the literals below MUST match
// apps/web/messages/pt-BR.json, because that is the language the UI speaks.
const COPY_NOT_ALLOWLISTED_TITLE = "Acesso não autorizado";
const COPY_NOT_ALLOWLISTED_BODY =
  "Sua conta não está liberada para usar o Caramello. Peça a quem administra o sistema para liberar o seu e-mail.";
const COPY_EMAIL_NOT_VERIFIED_TITLE = "E-mail não verificado";
const COPY_EMAIL_NOT_VERIFIED_BODY =
  "Seu e-mail ainda não foi verificado no provedor de login. Confirme o e-mail e tente entrar de novo.";

async function run() {
  let pg = null;
  let api = null;
  let web = null;
  let browser = null;
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

  const rotateMock = async ({ email, sub, emailVerified }) => {
    if (state.mock) {
      await state.mock.close().catch(() => {});
      state.mock = null;
      await sleep(200);
    }
    state.mock = await startMockOidc({
      port: MOCK_OIDC_PORT,
      email,
      sub,
      emailVerified,
      audience: OIDC_AUDIENCE,
    });
    return state.mock;
  };

  try {
    console.log("Starting ephemeral Postgres (pgembed)...");
    pg = await startEphemeralPostgres();

    const env = apiEnv({
      databaseUrl: pg.databaseUrl,
      issuerUrl: MOCK_ISSUER_URL,
      audience: OIDC_AUDIENCE,
    });

    runMigrations(env);
    seedAllowedEmail(env, ALLOWED_EMAIL);
    // Deliberately allowlisted: scenario C must fail on `email_verified`
    // ALONE, proving the two denials are independent checks.
    seedAllowedEmail(env, UNVERIFIED_EMAIL);

    await rotateMock({ email: ALLOWED_EMAIL, sub: ALLOWED_SUB, emailVerified: true });

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

    browser = await chromium.launch();

    // Scenario A — accepted login.
    {
      const context = await browser.newContext();
      const page = await context.newPage();
      await loginViaMockOidc(page, { webBaseUrl: WEB_APP_URL });
      const url = new URL(page.url());
      check(
        url.origin === WEB_BASE_URL && url.pathname === APP_BASE_PATH,
        `an accepted login lands on the app home ${APP_BASE_PATH} (landed at ${page.url()})`,
      );
      await context.close();
    }

    // Scenario B — authenticated at the provider, outside the allowlist.
    await rotateMock({ email: DENIED_EMAIL, sub: DENIED_SUB, emailVerified: true });
    {
      const context = await browser.newContext();
      const page = await context.newPage();
      await loginViaMockOidc(page, { webBaseUrl: WEB_APP_URL });
      const url = new URL(page.url());
      check(
        url.pathname === `${APP_BASE_PATH}/auth/error` &&
          url.searchParams.get("reason") === "not_allowlisted",
        `a login outside the allowlist lands on /auth/error?reason=not_allowlisted (landed at ${page.url()})`,
      );
      const bodyText = (await page.textContent("body")) ?? "";
      check(
        bodyText.includes(COPY_NOT_ALLOWLISTED_TITLE) &&
          bodyText.includes(COPY_NOT_ALLOWLISTED_BODY),
        "the error page renders the generic access-denied copy",
      );
      check(
        !bodyText.includes(DENIED_EMAIL) && !page.url().includes(DENIED_EMAIL),
        "neither the page nor the URL ever exposes the rejected e-mail address",
      );
      await context.close();
    }

    // Scenario C — allowlisted but email_verified=false.
    await rotateMock({ email: UNVERIFIED_EMAIL, sub: UNVERIFIED_SUB, emailVerified: false });
    {
      const context = await browser.newContext();
      const page = await context.newPage();
      await loginViaMockOidc(page, { webBaseUrl: WEB_APP_URL });
      const url = new URL(page.url());
      check(
        url.pathname === `${APP_BASE_PATH}/auth/error` &&
          url.searchParams.get("reason") === "email_not_verified",
        `email_verified=false lands on /auth/error?reason=email_not_verified (landed at ${page.url()})`,
      );
      const bodyText = (await page.textContent("body")) ?? "";
      check(
        bodyText.includes(COPY_EMAIL_NOT_VERIFIED_TITLE) &&
          bodyText.includes(COPY_EMAIL_NOT_VERIFIED_BODY) &&
          !bodyText.includes(COPY_NOT_ALLOWLISTED_TITLE) &&
          !bodyText.includes(COPY_NOT_ALLOWLISTED_BODY),
        "the unverified-e-mail message is DISTINCT from the allowlist one",
      );
      await context.close();
    }

    // Scenario D — the api enforces protection on its own, regardless of the
    // proxy in front of it.
    {
      const noToken = await fetch(`${API_BASE_URL}${API_V1}/users/me`);
      check(
        noToken.status === 401,
        `GET ${API_V1}/users/me without Authorization responds 401 (got ${noToken.status})`,
      );
      const badToken = await fetch(`${API_BASE_URL}${API_V1}/users/me`, {
        headers: { Authorization: "Bearer token-invalido" },
      });
      check(
        badToken.status === 401,
        `GET ${API_V1}/users/me with a malformed token responds 401 (got ${badToken.status})`,
      );
      const health = await fetch(`${API_BASE_URL}/health`);
      check(health.status === 200, `GET /health stays public (got ${health.status})`);
    }

    // Scenario E — segment boundary in proxy.ts's PUBLIC_PATHS.
    {
      const evil = await fetch(`${WEB_APP_URL}/api/auth-evil`, { redirect: "manual" });
      const location = evil.headers.get("location") ?? "";
      check(
        evil.status >= 300 &&
          evil.status < 400 &&
          location.includes(`${APP_BASE_PATH}/api/auth/signin`),
        `${APP_BASE_PATH}/api/auth-evil is redirected to the login instead of being treated as public (status ${evil.status}, location ${location})`,
      );
    }
  } finally {
    // Reverse order of startup, stopping only what this script started.
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (state.mock) {
      await state.mock.close().catch(() => {});
    }
    await killAndWait(web);
    await killAndWait(api);
    await killAndWait(pg?.child);
  }

  if (failures > 0) {
    console.error(`\n${failures} scenario(s) failed.`);
    process.exit(1);
  }
  console.log("\nAll auth-flows scenarios passed.");
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
