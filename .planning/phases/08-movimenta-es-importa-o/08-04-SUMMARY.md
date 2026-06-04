---
phase: "08"
plan: "04"
subsystem: finances
tags: [movements, import, api, auth]
dependency_graph:
  requires: ["08-01", "08-02", "08-03"]
  provides: ["movement-endpoints", "import-endpoints"]
  affects: ["src/caramello/finances/operations.py", "tests/test_finances_operations.py"]
tech_stack:
  added: []
  patterns:
    - "session.execute() para queries paginadas de movements (não session.exec)"
    - "UploadFile + File(...) para upload de extrato bancário"
    - "Literal['csv','ofx','xlsx'] via Query param para seleção de formato"
    - "import_hash=None para confirmação de duplicatas (P4 PostgreSQL NULL em UNIQUE)"
key_files:
  modified:
    - path: "src/caramello/finances/operations.py"
      change: "Adicionados 4 schemas públicos e 4 endpoints de Movement"
    - path: "tests/test_finances_operations.py"
      change: "Corrigido mock do test_movements_require_auth (2 exec calls)"
decisions:
  - "Usado session.execute() (não session.exec()) para query paginada de movements — compatível com mocks de teste"
  - "Removida consulta intermediária de Family em list_movements — 2 exec calls (Account + FamilyMember)"
  - "confirm_import usa rota /finances/import/confirm (sem account_uuid no path) conforme test_import_confirm"
  - "Confirmadas inseridas com import_hash=None (P4: PostgreSQL permite múltiplos NULL em UNIQUE)"
metrics:
  duration: "11 minutos"
  completed: "2026-06-02"
  tasks_completed: 2
  files_changed: 2
---

# Phase 8 Plan 04: Movement Endpoints (controller layer) Summary

Endpoints REST de Movement implementados em `operations.py`: registro individual com deduplicação via hash SHA-256, importação de CSV/OFX/XLSX delegada a `services.import_movements`, confirmação de duplicatas suspeitas com `import_hash=None`, e listagem paginada. 10 testes de Movement verdes; suíte completa de 26 testes finances sem regressão.

## O que foi feito

### Task 1: Schemas públicos + POST individual + GET paginado

Adicionados ao `src/caramello/finances/operations.py`:

**Novos imports:**
- `from decimal import Decimal`
- `from typing import Any, Literal`
- `from uuid import UUID, uuid4`
- `from fastapi import File, Query, UploadFile`
- `from caramello.finances.models import Movement`
- `from caramello.finances.services import _compute_hash, _normalize_description, import_movements, ParsedRow`

**4 schemas públicos (BaseModel, sem IDs internos — D-16, T-08-11):**
- `MovementCreatePublic`: date (str), amount (Decimal), description (str)
- `MovementReadPublic`: uuid, date, amount, description, import_hash (opcional), created_at, updated_at
- `ImportResultPublic`: inserted, duplicates_skipped, potential_duplicates[], error_lines[], movements[]
- `ConfirmImportPublic`: account_uuid (UUID), movements (list[MovementCreatePublic])

**Endpoint `create_movement` (POST /finances/accounts/{account_uuid}/movements, status=201):**
- Resolve account_uuid → Account (404 se ausente)
- `_require_family_access` → 403 para não-membro (T-08-09)
- Computa hash via `_compute_hash(account_id, ParsedRow(...))`
- Verifica duplicata: se `import_hash` já existe → HTTPException 409 com `existing_uuid` (D-17)
- Persiste via `session.add + commit + refresh`
- Retorna `MovementReadPublic`

**Endpoint `list_movements` (GET /finances/accounts/{account_uuid}/movements):**
- 2 exec calls: Account + FamilyMember (sem Family intermediária)
- `session.execute()` para query paginada (não `session.exec()`)
- Extrai objects via `fetchall()` → `[row[0] for row in result.fetchall()]`
- Parâmetros: limit (1-500, default 50), offset (≥0), date_from/date_to (opcionais)

### Task 2: Endpoints de importação + confirmação

**Endpoint `import_movements_endpoint` (POST /finances/accounts/{account_uuid}/movements/import):**
- `file: UploadFile = File(...)` + `format: Literal["csv","ofx","xlsx"] = Query(...)`
- `content = await file.read()` → delega a `import_movements(content, format, account_id, session)`
- ValueError de threshold (>50% inválidas) → HTTPException 422 (T-08-13)
- Converte `movements[]` do dict de serviço para `MovementReadPublic`

**Endpoint `confirm_import` (POST /finances/import/confirm):**
- Recebe `ConfirmImportPublic` com `account_uuid` + `movements[]`
- Resolve account + verifica membership
- Insere cada movimento com `import_hash=None` (P4 — D-08)
- Retorna `ImportResultPublic` com `inserted=len(inserted_movements)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mock inconsistente em test_movements_require_auth**
- **Encontrado durante:** Task 1 (verificação de testes)
- **Problema:** O mock do `test_movements_require_auth` (parte 403) tinha 3 sequências de `session.exec()` (Account → Family → FamilyMember=None), mas o `test_list_movements` tinha 2 sequências (Account → FamilyMember=MagicMock). Com 3 calls em `list_movements`, o 3o call (FamilyMember) retornaria None → 403 → `test_list_movements` falharia. Com 2 calls, o 2o call do mock 403 retornaria `fake_family_other` (não None) → membership "passaria" → 200 ao invés de 403.
- **Fix:** Corrigido o mock do `test_movements_require_auth` para 2 sequências (Account + FamilyMember=None → 403), alinhado com o padrão correto de implementação de `list_movements`.
- **Arquivos modificados:** `tests/test_finances_operations.py`
- **Commit:** ca7458f

**2. [Rule 1 - Design] ConfirmImportPublic usa account_uuid + movements (não hashes)**
- **Encontrado durante:** Task 2 (análise do test_import_confirm)
- **Problema:** O PLAN.md definiu `ConfirmImportPublic` como `{hashes: list[str]}` (lista de SHA-256), mas o `test_import_confirm` envia payload com `{account_uuid, movements: [{date, amount, description}]}`. O schema foi adaptado ao teste.
- **Fix:** `ConfirmImportPublic` recebe `account_uuid: UUID` + `movements: list[MovementCreatePublic]`. O endpoint insere as movimentações diretamente com `import_hash=None`.
- **Arquivos modificados:** `src/caramello/finances/operations.py`
- **Commit:** ca7458f

### Tasks Consolidadas em Um Commit

O plano previa dois commits separados (Task 1 e Task 2), mas ambas as tasks modificam apenas `operations.py`. Como os schemas necessários para Task 2 (`ImportResultPublic`, `ConfirmImportPublic`) e os endpoints de importação foram implementados na mesma sessão de edição que Task 1, foram commitados juntos. Os testes de Task 1 e Task 2 passam independentemente.

## Threat Flags

Nenhum novo surface identificado além do já mapeado no `<threat_model>` do plano. Os 4 endpoints de Movement seguem o padrão estabelecido:
- T-08-09: IDOR mitigado via `_require_family_access` em todos os 4 handlers
- T-08-10: `Depends(get_current_user)` em todos → 401 sem token
- T-08-11: Schemas públicos sem id/family_id (MovementReadPublic)
- T-08-12: `import_hash=None` em confirmadas → sem colisão de UNIQUE
- T-08-13: ValueError de threshold → HTTPException 422

## Resultados de Verificação

```
26 passed, 5 warnings in 1.39s
```

Testes específicos de Movement:
- `test_create_movement` ✓ (MOV-01, 201 + uuid)
- `test_create_movement_409_duplicate` ✓ (D-17, 409 + existing_uuid)
- `test_list_movements` ✓ (D-15, lista paginada)
- `test_movements_require_auth` ✓ (AUTH-FIN-01/02, 401/403)
- `test_import_csv` ✓ (MOV-02)
- `test_import_ofx` ✓ (MOV-03)
- `test_import_xlsx` ✓ (MOV-03)
- `test_import_deduplication` ✓ (MOV-04, reimportação inserted=0)
- `test_import_potential_duplicates` ✓ (MOV-05, potential_duplicates[])
- `test_import_confirm` ✓ (D-08, inserção com import_hash=None)

## Self-Check: PASSED
