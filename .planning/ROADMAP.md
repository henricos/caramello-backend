# Roadmap: Caramello API

## Milestones

- ✅ **[v1.0 — Fundação](milestones/v1.0-ROADMAP.md)** — Stack async, auth Keycloak, estrutura por domínios, domínio families, MCP, Docker, testes _(SHIPPED 2026-05-30 · 5 phases · 25 plans)_

---

## Milestone 2: Domínio Financeiro

> _A ser planejado via `/gsd-new-milestone`_

**Fases previstas (esboço):**
- Domínio `finances` — categorias, transações, saldos
- FAMILY-04/05/06 — fluxo de convite reutilizável (deferido do M1)
- OPS-01/02 — health endpoint + logging estruturado

---

## Backlog

| Item | Origem | Prioridade |
|------|--------|-----------|
| FAMILY-04: código de convite reutilizável | M1 D-04 | Alta |
| FAMILY-05: solicitação de entrada via convite | M1 D-04 | Alta |
| FAMILY-06: aprovação/rejeição de solicitações | M1 D-04 | Alta |
| OPS-01: GET /health com ping ao banco | v2 backlog | Média |
| OPS-02: logging estruturado (structlog) | v2 backlog | Média |
| OPS-03: SSL no DATABASE_URL em produção | v2 backlog | Média |
| OPS-04: CI pipeline (GitHub Actions) | v2 backlog | Baixa |
| MCP-03: ferramentas MCP de escrita | v2 backlog | Baixa |
