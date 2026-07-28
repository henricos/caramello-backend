# caramello-web

![version](https://img.shields.io/badge/version-2.0.0-blue)

Mobile-first web interface for Caramello, the family platform for schedule, finances, shopping lists, health and entertainment. A server-rendered Next.js application that drives the OAuth2/OIDC login (Keycloak in production, a local mock in development), keeps the tokens only in the encrypted session cookie and consumes `apps/api` server-side.

## Documentation

- [`docs/dev-setup.md`](docs/dev-setup.md) — prerequisites, installation and how to run in development
- [`docs/architecture.md`](docs/architecture.md) — module structure and relevant decisions
- [`docs/release.md`](docs/release.md) — release checklist and how to run the image
- [`AGENTS.md`](AGENTS.md) — code standards and invariants, for AI agents
