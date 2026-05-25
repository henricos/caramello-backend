# Phase 3: Estrutura por Domínios e Autenticação — Pattern Map

**Mapeado:** 2026-05-25
**Arquivos analisados:** 12 novos/modificados
**Análogos encontrados:** 10 / 12

---

## File Classification

| Arquivo Novo/Modificado | Role | Data Flow | Análogo Mais Próximo | Qualidade |
|-------------------------|------|-----------|----------------------|-----------|
| `src/caramello/shared/auth.py` | middleware | request-response | `src/caramello/shared/database.py` | role-match |
| `src/caramello/user/models.py` | model | CRUD | `src/caramello/models/user.py` | exact |
| `src/caramello/user/router.py` | controller | request-response | `src/caramello/api/generated/user_router.py` | exact |
| `src/caramello/user/operations.py` | controller | request-response | `src/caramello/api/generated/user_router.py` | role-match |
| `src/caramello/family/models.py` | model | CRUD | `src/caramello/models/user.py` | exact |
| `src/caramello/family/router.py` | controller | request-response | `src/caramello/api/generated/user_router.py` | exact |
| `src/caramello/core/config.py` | config | — | `src/caramello/core/config.py` (modificar) | self |
| `src/caramello/main.py` | config | — | `src/caramello/main.py` (modificar) | self |
| `scripts/generate_code.py` | utility | batch | `scripts/generate_code.py` (modificar) | self |
| `dsl/entities/*.yaml` | config | — | `dsl/entities/user.yaml` (modificar) | self |
| `dsl/operations/user.yaml` | config | — | `dsl/manifest.yaml` | partial |
| `alembic/env.py` | config | — | `alembic/env.py` (modificar) | self |

---

## Pattern Assignments

### `src/caramello/shared/auth.py` (middleware, request-response)

**Análogo:** `src/caramello/shared/database.py`

**Padrão de imports** (database.py linhas 1-6):
```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.core.config import settings
```

**Padrão de módulo shared** — o módulo expõe uma função pública injetável via `Depends()`, com estado de módulo (engine singleton em database.py, `_jwks_cache` em auth.py). O novo arquivo `auth.py` segue a mesma estrutura: estado de módulo no topo, função async pública, sem classe.

**Estrutura alvo para auth.py:**
```python
from __future__ import annotations

from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.core.config import settings
from caramello.shared.database import get_session

# Estado de módulo — análogo ao `engine` singleton em database.py
_jwks_cache: dict[str, Any] = {}

http_bearer = HTTPBearer()


async def fetch_jwks() -> None:
    """Busca chaves JWKS do Keycloak e popula o cache. Chamado no lifespan."""
    jwks_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()
    for key_data in jwks.get("keys", []):
        kid = key_data["kid"]
        _jwks_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: AsyncSession = Depends(get_session),
) -> "User":
    ...
```

**Padrão de sessão assíncrona** (database.py linhas 21-23) — reutilizar `get_session()` de `shared/database.py` via `Depends(get_session)` em `get_current_user`. Não criar nova sessão em auth.py.

---

### `src/caramello/user/models.py` (model, CRUD)

**Análogo:** `src/caramello/models/user.py`

**ATENÇÃO — arquivo gerado:** Este arquivo é produzido por `scripts/generate_code.py`. O padrão abaixo deve ser o que o generator emite, não código escrito à mão.

**Padrão atual de imports** (models/user.py linhas 1-6) — viola ruff UP035:
```python
from typing import Optional, List      # VIOLAÇÃO — UP035
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from caramello.models.familymember import FamilyMember  # QUEBRA após reorganização
```

**Padrão alvo que o generator deve emitir** (ruff-compliant):
```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

from caramello.family.models import FamilyMember  # import cross-domain correto
```

**Padrão de classes** (models/user.py linhas 8-40) — estrutura das 4 classes a preservar:
```python
class User(SQLModel, table=True):
    """Represents a system user, provisioned on first authentication via Keycloak."""
    __tablename__ = "user"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    idp_sub: str = Field(unique=True, nullable=False)
    email: EmailStr = Field(unique=True, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    families: list[Family] = Relationship(back_populates="members", link_model=FamilyMember)
    sent_invitations: list[FamilyInvitation] = Relationship(back_populates="inviter")

class UserRead(SQLModel):
    uuid: UUID
    idp_sub: str
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime

class UserCreate(SQLModel):
    idp_sub: str
    email: EmailStr
    name: str

class UserUpdate(SQLModel):
    idp_sub: str | None = None
    email: EmailStr | None = None
    name: str | None = None
```

**Diferenças chave em relação ao atual:** `Optional[X]` → `X | None`; quoted standard types (`'str'`, `'int'`) → sem aspas; import cross-domain de `FamilyMember` vem de `caramello.family.models`.

---

### `src/caramello/user/router.py` (controller, request-response)

**Análogo:** `src/caramello/api/generated/user_router.py`

**ATENÇÃO — arquivo gerado:** Produzido por `generate_router()` em `scripts/generate_code.py`.

**Padrão de imports atual** (user_router.py linhas 1-8) — base para o template atualizado:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.user import User, UserRead, UserCreate, UserUpdate
```

**Imports do template atualizado** — adicionar `get_current_user` e corrigir path:
```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.user.models import User, UserRead, UserCreate, UserUpdate
```

**Padrão de endpoint com auth** — adicionar `_: User = Depends(get_current_user)` em cada handler (user não usado em CRUD genérico):
```python
@router.get("/", response_model=list[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[User]:
    result = await session.exec(select(User).offset(offset).limit(limit))
    return list(result.all())
```

**Padrão completo de CRUD** (user_router.py linhas 11-68) — preservar exatamente a lógica de POST, GET, GET/{uuid}, PATCH/{uuid}, DELETE/{uuid}, adicionando `_: User = Depends(get_current_user)` em cada assinatura.

**Padrão de erro 404** (user_router.py linhas 33-36):
```python
if not user:
    raise HTTPException(status_code=404, detail="User not found")
```

---

### `src/caramello/user/operations.py` (controller, request-response)

**Análogo:** `src/caramello/api/generated/user_router.py` (estrutura de router)

**Arquivo gerado inicialmente como stub, depois implementado manualmente.**

**Padrão do stub gerado** — estrutura mínima que o generator deve emitir:
```python
# CARAMELLO-GENERATED: stub
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    raise NotImplementedError
```

**Após implementação — alterar anotação no topo e remover `raise NotImplementedError`:**
```python
# CARAMELLO-GENERATED: implemented
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    return current_user
```

---

### `src/caramello/family/models.py` e `src/caramello/family/router.py` (model + controller, CRUD)

**Análogo:** `src/caramello/models/user.py` e `src/caramello/api/generated/user_router.py`

Mesmos padrões de `user/models.py` e `user/router.py` acima — a diferença é:
- `family/models.py` agrupa `Family`, `FamilyMember` (link model, `is_link_model: true`, sem `id`/`uuid`), e `FamilyInvitation` em um único arquivo por domínio
- `family/router.py` exporta routers para `Family` e `FamilyInvitation` (não `FamilyMember`, que é link model sem router próprio)
- Import cross-domain em `family/models.py`: `from caramello.user.models import User`

**Padrão de link model** — `FamilyMember` não tem `id`, `uuid`, `created_at`, `updated_at`; usa `is_link_model: true` no YAML. O generator deve pular a geração de router para link models (padrão já presente em `generate_code.py` linha 444: `if is_link: continue`).

---

### `src/caramello/core/config.py` (config — MODIFICAR)

**Análogo:** `src/caramello/core/config.py` (o próprio arquivo)

**Padrão atual** (config.py linhas 1-37) — base para extensão:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DATABASE_URL: str | None = None

    # Individual DB variables (Required)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    def model_post_init(self, __context: object) -> None:
        ...


settings = Settings()  # type: ignore[call-arg]
```

**Campos Keycloak a adicionar** — seguir o padrão de `DB_HOST` etc. (variáveis obrigatórias sem default):
```python
    # Keycloak Configuration (Required)
    KEYCLOAK_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
```

**Posicionamento:** Adicionar após `CORS_ORIGINS`, antes de `model_post_init`. Manter exatamente o padrão de nomes em UPPER_CASE e sem valores default (campos obrigatórios lidos do `.env`).

---

### `src/caramello/main.py` (config — MODIFICAR)

**Análogo:** `src/caramello/main.py` (o próprio arquivo)

**Estado atual** (main.py linhas 1-35) — base para refatoração:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caramello.api.generated import (
    family_router,
    familyinvitation_router,
    familymember_router,
    user_router,
)
from caramello.core.config import settings

app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router)
app.include_router(family_router.router)
app.include_router(familymember_router.router)
app.include_router(familyinvitation_router.router)
```

**Padrão alvo** — adicionar `lifespan` com `asynccontextmanager`, trocar imports de routers:
```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from caramello.core.config import settings
from caramello.shared.auth import fetch_jwks
from caramello.user import router as user_router
from caramello.user import operations as user_operations
from caramello.family import router as family_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_jwks()
    yield


app = FastAPI(
    title="Caramello Backend",
    description="Backend API for Caramello",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router)
app.include_router(user_operations.router)
app.include_router(family_router.router)
```

**Manter:** bloco `add_middleware` sem modificação; `@app.get("/")` root handler.

---

### `scripts/generate_code.py` (utility, batch — MODIFICAR)

**Análogo:** `scripts/generate_code.py` (o próprio arquivo)

**Padrão de paths atual** (generate_code.py linhas 8-13) — a ser substituído por paths dinâmicos:
```python
ROOT_DIR = Path(__file__).parent.parent
DSL_DIR = ROOT_DIR / "dsl"
ENTITIES_DIR = DSL_DIR / "entities"
MODELS_OUTPUT_DIR = ROOT_DIR / "src" / "caramello" / "models"
API_OUTPUT_DIR = ROOT_DIR / "src" / "caramello" / "api" / "generated"
TESTS_OUTPUT_DIR = ROOT_DIR / "tests" / "generated"
```

**Padrão de `load_yaml()`** (linhas 18-25) — reutilizar sem modificação para carregar `dsl/operations/*.yaml`.

**Padrão de `main()`** (linhas 412-461) — estrutura de loop a evoluir:
```python
# Passo 1: Carregar todos os YAMLs e construir entity_domain map
entity_domain: dict[str, str] = {}
for entity_file in entity_ids:
    data = load_yaml(ENTITIES_DIR / entity_file)
    if data:
        entity_domain[data["name"]] = data.get("domain", "")

# Passo 2: Processar cada entidade com domain dinâmico
for entity_file in entity_ids:
    data = load_yaml(ENTITIES_DIR / entity_file)
    domain = data.get("domain", "")
    domain_dir = ROOT_DIR / "src" / "caramello" / domain
    domain_dir.mkdir(parents=True, exist_ok=True)
    (domain_dir / "__init__.py").touch()

    model_code = generate_models(data, entity_domain)  # passa mapa para resolver cross-domain
    (domain_dir / "models.py").write_text(model_code)
    ...

# Passo 3: Processar operations YAMLs
OPERATIONS_DIR = DSL_DIR / "operations"
for op_file in OPERATIONS_DIR.glob("*.yaml"):
    op_data = load_yaml(op_file)
    domain = op_data.get("domain", "")
    ops_path = ROOT_DIR / "src" / "caramello" / domain / "operations.py"
    # Verificar anotação D-09 antes de sobrescrever
    if ops_path.exists():
        first_line = ops_path.read_text().splitlines()[0]
        if first_line.strip() == "# CARAMELLO-GENERATED: implemented":
            continue  # pular arquivo já implementado
    ops_code = generate_operations(op_data)
    ops_path.write_text(ops_code)
```

**Padrão de `generate_models()` a corrigir** (linhas 128-254):
- Remover `from typing import Optional, List` do bloco de imports gerado
- Adicionar `from __future__ import annotations` como primeira linha
- Substituir `Optional[X]` por `X | None` em todo o output
- Substituir `f"from caramello.models.{lm.lower()} import {lm}"` por `f"from caramello.{entity_domain[lm]}.models import {lm}"`

**Padrão de `generate_router()` a corrigir** (linhas 256-329):
- Substituir `from caramello.models.{var_name} import` por `from caramello.{domain}.models import`
- Adicionar linha `from caramello.shared.auth import get_current_user`
- Adicionar `_: {name} = Depends(get_current_user),` em cada assinatura de endpoint

---

### `dsl/entities/*.yaml` (config — MODIFICAR)

**Análogo:** `dsl/entities/user.yaml` (o próprio arquivo)

**Padrão atual** (user.yaml linhas 1-7):
```yaml
name: User
description: Represents a system user, provisioned on first authentication via Keycloak.
table_name: user
```

**Padrão alvo** — adicionar campo `domain` como segundo campo após `name`:
```yaml
name: User
domain: user          # NOVO — obrigatório nesta fase
description: Represents a system user, provisioned on first authentication via Keycloak.
table_name: user
```

**Mapeamento de domínios:**
- `user.yaml` → `domain: user`
- `family.yaml` → `domain: family`
- `family_member.yaml` → `domain: family`
- `family_invitation.yaml` → `domain: family`

---

### `dsl/operations/user.yaml` (config — NOVO)

**Análogo:** `dsl/manifest.yaml` (estrutura YAML do projeto DSL)

**Sem análogo direto no codebase.** Formato mínimo definido em RESEARCH.md §Generator Evolution:
```yaml
# dsl/operations/user.yaml
domain: user
operations:
  - name: get_me
    method: GET
    path: /user/me
    description: "Retorna o perfil do usuário autenticado."
```

---

### `alembic/env.py` (config — MODIFICAR)

**Análogo:** `alembic/env.py` (o próprio arquivo)

**Linha a substituir** (env.py linha 22):
```python
# ANTES:
from caramello.models import *  # noqa: E402, F403 # Import all models for autogenerate

# DEPOIS:
from caramello.user.models import User  # noqa: E402
from caramello.family.models import Family, FamilyMember, FamilyInvitation  # noqa: E402
```

**Todo o restante de env.py permanece inalterado** — a estrutura de `run_migrations_offline()`, `run_async_migrations()` e `run_migrations_online()` não é tocada.

---

## Shared Patterns

### AsyncSession via Depends
**Fonte:** `src/caramello/shared/database.py` linhas 21-23
**Aplicar em:** Todos os handlers de router e em `get_current_user()` em auth.py
```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```
Injetar como `session: AsyncSession = Depends(get_session)`.

### pydantic-settings — novos campos obrigatórios
**Fonte:** `src/caramello/core/config.py` linhas 19-23
**Aplicar em:** Adição de `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` ao `Settings`
```python
    # Individual DB variables (Required)
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
```
Campos obrigatórios sem default — pydantic-settings levanta erro claro se a env var estiver ausente. Mesmo padrão para os campos Keycloak.

### Padrão de erro HTTP
**Fonte:** `src/caramello/api/generated/user_router.py` linhas 33-36 e 59-68
**Aplicar em:** Todos os handlers de router gerados e em `get_current_user()`
```python
raise HTTPException(status_code=404, detail="User not found")
raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
```
Em auth.py usar `status.HTTP_401_UNAUTHORIZED` (importar `status` de `fastapi`). Em routers CRUD usar literais `404`.

### Importação de settings
**Fonte:** `src/caramello/shared/database.py` linha 6 e `src/caramello/core/config.py` linha 37
**Aplicar em:** `shared/auth.py`, qualquer módulo que precise de config
```python
from caramello.core.config import settings
# usar: settings.KEYCLOAK_URL, settings.DATABASE_URL, etc.
```

### from __future__ import annotations
**Fonte:** Padrão Python 3.10+ exigido pelo ruff UP
**Aplicar em:** Todos os arquivos gerados novos (`user/models.py`, `user/router.py`, `family/models.py`, `family/router.py`, `user/operations.py`) e em `shared/auth.py`
```python
from __future__ import annotations
```
Primeira linha de cada arquivo — permite tipos modernos (`str | None`, `list[T]`) sem import de `typing`.

---

## No Analog Found

| Arquivo | Role | Data Flow | Motivo |
|---------|------|-----------|--------|
| `src/caramello/shared/auth.py` | middleware | request-response | Nenhuma camada de auth existe no codebase — primeiro arquivo de auth do projeto. Usar RESEARCH.md §Pattern 1 e §Pattern 2 como referência primária. |
| `dsl/operations/user.yaml` | config | — | Conceito novo (DSL operations). Usar formato documentado em RESEARCH.md §Generator Evolution §Novo Conceito. |

---

## Metadata

**Escopo de busca de análogos:** `src/caramello/`, `scripts/`, `alembic/`, `dsl/`
**Arquivos lidos:** 11
**Data de mapeamento:** 2026-05-25
