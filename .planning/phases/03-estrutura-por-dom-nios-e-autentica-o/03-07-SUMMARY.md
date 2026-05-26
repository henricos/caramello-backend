---
plan: "03-07"
phase: 03-estrutura-por-dom-nios-e-autentica-o
status: deferred
tasks_completed: 1
tasks_total: 2
deferred_by: operator
deferred_reason: "Operador em viagem — infra Keycloak + PostgreSQL indisponível. Retomar quando infra acessível."
completed: 2026-05-26
---

# Summary — Plano 03-07: E2E Smoke Test (Gap 2)

## Status: Parcialmente executado — Task 2 diferida pelo operador

O operador declarou não ter acesso à infraestrutura real (Keycloak + PostgreSQL) no momento
da execução. A Task 2 (checklist E2E + EVIDENCE.md) foi diferida por decisão explícita do
operador.

## Tasks

| Task | Status | Commit | Detalhe |
|------|--------|--------|---------|
| Task 1: Criar scripts/smoke_e2e.py | ✅ Completa | `4794b4b` | Script lint-clean com 6 funções: check_unauthenticated, check_authenticated_get_me, check_idempotent_jit, check_crud_requires_auth, inspect_token_audience, main |
| Task 2: Operador executa checklist E2E | ⏸ Diferida | — | Requer Keycloak real + PostgreSQL familia_dev — diferida por operador em viagem |

## O que foi entregue

### scripts/smoke_e2e.py

Script Python autocontido que, dado `SMOKE_TOKEN` (token Keycloak) e app rodando em
`localhost:8000`, executa e reporta PASS/FAIL para:

- **AUTH-01** — `GET /user/me` sem token → 401/403
- **AUTH-01 D-11** — endpoints CRUD sem token rejeitam (`/user/`, `/family/`, `/family_invitation/`)
- **USER-01** — `GET /user/me` com Bearer token → 200 + campos `uuid`, `email`, `name`
- **AUTH-02** — duas chamadas com mesmo token retornam mesmo `uuid` (idempotência JIT)
- **D-02** — inspeção do claim `aud` com recomendação sobre `verify_aud`

### Task 2 (diferida) — Checklist E2E para retomada futura

Quando a infra estiver disponível, retomar executando:

```bash
# Pré-requisitos: .env preenchido, PostgreSQL acessível, Keycloak acessível
bin/setup_db
bin/manage_db upgrade

# Terminal 1 (manter rodando)
uv run uvicorn caramello.main:app --reload --port 8000

# Terminal 2
export SMOKE_TOKEN="<token via password grant ou Impersonate>"
uv run python scripts/smoke_e2e.py

# Criar .planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-07-EVIDENCE.md
# Commitar com: docs(03-07): registra evidências E2E da Phase 3 — Gap 2
```

Após preenchimento do EVIDENCE.md e commit, rodAr `/gsd-verify-work 3` para fechar Gap 2
em `03-VERIFICATION.md` e marcar AUTH-02 e USER-01 como SATISFIED.

## Gap 2 status

**Status atual:** Aberto (diferido por operador)
**Impacto:** Nenhum no desenvolvimento — código de auth está correto e verificado por
testes unitários/mocked. A verificação E2E com Keycloak real é evidência complementar,
não pré-requisito para Phase 4.

## Self-Check

- ✅ Task 1 executada e commitada
- ✅ SUMMARY.md criado documentando decisão e caminho de retomada
- ⏸ Task 2 diferida por decisão do operador (não é falha técnica)
- ✅ Sem modificações em STATE.md ou ROADMAP.md (incumbência do orquestrador)
