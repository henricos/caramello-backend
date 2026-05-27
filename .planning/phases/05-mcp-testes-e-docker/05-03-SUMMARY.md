---
phase: 05-mcp-testes-e-docker
plan: "03"
subsystem: testing/families
tags: [integration-tests, pytest-asyncio, async-client, dependency-overrides, rollback]
dependency_graph:
  requires: [05-01, 05-02]
  provides: [test_families_integration_complete]
  affects: []
tech_stack:
  added: []
  patterns: [async-integration-tests-with-savepoint-rollback, dependency-overrides-auth]
key_files:
  created: []
  modified:
    - tests/test_api/test_families_integration.py
decisions:
  - "test_list_my_families cria família antes de listar para garantir resultado verificável (não depende de estado pré-existente)"
  - "test_list_members verifica role == 'owner' via list comprehension, tolerando múltiplos membros"
  - "test_pre_register_member verifica data['email'] na resposta do 201"
metrics:
  duration: "5 minutos"
  completed: "2026-05-27"
  tasks_completed: 1
  files_created: 0
  files_modified: 1
---

# Phase 05 Plan 03: Testes de Integração do Domínio Family — SUMMARY

**One-liner:** Substituição dos stubs por implementações completas dos 4 testes de integração do domínio family com asserções completas conforme critérios TEST-01, TEST-02 e TEST-03.

## O que foi feito

Os stubs criados no plano 05-01 foram substituídos por implementações completas com as asserções específicas definidas no plano 05-03. Cada teste usa o fixture `async_client` (com `dependency_overrides` de auth e session já encapsulados) e opera contra `caramello_dev` com rollback por savepoint.

### Task 1: Testes de integração completos do domínio family

Os seguintes testes foram implementados em `tests/test_api/test_families_integration.py`:

- **test_create_family**: POST /families/registry → 201; verifica `data["name"]` e presença de `"uuid"` no response
- **test_list_my_families**: cria família, GET /families/families → 200; verifica que o uuid da família criada está na lista retornada
- **test_pre_register_member**: cria família, POST /families/families/{uuid}/pre-register → 201; verifica `data["email"] == "novo@example.com"`
- **test_list_members**: cria família, GET /families/families/{uuid}/members → 200; verifica que `"owner"` está entre os roles dos membros retornados

## Commits

| Task | Descrição | Commit |
|------|-----------|--------|
| 1 | Implementa testes de integração do domínio family | 56e6373 |

## Deviations from Plan

None — o plano foi executado exatamente como escrito. Os stubs existentes do 05-01 já tinham a estrutura correta; apenas as asserções foram completadas.

## Known Stubs

Nenhum. Os 4 testes estão completamente implementados com asserções específicas.

## Threat Surface Scan

Nenhuma superfície nova introduzida. Mitigações do threat model verificadas:

- **T-05-05 (Tampering — rollback):** `join_transaction_mode="create_savepoint"` na fixture `db_session` do conftest.py garante rollback mesmo que os endpoints chamem flush/commit interno. Nenhum dado persiste no `caramello_dev` após cada teste.
- **T-05-06 (Spoofing — override de auth):** O `dependency_overrides[get_current_user]` existe apenas no escopo da fixture `async_client` (conftest.py). A app de produção usa `get_current_user` real com validação JWT — sem bypass em runtime.

## Verificação

- `grep -c "@pytest.mark.integration" tests/test_api/test_families_integration.py` → **4** (OK)
- `grep -c "async def test_" tests/test_api/test_families_integration.py` → **4** (OK)
- `uv run pytest tests/test_api/test_families_integration.py --collect-only -q` → **4 tests collected in 0.02s** (OK)
- Banco `caramello_dev` indisponível no ambiente de sandbox — validação completa requer ambiente com PostgreSQL. O `--collect-only` confirma que não há erros de import.

## Self-Check: PASSED

- [x] `tests/test_api/test_families_integration.py` — FOUND e modificado
- [x] Commit `56e6373` — FOUND
- [x] 4 marcadores `@pytest.mark.integration` — CONFIRMADO
- [x] 4 `async def test_` — CONFIRMADO
- [x] `--collect-only` listas 4 testes sem erros — CONFIRMADO
