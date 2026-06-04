---
phase: 05-mcp-testes-e-docker
plan: "02"
subsystem: families/services
tags: [service-layer, tdd, mcp-prep, refactoring]
dependency_graph:
  requires: [05-01]
  provides: [families/services.py, operation_id="list_my_families"]
  affects: [05-04-mcp-integration]
tech_stack:
  added: []
  patterns: [service-layer-extraction, local-import-to-avoid-circular-dependency]
key_files:
  created:
    - src/caramello/families/services.py
    - tests/test_services/test_family_service.py
  modified:
    - src/caramello/families/operations.py
decisions:
  - "Import do service é local (dentro da função em operations.py) para evitar ciclo de import entre families/services.py e families/operations.py"
  - "operation_id explícito obrigatório para FastApiMCP.include_operations funcionar corretamente (FastAPI gera IDs automáticos longos sem ele)"
  - "Docstring de services.py não menciona HTTPException para passar grep de aceitação limpo"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-27"
  tasks_completed: 2
  files_changed: 3
---

# Phase 5 Plan 02: Extração de families/services.py Summary

**One-liner:** Extração da lógica de listagem de famílias para service puro + `operation_id="list_my_families"` obrigatório para MCP.

## O Que Foi Feito

Criado `src/caramello/families/services.py` com `list_my_families(session, user)` — função async pura sem dependências FastAPI — e refatorado o endpoint `GET /families/families` em `operations.py` para delegá-la ao service com `operation_id` explícito.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|---------|
| 1 (RED) | Testes unitários do service | `49c126e` | `tests/test_services/test_family_service.py` |
| 1 (GREEN) | Implementação families/services.py | `63df389` | `src/caramello/families/services.py` |
| 2 | Refatoração operations.py | `e520fb5` | `src/caramello/families/operations.py` |

## Resultados de Verificação

- `uv run pytest -m "not integration"`: **34 passed, 3 xfailed** (sem regressões)
- `uv run ruff check src/`: **All checks passed**
- `uv run mypy src/`: **Success: no issues found in 16 source files**
- `grep 'operation_id="list_my_families"' src/caramello/families/operations.py`: match encontrado
- `grep "from caramello.families.services import list_my_families as svc"`: match encontrado

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring de services.py mencionava "HTTPException"**
- **Found during:** Task 1 (acceptance criteria check)
- **Issue:** O plano especifica `grep -c "fastapi\|APIRouter\|HTTPException" services.py` deve retornar 0, mas o texto da docstring mencionava "HTTPException" para explicar o que o service NÃO faz
- **Fix:** Reescrita da docstring para explicar o comportamento sem citar o nome da classe FastAPI
- **Files modified:** `src/caramello/families/services.py`
- **Commit:** parte do `63df389`

### Observação: testes test_family_operations.py falham sem env vars

Os testes em `tests/test_family_operations.py` falham quando executados sem variáveis de ambiente (DB_HOST, KEYCLOAK_URL etc.) — falha de settings validation Pydantic, pré-existente antes deste plano. Com as variáveis adequadas, todos os 8 testes passam. Não é regressão introduzida por este plano.

## TDD Gate Compliance

- RED gate: commit `49c126e` — `test(05-02): adiciona testes unitários de families/services.py`
- GREEN gate: commit `63df389` — `feat(05-02): cria families/services.py com list_my_families puro`

## Threat Surface Scan

Nenhum novo endpoint de rede criado. O service `list_my_families` não é exposto diretamente — apenas via `GET /families/families` já existente. As mitigações T-05-03 e T-05-04 do threat model foram implementadas:

- T-05-03 (Elevation of Privilege): filtro `.where(FamilyMember.user_id == user.id)` presente em `services.py`
- T-05-04 (Information Disclosure): `response_model=list[FamilyRead]` mantido no endpoint em `operations.py`

## Self-Check: PASSED

Arquivos criados verificados:
- `src/caramello/families/services.py`: FOUND
- `tests/test_services/test_family_service.py`: FOUND
- `src/caramello/families/operations.py` (modificado): FOUND

Commits verificados:
- `49c126e`: test(05-02) — FOUND
- `63df389`: feat(05-02) — FOUND
- `e520fb5`: refactor(05-02) — FOUND
