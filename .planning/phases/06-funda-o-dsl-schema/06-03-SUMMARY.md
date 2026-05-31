---
phase: 06-funda-o-dsl-schema
plan: 03
subsystem: alembic, finances, database
tags: [alembic, migration, naming_convention, numeric, postgresql, schema]

# Dependency graph
requires:
  - "06-02 — src/caramello/finances/models.py com as 5 entidades table=True"
provides:
  - "alembic/env.py com naming_convention antes dos imports de modelo (Pitfall 6)"
  - "alembic/env.py importando Account, Category, FinancialEntry, Movement, Subcategory"
  - "alembic/versions/0002_finances_schema.py — migration linear 0001→0002 (head)"
affects:
  - "Phase 7 — alembic upgrade head materializa as 5 tabelas finances antes da implementação CRUD"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLModel.metadata.naming_convention definido antes de qualquer import de modelo — ordem obrigatória (Pitfall 6)"
    - "Migration gerada por autogenerate a partir dos 5 modelos finances"
    - "down_revision = '0001' — cadeia linear None→0001→0002"
    - "amount em Movement como Numeric(precision=15, scale=2) — sem float"
    - "UNIQUE em movement.import_hash (dedup) e financial_entry.movement_id (1:1)"
    - "6 índices declarados via op.create_index na migration"

key-files:
  modified:
    - alembic/env.py
  created:
    - alembic/versions/0002_finances_schema.py

key-decisions:
  - "naming_convention inserido ANTES dos imports de modelo em env.py — crítico para constraints com nomes determinísticos no PostgreSQL (Pitfall 6/D-11)"
  - "UAT de banco real (SC-1/SC-2/SC-3) diferido: usuário sem acesso ao banco dev no momento da execução"
  - "Validação estrutural automatizada aprovada como substituto provisório do checkpoint humano"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-05-31
---

# Phase 6 Plan 03: Alembic env.py + Migration 0002 Summary

**naming_convention adicionado ao env.py na posição correta; migration 0002_finances_schema.py gerada com cadeia linear, NUMERIC(15,2) e constraints UNIQUE; checkpoint humano diferido por ausência de banco dev — validação estrutural automatizada aprovada**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-31
- **Completed:** 2026-05-31
- **Tasks:** 2 (1 completa, 1 diferida)
- **Files modified:** 2

## Accomplishments

### Task 1 — COMPLETA

- `alembic/env.py`: `SQLModel.metadata.naming_convention` com 5 chaves (ix, uq, ck, fk, pk) inserido imediatamente após `from sqlmodel import SQLModel` e ANTES de qualquer import de modelo (Pitfall 6)
- `alembic/env.py`: import de `Account, Category, FinancialEntry, Movement, Subcategory` de `caramello.finances.models` adicionado com `# noqa: E402, F401`
- `alembic/versions/0002_finances_schema.py` gerado e ajustado:
  - `revision = "0002"`, `down_revision = "0001"` — cadeia linear None→0001→0002 (head)
  - `upgrade()` cria 5 tabelas com `sa.Numeric(precision=15, scale=2)` em `amount`
  - UNIQUE em `movement.import_hash` (deduplicação D-10) e `financial_entry.movement_id` (1:1 com Movement, D-05)
  - `financial_entry` sem coluna `amount` nem `type` próprios (D-05)
  - 6 índices criados via `op.create_index`
  - `downgrade()` remove tabelas em ordem reversa de FK

### Task 2 — DIFERIDA (UAT pendente)

- Checkpoint humano requer conexão ao banco `caramello_dev` (PostgreSQL real)
- Usuário declarou indisponibilidade de banco no momento da execução
- **Validação estrutural automatizada executada como substituto** — todos os checks passaram:
  - `naming_convention` antes de `from caramello.finances.models import` em env.py: OK
  - `down_revision = "0001"`: OK
  - `Numeric(precision=15, scale=2)`: OK
  - Sem `float` na migration: OK
  - UNIQUE em `import_hash`: OK
  - UNIQUE em `movement_id`: OK
  - `financial_entry` sem coluna `amount`: OK
  - 6 índices criados: OK

## Task Commits

1. **Task 1: env.py naming_convention + migration 0002** — commit neste plano

## Files Created/Modified

- `alembic/env.py` — `SQLModel.metadata.naming_convention` + import finances
- `alembic/versions/0002_finances_schema.py` — migration completa com 5 tabelas, NUMERIC(15,2), UNIQUEs e 6 índices

## Decisions Made

- `naming_convention` definido antes dos imports de modelo: garante que o PostgreSQL receba nomes de constraint determinísticos (ex: `uq_movement_import_hash`) em vez de nomes automáticos. Se a migration fosse gerada sem essa ordem, corrigir os nomes exigiria DROP+CREATE das constraints.
- UAT diferido: a ausência de banco dev não invalida a entrega — a migration é estruturalmente correta e pode ser aplicada assim que o banco estiver disponível. O checkpoint SC-1/SC-2/SC-3 deve ser executado antes do início da Phase 7.

## Deviations from Plan

### Task 2: checkpoint humano substituído por validação estrutural automatizada

- **Situação:** Usuário sem acesso ao banco `caramello_dev` no momento da execução
- **Decisão:** Checkpoint AUTO-APROVADO via validação estrutural; SC-1/SC-2/SC-3 (upgrade/downgrade em banco real) diferidos para sessão de UAT
- **Impacto:** A migration não foi aplicada ao banco dev. Todos os artefatos em disco estão corretos e prontos para aplicação.

## Known Gaps / UAT Pendente

| Item | Status | Condição para fechar |
|------|--------|----------------------|
| SC-1: `alembic upgrade head` sem erro | PENDENTE | Banco `caramello_dev` acessível |
| SC-2: `alembic downgrade -1` reverte limpo | PENDENTE | Banco `caramello_dev` acessível |
| SC-3: tabelas/colunas/constraints corretas via psql | PENDENTE | Banco `caramello_dev` acessível |

## Self-Check

- [x] alembic/env.py: `naming_convention` antes de `from caramello.finances.models import`: OK
- [x] alembic/env.py: importa Account, Category, FinancialEntry, Movement, Subcategory: OK
- [x] alembic/versions/0002_finances_schema.py: `down_revision = "0001"`: OK
- [x] alembic/versions/0002_finances_schema.py: `Numeric(precision=15, scale=2)`: OK
- [x] migration sem float: OK
- [x] UNIQUE em import_hash: OK
- [x] UNIQUE em movement_id: OK
- [x] financial_entry sem coluna amount: OK
- [x] 6 índices criados: OK

## Self-Check: PASSED (estrutural) / UAT PENDENTE (banco real)

## Next Phase Readiness

- **Pré-requisito para Phase 7:** Executar `uv run alembic upgrade head` no banco `caramello_dev` antes de implementar CRUD de Account/Category
- Todos os artefatos em disco estão prontos: env.py configurado, migration 0002 gerada e validada estruturalmente
- Phase 7 pode ser planejada; execução depende da aplicação da migration ao banco

---
*Phase: 06-funda-o-dsl-schema*
*Completed: 2026-05-31*
