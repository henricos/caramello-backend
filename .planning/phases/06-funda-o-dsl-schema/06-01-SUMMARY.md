---
phase: 06-funda-o-dsl-schema
plan: 01
subsystem: testing, database
tags: [dsl, sqlmodel, sqlalchemy, decimal, numeric, pytest, code-generation, python]

# Dependency graph
requires: []
provides:
  - "Gerador DSL suporta tipo Decimal → Column(Numeric(15, 2)) com import from decimal import Decimal"
  - "Gerador DSL suporta bloco filters: → __table_args__ com Index em __table_args__"
  - "DOMAIN_TO_ENTITY_NAME registra domínio finances com entidade âncora Account"
  - "_run_ruff_fix descobre domínios dinamicamente (inclui finances automaticamente)"
  - "dsl/schema.yaml documenta chave filters: como propriedade válida"
  - "Testes unitários SC-7 e SC-8 verificando as extensões do gerador"
affects:
  - "06-02 — usa Decimal e filters: nos 5 YAMLs financeiros gerados pelo gerador estendido"
  - "06-03 — migration 0002 usa modelos gerados com __table_args__ e Column(Numeric)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Campo Decimal no DSL gera sa_column=Column(Numeric(15, 2)) — sem float em campos monetários"
    - "Bloco filters: no YAML gera __table_args__ com Index na classe table=True"
    - "TDD RED→GREEN para extensões do gerador: teste escrito antes da implementação"

key-files:
  created: []
  modified:
    - scripts/generate_code.py
    - dsl/schema.yaml
    - tests/test_generator.py

key-decisions:
  - "Decimal usa sa_column=Column(Numeric(15, 2)) — garantia de precisão NUMERIC(15,2) no banco sem risco de float"
  - "__table_args__ injetado apenas na classe table=True, nunca em Read/Create/Update"
  - "sa_imports ordenados (Column, Index, Numeric) para garantir import determinístico"
  - "Descoberta dinâmica em _run_ruff_fix exclui shared e core — segura para qualquer domínio futuro"

patterns-established:
  - "Pattern Decimal: campo type: Decimal no YAML → from decimal import Decimal + Field(sa_column=Column(Numeric(15, 2), nullable=...))"
  - "Pattern filters: campo filters: no YAML → __table_args__ = (Index(...), ...) na classe table=True"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-05-31
---

# Phase 6 Plan 01: Extensão do Gerador DSL Summary

**Gerador DSL estendido com suporte a Decimal→NUMERIC(15,2) e filters:→__table_args__ com Index, habilitando geração precisa do domínio financeiro**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-31T08:26:00Z
- **Completed:** 2026-05-31T08:41:34Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Dois testes TDD RED criados e verificados como falhos antes da implementação (SC-7 e SC-8)
- Gerador estendido com 5 modificações: type_map Decimal, ramo Decimal em get_field_definition, helper _build_table_args, registro finances em DOMAIN_TO_ENTITY_NAME, descoberta dinâmica em _run_ruff_fix
- Suite completa de 18 testes passa (16 preexistentes + 2 novos), sem regressões

## Task Commits

Cada tarefa foi commitada atomicamente:

1. **Task 1: Wave 0 — testes unitários do gerador para Decimal e filters** - `01b316f` (test)
2. **Task 2: Estender o gerador — Decimal, filters→__table_args__, finances, ruff dinâmico** - `6ce58b7` (feat)

_Nota: Task 1 = RED (testes falham), Task 2 = GREEN (implementação passa os testes)_

## Files Created/Modified

- `tests/test_generator.py` — adicionados test_generator_decimal_emits_numeric e test_generator_filters_emits_table_args (115 linhas novas)
- `scripts/generate_code.py` — 5 modificações: type_map, get_field_definition, _build_table_args, DOMAIN_TO_ENTITY_NAME, _run_ruff_fix
- `dsl/schema.yaml` — documentada chave filters: como propriedade válida do schema DSL

## Decisions Made

- Decimal usa `sa_column=Column(Numeric(15, 2), nullable=...)` em vez de `Field(nullable=False)` padrão — garante NUMERIC(15,2) no banco; Field padrão produziria FLOAT (pitfall P1 do RESEARCH.md).
- `__table_args__` injetado apenas na classe `table=True`, nunca nas classes Read/Create/Update — Pitfall 5 do RESEARCH.md; tabelas filho/não-table não herdam __table_args__.
- sa_imports determinísticos: `Column, Index, Numeric` ordenados alfabeticamente para evitar variações na geração.
- Descoberta dinâmica em `_run_ruff_fix` exclui `shared` e `core` por serem módulos internos, não domínios de negócio.

## Deviations from Plan

Nenhum — plano executado exatamente como escrito.

## Issues Encountered

Nenhum. O ambiente já tinha todas as dependências instaladas (sqlmodel, sqlalchemy, pytest, yaml).

## Known Stubs

Nenhum stub introduzido. Os dois novos testes exercem diretamente as funções do gerador em memória, sem stubs.

## Threat Flags

Nenhuma superfície nova de segurança introduzida. Esta fase é build-time e não afeta o runtime de produção (T-06-02 aceito; T-06-SC não aplicável — sem pacotes novos).

## Self-Check

- [x] tests/test_generator.py modificado existe: OK
- [x] scripts/generate_code.py modificado existe: OK
- [x] dsl/schema.yaml modificado existe: OK
- [x] Commit 01b316f existe: OK (test RED)
- [x] Commit 6ce58b7 existe: OK (feat GREEN)

## Self-Check: PASSED

## Next Phase Readiness

- Plano 02 pode começar imediatamente: criar 5 YAMLs financeiros (account, movement, financial_entry, category, subcategory) e rodar o gerador estendido
- O gerador está pronto para processar campos Decimal e blocos filters: corretamente
- Domínio finances registrado em DOMAIN_TO_ENTITY_NAME — operations.py será gerado com import correto de Account

---
*Phase: 06-funda-o-dsl-schema*
*Completed: 2026-05-31*
