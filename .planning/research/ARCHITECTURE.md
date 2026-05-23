# Architecture Patterns

**Domain:** Backend FastAPI organizado por domínios com MCP integrado (Keycloak + fastapi-mcp)
**Researched:** 2026-05-23
**Confidence:** HIGH — baseado em documentação oficial fastapi-mcp (Context7), FastAPI oficial, codebase inspecionado

---

## Recommended Architecture

```
src/caramello/
├── main.py                        # App factory: registra routers, monta MCP, configura CORS/lifespan
├── shared/
│   ├── __init__.py
│   ├── auth.py                    # JWT validation (Keycloak JWKS) + get_current_user dependency
│   └── database.py                # AsyncEngine + get_session dependency (move de core/)
├── domains/
│   ├── __init__.py
│   ├── familia/
│   │   ├── __init__.py
│   │   ├── models.py              # SQLModel table=True (gerado pelo DSL)
│   │   ├── schemas.py             # Pydantic Read/Create/Update (gerado pelo DSL)
│   │   ├── services.py            # Business logic puro (manual, sem FastAPI)
│   │   └── routes.py              # APIRouter com Depends(get_current_user) (manual)
│   ├── financeiro/                # Futuro M2
│   └── lista_compras/             # Futuro M3
└── core/
    └── config.py                  # Settings via pydantic-settings (já existe)

alembic/
├── env.py                         # imports from caramello.domains.*
└── versions/

dsl/
├── manifest.yaml
└── entities/
    ├── user.yaml                  # domain: shared
    ├── family.yaml                # domain: familia
    ├── family_member.yaml         # domain: familia
    └── family_invitation.yaml     # domain: familia
```

---

## Component Boundaries

| Componente | Responsabilidade | Comunica com |
|------------|-----------------|--------------|
| `main.py` | Registra routers, monta MCP server, configura CORS e lifespan | Todos os routers de domínio; FastApiMCP |
| `shared/auth.py` | Valida JWT (Keycloak JWKS), provisiona User just-in-time, expõe `get_current_user` | `shared/database.py` (session), `domains/familia/models.py` (User model) |
| `shared/database.py` | `AsyncEngine`, `get_session()` generator | PostgreSQL via asyncpg |
| `domains/familia/models.py` | SQLModel table definitions — gerado pelo DSL | PostgreSQL (via Alembic migrations) |
| `domains/familia/schemas.py` | Pydantic I/O shapes (Read, Create, Update) — gerado pelo DSL | `routes.py` (response_model), serializacão |
| `domains/familia/services.py` | Business logic: Family CRUD, membership, invitation lifecycle | `models.py`, `AsyncSession` (via injeção) |
| `domains/familia/routes.py` | FastAPI APIRouter: HTTP → service call → response | `services.py`, `shared/auth.py` (Depends), `schemas.py` |
| `fastapi-mcp` (montado em `main.py`) | Expõe endpoints FastAPI como MCP tools via `/mcp` | Mesma ASGI app — sem HTTP extra |
| `alembic/` | Versionamento de schema PostgreSQL | `SQLModel.metadata` — importa modelos de todos os domains |

**Regra de dependência:** A seta aponta para o que é importado. Routes → Services → Models. Nunca o inverso. `services.py` não deve importar de `routes.py`.

---

## Data Flow

### Request REST normal (autenticado)

```
HTTP Request (Bearer token)
  → main.py (CORS middleware)
  → domains/familia/routes.py (APIRouter)
  → shared/auth.py: get_current_user (Depends)
      → valida JWT contra Keycloak JWKS (local, sem round-trip ao Keycloak)
      → upsert User na tabela users (just-in-time provisioning)
      → retorna User object
  → domains/familia/services.py: lógica de negócio
      → shared/database.py: get_session (AsyncSession)
      → queries SQLModel async (select, add, commit)
  → serialização via schemas.py (response_model)
  → HTTP Response
```

### Request MCP tool call

```
MCP client → POST /mcp (Streamable HTTP transport)
  → fastapi-mcp converte tool call em HTTP request interno
  → reutiliza a mesma ASGI app (sem HTTP extra, sem porta separada)
  → passa pelo mesmo fluxo de autenticação acima
      (fastapi-mcp propaga Authorization header via headers=["authorization"])
  → mesmo service, mesma lógica
  → resposta serializada de volta ao cliente MCP
```

### DSL generation flow

```
editar dsl/entities/*.yaml (com campo domain:)
  → bin/generate_code (scripts/generate_code.py)
  → para cada entity: lê domain, resolve output_dir = src/caramello/domains/{domain}/
  → gera models.py (SQLModel table=True)
  → gera schemas.py (Read, Create, Update — sem Field args de banco)
  → NÃO gera services.py nem routes.py (manual)
  → NÃO toca em arquivos existentes fora de models.py e schemas.py
```

---

## Decisions: fastapi-mcp

### Como fastapi-mcp descobre endpoints

fastapi-mcp lê a OpenAPI spec gerada automaticamente pelo FastAPI. **Não precisa de anotações especiais além de `operation_id` e `tags`**, que já fazem parte do padrão FastAPI. Cada endpoint se torna um MCP tool usando seu `operation_id` como nome da ferramenta.

**Decisão para este projeto:** usar `tags` por domínio como mecanismo de controle.

```python
# domains/familia/routes.py
router = APIRouter(
    prefix="/familia",
    tags=["familia"],          # tag de domínio — controla exposição MCP
)

@router.get("/families/{family_id}", operation_id="get_family")
async def get_family(...):
    ...
```

**O que NÃO expor via MCP:** endpoints internos/operacionais (health check, readiness probe, rotas de debug) devem receber a tag `"internal"` e ser excluídos explicitamente.

### Configuração fastapi-mcp em main.py

```python
from fastapi_mcp import FastApiMCP, AuthConfig
from fastapi.security import HTTPBearer

mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    description="Família domain tools for AI agents",
    include_tags=["familia"],          # expõe só endpoints do domínio familia
    # futuramente: include_tags=["familia", "financeiro", "lista_compras"]
    describe_all_responses=True,       # ajuda agentes a entender estrutura de retorno
    describe_full_response_schema=True,
    auth_config=AuthConfig(
        dependencies=[Depends(get_current_user)],   # mesma dependency que as rotas REST
    ),
    headers=["authorization"],         # propaga Bearer token aos tool calls
)
mcp.mount_http()   # monta em /mcp (padrão)
```

**Ponto crítico:** `FastApiMCP` deve ser instanciado DEPOIS que todos os `include_router()` já foram chamados. Se routers forem adicionados depois, é necessário chamar `mcp.setup_server()` novamente. Para este projeto (routers registrados no startup), a ordem em `main.py` é:

1. Criar `app = FastAPI(...)`
2. Registrar todos os routers de domínio via `app.include_router(...)`
3. Instanciar `FastApiMCP(app, ...)` e chamar `mcp.mount_http()`

### Controle: o que expor vs. o que não expor

| Endpoint | Tag | Exposto via MCP? |
|----------|-----|-----------------|
| `GET /familia/families` | `familia` | Sim |
| `POST /familia/families/{id}/invite` | `familia` | Sim |
| `GET /health` | `internal` | Não (`exclude_tags=["internal"]` ou simplesmente não incluir na `include_tags`) |
| `GET /` (root) | nenhuma | Não (não está em `include_tags=["familia"]`) |

---

## Decisions: Autenticação

### Middleware vs. Depends — qual usar

**Decisão: `Depends(get_current_user)` explicitamente em cada router, não middleware global.**

Razão: alguns endpoints não precisam de auth (`GET /health`, `GET /docs`). Middleware global exige lógica de exceção e torna o código menos legível. `Depends` é o padrão idiomático do FastAPI, aparece na OpenAPI spec, e fastapi-mcp o respeita nativamente.

**Na prática:** auth é aplicada no nível do `APIRouter` via `dependencies=[Depends(get_current_user)]`:

```python
router = APIRouter(
    prefix="/familia",
    tags=["familia"],
    dependencies=[Depends(get_current_user)],   # aplica a todas as rotas deste router
)
```

Isso aplica `get_current_user` a todas as rotas do router sem repetir o parâmetro em cada função. Endpoints individuais que precisam do objeto `user` recebem `current_user: User = Depends(get_current_user)` como parâmetro para poder acessá-lo.

### shared/auth.py — estrutura

```python
# shared/auth.py

from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession
from shared.database import get_session

security = HTTPBearer()

class JWKSClient:
    """Singleton com cache de chaves públicas do Keycloak."""
    _client: PyJWKClient | None = None

    @classmethod
    def get(cls, jwks_url: str) -> PyJWKClient:
        if cls._client is None:
            cls._client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        return cls._client

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Valida JWT contra Keycloak JWKS. Faz upsert just-in-time do usuário local."""
    token = credentials.credentials
    # 1. Valida assinatura RS256 contra Keycloak JWKS (local, sem round-trip)
    # 2. Verifica exp, iss, aud
    # 3. Extrai sub (idp_sub), email, name
    # 4. Upsert na tabela users
    # 5. Retorna User ORM object
    ...
```

**Biblioteca JWT:** PyJWT (`jwt` package) com `PyJWKClient` — mais mantida que python-jose, suporte nativo a JWKS. Keycloak usa RS256 por padrão.

**Sem round-trip ao Keycloak por request:** validação local contra chave pública (do JWKS endpoint), não via introspection endpoint. Chave em cache por 1 hora.

---

## Decisions: Registro de Routers em main.py

### Prefixo por domínio (escolhido) vs. versioning

**Decisão: prefixo por domínio, sem `/v1/` no path.**

Razão: este é um backend pessoal/familiar com um único cliente front-end sob controle total. Versioning de URL resolve um problema de compatibilidade retroativa que não existe aqui. Prefixo por domínio comunica intenção arquitetural e é mais limpo para o MCP.

```python
# main.py
from domains.familia import routes as familia_routes

app.include_router(familia_routes.router, prefix="/familia")
# futuro: app.include_router(financeiro_routes.router, prefix="/financeiro")
# futuro: app.include_router(lista_compras_routes.router, prefix="/lista_compras")
```

O `prefix` em `include_router` combina com o `prefix` definido no próprio `APIRouter`:

```python
# routes.py define prefix="/families" (plural, o recurso)
# include_router adiciona prefix="/familia" (o domínio)
# resultado: GET /familia/families/{id}
```

**Tags para OpenAPI/MCP:** cada router usa `tags=["{domain_name}"]`. fastapi-mcp usa tags para filtragem.

---

## Decisions: DSL Generator — Evolução para Domínios

### Campo `domain` no YAML

Adicionar campo obrigatório `domain` em cada entity YAML:

```yaml
# dsl/entities/family.yaml
name: Family
domain: familia           # novo campo — define o subdiretório de output
table_name: family
...
```

```yaml
# dsl/entities/user.yaml
name: User
domain: shared            # User é cross-domain — fica em shared/
table_name: users         # corrigir para plural (convenção)
...
```

### Output do generator

O generator atualizado resolve o diretório de output assim:

```python
domain = entity_data.get('domain', 'shared')
output_dir = ROOT_DIR / "src" / "caramello" / (
    "shared" if domain == "shared"
    else f"domains/{domain}"
)
```

**O generator produz apenas:**
- `models.py` — SQLModel com `table=True`
- `schemas.py` — Read/Create/Update sem Field args de banco

**O generator NÃO produz:**
- `services.py` — lógica de negócio é manual
- `routes.py` — routers são manuais (dependências de auth, lógica de negócio específica)

### Imports entre domínios

Regra: modelos só referenciam outros modelos via import direto:

```python
# domains/familia/models.py (gerado)
from caramello.shared.models import User   # cross-domain import explícito
```

O generator deve gerar imports corretos baseado no campo `domain` da entidade referenciada. O `manifest.yaml` deve ser o índice que o generator usa para resolver `domain` de cada entidade pelo nome.

Estratégia no generator:

```python
# construir índice domain por entity name durante a leitura do manifest
entity_domain_map = {data['name']: data.get('domain', 'shared') for data in all_entities}

# ao gerar import de relacionamento:
def resolve_import(entity_name: str) -> str:
    domain = entity_domain_map[entity_name]
    base = "caramello.shared" if domain == "shared" else f"caramello.domains.{domain}"
    return f"from {base}.models import {entity_name}"
```

---

## Decisions: Alembic com Múltiplos Domínios

### Estratégia: uma migration, todos os domínios

**Decisão: um único Alembic `env.py`, uma única cadeia de migrations, todos os modelos.**

Razão: o banco `familia_dev` / `familia_prod` é um único database PostgreSQL para um único grupo. Não há necessidade de migrations isoladas por domínio — isso adicionaria complexidade operacional sem benefício real no escopo deste projeto (1-5 usuários, equipe de 1).

### env.py atualizado

O `env.py` atual usa `from caramello.models import *`. Com a nova estrutura, muda para importação explícita de todos os domínios:

```python
# alembic/env.py
from sqlmodel import SQLModel

# Importar todos os modelos para registrar metadata antes do autogenerate
from caramello.shared.models import User          # noqa: F401
from caramello.domains.familia.models import (    # noqa: F401
    Family, FamilyMember, FamilyInvitation
)
# Futuros domínios: importar aqui quando adicionados
# from caramello.domains.financeiro.models import ...

target_metadata = SQLModel.metadata
```

**Alternativa (para quando houver muitos domínios):** scan automático via `importlib` de todos os `domains/*/models.py`. Para o M1 com 1 domínio, importação explícita é mais simples e mais previsível.

### Naming convention de tabelas

Definida em `docs/apps-platform.md` §5: sem schemas PostgreSQL, isolamento por prefixo de tabela.

```
users              # shared (sem prefixo — User é cross-domain central)
family             # domínio familia → renomear para familia_family
family_member      # → familia_family_member
family_invitation  # → familia_family_invitation
```

**Decisão:** manter `users` sem prefixo (é referenciado por todos os domínios via FK). Tabelas específicas de domínio recebem prefixo `{domain}_`.

---

## Build Order (Dependências entre Componentes)

Ordem de implementação com dependências anotadas:

```
1. core/config.py (já existe, ajustar para variáveis Keycloak)
   └── depende de: nada

2. shared/database.py (novo — move de core/, troca psycopg2 por asyncpg, AsyncSession)
   └── depende de: core/config.py

3. User model em shared/ (DSL generator + dsl/entities/user.yaml corrigido)
   └── depende de: shared/database.py (para Alembic)
   └── CRÍTICO: remover hashed_password, google_id; adicionar idp_sub; PK UUID

4. shared/auth.py (Keycloak JWT + get_current_user + just-in-time provisioning)
   └── depende de: shared/database.py (get_session), User model

5. DSL generator evoluído (suporte a campo domain, output em domains/{domain}/)
   └── depende de: definição de estrutura de pastas (passos 1-4)

6. domains/familia/models.py + schemas.py (DSL generator)
   └── depende de: generator evoluído, User model em shared/

7. domains/familia/services.py (manual — Family CRUD, membership, invitations)
   └── depende de: models.py, shared/database.py

8. domains/familia/routes.py (manual — APIRouter com auth)
   └── depende de: services.py, shared/auth.py, schemas.py

9. main.py reescrito (registra router familia, monta fastapi-mcp)
   └── depende de: routes.py, fastapi-mcp instalado

10. alembic/env.py atualizado + migration recriada
    └── depende de: todos os models importáveis (passos 3, 6)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Services com import de FastAPI
**O que é:** `services.py` importa `HTTPException`, `Request`, ou qualquer coisa de `fastapi`.
**Por que é ruim:** Quebra o princípio de services como lógica pura. Impossibilita reutilização via MCP sem passar pela camada HTTP.
**Em vez disso:** Services lançam exceções de domínio (ex: `FamilyNotFoundError`). Routes capturam e convertem em `HTTPException`.

### Anti-Pattern 2: Lógica de negócio em routes.py
**O que é:** queries SQLModel diretamente em funções de router, sem services.
**Por que é ruim:** fastapi-mcp expõe os endpoints REST como ferramentas MCP. A lógica fica duplicada se alguém quiser adicionar uma rota MCP diferente.
**Em vez disso:** Toda lógica fica em `services.py`. Routes são wrappers de 5-10 linhas.

### Anti-Pattern 3: FastApiMCP instanciado antes dos routers
**O que é:** chamar `FastApiMCP(app)` antes de `app.include_router(...)`.
**Por que é ruim:** fastapi-mcp lê a OpenAPI spec no momento da instanciação. Endpoints adicionados depois não são incluídos automaticamente.
**Em vez disso:** instanciar `FastApiMCP` depois de todos os `include_router()` em `main.py`.

### Anti-Pattern 4: Validação JWT por introspection endpoint
**O que é:** chamar `{keycloak_url}/introspect` em cada request para validar o token.
**Por que é ruim:** Adiciona latência de rede em cada request, cria dependência de disponibilidade do Keycloak para cada operação.
**Em vez disso:** Validação local usando chave pública do JWKS endpoint (`{keycloak_url}/.well-known/jwks.json`), com cache de 1 hora.

### Anti-Pattern 5: Editar arquivos gerados pelo DSL diretamente
**O que é:** editar `domains/familia/models.py` ou `schemas.py` manualmente.
**Por que é ruim:** o próximo `bin/generate_code` sobrescreve tudo.
**Em vez disso:** editar o YAML em `dsl/entities/` e regenerar.

---

## Scalability Considerations

Este backend serve 1-5 usuários simultâneos. As decisões abaixo são adequadas para esse escopo e não precisam ser revisitadas até crescimento expressivo.

| Preocupação | Na escala atual (1-5 usuários) | Se crescer |
|-------------|-------------------------------|-----------|
| Connection pool | `NullPool` para Alembic, pool padrão SQLAlchemy para app | Ajustar pool size |
| fastapi-mcp em processo | Single ASGI app — adequado | Separar em `mcp_app` com httpx apontando para API |
| Keycloak JWKS cache | 1 hora em memória — sem problema | Redis para instâncias múltiplas |
| Migrations | Sequential, single-branch | Continua adequado |

---

## Sources

- Context7 / fastapi-mcp official docs: `include_operations`, `include_tags`, `exclude_tags`, `AuthConfig`, `headers`, `mount_http` — HIGH confidence
- FastAPI official docs (fastapi.tiangolo.com/tutorial/bigger-applications/): `include_router`, prefix, tags, dependencies — HIGH confidence
- Context7 / SQLModel docs: `AsyncSession`, `get_session` dependency pattern — HIGH confidence
- skycloak.io Keycloak+FastAPI tutorial: `PyJWKClient`, RS256 local validation — MEDIUM confidence (single source, pattern verified against PyJWT docs)
- WebSearch: Alembic multi-domain strategy, single env.py com importação explícita — MEDIUM confidence (múltiplas fontes concordam no padrão)
