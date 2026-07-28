---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Domínio Financeiro
status: archived
last_updated: 2026-06-04T14:00:00.000Z
last_activity: 2026-06-04 -- Milestone v2.0 fechado formalmente
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 14
  completed_plans: 14
  percent: 100
stopped_at: Milestone v2.0 arquivado — próximo passo /gsd-new-milestone
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-04)

**Core value:** Um backend sólido, seguro e extensível onde cada novo domínio de negócio pode ser adicionado sem tocar no que já existe.
**Current focus:** Between milestones — M2 archived, M3 not yet defined

## Current Position

Status: Between milestones
Last milestone: v2.0 — Domínio Financeiro (SHIPPED 2026-06-04)
Next step: `/gsd-new-milestone` para iniciar o planejamento do M3

> **Em andamento (fora de milestone):** alinhamento do repositório com o template
> `ai-ready-project-template`. O escopo atravessa os dois módulos e a raiz — por
> isso este diretório `.planning/` foi movido de `apps/api/.planning/` para a raiz
> do repositório. Os arquivos em `milestones/` permanecem inalterados: são as
> únicas definições sobreviventes dos IDs de requisito (`FAMILY-01`, `ACC-01`,
> `MOV-03`, `LAN-02`, `REL-04`, …) referenciados por comentários no código e pelo
> roadmap.

## M1 Reference (SHIPPED 2026-05-30)

- 5 phases, 25 plans
- Stack async: FastAPI + asyncpg + AsyncSession + Alembic async
- Auth: Keycloak JWT, JWKS cache, JIT provisioning, auto-join por email
- Domínios: users + families (6 endpoints negócio + pré-registro por email)
- MCP: `/mcp` com `list_my_families` e whitelist
- Docker: Dockerfile multi-stage non-root + compose.yaml
- Testes: 36 unitários + 4 integração stub

## M2 Reference (SHIPPED 2026-06-04)

- 4 phases, 14 plans, 125 commits, 98 arquivos alterados
- Domínio `finances`: 25 endpoints de negócio
- Account/Category/Subcategory CRUD scoped por família
- Movimentações: registro individual + importação CSV/OFX/XLSX com SHA-256 dedup
- Conciliação 1:1 Movement→FinancialEntry + suggest_category via rapidfuzz
- Saldos por conta/família + breakdown mensal e por membro
- DSL estendido: Decimal, filters→Index, expose_as_uuid, operations sync
- Testes: 85 unitários + 4 integração stub
- Migrations: 0001–0004

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| E2E Testing | Verificação E2E com Keycloak real + banco PostgreSQL | Pendente UAT | M1 |
| E2E Testing | UAT com banco real do domínio finances | Pendente UAT | M2 |
| Convites | FAMILY-04/05/06 — fluxo de convite reutilizável | Backlog M3 | M1 D-04 |
| MCP Finances | D-MCP-01: ferramentas MCP financeiras | Backlog M3 | M2 Phase 9 |
| OFX encoding | Testar com extrato real de banco BR | Backlog M3 | M2 Phase 8 |

## Session Continuity

Last session: 2026-06-04
Stopped at: Milestone v2.0 fechado
Resume: `/gsd-new-milestone` para planejar M3
