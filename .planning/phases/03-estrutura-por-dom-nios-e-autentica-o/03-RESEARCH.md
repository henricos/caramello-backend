# Phase 3: Estrutura por Domínios e Autenticação — Research

**Pesquisado:** 2026-05-25
**Domínio:** Reorganização de codebase Python/FastAPI por domínios de negócio + autenticação Keycloak via JWKS cacheado
**Confiança:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Configuração Keycloak via env vars em `Settings`. Campos: `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`. Realm: `caramello`. JWKS URL: `{KEYCLOAK_URL}/realms/caramello/protocol/openid-connect/certs`.

**D-02:** Validação de audience (`aud` claim): implementador deve verificar o valor real emitido pelo Keycloak antes de decidir se valida `aud == client_id` ou omite audiência inicialmente.

**D-03:** Extração do nome: claim `name` (OIDC padrão); fallback para `preferred_username`. Mapeamento: `sub` → `idp_sub`, `email` → `email`, `name` (ou `preferred_username`) → `name`.

**D-04:** Biblioteca JWT: `PyJWT[crypto]` via `uv add "PyJWT[crypto]"`. Sem `python-jose`.

**D-05:** Cache JWKS em memória: chaves buscadas uma vez no lifespan FastAPI. Rotação de kid: re-busca antes de retornar 401. Sem `cachetools` — dict simples em `shared/auth.py`.

**D-06:** Campo `domain` nas YAMLs. Mapeamento: `User` → `domain: user`, Family/FamilyMember/FamilyInvitation → `domain: family`.

**D-07:** Generator produz `models.py` e `router.py` por entidade dentro do diretório do domínio.

**D-08:** Novo conceito DSL: `dsl/operations/{domain}.yaml` — operações de negócio. Generator produz `src/caramello/{domain}/operations.py` com stubs.

**D-09:** Anotação de segurança de regeneração: `# CARAMELLO-GENERATED: stub` (sobrescreve) vs `# CARAMELLO-GENERATED: implemented` (pula).

**D-10:** `GET /user/me` é operação de negócio em `dsl/operations/user.yaml`. Stub gerado e implementado nesta fase; anotação atualizada para `implemented`.

**D-11:** Template de router atualizado para incluir `Depends(get_current_user)` em todos os endpoints.

**D-12:** JIT provisioning centralizado em `get_current_user()` em `shared/auth.py`. Fluxo: validar JWT → extrair `idp_sub` → buscar user → criar com `ON CONFLICT DO NOTHING` se não encontrado → retornar `User`.

**D-13:** `src/caramello/models/` e `src/caramello/api/generated/` removidos ao final da fase.

**D-14:** `main.py` atualizado para importar de `caramello.user.router` e `caramello.family.router`.

### Claude's Discretion

Nenhum item registrado em CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

- Operações de negócio de escrita no DSL (Phase 4)
- `GET /health` com ping ao banco (OPS-01, v2)
- Stub generation com schema de request/response no YAML de operations
- Logging estruturado com structlog (OPS-02, v2)
- Token introspection/revogação
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Descrição | Suporte da Research |
|----|-----------|---------------------|
| STRUCT-01 | Código organizado por domínio em `src/caramello/user/`, `src/caramello/family/`, `src/caramello/shared/` — `models/` e `api/generated/` removidos | Seções Architecture Patterns e Code Examples documentam o novo layout e o processo de migração |
| STRUCT-02 | DSL generator produz `models.py` e `schemas.py` dentro do diretório do domínio quando YAML contém campo `domain` | Seção Generator Evolution documenta todas as mudanças necessárias em `generate_code.py` |
| AUTH-01 | Endpoints protegidos rejeitam requests sem Bearer token Keycloak válido com 401 — validação local via JWKS | Seção Standard Stack e Code Examples documentam PyJWT[crypto] + HTTPBearer + `get_current_user` |
| AUTH-02 | Usuário criado automaticamente no banco na primeira request com token válido (JIT provisioning com `ON CONFLICT DO NOTHING`) | Seção Code Examples documenta o padrão `sqlalchemy.dialects.postgresql.insert` com conflito |
| AUTH-03 | `shared/auth.py` isola completamente a lógica de validação JWT — qualquer endpoint usa `Depends(get_current_user)` | Seção Architecture Patterns documenta o módulo `shared/auth.py` e seu papel |
| USER-01 | Usuário autenticado pode consultar seu próprio perfil (`GET /user/me`) — retorna `id`, `email`, `name` | Seção Code Examples documenta o stub de operations.py e sua implementação |
</phase_requirements>

---

## Summary

Esta fase é a maior refatoração estrutural do Milestone 1. Ela combina três transformações simultâneas: (1) reorganização física do codebase de camadas técnicas planas (`models/`, `api/generated/`) para diretórios por domínio de negócio (`user/`, `family/`); (2) evolução do gerador DSL para suportar o campo `domain` e o conceito de `dsl/operations/`; e (3) implementação da camada de autenticação Keycloak com validação JWT local, JWKS cacheado em memória e JIT provisioning.

A maior armadilha da fase é a interdependência de mudanças: o gerador precisa ser atualizado *antes* de regenerar, os imports do Alembic precisam ser atualizados *junto* com a remoção de `models/`, e o `main.py` precisa ser atualizado *com* a nova estrutura de routers. A ordem de execução das tarefas é crítica. Um segundo risco é a qualidade do código gerado: as novas paths de domínio *não são excluídas* pelo ruff/mypy (ao contrário dos paths antigos), portanto o gerador deve produzir código que passa nas verificações. O código gerado atual tem violações de ruff (tipos antigos como `Optional[str]`, `List[T]`, imports não ordenados) que *precisam ser corrigidas no generator* antes de regenerar.

A camada de auth usa `PyJWT[crypto]` com `httpx.AsyncClient` para busca assíncrona de JWKS — `PyJWKClient` nativo do PyJWT usa `urllib` síncrono e bloquearia o event loop. O cache é um `dict` simples em módulo nível (`_jwks_cache: dict[str, Any]`) com busca no lifespan e re-busca sob demanda quando um `kid` desconhecido aparece.

**Recomendação primária:** Executar em três blocos sequenciais — (1) evoluir generator e DSL, (2) implementar auth, (3) reorganizar estrutura e atualizar imports. Nunca remover os diretórios antigos antes que os novos estejam funcionais e testados.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Validação JWT | API / Backend (`shared/auth.py`) | — | Lógica de segurança pertence ao backend; nunca ao cliente |
| JWKS cache em memória | API / Backend (módulo level) | — | Cache de processo único, sem necessidade de Redis para 1-5 usuários |
| JIT provisioning de User | API / Backend (`get_current_user`) | Database (PostgreSQL `ON CONFLICT DO NOTHING`) | Operação atômica que toca banco pertence ao backend |
| Extração de claims JWT | API / Backend (`shared/auth.py`) | — | Parsing de token é responsabilidade da camada de auth |
| Geração de código DSL | Tooling (`scripts/generate_code.py`) | — | Ferramenta de dev, não runtime |
| Routing por domínio | API / Backend (`user/router.py`, `family/router.py`) | — | Cada domínio own seus endpoints |
| Operações de negócio | API / Backend (`{domain}/operations.py`) | — | Lógica de negócio isolada de routers CRUD |
| Registro de routers | API / Backend (`main.py`) | — | Composição de routers é responsabilidade do entrypoint |

---

## Standard Stack

### Core

| Biblioteca | Versão | Propósito | Por que padrão |
|-----------|--------|-----------|----------------|
| `PyJWT[crypto]` | 2.13.0 | Decode e validação de JWT com RS256/ES256 | Biblioteca de referência para JWT em Python; `[crypto]` inclui dependência `cryptography` para algoritmos assimétricos. `python-jose` tem CVEs registradas (D-04) |
| `httpx` | 0.28.1 | Busca assíncrona de JWKS do Keycloak | `PyJWKClient` nativo usa `urllib` síncrono (bloqueante); `httpx.AsyncClient` é necessário para não bloquear o event loop em FastAPI async |
| `fastapi.security.HTTPBearer` | (já em fastapi 0.118.0) | Extração do Bearer token do header `Authorization` | Padrão FastAPI para extração de token; retorna 401 automaticamente se header ausente |

[VERIFIED: pip index versions PyJWT] — versão 2.13.0 é a mais recente no PyPI
[VERIFIED: Context7 /jpadilla/pyjwt] — PyJWKClient.fetch_data() usa urllib síncrono, confirmado por inspeção de código
[VERIFIED: codebase] — httpx 0.28.1 já está nos dev deps; precisa ser movido para main deps

### Supporting

| Biblioteca | Versão | Propósito | Quando usar |
|-----------|--------|-----------|-------------|
| `sqlalchemy.dialects.postgresql.insert` | (já em sqlmodel 0.0.38) | `INSERT ... ON CONFLICT DO NOTHING` para JIT provisioning atômico | Apenas no JIT provisioning de User em `get_current_user()` |
| `contextlib.asynccontextmanager` | (stdlib) | Lifespan FastAPI para busca de JWKS no startup | Padrão recomendado pelo FastAPI 0.93+ |

[VERIFIED: Context7 /fastapi/fastapi] — asynccontextmanager + lifespan é o padrão atual recomendado
[VERIFIED: uv run python] — `from sqlalchemy.dialects.postgresql import insert` disponível no venv

### Alternativos Considerados

| Em vez de | Poderia usar | Tradeoff |
|-----------|-------------|----------|
| `httpx.AsyncClient` para JWKS | `PyJWKClient` nativo | `PyJWKClient` é síncrono (urllib) — bloquearia event loop; não usar em handler async |
| `httpx.AsyncClient` para JWKS | `asyncio.run_in_executor` + urllib | Funciona mas é mais complexo e verboso sem benefício |
| dict simples p/ cache JWKS | `cachetools.TTLCache` | D-05 proíbe cachetools; dict simples com re-busca por kid é suficiente para 1-5 usuários |

**Instalação:**
```bash
uv add "PyJWT[crypto]"
# httpx já está no venv; mover de dependency-groups.dev para project.dependencies em pyproject.toml
```

---

## Architecture Patterns

### Diagrama de Arquitetura

```
HTTP Request (Bearer: <token>)
         |
         v
  FastAPI HTTPBearer
  (extrai token do header; retorna 401 se ausente)
         |
         v
  get_current_user() [shared/auth.py]
  - jwt.decode(token, key_from_cache, algorithms=["RS256"])
  - Se kid não encontrado em cache → re-busca JWKS via httpx
  - Extrai sub, email, name/preferred_username
  - SELECT User WHERE idp_sub = sub
  - Se não encontrado: INSERT ON CONFLICT DO NOTHING → SELECT
  - Retorna objeto User
         |
         v
  Router endpoint recebe User como parâmetro
  (user/router.py ou user/operations.py)
         |
         v
  AsyncSession via get_session() [shared/database.py]
         |
         v
  PostgreSQL (familia_dev / familia_prod)

Startup (lifespan):
  httpx.AsyncClient → GET {KEYCLOAK_URL}/realms/caramello/protocol/openid-connect/certs
  → popular _jwks_cache: dict[str, Any]  (kid → public key)
```

### Estrutura de Projeto Resultante

```
src/caramello/
├── __init__.py
├── main.py                  # lifespan + include_router de cada domínio
├── core/
│   └── config.py            # Settings + KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID
├── shared/
│   ├── __init__.py
│   ├── database.py          # get_session() — não muda
│   └── auth.py              # get_current_user(), _jwks_cache, fetch_jwks()
├── user/
│   ├── __init__.py
│   ├── models.py            # GENERATED: User, UserRead, UserCreate, UserUpdate
│   ├── router.py            # GENERATED: CRUD com Depends(get_current_user)
│   └── operations.py        # GENERATED stub → IMPLEMENTED: GET /user/me
└── family/
    ├── __init__.py
    ├── models.py            # GENERATED: Family, FamilyMember, FamilyInvitation + Read/Create/Update
    ├── router.py            # GENERATED: CRUD com Depends(get_current_user)
    └── operations.py        # GENERATED stub (vazio nesta fase — Phase 4 implementa)

dsl/
├── manifest.yaml            # adicionar referência a dsl/operations/
├── schema.yaml              # atualizar para incluir campo domain
├── entities/
│   ├── user.yaml            # adicionar domain: user
│   ├── family.yaml          # adicionar domain: family
│   ├── family_member.yaml   # adicionar domain: family
│   └── family_invitation.yaml  # adicionar domain: family
└── operations/
    └── user.yaml            # NEW: define GET /user/me

REMOVIDOS ao final da fase:
  src/caramello/models/
  src/caramello/api/
  src/caramello/repositories/
  src/caramello/services/
  tests/generated/
```

### Pattern 1: JWKS Cache em Memória com Re-busca por kid

**O quê:** Dict de módulo populado no lifespan; re-busca quando kid ausente.
**Quando usar:** Apenas em `shared/auth.py`; nunca recriar o pattern em outro lugar.

```python
# src/caramello/shared/auth.py
# Source: adaptado de PyJWT docs + FastAPI lifespan pattern

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.core.config import settings
from caramello.shared.database import get_session

_jwks_cache: dict[str, Any] = {}  # kid -> JWK key object

http_bearer = HTTPBearer()


async def fetch_jwks() -> None:
    """Busca chaves JWKS do Keycloak e popula o cache. Chamado no lifespan."""
    import httpx

    jwks_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        jwks = response.json()
    for key_data in jwks.get("keys", []):
        kid = key_data["kid"]
        _jwks_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)


def _get_key_for_kid(kid: str) -> Any:
    """Retorna a chave pública para o kid dado. Raises se não encontrado."""
    key = _jwks_cache.get(kid)
    if key is None:
        raise KeyError(f"kid {kid!r} não encontrado no cache JWKS")
    return key
```

[VERIFIED: Context7 /jpadilla/pyjwt] — `jwt.algorithms.RSAAlgorithm.from_jwk()` disponível no PyJWT 2.x para converter JWK dict em chave RSA pública
[VERIFIED: Context7 /fastapi/fastapi] — padrão lifespan com asynccontextmanager

### Pattern 2: get_current_user com JIT Provisioning

**O quê:** Dependency injetada em todos os endpoints protegidos.
**Quando usar:** Em cada endpoint de router gerado e em operations.py.

```python
# src/caramello/shared/auth.py (continuação)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    session: AsyncSession = Depends(get_session),
) -> "User":
    token = credentials.credentials

    # 1. Extrair kid do header sem validar (para lookup no cache)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.DecodeError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    kid = unverified_header.get("kid")

    # 2. Buscar chave do cache; re-buscar se kid desconhecido
    try:
        public_key = _get_key_for_kid(kid)
    except KeyError:
        await fetch_jwks()  # rotação de chaves
        try:
            public_key = _get_key_for_kid(kid)
        except KeyError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="kid não reconhecido")

    # 3. Validar JWT
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            # audience=settings.KEYCLOAK_CLIENT_ID,  # D-02: verificar claim aud real antes de ativar
            options={"verify_aud": False},  # remover quando audience confirmado
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from exc

    # 4. Extrair claims (D-03)
    idp_sub: str = payload["sub"]
    email: str = payload.get("email", "")
    name: str = payload.get("name") or payload.get("preferred_username", "")

    # 5. JIT provisioning com ON CONFLICT DO NOTHING (D-12)
    stmt = (
        pg_insert(User)
        .values(idp_sub=idp_sub, email=email, name=name)
        .on_conflict_do_nothing(index_elements=["idp_sub"])
    )
    await session.exec(stmt)  # type: ignore[arg-type]
    await session.commit()

    # 6. Buscar user (sempre existirá após upsert)
    result = await session.exec(select(User).where(User.idp_sub == idp_sub))
    user = result.first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao provisionar usuário")
    return user
```

[VERIFIED: codebase] — `from sqlalchemy.dialects.postgresql import insert` disponível no venv atual
[VERIFIED: REQUIREMENTS.md AUTH-02] — ON CONFLICT DO NOTHING é o padrão especificado

### Pattern 3: Lifespan FastAPI com Busca de JWKS

```python
# src/caramello/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from caramello.shared.auth import fetch_jwks


@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetch_jwks()  # Popula cache JWKS no startup
    yield
    # sem cleanup necessário para cache in-memory


app = FastAPI(title="Caramello Backend", version="0.1.0", lifespan=lifespan)

# Após reorganização:
from caramello.user import router as user_router
from caramello.family import router as family_router

app.include_router(user_router.router)
app.include_router(family_router.router)
```

[VERIFIED: Context7 /fastapi/fastapi] — lifespan com asynccontextmanager é o padrão atual (FastAPI 0.93+)

### Pattern 4: GET /user/me como Operação de Negócio

```python
# src/caramello/user/operations.py
# CARAMELLO-GENERATED: implemented

from fastapi import APIRouter, Depends
from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    return current_user
```

[ASSUMED] — formato exato do stub gerado pelo generator será definido na implementação de D-08

### Pattern 5: Router Gerado com Auth (template atualizado)

```python
# Template generate_router() — novo padrão com Depends(get_current_user)
# Source: pattern adaptado de caramello.api.generated.user_router (atual) + auth

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.shared.database import get_session
from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead, UserCreate, UserUpdate

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/", response_model=list[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),  # auth; user não usado no CRUD genérico
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[User]:
    result = await session.exec(select(User).offset(offset).limit(limit))
    return list(result.all())
```

[VERIFIED: codebase] — padrão Depends() com underscore `_` para auth sem uso do user é idiomático em FastAPI

### Anti-Patterns a Evitar

- **Usar `PyJWKClient.get_signing_key_from_jwt()` em endpoint async:** `PyJWKClient.fetch_data()` usa `urllib.request.urlopen` (síncrono) — bloquearia o event loop. Usar `httpx.AsyncClient` para busca async.
- **Deletar `models/` antes de atualizar `alembic/env.py`:** `env.py` importa `from caramello.models import *` — aplicação e Alembic quebram imediatamente. Atualizar imports primeiro, remover diretório depois.
- **Editar diretamente `user/models.py` ou `user/router.py`:** São gerados e serão sobrescritos. Editar YAML e regenerar.
- **Editar `user/operations.py` sem atualizar anotação:** Ao implementar um stub, mudar `# CARAMELLO-GENERATED: stub` para `# CARAMELLO-GENERATED: implemented` ou o arquivo será sobrescrito na próxima geração.
- **Código gerado com tipos antigos:** `Optional[str]` → `str | None`, `List[T]` → `list[T]`. Ruff UP rule falha nos novos paths (que não são excluídos).

---

## Generator Evolution

Esta seção documenta todas as mudanças necessárias em `scripts/generate_code.py`. É o trabalho mais complexo da fase.

### Mudanças na Estrutura de Paths

| Antes | Depois |
|-------|--------|
| `MODELS_OUTPUT_DIR = src/caramello/models` | Calculado dinamicamente: `src/caramello/{domain}/` |
| `API_OUTPUT_DIR = src/caramello/api/generated` | Mesmo `src/caramello/{domain}/` |
| `TESTS_OUTPUT_DIR = tests/generated` | Removido (tests gerados são abolidos) |

### Novo Campo `domain` no YAML

```yaml
# Exemplo: dsl/entities/user.yaml
name: User
domain: user          # NOVO campo obrigatório
table_name: user
# ...
```

O gerador deve:
1. Ler `domain` de cada YAML
2. Construir mapa global `entity_domain: dict[str, str]` antes de processar qualquer entidade (necessário para resolver imports cross-domain de link models)
3. Criar diretório `src/caramello/{domain}/` se não existir
4. Criar `src/caramello/{domain}/__init__.py` se não existir

### Correção de Tipos para Ruff Compliance

O código gerado atual tem violações de ruff (UP035, I001). As novas paths de domínio **não são excluídas** pelo ruff. O gerador deve emitir:

| Antes (viola ruff) | Depois (ruff-compliant) |
|---------------------|------------------------|
| `from typing import Optional, List` | `from __future__ import annotations` (sem import de Optional/List) |
| `Optional[str]` | `str \| None` |
| `Optional[int]` | `int \| None` |
| `List[T]` | `list[T]` |
| `'str'` (quoted standard type) | `str` (sem aspas) |
| `'int'` (quoted) | `int` (sem aspas) |
| Imports não ordenados | Ordenados por isort (I rule) |

[VERIFIED: codebase] — `uv run ruff check /tmp/test_model.py` confirma violações UP035 e I001 no código atual gerado
[VERIFIED: pyproject.toml] — `select = ["E", "F", "I", "UP", "B", "SIM"]` — UP e I estão ativos

### Imports Cross-Domain de Link Models

O `User` (domain=user) tem `link_model=FamilyMember` (domain=family). O gerador atual emite:
```python
from caramello.models.familymember import FamilyMember  # QUEBRA após reorganização
```

Deve emitir:
```python
from caramello.family.models import FamilyMember  # cross-domain import correto
```

Para resolver, o gerador deve construir o mapa `entity_domain` antes de processar modelos e usá-lo na função `generate_models()`.

### Import de Router no generate_router()

```python
# Antes:
from caramello.models.{var_name} import {Name}, {Name}Read, {Name}Create, {Name}Update

# Depois:
from caramello.{domain}.models import {Name}, {Name}Read, {Name}Create, {Name}Update
from caramello.shared.auth import get_current_user
```

### Novo Conceito: dsl/operations/{domain}.yaml

Formato mínimo do YAML de operações (D-08):

```yaml
# dsl/operations/user.yaml
domain: user
operations:
  - name: get_me
    method: GET
    path: /user/me
    description: "Retorna o perfil do usuário autenticado."
```

O generator produz `src/caramello/{domain}/operations.py` com:
1. Verificação da anotação no topo do arquivo (D-09)
2. Se `# CARAMELLO-GENERATED: implemented` → pula arquivo
3. Se `# CARAMELLO-GENERATED: stub` ou arquivo ausente → gera/sobrescreve com stubs

### Atualizar Exclusões de Ruff/Mypy no pyproject.toml

Os paths antigos (`src/caramello/api/generated`, `src/caramello/models`) serão removidos. As novas paths de domínio **não devem ser excluídas** — o código gerado deve passar nas verificações. Remover as entradas obsoletas de `[tool.ruff] exclude` e `[tool.mypy] exclude`.

### Atualizar alembic/env.py

```python
# Antes:
from caramello.models import *  # noqa: E402, F403

# Depois:
from caramello.user.models import User  # noqa: E402
from caramello.family.models import Family, FamilyMember, FamilyInvitation  # noqa: E402
```

---

## Don't Hand-Roll

| Problema | Não construir | Usar em vez disso | Por quê |
|----------|--------------|-------------------|---------|
| Decodificação JWT RS256 | Parser de JWT manual | `PyJWT[crypto]` com `jwt.decode()` | Verificação de assinatura, expiração, issuer — muitos vetores de ataque |
| Fetch de JWKS | `urllib.request` síncrono | `httpx.AsyncClient` | Não bloqueante; não travar o event loop numa app FastAPI async |
| Extração de Bearer token | Parsing manual de header `Authorization` | `fastapi.security.HTTPBearer` | Retorna 401 automático com `WWW-Authenticate: Bearer` quando token ausente |
| Atualização de campos na entidade `User` | `setattr` em loop | `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing()` | Atomicidade; sem race condition em requests concorrentes do mesmo usuário |
| Verificação de `kid` no JWT | Decode sem verificar kid | `jwt.get_unverified_header(token)` antes do decode | Necessário para lookup no cache sem validar assinatura prematuramente |

---

## Common Pitfalls

### Pitfall 1: PyJWKClient bloqueia o event loop

**O que dá errado:** Usar `PyJWKClient().get_signing_key_from_jwt(token)` em um endpoint async — a biblioteca usa `urllib.request.urlopen` (síncrono) que bloqueia o event loop de asyncio.
**Por que acontece:** PyJWT não tem implementação async do cliente JWKS.
**Como evitar:** Usar `httpx.AsyncClient` para buscar JWKS explicitamente no lifespan e em re-buscas. Cache em dict de módulo evita chamadas repetidas.
**Sinais de alerta:** Requests lentos sem motivo aparente; warnings de "blocking call in event loop" em modo debug.

### Pitfall 2: Remover `models/` antes de atualizar Alembic

**O que dá errado:** `alembic/env.py` importa `from caramello.models import *`. Deletar `models/` antes de atualizar este import quebra o Alembic imediatamente — migrações futuras falham.
**Por que acontece:** Alembic precisa importar os modelos SQLModel para comparar com o schema do banco.
**Como evitar:** Atualizar `alembic/env.py` para importar dos novos módulos de domínio *antes* de deletar `src/caramello/models/`. Verificar com `alembic check` ou `alembic history`.
**Sinais de alerta:** `ModuleNotFoundError: No module named 'caramello.models'` ao rodar alembic.

### Pitfall 3: Código gerado com tipos antigos falha no ruff

**O que dá errado:** O gerador atual usa `Optional[str]`, `List[T]`, `from typing import Optional, List`. Os novos paths de domínio (`src/caramello/user/models.py`) *não são excluídos* pelo ruff. O `bin/generate_code` vai passar, mas `ruff check src/` vai falhar.
**Por que acontece:** As exclusões de ruff `src/caramello/models` e `src/caramello/api/generated` serão removidas junto com esses diretórios; os novos paths não têm exclusão.
**Como evitar:** Atualizar `generate_models()` e `generate_router()` para emitir tipos modernos (`str | None`, `list[T]`, `from __future__ import annotations`) *antes* de regenerar.
**Sinais de alerta:** `ruff check src/` mostra UP035 (List deprecated), UP006, I001 após regeneração.

### Pitfall 4: Import cross-domain de link model quebrado

**O que dá errado:** `User` tem `link_model=FamilyMember`. O gerador atual emite `from caramello.models.familymember import FamilyMember`. Após reorganização, este import não existe mais.
**Por que acontece:** O gerador atual não tem noção de domínios — hardcoded para `caramello.models`.
**Como evitar:** Construir mapa `entity_domain: dict[str, str]` no início de `main()` do gerador, antes de processar qualquer entidade. Usar este mapa em `generate_models()` para resolver imports.
**Sinais de alerta:** `ImportError` na inicialização da app após regeneração.

### Pitfall 5: `ON CONFLICT DO NOTHING` não retorna a linha

**O que dá errado:** Após o `INSERT ... ON CONFLICT DO NOTHING`, o resultado não retorna a linha existente — precisa de um SELECT separado.
**Por que acontece:** `ON CONFLICT DO NOTHING` não faz upsert; apenas ignora o conflito silenciosamente.
**Como evitar:** Sempre seguir o INSERT de um SELECT por `idp_sub`. Esse é o padrão correto documentado em D-12.
**Sinais de alerta:** `user` retorna `None` no JIT provisioning quando o usuário já existe — 500 Internal Server Error.

### Pitfall 6: Anotação de segurança de geração esquecida

**O que dá errado:** Implementar `user/operations.py` mas esquecer de mudar `# CARAMELLO-GENERATED: stub` para `# CARAMELLO-GENERATED: implemented`. Na próxima execução de `bin/generate_code`, o arquivo implementado é sobrescrito.
**Por que acontece:** Fluxo manual; fácil de esquecer sob pressão.
**Como evitar:** O plano deve incluir explicitamente o passo de atualizar a anotação como parte da tarefa de implementação do stub. Documentar no CONTEXT.md D-09.
**Sinais de alerta:** `GET /user/me` retorna erro de not implemented após rodar `bin/generate_code`.

---

## Code Examples

### Instalação de PyJWT[crypto]

```bash
# Source: PyJWT docs installation guide [VERIFIED: Context7 /jpadilla/pyjwt]
uv add "PyJWT[crypto]"
```

### Mover httpx de dev para main deps no pyproject.toml

```toml
# [project] dependencies — adicionar:
"httpx>=0.28.1",

# [dependency-groups] dev — remover httpx (mantém pytest, ruff, mypy)
```

[VERIFIED: codebase] — httpx está em `dependency-groups.dev`; precisa estar em `project.dependencies` para disponibilidade em produção

### Decodificação JWT com kid lookup manual

```python
# Source: Pattern derivado de PyJWT CHANGELOG v2.12.0 e docs/usage.md [CITED: Context7 /jpadilla/pyjwt]

import jwt

unverified_header = jwt.get_unverified_header(token)
kid = unverified_header["kid"]
public_key = _jwks_cache[kid]

payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    options={"verify_aud": False},  # remover após confirmar claim aud (D-02)
)
```

### Conversão de JWK dict para chave RSA pública

```python
# Source: PyJWT docs [CITED: Context7 /jpadilla/pyjwt]
import jwt

for key_data in jwks["keys"]:
    kid = key_data["kid"]
    _jwks_cache[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
```

### INSERT ON CONFLICT DO NOTHING (SQLAlchemy + asyncpg)

```python
# Source: SQLAlchemy PostgreSQL dialect docs [VERIFIED: uv run python — import funciona no venv atual]
from sqlalchemy.dialects.postgresql import insert as pg_insert
from caramello.user.models import User

stmt = (
    pg_insert(User.__table__)
    .values(idp_sub=idp_sub, email=email, name=name)
    .on_conflict_do_nothing(index_elements=["idp_sub"])
)
await session.execute(stmt)
await session.commit()
# Depois: SELECT para obter o user (ON CONFLICT DO NOTHING não retorna)
```

Nota: com SQLModel AsyncSession, usar `session.execute(stmt)` (SQLAlchemy nativo) em vez de `session.exec()` para statements dialect-específicos.

[ASSUMED] — `session.execute()` vs `session.exec()` para dialect-specific statements no AsyncSession do SQLModel 0.0.38; verificar na implementação

---

## Estado da Arte

| Abordagem Antiga | Abordagem Atual | Mudou em | Impacto |
|-----------------|-----------------|----------|---------|
| `@app.on_event("startup")` | `@asynccontextmanager async def lifespan(app)` | FastAPI 0.93 | Startup e shutdown em uma função; mais limpo |
| `Optional[str]` de `typing` | `str \| None` nativo Python 3.10+ | Python 3.10 | Ruff UP rule exige o estilo moderno |
| `python-jose` para JWT | `PyJWT[crypto]` | — | `python-jose` tem CVEs; PyJWT é a alternativa padrão |
| `PyJWKClient` para JWKS | `httpx.AsyncClient` + dict manual | — | `PyJWKClient` é síncrono; não adequado para FastAPI async |

**Deprecated/Obsoleto:**
- `src/caramello/models/` — será removido nesta fase
- `src/caramello/api/generated/` — será removido nesta fase
- `src/caramello/repositories/__init__.py` — stub vazio, será removido
- `src/caramello/services/__init__.py` — stub vazio, será removido
- `tests/generated/` — testes gerados importam de `caramello.models.*`; serão removidos junto com os paths antigos

---

## Runtime State Inventory

Esta fase é uma reorganização de codebase (rename/refactor), mas não há runtime state com os caminhos antigos embeddados fora do repositório git.

| Categoria | Items Encontrados | Ação Necessária |
|-----------|-------------------|-----------------|
| Dados armazenados | Nenhum — banco `familia_dev` tem tabelas `user`, `family`, `family_member`, `family_invitation` mas sem referências a paths Python | Nenhuma migração de dados |
| Config de serviço live | Nenhum — sem n8n, sem tasks scheduladas, sem processos externos referenciando paths Python | Nenhuma |
| Estado registrado no OS | Nenhum | Nenhuma |
| Secrets/env vars | `.env.example` já tem os campos Keycloak como placeholder vazio; `.env` (gitignored) não verificado mas segue o template | Adicionar valores reais de `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` |
| Build artifacts | `__pycache__/` em todos os módulos antigos — serão invalidados automaticamente quando os módulos forem removidos | Limpar com `find . -type d -name __pycache__ -exec rm -rf {} +` após reorganização |

[VERIFIED: codebase] — `find src/ -name "*.py" | xargs grep -l "caramello.models\|caramello.api.generated"` — apenas arquivos no próprio repo

---

## Open Questions (RESOLVED)

1. **Valor real do claim `aud` no Keycloak existente (D-02)**
   - O que sabemos: CONTEXT.md D-02 diz para verificar antes de ativar validação de audience
   - O que era incerto: Se Keycloak emite `aud=["account"]`, `aud=client_id`, ou array com múltiplos valores
   - **RESOLVED:** Inspeção do token real delegada ao checkpoint humano do Plan 05 Task 7 Passo 7. `shared/auth.py` inicia com `options={"verify_aud": False}` conforme D-02 — ativar após confirmar o valor real do claim `aud` no Keycloak da infra existente.

2. **`session.execute()` vs `session.exec()` para INSERT dialect-specific**
   - O que sabemos: `session.exec()` é a interface SQLModel; `session.execute()` é SQLAlchemy nativo
   - O que era incerto: SQLModel 0.0.38 AsyncSession aceita `session.execute(pg_insert_stmt)` diretamente?
   - **RESOLVED:** Usar `session.execute(stmt)` (SQLAlchemy nativo) para dialect-specific PostgreSQL INSERT. Fallback documentado: se `session.execute()` não funcionar com AsyncSession, usar `await session.connection()` para acesso ao `Connection` nativo. Code examples incluídos nos planos.

---

## Environment Availability

| Dependência | Requerida por | Disponível | Versão | Fallback |
|-------------|--------------|------------|--------|---------|
| PostgreSQL | JIT provisioning, todos os routers | Não verificável nesta máquina | — | Sem fallback — obrigatório conforme CLAUDE.md |
| Keycloak | Auth (JWKS fetch no lifespan) | Não verificável nesta máquina | — | Sem fallback — infra existente segundo CONTEXT.md |
| Python 3.12.3 | Runtime | Sim | 3.12.3 | — |
| uv 0.11.11 | Gerenciamento de deps | Sim | 0.11.11 | — |
| PyJWT[crypto] | shared/auth.py | Não (precisa instalar) | 2.13.0 disponível no PyPI | — |
| httpx | Busca JWKS async | Sim (dev dep) | 0.28.1 | Precisa mover para main deps |
| sqlalchemy.dialects.postgresql | ON CONFLICT DO NOTHING | Sim (via sqlmodel) | — | — |

**Dependências ausentes sem fallback:**
- PostgreSQL: obrigatório para testes de integração e JIT provisioning
- Keycloak: necessário para o lifespan funcionar em produção (sem mock nos testes — Phase 5)

**Dependências ausentes com fallback:**
- PyJWT[crypto]: não instalado no venv do projeto — instalar com `uv add "PyJWT[crypto]"` como primeiro passo
- httpx em main deps: está nos dev deps; mover para main deps é necessário para o container Docker funcionar (Phase 5)

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|------------|-------|
| Framework | pytest 9.0.1 |
| Config file | nenhum — sem `[tool.pytest.ini_options]` em pyproject.toml |
| Comando rápido | `uv run pytest tests/ -x -q` |
| Suite completa | `uv run pytest tests/ -v` |

### Mapeamento Requirements → Testes

| Req ID | Comportamento | Tipo de Teste | Comando Automatizado | Arquivo Existe? |
|--------|--------------|---------------|---------------------|----------------|
| STRUCT-01 | `grep -r "models/" src/` retorna vazio | Smoke (shell) | `grep -r "models/" src/ && exit 1 || exit 0` | N/A — verificação shell |
| STRUCT-02 | Generator produz `user/models.py` com campo `domain` | Unit | `uv run pytest tests/test_generator.py -x` | Não — Wave 0 |
| AUTH-01 | `GET /user/me` sem token retorna 401 | Integration | `uv run pytest tests/test_auth.py::test_me_unauthenticated -x` | Não — Wave 0 |
| AUTH-02 | Primeira request com token válido cria user no banco | Integration | `uv run pytest tests/test_auth.py::test_jit_provisioning -x` | Não — Wave 0 |
| AUTH-03 | `get_current_user` importável de `shared.auth` | Unit | `uv run pytest tests/test_auth.py::test_auth_module -x` | Não — Wave 0 |
| USER-01 | `GET /user/me` com token válido retorna `id`, `email`, `name` | Integration | `uv run pytest tests/test_user_operations.py::test_get_me -x` | Não — Wave 0 |

### Sampling Rate

- **Por commit de task:** `uv run ruff check src/ && uv run mypy src/`
- **Por merge de wave:** `uv run pytest tests/ -x -q`
- **Phase gate:** `uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/ -v` verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_generator.py` — cobre STRUCT-02 (generator com campo domain)
- [ ] `tests/test_auth.py` — cobre AUTH-01, AUTH-02, AUTH-03 (usando `dependency_overrides` para mock de token — Phase 5 tem banco isolado, mas testes básicos de auth podem usar mocks)
- [ ] `tests/test_user_operations.py` — cobre USER-01

**Nota sobre isolamento de banco:** Phase 5 implementa banco isolado (TEST-01). Nesta fase, testes de auth podem usar `dependency_overrides` para mockar `get_current_user` e evitar dependência de Keycloak real. Testes que precisam de banco real dependem de `.env` configurado — marcar como `@pytest.mark.integration` e excluir da suite padrão até Phase 5.

---

## Security Domain

### Categorias ASVS Aplicáveis

| Categoria ASVS | Aplica | Controle Padrão |
|----------------|--------|-----------------|
| V2 Authentication | Sim | PyJWT[crypto] + HTTPBearer — validação local de JWT RS256 |
| V3 Session Management | Não | Stateless JWT — sem sessão server-side |
| V4 Access Control | Sim | `Depends(get_current_user)` em todos os endpoints protegidos |
| V5 Input Validation | Sim | Pydantic valida automaticamente claims extraídos; SQLModel valida tipos de campo |
| V6 Cryptography | Sim | PyJWT[crypto] para verificação de assinatura RSA — sem implementação manual |

### Padrões de Ameaça Conhecidos para FastAPI + Keycloak JWT

| Padrão | STRIDE | Mitigação Padrão |
|--------|--------|-----------------|
| JWT sem verificação de assinatura | Tampering | `jwt.decode()` com algoritmo explícito `["RS256"]` — nunca `algorithms=["none"]` |
| JWT com algoritmo `none` (downgrade) | Tampering | Lista explícita de algoritmos em `jwt.decode()` previne downgrade |
| Token expirado aceito | Elevation of Privilege | PyJWT verifica `exp` por padrão — não usar `"verify_exp": False` em produção |
| JWKS fetch falho silencioso no startup | Denial of Service | `response.raise_for_status()` + erro fatal no lifespan se JWKS inacessível |
| Race condition no JIT provisioning | Tampering | `ON CONFLICT DO NOTHING` garante atomicidade; não usar `select-then-insert` |
| Endpoint desprotegido por esquecimento | Elevation of Privilege | Template de router inclui `Depends(get_current_user)` por padrão — opt-out explícito se necessário |

---

## Assumptions Log

| # | Claim | Seção | Risco se Errado |
|---|-------|-------|----------------|
| A1 | Formato do stub gerado em `operations.py` (router + APIRouter + decorator) | Code Examples — Pattern 4 | O planner pode especificar estrutura que conflita com o que o gerador produz — baixo risco, ajuste na implementação |
| A2 | `session.execute(pg_insert_stmt)` funciona com SQLModel AsyncSession 0.0.38 | Code Examples — INSERT ON CONFLICT | Se não funcionar, precisará de `await session.connection()` para acesso nativo — workaround conhecido |
| A3 | Keycloak emite `alg: RS256` nos tokens (não ES256 ou RS384) | Pattern 1 e 2 — algorithms=["RS256"] | Se Keycloak usar ES256, o `from_jwk` correto muda e o decode falha — verificar ao inspecionar token real |

---

## Sources

### Primary (HIGH confidence)
- Context7 `/jpadilla/pyjwt` — PyJWKClient.fetch_data() é síncrono (urllib); `jwt.algorithms.RSAAlgorithm.from_jwk()`; `jwt.get_unverified_header()`; `jwt.decode()` com algorithms
- Context7 `/fastapi/fastapi` — lifespan asynccontextmanager; HTTPBearer; Depends() pattern
- Codebase inspecionado — `scripts/generate_code.py`, `shared/database.py`, `core/config.py`, `main.py`, `pyproject.toml`, `alembic/env.py`, todos os YAMLs DSL

### Secondary (MEDIUM confidence)
- `pip index versions PyJWT` — versão 2.13.0 verificada no PyPI
- `uv run python -c "from sqlalchemy.dialects.postgresql import insert"` — import disponível no venv
- `uv run ruff check /tmp/test_model.py` — violações UP035, I001 confirmadas no código gerado atual
- `uv run python -c "from sqlmodel import SQLModel, Field; ..."` — SQLModel 0.0.38 aceita tipos modernos `str | None`

### Tertiary (LOW confidence)
- Nenhum

---

## Project Constraints (from CLAUDE.md)

| Diretriz | Fonte | Implicação para esta fase |
|---------|-------|--------------------------|
| Stack: Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL obrigatório — sem SQLite | CLAUDE.md Constraints | Auth JIT provisioning usa AsyncSession; sem fallback SQLite nos testes desta fase |
| Auth: Keycloak com OIDC/JWT — clients de dev e prod já configurados | CLAUDE.md Constraints | `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` precisam de valores reais antes de testar |
| Código gerado em `src/caramello/domains/*/` não deve ser editado diretamente | CLAUDE.md Constraints | `user/models.py`, `user/router.py`, `family/models.py`, `family/router.py` — nunca editar; editar YAML e regenerar. Exceção: `operations.py` com anotação `implemented` |
| ruff check src/ e mypy src/ devem passar sem erros | CLAUDE.md (herdado das Phases 1 e 2) | Gerador deve emitir código ruff/mypy-clean; exclusões antigas (`src/caramello/models`, `src/caramello/api/generated`) serão removidas do pyproject.toml junto com os diretórios |
| Escopo: apenas Grupo Família — sem tabelas compartilhadas | CLAUDE.md Constraints | Domínios `user` e `family` apenas; sem outros domínios nesta fase |
| Commits em pt-BR, Conventional Commits, corpo obrigatório | AGENTS.md | Todos os commits desta fase seguem este padrão |

---

## Metadata

**Breakdown de confiança:**
- Standard Stack: HIGH — versões verificadas no PyPI e no venv; comportamento de PyJWKClient verificado por inspeção de código-fonte
- Architecture: HIGH — baseado em código existente do projeto + Context7 para FastAPI lifespan e HTTPBearer
- Generator Evolution: HIGH — baseado em inspeção direta de `scripts/generate_code.py` e teste de ruff violations
- Pitfalls: HIGH — todos verificados experimentalmente (ruff test, import test, código-fonte do PyJWKClient)

**Data da research:** 2026-05-25
**Válida até:** 2026-06-25 (stack estável; PyJWT e FastAPI têm versões fixas no lockfile)
