---
phase: 05-mcp-testes-e-docker
plan: "01"
subsystem: testing-infrastructure
tags: [pytest, fastapi-mcp, pytest-asyncio, fixtures, integration-tests]
dependency_graph:
  requires: []
  provides: [test-infrastructure, async-fixtures, test-stubs]
  affects: [05-02, 05-03, 05-04, 05-05, 05-06]
tech_stack:
  added: [fastapi-mcp>=0.4.0, pytest-asyncio>=1.4.0]
  patterns: [async-fixtures-with-savepoint-rollback, xfail-stubs, dependency-overrides]
key_files:
  created:
    - tests/test_api/test_version.py
    - tests/test_api/test_mcp.py
    - tests/test_api/test_families_integration.py
  modified:
    - pyproject.toml
    - uv.lock
    - tests/conftest.py
decisions:
  - "Banco de testes usa caramello_dev (mesmo banco de dev) — isolamento via rollback por savepoint, não banco separado"
  - "asyncio_mode=auto configurado em pyproject.toml para evitar ScopeMismatch no pytest-asyncio 1.4.0"
  - "Testes test_version.py e test_mcp.py marcados xfail(strict=False) para não causar falhas ativas até 05-04"
metrics:
  duration: "3 minutos"
  completed: "2026-05-27"
  tasks_completed: 3
  files_created: 3
  files_modified: 3
---

# Phase 05 Plan 01: Infraestrutura de Testes — SUMMARY

**One-liner:** Instalação de fastapi-mcp e pytest-asyncio com fixtures async de rollback por savepoint contra caramello_dev e stubs xfail coletáveis pelo pytest.

## O que foi feito

Wave 0 da Phase 5 destravou todas as waves seguintes instalando as dependências obrigatórias e criando a infraestrutura de testes async.

### Task 1: Dependências e configuração pytest

- `fastapi-mcp 0.4.0` adicionado em `[project] dependencies` do pyproject.toml
- `pytest-asyncio 1.4.0` adicionado em `[dependency-groups] dev`
- `asyncio_mode = "auto"` configurado em `[tool.pytest.ini_options]` — obrigatório para pytest-asyncio 1.4.0
- Marcador de integration atualizado: agora referencia `caramello_dev` em vez de Keycloak
- `uv.lock` regenerado com as novas dependências

### Task 2: Fixtures async no conftest.py

O `conftest.py` foi expandido mantendo o fixture `client` síncrono existente intacto e adicionando:

- `TEST_DB_URL`: URL construída de variáveis de ambiente com fallback padrão para `caramello_dev`
- `test_engine` (scope=session): engine async compartilhado entre todos os testes da sessão
- `db_session`: sessão async com `join_transaction_mode="create_savepoint"` para garantir rollback por teste com asyncpg
- `async_client`: cliente HTTP async com overrides de `get_session` e `get_current_user` injetando fake_user

### Task 3: Arquivos de teste (stubs verificáveis)

Criados 3 arquivos de teste coletáveis pelo pytest:

- `test_version.py`: verifica `APP_VERSION` na OpenAPI spec; marcado `@pytest.mark.xfail(strict=False)` até 05-04
- `test_mcp.py`: smoke tests de auth no `/mcp`; ambos marcados `@pytest.mark.xfail(strict=False)` até 05-04
- `test_families_integration.py`: 4 testes marcados `@pytest.mark.integration` cobrindo create_family, list_my_families, pre_register_member e list_members contra banco real com rollback

## Commits

| Task | Descrição | Commit |
|------|-----------|--------|
| 1 | Instala fastapi-mcp e pytest-asyncio, configura asyncio_mode | 9aec796 |
| 2 | Adiciona fixtures async ao conftest com rollback por savepoint | 5f30dba |
| 3 | Cria stubs de testes verificáveis para versão, MCP e integração | 5538d94 |

## Deviations from Plan

None - o plano foi executado exatamente como escrito.

## Known Stubs

| Arquivo | Stub | Razão |
|---------|------|-------|
| `tests/test_api/test_version.py` | `test_openapi_version_field` com xfail | APP_VERSION não é dinâmico ainda — resolvido em 05-04 |
| `tests/test_api/test_mcp.py` | `test_mcp_requires_auth` com xfail | Endpoint /mcp não montado ainda — resolvido em 05-04 |
| `tests/test_api/test_mcp.py` | `test_mcp_with_valid_token_returns_tools` com xfail | MCP não montado ainda — resolvido em 05-04 |

Os stubs são intencionais: não impedem o objetivo do plano (infraestrutura de testes funcional) e serão ativados pelo plano 05-04.

## Threat Surface Scan

Nenhuma nova superfície de rede ou auth introduzida. O `TEST_DB_URL` lê credenciais de variáveis de ambiente sem secrets hardcoded (T-05-02 mitigado). O `join_transaction_mode="create_savepoint"` garante que nenhum dado de teste persiste no banco (T-05-01 mitigado).

## Self-Check: PASSED

- [x] `tests/conftest.py` — FOUND
- [x] `tests/test_api/test_version.py` — FOUND
- [x] `tests/test_api/test_mcp.py` — FOUND
- [x] `tests/test_api/test_families_integration.py` — FOUND
- [x] Commit 9aec796 — FOUND
- [x] Commit 5f30dba — FOUND
- [x] Commit 5538d94 — FOUND
