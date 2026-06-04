---
phase: 06-funda-o-dsl-schema
plan: 02
subsystem: dsl, finances, database
tags: [dsl, yaml, finances, sqlmodel, sqlalchemy, decimal, numeric, pytest, code-generation]

# Dependency graph
requires:
  - "06-01 — gerador DSL com suporte a Decimal→Numeric(15,2) e filters:→__table_args__"
provides:
  - "5 YAMLs DSL do domínio finances: account, movement, financial_entry, category, subcategory"
  - "dsl/manifest.yaml atualizado com as 5 novas entidades"
  - "dsl/operations/finances.yaml stub para Phase 7"
  - "src/caramello/finances/ gerado: __init__.py, models.py, router.py, operations.py"
  - "Testes Wave 0 SC-4/SC-5/SC-6 verificados"
affects:
  - "06-03 — migration 0002 usa os modelos gerados em src/caramello/finances/models.py"
  - "Phase 7 — implementação de Account + Category CRUD usa esses modelos"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "5 entidades finances com domain: finances, 4 campos padrão + campos específicos"
    - "Movement.amount usa type: Decimal → Column(Numeric(15,2)) — precisão monetária garantida"
    - "FinancialEntry sem campo amount/type próprio — herda de Movement via relação 1:1 (D-05)"
    - "Subcategory com FK category.id apenas — sem self-referencial (D-09/CAT-03)"
    - "Hierarquia 2 níveis: Category → Subcategory (D-06)"

key-files:
  created:
    - dsl/entities/account.yaml
    - dsl/entities/movement.yaml
    - dsl/entities/financial_entry.yaml
    - dsl/entities/category.yaml
    - dsl/entities/subcategory.yaml
    - dsl/operations/finances.yaml
    - src/caramello/finances/__init__.py
    - src/caramello/finances/models.py
    - src/caramello/finances/router.py
    - src/caramello/finances/operations.py
  modified:
    - dsl/manifest.yaml
    - tests/test_generator.py

key-decisions:
  - "FinancialEntry sem amount/type próprio — herda de Movement (D-05); campo movement_id com unique=True garante relação 1:1"
  - "Subcategory com FK category.id apenas — hierarquia de 2 níveis sem self-referencial (D-06/D-09)"
  - "import_hash em Movement com unique=True — deduplicação de importações (D-10)"
  - "filters: nos 5 entidades geram __table_args__ com Index via gerador (D-11)"
  - "Sem relationships cross-domain nos YAMLs finances — apenas foreign_key: por campo (Pitfall 4)"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-05-31
---

# Phase 6 Plan 02: YAMLs Financeiros + Geração de Código Summary

**5 YAMLs DSL do domínio finances criados com hierarquia Category/Subcategory em duas entidades, Movement com Decimal/NUMERIC(15,2), FinancialEntry sem valor próprio, geração executada com sucesso e 21 testes passando**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-31T08:46:13Z
- **Completed:** 2026-05-31T08:51:23Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Criados 5 YAMLs DSL em `dsl/entities/` com `domain: finances` e 4 campos padrão cada
- `movement.yaml` com campo `amount: Decimal` (→ Numeric(15,2)) e `import_hash` único (D-10)
- `financial_entry.yaml` sem `amount`/`type` próprios (D-05); `movement_id` com `unique: true` (1:1); `competencia_year`/`competencia_month` (D-04)
- `subcategory.yaml` com FK `category.id` apenas — sem self-referencial (D-09/CAT-03)
- Bloco `filters:` em todas as 5 entidades → `__table_args__` com `Index` nos modelos gerados
- `dsl/manifest.yaml` atualizado com as 5 novas entradas
- `dsl/operations/finances.yaml` stub criado com operação `list_accounts` placeholder
- Gerador executado com sucesso: `src/caramello/finances/` gerado com 4 arquivos
- `from caramello.finances import models` sem ImportError (SC-4)
- `models.py` com `Numeric(15, 2)`, `from decimal import Decimal`, 5 classes `table=True`, `__table_args__` com Index
- 3 testes Wave 0 adicionados e passando: SC-4, SC-5, SC-6
- Suite completa: 21 testes passam (16 preexistentes + 2 Plano 01 + 3 novos)

## Task Commits

1. **Task 1: 5 YAMLs financeiros + manifest + operations stub** — `c3ef58e` (feat)
2. **Task 2: Geração de código finances + testes Wave 0** — `a02ba9a` (feat)

_Nota: Merge do Plano 01 (`b270f85`) foi necessário pois o worktree foi criado antes do merge da wave 1._

## Files Created/Modified

- `dsl/entities/account.yaml` — conta bancária/cartão com family_id, currency, is_active, filters: [family_id]
- `dsl/entities/movement.yaml` — movimentação bruta com amount Decimal, import_hash unique, is_duplicate, filters: [account_id]
- `dsl/entities/financial_entry.yaml` — lançamento sem valor próprio; movement_id unique, subcategory_id, competencia_year/month, is_recorrente; filters: [year+month, subcategory_id]
- `dsl/entities/category.yaml` — categoria nível 1 com family_id, filters: [family_id]
- `dsl/entities/subcategory.yaml` — subcategoria nível 2 com category_id (sem self-ref), filters: [category_id]
- `dsl/manifest.yaml` — +5 entradas (account, movement, financial_entry, category, subcategory)
- `dsl/operations/finances.yaml` — stub com domain: finances + operação list_accounts
- `src/caramello/finances/__init__.py` — criado pelo gerador (vazio)
- `src/caramello/finances/models.py` — 5 entidades × 4 classes (Account, Movement, FinancialEntry, Category, Subcategory) com Decimal/Numeric e __table_args__
- `src/caramello/finances/router.py` — CRUD async gerado para as 5 entidades
- `src/caramello/finances/operations.py` — stub (# CARAMELLO-GENERATED: stub)
- `tests/test_generator.py` — +3 testes Wave 0: SC-4, SC-5, SC-6

## Decisions Made

- `FinancialEntry` sem campo `amount`/`type` próprio: herda de `Movement` via relação 1:1 com `movement_id unique=True` — decisão D-05. A classification entity não duplica dados do extrato.
- Hierarquia de 2 níveis via 2 entidades separadas (`Category` + `Subcategory`) em vez de self-referencial — decisão D-06/D-07. Elimina complexidade de self-join e torna a hierarquia explícita no schema.
- Nenhum relationship cross-domain nos YAMLs finances: apenas `foreign_key:` por campo para evitar ciclo de import (Pitfall 4). Relacionamentos bidirecionais são responsabilidade de Phase 7+.
- `import_hash` com `unique: true` e `nullable: true` — permite null para entradas manuais, garante unicidade apenas para importações de extrato (D-10).

## Deviations from Plan

### Auto-fixed Issues

**1. [Regra 3 - Bloqueio] Merge do Plano 01 necessário**
- **Encontrado durante:** Task 2 — execução do gerador
- **Problema:** O worktree foi criado antes do merge da wave 1 (Plano 01). O `generate_code.py` neste worktree não tinha as extensões de Decimal/filters/finances. O gerador falhou com `ValueError: domain 'finances' não mapeado em DOMAIN_TO_ENTITY_NAME`.
- **Correção:** `git merge main` para trazer as mudanças do Plano 01 (commits 01b316f, 6ce58b7, 6aa693f, 17e52d0, f02c031). Merge limpo sem conflitos.
- **Impacto:** Zero — o merge integrou apenas as mudanças do Plano 01 (gerador estendido + 2 testes + dsl/schema.yaml).

## Known Stubs

- `src/caramello/finances/operations.py` — stub `# CARAMELLO-GENERATED: stub` com único endpoint `list_accounts`. Implementação real na Phase 7.
- `src/caramello/finances/router.py` — CRUD gerado funcional mas sem registro em `main.py` (deferred para Phase 7 conforme decisão do planner/CONTEXT.md).

## Threat Flags

Nenhuma superfície nova de segurança introduzida. Esta fase é build-time/schema; nenhum endpoint funcional é exposto (routers não registrados em main.py). T-06-03 (float), T-06-04 (import circular), T-06-05 (subcategoria de subcategoria) verificados como mitigados pelos critérios de aceitação.

## Self-Check

- [x] dsl/entities/account.yaml existe: FOUND
- [x] dsl/entities/movement.yaml existe: FOUND
- [x] dsl/entities/financial_entry.yaml existe: FOUND
- [x] dsl/entities/category.yaml existe: FOUND
- [x] dsl/entities/subcategory.yaml existe: FOUND
- [x] dsl/manifest.yaml atualizado com 9 entradas: FOUND
- [x] dsl/operations/finances.yaml existe: FOUND
- [x] src/caramello/finances/models.py gerado: FOUND
- [x] src/caramello/finances/operations.py gerado: FOUND
- [x] src/caramello/finances/router.py gerado: FOUND
- [x] Commit c3ef58e existe: OK (feat Task 1)
- [x] Commit a02ba9a existe: OK (feat Task 2)
- [x] 21 testes passam: OK

## Self-Check: PASSED

## Next Phase Readiness

- Plano 03 pode começar: `src/caramello/finances/models.py` com as 5 classes `table=True` está pronto para `alembic revision --autogenerate`
- O `alembic/env.py` precisa de: (1) `SQLModel.metadata.naming_convention` antes dos imports de modelo; (2) import das 5 classes finances
- `alembic upgrade head` criará as 5 tabelas no banco caramello_dev

---
*Phase: 06-funda-o-dsl-schema*
*Completed: 2026-05-31*
