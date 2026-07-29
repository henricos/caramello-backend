# Roadmap: Caramello

## Milestones

- ✅ **[v1.0 — Foundation](milestones/v1.0-ROADMAP.md)** — Async stack, Keycloak auth, domain-based structure, families domain, MCP, Docker, tests _(SHIPPED 2026-05-30 · 5 phases · 25 plans)_
- ✅ **[v2.0 — Financial Domain](milestones/v2.0-ROADMAP.md)** — Accounts, movements (CSV/OFX/XLSX), hierarchical categories, reconciliation, balances and analytical reports _(SHIPPED 2026-06-04 · 4 phases · 14 plans)_

Outside any milestone, after v2.0: alignment of the repository with the `ai-ready-project-template` template. It cut across both modules and the root, which is why this directory moved from `apps/api/.planning/` to the root. Among other things it replaced SQLModel with SQLAlchemy 2, versioned the business routes under `/api/v1`, adopted an e-mail allowlist with audience validation, created the `apps/web` module, and added the E2E suite at the root.

The files in `milestones/` are a historical record of what was delivered and are not updated retroactively: they describe the state at the closing of each milestone, not the current state.

---

## Backlog

| Item | Source | Priority |
|------|--------|-----------|
| FAMILY-04: reusable invitation code | M1 D-04 | High |
| FAMILY-05: join request via invitation | M1 D-04 | High |
| FAMILY-06: approval/rejection of requests | M1 D-04 | High |
| MCP-FIN: financial MCP tools (D-MCP-01) | M2 deferred | High |
| An E2E journey crossing the finances domain — today the root suite does not touch it, so nothing proves that its layers connect end to end. One representative journey is enough (create account, record movement, reconcile, check balance); the remaining rules stay covered by unit tests, per the pyramid in `docs/testing.md` | Template alignment | High |
| MCP UAT with a Bearer token from a real Keycloak (the E2E suite uses a mock provider, with real RS256) | M2 | Medium |
| OFX import with a real BR bank statement — the ISO-8859-1 fallback has never been exercised with an actual file | M2 Phase 8 | Medium |
| OPS-02: structured logging (structlog) | v2 backlog | Medium |
| OPS-03: SSL on DATABASE_URL in production | v2 backlog | Medium |
| Prevent an owner from removing themselves, and a single owner per family (rules in prd-core.md not yet implemented) | prd-core.md | Medium |
| Selecting and switching the "active family", and voluntary member departure (prd-core.md) | prd-core.md | Medium |

### Left the backlog

- **OPS-01: `GET /health` with a database ping** — delivered in the template alignment. The endpoint is public, unversioned, and reports `database` (via `SELECT 1`) and `data_dir`.
- **OPS-04: CI pipeline (GitHub Actions)** — decided against, for now. See "No CI for now" in `docs/architecture.md`: verification runs locally, conducted by the AI, and the release gate is each module's manual checklist. The only workflow that exists publishes the images to GHCR. This absence is not to be "fixed" before that discussion happens.
- **E2E UAT with real Keycloak + PostgreSQL** — replaced by the `e2e/` suite at the root, which provisions an ephemeral PostgreSQL and a mock OIDC provider signing with real RS256, exercising the same JWKS and signature path as production. What remains is the MCP item above.

---

> `PROJECT.md` and `STATE.md` were removed for being outdated to the point of being misleading: they described 85 tests where there are 142, Python 3.10+, SQLModel, `compose.yaml` inside the module and migrations up to 0004. They are files GSD regenerates from the code — `/gsd-onboard` or `/gsd-new-milestone` recreates them against the current reality. Their history is in git.
