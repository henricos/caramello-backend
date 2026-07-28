"use strict";

/**
 * Infrastructure shared by the E2E scripts: brings each script's isolated
 * stack up/down (ephemeral pgembed Postgres, `apps/api` via uvicorn,
 * `apps/web` via `next dev`), runs migrations and administers the allowlist.
 *
 * Long-lived processes use the directly installed binaries
 * (`.venv/bin/uvicorn`, `.venv/bin/python`, `node_modules/.bin/next`), never
 * `uv run`/`npm run` — wrappers create a real subprocess that killing the
 * parent process does not reliably reach, which would leave an orphan api,
 * `next dev` or Postgres behind after the script exits. Short-lived commands
 * (`alembic`, the allowlist scripts) still go through `uv run`, which
 * `execFileSync` waits for synchronously, so there is nothing to kill.
 *
 * Nothing here reads `apps/api/.env.development` or `apps/web/.env.development`
 * for the api: every variable is passed explicitly, so an E2E run can never
 * be steered at the developer's own `caramello_dev` database by a stale line
 * in a committed dotenv file. `next dev` does load its own
 * `.env.development`, but every variable that matters is overridden in the
 * spawned environment, which wins.
 */

const path = require("path");
const { spawn, execFileSync } = require("child_process");

const ROOT_DIR = path.join(__dirname, "..", "..");
const API_DIR = path.join(ROOT_DIR, "apps", "api");
const WEB_DIR = path.join(ROOT_DIR, "apps", "web");
const API_VENV_BIN = path.join(API_DIR, ".venv", "bin");
const WEB_NEXT_BIN = path.join(WEB_DIR, "node_modules", ".bin", "next");

// pgembed downloads/initializes a real PostgreSQL cluster on the first run of
// a fresh data directory (`initdb`), which is by far the slowest step here.
const DATABASE_URL_TIMEOUT_MS = 180000;
const MIGRATION_TIMEOUT_MS = 120000;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitUntil(predicateFn, timeoutMs, description) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const result = await predicateFn();
    if (result) {
      return result;
    }
    await sleep(300);
  }
  throw new Error(`Timeout waiting for ${description}`);
}

/**
 * Waits until `url` answers anything at all.
 *
 * `child` is optional and purely diagnostic: when the wait times out, the
 * process's captured output is embedded in the error, which turns "Timeout
 * waiting for apps/web to respond" into the actual reason — a missing
 * environment variable, a port already taken, or Next.js refusing to start a
 * second dev server from the same directory (see `spawnWeb`).
 */
async function waitForHttpStatus(url, timeoutMs, description, child) {
  try {
    await waitUntil(
      async () => {
        try {
          const response = await fetch(url);
          return response.status > 0;
        } catch {
          return false;
        }
      },
      timeoutMs,
      description,
    );
  } catch (error) {
    if (!child) {
      throw error;
    }
    throw new Error(
      `${error.message}\n--- stdout ---\n${child.output.stdout}\n--- stderr ---\n${child.output.stderr}`,
    );
  }
}

/**
 * Spawns a long-lived process accumulating stdout/stderr into buffers for
 * diagnosis in case the process dies unexpectedly or an assertion fails.
 *
 * `detached: true` puts the child in its own process group, which is what
 * makes `killAndWait` able to reach any grandchild it may have spawned.
 */
function spawnLongLived(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  child.output = { stdout: "", stderr: "" };
  child.stdout.on("data", (chunk) => {
    child.output.stdout += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    child.output.stderr += chunk.toString();
  });
  return child;
}

function killBoth(pid, signal) {
  try {
    process.kill(pid, signal);
  } catch {
    // Process no longer exists — nothing to do.
  }
  try {
    process.kill(-pid, signal);
  } catch {
    // Group no longer exists — nothing to do.
  }
}

function killAndWait(child, timeoutMs = 15000) {
  return new Promise((resolve) => {
    if (!child || child.exitCode !== null || child.signalCode !== null) {
      resolve();
      return;
    }
    let settled = false;
    const finish = () => {
      if (!settled) {
        settled = true;
        clearTimeout(forceKillTimer);
        resolve();
      }
    };
    child.once("exit", finish);
    const forceKillTimer = setTimeout(() => {
      killBoth(child.pid, "SIGKILL");
      finish();
    }, timeoutMs);
    killBoth(child.pid, "SIGTERM");
  });
}

/**
 * Starts the ephemeral Postgres (pgembed) and resolves with
 * `{ child, databaseUrl }` as soon as the `DATABASE_URL=...` line shows up
 * on stdout.
 *
 * The server itself (`apps/api/scripts/e2e_ephemeral_server.py`) uses a temp
 * data directory and the `caramello_e2e` database, so it can never touch the
 * developer's persistent `caramello_dev`, and it binds a unix socket rather
 * than a TCP port, so concurrent runs cannot collide.
 */
async function startEphemeralPostgres() {
  const child = spawnLongLived(
    path.join(API_VENV_BIN, "python"),
    ["scripts/e2e_ephemeral_server.py"],
    { cwd: API_DIR },
  );

  const databaseUrl = await waitUntil(
    () => {
      const match = child.output.stdout.match(/DATABASE_URL=(\S+)/);
      return match ? match[1] : null;
    },
    DATABASE_URL_TIMEOUT_MS,
    `"DATABASE_URL=" in the output of e2e_ephemeral_server.py\nstdout: ${child.output.stdout}\nstderr: ${child.output.stderr}`,
  );

  return { child, databaseUrl };
}

/**
 * The environment `apps/api` needs. `core/config.py` requires
 * `DATABASE_URL`, `AUTH_OIDC_ISSUER` and `AUTH_OIDC_AUDIENCE` even for tasks
 * that never talk to the provider (migrations, seeds), and reads ONLY the
 * process environment — no dotenv is loaded. The api is a pure resource
 * server: it takes the issuer and its own expected audience, never a client
 * id/secret.
 */
function apiEnv({ databaseUrl, issuerUrl, audience, extra = {} }) {
  return {
    ...process.env,
    DATABASE_URL: databaseUrl,
    AUTH_OIDC_ISSUER: issuerUrl,
    AUTH_OIDC_AUDIENCE: audience,
    ...extra,
  };
}

function runMigrations(env) {
  try {
    execFileSync("uv", ["run", "alembic", "upgrade", "head"], {
      cwd: API_DIR,
      env,
      encoding: "utf8",
      timeout: MIGRATION_TIMEOUT_MS,
    });
  } catch (error) {
    throw new Error(`"uv run alembic upgrade head" failed: ${error.stderr || error.message}`);
  }
}

function seedAllowedEmail(env, email) {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "scripts/seed_allowed_email.py",
      "--database-url",
      env.DATABASE_URL,
      "--email",
      email,
    ],
    { cwd: API_DIR, env, encoding: "utf8" },
  );
}

function removeAllowedEmail(env, email) {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "scripts/remove_allowed_email.py",
      "--database-url",
      env.DATABASE_URL,
      "--email",
      email,
    ],
    { cwd: API_DIR, env, encoding: "utf8" },
  );
}

function spawnApi({ env, port }) {
  return spawnLongLived(
    path.join(API_VENV_BIN, "uvicorn"),
    ["caramello_api.main:app", "--port", String(port)],
    {
      cwd: API_DIR,
      // `GET /health` checks that DATA_DIR is a reachable directory, and the
      // repository's own `data/` is not what an E2E run should write near.
      env: { ...env, DATA_DIR: env.DATA_DIR || "/tmp" },
    },
  );
}

/**
 * Starts `apps/web` with `next dev`.
 *
 * IMPORTANT — a platform constraint, not a gap in this harness: Next.js 16
 * allows only ONE `next dev` server per project directory. A second one exits
 * with "Another next dev server is already running", naming the first one's
 * PID, EVEN on a different port, because the lock lives in the shared
 * `apps/web/.next/` directory rather than on the port. The two browser-driven
 * scripts (`walking-skeleton.js` and `auth-flows.js`) therefore cannot run at
 * the same time as each other; they can each run alongside `api-endpoints.js`,
 * which starts no web at all. Pass the returned child to
 * `waitForHttpStatus(..., child)` so the collision is reported instead of
 * surfacing as an opaque timeout.
 */
function spawnWeb({ env, port }) {
  return spawnLongLived(WEB_NEXT_BIN, ["dev", "-p", String(port)], {
    cwd: WEB_DIR,
    env: { ...env, PORT: String(port) },
  });
}

module.exports = {
  API_DIR,
  WEB_DIR,
  assert,
  sleep,
  waitUntil,
  waitForHttpStatus,
  spawnLongLived,
  killAndWait,
  startEphemeralPostgres,
  apiEnv,
  runMigrations,
  seedAllowedEmail,
  removeAllowedEmail,
  spawnApi,
  spawnWeb,
};
