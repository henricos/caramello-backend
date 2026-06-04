# Phase 5: MCP, Testes e Docker - Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 12
**Analogs found:** 10 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/caramello/families/services.py` | service | CRUD | `src/caramello/families/operations.py` | exact (extração direta) |
| `src/caramello/main.py` | config/entrypoint | request-response | `src/caramello/main.py` (si mesmo) | self-modify |
| `tests/conftest.py` | test-fixture | CRUD + async | `tests/test_family_operations.py` | role-match |
| `tests/test_api/test_families_integration.py` | test | CRUD + integration | `tests/test_family_operations.py` | role-match |
| `tests/test_api/test_mcp.py` | test | request-response | `tests/test_family_operations.py` | role-match |
| `tests/test_api/test_version.py` | test | request-response | `tests/test_family_operations.py` | partial-match |
| `Dockerfile` | config | — | nenhum análogo no repo | no-analog |
| `compose.yaml` | config | — | `docs/deploy.md` §3 (trecho YAML) | partial-match |
| `bin/manage_db` | utility/script | — | `bin/manage_db` (si mesmo) | self-modify |
| `.env.example` | config | — | `.env.example` (si mesmo) | self-modify |
| `pyproject.toml` | config | — | `pyproject.toml` (si mesmo) | self-modify |
| `docs/apps-platform.md` | documentation | — | `docs/apps-platform.md` (si mesmo) | self-modify |

---

## Pattern Assignments

### `src/caramello/families/services.py` (service, CRUD)

**Analog:** `src/caramello/families/operations.py`

**Imports pattern** (lines 17-38 do analog):
```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.families.models import (
    Family,
    FamilyInvitation,
    FamilyMember,
    FamilyRead,
)
from caramello.users.models import User
```

**Nota crítica:** `services.py` NÃO importa `fastapi`, `APIRouter`, `Depends`, `HTTPException` — esses ficam em `operations.py`. O service recebe `AsyncSession` e `User` como parâmetros diretos (não via `Depends`).

**Core pattern — extração de `list_my_families`** (lines 160-171 do analog):
```python
# Em operations.py — lógica a EXTRAIR para services.py:
async def list_my_families(session: AsyncSession, user: User) -> list[Family]:
    """Retorna as famílias onde o usuário autenticado é membro."""
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)  # type: ignore[arg-type]
        .where(FamilyMember.user_id == user.id)
    )
    return list(result.all())
```

**Endpoint em operations.py após extração** (refatorar lines 160-171):
```python
@router.get("/families", response_model=list[FamilyRead], operation_id="list_my_families")
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Family]:
    """FAMILY-02: lista famílias onde o usuário autenticado é membro."""
    from caramello.families.services import list_my_families as svc
    return await svc(session, current_user)
```

**Nota sobre `operation_id`:** O `operation_id="list_my_families"` é obrigatório para que `include_operations=["list_my_families"]` no `FastApiMCP` funcione. Sem ele, FastAPI gera um `operation_id` automático diferente.

**Error handling:** Services não levantam `HTTPException` — erros de domínio devem ser erros Python puros ou `None` retornado; o caller (operations.py) trata e levanta HTTPException.

---

### `src/caramello/main.py` (config/entrypoint — modificar)

**Base:** `src/caramello/main.py` (atual)

**Imports a adicionar** (após line 15):
```python
import os

from fastapi.security import HTTPBearer
from fastapi_mcp import AuthConfig, FastApiMCP
```

**APP_VERSION pattern** (substituir line 33-38):
```python
app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version=os.getenv("APP_VERSION", "0.0.0"),
    lifespan=lifespan,
)
```

**MCP mount pattern — APÓS todos os include_router** (adicionar após line 56):
```python
# MCP — montar DEPOIS de todos os include_router (pitfall: routers registrados
# após mount_http não aparecem como ferramentas)
http_bearer = HTTPBearer()
mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    include_operations=["list_my_families"],  # operation_id explícito em operations.py
    auth_config=AuthConfig(
        dependencies=[Depends(http_bearer)],
    ),
    headers=["authorization"],  # propaga token para get_current_user()
)
mcp.mount_http()
```

**Imports contexto** (line 15-16 existente — manter `http_bearer` do auth.py se já existe lá):
```python
# shared/auth.py já exporta http_bearer — importar de lá para evitar duplicidade:
from caramello.shared.auth import fetch_jwks, http_bearer
```

**Anti-pattern a evitar:** Não criar `tools.py` manual — `fastapi-mcp` 0.4.0 só expõe endpoints FastAPI como ferramentas, não funções customizadas.

---

### `tests/conftest.py` (test-fixture — modificar)

**Base:** `tests/conftest.py` (atual — 14 linhas, substituir + expandir)

**Padrão atual** (lines 1-14 — manter o `client` fixture existente):
```python
"""Fixtures compartilhadas para os testes do Caramello."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient da app FastAPI, importado tarde para evitar erros em waves anteriores."""
    from caramello.main import app
    return TestClient(app)
```

**Fixtures async a adicionar** (novas fixtures após as existentes):
```python
import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from httpx import AsyncClient, ASGITransport

# URL do banco de teste — substitui apenas DB_NAME por caramello_test
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

**Padrão de fake_user:** copiar de `test_family_operations.py` lines 22-36 — mesmo padrão `_make_fake_user()` com todos os campos obrigatórios do modelo `User`.

---

### `tests/test_api/test_families_integration.py` (test, integration)

**Analog:** `tests/test_family_operations.py`

**Marcação e imports obrigatórios** (linhas 1-20 do novo arquivo):
```python
"""Testes de integração do domínio families — banco real caramello_test.

Usa transaction rollback por teste (fixtures db_session + async_client de conftest.py).
Requer: bin/manage_db init --env test previamente executado.
"""
from __future__ import annotations

import pytest
```

**Padrão de teste** — cada teste recebe `async_client` como fixture (não `client`):
```python
@pytest.mark.integration
async def test_create_family(async_client):
    """POST /families/registry cria família com banco real."""
    response = await async_client.post(
        "/families/registry",
        json={"name": "Familia Integração"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Familia Integração"
    assert "uuid" in data
```

**Padrão `dependency_overrides` para auth** (base em `test_family_operations.py` lines 132-137):
```python
# NOTA: o override de auth já está encapsulado no fixture async_client (conftest.py)
# Testes de integração NÃO repetem app.dependency_overrides — usam async_client diretamente.
# Para testes que precisam de usuário diferente, criar fixture alternativa em conftest.
```

**Padrão de estrutura por caso de uso:**
- `test_create_family` — POST /families/registry → 201
- `test_list_my_families` — GET /families/families → 200 lista
- `test_pre_register_member` — POST /families/{uuid}/pre-register → 201
- `test_list_members` — GET /families/{uuid}/members → 200 lista

---

### `tests/test_api/test_mcp.py` (test, request-response)

**Analog:** `tests/test_family_operations.py` (padrão `dependency_overrides` + TestClient)

**Padrão de smoke test sem banco real** (pode usar `client` síncrono do conftest):
```python
"""Smoke tests do endpoint MCP — verifica auth e descoberta de ferramentas.

Estes testes NÃO são marcados como integration — não precisam de caramello_test.
Verificam apenas que /mcp existe, exige auth, e retorna estrutura MCP válida.
"""
from __future__ import annotations

import pytest


def test_mcp_requires_auth(client):
    """MCP-02: GET /mcp sem Bearer token retorna 401 ou 403."""
    response = client.get("/mcp")
    assert response.status_code in (401, 403)
```

**Padrão com auth mockada** (base em lines 135-155 do analog):
```python
def test_mcp_with_valid_token_returns_tools(client):
    """MCP-01: GET /mcp com token válido retorna estrutura com ferramentas."""
    from caramello.main import app
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
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        response = client.get("/mcp")
        # /mcp com fastapi-mcp retorna spec MCP — 200 ou redirect
        assert response.status_code in (200, 307)
    finally:
        app.dependency_overrides.clear()
```

---

### `tests/test_api/test_version.py` (test, request-response)

**Analog:** `tests/test_family_operations.py` (TestClient básico)

**Padrão** — sem banco, sem auth:
```python
"""Verifica que APP_VERSION aparece no campo version da OpenAPI spec (DEPLOY-03)."""
from __future__ import annotations

import os


def test_openapi_version_field(client):
    """DEPLOY-03: /openapi.json contém campo version com APP_VERSION ou fallback."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "info" in spec
    assert "version" in spec["info"]
    # Sem APP_VERSION setado, fallback deve ser "0.0.0"
    expected = os.getenv("APP_VERSION", "0.0.0")
    assert spec["info"]["version"] == expected
```

---

### `Dockerfile` (config — novo)

**Sem análogo no repo.** Padrão: multi-stage Python/uv conforme RESEARCH.md Pattern 4.

**Estrutura a seguir** (RESEARCH.md lines 407-445):
```dockerfile
ARG APP_VERSION=0.0.0

# Stage 1: builder
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv venv /app/.venv \
    && uv sync --python /app/.venv/bin/python --no-dev

# Stage 2: runtime
FROM python:3.12-slim AS runtime
ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}
WORKDIR /app
RUN addgroup --system app && adduser --system --group app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "caramello.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Regra crítica — sem secrets como ARG:** Apenas `APP_VERSION` é `ARG`. `DB_PASSWORD`, `KEYCLOAK_*` são env vars de runtime, nunca de build.

**Nota sobre `uv sync`:** Preferir `uv sync --no-dev` sobre `uv pip install -e .` no builder — usa o `uv.lock` diretamente. Se a instalação editável no container não funcionar bem, usar `uv pip install --python /app/.venv/bin/python .`.

---

### `compose.yaml` (config — novo)

**Analog:** `docs/deploy.md` §3 (lines 34-49 do doc)

**Padrão base** (do doc existente — expandir com `build` e `APP_VERSION`):
```yaml
# Analog: docs/deploy.md linhas 34-49
services:
  api:
    image: ghcr.io/henricos/caramello-api:latest
    container_name: caramello-api
    restart: unless-stopped
    environment:
      ENVIRONMENT: ${ENVIRONMENT:-production}
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT:-5432}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME:-caramello}
    ports:
      - "${API_HOST_PORT:-8000}:8000"
```

**Adições para Phase 5** (build arg APP_VERSION + Keycloak):
```yaml
services:
  api:
    build:
      context: .
      args:
        APP_VERSION: ${APP_VERSION:-0.0.0}
    image: ghcr.io/henricos/caramello-api:${APP_VERSION:-latest}
    # ... resto igual ao analog, adicionar vars Keycloak:
    environment:
      # ... DB vars ...
      CORS_ORIGINS: ${CORS_ORIGINS:-}
      KEYCLOAK_URL: ${KEYCLOAK_URL}
      KEYCLOAK_REALM: ${KEYCLOAK_REALM}
      KEYCLOAK_CLIENT_ID: ${KEYCLOAK_CLIENT_ID}
```

---

### `bin/manage_db` (utility/script — modificar)

**Base:** `bin/manage_db` (atual, lines 1-70)

**Padrão de argumento `--env`** — inserir antes do `COMMAND=$1` atual (line 24):
```bash
# Parse --env flag (deve vir ANTES da leitura de COMMAND)
ENV_FLAG="dev"  # default não muda comportamento atual

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

COMMAND=$1
shift
```

**Padrão de carregamento de .env** (já existe no `reset` branch, lines 53-55 — generalizar para todos os comandos):
```bash
# Mover para ANTES do case, logo após o parse de --env:
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi
# Depois sobrescrever DB_NAME se --env test (a sobrescrita vem APÓS o carregamento do .env)
if [[ "$ENV_FLAG" == "test" ]]; then
  export DB_NAME="caramello_test"
fi
```

**Usage atualizado** — adicionar à função `usage()`:
```bash
echo "  --env {dev|test}  Target environment (default: dev)"
echo ""
echo "Examples:"
echo "  $0 init --env test        Initialize caramello_test"
echo "  $0 reset --env test       Reset caramello_test (DATA LOSS WARNING)"
```

---

### `.env.example` (config — modificar)

**Base:** `.env.example` (atual, lines 1-20)

**Mudança:** linha 7 (`DB_NAME=familia_dev` → `DB_NAME=caramello_dev`) e comentário:
```bash
# Banco de dados PostgreSQL
# Nomenclatura: caramello (prod), caramello_dev (dev), caramello_test (testes)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=caramello_dev
```

---

### `pyproject.toml` (config — modificar)

**Base:** `pyproject.toml` (atual)

**Deps a adicionar em `[project] dependencies`** (após `httpx>=0.28.1`):
```toml
"fastapi-mcp>=0.4.0",
```

**Deps a adicionar em `[dependency-groups] dev`** (após `mypy`):
```toml
"pytest-asyncio>=1.4.0",
"httpx>=0.28.1",
```

**Config de pytest — adicionar `asyncio_mode`** (em `[tool.pytest.ini_options]`):
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: testes que requerem banco real — não rodam sem caramello_test",
]
```

---

### `docs/apps-platform.md` (documentation — modificar)

**Base:** `docs/apps-platform.md` §5 (lines 148-175)

**Tabela a atualizar** (lines 163-170 — substituir `familia_*` por `caramello_*`):

Tabela original:
```
| familia_prod | Produção do Grupo Família |
| familia_dev  | Desenvolvimento do Grupo Família |
```

Nova tabela (3 bancos):
```markdown
| Database | Propósito |
|---|---|
| `caramello` | Produção do Grupo Família |
| `caramello_dev` | Desenvolvimento do Grupo Família |
| `caramello_test` | Testes de integração (banco isolado) |
```

---

## Shared Patterns

### AsyncSession via Depends — padrão universal
**Source:** `src/caramello/families/operations.py` lines 128-132
**Apply to:** `services.py`, `conftest.py` (fixtures), todos os endpoints novos
```python
# Em endpoints (operations.py):
session: AsyncSession = Depends(get_session),
current_user: User = Depends(get_current_user),

# Em services (services.py) — sem Depends; parâmetros diretos:
async def my_service(session: AsyncSession, user: User) -> ...:
```

### dependency_overrides para auth em testes
**Source:** `tests/test_family_operations.py` lines 132-137 + 154-155
**Apply to:** `conftest.py` (async_client fixture), `test_mcp.py`
```python
app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_session] = _session_override
try:
    # ... test code ...
finally:
    app.dependency_overrides.clear()
```

### Fake User para testes
**Source:** `tests/test_family_operations.py` lines 22-36
**Apply to:** `conftest.py`, `test_mcp.py`
```python
from caramello.users.models import User
from uuid import uuid4
from datetime import datetime, timezone

fake_user = User(
    id=1,
    uuid=uuid4(),
    idp_sub="test-sub",
    email="test@example.com",
    name="Test User",
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)
```

### SQLModel select + join + where
**Source:** `src/caramello/families/operations.py` lines 166-170
**Apply to:** `families/services.py`
```python
result = await session.exec(
    select(Family)
    .join(FamilyMember, FamilyMember.family_id == Family.id)  # type: ignore[arg-type]
    .where(FamilyMember.user_id == user.id)
)
return list(result.all())
```

### Lifespan + include_router ordering
**Source:** `src/caramello/main.py` lines 26-56
**Apply to:** `src/caramello/main.py` (modificação)
```python
# REGRA: include_router → DEPOIS → FastApiMCP → mcp.mount_http()
# Se montar MCP antes de registrar routers, as ferramentas não aparecem.
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)
app.include_router(families_router.router)
# MCP LAST:
mcp = FastApiMCP(app, ...)
mcp.mount_http()
```

### DATABASE_URL construído de variáveis individuais
**Source:** `src/caramello/core/config.py` lines 35-41
**Apply to:** `tests/conftest.py` (TEST_DB_URL)
```python
# Config.py constrói a URL assim:
f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# conftest.py replica o mesmo padrão para caramello_test:
TEST_DB_URL = (
    f"postgresql+asyncpg://{os.getenv('DB_USER', 'postgres')}"
    f":{os.getenv('DB_PASSWORD', 'postgres')}"
    f"@{os.getenv('DB_HOST', 'localhost')}"
    f":{os.getenv('DB_PORT', '5432')}"
    f"/caramello_test"
)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `Dockerfile` | config | — | Nenhum Dockerfile existe no repo; padrão vem de RESEARCH.md Pattern 4 (multi-stage Python/uv) |

---

## Critical Decisions Captured

1. **`mcp/tools.py` NÃO existe:** `fastapi-mcp` 0.4.0 não suporta tools customizadas fora de endpoints FastAPI. A ferramenta MCP é o endpoint REST `GET /families/families` com `operation_id="list_my_families"` exposto via `include_operations`. (RESEARCH.md Alerta Crítico)

2. **`operation_id` explícito obrigatório:** Adicionar `operation_id="list_my_families"` ao decorator `@router.get("/families", ...)` em `operations.py`. FastAPI gera IDs automáticos com nomes longos que quebram o filtro `include_operations`.

3. **`join_transaction_mode="create_savepoint"`:** Obrigatório para rollback funcionar com `asyncpg` em transações aninhadas. Sem isso, `db_session` fixture não garante isolamento.

4. **`asyncio_mode = "auto"` em pyproject.toml:** Necessário para `pytest-asyncio` 1.4.0 — evita `ScopeMismatch` em fixtures de sessão.

5. **Nomenclatura de banco:** `caramello` (prod), `caramello_dev` (dev), `caramello_test` (test) — atualizar `.env.example`, `docs/apps-platform.md §5`, e comentário no CLAUDE.md.

---

## Metadata

**Analog search scope:** `src/caramello/`, `tests/`, `bin/`, `docs/`, raiz do repo
**Files scanned:** 12 arquivos lidos (main.py, operations.py, auth.py, database.py, config.py, conftest.py, test_family_operations.py, pyproject.toml, manage_db, .env.example, deploy.md, apps-platform.md)
**Pattern extraction date:** 2026-05-26
