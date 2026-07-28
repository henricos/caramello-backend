# Monorepo Conventions

This document defines the conventions for organization, documentation, AI context and cross-module coordination in this repository.

The central guideline is: this repository is a monorepo, but each module must be treated as a well-delimited technical unit — with operational autonomy over dependencies, commands, tests and documentation. The root provides integrated vision, coordination and cross-cutting context; it must not turn distinct modules into a single project without boundaries.

---

## 1. General principles

1. The repository root coordinates the whole; each module runs, tests, validates and documents its own part.
2. The monorepo should ease integration, not create unnecessary coupling.
3. Dependencies belong in the module that uses them.
4. Changes that cross modules must update the related contracts, tests and documentation.
5. AI agents must identify the affected module before acting and respect the scope of the folder they are working in.
6. Avoid changing multiple modules without need; when unavoidable, explain the reason for the coordinated change.
7. Do not move responsibilities between modules without an architectural justification.
8. General documentation (rules, conventions and decisions) must never be duplicated: it lives in a single place and other documents only reference it. Operational procedures (release, setup) are exempt from this rule: it is important that each module has its own, self-contained and runnable end to end, even if similar to another module's.

---

## 2. Module structure and organization

The monorepo may contain modules in different technologies. Each module must keep its own configuration files, dependencies, tests and commands.

Naming may vary per project, but the conceptual separation must be preserved:

- `apps/`: runnable applications — services, APIs, workers, interfaces.
- `packages/` or `libs/`: libraries, contracts, schemas or shared artifacts.
- `docs/`: cross-cutting documentation for the monorepo.
- `scripts/`: auxiliary automation, when needed.
- `e2e/`: end-to-end scripts covering the running system, regardless of how many modules a journey crosses.

Rules:

1. Module-specific lint, test and build configuration must live close to the module.
2. Global configuration should only exist when it is genuinely cross-cutting.
3. A module must not depend on another module's internal structure; when needed, use explicit contracts.

---

## 3. Work scope

The repository can be opened in two ways, depending on the activity:

**Entire repository**

Use when the activity involves cross-module integration, contract changes, architectural changes, CI/CD, cross-cutting documentation or coordinated refactorings.

**Specific module**

Use when the activity is restricted to a single module. This mode reduces noise for indexers, extensions and AI agents, and is the preferred mode for focused work.

---

## 4. Documentation

The root `docs/` contains only cross-cutting documentation. Module-specific details live in each module's own `docs/`.

Each module follows a fixed three-file scheme:

| File | Audience | Contains |
|------|----------|----------|
| `README.md` | humans | what the module is + version badge + pointer to `docs/` — nothing else |
| `docs/` | humans and agents | the module's own documentation — `dev-setup.md`, `release.md`, `architecture.md`; non-obvious decisions are recorded in the "Relevant decisions" section of `architecture.md`, never in a parallel ADR log |
| `AGENTS.md` | AI agents | code standards, invariants and caveats — no stack, no commands |

There is deliberately no `docs/decisions/` directory and no ADR log. Cross-cutting decisions go in the root `docs/architecture.md`; module-local ones in that module's `architecture.md`.

Documents that carry **product knowledge** rather than technical convention (vision, functional requirements, platform-level decisions) live in the owning module's `docs/` alongside the technical files and are exempt from the three-file scheme — they are inputs to the product, not descriptions of the stack.

---

## 5. Dependencies

Dependency manifests (`pyproject.toml`, `package.json`) pin **major and minor** and let **only the patch float** — `~=X.Y.Z` in Python, `~X.Y.Z` in npm. The goal is twofold: no unintended breakage just because a new version came out (minor and major never come in on their own) and security fixes at the patch level keep flowing in.

Rules:

1. The lockfile (`uv.lock`, `package-lock.json`) is versioned and is the source of exact build reproducibility.
2. Bumping minor or major is always a deliberate act: edit the manifest, run the tests and commit the change together with the lockfile.
3. Pre-releases are the exception and are pinned exactly (e.g. `next-auth 5.0.0-beta.31`), because between pre-releases there is no compatibility guarantee nor reliable semver.

---

## 6. Recommended folder structure

```text
repo/
  README.md
  AGENTS.md
  compose.example.yaml

  docs/
    monorepo.md
    architecture.md
    testing.md
    skill-conventions.md

  e2e/

  apps/
    api/
      README.md
      AGENTS.md
      .env.development
      docs/
        dev-setup.md
        release.md
        architecture.md
      src/
    web/
      README.md
      AGENTS.md
      .env.development
      docs/
        dev-setup.md
        release.md
        architecture.md
      src/
```
