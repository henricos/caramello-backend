---
phase: 07-crud-account-category
plan: "02"
subsystem: finances/auth
tags: [wave-1, auth, account-crud, category-crud, subcategory-crud, finances]
dependency_graph:
  requires: [07-01]
  provides:
    - src/caramello/shared/auth._require_family_access
    - src/caramello/finances/operations.AccountReadPublic
    - src/caramello/finances/operations.router
  affects:
    - src/caramello/main.py
tech_stack:
  added: []
  patterns:
    - lazy-import para evitar ciclo shared/ ↔ families/
    - schemas públicos *Public sem IDs internos
    - UUID público → ID interno no backend (D-07/D-08/D-09)
    - _require_family_access reutilizável (Phases 7/8/9)
    - include_router antes de mcp.mount_http() (pitfall P7)
key_files:
  created: []
  modified:
    - src/caramello/shared/auth.py
    - src/caramello/finances/operations.py
    - src/caramello/main.py
decisions:
  - "family_uuid como query param obrigatório em GET /finances/accounts (Open Question 1 — mais explícito)"
  - "AUTH-FIN-01 retorna 403 (não 401) para token ausente — comportamento documentado do HTTPBearer auto_error=True"
  - "Subcategory list retorna lista vazia sem filtro (seguro por padrão)"
metrics:
  duration: "~15min"
  completed: "2026-06-01T16:47:04Z"
  tasks_completed: 3
  files_created: 0
  files_modified: 3
---

# Phase 7 Plan 02: Account CRUD + Auth Helper Summary

Implementa controle de acesso por família e CRUD completo de Account no domínio finances via helper `_require_family_access` em `shared/auth.py`, schemas públicos `*Public` sem IDs internos em `finances/operations.py`, e registro do router antes do MCP em `main.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Adicionar helper _require_family_access em shared/auth.py | 744183d | src/caramello/shared/auth.py |
| 2 | Implementar schemas públicos + CRUD de Account em finances/operations.py | a244423 | src/caramello/finances/operations.py |
| 3 | Registrar finances_operations.router em main.py antes do MCP | 4a99c45 | src/caramello/main.py |

## Verification Results

- `uv run python -m pytest tests/test_finances_operations.py::test_create_account_returns_uuid tests/test_finances_operations.py::test_list_accounts_scoped_to_family tests/test_finances_operations.py::test_accounts_require_auth tests/test_finances_operations.py::test_accounts_403_non_member tests/test_finances_operations.py::test_archive_account -x` → 5 passed
- `uv run python -m pytest tests/test_finances_operations.py -q` → 11 passed (todos os testes do arquivo)
- `uv run python -c "from caramello.main import app; assert '/finances/accounts' in {r.path for r in app.routes}"` → ok
- Suíte completa: 52 passed, 1 skipped, 1 xpassed, 4 errors pré-existentes (integração DB)

## Acceptance Criteria Verification

| Critério | Status |
|----------|--------|
| shared/auth.py contém `async def _require_family_access(` | PASS |
| Import lazy de FamilyMember dentro do corpo da função | PASS |
| Levanta HTTP_403_FORBIDDEN quando first() is None | PASS |
| finances/operations.py primeira linha == `# CARAMELLO-GENERATED: implemented` | PASS |
| AccountReadPublic não contém campo `family_id` | PASS |
| 11 chamadas a `await _require_family_access(` | PASS |
| `db_account.updated_at = datetime.now(timezone.utc)` no PATCH | PASS |
| finances/operations.py >= 120 linhas (tem 537) | PASS |
| main.py contém import finances_operations | PASS |
| include_router antes de mount_http (linha 60 < 73) | PASS |
| Router gerado NÃO importado em main.py | PASS |
| `/finances/accounts` presente em app.routes | PASS |

## Test Coverage Map

| Função de Teste | Requisito | Status |
|----------------|-----------|--------|
| `test_finances_module_exists` | — | PASSED |
| `test_finances_operations_annotation_is_implemented` | — | PASSED |
| `test_finances_router_paths` | CAT-03 | PASSED |
| `test_create_account_returns_uuid` | ACC-01, T-07-01 | PASSED |
| `test_list_accounts_scoped_to_family` | ACC-02 | PASSED |
| `test_accounts_require_auth` | AUTH-FIN-01 | PASSED |
| `test_accounts_403_non_member` | AUTH-FIN-02 | PASSED |
| `test_archive_account` | ACC-03 | PASSED |
| `test_create_category` | CAT-01 | PASSED |
| `test_list_update_categories` | CAT-04 | PASSED |
| `test_create_subcategory` | CAT-02 | PASSED |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] .env ausente no worktree impedia importação dos módulos**

- **Found during:** Task 2 — execução dos testes
- **Issue:** O pytest.importorskip falha com ValidationError (pydantic-settings) em vez de ImportError quando as variáveis de ambiente obrigatórias estão ausentes. O arquivo `.env` existe no repositório principal mas não no worktree.
- **Fix:** Copiado `.env` do repositório principal para a raiz do worktree antes de executar os testes. Arquivo `.env` é gitignored por padrão — não foi commitado.
- **Files modified:** `.env` (cópia temporária, não commitada)
- **Commit:** n/a (não commitado — gitignored)

### Plan Executed as Written

Exceto pela questão do `.env` acima, o plano foi executado exatamente conforme especificado. Todas as decisões locked (D-01 a D-13) foram respeitadas.

## Known Stubs

Nenhum stub introduzido. `finances/operations.py` marcado como `# CARAMELLO-GENERATED: implemented` e completamente funcional.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-07-01 mitigado | src/caramello/finances/operations.py | AccountReadPublic sem id/family_id; todos schemas públicos sem IDs internos |
| T-07-02 mitigado | src/caramello/finances/operations.py | _require_family_access chamado em todos os endpoints; 403 para não-membro |
| T-07-03 mitigado | src/caramello/finances/operations.py | family_uuid resolvido no backend; Literal["corrente",...] valida type |
| T-07-04 mitigado | src/caramello/finances/operations.py | Depends(get_current_user) em todos os handlers |

## Self-Check: PASSED

- [x] src/caramello/shared/auth.py modificado com _require_family_access
- [x] src/caramello/finances/operations.py implementado (537 linhas, marcado implemented)
- [x] src/caramello/main.py com import e include_router antes de mount_http
- [x] Commits 744183d, a244423, 4a99c45 existem em git log
- [x] 11 testes de test_finances_operations.py verdes
- [x] 52 testes da suíte completa passam (4 erros pré-existentes de integração DB)
