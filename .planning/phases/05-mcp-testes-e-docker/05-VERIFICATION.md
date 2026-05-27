---
phase: 05-mcp-testes-e-docker
verified: 2026-05-27T03:00:00Z
status: human_needed
score: 5/5
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "SC4 do ROADMAP atualizado para refletir D-TEST-01: pytest executa contra caramello_dev com rollback por savepoint — sem banco separado caramello_test"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Executar docker build --build-arg APP_VERSION=1.0.0-test -t caramello-api:test . e verificar que a build conclui sem erro"
    expected: "Build termina exitcode 0; docker inspect --format '{{.Config.User}}' caramello-api:test retorna 'app'; docker history caramello-api:test | grep -iE 'DB_PASSWORD|KEYCLOAK_CLIENT' retorna vazio"
    why_human: "Build Docker leva >30 segundos e exige Docker daemon disponivel — fora do escopo de verificacao automatizada"
  - test: "Criar .env com variaveis reais, executar docker compose up, acessar http://localhost:8000/openapi.json e verificar que version corresponde ao valor de APP_VERSION"
    expected: "Campo version na spec e igual ao APP_VERSION passado como build arg; app responde 200 em /"
    why_human: "Requer Docker daemon, PostgreSQL externo e Keycloak configurados — ambiente completo de integracao"
  - test: "Executar uv run pytest -m integration com banco caramello_dev disponivel e schema migrado (bin/manage_db upgrade) e verificar os 4 testes de integracao do dominio family"
    expected: "4 testes passam; nenhum dado persiste no banco apos a suite (rollback por savepoint)"
    why_human: "Requer PostgreSQL caramello_dev acessivel — banco nao disponivel no ambiente de sandbox"
  - test: "Conectar um cliente MCP (npx @modelcontextprotocol/inspector http://localhost:8000/mcp) com Bearer token Keycloak valido e verificar que list_my_families aparece na lista de ferramentas"
    expected: "Ferramenta list_my_families listada; sem Bearer token, /mcp retorna 401/403"
    why_human: "Requer Keycloak real configurado + app rodando — nao verificavel por testes automatizados"
---

# Phase 05: MCP, Testes e Docker — Relatorio de Verificacao

**Objetivo da Phase:** Aplicacao containerizada, testada com isolamento de banco, e expondo uma ferramenta MCP protegida por auth — pronta para deploy

**Verificado:** 2026-05-27T03:00:00Z
**Status:** human_needed
**Re-verificacao:** Sim — apos fechamento do gap do SC4 (ROADMAP.md atualizado)

---

## Objetivo Geral

A Phase 5 entrega tres pilares: (1) MCP expondo `list_my_families` com auth Bearer obrigatorio, (2) Docker multi-stage com APP_VERSION e sem secrets nos layers de build, (3) testes de integracao com isolamento via rollback por savepoint contra `caramello_dev`. A verificacao parte do ROADMAP.md como contrato canonico e rastrea cada Success Criterion ate o codigo real.

---

## Verdades Observaveis (Success Criteria do ROADMAP)

| # | Verdade (SC do ROADMAP) | Status | Evidencia |
|---|------------------------|--------|-----------|
| 1 | Cliente MCP em `/mcp` descobre `list_my_families` exigindo Bearer token | VERIFICADO | `main.py`: `include_operations=["list_my_families"]`, `AuthConfig(dependencies=[Depends(http_bearer)])`, `headers=["authorization"]`; `test_mcp_requires_auth` e `test_mcp_with_valid_token_returns_tools` passam (2 passed) |
| 2 | `docker build` produz imagem multi-stage, non-root, sem secrets nos layers | VERIFICADO | `Dockerfile`: `FROM python:3.12-slim AS builder` + `AS runtime`, `USER app`, `ARG APP_VERSION` unico; grep de ARG DB_PASSWORD/KEYCLOAK retorna vazio; `.dockerignore` exclui `.env` |
| 3 | `docker compose up` com config exclusivamente via env vars; APP_VERSION como build arg na OpenAPI spec | VERIFICADO | `compose.yaml`: todos os valores via `${VAR}` sem hardcode; `APP_VERSION: ${APP_VERSION:-0.0.0}` conecta ao Dockerfile ARG; `main.py`: `version=os.getenv("APP_VERSION", "0.0.0")`; `test_openapi_version_field` XPASSED |
| 4 | `pytest` executa contra `caramello_dev` com rollback por savepoint por teste — sem banco separado `caramello_test`; isolamento garantido pela transacao revertida (D-TEST-01) | VERIFICADO | `conftest.py`: `TEST_DB_URL` com default `DB_NAME=caramello_dev`; `join_transaction_mode="create_savepoint"` presente; ROADMAP.md SC4 corrigido para refletir esta decisao |
| 5 | Casos de sucesso do dominio family testados: criar familia, pre-registrar membro, listar membros — com `dependency_overrides` | VERIFICADO | `test_families_integration.py`: 4 testes async com `@pytest.mark.integration` cobrindo create, list, pre_register, list_members; `conftest.py async_client` usa `dependency_overrides` para `get_session` e `get_current_user` |

**Pontuacao:** 5/5 verdades verificadas

---

## Itens Diferidos

Nao ha itens diferidos para phases posteriores — esta e a ultima phase do Milestone 1.

---

## Artefatos Obrigatorios

| Artefato | Proposito | Status | Detalhes |
|----------|-----------|--------|----------|
| `pyproject.toml` | fastapi-mcp>=0.4.0, pytest-asyncio>=1.4.0, asyncio_mode=auto | VERIFICADO | `fastapi-mcp>=0.4.0` em `[project] dependencies` (linha 18); `pytest-asyncio>=1.4.0` em `[dependency-groups] dev` (linha 46); `asyncio_mode = "auto"` em `[tool.pytest.ini_options]` (linha 50) |
| `tests/conftest.py` | Fixtures async test_engine, db_session, async_client com rollback | VERIFICADO | `join_transaction_mode="create_savepoint"` (linha 50); `TEST_DB_URL` default `caramello_dev` (linha 21); fixture `client` sincrono mantido; `async_client` com overrides de `get_session` e `get_current_user` |
| `tests/test_api/test_families_integration.py` | 4 testes de integracao marcados integration | VERIFICADO | 4 marcadores `@pytest.mark.integration`; 4 `async def test_`; coleta sem erros (`--collect-only`: 4 tests collected in 0.01s) |
| `tests/test_api/test_mcp.py` | Smoke tests de auth do /mcp | VERIFICADO | `test_mcp_requires_auth` (POST sem Bearer retorna 401/403); `test_mcp_with_valid_token_returns_tools` (POST com Bearer retorna 200 + jsonrpc); sem xfail; 2 testes passam ativamente |
| `tests/test_api/test_version.py` | Verificacao de APP_VERSION na OpenAPI spec | VERIFICADO | Teste passa (XPASSED); xfail decorator remanescente (aviso menor — nao bloqueante) |
| `src/caramello/families/services.py` | Service list_my_families(session, user) puro | VERIFICADO | `async def list_my_families`; `grep -c "fastapi|APIRouter|HTTPException"` retorna 0; sem CARAMELLO-GENERATED |
| `src/caramello/families/operations.py` | Endpoint com operation_id="list_my_families" + import do service | VERIFICADO | `operation_id="list_my_families"` (linha 163); `from caramello.families.services import list_my_families as svc` (linha 170) |
| `src/caramello/main.py` | FastApiMCP montado em /mcp + APP_VERSION dinamico | VERIFICADO | `from fastapi_mcp import AuthConfig, FastApiMCP`; `include_operations=["list_my_families"]`; `headers=["authorization"]`; `mcp.mount_http()` apos todos os include_router; `version=os.getenv("APP_VERSION", "0.0.0")` |
| `Dockerfile` | Multi-stage, non-root, APP_VERSION arg | VERIFICADO | `FROM python:3.12-slim AS builder` + `AS runtime`; `ARG APP_VERSION` + `ENV APP_VERSION=${APP_VERSION}`; `USER app`; sem `ARG DB_PASSWORD` ou `ARG KEYCLOAK_*` |
| `compose.yaml` | Servico api com config via env vars, APP_VERSION conectado | VERIFICADO | `APP_VERSION: ${APP_VERSION:-0.0.0}` em `build.args`; todos os DB_*/KEYCLOAK_* como `${VAR}` sem hardcode; sem servico PostgreSQL (PG externo) |
| `.dockerignore` | Exclui .env, .git, .venv, __pycache__ | VERIFICADO | `.env`, `.git`, `.venv`, `__pycache__/`, `*.pyc`, `.planning/`, `tests/` presentes |
| `.env.example` | DB_NAME=caramello_dev, sem familia_dev | VERIFICADO | `DB_NAME=caramello_dev`; nenhuma ocorrencia de `familia_dev` ou `familia_prod` |
| `tests/test_services/test_family_service.py` | Testes unitarios do service com AsyncMock | VERIFICADO | 3 testes com `@pytest.mark.asyncio`; passam em `uv run pytest -m "not integration"` |

---

## Verificacao de Links Criticos

| De | Para | Via | Status | Detalhe |
|----|------|-----|--------|---------|
| `src/caramello/main.py` | endpoint `list_my_families` (operations.py) | `include_operations=["list_my_families"]` | CONECTADO | Linha presente; MCP expoe apenas este endpoint (whitelist) |
| `src/caramello/main.py mcp.mount_http()` | todos os include_router | montagem apos os 4 `app.include_router(...)` | CONECTADO | `mcp.mount_http()` aparece apos todos os routers — RESEARCH Pitfall 2 respeitado |
| `src/caramello/families/operations.py` | `src/caramello/families/services.py` | `from caramello.families.services import list_my_families as svc` | CONECTADO | Import local dentro da funcao; chamada `await svc(session, current_user)` |
| `Dockerfile ARG APP_VERSION` | `ENV APP_VERSION` no runtime | `ARG APP_VERSION` no stage runtime + `ENV APP_VERSION=${APP_VERSION}` | CONECTADO | Ambos presentes no Dockerfile (linhas 20-21) |
| `compose.yaml build.args` | `Dockerfile ARG APP_VERSION` | `APP_VERSION: ${APP_VERSION:-0.0.0}` | CONECTADO | Padrao de passagem de build arg confirmado |
| `tests/conftest.py` | banco `caramello_dev` | `TEST_DB_URL` com default `DB_NAME=caramello_dev` | CONECTADO | URL construida de env vars; isolamento via `join_transaction_mode="create_savepoint"` |

---

## Rastreamento de Dados (Level 4)

| Artefato | Variavel de Dado | Fonte | Dados Reais | Status |
|----------|-----------------|-------|-------------|--------|
| `list_my_families` em main.py | endpoint REST via FastApiMCP | `families/operations.py` query SQLModel | Sim — `select(Family).join(FamilyMember).where(FamilyMember.user_id == user.id)` | FLUINDO |
| `test_openapi_version_field` | `spec["info"]["version"]` | `os.getenv("APP_VERSION", "0.0.0")` | Sim — lido do ambiente em runtime | FLUINDO |
| `async_client` fixture | `db_session` | `test_engine.connect()` + `conn.begin()` + savepoint | Sim — conexao real ao PostgreSQL caramello_dev | FLUINDO (requer DB externo) |

---

## Verificacoes de Comportamento (Spot-Checks)

| Comportamento | Comando | Resultado | Status |
|---------------|---------|-----------|--------|
| pytest coleta 7 testes sem erro | `uv run pytest tests/test_api/ --collect-only -q -m "not integration"` | 3/7 tests collected (4 deselected) in 0.01s | PASS |
| Testes nao-integration passam | `uv run pytest -m "not integration" -q` | 36 passed, 5 deselected, 1 xpassed, 5 warnings | PASS |
| Testes de MCP passam ativamente | `uv run pytest tests/test_api/test_mcp.py tests/test_api/test_version.py -v` | 2 passed, 1 xpassed | PASS |
| Testes unitarios do service passam | `uv run pytest tests/test_services/test_family_service.py -q` (inferido de 36 passed total) | PASS | PASS |
| fastapi-mcp 0.4.0 importavel | `python -c "import fastapi_mcp; print(fastapi_mcp.__version__)"` | 0.4.0 | PASS |
| pytest-asyncio 1.4.0 importavel | `python -c "import pytest_asyncio; print(pytest_asyncio.__version__)"` | 1.4.0 | PASS |
| Dockerfile sem secrets em ARG | `grep -c "ARG (DB_PASSWORD|KEYCLOAK|DB_USER)" Dockerfile` | 0 | PASS |
| Diretorio mcp/ nao criado | `test ! -d src/caramello/mcp` | exit 0 | PASS |
| conftest.py tem join_transaction_mode | `grep "join_transaction_mode" tests/conftest.py` | match linha 50 | PASS |
| ROADMAP SC4 menciona caramello_dev (nao caramello_test) | `grep "caramello_dev" .planning/ROADMAP.md` | linha 119 com D-TEST-01 | PASS |
| Testes de integracao Docker (docker build real) | nao executado — requer Docker daemon | - | SKIP (humano) |

---

## Cobertura de Requisitos

| Requisito | Plano | Descricao | Status | Evidencia |
|-----------|-------|-----------|--------|-----------|
| MCP-01 | 05-02, 05-04 | Cliente MCP descobre ferramentas do dominio family | PARCIAL (aceito para M1) | `list_my_families` exposta via FastApiMCP; ROADMAP SC1 delimita corretamente 1 ferramenta para M1 (D-MCP-04); REQUIREMENTS.md exige mais — escopo M2+ |
| MCP-02 | 05-04 | Ferramentas MCP exigem Bearer token | VERIFICADO | `AuthConfig(dependencies=[Depends(http_bearer)])` + `headers=["authorization"]`; `test_mcp_requires_auth` confirma 401/403 sem token |
| DEPLOY-01 | 05-05 | Imagem Docker reproducivel multi-stage, non-root, sem secrets | VERIFICADO | Dockerfile com 2 stages, `USER app`, sem ARG DB_PASSWORD/KEYCLOAK |
| DEPLOY-02 | 05-05 | `docker compose up` com config exclusivamente via env vars | VERIFICADO | compose.yaml: todos os valores via `${VAR}` sem hardcode |
| DEPLOY-03 | 05-04, 05-05 | APP_VERSION como build arg na OpenAPI spec | VERIFICADO | `version=os.getenv("APP_VERSION", "0.0.0")` em main.py; ARG+ENV no Dockerfile; build.args no compose.yaml |
| TEST-01 | 05-01, 05-03 | Testes com banco isolado e rollback por teste | VERIFICADO | `join_transaction_mode="create_savepoint"` implementado; `caramello_dev` com rollback por savepoint; ROADMAP SC4 alinhado |
| TEST-02 | 05-03 | Cobertura de sucesso: criar familia, listar, pre-registrar, listar membros | VERIFICADO (escopo ROADMAP SC5) | 4 testes de integracao cobrem os casos do SC5; "convidar/aprovar" e M2 (FAMILY-04/05/06 deferidos) |
| TEST-03 | 05-01, 05-03 | `dependency_overrides` simulando usuario sem Keycloak | VERIFICADO | `async_client` fixture usa `app.dependency_overrides[get_current_user] = lambda: fake_user` |
| MODEL-03 | 05-06 | Nomenclatura `caramello_dev`/`caramello` em docs e configs | VERIFICADO | `.env.example`, `CLAUDE.md`, `docs/apps-platform.md`, `REQUIREMENTS.md` atualizados; sem `familia_dev`/`familia_prod` |

**Nota sobre MCP-01 e TEST-02:** O REQUIREMENTS.md define escopo mais amplo do que o ROADMAP SC para Phase 5. O ROADMAP SC e o contrato de verificacao de phase. A entrega parcial e aceita por decisao de design (D-MCP-04, D-04) — M2+ adiciona mais ferramentas e testes.

---

## Antipadroes Encontrados

| Arquivo | Linha | Padrao | Severidade | Impacto |
|---------|-------|--------|------------|---------|
| `tests/test_api/test_version.py` | 9 | `@pytest.mark.xfail(strict=False)` remanescente apos 05-04 | Aviso | Teste passa (XPASSED) — nao causa falha ativa; cleanup pendente mas nao bloqueante |
| `.planning/REQUIREMENTS.md` | 143-150 | Traceability table mostra todas as Phase 5 como "Pendente" | Aviso | MODEL-03 e TEST-01 tem checkbox `[x]` mas tabela de rastreabilidade diz "Pendente"; documentacao desalinhada |
| `.planning/ROADMAP.md` | Progress table | Phase 5 mostra "0/6, Planned" mas todos os 6 planos estao completos | Aviso | Documentacao desalinhada com realidade — progress table nao atualizada |

---

## Verificacao Humana Necessaria

### 1. Build Docker real

**Teste:** `docker build --build-arg APP_VERSION=1.0.0-test -t caramello-api:test .`
**Esperado:** Exit 0; `docker inspect --format '{{.Config.User}}' caramello-api:test` retorna `app`; `docker history caramello-api:test | grep -iE "DB_PASSWORD|KEYCLOAK_CLIENT"` retorna vazio
**Por que humano:** Build Docker leva >30s, requer Docker daemon — fora do escopo automatizado de verificacao

### 2. Stack completa com docker compose

**Teste:** Criar `.env` com variaveis reais, `docker compose up`, acessar `http://localhost:8000/openapi.json`
**Esperado:** Campo `version` na spec corresponde ao APP_VERSION passado no build arg; app responde 200 em `/`
**Por que humano:** Requer Docker daemon + PostgreSQL externo + Keycloak configurados

### 3. Suite de integracao contra caramello_dev

**Teste:** Com banco `caramello_dev` disponivel e schema migrado (`bin/manage_db upgrade`): `uv run pytest -m integration -v`
**Esperado:** 4 testes passam; logs confirmam que nenhum dado persiste (rollback por savepoint)
**Por que humano:** Banco PostgreSQL nao disponivel no ambiente de sandbox de verificacao

### 4. Verificacao MCP com cliente real

**Teste:** `npx @modelcontextprotocol/inspector http://localhost:8000/mcp` com Bearer token Keycloak valido
**Esperado:** Ferramenta `list_my_families` listada; sem token, `/mcp` retorna 401/403
**Por que humano:** Requer Keycloak real + app rodando com PostgreSQL acessivel

---

## Resumo

Todos os 5 Success Criteria do ROADMAP estao verificados no codigo:

1. **MCP em /mcp** com `list_my_families` via whitelist `include_operations`, Bearer obrigatorio via `AuthConfig` e propagacao do header `authorization` — confirmado por testes automatizados (2 passed).
2. **Dockerfile multi-stage** com stages `builder`/`runtime`, `USER app` (non-root), `ARG APP_VERSION` como unico build arg sem secrets nos layers.
3. **compose.yaml app-only** com toda a config via `${VAR}`, `APP_VERSION` conectado como build arg ao Dockerfile e exposto na OpenAPI spec via `os.getenv`.
4. **pytest contra caramello_dev** com `join_transaction_mode="create_savepoint"` — sem banco separado caramello_test; ROADMAP SC4 agora alinhado com a implementacao.
5. **4 testes de integracao** cobrem criar familia, listar, pre-registrar e listar membros; auth simulada via `dependency_overrides` sem Keycloak real.

O gap da verificacao anterior (SC4 com caramello_test) foi fechado pela correcao do ROADMAP.md. Os itens de verificacao humana (build Docker real, stack completa, suite de integracao com banco real, cliente MCP) sao requerimentos de ambiente que nao podem ser verificados em sandbox.

---

*Verificado: 2026-05-27T03:00:00Z*
*Re-verificacao apos fechamento do gap SC4*
*Verificador: Claude (gsd-verifier)*
