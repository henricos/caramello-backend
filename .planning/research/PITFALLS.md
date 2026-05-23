# Domain Pitfalls

**Domain:** FastAPI brownfield — asyncpg migration, Keycloak JWT, fastapi-mcp, domain restructure, DSL generator, Docker/uv
**Researched:** 2026-05-23
**Context:** Brownfield com fundação parcial. Gaps críticos catalogados em `.planning/codebase/CONCERNS.md`. Stack: Python 3.10+, FastAPI, SQLModel/SQLAlchemy, PostgreSQL, asyncpg, Keycloak, fastapi-mcp, uv, Docker.

---

## 1. Migração psycopg2 → asyncpg

### PITFALL-1A: `create_engine` deixado no código junto com `create_async_engine`

**O que vai errado:** Durante a migração, o `session.py` atual usa `create_engine` (síncrono) do SQLModel. Se qualquer import transitivo — por exemplo, um modelo ou o próprio `alembic/env.py` — continuar referenciando o engine síncrono enquanto o app usa `AsyncSession`, as duas instâncias de engine coexistem silenciosamente. Queries aparentam funcionar mas bloqueiam o event loop.

**Por que acontece:** O SQLModel importa tanto `Session` quanto `AsyncSession` do mesmo namespace. É fácil deixar o import antigo e adicionar o novo ao lado sem remover o original.

**Sinal de alerta:** `greenlet_spawn has not been called` ou `MissingGreenlet` no log com stack trace apontando para o router. Ou queries lentas sob carga mínima (1-2 requests simultâneos).

**Prevenção:**
- Substituir `session.py` inteiro de uma vez, não incrementalmente.
- URL do banco deve ter prefixo `postgresql+asyncpg://`, não `postgresql://`. Uma URL sem o driver explícito usará o driver padrão, que é síncrono.
- Rodar `grep -r "create_engine\|from sqlmodel import.*Session" src/` após a migração — qualquer `create_engine` que não seja `create_async_engine` é bug.

**Fase:** Milestone 1 — Fase 2 (Stack Atualizada).

---

### PITFALL-1B: Lazy loading de relacionamentos quebra silenciosamente em AsyncSession

**O que vai errado:** SQLModel gera relacionamentos com `Relationship()` sem especificar `lazy`. O padrão do SQLAlchemy em contexto async é `lazy="select"`, que dispara IO implícito ao acessar o atributo. No contexto async isso levanta `MissingGreenletError` em runtime, não em tempo de compilação.

**Por que acontece:** No contexto síncrono, `session.refresh(obj)` carrega o relacionamento transparentemente. No contexto async, o mesmo acesso ao atributo fora de um `await` levanta exceção. O DSL generator atual não especifica `lazy` — todos os `Relationship()` gerados herdam o default problemático.

**Consequência específica para este projeto:** `FamilyMember` tem relacionamento com `User` e `Family`. Ao retornar um `FamilyMember` com relacionamentos expandidos, o FastAPI serializa o objeto — e o acesso ao relacionamento dispara `MissingGreenletError` em produção.

**Sinal de alerta:** `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await from handler` aparece apenas quando um endpoint tenta serializar um relacionamento, não na consulta principal.

**Prevenção:**
- Usar `selectinload` ou `joinedload` explicitamente em queries que precisam de relacionamentos: `select(Family).options(selectinload(Family.members))`.
- Configurar `async_sessionmaker` com `expire_on_commit=False` para evitar que atributos simples expirem e disparem reloads implícitos após commit.
- Atualizar o DSL generator para emitir `lazy="raise"` em todos os `Relationship()` — isso converte o erro silencioso em erro explícito durante desenvolvimento.

```python
# session.py correto
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine("postgresql+asyncpg://...", echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

**Fase:** Milestone 1 — Fase 2 (Stack Atualizada). Atualização do DSL generator na Fase 3.

---

### PITFALL-1C: Alembic `env.py` não adaptado para async engine

**O que vai errado:** O `alembic/env.py` gerado pelo `alembic init` usa `engine.connect()` síncrono. Com `asyncpg`, a conexão async não é compatível com o contexto síncrono do Alembic. Resultado: `alembic upgrade head` falha com `TypeError` ou trava sem mensagem clara.

**Por que acontece:** Alembic precisa de um padrão específico para async: `async_engine_from_config` + `connection.run_sync(do_run_migrations)` + `poolclass=NullPool`. Sem `NullPool`, o pool fica aberto após a migração, causando warnings e eventual vazamento de conexão.

**Prevenção:** Reescrever `env.py` usando o template oficial async (`alembic init -t async`). O padrão obrigatório:

```python
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,  # obrigatório — sem isso, pool vaza
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())
```

**Fase:** Milestone 1 — Fase 2. Deve ser feito junto com a troca do driver.

---

### PITFALL-1D: `target_metadata` no `env.py` com modelos não importados

**O que vai errado:** `alembic revision --autogenerate` gera uma migration vazia (só `pass` no `upgrade`) porque `SQLModel.metadata.tables` está vazio. Alembic não avisa — ele silenciosamente acha que o banco já está em sincronia com os modelos.

**Por que acontece:** O `env.py` precisa importar todos os models antes de usar `SQLModel.metadata` como `target_metadata`. Se os imports falharem silenciosamente (ex: módulo movido durante a reestruturação por domínios), o metadata fica vazio.

**Sinal de alerta:** Migration gerada com `pass` em `upgrade()` e `downgrade()`. Rodar `python -c "from caramello.domains.familia.models import *; from sqlmodel import SQLModel; print(SQLModel.metadata.tables.keys())"` antes de gerar migrations.

**Prevenção:**
```python
# env.py — imports explícitos antes de target_metadata
from sqlmodel import SQLModel
from caramello.domains.familia import models  # noqa: F401 — import necessário para registrar metadata
from caramello.shared import user_model  # noqa: F401

target_metadata = SQLModel.metadata
```

**Fase:** Milestone 1 — Fase 2 e Fase 3 (ao reorganizar domínios, atualizar env.py imediatamente).

---

## 2. Keycloak + FastAPI JWT

### PITFALL-2A: `algorithms` omitido ou fixado como `["HS256"]` em vez de `["RS256"]`

**O que vai errado:** Keycloak emite tokens RS256 por padrão (assimétrico — chave pública/privada). Se `jwt.decode()` for chamado sem `algorithms=["RS256"]`, PyJWT usa o default ou aceita qualquer algoritmo declarado no header do token — criando uma vulnerabilidade de algoritmo downgrade onde um atacante pode forjar tokens HS256 usando a chave pública como secret.

**Prevenção:**
```python
# ERRADO — nunca fazer isso
decoded = jwt.decode(token, key)

# CORRETO
decoded = jwt.decode(token, signing_key.key, algorithms=["RS256"])
```
Hardcode `algorithms=["RS256"]` — nunca derivar do header do token.

**Fase:** Milestone 1 — Fase 3 (implementação de `shared/auth.py`).

---

### PITFALL-2B: `aud` (audience) ausente no token Keycloak

**O que vai errado:** Keycloak só inclui o `client_id` no claim `aud` se o usuário tiver pelo menos um role atribuído ao client. Em ambientes de desenvolvimento onde nenhum role foi configurado, os tokens não têm `aud` — e PyJWT com `audience=` configurado rejeita o token com `InvalidAudienceError`.

**Por que acontece:** Comportamento documentado do Keycloak. A ausência de `aud` é silenciosa — o Keycloak não avisa, o token é emitido normalmente, mas a validação no app falha.

**Sinal de alerta:** `jwt.exceptions.InvalidAudienceError` em ambiente de dev mas não nos testes manuais via Postman (onde audience não é validado).

**Prevenção:**
- Configurar um **Audience Mapper** no Keycloak client (Client → Client Scopes → Add mapper → Audience). Isso garante que `aud` sempre contém o `client_id`, independente de roles.
- Validar em staging com um token real antes de ir para produção.
- No código, nunca usar `options={"verify_aud": False}` em produção — isso desabilita a proteção.

**Fase:** Milestone 1 — Fase 3. Configurar o mapper no Keycloak junto com a implementação do `shared/auth.py`.

---

### PITFALL-2C: JWKS endpoint chamado em toda request (sem cache) ou com cache eterno (chaves revogadas aceitas)

**O que vai errado:** Dois cenários opostos:
1. **Sem cache:** `PyJWKClient` instanciado dentro do handler ou em cada request → uma chamada HTTP ao Keycloak por request → latência alta, dependência de rede em hot path.
2. **Com `cache_keys=True` (default):** `lru_cache` sem TTL → se Keycloak rotacionar chaves, a chave antiga permanece em cache indefinidamente → tokens com chaves revogadas continuam sendo aceitos.

**Prevenção:**
- Instanciar `PyJWKClient` uma única vez no startup da aplicação (module-level ou como singleton via `lifespan`).
- O `PyJWKClient` já trata rotação automaticamente: se `kid` do token não está no cache, ele re-fetcha o JWKS. Isso é suficiente para rotação normal de chaves.
- Para o projeto de 1-5 usuários, o cache default é aceitável. Documentar o comportamento e adicionar health-check que verifica conectividade com o JWKS endpoint.

```python
# shared/auth.py — inicializar uma vez
from jwt import PyJWKClient

JWKS_URL = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
jwks_client = PyJWKClient(JWKS_URL)  # singleton — não instanciar por request
```

**Fase:** Milestone 1 — Fase 3.

---

### PITFALL-2D: Just-in-time provisioning sem constraint UNIQUE no banco cria usuários duplicados

**O que vai errado:** O padrão de JIT provisioning é: "se não existe usuário com este `idp_sub`, criar". Em FastAPI async com múltiplas coroutines, duas requests simultâneas do mesmo usuário podem passar pelo `SELECT` antes do `INSERT` de qualquer uma delas, e ambas tentam inserir — o banco lança `UniqueConstraintViolation` na segunda, que vira HTTP 500 não tratado.

**Por que acontece:** A operação "check-then-insert" não é atômica sem um lock ou `INSERT ... ON CONFLICT DO NOTHING`.

**Prevenção:**
```python
# Padrão correto: upsert atômico
async def get_or_create_user(session: AsyncSession, idp_sub: str, email: str, name: str) -> User:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    stmt = pg_insert(User).values(idp_sub=idp_sub, email=email, name=name)
    stmt = stmt.on_conflict_do_nothing(index_elements=["idp_sub"])
    await session.execute(stmt)
    await session.commit()
    result = await session.execute(select(User).where(User.idp_sub == idp_sub))
    return result.scalar_one()
```

Alternativamente, capturar `IntegrityError` e re-fetch. O constraint `UNIQUE` em `idp_sub` no banco (garantido pelo Alembic migration) é a linha de defesa final — nunca omiti-lo.

**Fase:** Milestone 1 — Fase 3.

---

## 3. fastapi-mcp

### PITFALL-3A: MCP expõe todos os endpoints automaticamente, incluindo CRUD interno perigoso

**O que vai errado:** Por padrão, `FastApiMCP(app)` descobre todos os endpoints registrados no app e os expõe como MCP tools — incluindo `DELETE /user/{uuid}`, `PATCH /family/{uuid}`, e outros endpoints administrativos ou internos que não devem ser expostos a agentes de IA.

**Consequência específica:** Os 4 routers gerados atualmente (user, family, familymember, familyinvitation) incluem endpoints de deleção e listagem irrestrita. Sem filtragem explícita, um agente MCP pode deletar registros ou listar todos os usuários.

**Prevenção:** Usar `include_tags` com a tag `"mcp"` como allow-list positiva — mais seguro que `exclude_operations` (deny-list, que cresce a cada novo endpoint):

```python
# Nos routers, taggear apenas o que deve ser exposto via MCP
router = APIRouter(prefix="/familia", tags=["familia", "mcp"])

# No main.py
mcp = FastApiMCP(
    app,
    include_tags=["mcp"],  # apenas endpoints explicitamente taggeados
)
mcp.mount_http()
```

**Alternativa:** `include_operations=["list_families", "get_family"]` — mais granular mas requer manutenção manual.

**Fase:** Milestone 1 — Fase de integração MCP (última fase do M1).

---

### PITFALL-3B: `FastApiMCP` instanciado antes dos `include_router` — endpoints não aparecem no MCP

**O que vai errado:** `fastapi-mcp` descobre endpoints no momento da inicialização do servidor, não em tempo de request. Se `FastApiMCP(app)` é instanciado antes de `app.include_router(...)`, os routers incluídos depois não aparecem como MCP tools.

**Sinal de alerta:** `mcp.setup_server()` deve ser chamado após todos os `include_router`. Ou simplesmente: instanciar `FastApiMCP` no final de `main.py`, depois de todos os routers.

**Prevenção:**
```python
# main.py — ordem importa
app = FastAPI()

app.include_router(familia_router, prefix="/familia")
app.include_router(user_router, prefix="/user")

# FastApiMCP DEPOIS de todos os routers
mcp = FastApiMCP(app, include_tags=["mcp"])
mcp.mount_http()
```

Se usar padrão de routers dinâmicos ou `lifespan`, chamar `mcp.setup_server()` após montar os routers.

**Fase:** Milestone 1 — Fase de integração MCP.

---

### PITFALL-3C: MCP endpoint não protegido por autenticação — acesso irrestrito ao agente

**O que vai errado:** O endpoint `/mcp` montado por `fastapi-mcp` não herda automaticamente os `Depends` dos routers que ele expõe. Um agente sem token pode chamar ferramentas MCP que internamente chamam endpoints protegidos — mas a proteção depende de como a tool faz a chamada.

**Prevenção:** Usar `AuthConfig` para proteger o próprio endpoint MCP:

```python
from fastapi_mcp import FastApiMCP, AuthConfig
from fastapi.security import HTTPBearer

mcp = FastApiMCP(
    app,
    include_tags=["mcp"],
    auth_config=AuthConfig(
        dependencies=[Depends(get_current_user)]
    ),
    headers=["authorization"],  # propaga o Bearer token para as tool calls
)
```

**Fase:** Milestone 1 — Fase de integração MCP.

---

## 4. Reorganização de estrutura por domínios

### PITFALL-4A: Alembic `env.py` com imports quebrados após mover modelos

**O que vai errado:** Ao mover `src/caramello/models/user.py` para `src/caramello/shared/user.py` (ou `domains/familia/models.py`), o `env.py` do Alembic continua importando do caminho antigo. Como o `env.py` é executado pelo CLI do Alembic (não pelo app), o erro de import pode não aparecer nos testes do app — só ao rodar `alembic upgrade head` ou `alembic revision`.

**Sinal de alerta:** `ModuleNotFoundError: No module named 'caramello.models.user'` ao rodar qualquer comando Alembic.

**Prevenção:**
- Atualizar `env.py` imediatamente ao mover qualquer model.
- Adicionar um smoke test no CI: `python -c "import alembic.config; alembic.config.main(['check'])"` — falha rapidamente se env.py tem imports quebrados.
- Não mover models e gerar migrations no mesmo commit.

**Fase:** Milestone 1 — Fase 3 (Reestruturação por domínios).

---

### PITFALL-4B: Migration existente referencia tabelas/colunas do modelo errado

**O que vai errado:** A única migration existente (`20260104-fix_relationships.py`) foi gerada com o modelo incorreto (`hashed_password`, `google_id`). Se o desenvolvedor não a descarta e tenta rodar `alembic upgrade head` em um banco limpo, o schema produzido diverge do modelo atual — futuros `--autogenerate` criam migrations de "correção" confusas.

**Estratégia de descarte seguro:**
1. Garantir que não há dados de produção na migration antiga (projeto ainda não tem usuários reais — confirmado em `.planning/PROJECT.md`).
2. Deletar o arquivo `alembic/versions/20260104-*.py`.
3. Corrigir o DSL (`user.yaml`) e regenerar os modelos.
4. Rodar `alembic revision --autogenerate -m "initial_schema"` para criar a migration correta.
5. Não usar `alembic stamp head` como atalho — ele marca o banco como atualizado sem aplicar as mudanças.

**Fase:** Milestone 1 — Fase 1 (Correção do Modelo). Deve ser a primeira ação.

---

### PITFALL-4C: Imports circulares ao reorganizar para `domains/`

**O que vai errado:** Com estrutura plana (`models/`, `schemas/`, `services/`), os imports são unidirecionais. Ao mover para `domains/familia/models.py`, é tentador importar de `shared/user.py` dentro do model — e `shared/user.py` importar de volta alguma coisa do domínio. Python levanta `ImportError: cannot import name 'X' from partially initialized module`.

**Padrão de prevenção:**
- `shared/` nunca importa de `domains/` — fluxo unidirecional.
- `domains/` pode importar de `shared/`.
- Relacionamentos cross-domain via `TYPE_CHECKING` guard:
```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from caramello.domains.agenda.models import Event
```

**Fase:** Milestone 1 — Fase 3.

---

## 5. DSL generator evolution

### PITFALL-5A: Gerador sobrescreve arquivos com código manual sem merge

**O que vai errado:** O gerador atual (`generate_code.py`) usa `open(..., 'w')` — abre o arquivo em modo de escrita destrutiva. Se um desenvolvedor adicionar lógica manual em um arquivo gerado (ex: método customizado em um model), a próxima execução do gerador apaga tudo silenciosamente.

**Consequência:** Perda de trabalho sem aviso. O gerador não tem mecanismo de detecção de conflito ou merge.

**Prevenção obrigatória para a evolução do gerador:**
- **Separação de fronteiras clara:** arquivos gerados ficam em `domains/{domain}/generated/` — nunca tocar. Extensões ficam em `domains/{domain}/models.py` importando do generated.
- **Header de geração no topo de todo arquivo gerado:**
```python
# THIS FILE IS AUTO-GENERATED. DO NOT EDIT MANUALLY.
# Regenerate with: bin/generate_code
# Source: dsl/entities/family.yaml
```
- **Verificação no CI:** `git diff --name-only | grep "domains/.*/generated/"` — falha se arquivo gerado foi editado manualmente.

**Fase:** Milestone 1 — Fase 3 (evolução do DSL generator para suporte a `domain` field).

---

### PITFALL-5B: `default_factory=datetime.utcnow` hardcoded no gerador

**O que vai errado:** O gerador atual emite `default_factory=datetime.utcnow` (linha 96 de `generate_code.py`). `datetime.utcnow` está deprecated desde Python 3.12 e será removido em versão futura. Todo modelo gerado herdará o bug.

**Sinal de alerta:** `DeprecationWarning: datetime.utcnow() is deprecated` aparece nos logs, mas não é um erro — passa silenciosamente em Python 3.10/3.11.

**Prevenção:** Atualizar o gerador para emitir `default_factory=lambda: datetime.now(timezone.utc)` e adicionar `from datetime import timezone` nos imports gerados.

**Fase:** Milestone 1 — Fase 3 (evolução do gerador). Fix simples, feito junto com a adição do campo `domain`.

---

### PITFALL-5C: Gerador gera routers síncronos — incompatível com AsyncSession

**O que vai errado:** Os routers gerados por `generate_router()` usam `def create_user(session: Session = Depends(get_session))` — síncrono. Com a migração para `AsyncSession`, esses handlers bloqueiam o event loop porque FastAPI executa `def` functions em threadpool (não `async def`), mas `AsyncSession` não é thread-safe.

**Prevenção:** Atualizar o gerador para emitir `async def` em todos os handlers e `await session.exec(...)`:

```python
# Padrão gerado ERRADO (atual)
def create_family(family_in: FamilyCreate, session: Session = Depends(get_session)):
    ...

# Padrão gerado CORRETO (após migração)
async def create_family(family_in: FamilyCreate, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Family))
    ...
```

**Fase:** Milestone 1 — Fase 2 (junto com a migração do driver de banco).

---

## 6. Docker multi-stage com Python e uv

### PITFALL-6A: `UV_LINK_MODE` não configurado — symlinks quebram entre stages

**O que vai errado:** Por padrão, uv cria symlinks ao instalar pacotes (para velocidade). No multi-stage Docker build, o `.venv` criado no stage `builder` é copiado para o stage `runtime`. Os symlinks no `.venv` apontam para caminhos do stage `builder` que não existem no stage `runtime` — imports falham em runtime com `ModuleNotFoundError` para pacotes que parecem instalados.

**Sinal de alerta:** `docker run` falha com `ModuleNotFoundError` mas `docker build` conclui sem erro.

**Prevenção:**
```dockerfile
# No stage builder, sempre setar antes de qualquer uv sync
ENV UV_LINK_MODE=copy
```

**Fase:** Milestone 1 — implementação do Dockerfile.

---

### PITFALL-6B: `uv sync` sem separar dependências do projeto — layer caching ineficiente

**O que vai errado:** Copiar todo o código fonte antes de `uv sync` invalida o cache Docker de dependências em cada mudança de código-fonte. Em projetos Python, as dependências mudam raramente; o código muda frequentemente.

**Prevenção — padrão obrigatório:**
```dockerfile
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# 1. Copiar APENAS os arquivos de dependência
COPY pyproject.toml uv.lock ./

# 2. Instalar dependências (sem o projeto) — camada cacheada
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# 3. Copiar código fonte e instalar o projeto
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
# ... rest of runtime config
```

**Fase:** Milestone 1 — implementação do Dockerfile.

---

### PITFALL-6C: `uv.lock` ausente ou não commitado — builds não reproduzíveis

**O que vai errado:** `uv sync --locked` (com flag `--locked`) falha se `uv.lock` não existir ou estiver desatualizado em relação ao `pyproject.toml`. O `pyproject.toml` atual não tem `uv.lock` rastreado no git (inferido pela ausência de menção nos commits).

**Sinal de alerta:** `error: uv.lock is not up-to-date` no CI/CD.

**Prevenção:**
- Sempre commitar `uv.lock` no repositório.
- Adicionar ao `Makefile` ou script de setup: `uv lock` antes de qualquer `uv sync`.
- No Dockerfile usar `--locked` (não `--frozen`) para builds reproduzíveis. `--frozen` permite lockfile desatualizado; `--locked` exige sincronia.

**Fase:** Milestone 1 — implementação do Dockerfile e setup inicial.

---

### PITFALL-6D: `PATH` não configurado corretamente no stage runtime

**O que vai errado:** Após copiar `.venv` do builder para o runtime, se `PATH` não incluir `/app/.venv/bin`, o comando `CMD ["uvicorn", ...]` usa o `uvicorn` do sistema (que não existe na imagem slim) em vez do `.venv`.

**Sinal de alerta:** `exec: "uvicorn": executable file not found in $PATH` ao iniciar o container.

**Prevenção:** `ENV PATH="/app/.venv/bin:$PATH"` no stage runtime é obrigatório. Não usar `python -m uvicorn` como alternativa — isso usa o Python do sistema, não o do `.venv`.

**Fase:** Milestone 1 — implementação do Dockerfile.

---

## Phase-Specific Warning Matrix

| Fase | Tópico | Armadilha principal | Mitigação |
|------|--------|---------------------|-----------|
| Fase 1 — Correção do Modelo | Descartar migration antiga | `alembic stamp head` sem schema correto | Deletar o arquivo, regenerar do zero |
| Fase 2 — Stack async | Migração psycopg2→asyncpg | URL sem `+asyncpg` prefixo | Validar URL via grep antes de rodar app |
| Fase 2 — Stack async | env.py Alembic | Engine sync no Alembic | Reescrever usando template `async` oficial |
| Fase 2 — Stack async | DSL generator | Routers síncronos gerados | Atualizar gerador junto com a migração do driver |
| Fase 3 — Domínios | Reorganização | Imports circulares `shared` ↔ `domains` | Fluxo unidirecional; TYPE_CHECKING para referências cruzadas |
| Fase 3 — Domínios | Alembic env.py | Imports quebrados após mover modelos | Atualizar env.py imediatamente ao mover models |
| Fase 3 — Auth JWT | Keycloak audience | `aud` ausente sem Audience Mapper | Configurar mapper no Keycloak antes de testar |
| Fase 3 — Auth JWT | JIT provisioning | Race condition INSERT duplicado | Usar `ON CONFLICT DO NOTHING` + UNIQUE constraint |
| Fase 3 — DSL evolution | Gerador | `utcnow` deprecated + routers síncronos | Corrigir ambos ao evoluir o gerador |
| Fase 3 — MCP | fastapi-mcp | Todos os endpoints expostos por padrão | `include_tags=["mcp"]` como allow-list |
| Fase 3 — MCP | fastapi-mcp | Instanciado antes dos routers | Instanciar FastApiMCP no final de main.py |
| Fase 4 — Docker | Dockerfile | Symlinks quebrados entre stages | `UV_LINK_MODE=copy` obrigatório |
| Fase 4 — Docker | uv.lock | Lock não commitado | Commitar uv.lock antes do primeiro build |

---

## Sources

- SQLAlchemy 2.0 async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Alembic async template: https://github.com/sqlalchemy/alembic/blob/main/alembic/templates/async/env.py
- fastapi-mcp customization: https://fastapi-mcp.tadata.com/configurations/customization
- fastapi-mcp transport: https://fastapi-mcp.tadata.com/advanced/transport
- PyJWT JWKS usage: https://github.com/jpadilla/pyjwt
- PyJWKClient cache issue: https://github.com/jpadilla/pyjwt/issues/1051
- Keycloak audience configuration: https://dev.to/metacosmos/how-to-configure-audience-in-keycloak-kp4
- uv Docker guide: https://docs.astral.sh/uv/guides/integration/docker/
- uv Docker pitfalls: https://hynek.me/articles/docker-uv/
- SQLAlchemy MissingGreenlet: https://medium.com/@vickypalaniappan12/sqlalchemy-missinggreenleterror-656825b3ce13
- FastAPI Keycloak auth: https://skycloak.io/blog/keycloak-fastapi-python-api-authentication/
