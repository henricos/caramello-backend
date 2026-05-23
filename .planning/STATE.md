# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-23)

**Core value:** Um backend sólido, seguro e extensível onde cada novo domínio de negócio pode ser adicionado sem tocar no que já existe.
**Current focus:** Phase 1 — Infra Base

## Current Position

Phase: 1 of 5 (Infra Base)
Plan: 0 of ? in current phase
Status: Ready to plan
Last activity: 2026-05-23 — Roadmap M1 criado (5 fases, 27 requisitos mapeados)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:** N/A — nenhum plano executado ainda

## Accumulated Context

### Decisions

Decisões registradas em PROJECT.md Key Decisions table.

Decisões relevantes para a fase atual:
- Keycloak como provedor de auth (reverte Logto) — clients dev/prod já configurados na infra existente
- Migration Alembic inicial descartada e recriada — foi gerada com modelo errado (`hashed_password`, `google_id`)
- DB naming: `familia_dev` (dev) e `familia_prod` (prod)

### Pending Todos

Nenhum ainda.

### Blockers/Concerns

- Questão em aberto: confirmar realm name, audience claim e client ID do Keycloak antes de implementar `shared/auth.py` (Phase 3)
- Questão em aberto: subdomínio definitivo para API vs MCP (decide no Phase 5 deploy)

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-23
Stopped at: Roadmap criado — pronto para `/gsd-plan-phase 1`
Resume file: None
