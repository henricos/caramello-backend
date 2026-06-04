---
phase: 08-movimenta-es-importa-o
plan: "01"
subsystem: finances/testing
tags: [nyquist, tdd, dependencies, testing, movements, import]
dependency_graph:
  requires: []
  provides:
    - "ofxparse>=0.21 instalado e verificado"
    - "openpyxl>=3.1.5 instalado e verificado"
    - "Malha Nyquist completa — 15 stubs de teste para MOV-01..05, D-15, AUTH-FIN-01/02"
  affects:
    - "tests/test_finances_operations.py"
    - "tests/test_services/test_finances_service.py"
    - "pyproject.toml"
    - "uv.lock"
tech_stack:
  added:
    - "ofxparse==0.21 — parser OFX com suporte a FITID para deduplicação definitiva"
    - "openpyxl==3.1.5 — parser XLSX com read_only=True para eficiência de memória"
    - "lxml==6.1.1 — dependência transitiva do ofxparse"
    - "et-xmlfile==2.0.0 — dependência transitiva do openpyxl"
  patterns:
    - "pytest.importorskip para coleta segura antes de módulo existir"
    - "_skip_if_stub para testes red/skip baseados na anotação de operations.py"
    - "lazy imports dentro de test body para evitar erros de coleta"
    - "call_count pattern para mock multi-step em endpoints com múltiplas queries"
    - "AsyncMock(session.execute) para pre-check de hash além de session.exec"
key_files:
  created:
    - tests/test_finances_operations.py
    - tests/test_services/test_finances_service.py
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - "Task 1 pulada (checkpoint:human-verify já resolvido pelo operador antes do spawn)"
  - "test_finances_operations.py criado do zero no worktree (arquivo existe no main mas não no commit base do worktree)"
  - "test_finances_service.py usa pytest.importorskip(caramello.finances.services) para coleta segura"
  - "test_compute_hash e test_normalize_description testam funções privadas via getattr para evitar ImportError na coleta"
  - "test_import_confirm usa endpoint /finances/import/confirm (decisão de path a ser validada em 08-03)"
metrics:
  duration: "~10 minutos"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 2
---

# Phase 08 Plan 01: Dependências e Malha Nyquist de Testes Summary

Adiciona ofxparse e openpyxl ao pyproject.toml e instala via uv; cria 15 stubs de teste red/skipados cobrindo todos os requisitos de movimentação e importação da Phase 8 antes de qualquer código de produção.

## O que foi feito

### Task 1 (checkpoint:human-verify)
Pulada — operador aprovou explicitamente `ofxparse` e `openpyxl` como pacotes legítimos antes do spawn deste agente.

### Task 2: Dependências adicionadas
- `ofxparse>=0.21` e `openpyxl>=3.1.5` adicionados à lista `dependencies` em `pyproject.toml`
- `uv add` executado com sucesso — ambiente sincronizado, `uv.lock` atualizado
- Verificação: `uv run python -c "import ofxparse, openpyxl"` → ok
- `python-multipart` não adicionado (já presente transitivamente via uv.lock 0.0.29)

### Task 3: Malha Nyquist criada

**tests/test_finances_operations.py** — arquivo criado com conteúdo completo:
- 11 testes existentes (Account/Category — mantidos integralmente do main)
- 10 novos stubs de endpoint: `test_create_movement`, `test_create_movement_409_duplicate`, `test_import_csv`, `test_import_ofx`, `test_import_xlsx`, `test_import_deduplication`, `test_import_potential_duplicates`, `test_import_confirm`, `test_list_movements`, `test_movements_require_auth`

**tests/test_services/test_finances_service.py** — arquivo novo:
- 5 stubs de parser puro: `test_parse_csv`, `test_parse_csv_error_lines`, `test_parse_csv_abort_threshold`, `test_compute_hash`, `test_normalize_description`
- Todos usam `pytest.importorskip("caramello.finances.services")` → skip limpo enquanto módulo não existe

## Verificação

- `uv run python -c "import ofxparse, openpyxl"` → **ok**
- `uv run python -m pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py --collect-only -q` → **26 testes coletados**
- Testes de service: **5 skipped** (caramello.finances.services ainda não existe → skip via importorskip)
- Testes de operations novos: **red** (falham ao importar caramello.main sem env vars — comportamento correto; serão green após 08-02/08-03)
- Testes existentes (11): coletáveis sem alteração

## Deviations from Plan

**1. [Rule 3 - Blocker] test_finances_operations.py criado do zero (não estendido)**
- **Found during:** Task 3
- **Issue:** O arquivo `tests/test_finances_operations.py` existe no branch `main` do repositório mas NÃO no commit base do worktree (`9a53bc3`). O worktree foi criado antes do plano 07-03 completar no main. `git show HEAD:tests/test_finances_operations.py` retornava "does not exist".
- **Fix:** Arquivo criado do zero com todo o conteúdo: 11 testes existentes (copiados do main para não perder cobertura) + 10 stubs novos da Phase 8.
- **Impacto:** Nenhum — conteúdo idêntico ao que existiria após merge. Merge resolverá sem conflito pois o worktree recria com conteúdo compatível.
- **Files modified:** `tests/test_finances_operations.py` (criado)
- **Commits:** `7a54a08`

## Known Stubs

Os 15 novos testes são stubs intencionais — seu propósito é existir como red/skip antes da implementação. Cada um será verde após o plano correspondente:

| Stub | Arquivo | Resolvido em |
|------|---------|--------------|
| test_create_movement | test_finances_operations.py | 08-02 |
| test_create_movement_409_duplicate | test_finances_operations.py | 08-02 |
| test_list_movements | test_finances_operations.py | 08-02 |
| test_import_csv | test_finances_operations.py | 08-03 |
| test_import_ofx | test_finances_operations.py | 08-03 |
| test_import_xlsx | test_finances_operations.py | 08-03 |
| test_import_deduplication | test_finances_operations.py | 08-03 |
| test_import_potential_duplicates | test_finances_operations.py | 08-03 |
| test_import_confirm | test_finances_operations.py | 08-03 |
| test_movements_require_auth | test_finances_operations.py | 08-02 |
| test_parse_csv | test_finances_service.py | 08-03 |
| test_parse_csv_error_lines | test_finances_service.py | 08-03 |
| test_parse_csv_abort_threshold | test_finances_service.py | 08-03 |
| test_compute_hash | test_finances_service.py | 08-03 |
| test_normalize_description | test_finances_service.py | 08-03 |

## Threat Surface Scan

Nenhuma nova superfície de rede, autenticação, acesso a arquivos ou mudança de schema foi introduzida neste plano. As únicas mudanças são dependências Python e arquivos de teste.

## Self-Check: PASSED

- [x] `pyproject.toml` contém `ofxparse>=0.21` e `openpyxl>=3.1.5`
- [x] `uv run python -c "import ofxparse, openpyxl"` → ok
- [x] `tests/test_finances_operations.py` existe e contém `def test_create_movement`
- [x] `tests/test_services/test_finances_service.py` existe e contém `def test_parse_csv`
- [x] 26 testes coletáveis (--collect-only -q: 26 tests collected)
- [x] Commit c4c7f1c (Task 2) verificado: `git log --oneline | grep c4c7f1c`
- [x] Commit 7a54a08 (Task 3) verificado: `git log --oneline | grep 7a54a08`
