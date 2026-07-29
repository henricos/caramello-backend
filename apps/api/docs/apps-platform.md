# Personal Platform — Context, Decisions and Architecture

---

## Overview

A set of independent personal web applications, running on a self-hosted server via Docker with public DNS. The current goal is experimentation and incremental evolution, with future convergence into logical groupings by usage domain. Usage volume is small (1 to 5 users). Performance is not a priority; simplicity, flexibility, maintainability and gradual evolution are.

---

## 1. Universe of Applications

Estimated total: **10 to 15 applications**, organized into three groups with distinct architecture and convergence profiles.

### Group A — Family
- Family management applications: budget, shopping list, family appointments and similar.
- Users: a closed, known set (the family members).
- Cohesive domain — the features benefit from data shared among themselves.
- **Defined destination:** a single monolithic backend with APIs organized by business domain. A single frontend, mobile-first, growing gradually as new features are added to the menu. Packaged as a mobile app via Capacitor.

### Group B — Work
- Professional productivity applications: activity management, presentation generation, team feedback records, knowledge base, studies and similar.
- Users: predominantly a single user, with the door open for eventual sharing with a second user in the future.
- **UX requirement:** visual context isolation — interfaces for distinct subjects must not be mixed on the same screen, not least because some of these interfaces are used in day-to-day professional work.
- **Desired navigation model:** Google-style switching (Gmail/YouTube) — shared SSO with a shortcut menu between the applications, but each one opens its own clean, contextually isolated interface.
- **Defined destination:** separate APIs per application, each with an independent repository and deploy cycle.
- **Open:** which applications will be grouped or will remain separate — a business decision not yet made, with no immediate technical impact.

### Group C — Other
- Applications with no connection to each other and no shared domain. The name "Personal" was revised to "Other" because it better reflects the heterogeneous nature of the group.
- Single user in all of them — exclusively the developer.
- **Defined destination:** applications fully independent of each other, with no navigation integration and no shared database.

---

## 2. Identity and Authentication

### Defined requirements
- SSO within each group.
- Social login via OAuth2 / Google.
- Access control by e-mail (only certain addresses may register).
- Support for MFA and password recovery.
- Future support for multiple real users (today each application uses a fixed/configured user).
- Adoption of open standards such as JWT to ease interoperability with frameworks, testing tools and AI agents.

### Defined preferences
- Use an **off-the-shelf solution**, not one built from scratch — no reinventing the wheel.
- Avoid over-engineering.

### Decision
**Keycloak**, with **tenants isolated per group** (in Keycloak terms, one realm per group).

Keycloak covers all the requirements (OAuth2/Google, MFA, OIDC, standard JWT, admin GUI, e-mail allowlist) and is already running in the existing infrastructure with dev/prod clients configured, which removes the need to introduce and operate an additional identity service.

> **Decision history:** the original choice recorded in this document was **Logto**, selected for its smaller footprint compared to Authentik (which consumes ~375MB on the server alone plus ~360MB on the worker at idle) and for being designed to reduce the complexity of small to medium setups; Keycloak had been assessed as too heavy for the size of the project. That decision was **reverted** in favor of Keycloak, because it was already provisioned in the infrastructure with dev/prod clients configured. The authentication model this settled on is recorded in the root `docs/architecture.md`.

The Keycloak instance is single and shared as an infrastructure service, but each group operates in its own isolated tenant:

| Group | Tenant | Users |
|---|---|---|
| Family | `tenant-familia` | Family members |
| Work | `tenant-trabalho` | Single user, door open for a second |
| Other | `tenant-outros` | Single user |

This separation by tenant is the **only** form of sharing between the groups. Data, backends and databases are completely independent of each other — there is no cross-group data infrastructure.

---

## 3. Backend Architecture

### Current situation
- Monolithic backends per application (frontend and backend in the same repository and Docker container).
- Current complexity is small — refactoring is not a technical blocker.

### Defined requirements and intentions
- Separate the frontend and the backend of each application.
- The backend must be designed to survive the future unification of the frontends — it is the longest-lived asset.
- APIs reusable across applications of the same group are desirable.
- Part of the functionality will have to be exposed to AI agents via MCP — which pushes for well-defined APIs and a clear separation between interface and business logic.

### Decision per group

**Family Group — a single monolithic backend, Python + FastAPI.**

A single backend repository with APIs organized internally by business domain. The cohesion of the family domain and the fact that the features share data justify the monolith — there is nothing to gain from separation here.

```
familia-backend/
├── app/
│   ├── main.py
│   ├── domains/
│   │   ├── orcamento/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── services.py
│   │   │   └── routes.py
│   │   ├── lista_compras/
│   │   │   └── ...
│   │   └── compromissos/
│   │       └── ...
│   └── shared/
│       └── auth.py       # JWT validation + upsert of the local user
├── migrations/           # Alembic, all the group's tables
├── Dockerfile
└── docker-compose.yml
```

**Work Group — separate APIs per application, Python + FastAPI.**

Each application has its own repository, Docker container and independent deploy cycle. No update in one application affects or requires intervention in the others.

```
trabalho-atividades/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── services.py
│   └── auth.py           # JWT validation + upsert of the local user
├── migrations/
├── Dockerfile
└── docker-compose.yml
```

**Other Group — separate APIs per application, Python + FastAPI.**

Same structure as the Work Group. Each application is completely autonomous.

---

In all groups, FastAPI is the backend framework for the same reasons: it generates the OpenAPI spec automatically (making future exposure via MCP easier with no rework), it is lightweight, and it has the best Python ecosystem for LLM integration on the market.

The separation between `services.py` and the routes is not an aesthetic detail — it is what will allow reusing the logic both via the REST API and via MCP in the future, without rewriting code.

---

## 4. Frontend Architecture

### Decision per group

**Family Group:** React with Capacitor for mobile packaging. A single frontend repository that aggregates all of the group's features, with new features being added gradually to the menu. Mobile-first from the start.

**Work Group:** each application keeps its own independent frontend. The switching menu is implemented as **simple links with SSO** — a lightweight navigation component injected into the header of each app, with icons/shortcuts to the others. Since SSO via Keycloak is cross-cutting within the group, the user will already be authenticated when navigating between the applications, with no need for micro-frontends or a more complex architecture.

**Other Group:** no navigation integration. Each application is completely autonomous.

---

## 5. Persistence and Database

### Current situation
- Persistence mostly file-based for simplicity.
- PostgreSQL is already running on the server, currently used only by third-party applications.

### Defined requirements and intentions
- Migrating from file-based to a relational database is necessary and inevitable.
- Preference for migrating straight to the final, definitive model, taking advantage of the mandatory refactoring to avoid future rework.
- Each application must be able to evolve and deploy independently, updating only its own tables.
- There is a need for a safe space for experimentation, separate from the production environment.

### Decision
**One PostgreSQL server, two databases per group (`prod` and `dev`), no explicit schemas, no data infrastructure shared between groups.**

| Database | Purpose |
|---|---|
| `caramello` | Production of the Family Group |
| `caramello_dev` | Development and integration tests (rollback per test) |
| `trabalho_prod` | Production of the Work Group |
| `trabalho_dev` | Development of the Work Group |
| `outros_prod` | Production of the Other Group |
| `outros_dev` | Development of the Other Group |

Within each database, no PostgreSQL schemas are used — isolation is done by table naming convention (prefix per domain, e.g. `orcamento_lancamentos`, `lista_itens`). This is sufficient given that there is no real risk of conflict between distinct business domains within the same group.

Each application manages its own migrations via **Alembic** and operates exclusively on its own tables — completely independent deploys, with no risk of regression between applications.

---

## 6. User Model per Group — Decoupling Decision

This is one of the most relevant architectural decisions of the project, since it eliminates the only point of coupling that existed between groups in the previous version of the architecture.

### The problem that was discarded

An earlier version of this architecture considered a `users` table shared across all applications, managed by a dedicated infrastructure repository called `plataforma-core`. That model was discarded because it created coupling between groups that have completely distinct profiles, users and domains — complexity with no real benefit for this project's context.

### The decision: each group is a complete island

Each group has its own users, its own `users` table, and neither knows nor depends on the users of any other group. Keycloak is the only link between the groups — and only as an authentication infrastructure service, not as shared data.

### How it works in each group

**Family Group**

The `users` table lives in the `caramello` database, managed by the migrations of the group's monolithic backend. It records the family members who authenticated through Keycloak's `tenant-familia` tenant.

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idp_sub    TEXT NOT NULL UNIQUE,  -- "sub" of the JWT issued by Keycloak
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

All of the group's domain tables reference `users.id` with a foreign key. The user record is created automatically on first access via **just-in-time provisioning** — with no separate registration flow.

**Work Group**

Each application in the group has its own `users` table in its own database. Since the group has predominantly a single user, in practice this table will have a single record — but the structure is identical to the Family Group's, keeping the pattern and leaving the door open for an eventual second user with no architectural change at all.

Independence here is total: there is no table shared between the applications of the group, nor between the group and the others. Each application manages its own `users` via its own migrations.

**Other Group**

Same structure as the Work Group. Each application has its local `users` table with a single record. The use of Keycloak is not motivated by robust security, but by **interoperability by convention**: the JWT issued by Keycloak is a standard recognized by middlewares, frameworks, testing tools and AI agents — with no need to explain or customize the authentication mechanism in each application.

### What `plataforma-core` would be and why it was discarded

In the previous architecture, `plataforma-core` would be a repository dedicated to managing the migration of the shared `users` table, creating an execution-order dependency across all groups. Its existence introduced three problems:

**Implicit deploy coupling** — any new environment would need to run `plataforma-core` before any other application, creating an operational dependency invisible to anyone unfamiliar with the architecture.

**False economy** — each group's `users` table has distinct user profiles, fields and semantics. Forcing a single shared table would mean creating an overly generic table or adding columns that only make sense for some groups.

**Violation of the island principle** — groups with completely independent domains should not share any data at all. The only legitimate sharing is the authentication service (Keycloak), not the user data itself.

The decision to eliminate `plataforma-core` simplifies the operational model without giving up any real requirement of the project.

### Summary of the user model

| Group | `users` table | Owner of the migrations | Expected users |
|---|---|---|---|
| Family | `caramello.users` | The group's monolithic backend | Family members |
| Work (per app) | `trabalho_prod.users` | Each application individually | 1, door open for 2 |
| Other (per app) | `outros_prod.users` | Each application individually | 1 (single user) |

---

## 7. Integration with AI and MCP

### Defined requirements and intentions
- Part of the functionality will have to be exposed to AI agents.
- Intention to add an MCP layer on top of the existing APIs.
- This pushes for: well-defined APIs, a clear separation between interface and business logic, and a backend with a good ecosystem for LLM integration.

### Architectural position
The choice of FastAPI solves a good part of this requirement automatically: the OpenAPI spec generated by the framework is the direct input for building MCP servers. Keeping the logic separated in `services.py` ensures that future MCP endpoints are thin wrappers over already existing and tested code — with no duplication of business logic.

The standard JWT issued by Keycloak also contributes here: AI agents that know the OIDC/JWT standard are able to authenticate and operate on the APIs with no special configuration.

There is nothing to build right now beyond maintaining this architectural discipline from the start.

---

## 8. Constraints and Assumptions

- Personal and family use.
- 1 to 5 simultaneous users — no need for scale.
- Microservices for scale make no sense in this context.
- Priorities: operational simplicity, maintainability, gradual evolution without rework, freedom to experiment, preparation for AI and MCP, avoiding over-engineering.

---

## 9. Decision Table

| Question | Decision |
|---|---|
| Identity provider | **Keycloak** — already provisioned in the infrastructure, covers OAuth2/Google + MFA + standard JWT (reverted the original Logto decision) |
| Tenant model | **One tenant per group** — Family, Work and Other isolated |
| Backend language | **Python** |
| Backend framework | **FastAPI** — automatic OpenAPI, AI/LLM ecosystem, lightweight |
| Family Group backend | **A single monolith** — the cohesive domain justifies the monolith |
| Work Group backend | **Separate APIs per application** — independent deploy by design |
| Other Group backend | **Separate APIs per application** — applications with no connection to each other |
| Database | **One PostgreSQL server, two databases per group** (`prod` and `dev`) |
| PostgreSQL schemas | **No** — isolation by table naming is sufficient |
| Migrations | **Alembic** per application/monolith, operating only on its own tables |
| `users` table | **Local per application/group** — no sharing between groups |
| `plataforma-core` | **Discarded** — coupling with no real benefit for this context |
| Work Group switching menu | **Simple links with SSO** via a shared navigation component |
| Other Group authentication | **Keycloak** — for JWT interoperability, not out of a need for robust security |

---

## 10. Questions Still Open

1. **Work Group:** which applications will be grouped or will remain separate — a pending business decision, with no immediate technical impact.

---

## 11. Suggested Implementation Sequence

The infrastructure foundation comes first, before any application:

1. Bring up PostgreSQL with each group's databases (`caramello`, `caramello_dev`, `trabalho_prod`, `trabalho_dev`, `outros_prod`, `outros_dev`)
2. Install and configure Keycloak with the three tenants (`tenant-familia`, `tenant-trabalho`, `tenant-outros`)
3. Configure OAuth2/Google, MFA and the e-mail allowlist in each tenant
4. Define and document the base backend template (FastAPI + Alembic + standard folder structure)
5. Implement the Family Group first — the monolith is the most representative case for validating the whole foundation in practice
6. From there, each new application of the other groups follows the template and integrates the corresponding Keycloak tenant from the start
