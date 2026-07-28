# Context and Guidelines for AI Agents

## Context and references

Before deciding on conventions, flows or rules, check `docs/`. What is documented there is normative: it prevails over assumptions and must be followed. If a decision changes something already documented, update the corresponding document.

For general orientation:

- `README.md` — high-level view for humans; points to `docs/` when something needs detail.
- `docs/` — architectural and technical decisions and cross-cutting procedures of the project.
- `docs/monorepo.md` — structure, per-module documentation and work scope. Normative; consult it before deciding where something belongs.

## Tool-agnostic AI strategy

This project adopts a tool-agnostic strategy to support multiple AIs without duplicating instructions.

**Editable sources of truth:**

- `AGENTS.md` — operational rules common to any agent.
- `.agents/skills/` — the project's skills.

Compatibility files such as `CLAUDE.md` and tool-specific directories are only pointers to those sources of truth. Never edit the pointers directly when the intent is to change rules or skills.

**How each tool loads the instructions and the skills:**

- **Claude Code** — loads the rules through `CLAUDE.md`, which includes `@AGENTS.md` and must not be edited; skills via `.claude/skills`, which points to `.agents/skills`.
- **Cursor** — reads `AGENTS.md` as its native instructions file; skills via `.cursor/skills`, which points to `.agents/skills`.
- **Codex CLI / other tools** — read `AGENTS.md` directly; skills from `.agents/skills`.

## Project skills

Project skills follow specific conventions for frontmatter, file structure and authoring. Whenever you create or edit a skill, consult `docs/skill-conventions.md` before finalizing.

## Language

The repository is written entirely in **English**: code, comments, configuration, documentation (`README.md`, `docs/`), commit messages, skills, and operator-facing runtime output (logs, `echo` messages, CLI errors, validation errors, test output).

The **product** is multilanguage, and the implemented locale is **pt-BR**. Every string rendered to the end user (UI labels, page texts, user-facing error messages, reference data displayed in the product) lives in the i18n message catalog of the owning module — never hardcoded in components or business logic. Concretely:

- The api returns machine-readable codes (e.g. `not_allowlisted`); human-readable text is resolved at the presentation layer.
- When creating or changing user-facing text, add or update the key in the module's pt-BR catalog (see each module's `docs/architecture.md` for the mechanism). Adding a string directly in a component is a policy violation, even as a temporary step.

**Sample data is pt-BR.** Example and fixture *data values* (URLs, hostnames, e-mail addresses, paths and other placeholder values in docs, configs and tests) follow the product locale, not the repository language: `https://exemplo.com`, `keycloak.exemplo.com`, `pessoa@exemplo.com` or a `/painel` test path are correct and must not be "fixed" into English. The English-only rule applies to prose and code (comments, messages, identifiers of the codebase itself), never to data.

**Domain vocabulary stays in pt-BR when it is an accounting concept with no faithful English equivalent.** `competencia_year` / `competencia_month` (the accounting period an entry belongs to, distinct from the movement date) and `is_recorrente` are deliberate: translating them would lose precision that the product's users depend on. The same applies to the `Account.type` enum values (`corrente`, `poupanca`, `cartao`, `investimento`) — these are data, not prose.

Chat communication with the operator follows the operator's language (pt-BR).

In pt-BR text for humans (product strings, chat), avoid overusing the em dash ("—") to interleave asides mid-sentence; prefer commas or parentheses, as a pt-BR copywriter normally would. This is not a ban: the em dash remains correct in dialogue, titles and occasional emphasis; the problem is repetitive, unidiomatic use. In Markdown lists and bullets, use a hyphen ("-").

## Monorepo

This repository is a monorepo — each module (`apps/*`) is an autonomous unit. Before acting, identify the right module and work inside it; use the root only for what is genuinely cross-cutting. Full conventions for structure, per-module documentation and work scope are in `docs/monorepo.md` — it is normative, consult it before deciding where something should live.

**Module naming:**

| Context | Correct name |
|---------|--------------|
| The project as a whole (monorepo, platform) | `caramello` |
| Backend module — Python project name and container image | `caramello-api` |
| Frontend module — app name and npm package | `caramello-web` |

## Configuration and environment variables

The repository never ships a `.env.example`, and no module reads a dotenv file on its own initiative.

- **Production** receives environment variables directly from the orchestrator (compose), never from a file in the repository.
- **Development** uses a single `.env.development` per module, **committed on purpose** (excepted from the blanket `.env*` rule in `.gitignore`).

Only two kinds of value may live in `.env.development`, both safe to commit:

1. **Throwaway local dev values** — meaningless outside the developer's machine, because dev services are self-contained and ephemeral (the embedded Postgres DSN, the local mock OIDC issuer).
2. **Indirection to variables the developer already exports elsewhere** (shell profile, `direnv`, a secret manager) for anything genuinely sensitive, such as credentials of real external services: `SOME_KEY=${SOME_KEY}`. The raw secret value is never written into the committed file.

Consequences that must be respected:

- The api's `Settings` deliberately sets **no `env_file`**: it reads only the real process environment and fails loudly when a required variable is missing. Whatever launches the server is responsible for populating the environment — in dev, `set -a && source .env.development && set +a`. Because a shell resolves the file, `${VAR:-fallback}` indirection is available there.
- The web module's `.env.development` **is** loaded automatically by `next dev`/`next start` (Next.js's own convention). Its loader is not a shell, so only plain `${VAR}` indirection is allowed there — never `${VAR:-default}`. Defaults for the web belong in its typed env validator, not in the file.

Each module's `docs/dev-setup.md` explains this mechanism, and the header comment of each `.env.development` restates it in place.

## Tests

The AI writes, maintains and runs all tests. When implementing or changing functionality, create or update the corresponding scripts. When verifying functionality or conducting UAT, run the scripts and report the results. See `docs/testing.md`.

**All functional verification is E2E** — scripts in `e2e/` at the repository root, against the running system. Unit tests are not UAT.

## Commits

- Messages always in **English**.
- **Conventional Commits** format: `type: concise subject` (subject up to ~72 characters).
- Valid types: `feat`, `fix`, `docs`, `refactor`, `chore`.
- Subject and body in the imperative mood, describing what the commit does: `add`, `fix`, `update`, `remove`, `refactor`, `document`.
- Body required, with a short paragraph summarizing the goal of the change and a bullet list describing the changes made.
- Before running `git push`, present the proposal and wait for explicit operator approval.
- Use explicit files in `git add`; never broad staging like `git add .`.
- If there are files unrelated to the task outside staging, ask the operator what to do. Never mention pending files in the commit message.
- **NEVER** add AI authorship or attribution trailers (e.g. `Co-Authored-By`, as Claude Code inserts by default), regardless of the tool in use.
- `git push` may be blocked by the tool's sandbox. If that happens, run the push outside the sandbox — do not delegate it to the operator because of a network failure.
