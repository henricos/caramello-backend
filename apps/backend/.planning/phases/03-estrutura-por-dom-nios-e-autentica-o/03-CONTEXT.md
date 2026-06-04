# Phase 3: Estrutura por Domínios e Autenticação - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Reorganizar o código-fonte para arquitetura por domínios de negócio (`src/caramello/user/`, `src/caramello/family/`, `src/caramello/shared/`), evoluir o DSL generator para suportar o campo `domain` nos YAMLs de entidade e produzir output em `src/caramello/{domain}/`, introduzir o conceito de `dsl/operations/{domain}.yaml` para operações de negócio com geração de stubs protegidos por anotação, implementar a camada de autenticação Keycloak em `shared/auth.py` com validação JWT local via JWKS cacheado e provisioning just-in-time, e entregar o endpoint `GET /user/me` como primeira operação de negócio gerada e implementada.

**Entregável concreto:**
- `grep -r "models/" src/` retorna vazio — diretório `models/` e `api/generated/` removidos
- `src/caramello/user/` e `src/caramello/family/` contêm `models.py`, `router.py`, `operations.py` (com stub do `/user/me` implementado)
- `GET /user/me` com Bearer token Keycloak válido retorna `id`, `email`, `name`
- `GET /user/me` sem token retorna 401
- `GET /user/` (CRUD) sem token retorna 401 — todos os endpoints gerados exigem auth

**Fora de escopo desta fase:** endpoints do domínio `family` (Phase 4), MCP (Phase 5), Docker (Phase 5), testes isolados (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Configuração Keycloak

- **D-01:** Configuração via env vars em `Settings` (`src/caramello/core/config.py`). Adicionar campos: `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`. Realm confirmado: `caramello`. JWKS URL: `{KEYCLOAK_URL}/realms/caramello/protocol/openid-connect/certs`.
- **D-02:** Validação de audience (`aud` claim): o implementador deve verificar o valor real emitido pelo Keycloak da infra existente antes de decidir se valida `aud == client_id` ou omite a validação de audience inicialmente.
- **D-03:** Extração do nome do usuário para JIT provisioning: tentar claim `name` (OIDC padrão); se ausente ou vazio, usar `preferred_username` como fallback. Mapeamento de claims: `sub` → `idp_sub`, `email` → `email`, `name` (ou `preferred_username`) → `name`.

### Biblioteca JWT e cache JWKS

- **D-04:** Biblioteca: `PyJWT[crypto]` — adicionar via `uv add "PyJWT[crypto]"`. Não usar `python-jose` (CVEs registradas).
- **D-05:** Cache JWKS em memória: chaves buscadas uma vez na inicialização da app via FastAPI `lifespan`. Em caso de `kid` não encontrado durante validação (key rotation), re-busca as chaves do Keycloak antes de retornar 401. Sem dependência de `cachetools` — dict simples em módulo `shared/auth.py`.

### DSL generator — output por domínio e operações de negócio

- **D-06:** Adicionar campo `domain` às definições YAML das entidades. Mapeamento de domínios:
  - `User` → `domain: user` → output em `src/caramello/user/`
  - `Family`, `FamilyMember`, `FamilyInvitation` → `domain: family` → output em `src/caramello/family/`
- **D-07:** O generator produz por entidade, dentro do diretório do domínio: `models.py` (4 classes: Entity, EntityRead, EntityCreate, EntityUpdate) e `router.py` (CRUD completo: POST /, GET /, GET /{uuid}, PATCH /{uuid}, DELETE /{uuid}). Estrutura análoga ao atual — só muda o output path.
- **D-08:** Novo conceito DSL: `dsl/operations/{domain}.yaml` — define operações de negócio de um domínio (que podem envolver múltiplas entidades). O generator produz `src/caramello/{domain}/operations.py` com stubs de cada operação.
- **D-09:** Segurança de regeneração via anotação no topo do arquivo gerado:
  - `# CARAMELLO-GENERATED: stub` → pode sobrescrever livremente na próxima `bin/generate_code`
  - `# CARAMELLO-GENERATED: implemented` → generator pula este arquivo; desenvolvedor altera a anotação manualmente quando implementa o stub
  - Arquivo ausente → generator cria normalmente
- **D-10:** `GET /user/me` é implementado como operação de negócio definida em `dsl/operations/user.yaml`. O stub gerado é implementado nesta fase; a anotação é atualizada para `implemented`.

### Autenticação nos routers gerados

- **D-11:** O template de router do generator é atualizado para incluir `Depends(get_current_user)` em todos os endpoints. Todos os endpoints CRUD gerados (incluindo os de `user/` e `family/`) exigem Bearer token Keycloak válido. Não existem endpoints CRUD públicos a partir desta fase.
- **D-12:** JIT provisioning centralizado em `get_current_user()` em `shared/auth.py`. Fluxo: validar token JWT → extrair `idp_sub` → buscar user no banco → se não encontrado, criar com `ON CONFLICT DO NOTHING` → retornar objeto `User`. Todo endpoint com `Depends(get_current_user)` tem garantia de que o user existe no banco.

### Reorganização do codebase

- **D-13:** Diretórios `src/caramello/models/` e `src/caramello/api/generated/` são removidos ao final desta fase — todo o conteúdo migrado para os diretórios de domínio.
- **D-14:** `src/caramello/main.py` atualizado para importar routers de `caramello.user.router` e `caramello.family.router` (e subdomínios quando houver) em vez de `caramello.api.generated.*`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Estrutura alvo por domínios
- `docs/apps-platform.md` §3 — arquitetura de backend por domínios; estrutura de pastas target com `domains/`, `shared/` (referência normativa)
- `.planning/REQUIREMENTS.md` §STRUCT-01, §STRUCT-02, §AUTH-01, §AUTH-02, §AUTH-03, §USER-01 — requisitos que esta fase implementa
- `.planning/ROADMAP.md` §Phase 3 — success criteria definitivos para esta fase

### DSL generator
- `scripts/generate_code.py` — generator atual (a ser evoluído para suportar campo `domain` e novo conceito de `operations/`)
- `docs/dsl_rules.md` — regras da DSL que o generator deve seguir
- `dsl/entities/user.yaml` — entidade User (adicionar campo `domain: user`)
- `dsl/entities/family.yaml` — entidade Family (adicionar campo `domain: family`)
- `dsl/entities/family_member.yaml` — entidade FamilyMember (adicionar campo `domain: family`)
- `dsl/entities/family_invitation.yaml` — entidade FamilyInvitation (adicionar campo `domain: family`)
- `dsl/manifest.yaml` — manifesto de entidades; atualizar para incluir `dsl/operations/`

### Autenticação e JWT
- `src/caramello/core/config.py` — Settings onde `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` serão adicionados
- `src/caramello/shared/database.py` — padrão de módulo em `shared/` que `auth.py` deve seguir
- `.planning/phases/02-stack-async/02-CONTEXT.md` §D-03, §D-04 — como `shared/database.py` foi estruturado (modelo para `shared/auth.py`)

### Codebase atual (a ser reorganizado)
- `src/caramello/main.py` — ponto de entrada da app; imports dos routers serão atualizados
- `src/caramello/models/user.py` — modelo User atual (referência para o conteúdo de `user/models.py`)
- `src/caramello/api/generated/user_router.py` — router gerado atual (referência para o template async a ser adaptado com auth)

### Qualidade
- `pyproject.toml` — configuração ruff/mypy strict; código gerado e manual desta fase deve passar

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/caramello/shared/database.py`: `get_session()`, `AsyncSession`, `async_sessionmaker` — `shared/auth.py` usa a mesma sessão para o JIT provisioning (buscar/criar User)
- `src/caramello/core/config.py`: `Settings` com `model_post_init` — adicionar `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` seguindo o mesmo padrão
- `src/caramello/api/generated/user_router.py`: template do router async gerado — atualizar `generate_router()` no generator para incluir `Depends(get_current_user)` nos endpoints

### Established Patterns
- **DSL First:** nunca editar arquivos em `src/caramello/{domain}/` diretamente — editar YAML e rodar `bin/generate_code`. Exceção: `operations.py` com anotação `CARAMELLO-GENERATED: implemented`.
- **ruff + mypy strict:** todo código gerado e manual deve passar sem erros — restrição herdada das Phases 1 e 2
- **pydantic-settings:** novas vars de ambiente entram como campos em `Settings`
- **AsyncSession via Depends:** todos os endpoints usam `AsyncSession = Depends(get_session)` — `get_current_user` recebe a mesma sessão para o upsert do user

### Integration Points
- `src/caramello/main.py`: substituir imports de `api.generated.*` por `user.router`, `family.router` — adicionar lifespan handler para carregar JWKS na inicialização
- `alembic/versions/` e `alembic/env.py`: `env.py` importa `from caramello.models import *` — mudar para importar dos novos paths de domínio após reorganização
- Diretório `src/caramello/shared/`: `auth.py` será o segundo arquivo aqui (ao lado de `database.py`)

</code_context>

<specifics>
## Specific Ideas

- O `lifespan` do FastAPI em `main.py` é o lugar correto para buscar e cachear as chaves JWKS do Keycloak na startup — `async with asyncio.TaskGroup` ou simplesmente `await` na função async do lifespan.
- Realm `caramello`: JWKS URL será `{settings.KEYCLOAK_URL}/realms/caramello/protocol/openid-connect/certs`.
- O implementador deve verificar o token real emitido pelo Keycloak existente para confirmar se `aud` claim contém `client_id` ou outro valor antes de decidir a estratégia de validação de audience.
- `dsl/operations/user.yaml` criado nesta fase com a operação `GET /user/me`; o stub gerado em `user/operations.py` é implementado nesta mesma fase.

</specifics>

<deferred>
## Deferred Ideas

- **Operações de negócio de escrita no DSL** (criar família, convidar, aprovar) — definidas em `dsl/operations/family.yaml` na Phase 4, que implementa o domínio family completo
- **`GET /health` com ping ao banco** (OPS-01) — v2 requirements, milestone posterior
- **Stub generation com YAML de schema de request/response** — o formato atual do `dsl/operations/*.yaml` define apenas `method`, `path`, `description`; enriquecer com tipos de request/response é evolução futura do DSL
- **Logging estruturado em JSON (`structlog`)** — OPS-02, milestone posterior
- **Token introspection/revogação** — validação local via JWKS é suficiente para o porte do projeto; revogação de token ativo é OPS futuro

</deferred>

---

*Phase: 3-Estrutura por Domínios e Autenticação*
*Context gathered: 2026-05-25*
