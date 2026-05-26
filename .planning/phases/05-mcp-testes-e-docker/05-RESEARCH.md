# Phase 5: MCP, Testes e Docker — Research

**Pesquisado:** 2026-05-26
**Domínio:** fastapi-mcp, pytest-asyncio, Docker multi-stage, PostgreSQL test isolation
**Confiança:** HIGH (stack verificado via Context7 + PyPI + documentação oficial)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MCP — Integração e Ferramentas**
- D-MCP-01: Servidor MCP montado na mesma app FastAPI via `fastapi-mcp`, exposto em `/mcp`. Mesmo processo, sem serviço separado.
- D-MCP-02: Ferramentas MCP implementadas **manualmente** em `src/caramello/mcp/tools.py`. [VEJA ALERTA CRÍTICO abaixo]
- D-MCP-03: Lógica extraída de `families/operations.py` para `families/services.py`. Services recebem `AsyncSession` + `User`; chamados por ferramentas MCP e por endpoints REST.
- D-MCP-04: 1 ferramenta MCP de exemplo: `get_my_families`.
- D-MCP-05: Auth MCP via Bearer token, mesmo `get_current_user()` dos endpoints REST.

**Testes — Infraestrutura**
- D-TEST-01: Banco real `caramello_test` para testes de integração.
- D-TEST-02: Transaction rollback por teste.
- D-TEST-03: `bin/manage_db --env test` gerencia `caramello_test`.
- D-TEST-04: `@pytest.mark.integration` para testes que dependem de PG real.
- D-TEST-05: Testes de integração cobrem criar família, pré-registrar membro, listar membros.

**Docker — Containerização**
- D-DOCKER-01: Dockerfile multi-stage, non-root user, sem secrets nos layers de build.
- D-DOCKER-02: `compose.yaml` app only (PG externo), config via env vars.
- D-DOCKER-03: `APP_VERSION` no campo `version` da OpenAPI spec via `os.getenv("APP_VERSION", "0.0.0")`.

**Nomenclatura de Banco**
- D-NAMING-01: Renomear para `caramello` (prod), `caramello_dev` (dev), `caramello_test` (test). Atualizar `.env.example`, `REQUIREMENTS.md` e `docs/apps-platform.md §5`.

### Claude's Discretion

Nenhuma área de discrição explicitamente definida — todas as decisões estão locked.

### Deferred Ideas (OUT OF SCOPE)

- Ferramentas MCP de escrita (create_family, pre_register_member) — M2+
- Ferramentas MCP adicionais de leitura — M2+
- `GET /health` com ping ao banco — OPS-01 v2
- Docker compose com PostgreSQL incluso (self-contained) — não necessário
- CI pipeline GitHub Actions — OPS-04 v2

</user_constraints>

---

> **ALERTA CRITICO — D-MCP-02 requer correção de abordagem**
>
> A decisão D-MCP-02 assume que é possível implementar ferramentas MCP manualmente em
> `src/caramello/mcp/tools.py` com `fastapi-mcp`. Essa suposição está **incorreta**.
>
> Conforme documentação oficial do fastapi-mcp 0.4.0 (FAQ e verificação via Context7):
> *"FastApiMCP only supports tools that are derived from FastAPI endpoints."*
> Feature request de custom tools aberta em issue #75, ainda não implementada.
>
> **Implicação para o plano:** a ferramenta `get_my_families` deve ser exposta via o
> endpoint REST existente `GET /families/families`, usando `include_operations=["list_my_families"]`
> no `FastApiMCP`. Não há `tools.py` manual. Os services (`families/services.py`) ainda devem
> ser extraídos para que a lógica fique testável, mas a integração MCP acontece pelo endpoint.
>
> [VERIFIED: Context7 /tadata-org/fastapi_mcp — FAQ.mdx; issue #75]

---

<phase_requirements>
## Phase Requirements

| ID | Descrição | Suporte da Research |
|----|-----------|---------------------|
| MCP-01 | Cliente MCP em `/mcp` descobre ferramentas de consulta do domínio `family` e `user` | `FastApiMCP(app, include_operations=[...])` + `mcp.mount_http()` expõe endpoints existentes |
| MCP-02 | Ferramentas MCP exigem Bearer token válido — mesmo mecanismo dos endpoints REST | `AuthConfig(dependencies=[Depends(http_bearer)])` + `headers=["authorization"]` — token é propagado aos endpoints que já usam `get_current_user()` |
| DEPLOY-01 | Imagem Docker reproducível com Dockerfile multi-stage, non-root user, sem secrets | Padrão confirmado; Python 3.12-slim como base runtime [VERIFIED: Docker Hub] |
| DEPLOY-02 | `docker compose up` com configuração via env vars, sem hardcode | `compose.yaml` alinhado com `docs/deploy.md`; env vars `DB_*` e Keycloak já definidos |
| DEPLOY-03 | `APP_VERSION` como build arg na OpenAPI spec | `FastAPI(version=os.getenv("APP_VERSION", "0.0.0"))` + `ARG APP_VERSION` no Dockerfile |
| TEST-01 | Testes contra banco isolado `caramello_test` com rollback por teste | pytest-asyncio 1.4.0 + AsyncSession + transaction rollback via savepoint |
| TEST-02 | Cobertura de casos de sucesso do domínio family | Testes async com `AsyncClient` + banco real + `dependency_overrides` para auth |
| TEST-03 | `dependency_overrides` para simular usuário autenticado sem Keycloak real | Padrão já estabelecido em `test_family_operations.py`; replicar com AsyncSession real |

</phase_requirements>

---

## Summary

A Phase 5 entrega três frentes: integração MCP, infraestrutura de testes com banco real e isolamento por rollback, e containerização Docker. O ponto mais crítico desta fase é a correção da abordagem de integração MCP: `fastapi-mcp` não suporta ferramentas customizadas fora de endpoints FastAPI — a ferramenta `get_my_families` é exposta via o endpoint REST existente filtrado por `include_operations`.

Para testes, o padrão de transaction rollback por teste com `pytest-asyncio` e `AsyncSession` é bem estabelecido: usa `create_savepoint` para aninhamento de transações e garante que o banco `caramello_test` está sempre limpo entre testes sem custo de truncate. A dependência `pytest-asyncio` (1.4.0 disponível) ainda não está instalada.

Para Docker, o padrão é Dockerfile multi-stage com `python:3.12-slim` como base runtime, non-root user, e `compose.yaml` alinhado com o exemplo já documentado em `docs/deploy.md`. O `APP_VERSION` é injetado como `ARG` no Dockerfile e lido via `os.getenv()` no `main.py`.

**Recomendação primária:** Antes de planejar a ferramenta MCP, o planner deve notar que o módulo `src/caramello/mcp/tools.py` (D-MCP-02) não existe no modelo de fastapi-mcp — a ferramenta `get_my_families` é o endpoint REST `list_my_families` exposto via `include_operations`. O arquivo `families/services.py` ainda faz sentido para testabilidade e reutilização, mas não como caminho de integração MCP.

---

## Architectural Responsibility Map

| Capacidade | Tier Primário | Tier Secundário | Racional |
|------------|--------------|-----------------|----------|
| Servidor MCP `/mcp` | API/Backend | — | Montado na mesma app FastAPI via `FastApiMCP.mount_http()` |
| Auth Bearer token em MCP | API/Backend | — | `AuthConfig` + `headers=["authorization"]` propaga para `get_current_user()` |
| Ferramenta `get_my_families` | API/Backend | — | É o endpoint REST existente `GET /families/families`, filtrado por `include_operations` |
| Lógica de negócio `families/services.py` | API/Backend | — | Extraída de `operations.py`; chamada por endpoints REST (e indirectamente pelo MCP) |
| Testes de integração | — (infra de teste) | — | `caramello_test` + rollback por teste; não é tier de produção |
| Infraestrutura Docker | Container | — | Dockerfile multi-stage + `compose.yaml` |
| `APP_VERSION` na spec OpenAPI | API/Backend | — | `FastAPI(version=os.getenv(...))` + build arg |

---

## Standard Stack

### Core

| Biblioteca | Versão | Propósito | Por que Standard |
|------------|--------|-----------|-----------------|
| `fastapi-mcp` | 0.4.0 | Exposição de endpoints FastAPI como ferramentas MCP | Última versão estável; requerida pela decisão D-MCP-01 |
| `pytest-asyncio` | 1.4.0 | Suporte a testes async com pytest | Última versão; necessário para fixtures async com AsyncSession |
| `mcp` | 1.27.1 | Protocolo MCP (transitividade de fastapi-mcp) | Instalado automaticamente com fastapi-mcp |

[VERIFIED: PyPI — `pip index versions fastapi-mcp` retornou 0.4.0 como mais recente; `pip index versions pytest-asyncio` retornou 1.4.0]

### Supporting

| Biblioteca | Versão | Propósito | Quando Usar |
|------------|--------|-----------|-------------|
| `httpx` | >=0.28.1 | `AsyncClient` para testes async de endpoints | Já no `pyproject.toml`; usar nos testes de integração |
| `python-multipart` | 0.0.29 | Parsing de form data (transitividade de fastapi-mcp) | Instalado automaticamente |

### Já Instaladas (sem mudança)

| Biblioteca | Versão atual | Status |
|------------|-------------|--------|
| `fastapi` | 0.118.0 | Sem mudança |
| `sqlmodel` | >=0.0.38 | Sem mudança |
| `asyncpg` | >=0.31.0 | Sem mudança |
| `pyjwt[crypto]` | >=2.13.0 | Sem mudança |
| `httpx` | >=0.28.1 | Sem mudança — reutilizado nos testes |

### Alternativas Consideradas

| Em vez de | Poderia Usar | Tradeoff |
|-----------|-------------|---------|
| `fastapi-mcp` | `fastmcp` (Anthropic) | `fastmcp` suporta tools customizadas; mais flexível mas requer mais código boilerplate; `fastapi-mcp` é mais simples para o caso de uso atual |
| `pytest-asyncio` | `anyio` (pytest-anyio) | `anyio` é o que FastAPI docs recomenda para async tests; `pytest-asyncio` tem ecossistema maior e é a escolha mais comum em projetos SQLAlchemy |

**Instalação:**
```bash
uv add fastapi-mcp
uv add --group dev pytest-asyncio
```

**Verificação de versão:**
```bash
# fastapi-mcp
uv run python -c "import fastapi_mcp; print(fastapi_mcp.__version__)"
# pytest-asyncio
uv run pytest --version
```

---

## Architecture Patterns

### System Architecture Diagram

```
MCP Client (Claude Desktop, Cursor, etc.)
        │ Bearer token no header
        ▼
[GET /mcp — FastApiMCP HTTP endpoint]
        │ propaga Authorization header (headers=["authorization"])
        ▼
[FastAPI ASGI — mesma app]
        │ Depends(get_current_user)
        ▼
[shared/auth.py — valida JWT Keycloak]
        │ retorna User autenticado
        ▼
[Endpoint REST filtrado por include_operations]
   GET /families/families → list_my_families()
        │
        ▼
[families/services.py — list_my_families(session, user)]
        │
        ▼
[AsyncSession → PostgreSQL caramello / caramello_dev]

─────────────────────────────────────────────────────

Test Runner (pytest)
        │ @pytest.mark.integration
        ▼
[conftest.py — fixtures async]
        │ engine → caramello_test
        ▼
[AsyncSession com savepoint (create_savepoint)]
        │ rollback ao final do teste
        ▼
[AsyncClient(transport=ASGITransport(app)) — sem Keycloak real]
        │ dependency_overrides[get_current_user] = lambda: fake_user
        │ dependency_overrides[get_session] = override_session
        ▼
[Endpoint REST → families/services.py → PostgreSQL caramello_test]
```

### Estrutura de Projeto Recomendada

```
src/caramello/
├── families/
│   ├── models.py            # (existente — gerado por DSL, não editar)
│   ├── operations.py        # (existente — endpoints REST com Depends(get_session))
│   ├── router.py            # (existente — CRUD gerado)
│   └── services.py          # NOVO — lógica extraída de operations.py
├── shared/
│   ├── auth.py              # (existente)
│   └── database.py          # (existente)
├── users/
│   └── ...                  # (existente)
└── main.py                  # EDITAR — adicionar FastApiMCP + APP_VERSION

tests/
├── conftest.py              # EDITAR — adicionar fixtures async + engine teste
├── test_auth.py             # (existente)
├── test_family_operations.py # (existente — unit tests com AsyncMock)
├── test_generator.py        # (existente)
├── test_api/
│   └── test_families_integration.py  # NOVO — testes de integração
└── test_services/
    └── test_family_service.py        # NOVO (opcional) — unit tests de services.py

Dockerfile                   # NOVO
compose.yaml                 # NOVO
```

### Pattern 1: Montagem do fastapi-mcp com Auth e Filtro de Operações

**O que é:** `FastApiMCP` recebe a app FastAPI, expõe endpoints selecionados como ferramentas MCP no path `/mcp`, com `AuthConfig` para exigir Bearer token e `headers=["authorization"]` para propagar o token aos endpoints subjacentes.

**Quando usar:** sempre que novos endpoints REST precisarem ser adicionados ao catálogo MCP.

**Exemplo:**
```python
# Source: Context7 /tadata-org/fastapi_mcp — auth.mdx + customization.mdx
import os
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer
from fastapi_mcp import FastApiMCP, AuthConfig

http_bearer = HTTPBearer()

app = FastAPI(
    title="Caramello Backend",
    version=os.getenv("APP_VERSION", "0.0.0"),
    lifespan=lifespan,
)

# ... routers registrados normalmente ...

mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    # Expõe apenas as operações MCP habilitadas para esta fase
    include_operations=["list_my_families"],
    auth_config=AuthConfig(
        dependencies=[Depends(http_bearer)],  # exige Bearer token no /mcp
    ),
    headers=["authorization"],  # propaga token para get_current_user() nos endpoints
)
mcp.mount_http()
```

**Ponto crítico:** `mcp.mount_http()` deve ser chamado **depois** de todos os `app.include_router()`. Se routers forem adicionados após a montagem, chamar `mcp.setup_server()` para re-registrar as ferramentas. [VERIFIED: Context7 /tadata-org/fastapi_mcp — refresh.mdx]

### Pattern 2: Extração de Services (D-MCP-03)

**O que é:** Lógica de query é movida de `operations.py` (que tem acoplamento ao router FastAPI) para `services.py` (funções puras que recebem `AsyncSession` + `User`).

**Quando usar:** Para que a mesma lógica seja chamável via testes de unidade sem fixtures de banco, e para dar testabilidade independente dos routers.

**Exemplo:**
```python
# src/caramello/families/services.py
# Source: padrão definido em D-MCP-03 (CONTEXT.md Phase 5)
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.users.models import User
from caramello.families.models import Family, FamilyMember
from sqlmodel import select

async def list_my_families(session: AsyncSession, user: User) -> list[Family]:
    """Retorna as famílias onde o usuário é membro."""
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == user.id)
    )
    return list(result.all())
```

```python
# src/caramello/families/operations.py — operação refatorada para chamar service
@router.get("/families", response_model=list[FamilyRead])
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Family]:
    from caramello.families.services import list_my_families as svc
    return await svc(session, current_user)
```

### Pattern 3: Fixtures Async com Transaction Rollback

**O que é:** Engine separado apontando para `caramello_test`, sessão por teste que usa savepoint para rollback sem custo de DROP/CREATE.

**Quando usar:** em todos os testes marcados com `@pytest.mark.integration`.

**Exemplo:**
```python
# tests/conftest.py — adições para Phase 5
# Source: padrão SQLAlchemy async + pytest-asyncio documentado em
# https://www.core27.co/post/transactional-unit-tests-with-pytest-and-async-sqlalchemy

import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient, ASGITransport

# URL do banco de teste — constrói a partir das mesmas vars do .env,
# substituindo apenas DB_NAME por caramello_test
TEST_DB_URL = (
    f"postgresql+asyncpg://{os.getenv('DB_USER', 'postgres')}"
    f":{os.getenv('DB_PASSWORD', 'postgres')}"
    f"@{os.getenv('DB_HOST', 'localhost')}"
    f":{os.getenv('DB_PORT', '5432')}"
    f"/caramello_test"
)

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Sessão async com rollback por teste via savepoint."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        await session.close()
        await conn.rollback()

@pytest_asyncio.fixture
async def async_client(db_session):
    """AsyncClient com override de get_session e get_current_user."""
    from caramello.main import app
    from caramello.shared.database import get_session
    from caramello.shared.auth import get_current_user
    from caramello.users.models import User
    from uuid import uuid4
    from datetime import datetime, timezone

    fake_user = User(
        id=1, uuid=uuid4(), idp_sub="test-sub",
        email="test@example.com", name="Test User",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def _session_override():
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_current_user] = lambda: fake_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

**Aviso de compatibilidade:** `pytest-asyncio` 1.4.0 introduz `loop_scope` em fixtures de sessão. Para evitar `ScopeMismatch`, adicionar ao `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```
[VERIFIED: Context7 /pytest-dev/pytest-asyncio — configuration.md]

### Pattern 4: Dockerfile Multi-Stage para Python/uv

**O que é:** Dois estágios — `builder` instala dependências com uv, `runtime` copia apenas o virtualenv instalado; non-root user.

**Quando usar:** build de produção — imagem menor, sem ferramentas de build no runtime layer.

**Exemplo:**
```dockerfile
# Source: padrão Docker multi-stage Python [ASSUMED — adaptado de práticas comuns]
ARG APP_VERSION=0.0.0

# ─── Stage 1: builder ───────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# uv para instalação de dependências
RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Instala dependências de produção num virtualenv
RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python -e . \
    && uv pip install --python /app/.venv/bin/python fastapi-mcp

# ─── Stage 2: runtime ───────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app

# Non-root user
RUN addgroup --system app && adduser --system --group app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src

ENV PATH="/app/.venv/bin:$PATH"

USER app

EXPOSE 8000
CMD ["uvicorn", "caramello.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Pattern 5: `APP_VERSION` na OpenAPI spec

**O que é:** Valor lido de variável de ambiente, injetado no `FastAPI(version=...)`. Visível em `/openapi.json` e na UI Swagger.

**Quando usar:** sempre que a versão do build precisar ser rastreável via API.

**Exemplo:**
```python
# src/caramello/main.py — trecho a adicionar
# Source: D-DOCKER-03 (CONTEXT.md Phase 5)
import os

app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version=os.getenv("APP_VERSION", "0.0.0"),
    lifespan=lifespan,
)
```

### Anti-Patterns a Evitar

- **Chamar `mcp.mount_http()` antes de `app.include_router()`:** os endpoints ainda não registrados na app não aparecem como ferramentas MCP. Sempre montar o MCP depois de registrar todos os routers.
- **Usar `TestClient` síncrono em testes de integração async:** `TestClient` não suporta `async def` nos fixtures. Usar `httpx.AsyncClient` com `ASGITransport`.
- **Compartilhar `AsyncSession` entre testes:** cada teste deve ter sua própria sessão com rollback independente.
- **Secrets como `ARG` no Dockerfile:** `ARG` fica visível no histórico de layers via `docker history`. Credenciais de banco e Keycloak devem ser passadas como env vars em tempo de runtime, não durante o build.
- **Hardcode de `DB_NAME=caramello_test` no `alembic/env.py`:** alembic lê `settings.DATABASE_URL`, que constrói a URL a partir de `DB_NAME`. Para rodar migrations no banco de teste, basta exportar `DB_NAME=caramello_test` antes de chamar `alembic`.

---

## Don't Hand-Roll

| Problema | Não Construir | Usar em vez disso | Por que |
|----------|--------------|-------------------|---------|
| Exposição de endpoints REST como MCP tools | Parser de OpenAPI manual | `FastApiMCP(app, include_operations=[...])` | fastapi-mcp converte a spec automaticamente, preserva schemas e documentação |
| Auth Bearer token no servidor MCP | Middleware custom | `AuthConfig(dependencies=[Depends(http_bearer)])` + `headers=["authorization"]` | Reutiliza a mesma infraestrutura de auth dos endpoints REST |
| Rollback de banco entre testes | DROP/TRUNCATE por teste | Transaction rollback com `join_transaction_mode="create_savepoint"` | Muito mais rápido; savepoint permite aninhamento; banco permanece preparado |
| Fixtures async no pytest | `asyncio.run()` manual | `pytest-asyncio` + `@pytest_asyncio.fixture` | Integração nativa com o event loop do pytest |
| Imagem Docker mínima | Copiar todo o código-fonte | Multi-stage build com `python:3.12-slim` | Imagem de runtime sem ferramentas de build; menor superfície de ataque |

---

## Common Pitfalls

### Pitfall 1: fastapi-mcp não suporta tools customizadas (D-MCP-02 precisa de revisão)

**O que dá errado:** O plano cria `src/caramello/mcp/tools.py` com funções anotadas como ferramentas MCP manualmente registradas, mas `FastApiMCP` ignora esse arquivo — ele só expõe endpoints FastAPI.

**Por que acontece:** A decisão D-MCP-02 foi baseada na suposição de que o fastapi-mcp suporta ferramentas manuais fora de endpoints. Isso não é verdade na versão 0.4.0.

**Como evitar:** A ferramenta `get_my_families` é o endpoint REST `GET /families/families` com `operation_id="list_my_families"`. O fastapi-mcp o expõe como ferramenta MCP via `include_operations=["list_my_families"]`. O arquivo `families/services.py` ainda faz sentido para separação de lógica e testabilidade, mas não é o caminho de integração MCP.

**Sinais de alerta:** Se o plano contiver `mcp.add_tool(...)` ou `@mcp_server.tool(...)`, está usando a API errada.

[VERIFIED: Context7 /tadata-org/fastapi_mcp — FAQ.mdx — "FastApiMCP only supports tools that are derived from FastAPI endpoints."]

### Pitfall 2: `mount_http()` vs `mount()` — ordem de registro dos routers

**O que dá errado:** `mcp.mount_http()` captura a lista de routers no momento em que é chamado. Routers adicionados depois não aparecem como ferramentas.

**Por que acontece:** `FastApiMCP` lê as rotas da app no momento da criação/montagem.

**Como evitar:** Sempre chamar `mcp.mount_http()` como **última operação** em `main.py`, depois de todos os `app.include_router()`. Se routers forem adicionados dinamicamente (não é o caso aqui), chamar `mcp.setup_server()` depois.

[VERIFIED: Context7 /tadata-org/fastapi_mcp — refresh.mdx]

### Pitfall 3: Conflito de event loop entre `TestClient` e `pytest-asyncio`

**O que dá errado:** Misturar fixtures async de `pytest-asyncio` com `TestClient` síncrono causa `RuntimeError: Event loop is closed` ou `Task attached to a different loop`.

**Por que acontece:** `TestClient` cria seu próprio event loop internamente. Fixtures async do `pytest-asyncio` operam em outro loop. Os dois não se misturam.

**Como evitar:** Testes de integração (com banco real) usam exclusivamente `httpx.AsyncClient` com `ASGITransport`. Testes de unidade existentes (com `AsyncMock`) continuam usando `TestClient` — não converter.

### Pitfall 4: `join_transaction_mode` — necessário para savepoints com asyncpg

**O que dá errado:** Sem `join_transaction_mode="create_savepoint"`, a sessão de teste não consegue criar savepoints dentro de uma transação externa (aberta pelo fixture de engine). O rollback não funciona.

**Por que acontece:** asyncpg tem comportamento diferente de psycopg2 em transações aninhadas.

**Como evitar:** Usar `AsyncSession(bind=conn, join_transaction_mode="create_savepoint")` no fixture `db_session`.

[CITED: https://github.com/sqlalchemy/sqlalchemy/discussions/10857]

### Pitfall 5: Secrets como `ARG` no Dockerfile (sem secrets nos layers)

**O que dá errado:** `ARG DB_PASSWORD` no Dockerfile armazena o valor no histórico de layers, visível via `docker history`.

**Por que acontece:** `ARG` e `ENV` durante o build ficam no cache de layers.

**Como evitar:** Apenas `APP_VERSION` é passado como `ARG`. Credenciais de banco e Keycloak são passadas como env vars em runtime (`docker run -e` ou `compose.yaml`), nunca durante o build.

### Pitfall 6: Nomenclatura divergente entre `.env.example` e `docs/apps-platform.md`

**O que dá errado:** A decisão D-NAMING-01 renomeia os bancos, mas `.env.example` ainda referencia `familia_dev` e `docs/apps-platform.md §5` documenta o esquema antigo. Operadores que seguem a documentação criarão o banco com nome errado.

**Por que acontece:** O projeto acumulou documentação inconsistente ao longo das fases — `CLAUDE.md` ainda diz `familia_dev`/`familia_prod`, `.env.example` diz `familia_dev`, mas a decisão é usar `caramello_dev`.

**Como evitar:** O plano deve incluir uma tarefa explícita de atualização de documentação: `.env.example`, `docs/apps-platform.md §5`, `CLAUDE.md §Constraints` e `REQUIREMENTS.md` (MODEL-03).

---

## Code Examples

### Integração MCP completa em `main.py`

```python
# Source: Context7 /tadata-org/fastapi_mcp — auth.mdx + customization.mdx
import os
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer
from fastapi_mcp import FastApiMCP, AuthConfig
from caramello.shared.auth import fetch_jwks, http_bearer

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await fetch_jwks()
    yield

app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version=os.getenv("APP_VERSION", "0.0.0"),
    lifespan=lifespan,
)

# ... CORS, routers ...
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)
app.include_router(families_router.router)

# MCP DEVE ser montado APÓS todos os include_router
mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    include_operations=["list_my_families"],  # operation_id do endpoint
    auth_config=AuthConfig(
        dependencies=[Depends(http_bearer)],
    ),
    headers=["authorization"],
)
mcp.mount_http()
```

### `bin/manage_db` com suporte a `--env test`

```bash
# Lógica a adicionar — bin/manage_db
# Antes do case "$COMMAND":

ENV_FLAG="dev"  # default
DB_NAME_OVERRIDE=""

# Parse --env flag
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_FLAG="$2"
      shift 2
      ;;
    *) break ;;
  esac
done

# Se --env test, sobrescreve DB_NAME para caramello_test
if [[ "$ENV_FLAG" == "test" ]]; then
  export DB_NAME="caramello_test"
fi
```

### `compose.yaml` alinhado com `docs/deploy.md`

```yaml
# Source: docs/deploy.md (existente, adaptado para APP_VERSION)
services:
  api:
    build:
      context: .
      args:
        APP_VERSION: ${APP_VERSION:-0.0.0}
    image: ghcr.io/henricos/caramello-api:${APP_VERSION:-latest}
    container_name: caramello-api
    restart: unless-stopped
    environment:
      ENVIRONMENT: ${ENVIRONMENT:-production}
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT:-5432}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME:-caramello}
      CORS_ORIGINS: ${CORS_ORIGINS:-}
      KEYCLOAK_URL: ${KEYCLOAK_URL}
      KEYCLOAK_REALM: ${KEYCLOAK_REALM}
      KEYCLOAK_CLIENT_ID: ${KEYCLOAK_CLIENT_ID}
    ports:
      - "${API_HOST_PORT:-8000}:8000"
```

---

## State of the Art

| Abordagem Antiga | Abordagem Atual | Quando Mudou | Impacto |
|-----------------|-----------------|-------------|---------|
| `mcp.mount()` (SSE) | `mcp.mount_http()` (HTTP transport) | fastapi-mcp >= 0.3.0 | HTTP transport é o recomendado para novas implementações; SSE ainda funciona mas é legado |
| `TestClient` síncrono para tudo | `AsyncClient` para testes de integração async | pytest-asyncio >= 0.21 | Testes com banco real requerem async; `TestClient` continua válido para unit tests com mocks |
| `psycopg2-binary` síncrono | `asyncpg` + `AsyncSession` | Phase 2 (concluída) | Já implementado no projeto |

**Deprecated/Outdated:**
- `mcp.mount()`: ainda funciona mas `mount_http()` é o método recomendado pelo fastapi-mcp 0.4.0 [VERIFIED: Context7 /tadata-org/fastapi_mcp — transport.mdx]
- `event_loop` fixture: deprecated no pytest-asyncio >= 0.23; usar `asyncio_mode = "auto"` no `pyproject.toml` [VERIFIED: Context7 /pytest-dev/pytest-asyncio]

---

## Runtime State Inventory

> Esta fase não é rename/refactor, mas inclui a decisão D-NAMING-01 que renomeia bancos de dados.

| Categoria | Itens Encontrados | Ação Necessária |
|-----------|------------------|-----------------|
| Stored data | Banco `familia_dev` existe no PostgreSQL de dev com dados do usuário | Criar `caramello_dev` novo; não renomear (operação de banco) — confirmar com operador |
| Live service config | N/A — sem serviços externos com nome do banco | — |
| OS-registered state | N/A | Nenhum |
| Secrets/env vars | `.env` tem `DB_NAME=familia_dev`; `.env.example` tem `DB_NAME=familia_dev` | Atualizar `.env.example` para `caramello_dev`; operador atualiza `.env` manualmente |
| Build artifacts | N/A — sem binários compilados | Nenhum |

**Atenção:** O banco `caramello_test` é novo — precisa ser criado via `bin/manage_db init --env test` antes de rodar os testes de integração. Isso é responsabilidade do operador, não do teste em si (D-TEST-03).

---

## Open Questions

1. **`operation_id` do endpoint `list_my_families`**
   - O que sabemos: FastAPI gera `operation_id` automático como `list_my_families_families_families_get` se não for especificado explicitamente.
   - O que está unclear: o endpoint atual em `operations.py` não define `operation_id` explícito. O `include_operations` precisa do `operation_id` exato.
   - Recomendação: adicionar `operation_id="list_my_families"` ao decorator `@router.get("/families", ...)` em `operations.py`. Isso também melhora a legibilidade da spec OpenAPI para clientes MCP.

2. **`families/services.py` ainda faz sentido como extração?**
   - O que sabemos: D-MCP-03 pede a extração para `services.py`. O MCP não precisa mais dela diretamente (usa o endpoint). Mas a extração tem valor de testabilidade.
   - Recomendação: manter a extração para `services.py` — os testes de integração podem chamar tanto via endpoint quanto via service diretamente. Isso também prepara o terreno para M2.

3. **`caramello_dev` vs `familia_dev` — migração de dados**
   - O que sabemos: D-NAMING-01 define `caramello_dev` como novo nome, mas o banco físico atual é `familia_dev`. Renomear exige operação de banco (não é só código).
   - O que está unclear: se o operador tem dados de dev que precisa preservar ou se pode criar um banco limpo.
   - Recomendação: o plano deve incluir uma tarefa documentada "operador cria `caramello_dev` e `caramello_test` via `bin/setup_db` ou SQL direto" — não automatizar a migração de dados de dev.

---

## Environment Availability

| Dependência | Requerida por | Disponível | Versão | Fallback |
|-------------|--------------|------------|--------|---------|
| Docker Engine | DEPLOY-01, DEPLOY-02 | ✓ | 29.4.3 | — |
| Docker Compose v2 | DEPLOY-02 | ✓ | 5.1.3 | — |
| PostgreSQL | TEST-01, TEST-02 (banco `caramello_test`) | Indisponível neste ambiente CI | — | Testes de integração marcados `@pytest.mark.integration` são pulados automaticamente sem PG |
| `fastapi-mcp` | MCP-01, MCP-02 | ✗ (não instalada) | 0.4.0 disponível | — |
| `pytest-asyncio` | TEST-01, TEST-02 | ✗ (não instalada) | 1.4.0 disponível | — |

[VERIFIED: `docker --version` → 29.4.3; `docker compose version` → 5.1.3; `uv run python -c "import fastapi_mcp"` → ModuleNotFoundError; `uv run python -c "import pytest_asyncio"` → ModuleNotFoundError]

**Dependências faltando sem fallback (bloqueiam execução):**
- `fastapi-mcp` — necessária para MCP-01 e MCP-02. Instalar com `uv add fastapi-mcp`.
- `pytest-asyncio` — necessária para TEST-01 e TEST-02. Instalar com `uv add --group dev pytest-asyncio`.
- PostgreSQL com banco `caramello_test` — necessário para TEST-01 e TEST-02. Operador deve criar via `bin/manage_db init --env test` (após evolução do script).

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 9.0.1 + pytest-asyncio 1.4.0 (a instalar) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Comando rápido | `uv run pytest -m "not integration"` |
| Suite completa | `uv run pytest` (requer `caramello_test` disponível) |

### Phase Requirements → Test Map

| Req ID | Comportamento | Tipo de Teste | Comando Automatizado | Arquivo Existe? |
|--------|--------------|---------------|----------------------|----------------|
| MCP-01 | `/mcp` descobre ferramenta `list_my_families` | smoke (manual com cliente MCP) | — (manual) | ❌ Wave 0: smoke test na Wave de verificação |
| MCP-02 | `/mcp` sem Bearer retorna 401/403 | integration | `uv run pytest tests/test_api/test_mcp.py -m integration -x` | ❌ Wave 0 |
| DEPLOY-01 | `docker build` completa sem erro | smoke (manual) | `docker build --build-arg APP_VERSION=test .` | ❌ Wave 0: verificação no plano Docker |
| DEPLOY-02 | `docker compose up` com env vars | smoke (manual) | — | ❌ manual |
| DEPLOY-03 | `APP_VERSION` aparece em `/openapi.json` | integration | `uv run pytest tests/test_api/test_version.py -x` | ❌ Wave 0 |
| TEST-01 | Banco `caramello_test` isolado com rollback | meta-teste / fixture | Confirmado por execução bem-sucedida dos testes de integração | ❌ Wave 0: conftest.py |
| TEST-02 | Criar família via endpoint, listar membros | integration | `uv run pytest tests/test_api/test_families_integration.py -m integration -x` | ❌ Wave 0 |
| TEST-03 | `dependency_overrides` mock de auth sem Keycloak | integration | (incluído em TEST-02) | ❌ Wave 0 |

### Sampling Rate

- **Por task commit:** `uv run pytest -m "not integration"` (unit tests sem PG, < 5s)
- **Por wave merge:** `uv run pytest` (suite completa, requer `caramello_test`)
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — adicionar fixtures `test_engine`, `db_session`, `async_client`
- [ ] `tests/test_api/test_families_integration.py` — testes de integração family (TEST-02, TEST-03)
- [ ] `tests/test_api/test_mcp.py` — smoke test de auth no `/mcp` (MCP-02)
- [ ] `tests/test_api/test_version.py` — verificação de `APP_VERSION` em `/openapi.json` (DEPLOY-03)
- [ ] Instalar: `uv add fastapi-mcp && uv add --group dev pytest-asyncio`
- [ ] Adicionar `asyncio_mode = "auto"` em `[tool.pytest.ini_options]` no `pyproject.toml`

---

## Security Domain

### ASVS Categories Aplicáveis

| Categoria ASVS | Aplica | Controle Padrão |
|----------------|--------|-----------------|
| V2 Authentication | sim | JWT RS256 via `get_current_user()` — já implementado em Phase 3 |
| V3 Session Management | não | Sem estado de sessão server-side; tokens JWT stateless |
| V4 Access Control | sim | `AuthConfig(dependencies=[Depends(http_bearer)])` no `FastApiMCP` |
| V5 Input Validation | sim | Pydantic schemas nos endpoints; sem input direto no MCP (usa endpoints) |
| V6 Cryptography | não aplicável diretamente | JWT validado via PyJWT + JWKS — não hand-roll |

### Threat Patterns para o Stack MCP

| Pattern | STRIDE | Mitigação Padrão |
|---------|--------|-----------------|
| Token do cliente MCP não propagado para endpoints | Spoofing | `headers=["authorization"]` obrigatório no `FastApiMCP` |
| Endpoint REST exposto via MCP sem querer | Elevation of Privilege | `include_operations` explícito — whitelist, não blacklist |
| Secrets (`DB_PASSWORD`, `KEYCLOAK_*`) nos layers do Dockerfile | Information Disclosure | Apenas `APP_VERSION` como `ARG`; credenciais via env em runtime |
| Token expirado aceito por cliente MCP sem re-validação | Tampering | `get_current_user()` valida JWT em cada chamada — sem cache de sessão |

---

## Project Constraints (from CLAUDE.md)

- **Stack obrigatório:** Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL. SQLite **não suportado**.
- **Package manager:** `uv` — instalar dependências com `uv add`, não `pip install` direto.
- **Código gerado:** arquivos em `src/caramello/models/` e `src/caramello/api/generated/` **não devem ser editados**. `families/services.py` é código manual — não gerado.
- **Nomenclatura de banco:** após D-NAMING-01, usar `caramello` (prod), `caramello_dev` (dev), `caramello_test` (test). Atualizar `CLAUDE.md §Constraints` também faz parte da limpeza de documentação.
- **Idioma:** código e configs em inglês; commits, docs narrativos e comentários explicativos em pt-BR.
- **Commits:** Conventional Commits, pt-BR, presente do indicativo terceira pessoa.
- **Qualidade:** `ruff check src/` e `mypy src/` devem passar sem erros em todo código novo.

---

## Assumptions Log

| # | Claim | Seção | Risco se Errado |
|---|-------|-------|----------------|
| A1 | O Dockerfile usa `python:3.12-slim` como base runtime | Standard Stack / Pattern 4 | Imagem maior se usar `python:3.12`; versão menor se usar `3.11-slim` — verificar contra política do operador |
| A2 | `uv pip install -e .` dentro do Dockerfile instala corretamente sem acesso ao `uv.lock` no contexto de build | Pattern 4 | Pode precisar de `COPY uv.lock` explícito ou usar `uv sync` — testar no `docker build` |
| A3 | O banco `caramello_test` deve ser criado com o mesmo schema do dev — via `alembic upgrade head` com `DB_NAME=caramello_test` | Runtime State Inventory | Alembic lê de `settings.DATABASE_URL`; se `settings` for singleton inicializado no import, sobrescrever `DB_NAME` via env antes do import é necessário |
| A4 | `join_transaction_mode="create_savepoint"` funciona com `asyncpg` na versão atual do SQLAlchemy | Pattern 3 | Se não funcionar, fallback: `await session.begin_nested()` explícito — testar no Wave 0 |

---

## Sources

### Primary (HIGH confidence)
- Context7 `/tadata-org/fastapi_mcp` — FAQ, auth, transport, customization, refresh (custom tools, AuthConfig, headers, mount_http, include_operations)
- Context7 `/pytest-dev/pytest-asyncio` — configuration, fixtures, asyncio_mode
- PyPI registry — versões verificadas: fastapi-mcp 0.4.0, pytest-asyncio 1.4.0
- Codebase — `src/caramello/main.py`, `src/caramello/families/operations.py`, `src/caramello/shared/auth.py`, `tests/conftest.py`, `tests/test_family_operations.py`, `pyproject.toml`, `bin/manage_db`

### Secondary (MEDIUM confidence)
- https://www.core27.co/post/transactional-unit-tests-with-pytest-and-async-sqlalchemy — padrão de transaction rollback async SQLAlchemy
- https://fastapi.tiangolo.com/advanced/async-tests/ — AsyncClient + ASGITransport com FastAPI
- https://github.com/sqlalchemy/sqlalchemy/discussions/10857 — `join_transaction_mode` com asyncpg

### Tertiary (LOW confidence)
- Nenhum item de LOW confidence neste research.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versões verificadas no PyPI registry
- Architecture: HIGH — fastapi-mcp API verificada via Context7 + documentação oficial
- Pitfalls: HIGH (Pitfall 1 crítico verificado via Context7 FAQ oficial)
- Docker patterns: MEDIUM — padrão multi-stage amplamente conhecido; detalhes do `uv` no Dockerfile marcados como [ASSUMED]

**Research date:** 2026-05-26
**Valid until:** 2026-08-26 (stack estável; fastapi-mcp está em desenvolvimento ativo — verificar changelog antes de implementar se for > 30 dias)
