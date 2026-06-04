---
phase: 07-crud-account-category
plan: "03"
subsystem: finances/auth
tags: [wave-2, auth, account-crud, category-crud, subcategory-crud, finances]
dependency_graph:
  requires: [07-02]
  provides:
    - src/caramello/shared/auth._require_family_access
    - src/caramello/finances/operations.CategoryReadPublic
    - src/caramello/finances/operations.SubcategoryReadPublic
    - src/caramello/finances/operations.router (6 paths completos)
  affects:
    - src/caramello/main.py
    - src/caramello/shared/auth.py
tech_stack:
  added: []
  patterns:
    - schemas públicos *Public sem IDs internos (D-10)
    - UUID público → ID interno no backend (D-07/D-08/D-09)
    - rotas planas /subcategory com category_uuid no payload (D-12/D-13)
    - _require_family_access reutilizável com import lazy (Phases 7/8/9)
    - CAT-03 enforced estruturalmente por duas tabelas (sem endpoint de nível 3)
    - include_router antes de mcp.mount_http() (pitfall P7)
key_files:
  created:
    - tests/test_finances_operations.py
  modified:
    - src/caramello/shared/auth.py
    - src/caramello/finances/operations.py
    - src/caramello/main.py
decisions:
  - "category_uuid como query param obrigatório em GET /finances/subcategory (D-12)"
  - "Subcategory acessa família via category.family_id — não via payload (D-13, IDOR mitigado)"
  - "CAT-03 enforced estruturalmente: apenas duas tabelas, zero validação de profundidade"
metrics:
  duration: "~10min"
  completed: "2026-06-01T16:55:35Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 3
---

# Phase 7 Plan 03: Category e Subcategory CRUD Summary

Implementa CRUD completo de Category (nível 1) e Subcategory (nível 2) em `finances/operations.py`, com helper `_require_family_access` em `shared/auth.py`, schemas públicos sem IDs internos, e 6 paths de router registrados antes do MCP.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implementar CRUD de Category + Account + helper auth | 11d7330 | src/caramello/shared/auth.py, src/caramello/finances/operations.py, src/caramello/main.py, tests/test_finances_operations.py |
| 2 | Implementar CRUD de Subcategory com rotas planas e validar 6 paths | 11d7330 | (incluído no mesmo commit — operations.py já estava completo) |

## Verification Results

- `uv run python -m pytest tests/test_finances_operations.py -q` → 11 passed
- `uv run python -m pytest tests/test_finances_operations.py::test_create_subcategory tests/test_finances_operations.py::test_finances_router_paths -v` → 2 passed
- `uv run python -m pytest -q` → 52 passed, 1 skipped, 1 xpassed, 4 errors pré-existentes (integração DB sem banco disponível)
- Router expõe exatamente 6 paths: `/finances/accounts`, `/finances/accounts/{account_uuid}`, `/finances/categories`, `/finances/categories/{category_uuid}`, `/finances/subcategory`, `/finances/subcategory/{subcategory_uuid}`

## Acceptance Criteria Verification

| Critério | Status |
|----------|--------|
| finances/operations.py contém `class CategoryReadPublic` sem campo `family_id` | PASS |
| finances/operations.py contém handlers para POST/GET/GET{uuid}/PATCH de /categories | PASS |
| Cada handler de Category contém `await _require_family_access(` | PASS |
| `test_create_category` e `test_list_update_categories` passam | PASS |
| finances/operations.py contém `class SubcategoryReadPublic` com `category_uuid` e sem `category_id`/`id` | PASS |
| finances/operations.py contém handlers para POST/GET/GET{uuid}/PATCH de /subcategory | PASS |
| Handlers de Subcategory resolvem `category_uuid` → Category e chamam `_require_family_access(category.family_id, ...)` | PASS |
| finances/operations.py NÃO contém endpoint de sub-subcategoria (CAT-03 estrutural) | PASS |
| `test_create_subcategory` e `test_finances_router_paths` passam (6 paths presentes) | PASS |
| shared/auth.py contém `async def _require_family_access(` com import lazy de FamilyMember | PASS |
| main.py importa finances_operations e registra router antes de mcp.mount_http() | PASS |

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

### Nota de Contexto

O worktree do Plan 03 partiu do estado base do repositório (antes do Plan 02), não de um estado pós-Plan 02. Por isso, as Tasks 1 e 2 do Plan 03 foram implementadas integralmente neste worktree:

- `_require_family_access` adicionado a `shared/auth.py` (previsto como pré-requisito do Plan 02)
- CRUD completo de Account implementado (previsto no Plan 02)
- CRUD de Category e Subcategory implementado (este plano)
- Arquivo `tests/test_finances_operations.py` criado (previsto no Plan 02)

Nenhum conflito com o Plan 02 — ambos produzem o mesmo resultado final. O merge do orquestrador resolverá a sobreposição.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] .env ausente no worktree impedia importação dos módulos**

- **Found during:** Execução inicial dos testes
- **Issue:** O pytest.importorskip falha com ValidationError (pydantic-settings) em vez de ImportError quando as variáveis de ambiente obrigatórias estão ausentes.
- **Fix:** Copiado `.env` do repositório principal para a raiz do worktree antes de executar os testes.
- **Files modified:** `.env` (cópia temporária, não commitada — gitignored)
- **Commit:** n/a

### Plan Executed as Written

Exceto pelo contexto de estado acima, o plano foi executado exatamente conforme especificado. Todas as decisões locked (D-10 a D-13) foram respeitadas.

## Known Stubs

Nenhum stub introduzido. `finances/operations.py` marcado como `# CARAMELLO-GENERATED: implemented` e completamente funcional com 6 paths de router.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-07-03 mitigado | src/caramello/finances/operations.py | CategoryReadPublic/SubcategoryReadPublic sem id/family_id/category_id; todos schemas públicos sem IDs internos |
| T-07-05 mitigado | src/caramello/finances/operations.py | subcategory resolve category_uuid → category.family_id → _require_family_access; 403 para não-membro (IDOR mitigado) |
| T-07-06 mitigado | src/caramello/finances/operations.py | CAT-03: apenas duas tabelas, zero endpoint de sub-subcategoria |

## Self-Check: PASSED

- [x] src/caramello/shared/auth.py modificado com _require_family_access
- [x] src/caramello/finances/operations.py implementado (marcado implemented, 6 paths)
- [x] src/caramello/main.py com import e include_router antes de mount_http
- [x] tests/test_finances_operations.py criado (11 testes)
- [x] Commit 11d7330 existe em git log
- [x] 11 testes de test_finances_operations.py verdes
- [x] 52 testes da suíte completa passam (4 erros pré-existentes de integração DB)
