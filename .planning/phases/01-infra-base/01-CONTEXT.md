# Phase 1: Infra Base - Context

**Gathered:** 2026-05-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Corrigir a fundação técnica do projeto: modelo User alinhado com a autenticação Keycloak (sem campos de auth local, com `idp_sub`), migration Alembic inicial limpa e aplicável em banco vazio, ferramentas de linting/type-check configuradas e passando, CORS habilitado para o frontend. Nenhum endpoint novo é criado — o foco é tornar o que já existe correto e as ferramentas funcionando.

**Entregável concreto:** `alembic upgrade head` em banco limpo cria o schema correto; `ruff check src/` e `mypy src/` passam sem erros; frontend em localhost não recebe erros de CORS.

</domain>

<decisions>
## Implementation Decisions

### Migration

- **D-01:** A migration existente (`20260104-1044-e667565d64eb-fix_relationships.py`) é descartada. Uma nova migration inicial é criada a partir do zero.
- **D-02:** A migration nova cobre **todas as 4 tabelas**: `user` (corrigido), `family`, `family_member`, `family_invitation`. `alembic upgrade head` em banco vazio cria o schema completo — não deixa o banco incompleto.
- **D-03:** Abordagem: corrigir `dsl/entities/user.yaml`, regenerar modelos com `bin/generate_code`, então `alembic revision --autogenerate` detecta todas as tabelas.
- **D-04:** O modelo User mantém o padrão **int `id` (PK interna) + `uuid` UUID (identificador público)** — consistente com todas as outras entidades. Adicionar `idp_sub TEXT NOT NULL UNIQUE` como campo de vínculo com o Keycloak (JWT `sub` claim). Remover `hashed_password`, `google_id`, `phone_number`, `is_active`.
- **D-05:** Corrigir o gerador DSL (`scripts/generate_code.py`) para emitir `datetime.now(UTC)` em vez de `datetime.utcnow` (deprecated no Python 3.12+). Esta correção entra nesta fase porque o gerador já está sendo tocado para o fix do User.

### Linting e Type-check (ruff + mypy)

- **D-06:** Postura **strict** — ruff e mypy configurados com regras rigorosas. O código deve passar sem erros, não apenas sem warnings ignorados com `# noqa` em massa.
- **D-07:** Para o código gerado (`src/caramello/api/generated/`, `src/caramello/models/`): corrigir o **gerador DSL** para emitir código que passe em ruff/mypy nativamente. Nunca editar arquivos gerados diretamente (seriam sobrescritos).
- **D-08:** Arquivos **vazios** removidos nesta fase (pois causam ruído no mypy e não contribuem nada):
  - `src/caramello/services/user.py`
  - `src/caramello/repositories/user.py`
  - `src/caramello/exceptions.py`
  - `src/caramello/http_errors.py`
  - `src/caramello/api/v1/routes.py`
  - `src/caramello/api/v1/users.py`
  - diretório `src/caramello/api/v1/` inteiro (skeleton nunca implementado)

### CORS

- **D-09:** CORS configurado via **env var** `CORS_ORIGINS` — lista de URLs separadas por vírgula. Valor dev: `http://localhost:3000,http://localhost:5173`. Produção: domínio definitivo quando definido.
- **D-10:** `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True` — permissivo para desenvolvimento. Para um grupo de 1-5 usuários, simplicidade prevalece sobre granularidade no CORS.
- **D-11:** `CORS_ORIGINS` adicionado como variável obrigatória no `.env.example`.

### Artefatos obsoletos

- **D-12:** Remover `src/caramello/schemas/` inteiro — `api_schemas.py` é um artefato desconectado (gerado por `datamodel-codegen`, não usado por nenhum router ou service). Cria confusão com os modelos SQLModel reais.
- **D-13:** Remover `tests/generated/` inteiro — testes que usam banco de produção sem fixtures isoladas. A infraestrutura de testes correta será criada na Phase 5 com `pytest-asyncio` e rollback por teste.
- **D-14:** Remover `tests/test_generated_api.py` — assertions com paths errados (`/users/`, `/family_invitations/`), nunca passou, não tem valor.
- **D-15:** Sem versioning de URL (`/v1/`) por enquanto. O Caramello serve consumidores que você controla (frontend próprio, agentes próprios). Versioning no URL adiciona overhead sem benefício real. Se surgir necessidade de v2, adiciona na época. Endpoints da Phase 3 em diante serão diretos: `/user/me`, `/family/families`, etc.

### Convenções atualizadas

- **D-16:** `.env.example` atualizado com `DB_NAME=familia_dev` (era `caramello_db`) e variáveis Keycloak como placeholders (`KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_URL`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Modelo de dados e convenções
- `dsl/entities/user.yaml` — definição atual do User (a ser corrigida nesta fase)
- `dsl/entities/family.yaml` — definição da Family (referência para migration)
- `dsl/entities/familymember.yaml` — definição do FamilyMember (referência para migration)
- `dsl/entities/familyinvitation.yaml` — definição do FamilyInvitation (referência para migration)
- `dsl/manifest.yaml` — lista de entidades registradas no gerador DSL
- `docs/apps-platform.md` §5 — convenção de nomenclatura do banco (`familia_dev` / `familia_prod`)
- `docs/apps-platform.md` §6 — schema alvo do User (campos esperados)

### Geração de código
- `scripts/generate_code.py` — gerador DSL atual (a ser corrigido para datetime e ruff/mypy compliance)
- `docs/dsl_rules.md` — regras da DSL que o gerador deve seguir

### Qualidade e linting
- `docs/quality_rules.md` — requisitos de ruff e mypy para o projeto

### Banco de dados e migrations
- `alembic.ini` — configuração do Alembic
- `alembic/versions/` — diretório das migrations (a migration atual será descartada)
- `src/caramello/core/config.py` — como DATABASE_URL é construído

### Contexto do pivot e gaps
- `docs/pivot-point.md` — gaps críticos mapeados que esta fase resolve (G1, G2 parcial, G3 parcial)
- `.planning/codebase/CONCERNS.md` — inventário completo de concerns do codebase

### Aplicação e configuração
- `src/caramello/main.py` — onde CORS e routers são registrados
- `.env.example` — variáveis de ambiente (a ser atualizado)
- `pyproject.toml` — onde ruff e mypy serão configurados

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/generate_code.py`: gerador DSL funcional — precisa de ajustes (datetime, ruff compliance), não de reescrita completa nesta fase
- `alembic/`: configuração Alembic em funcionamento — só precisa de nova migration, não de reconfiguração
- `src/caramello/core/config.py`: pydantic-settings configurado corretamente — adicionar `CORS_ORIGINS` field aqui
- `src/caramello/main.py`: ponto de entrada da app — adicionar `CORSMiddleware` aqui

### Established Patterns
- **DSL first**: nunca editar arquivos gerados em `src/caramello/models/` ou `src/caramello/api/generated/` — editar YAML e regenerar
- **pydantic-settings**: novas env vars entram como campos em `Settings` em `src/caramello/core/config.py`
- **int id + uuid**: padrão de PK dupla estabelecido nas 4 entidades — não quebrar nesta fase

### Integration Points
- `src/caramello/main.py`: CORSMiddleware entra antes dos routers existentes
- `pyproject.toml`: seções `[tool.ruff]` e `[tool.mypy]` a serem adicionadas
- `dsl/entities/user.yaml`: fonte de verdade do User model — corrigir aqui, regenerar cascateia para models/ e api/generated/

</code_context>

<specifics>
## Specific Ideas

- `idp_sub` deve ser `TEXT NOT NULL UNIQUE` — não pode ser nulo porque todo usuário autenticado via Keycloak terá um `sub`. Unique porque é o identificador de identidade do usuário no Keycloak.
- A migration recriada deve ter nome descritivo, ex.: `initial_schema` ou `create_initial_tables` — não um hash gerado automaticamente sem contexto.
- Variáveis Keycloak no `.env.example` como placeholders com comentários explicativos (`KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_URL`) — Phase 3 vai precisar delas para `shared/auth.py`.

</specifics>

<deferred>
## Deferred Ideas

- `GET /health` endpoint com ping ao banco (OPS-01 nos v2 requirements) — útil mas fora do escopo desta fase
- SSL no DATABASE_URL em produção (`sslmode=require`) — gap de segurança real, mas OPS-03 nos v2 requirements, resolve no deploy (Phase 5)
- Logging estruturado em JSON (`structlog`) — OPS-02, milestone posterior
- CI pipeline (GitHub Actions) — OPS-04, pós-fundação

</deferred>

---

*Phase: 1-Infra Base*
*Context gathered: 2026-05-24*
