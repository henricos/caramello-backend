---
phase: 07-crud-account-category
plan: "01"
subsystem: finances/tests
tags: [wave-0, tdd, scaffold, finances, accounts, categories]
dependency_graph:
  requires: []
  provides: [tests/test_finances_operations.py]
  affects: [src/caramello/finances/operations.py]
tech_stack:
  added: []
  patterns: [pytest.importorskip, AsyncMock, TestClient, dependency_overrides]
key_files:
  created:
    - tests/test_finances_operations.py
  modified: []
decisions:
  - "_skip_if_stub() em vez de importorskip puro: stub é importável mas não implementado — skip explícito via verificação da anotação da primeira linha do arquivo"
metrics:
  duration: "275s (~4m)"
  completed: "2026-06-01T16:38:11Z"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 7 Plan 01: Wave 0 Test Scaffold Summary

Scaffold de testes Wave 0 para o domínio finances com 11 funções de teste cobrindo todos os 9 requisitos da fase (ACC-01/02/03, CAT-01/02/03/04, AUTH-FIN-01/02). Todos os testes permanecem skipados enquanto `finances/operations.py` contém a anotação `stub`; passam a executar automaticamente quando os planos 07-02/07-03 marcarem o módulo como `implemented`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Criar scaffold tests/test_finances_operations.py | e89ecb9 | tests/test_finances_operations.py |

## Verification Results

- `uv run python -m pytest tests/test_finances_operations.py -q` → exit 0 (1 passed, 10 skipped)
- Todas as 11 funções de teste coletadas sem erro de sintaxe/importação
- `test_finances_module_exists` passa (módulo importável)
- Os 10 testes de implementação saltam via `_skip_if_stub()` enquanto annotation é `stub`

## Test Coverage Map

| Função de Teste | Requisito | Status |
|----------------|-----------|--------|
| `test_finances_module_exists` | — | PASSED (módulo existe) |
| `test_finances_operations_annotation_is_implemented` | — | SKIPPED (stub) |
| `test_finances_router_paths` | CAT-03 | SKIPPED (stub) |
| `test_create_account_returns_uuid` | ACC-01, T-07-01 | SKIPPED (stub) |
| `test_list_accounts_scoped_to_family` | ACC-02 | SKIPPED (stub) |
| `test_accounts_require_auth` | AUTH-FIN-01 | SKIPPED (stub) |
| `test_accounts_403_non_member` | AUTH-FIN-02 | SKIPPED (stub) |
| `test_archive_account` | ACC-03 | SKIPPED (stub) |
| `test_create_category` | CAT-01 | SKIPPED (stub) |
| `test_list_update_categories` | CAT-04 | SKIPPED (stub) |
| `test_create_subcategory` | CAT-02 | SKIPPED (stub) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mecanismo de skip ajustado para stub importável**

- **Found during:** Task 1 — verificação
- **Issue:** `pytest.importorskip("caramello.finances.operations")` só emite skip quando o módulo lança `ImportError`. O stub `finances/operations.py` importa sem erro, portanto `importorskip` sozinho não causaria skip — os testes executariam e falhariam.
- **Fix:** Introduzida função auxiliar `_skip_if_stub()` que: (1) chama `importorskip` para garantir que o módulo existe, (2) lê a primeira linha de `operations.py` e emite `pytest.skip()` explícito se contiver `"stub"`. Quando a anotação mudar para `implemented` nos planos 07-02/07-03, o skip some automaticamente.
- **Files modified:** tests/test_finances_operations.py
- **Commit:** e89ecb9

O padrão `pytest.importorskip` é mantido em `test_finances_module_exists` (comportamento puro do analog) e em `_skip_if_stub()` como primeiro passo. A abordagem é equivalente ao contrato do plano: "falhar limpo até a implementação chegar".

## Known Stubs

Nenhum stub introduzido por este plano. O arquivo de testes não tem lógica de renderização ou dados hardcoded — todos os mocks são reset entre testes via `app.dependency_overrides.clear()`.

## Threat Flags

Nenhuma nova superfície de segurança introduzida. O arquivo de testes usa apenas `TestClient` com mocks in-process; nenhum dado cruza para banco real.

## Self-Check: PASSED

- [x] `tests/test_finances_operations.py` existe
- [x] Commit e89ecb9 existe: `git log --oneline | grep e89ecb9` ✓
- [x] 11 funções `def test_` (>= 9 requeridos)
- [x] `pytest.importorskip("caramello.finances.operations")` presente
- [x] `_make_fake_user` presente
- [x] `TestClient(app)` presente (10 ocorrências)
- [x] Suite roda verde: 1 passed, 10 skipped, exit code 0
