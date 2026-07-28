# AI-driven tests

The AI fully owns the tests: it writes and updates the scripts as functionality is implemented, and runs the scripts when verifying or conducting UAT. It only delegates to the operator when automation is impossible (SSO with MFA, external hardware).

---

## 1. Test types and when to use each

| Type | What it covers | Where it lives | When to run |
|------|----------------|----------------|-------------|
| Unit | Isolated functions and components | the module's `tests/` or `src/` | When changing the internal logic of a unit |
| Module integration | Internal flows of one module against real dependencies | the module's `tests/` | When changing internal flows or contracts |
| E2E / UAT | Complete user journeys through the interface or the API | `e2e/` at the repository root | When verifying functionality or conducting UAT |

**UAT is always E2E** — it exercises the running system end to end. Never substitute unit tests for UAT.

E2E scripts live in `e2e/` at the repository root, never inside a module, regardless of how many modules the journey crosses. Single-module scripts stay in that module's `tests/`.

---

## 2. Autonomous UAT flow

### Step 0 — check for already running services

Before any setup, check whether the required services are already responding at the URLs documented in each module's `docs/dev-setup.md`.

If they all respond, skip straight to Step 3. Do not start services unnecessarily.

### Step 1 — prepare the environment (only if services must be started)

Each module ships a committed `.env.development` (see "Configuration and environment variables" in `AGENTS.md`), so there is nothing to create or copy. Two things to verify instead:

- Any variable that uses `${VAR}` indirection needs the corresponding **user-level** variable exported in the shell — those are credentials of real external services and are never stored in the repository. If one is missing, the api fails loudly at boot naming the variable.
- Never overwrite `.env.development` to work around a failure. It is versioned; a local edit to it is a change to the repository, not a test fixture. The exception is the embedded Postgres DSN lines, which are expected to differ per machine.

### Step 2 — start the services (only if needed)

Start in the background as documented in each module's `docs/dev-setup.md`. Wait for startup via health check before proceeding.

### Step 3 — run the E2E scripts

E2E scripts accept base URLs via environment variables with defaults pointing at localhost. Pass the variables on the command line when the defaults do not fit.

Each script provisions its own ephemeral dependencies (an embedded Postgres instance and a mock OIDC provider on dedicated ports), so scripts never collide with each other or with a running dev instance.

### Step 4 — stop the services (only those started in this session)

If you started the services in Step 2, stop them when finished. Never stop processes that were already running before the UAT.

---

## 3. Playwright

The `playwright` CLI is a global environment prerequisite, installed outside this repository and deliberately absent from every module's manifest. Use it directly — not via `npx`.

```bash
playwright screenshot --browser chromium http://localhost:3000 /tmp/page.png
```

The Playwright **library** used by the E2E scripts is declared in `e2e/package.json` and installed by the scripts themselves on first run.

Screenshots go to `/tmp/` — discarded when the session ends, used for inline diagnosis.

---

## 4. Test scripts

When implementing or changing functionality, create or update the corresponding scripts.

Each script in `e2e/` must:

- be self-contained and independently runnable
- list the covered scenarios in a comment at the top
- take base URLs from environment variables with localhost defaults, never hardcoded
- tear down in reverse order of startup, in a `finally` block, stopping only what it started

```
e2e/
  lib/                  shared harness, mock OIDC provider, login helpers
  walking-skeleton.js   the full stack end to end
  auth-flows.js         authentication and access-control flows
  api-endpoints.js      API contract without a browser
```

---

*Stack-agnostic — applicable to any monorepo following this pattern.*
