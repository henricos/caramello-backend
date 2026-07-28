# Caramello

Personal and family platform that centralizes the administrative side of family life — schedule, finances, shopping lists, health and entertainment. Built for a closed group of 1 to 5 people (the members of a household), with authentication through Keycloak and access from web and mobile clients as well as AI agents.

The product is delivered in pt-BR; the repository is written in English. See "Language" in [`AGENTS.md`](AGENTS.md).

---

## Modules

| Module | Description |
|--------|-------------|
| [`apps/api`](apps/api/README.md) | Python/FastAPI backend — hybrid REST + MCP, the data model and all business rules |
| [`apps/web`](apps/web/README.md) | Next.js frontend — the mobile-first interface for the family group |

---

## Cross-cutting documentation

- [`docs/architecture.md`](docs/architecture.md) — system overview, data flow and cross-cutting decisions
- [`docs/monorepo.md`](docs/monorepo.md) — organization, work scope, per-module documentation and dependency policy
- [`docs/testing.md`](docs/testing.md) — AI-driven test strategy and the autonomous E2E/UAT flow
- [`docs/skill-conventions.md`](docs/skill-conventions.md) — conventions for authoring project skills

## Getting started

Each module is self-contained and documents its own setup:

- [`apps/api/docs/dev-setup.md`](apps/api/docs/dev-setup.md)
- [`apps/web/docs/dev-setup.md`](apps/web/docs/dev-setup.md)

Development requires no installed PostgreSQL and no Keycloak: both modules run against self-contained ephemeral services. Configuration comes from a committed `.env.development` per module — see "Configuration and environment variables" in [`AGENTS.md`](AGENTS.md).
