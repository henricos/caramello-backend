---
phase: 09-concilia-o-relat-rios-mcp
plan: "01"
subsystem: finances
tags: [testing, stubs, nyquist, rapidfuzz, wave-0]
dependency_graph:
  requires: []
  provides: [test-stubs-phase-9, rapidfuzz-install]
  affects: [pyproject.toml, uv.lock, tests/test_finances_operations.py, tests/test_services/test_finances_service.py]
tech_stack:
  added: [rapidfuzz==3.14.5]
  patterns: [pytest.importorskip guard, _skip_if_stub pattern, AsyncMock session, dependency_overrides]
key_files:
  created:
    - tests/test_finances_operations.py
    - tests/test_services/test_finances_service.py
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "Stubs usam _skip_if_stub() para test_finances_operations e pytest.importorskip+getattr para test_finances_service — padrão existente nos testes de fase 7/8"
  - "test_finances_router_paths guarded por _skip_if_stub() enquanto os 8 paths da fase 9 não existem — plano 09-04 remove o guard"
  - ".env copiado para o worktree para permitir importação de caramello.finances.operations (requer Settings() válido)"
metrics:
  duration: ~8min
  completed_date: "2026-06-04"
---

# Phase 9 Plan 01: Infraestrutura de validação Nyquist e instalação de rapidfuzz

Instala `rapidfuzz>=3.14.5` (aprovado no checkpoint T-09-SC) e estabelece 18 stubs de teste para todos os comportamentos da fase 9 (conciliação, sugestão de categoria, saldos, relatórios). Todos os stubs skipam até as implementações chegarem nos planos 09-03 e 09-04.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Verificação supply chain rapidfuzz | (checkpoint aprovado pelo operador) | — |
| 2 | Instalar rapidfuzz + stubs de serviço | `9069b68` | pyproject.toml, uv.lock, tests/test_services/test_finances_service.py |
| 3 | Stubs de endpoint + router paths | `a8255e9` | tests/test_finances_operations.py |

## O que foi construído

### rapidfuzz instalado

- `rapidfuzz>=3.14.5` adicionado a `pyproject.toml` e `uv.lock`
- Versão instalada: 3.14.5 (MIT license, verificado em pypi.org/project/RapidFuzz)
- `import rapidfuzz` funciona sem erros

### 6 stubs de serviço (test_finances_service.py)

Arquivo criado do zero com padrão `pytest.importorskip("caramello.finances.services")` + `getattr(services, funcname, None)` + `pytest.skip`:

1. `test_suggest_category_service` — LAN-03, D-CAT-01/02: verifica chaves subcategory_uuid, subcategory_name, category_uuid, category_name, score (int)
2. `test_suggest_category_empty_history` — D-CAT-03: sem histórico retorna `[]`
3. `test_account_balance_empty` — REL-01, pitfall P6: SUM() vazio retorna Decimal("0.00")
4. `test_family_balance` — REL-02: retorna Decimal consolidado
5. `test_monthly_breakdown` — REL-03/04: retorna list de rows
6. `test_by_member_breakdown` — D-REP-02: inclui grupo user_uuid=None

### 12 stubs de endpoint (test_finances_operations.py)

Arquivo criado do zero com padrão `_skip_if_stub()` (verifica anotação `# CARAMELLO-GENERATED: stub` na primeira linha de operations.py):

1. `test_finances_router_paths` — 8 paths da fase 9 no expected set, guardado por `_skip_if_stub()`
2. `test_reconcile_movement` — LAN-01/04, D-REC-02: POST reconcile retorna 201 + schema rico
3. `test_reconcile_409_duplicate` — LAN-02, D-REC-01: IntegrityError para 409
4. `test_suggest_category` — LAN-03: GET suggest-category retorna lista
5. `test_update_entry` — LAN-05, D-REC-04: PATCH entries/{uuid}
6. `test_entry_responsible_user_uuid` — D-ATTR: null limpa responsável (model_fields_set)
7. `test_account_balance` — REL-01, D-BAL-01: GET balance retorna {account_uuid, balance, currency}
8. `test_family_balance` — REL-02, D-BAL-02: GET family balance retorna {family_uuid, total_balance}
9. `test_monthly_report` — REL-03/04, D-REP-01: GET monthly retorna {period, total, rows}
10. `test_report_uses_competencia` — REL-05, D-REP-03: aceita year/month, não retorna 422
11. `test_movement_entry_uuid_field` — D-MOV-01: movements inclui entry_uuid
12. `test_movement_reconciled_filter` — D-MOV-02: ?reconciled=false aceito sem 422

## Resultado da verificação

```
uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -x
# 18 skipped in 0.16s — suite verde
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] .env ausente no worktree bloqueava importação**
- **Found during:** Task 3 (primeira execução dos testes)
- **Issue:** `pytest.importorskip("caramello.finances.operations")` falha com `ValidationError` (não `ModuleNotFoundError`) porque `Settings()` requer variáveis de ambiente. Sem `.env` no worktree, todos os 12 testes falhavam em vez de skipar.
- **Fix:** Copiado `.env` do main repo para o worktree. Arquivo é gitignored e não comitado.
- **Files modified:** `.env` (criado, não rastreado pelo git)
- **Impact:** Nenhum — comportamento correto restaurado; 12 testes skipam como esperado.

## Known Stubs

Todos os testes são stubs intencionais — aguardam implementação nos planos 09-03 e 09-04. Nenhum produz dados ou comportamento de UI.

## Threat Flags

Nenhum. Este plano não introduz novos endpoints nem modifica superfícies de autenticação.

## Self-Check: PASSED

- [x] `tests/test_finances_operations.py` existe e contém 12 funções de teste
- [x] `tests/test_services/test_finances_service.py` existe e contém 6 funções de teste
- [x] `rapidfuzz>=3.14.5` em pyproject.toml
- [x] Commits `9069b68` e `a8255e9` existem no log
- [x] Suite verde: 18 skipped, 0 failed
