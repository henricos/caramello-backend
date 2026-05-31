---
phase: 06-funda-o-dsl-schema
verified: 2026-05-31T12:04:29Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Executar `uv run alembic upgrade head` no banco caramello_dev e confirmar que retorna código 0"
    expected: "Migration 0002 aplicada sem erros; 5 tabelas criadas"
    why_human: "Requer conexão ao banco PostgreSQL caramello_dev — não testável sem banco acessível (SQLite não suportado pelo projeto)"
  - test: "Executar `uv run alembic downgrade -1` após o upgrade e confirmar remoção limpa das 5 tabelas"
    expected: "Downgrade sem erros; tabelas account, movement, financial_entry, category, subcategory removidas"
    why_human: "Requer banco acessível e estado pós-upgrade"
  - test: "Inspecionar via psql: `\\d+ movement` mostra amount como numeric(15,2); `\\d+ movement` e `\\d+ financial_entry` mostram UNIQUE em import_hash e movement_id; `\\d+ financial_entry` não lista coluna amount nem type"
    expected: "Tipos e constraints corretos: NUMERIC(15,2), dois UNIQUEs, financial_entry sem amount/type"
    why_human: "Requer banco acessível para inspeção de schema real"
---

# Phase 6: Fundação DSL + Schema — Verification Report

**Phase Goal:** O esquema financeiro está no banco e o código gerado está pronto para receber lógica de negócio
**Verified:** 2026-05-31T12:04:29Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `alembic upgrade head` aplica migration 0002 sem erros em banco limpo (SC-1) | ? UNCERTAIN | Artefato em disco verificado estruturalmente; UAT de banco real diferido (sem banco acessível em sessão de execução) |
| 2 | `alembic downgrade -1` reverte completamente sem erro (SC-2) | ? UNCERTAIN | Mesma razão — requer banco real |
| 3 | Tabelas `account`, `movement`, `financial_entry`, `category`, `subcategory` existem com NUMERIC(15,2), UNIQUE em movement_id e import_hash (SC-3/SC-5) | ? UNCERTAIN | Migration 0002 contém as instruções DDL corretas; constraints e tipos verificáveis apenas em banco real |
| 4 | Código gerado em `src/caramello/finances/` passa em `from caramello.finances import models` sem ImportError (SC-4) | ✓ VERIFIED | `uv run python -c "from caramello.finances import models; print('OK')"` retornou OK; `test_finances_models_import_ok` passa |
| 5 | Hierarquia de categorias em duas entidades separadas: `Subcategory.category_id` → `Category.id`; sem self-referencial (SC-5) | ✓ VERIFIED | `dsl/entities/subcategory.yaml` contém `foreign_key: "category.id"` sem nenhum campo apontando para `subcategory.id`; `models.py` contém `category_id: int = Field(foreign_key="category.id", ...)` |

**Score:** 2/5 truths VERIFIED, 3/5 UNCERTAIN (requerem banco real) — ver nota sobre score abaixo

**Nota sobre score:** Os 3 itens UNCERTAIN (SC-1/SC-2/SC-3) são estruturalmente corretos em disco e foram deliberadamente diferidos por ausência de banco dev durante a execução. Os artefatos que os suportam (`alembic/versions/0002_finances_schema.py`, `alembic/env.py`) passam em todas as verificações estáticas disponíveis. O score de automação é 4/5 para as verificações não-banco (ver seção de must-haves dos PLANs).

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/generate_code.py` | Gerador estendido: Decimal, filters→\_\_table\_args\_\_, DOMAIN\_TO\_ENTITY\_NAME[finances], ruff dinâmico | ✓ VERIFIED | Contém `"decimal": "Decimal"`, `Numeric(15, 2)`, `def _build_table_args`, `"finances": "Account"`, descoberta dinâmica em `_run_ruff_fix` |
| `tests/test_generator.py` | Testes unitários para Decimal e filters | ✓ VERIFIED | Contém `test_generator_decimal_emits_numeric`, `test_generator_filters_emits_table_args`, `test_finances_yamls_have_domain_finances`, `test_finances_models_no_float`, `test_finances_models_import_ok`; todos 21 testes passam |
| `dsl/entities/account.yaml` | Conta com family\_id, currency, is\_active, filters: [family\_id] | ✓ VERIFIED | Existe; `domain: finances` |
| `dsl/entities/movement.yaml` | amount Decimal + import\_hash unique | ✓ VERIFIED | `type: Decimal` no campo amount; `unique: true` em import\_hash |
| `dsl/entities/financial_entry.yaml` | Sem amount/type próprio; movement\_id unique; competencia\_year/month | ✓ VERIFIED | Nenhum campo `amount` ou `type`; `movement_id` com unique; `competencia_year`, `competencia_month` presentes |
| `dsl/entities/category.yaml` | Categoria nível 1 com family\_id | ✓ VERIFIED | Existe; `domain: finances` |
| `dsl/entities/subcategory.yaml` | FK category.id; sem self-referencial | ✓ VERIFIED | `foreign_key: "category.id"`; nenhum campo aponta para `subcategory.id` |
| `dsl/manifest.yaml` | +5 entradas finances | ✓ VERIFIED | Contém account.yaml, movement.yaml, financial\_entry.yaml, category.yaml, subcategory.yaml |
| `dsl/operations/finances.yaml` | Stub com domain: finances | ✓ VERIFIED | Existe; `domain: finances` |
| `src/caramello/finances/__init__.py` | Criado pelo gerador | ✓ VERIFIED | Existe |
| `src/caramello/finances/models.py` | 5 classes table=True; Decimal/Numeric; \_\_table\_args\_\_ | ✓ VERIFIED | Contém Account, Movement, FinancialEntry, Category, Subcategory (table=True); `Numeric(15, 2)`; `from decimal import Decimal`; \_\_table\_args\_\_ com Index em todas as 5 classes |
| `src/caramello/finances/router.py` | CRUD gerado | ✓ VERIFIED | Existe (não registrado em main.py — deferido para Phase 7 conforme decisão documentada) |
| `src/caramello/finances/operations.py` | Stub `# CARAMELLO-GENERATED: stub` | ✓ VERIFIED | Primeira linha: `# CARAMELLO-GENERATED: stub` |
| `alembic/env.py` | naming\_convention + imports finances | ✓ VERIFIED | `SQLModel.metadata.naming_convention` em posição 584; `from caramello.finances.models import` em posição 1267; ordem correta confirmada por verificação de índice de string |
| `alembic/versions/0002_finances_schema.py` | Migration 0002 com down\_revision=0001, NUMERIC(15,2), UNIQUEs, índices | ✓ VERIFIED | `revision = "0002"`, `down_revision = "0001"`; `sa.Numeric(precision=15, scale=2)` na coluna amount; `UniqueConstraint("import_hash")` e `UniqueConstraint("movement_id")`; 6 índices via `op.create_index`; sem coluna amount/type em financial\_entry |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `scripts/generate_code.py get_field_definition` | `Column(Numeric(15, 2))` | ramo `ftype == "Decimal"` | ✓ WIRED | Linha 117-121: `if ftype == "Decimal": ... Field(sa_column=Column(Numeric(15, 2), nullable_kw))` |
| `scripts/generate_code.py generate_models` | `__table_args__` | `_build_table_args(entity_data)` | ✓ WIRED | `_build_table_args` em linha 202; injetado em generate\_models linha 330 (somente na classe table=True) |
| `dsl/entities/subcategory.yaml` | `category.id` | `foreign_key` | ✓ WIRED | `foreign_key: "category.id"` presente; nenhum `foreign_key: "subcategory.id"` |
| `src/caramello/finances/models.py` | `Decimal / Numeric(15, 2)` | gerador (campo amount) | ✓ WIRED | `amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))` |
| `alembic/env.py` | `caramello.finances.models` | import para autogenerate | ✓ WIRED | `from caramello.finances.models import (Account, Category, FinancialEntry, Movement, Subcategory)` |
| `alembic/versions/0002_finances_schema.py` | `0001` | `down_revision` | ✓ WIRED | `down_revision: str ... = "0001"` |

---

### Data-Flow Trace (Level 4)

Não aplicável a esta fase — nenhum componente de runtime dinâmico. Os artefatos são models SQLModel (schema), migrations Alembic (DDL) e templates de geração de código. Não há estado dinâmico renderiozado em runtime nesta fase.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `from caramello.finances import models` sem ImportError (SC-4) | `uv run python -c "from caramello.finances import models; print('OK')"` | `OK` | ✓ PASS |
| Suite completa de testes do gerador (21 testes) | `uv run pytest tests/test_generator.py -v` | 21 passed in 0.13s | ✓ PASS |
| Alembic history linear None→0001→0002 | `uv run alembic history --verbose` | `Rev: 0002 (head), Parent: 0001; Rev: 0001, Parent: <base>` | ✓ PASS |
| models.py não usa float em campos monetários | grep `: float\|Float(` em models.py | nenhum resultado | ✓ PASS |
| naming\_convention antes de finances import em env.py | Índice de string em env.py | posição 584 < 1267 | ✓ PASS |
| `alembic upgrade head` em banco real (SC-1) | `uv run alembic upgrade head` | NÃO EXECUTADO — sem banco dev acessível | ? SKIP |
| `alembic downgrade -1` em banco real (SC-2) | `uv run alembic downgrade -1` | NÃO EXECUTADO — sem banco dev acessível | ? SKIP |

---

### Probe Execution

Nenhum probe declarado nos PLANs. A task de checkpoint humano (06-03-PLAN Task 2) não define probe shell — define verificação interativa com o banco (`alembic upgrade/downgrade` + inspeção psql). Esses itens estão mapeados na seção Human Verification Required.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SC-1 (upgrade head) | 06-03-PLAN | `alembic upgrade head` aplica 0002 sem erros | ? NEEDS HUMAN | Migration gerada e estruturalmente correta; banco não disponível |
| SC-2 (downgrade -1) | 06-03-PLAN | `alembic downgrade -1` reverte limpo | ? NEEDS HUMAN | downgrade() em ordem reversa de FK verificado estaticamente |
| SC-3 (schema correto) | 06-03-PLAN | Tabelas/colunas/constraints corretas | ? NEEDS HUMAN | DDL em 0002\_finances\_schema.py verificado; requer banco real |
| SC-4 (import sem erro) | 06-02-PLAN | `from caramello.finances import models` | ✓ SATISFIED | Import retornou OK; test\_finances\_models\_import\_ok passa |
| SC-5 (hierarquia 2 entidades) | 06-02-PLAN | Category + Subcategory; sem self-referencial | ✓ SATISFIED | subcategory.yaml → category.id; models.py contém ambas as classes |
| SC-6 (sem float) | 06-02-PLAN | models.py não usa float em campos monetários | ✓ SATISFIED | grep sem resultado; Numeric(15, 2) presente |
| SC-7 (gerador Decimal→Numeric) | 06-01-PLAN | generate\_models emite Column(Numeric(15, 2)) para Decimal | ✓ SATISFIED | test\_generator\_decimal\_emits\_numeric passa |
| SC-8 (gerador filters→\_\_table\_args\_\_) | 06-01-PLAN | generate\_models emite \_\_table\_args\_\_ com Index | ✓ SATISFIED | test\_generator\_filters\_emits\_table\_args passa |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/caramello/finances/router.py` | — | Router gerado não registrado em `main.py` | ℹ️ Info | Intencional — deferido para Phase 7 conforme decisão documentada em 06-02-SUMMARY.md; sem impacto funcional nesta fase (nenhum endpoint de finances deve ser exposto ainda) |

Nenhum marcador `TBD`, `FIXME`, ou `XXX` encontrado nos arquivos modificados pela fase. Nenhum `TODO` não rastreável encontrado.

---

### Human Verification Required

#### 1. Migration upgrade em banco real (SC-1)

**Test:** Executar `uv run alembic upgrade head` no banco `caramello_dev`
**Expected:** Comando retorna código 0 sem erros; 5 tabelas criadas
**Why human:** Requer conexão ao PostgreSQL `caramello_dev` — sem banco acessível no momento da execução; SQLite não é suportado pelo projeto

#### 2. Migration downgrade reversível (SC-2)

**Test:** Executar `uv run alembic downgrade -1` após o upgrade
**Expected:** Comando retorna código 0; tabelas `account`, `movement`, `financial_entry`, `category`, `subcategory` removidas sem erro
**Why human:** Requer banco acessível e estado pós-upgrade

#### 3. Inspeção de schema no banco (SC-3)

**Test:** Via psql: `\d+ movement`, `\d+ financial_entry`, `\d+ account`, `\d+ category`, `\d+ subcategory`
**Expected:**
- `movement.amount` como `numeric(15,2)` (não float)
- `UNIQUE` em `movement.import_hash` e `financial_entry.movement_id`
- `financial_entry` sem coluna `amount` nem `type`
- Índices `ix_account_family_id`, `ix_movement_account_id`, `ix_financial_entry_competencia_year_competencia_month`, etc. existem
**Why human:** Requer banco acessível para inspeção de schema real via psql

---

### Gaps Summary

Nenhum gap bloqueador identificado. Todos os artefatos estão presentes, são substantivos e estão corretamente conectados. Os 3 itens UNCERTAIN (SC-1/SC-2/SC-3) são inteiramente dependentes de banco real — não representam falha de implementação, mas verificação de runtime que requer UAT humano.

O status `human_needed` é conservador e correto: a fase declara SC-1/SC-2/SC-3 como critérios de sucesso, e esses critérios só podem ser confirmados em banco PostgreSQL real.

**Pré-requisito para Phase 7:** Executar e aprovar o UAT de banco (itens 1-3 acima) antes de iniciar a implementação de CRUD em Phase 7.

---

_Verified: 2026-05-31T12:04:29Z_
_Verifier: Claude (gsd-verifier)_
