---
phase: 05
slug: mcp-testes-e-docker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 + pytest-asyncio 1.4.0 (a instalar no Wave 0) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -m "not integration"` |
| **Full suite command** | `uv run pytest` (requer `caramello_dev` disponível) |
| **Estimated runtime** | ~5s (quick) / ~30s (full) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -m "not integration"`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-W0-01 | setup | 0 | TEST-01, TEST-02, TEST-03 | — | N/A | fixture | `uv run pytest tests/ -x -m "not integration"` | ❌ W0: conftest.py | ⬜ pending |
| 05-MCP-01 | mcp | MCP | MCP-01 | T-mcp-01 | MCP expõe só `list_my_families` via whitelist | smoke manual | `docker run ... /mcp` + cliente MCP | ❌ W0 | ⬜ pending |
| 05-MCP-02 | mcp | MCP | MCP-02 | T-mcp-02 | `/mcp` sem Bearer retorna 401/403 | integration | `uv run pytest tests/test_api/test_mcp.py -m integration -x` | ❌ W0 | ⬜ pending |
| 05-DEPLOY-01 | docker | Docker | DEPLOY-01 | T-docker-01 | Sem secrets nos layers de build | smoke manual | `docker build --build-arg APP_VERSION=test .` | ❌ W0 | ⬜ pending |
| 05-DEPLOY-02 | docker | Docker | DEPLOY-02 | — | Config só via env vars | smoke manual | `docker compose up` com `.env` | ❌ W0 | ⬜ pending |
| 05-DEPLOY-03 | docker | Docker | DEPLOY-03 | — | `APP_VERSION` em `/openapi.json` | integration | `uv run pytest tests/test_api/test_version.py -x` | ❌ W0 | ⬜ pending |
| 05-TEST-02 | tests | Tests | TEST-02, TEST-03 | — | dependency_overrides simula auth sem Keycloak | integration | `uv run pytest tests/test_api/test_families_integration.py -m integration -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — adicionar fixtures `test_engine`, `db_session`, `async_client` com rollback por teste (`join_transaction_mode="create_savepoint"`)
- [ ] `tests/test_api/test_families_integration.py` — testes de integração family (TEST-02, TEST-03)
- [ ] `tests/test_api/test_mcp.py` — smoke test de auth no `/mcp` (MCP-02)
- [ ] `tests/test_api/test_version.py` — verificação de `APP_VERSION` em `/openapi.json` (DEPLOY-03)
- [ ] `uv add fastapi-mcp && uv add --group dev pytest-asyncio` — dependências obrigatórias
- [ ] Adicionar `asyncio_mode = "auto"` em `[tool.pytest.ini_options]` no `pyproject.toml`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `/mcp` descobre ferramenta `list_my_families` | MCP-01 | Requer cliente MCP real (ex: Claude Desktop ou mcp-inspector) | `npx @modelcontextprotocol/inspector http://localhost:8000/mcp` com Bearer token válido |
| `docker compose up` inicia app corretamente | DEPLOY-02 | Requer Docker Engine com env vars configuradas | Criar `.env` com vars, rodar `docker compose up`, acessar `http://localhost:8000/docs` |
| Operador cria banco `caramello_dev` (D-NAMING-01) | infra | Renomeação é operacional — não automatizável sem migração de dados | `bin/setup_db` com `DB_NAME=caramello_dev` no `.env` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
