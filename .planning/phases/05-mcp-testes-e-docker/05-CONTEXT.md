# Phase 5: MCP, Testes e Docker - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Entregar a app containerizada, testada com isolamento de banco, e expondo uma ferramenta MCP protegida por auth — fundação prática para as três frentes de infraestrutura do M1.

**Entregáveis concretos:**
- `Dockerfile` multi-stage, non-root user, sem secrets nos layers de build
- `compose.yaml` — app only (PG externo), config via env vars, `APP_VERSION` como build arg exposto no campo `version` da OpenAPI spec
- Infraestrutura de testes: banco real `caramello_test`, transaction rollback por teste, `@pytest.mark.integration` para coexistir com os unit tests AsyncMock existentes
- `bin/manage_db --env test` para gerenciar `caramello_test` (reset + migrate)
- 1 ferramenta MCP de exemplo (`get_my_families`) — implementação manual em `src/caramello/mcp/tools.py`, chamando services extraídos de `operations.py`
- Docs/nomenclatura de banco atualizados: `caramello` (prod), `caramello_dev` (dev), `caramello_test` (test)

**Fora de escopo desta fase:**
- Ferramentas MCP de escrita (create_family, pre_register_member) — M2+
- Ferramentas MCP adicionais de leitura — M2+ quando os services estiverem maduros
- `GET /health` com ping ao banco (OPS-01 v2 requirements) — deferido
- Docker compose com PostgreSQL incluso (compose self-contained) — não necessário; PG já na infra existente
- CI pipeline GitHub Actions — v2 requirements

</domain>

<decisions>
## Implementation Decisions

### MCP — Integração e Ferramentas

- **D-MCP-01:** Servidor MCP montado na mesma app FastAPI via `fastapi-mcp`, exposto em `/mcp`. Não é um serviço separado — mesma app, mesmo processo, sem overhead operacional extra.

- **D-MCP-02:** Ferramentas MCP implementadas **manualmente** em `src/caramello/mcp/tools.py`. O `fastapi-mcp` não auto-gera ferramentas a partir dos endpoints REST — a assinatura das ferramentas MCP é diferente da assinatura REST. Reutilização via services, não via exposição de routers.

- **D-MCP-03:** Lógica de negócio extraída de `families/operations.py` para `families/services.py`. As ferramentas MCP e os endpoints REST chamam os mesmos `services.py`. Padrão: services recebem `AsyncSession` + `User` como parâmetros; operações de query ficam em services, não em operations ou tools.

- **D-MCP-04:** Phase 5 implementa **1 ferramenta MCP de exemplo**: `get_my_families` — retorna as famílias do usuário autenticado. Serve como prova de conceito e estabelece o padrão. Implementação completa das ferramentas MCP fica para quando os services de todos os domínios estiverem maduros (M2+).

- **D-MCP-05:** Autenticação no MCP usa o mesmo mecanismo dos endpoints REST — Bearer token Keycloak validado via `get_current_user()`. A ferramenta recebe o `User` autenticado pelo mesmo mecanismo de dependency injection.

### Testes — Infraestrutura e Isolamento

- **D-TEST-01:** Banco real `caramello_test` para testes de integração. Banco separado de `caramello_dev` — não contamina o banco de desenvolvimento em nenhuma circunstância.

- **D-TEST-02:** Isolamento via **transaction rollback por teste**. Cada teste abre uma transação, executa as operações, e reverte ao final — banco sempre limpo entre testes sem custo de truncate/recreate. Requer `pytest-asyncio` e fixtures async com `AsyncSession`.

- **D-TEST-03:** `bin/manage_db --env test` gerencia o banco `caramello_test`. Comandos: `bin/manage_db reset --env test` (DROP + CREATE + migrate), `bin/manage_db migrate --env test` (só alembic upgrade head). Pytest assume banco já preparado — não gerencia o ciclo de vida do banco.

- **D-TEST-04:** Testes de integração marcados com `@pytest.mark.integration`. Coexistem com os unit tests existentes (AsyncMock em `test_family_operations.py`, `test_auth.py`). Execução:
  - `uv run pytest` — roda todos os testes (unit + integration; requer PG com `caramello_test`)
  - `uv run pytest -m 'not integration'` — roda só unit tests (sem PG necessário)

- **D-TEST-05:** Testes de integração do domínio family cobrem (TEST-02): criar família, pré-registrar membro, listar membros. Usam `dependency_overrides` para simular usuário autenticado (TEST-03) + banco real `caramello_test` para as queries.

### Docker — Containerização

- **D-DOCKER-01:** `Dockerfile` multi-stage (builder + runtime), non-root user, sem secrets nos layers de build. Padrão inspirado no `hiring-pipeline`: `ARG APP_VERSION` no Dockerfile, injetado via `docker build --build-arg APP_VERSION=x.y.z`.

- **D-DOCKER-02:** `compose.yaml` entrega apenas a app (PG externo). Configuração exclusivamente via variáveis de ambiente — sem valores hardcoded. Conteúdo alinhado com o exemplo já em `docs/deploy.md` (imagem `ghcr.io/henricos/caramello-api:latest`).

- **D-DOCKER-03:** `APP_VERSION` aparece no campo `version` da OpenAPI spec — `FastAPI(version=os.getenv("APP_VERSION", "0.0.0"))`. Visível em `/openapi.json` e na UI Swagger. Sem endpoint de health separado nesta fase.

### Nomenclatura de Banco

- **D-NAMING-01:** Corrigir divergência entre docs e realidade. Os bancos reais se chamam:
  - `caramello` (produção)
  - `caramello_dev` (desenvolvimento)
  - `caramello_test` (testes — a criar)

  Atualizar: `.env.example`, `REQUIREMENTS.md` (referências a `familia_dev`/`familia_prod`), e `docs/apps-platform.md` §5.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos e Roadmap
- `.planning/REQUIREMENTS.md` §MCP-01, §MCP-02, §DEPLOY-01, §DEPLOY-02, §DEPLOY-03, §TEST-01, §TEST-02, §TEST-03 — requisitos que esta fase implementa
- `.planning/ROADMAP.md` §Phase 5 — success criteria desta fase

### Contexto de Fases Anteriores
- `.planning/phases/04-dom-nio-family/04-CONTEXT.md` §D-05, §D-06, §D-07 — padrão operations.py (CARAMELLO-GENERATED: implemented, router separado, Depends) que a extração para services.py deve preservar
- `.planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-CONTEXT.md` §D-01, §D-02, §D-04, §D-05 — configuração Keycloak e `get_current_user()` que as ferramentas MCP reutilizam

### Código Existente (base para implementação)
- `src/caramello/families/operations.py` — lógica de negócio a extrair para `families/services.py`
- `src/caramello/shared/auth.py` — `get_current_user()` que ferramentas MCP devem reutilizar
- `src/caramello/shared/database.py` — `get_session()` e `AsyncSession`
- `src/caramello/main.py` — onde montar o servidor MCP (lifespan, include_router pattern)
- `tests/conftest.py` — fixtures a evoluir para suportar banco real + rollback por teste
- `tests/test_family_operations.py` — padrão AsyncMock que os novos testes de integração convivem com

### Infraestrutura
- `bin/manage_db` — evoluir para aceitar `--env test` (criar/resetar `caramello_test`)
- `alembic/` — migrations aplicadas no `caramello_test` via `bin/manage_db --env test`
- `.env.example` — atualizar nomenclatura de banco (`familia_dev` → `caramello_dev`)
- `docs/deploy.md` — referência para o conteúdo do `compose.yaml` de produção
- `docs/apps-platform.md` §5 — atualizar com nomenclatura real dos bancos

### Qualidade
- `pyproject.toml` — configuração ruff/mypy strict; todo código desta fase deve passar

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/caramello/shared/auth.py` — `get_current_user()`: já implementado e testado; ferramentas MCP e testes usam via `dependency_overrides`
- `src/caramello/families/operations.py` — lógica de `list_families`, `get_family_detail`, `list_members` a ser extraída para `services.py` (antes de escrever a ferramenta MCP `get_my_families`)
- `src/caramello/shared/database.py` — `get_session()` + `AsyncSession` para fixtures de testes com banco real
- `tests/test_family_operations.py` — padrão `dependency_overrides + AsyncMock` estabelecido; novos testes de integração seguem o mesmo padrão de override de auth mas substituem AsyncMock por sessão real

### Established Patterns
- **CARAMELLO-GENERATED: implemented** — `operations.py` tem essa anotação; services.py extraído dela é código manual, sem anotação gerada
- **ruff + mypy strict** — todo código novo deve passar em `ruff check src/` e `mypy src/`
- **AsyncSession via Depends** — todos os endpoints e services usam `AsyncSession = Depends(get_session)` — ferramentas MCP seguem o mesmo padrão
- **pytest marcações** — `@pytest.mark.integration` para testes que dependem de PG real

### Integration Points
- `src/caramello/main.py`: ponto de montagem do servidor MCP (`fastapi-mcp` integra no lifespan ou como middleware)
- `pyproject.toml`: adicionar `fastapi-mcp` às `dependencies` e `pytest-asyncio` às dev dependencies
- `bin/manage_db`: ponto de extensão para `--env test` (lê `DB_NAME_TEST` ou hardcoda `caramello_test`)
- `alembic/env.py`: verificar que aceita `DATABASE_URL` injetado para `caramello_test` (deve funcionar via env var já existente)

</code_context>

<specifics>
## Specific Ideas

- **Services.py antes do MCP:** Extrair `families/services.py` é pre-requisito da ferramenta MCP. Não implementar a ferramenta antes de ter o service extraído.
- **1 ferramenta como exemplo:** `get_my_families` é o exemplo canônico. A ferramenta deve ter docstring clara — é ela que o agente MCP lê para entender o que a ferramenta faz.
- **compose.yaml de prod alinhado com docs/deploy.md:** O `compose.yaml` que Phase 5 cria deve ser consistente com o exemplo já documentado em `docs/deploy.md` — não criar variações desnecessárias.
- **`APP_VERSION=0.0.0` como fallback:** `os.getenv("APP_VERSION", "0.0.0")` — quando o container não recebe o build arg, a spec mostra `0.0.0` em vez de falhar.
- **bin/manage_db --env test:** Deve ler a URL do banco de teste ou construí-la a partir de variáveis de ambiente (ex.: `DB_NAME=caramello_test` com outras vars iguais ao dev). Documentar o comando em `docs/dev.md`.

</specifics>

<deferred>
## Deferred Ideas

- **Ferramentas MCP de escrita (M2+):** `create_family`, `pre_register_member`, e outras operações de escrita. Deferidas para quando os services de todos os domínios estiverem maduros.
- **Ferramentas MCP adicionais de leitura (M2+):** `get_family_details`, `get_family_members`, `get_my_profile`. Padrão estabelecido em Phase 5; expansão em M2.
- **`GET /health` com ping ao banco (OPS-01 v2):** Deferido para milestone posterior.
- **CI pipeline GitHub Actions (OPS-04 v2):** Rodar testes e linting no push — deferido para milestone posterior.
- **Docker compose com PostgreSQL (self-contained para dev):** PG já na infra existente do operador — não necessário nesta fase. Pode ser adicionado como `compose.override.yml` futuramente para facilitar onboarding.

</deferred>

---

*Phase: 5-MCP, Testes e Docker*
*Context gathered: 2026-05-26*
