# Phase 2: Stack Async - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrar o driver de banco de `psycopg2-binary` (síncrono) para `asyncpg` (assíncrono), reescrever o módulo de session (`database/session.py` → `shared/database.py`) usando `create_async_engine` + `async_sessionmaker` + `AsyncSession`, configurar o Alembic para operar em modo async com `async_engine_from_config` e `NullPool`, e atualizar o DSL generator para emitir routers com `async def`. Após a atualização do generator, os 4 routers existentes são regenerados para ficarem async imediatamente.

**Entregável concreto:** `grep -r "create_engine" src/` retorna vazio; `shared/database.py` usa `AsyncSession`; `alembic upgrade head` conclui sem travar; routers gerados usam `async def` e `await session.exec()`.

**Fora de escopo desta fase:** campo `domain` no YAML do generator e mudança de output path para `domains/{domain}/` — isso entra na Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Driver e dependências

- **D-01:** Remover `psycopg2-binary` das dependências. Adicionar `asyncpg` via `uv add asyncpg`. Verificar que `uv.lock` reflete a remoção — `grep psycopg2 uv.lock` deve retornar vazio após a troca.
- **D-02:** Atualizar o SQLModel para a versão mais recente (`uv add sqlmodel` sem pin de versão). O researcher deve verificar o changelog da versão instalada para identificar breaking changes antes de planejar o migration path.

### Módulo de database

- **D-03:** Criar `src/caramello/shared/database.py` como novo módulo de session — não migrar in-place em `database/session.py`. O arquivo `database/session.py` é removido. Esta fase cria o diretório `shared/` que a Phase 3 vai expandir com `auth.py`.
- **D-04:** `shared/database.py` expõe: `engine` (via `create_async_engine`), `async_session_factory` (via `async_sessionmaker`), e `get_session()` como generator assíncrono usando `AsyncGenerator[AsyncSession, None]` — compatível com `Depends()` do FastAPI.
- **D-05:** `create_db_and_tables()` é removida. O schema é gerenciado exclusivamente pelo Alembic — não há razão para manter essa função num projeto com migrations.

### Alembic async

- **D-06:** `alembic/env.py` migrado para usar `asyncio.run()` + `async_engine_from_config` com `poolclass=NullPool`. Modo offline (`run_migrations_offline`) mantém comportamento síncrono — apenas o modo online vira async.
- **D-07:** `alembic/env.py` mantém o import `from caramello.models import *` para autogenerate. A localização dos models não muda nesta fase (ainda em `src/caramello/models/`).

### DSL generator — escopo mínimo async

- **D-08:** O generator (`scripts/generate_code.py`) tem seu template de router atualizado para emitir:
  - `async def` em todos os endpoints
  - `AsyncSession` como tipo da dependência de session
  - `await session.exec(select(...))` como padrão de query
  - Import de `from caramello.shared.database import get_session` (novo path)
- **D-09:** Campo `domain` no YAML e mudança de output path para `domains/{domain}/` **não entram nesta fase** — ficam integralmente para Phase 3.
- **D-10:** Após atualizar o generator, rodar `bin/generate_code` para regenerar os 4 routers (`user`, `family`, `family_member`, `family_invitation`). O código gerado deve passar em `ruff check src/` e `mypy src/` sem erros.

### Routers existentes

- **D-11:** Os 4 routers em `src/caramello/api/generated/` são regenerados nesta fase com o generator atualizado. Ao final da Phase 2, não há arquivo `.py` no projeto importando `Session` síncrona ou `create_engine`.
- **D-12:** `src/caramello/main.py` é atualizado para importar de `shared/database.py` se necessário (lifespan, startup events). Imports de `database.session` são removidos.

### Compatibilidade com ruff/mypy

- **D-13:** O generator emite código que passa em ruff/mypy nativamente — herança da decisão D-07 da Phase 1. Com `AsyncSession`, os tipos devem ser anotados explicitamente (`AsyncGenerator[AsyncSession, None]` no `get_session`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Módulo de database e session atual (a ser substituído)
- `src/caramello/database/session.py` — implementação sync atual; arquivo de referência do que precisa mudar
- `src/caramello/core/config.py` — como `DATABASE_URL` é construído; o novo `shared/database.py` consome deste mesmo Settings

### Alembic
- `alembic/env.py` — arquivo atual; deve ser migrado para modo async com `asyncio.run()` + `async_engine_from_config`
- `alembic.ini` — configuração do Alembic; `sqlalchemy.url` permanece vazio (DATABASE_URL vem do Settings)
- `alembic/versions/` — diretório das migrations geradas na Phase 1

### DSL generator
- `scripts/generate_code.py` — generator atual (sync); templates de router a serem convertidos para async
- `docs/dsl_rules.md` — regras da DSL que o generator deve seguir (não mudam nesta fase)
- `dsl/entities/` + `dsl/manifest.yaml` — entidades registradas que serão regeneradas

### Qualidade e linting
- `pyproject.toml` — configuração de ruff e mypy (definida na Phase 1); código gerado deve continuar passando

### Contexto arquitetural
- `.planning/ROADMAP.md` §Phase 2 — success criteria definitivos para esta fase
- `.planning/REQUIREMENTS.md` §INFRA-01 — requisito que esta fase resolve
- `.planning/phases/01-infra-base/01-CONTEXT.md` — decisões da Phase 1 que se aplicam aqui (D-06: postura strict no linting, D-07: generator emite código que passa em ruff/mypy)

</canonical_refs>

<code_context>
## Existing Code Insights

### Assets a substituir (não reusables)
- `src/caramello/database/session.py`: `create_engine` + `Session` síncrona — substituído integralmente por `shared/database.py` com `create_async_engine` + `AsyncSession`
- `alembic/env.py`: `engine_from_config` síncrono — convertido para `async_engine_from_config` com `asyncio.run()`

### Padrões estabelecidos (mantidos)
- **pydantic-settings:** `DATABASE_URL` vem de `settings.DATABASE_URL` — o novo `shared/database.py` mantém esse padrão
- **DSL first:** nunca editar `src/caramello/api/generated/` diretamente — atualizar o generator e rodar `bin/generate_code`
- **ruff + mypy strict:** todo código gerado deve passar sem erros — restrição herdada da Phase 1

### Pontos de integração
- `src/caramello/main.py`: se tiver import de `database.session` ou chamada a `create_db_and_tables()`, precisa ser atualizado para remover esses imports
- `src/caramello/api/generated/*_router.py`: 4 arquivos que serão sobrescritos pelo generator atualizado
- `alembic/env.py`: `from caramello.models import *` se mantém para autogenerate — models ainda estão em `src/caramello/models/`

### Diretório `shared/` (novo)
- Criado nesta fase com `shared/__init__.py` e `shared/database.py`
- Phase 3 adiciona `shared/auth.py` — a estrutura já estará pronta

</code_context>

<specifics>
## Specific Ideas

- O `get_session()` async deve usar `AsyncGenerator[AsyncSession, None]` como type hint para que mypy e FastAPI's `Depends()` funcionem corretamente.
- Ao atualizar SQLModel, verificar se `session.exec()` ainda é a API recomendada para AsyncSession na versão instalada — pode ser que a versão mais recente normalize para `session.execute()` do SQLAlchemy. O researcher deve validar isso e o planner definir o padrão a ser emitido pelo generator.
- O Alembic async requer `NullPool` no modo online — isso já estava no env.py atual, mas com o driver sync. Deve ser mantido na versão async.

</specifics>

<deferred>
## Deferred Ideas

- Campo `domain:` no YAML do DSL generator e output para `domains/{domain}/` — escopo da Phase 3
- `GET /health` com ping ao banco (OPS-01) — v2 requirements, milestone posterior
- SSL no `DATABASE_URL` em produção (`sslmode=require`) — Phase 5 deploy

</deferred>

---

*Phase: 2-Stack Async*
*Context gathered: 2026-05-25*
