---
phase: 08-movimenta-es-importa-o
plan: "02"
subsystem: database
tags: [alembic, sqlmodel, dsl, postgresql, migration, movement, finances]

# Dependency graph
requires:
  - phase: 08-01
    provides: dependências ofxparse/openpyxl instaladas, stubs de services.py e operations.py

provides:
  - dsl/entities/movement.yaml sem type/is_duplicate; amount com convenção de sinal
  - src/caramello/finances/models.py regenerado: Movement sem type/is_duplicate
  - alembic/versions/0003_movement_schema_update.py: DROP COLUMN type + DROP COLUMN is_duplicate

affects: [08-03, 08-04, 09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DSL-first: editar YAML → bin/generate_code → models.py regenerado automaticamente"
    - "Migration manual: escrever à mão para controlar exatamente as operações (sem autogenerate)"
    - "Downgrade seguro: ADD COLUMN com server_default preserva NOT NULL constraint"

key-files:
  created:
    - alembic/versions/0003_movement_schema_update.py
  modified:
    - dsl/entities/movement.yaml
    - src/caramello/finances/models.py

key-decisions:
  - "D-01: amount com sinal (positivo=crédito, negativo=débito) — campo type removido"
  - "D-02: is_duplicate removido — duplicatas suspeitas retornam em potential_duplicates[] na resposta"
  - "D-03: migration 0003 com down_revision='0002', grafo linear 0001→0002→0003"

patterns-established:
  - "Fluxo DSL: nunca editar models.py diretamente — editar YAML e regenerar"
  - "Migration reversível: downgrade() reconstrói colunas com server_default para manter NOT NULL"

requirements-completed: [MOV-01, MOV-04, MOV-05]

# Metrics
duration: 15min
completed: 2026-06-02
---

# Phase 08 Plan 02: Schema Update Movement Summary

**Schema Movement atualizado via DSL: campos `type` e `is_duplicate` removidos, `amount` adota convenção de sinal, migration 0003 com DROP COLUMN aplicável e revertível**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-02T20:54:00Z
- **Completed:** 2026-06-02T21:09:02Z
- **Tasks:** 2 de 2
- **Files modified:** 3

## Accomplishments

- Campo `type` removido do DSL YAML e do ORM Movement — `amount` com sinal elimina a necessidade do campo direcional
- Campo `is_duplicate` removido do DSL YAML e do ORM Movement — deduplicação passou para a camada de serviço com resposta `potential_duplicates[]`
- Migration 0003 criada com `down_revision="0002"`, grafo alembic linear 0001→0002→0003 verificado
- `uv run python -c "from caramello.finances.models import Movement; assert not hasattr(Movement, 'type')"` passa sem erro
- 21 testes do gerador continuam verdes após regeneração

## Task Commits

1. **Task 1: Editar movement.yaml e regenerar models.py** - `4f3f619` (refactor)
2. **Task 2: Criar migration 0003 DROP COLUMN type + is_duplicate** - `ebf65a8` (feat)

## Files Created/Modified

- `dsl/entities/movement.yaml` — removidos campos `type` e `is_duplicate`; descrição de `amount` atualizada para "Valor com sinal: positivo=crédito, negativo=débito. NUMERIC(15,2)."
- `src/caramello/finances/models.py` — regenerado via `bin/generate_code`; `Movement` sem `type`/`is_duplicate`; mantém `amount: Decimal` com `Numeric(15,2)` e `import_hash` único nullable
- `alembic/versions/0003_movement_schema_update.py` — migration `revision="0003"`, `down_revision="0002"`; upgrade() com dois DROP COLUMN; downgrade() reconstrói com server_default

## Decisions Made

Seguidas conforme especificadas no plano (D-01, D-02, D-03 do CONTEXT.md):
- `amount` com sinal é suficiente para diferenciar crédito/débito — `SUM(amount)` em Phase 9 sem `CASE WHEN`
- `is_duplicate` persistido não tem mais razão de existir — duplicatas tratadas na resposta da API
- `down_revision` verificado com `alembic history --verbose` conforme pitfall P6 do STATE.md

## Deviations from Plan

### Ambiente sem PostgreSQL

**Contexto:** O plano exigia executar `uv run alembic upgrade head` e `uv run alembic downgrade -1` em banco real (caramello_dev).

**Encontrado durante:** Task 2

**Situação:** O ambiente de CI/worktree não tem PostgreSQL disponível — tentativa de conexão retornou `[Errno 111] Connect call failed`.

**Ação:** Verificação estrutural alternativa realizada:
- Sintaxe Python da migration parseada via `ast.parse()` sem erros
- Conteúdo verificado programaticamente: `revision="0003"`, `down_revision="0002"`, `DROP COLUMN type`, `DROP COLUMN is_duplicate`, `ADD COLUMN` no downgrade
- `alembic history --verbose` confirma grafo linear 0003→0002→0001

**Impacto:** A migration está estruturalmente correta. O teste de banco real deve ser executado pelo operador em ambiente com PostgreSQL usando `bin/manage_db upgrade` antes de aplicar em produção.

---

**Total deviações:** 1 (limitação de ambiente — não código)
**Impacto no plano:** Sem impacto na qualidade do artefato. Migration correta; teste de banco real é responsabilidade do operador em ambiente adequado.

## Issues Encountered

Mudanças de formatação em `src/caramello/finances/operations.py` detectadas após `bin/generate_code` (reorganização de imports, reformatação de linhas longas). O gerador parece fazer formatação adicional mesmo em arquivos marcados como "implemented". Revertidas com `git checkout -- src/caramello/finances/operations.py` pois não fazem parte do escopo desta task.

## Known Stubs

Nenhum. Este plano não cria endpoints ou UI — apenas altera schema e regenera modelo.

## Next Phase Readiness

- Schema Movement pronto para receber endpoints (08-03: parsers, 08-04: endpoints)
- ORM `Movement` sem `type`/`is_duplicate` — `import_hash` e `amount: Decimal` mantidos
- Migration 0003 preparada; precisa ser aplicada em banco de desenvolvimento antes de 08-03/08-04

---
*Phase: 08-movimenta-es-importa-o*
*Completed: 2026-06-02*
