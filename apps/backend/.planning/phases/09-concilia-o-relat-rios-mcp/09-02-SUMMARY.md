---
phase: 09-concilia-o-relat-rios-mcp
plan: "02"
subsystem: finances/schema
tags: [migration, orm, dsl, financial-entry, responsible-user]
dependency_graph:
  requires: []
  provides: [responsible_user_id-column, migration-0004]
  affects: [src/caramello/finances/models.py, alembic/versions/0004_financial_entry_responsible_user.py, dsl/entities/financial_entry.yaml]
tech_stack:
  added: []
  patterns: [nullable-fk, alembic-add-column, dsl-manual-edit]
key_files:
  created:
    - alembic/versions/0004_financial_entry_responsible_user.py
  modified:
    - src/caramello/finances/models.py
    - dsl/entities/financial_entry.yaml
decisions:
  - "Campo responsible_user_id inserido manualmente em finances/models.py (arquivo marcado # CARAMELLO-GENERATED: implemented), não gerado pelo DSL — consistente com a política do projeto para arquivos com essa anotação"
  - "Coluna nullable sem server_default — linhas existentes recebem NULL automaticamente; sem data migration necessária"
  - "YAML DSL atualizado para que regeneração futura não perca o campo"
metrics:
  duration: "~7 minutos"
  completed: "2026-06-04T09:27:44Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 09 Plan 02: Schema FinancialEntry responsible_user_id Summary

**One-liner:** FK nullable `responsible_user_id → user.id` adicionada ao ORM `FinancialEntry` e migration `0004` com cadeia Alembic linear `0001→0002→0003→0004`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar responsible_user_id ao modelo + YAML DSL | c6d6c2d | src/caramello/finances/models.py, dsl/entities/financial_entry.yaml |
| 2 | Criar migration 0004 ADD COLUMN responsible_user_id | a52f261 | alembic/versions/0004_financial_entry_responsible_user.py |

## What Was Built

Extensão do schema de `financial_entry` com a coluna `responsible_user_id` (FK nullable → `user.id`), que sustenta a atribuição de responsável nos lançamentos (D-SCHEMA-01/02). Esta coluna é base necessária para:
- O payload de reconcile/PATCH dos endpoints de conciliação (LAN-01, LAN-05) — plano 09-03
- O relatório por membro que agrupa por responsável (plano 09-04)

**Modelo ORM (`FinancialEntry`):**
- Campo `responsible_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True)` inserido após `is_recorrente`, antes de `created_at`
- `__table_args__` inalterado — nenhum novo Index adicionado

**Migration 0004:**
- `revision="0004"`, `down_revision="0003"` — cadeia linear sem fork verificada
- `upgrade()`: `op.add_column` com `nullable=True`, sem `server_default`
- `downgrade()`: `op.drop_column` para reversão limpa

**YAML DSL:**
- Campo `responsible_user_id` adicionado após `is_recorrente` no `dsl/entities/financial_entry.yaml` para consistência DSL-first

## Verification Results

- `uv run python -c "from caramello.finances.models import FinancialEntry; assert 'responsible_user_id' in FinancialEntry.model_fields"` — passou
- Cadeia Alembic verificada via importação direta dos módulos: `0001(None)→0002→0003→0004` — linear sem fork
- `grep -q 'foreign_key="user.id"' src/caramello/finances/models.py` — passou
- `grep -q 'responsible_user_id' dsl/entities/financial_entry.yaml` — passou
- `__table_args__` inalterado — apenas os 2 Index originais

## Deviations from Plan

Nenhuma — plano executado exatamente como escrito.

## Known Stubs

Nenhum stub. O campo é real e funcional no ORM. A aplicação em banco (alembic upgrade head) requer ambiente PostgreSQL disponível (sandbox não possui DB configurado — comportamento esperado mencionado no plano).

## Threat Surface Scan

Nenhuma nova superfície de segurança introduzida além do previsto no `<threat_model>` do plano:
- `T-09-02` (fork Alembic): mitigado — `down_revision="0003"` verificado antes de criar
- `T-09-03` (FK responsible_user_id): aceito — validação de membership será feita no service (plano 09-03)

## Self-Check: PASSED

- [x] `src/caramello/finances/models.py` existe e contém `responsible_user_id`
- [x] `dsl/entities/financial_entry.yaml` existe e menciona `responsible_user_id`
- [x] `alembic/versions/0004_financial_entry_responsible_user.py` existe
- [x] Commit `c6d6c2d` existe — Task 1
- [x] Commit `a52f261` existe — Task 2
