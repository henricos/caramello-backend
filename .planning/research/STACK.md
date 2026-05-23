# Technology Stack — caramello-api M1

**Projeto:** caramello-api (Grupo Família backend)
**Pesquisado:** 2026-05-23
**Confiança geral:** HIGH (todas as versões verificadas no PyPI; padrões verificados em Context7 e fontes oficiais)

---

## Stack recomendado

### Core Framework

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| Python | 3.12 | Runtime | 3.10+ obrigatório; 3.12 é a versão estável com melhor suporte de ferramentas |
| FastAPI | ≥0.100.0 | Framework web async | Decisão existente; compatível com fastapi-mcp |
| uvicorn | ≥0.20.0 | ASGI server | Par natural do FastAPI; suporta uvloop no Docker |
| pydantic v2 | ≥2.0.0 | Validação/schemas | FastAPI depende; v2 obrigatório para sqlmodel 0.0.38+ |
| pydantic-settings | ≥2.5.2 | Config por env vars | Já em uso; versão mínima exigida pelo fastapi-mcp |

### Banco de dados

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| PostgreSQL | 15+ | Banco relacional | Já rodando na infra; família_dev / família_prod |
| asyncpg | 0.31.0 | Driver async nativo | O único driver que faz PostgreSQL realmente async com SQLAlchemy; psycopg3 existe mas asyncpg tem mais tracção com SQLModel |
| SQLAlchemy | ≥2.0 | ORM + async engine | `create_async_engine` + `async_sessionmaker` — base do async stack |
| SQLModel | 0.0.38 | Modelos unificados Pydantic+SA | Já em uso; versão 0.0.38 é a atual; sem wrappers async próprios |
| Alembic | atual | Migrations | Já configurado; permanece sem alterações no setup |

**Nota de compatibilidade (HIGH confidence — verificado):** SQLModel 0.0.38 não tem wrappers async próprios. O padrão correto é importar `AsyncSession` e `create_async_engine` diretamente do `sqlalchemy.ext.asyncio`, não do sqlmodel. O SQLModel funciona como camada de modelo; a infra de sessão usa SQLAlchemy puro.

### Autenticação

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| PyJWT | 2.13.0 | Validação JWT/RS256 | Ativo, mantido, suporta `PyJWKClient` com cache de chaves. python-jose está abandonado (último release 2021) |
| cryptography | ≥41.0 | Backend crypto para PyJWT[crypto] | Exigido para RS256; instalado via extra `PyJWT[crypto]` |

**Não usar:** python-jose — último release foi 2021, não recebe atualizações, vulnerabilidades acumuladas. PyJWT com `[crypto]` extra é o substituto direto.

### MCP

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| fastapi-mcp | 0.4.0 | Expor endpoints FastAPI como tools MCP | Decisão já tomada; monta diretamente na app FastAPI, sem serviço separado |
| mcp | ≥1.12.0 | Protocolo MCP (dependência indireta) | Puxado pelo fastapi-mcp |

### Qualidade

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| ruff | 0.15.x | Linter + formatter | Substitui flake8+isort+black em um binário; exigido por docs/quality_rules.md |
| mypy | 2.1.0 | Type checking | Exigido por docs/quality_rules.md |

### Testes

| Tecnologia | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| pytest | ≥9.0.1 | Test runner | Já em dev dependencies |
| pytest-asyncio | 1.3.0 | Suporte async em fixtures e tests | Versão atual; obrigatório para AsyncSession fixtures |
| httpx | 0.28.1 | HTTP client para TestClient async | Já em dev dependencies; exigido pelo AsyncClient do FastAPI |

---

## Configuração detalhada por área

### 1. asyncpg + SQLAlchemy async + FastAPI

**Connection string:**
```
postgresql+asyncpg://user:password@host:5432/familia_dev
```

**`src/caramello/database/session.py` (reescrita completa):**
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from caramello.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,  # deve usar postgresql+asyncpg://
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # obrigatório em async: evita lazy load implícito pós-commit
)

async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Por que `expire_on_commit=False`:** Em async, acessar atributo de objeto após commit dispara um lazy load que tenta IO síncrono — e isso falha silenciosamente ou levanta `MissingGreenlet`. Com `expire_on_commit=False`, os atributos do objeto permanecem acessíveis após commit sem nova query.

**Dependency injection nos routers:**
```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from caramello.database.session import get_async_session

SessionDep = Annotated[AsyncSession, Depends(get_async_session)]

@router.get("/items")
async def list_items(session: SessionDep):
    result = await session.execute(select(Item))
    return result.scalars().all()
```

**Alembic com asyncpg:** O `alembic/env.py` precisa usar `run_async_migrations` com `connectable.connect()` async. O padrão está em `alembic.ini` apontando para a mesma URL com `+asyncpg`.

---

### 2. Keycloak + FastAPI — validação JWT/OIDC

**Padrão recomendado:** PyJWT com `PyJWKClient` (cache automático de JWKS). O token é validado localmente a partir da chave pública do Keycloak — sem round-trip ao Keycloak por request.

**`src/caramello/shared/auth.py`:**
```python
from functools import lru_cache
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from caramello.core.config import settings

security = HTTPBearer()

@lru_cache(maxsize=1)
def get_jwks_client() -> PyJWKClient:
    # Keycloak JWKS endpoint:
    # {keycloak_url}/realms/{realm}/protocol/openid-connect/certs
    return PyJWKClient(
        settings.KEYCLOAK_JWKS_URL,
        cache_keys=True,
        lifespan=3600,
    )

class TokenPayload(BaseModel):
    sub: str            # Keycloak user ID — vira idp_sub na tabela users
    email: str | None = None
    preferred_username: str | None = None
    realm_roles: list[str] = []

def decode_token(token: str) -> TokenPayload:
    client = get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,  # ou "account" dependendo da config do realm
            issuer=settings.KEYCLOAK_ISSUER,        # {keycloak_url}/realms/{realm}
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Audience inválido")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Token inválido: {e}")

    realm_roles = payload.get("realm_access", {}).get("roles", [])
    return TokenPayload(
        sub=payload["sub"],
        email=payload.get("email"),
        preferred_username=payload.get("preferred_username"),
        realm_roles=realm_roles,
    )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> TokenPayload:
    return decode_token(credentials.credentials)

CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
```

**Variáveis de ambiente necessárias:**
```
KEYCLOAK_JWKS_URL=https://{host}/realms/{realm}/protocol/openid-connect/certs
KEYCLOAK_ISSUER=https://{host}/realms/{realm}
KEYCLOAK_CLIENT_ID={client-id-configurado-no-realm}
```

**Atenção ao `audience`:** Keycloak emite tokens com `aud` variável dependendo de como o client está configurado. Se o realm usa `account` como audiência padrão, use `audience="account"`. Se o client tem `audience mapper` configurado, use o client ID. Precisa ser verificado contra o Keycloak real do projeto.

---

### 3. fastapi-mcp — integração

**Versão atual:** 0.4.0 (julho 2025). Requer Python ≥3.10, FastAPI ≥0.100.0, mcp ≥1.12.0.

**Mounting pattern (minimal):**
```python
# src/caramello/main.py
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI(title="Caramello API")

# ... registrar routers de domínio ...

mcp = FastApiMCP(app)
mcp.mount()
# MCP server disponível em /mcp
```

**Com autenticação via dependência existente:**
```python
from caramello.shared.auth import get_current_user

mcp = FastApiMCP(
    app,
    # fastapi-mcp usa as dependências FastAPI declaradas nos endpoints —
    # endpoints marcados com Depends(get_current_user) ficam protegidos no MCP também
)
mcp.mount()
```

**Ordem importa:** `mcp.mount()` deve ser chamado **após** todos os routers estarem registrados. Se montar antes, os tools MCP não incluirão os endpoints adicionados depois.

**O MCP não duplica lógica:** Expõe os mesmos endpoints REST como tools. Isso valida a decisão arquitetural de colocar lógica em `services.py` — os endpoints MCP são automaticamente wrappers finos.

---

### 4. Dockerfile multi-stage com uv e non-root user

**Padrão recomendado para Python/FastAPI com uv:**

```dockerfile
# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.12
ARG APP_VERSION=dev

# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# Copia o binário uv da imagem oficial — mais rápido que instalar via pip
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copia manifests primeiro — camadas de deps ficam em cache entre builds
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copia código depois (muda com frequência, não invalida cache de deps)
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Non-root user — UID/GID fixos para consistência entre builds
RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

# Copia apenas o venv e o código — sem build tools no runtime
COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --from=builder --chown=app:app /app/src ./src
COPY --from=builder --chown=app:app /app/alembic ./alembic
COPY --from=builder --chown=app:app /app/alembic.ini ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "caramello.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**compose.yaml (desenvolvimento):**
```yaml
services:
  api:
    build:
      context: .
      args:
        APP_VERSION: dev
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: familia_dev
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

**Decisões chave do Dockerfile:**
- `UV_COMPILE_BYTECODE=1`: Bytecode compilado no build, não no startup — reduz tempo de cold start
- `UV_LINK_MODE=copy`: Evita hardlinks que não funcionam entre stages Docker
- `uv.lock*`: O glob aceita projetos sem lockfile ainda; usar `uv.lock` sem glob em produção real
- `--mount=type=cache`: Cache persistente do uv entre builds sem adicionar ao layer final
- UID/GID `1001`: Fixos, não root, consistentes

---

### 5. pytest + pytest-asyncio com banco isolado

**Versão atual:** pytest-asyncio 1.3.0. Mudança importante: a partir da 1.x, o modo padrão mudou e o modo `auto` precisa ser declarado explicitamente.

**`pyproject.toml` — configuração de testes:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**`tests/conftest.py` — fixtures de banco isoladas:**
```python
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from caramello.main import app
from caramello.database.session import get_async_session

TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost/familia_test"

# Engine de sessão — criado uma vez por suite
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()

# Session factory por engine de teste
@pytest_asyncio.fixture(scope="session")
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# Sessão isolada por teste — limpa a tabela via truncate ou cria nova transação
@pytest_asyncio.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
        await session.rollback()

# Override da dependency do app
@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

**Estratégia de isolamento:** Rollback por teste (padrão acima) é simples e sem custo de schema. Para fixtures com `scope="session"` que precisam de dados compartilhados, usar `scope="session"` com `loop_scope="session"` no decorator `@pytest_asyncio.fixture`.

**Autenticação nos testes:** Sobrescrever `get_current_user` com um usuário fixo fake:
```python
from caramello.shared.auth import get_current_user, TokenPayload

@pytest.fixture
def mock_user():
    return TokenPayload(sub="test-sub-uuid", email="test@familia.test")

@pytest_asyncio.fixture
async def auth_client(client, mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)
```

---

## Alternativas descartadas

| Categoria | Recomendado | Alternativa | Por que não |
|-----------|-------------|-------------|-------------|
| JWT | PyJWT 2.13.0 | python-jose | Abandonado desde 2021, vulnerabilidades conhecidas |
| JWT | PyJWT 2.13.0 | authlib | Mais complexo, orientado a OAuth server; aqui só precisamos de validação |
| Auth wrapper | Implementação própria | fastapi-keycloak-middleware | Middleware pesado demais; caveats de path-only exclusion; PyJWT direto é mais previsível |
| Driver DB | asyncpg | psycopg3 (asyncio) | asyncpg tem mais tracção com SQLModel/SA 2.0; psycopg3 async é alternativa válida mas menor ecossistema de exemplos |
| Test isolation | Rollback por teste | Drop/recreate tables por teste | Rollback é mais rápido; recreate só vale se tiver DDL-heavy no setup |
| Async mode | pytest-asyncio | anyio | anyio é preferido por FastAPI internamente, mas pytest-asyncio 1.3.0 funciona bem e tem mais exemplos na comunidade FastAPI |

---

## Instalação

```bash
# Remover driver síncrono
uv remove psycopg2-binary

# Core async
uv add "asyncpg>=0.31.0" "sqlalchemy[asyncio]>=2.0" "sqlmodel>=0.0.38"

# Auth
uv add "PyJWT[crypto]>=2.13.0"

# MCP
uv add "fastapi-mcp>=0.4.0"

# Qualidade
uv add --dev "ruff>=0.15.0" "mypy>=2.1.0"

# Testes
uv add --dev "pytest>=9.0.1" "pytest-asyncio>=1.3.0" "httpx>=0.28.1"
```

---

## Compatibilidade entre bibliotecas verificada

| Par | Versão | Status | Observação |
|-----|--------|--------|------------|
| SQLModel 0.0.38 + SQLAlchemy 2.0 | compatível | OK | SQLModel usa SA 2.0 internamente desde 0.0.22+ |
| asyncpg 0.31.0 + SQLAlchemy 2.0 | compatível | OK | SA 2.0 suporta asyncpg 0.29+ — o bug anterior com 0.29 foi corrigido |
| FastAPI + fastapi-mcp 0.4.0 | FastAPI ≥0.100.0 | OK | Já compatível com versão atual do FastAPI |
| PyJWT 2.13.0 + Python 3.12 | suportado | OK | PyPI confirma suporte 3.9–3.14 |
| pytest-asyncio 1.3.0 + pytest 9.x | compatível | OK | Versões atuais |

---

## Fontes

- SQLAlchemy async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html (Context7, HIGH)
- PyJWT + Keycloak pattern: https://skycloak.io/blog/keycloak-fastapi-python-api-authentication/ (MEDIUM — verificado contra PyPI)
- fastapi-mcp GitHub: https://github.com/tadata-org/fastapi_mcp (HIGH — README oficial)
- pytest-asyncio docs: https://github.com/pytest-dev/pytest-asyncio (Context7, HIGH)
- pytest-asyncio fixtures: https://praciano.com.br/fastapi-and-async-sqlalchemy-20-with-pytest-done-right.html (MEDIUM)
- Docker uv pattern: https://medium.com/@peziere.antonin/guide-senior-fastapi-docker-uv-patterns-production-2025-6443709dfc62 (MEDIUM)
- Versões verificadas diretamente no PyPI via `pip index versions`
