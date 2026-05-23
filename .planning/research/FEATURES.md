# Feature Landscape — M1: FastAPI Foundation (Brownfield)

**Domain:** Backend foundation para sistema de organização familiar (FastAPI async + Keycloak + MCP)
**Pesquisado:** 2026-05-23
**Confiança geral:** HIGH (stack bem documentado, decisões arquiteturais já estabelecidas)

---

## Contexto de Decisão

Este não é um projeto greenfield nem um domínio de negócio. M1 é revisão de fundação: corrigir o que existe,
estabelecer o padrão correto, e usar o domínio `familia` como piloto. Os gaps críticos estão mapeados em
`.planning/codebase/CONCERNS.md` (G1/G2/G3 bloqueiam qualquer produção).

As features abaixo respondem "o que uma fundação FastAPI async bem feita precisa ter?" para este stack
específico (FastAPI + asyncpg + SQLModel + Keycloak + fastapi-mcp).

---

## Table Stakes

Features sem as quais a fundação está errada. Ausência = produto tecnicamente incorreto ou inseguro.

### TS-1: Driver async com AsyncSession correta

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | FastAPI foi projetado para async I/O. `psycopg2-binary` + `Session` síncrona bloqueia o event loop em cada query — a app afirma ser async mas não é. Isso é G3 em CONCERNS.md. |
| Complexidade | Baixa — substituição cirúrgica |
| Dependências | Pré-requisito para todos os outros items |

**O que fazer:**
- Substituir `psycopg2-binary` por `asyncpg` no `pyproject.toml`
- Reescrever `session.py` usando `create_async_engine`, `async_sessionmaker`, `AsyncSession`
- `DATABASE_URL` deve usar prefixo `postgresql+asyncpg://`
- `get_session()` vira `AsyncGenerator[AsyncSession, None]` com `yield`
- Todos os routers passam a `async def` com `await session.*`

**Não fazer no M1:** Connection pooling avançado (PgBouncer, pool_size tuning) — escala de 1-5 usuários não justifica.

---

### TS-2: Modelo User correto (idp_sub, sem senha local)

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | O modelo atual tem `hashed_password` e `google_id` de uma estratégia de auth descartada. `UserCreate` aceita `password: str` em plaintext. Isso é G1 em CONCERNS.md — cada schema gerado está errado. |
| Complexidade | Baixa — mudança no DSL + regeneração |
| Dependências | TS-1 (precisa de AsyncSession para rodar a migration) |

**Campos corretos do User:**
```sql
id         UUID PRIMARY KEY DEFAULT gen_random_uuid()
idp_sub    TEXT NOT NULL UNIQUE   -- "sub" do JWT Keycloak
email      TEXT NOT NULL UNIQUE
name       TEXT
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

**O que fazer:**
- Atualizar `dsl/entities/user.yaml`: remover `hashed_password`, `google_id`, `phone_number`, `is_active`; adicionar `idp_sub`
- Regenerar modelos e schemas
- Descartar migration existente; criar nova migration via `alembic revision --autogenerate`
- `datetime.utcnow` → `datetime.now(timezone.utc)` em todos os modelos (deprecated desde Python 3.12)

---

### TS-3: Camada de autenticação JWT Keycloak (shared/auth.py)

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | Todos os endpoints são públicos hoje (G2 em CONCERNS.md). Qualquer caller pode ler, criar e deletar dados. A fundação não pode existir sem auth. |
| Complexidade | Média |
| Dependências | TS-2 (precisa do modelo User correto para provisioning) |

**O que fazer:**
- Criar `src/caramello/shared/auth.py`
- Biblioteca: `PyJWT[crypto]>=2.9.0` — PyJWT está ativamente mantido; `python-jose` não recebe atualizações há anos (HIGH confidence, múltiplas fontes)
- Validação obrigatória: assinatura RS256 via JWKS endpoint do Keycloak, `exp`, `iss` (realm URL), `aud`
- JWKS com cache local (não chamar Keycloak a cada request) — usar `PyJWKClient` com `cache_keys=True`
- Dependência FastAPI: `get_current_user(token: str = Depends(HTTPBearer())) -> User`
- Just-in-time provisioning dentro do `get_current_user`: buscar por `idp_sub`, criar registro se não existir

**Padrão canônico FastAPI para auth:**
```python
# shared/auth.py
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    session: AsyncSession = Depends(get_session),
) -> User:
    payload = validate_token(credentials.credentials)  # PyJWT decode + JWKS
    user = await get_or_create_user(session, idp_sub=payload["sub"], email=payload["email"])
    return user
```

**Não fazer no M1:**
- Middleware global de auth — FastAPI `Depends` por rota/router é o padrão correto; middleware é para cross-cutting concerns como logging
- Token introspection remota em cada request — valide localmente com JWKS cacheado
- Role-based authorization complexa — verificar membership na Family é suficiente para M1

---

### TS-4: Estrutura por domínios com shared/

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | Estrutura flat atual (`models/`, `schemas/`, `api/generated/`) contradiz a decisão arquitetural documentada em `docs/apps-platform.md` §3. Adicionar domínios futuros (financeiro, agenda) nessa estrutura flat cria um caos navegacional. |
| Complexidade | Média — reorganização de arquivos + atualização de imports |
| Dependências | TS-1, TS-2 |

**Estrutura alvo (HIGH confidence — padrão largamente adotado pela comunidade FastAPI):**
```
src/caramello/
├── main.py
├── shared/
│   ├── auth.py          # validação JWT + just-in-time provisioning
│   ├── config.py        # pydantic-settings
│   └── database.py      # AsyncSession, get_session
├── domains/
│   └── familia/
│       ├── models.py    # SQLModel table models
│       ├── schemas.py   # Pydantic request/response models
│       ├── services.py  # lógica de negócio (sem I/O direto de rota)
│       └── router.py    # APIRouter com Depends(get_current_user)
```

**Por que services.py é obrigatório (não opcional):**
A separação router → services.py é o que permite que MCP (via fastapi-mcp) e REST reutilizem a mesma lógica sem duplicação. Se a lógica estiver inline nos handlers, MCP precisará de código próprio. Isso é decisão arquitetural registrada em `docs/apps-platform.md` §7 e `PROJECT.md`.

**Sobre o DSL generator:**
O generator atual produz código flat. A decisão de evoluí-lo para suportar campo `domain` no YAML é correta para o longo prazo, mas para M1 o piloto `familia` pode ter seus arquivos escritos manualmente enquanto o generator é atualizado em paralelo. Prioridade: fazer a estrutura correta existir; o generator pode vir depois.

---

### TS-5: Endpoints do domínio familia protegidos e funcionais

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | M1 precisa de um domínio piloto que valide toda a fundação de ponta a ponta. Sem endpoints funcionais, a fundação não está validada. |
| Complexidade | Média |
| Dependências | TS-1, TS-2, TS-3, TS-4 |

**Operações mínimas do domínio familia:**

*User (shared — provisioning automático via JWT):*
- `GET /me` — retorna o User autenticado (criado via JIT se primeiro acesso)

*Family:*
- `POST /familia/families` — criar família (caller vira owner)
- `GET /familia/families/{id}` — detalhes da família
- `GET /familia/families/mine` — famílias do usuário autenticado

*FamilyMember:*
- `GET /familia/families/{id}/members` — listar membros

*FamilyInvitation:*
- `POST /familia/families/{id}/invitations` — gerar convite (apenas owner)
- `POST /familia/invitations/{token}/join` — usar convite para solicitar entrada
- `PATCH /familia/invitations/{id}/approve` — owner aprova solicitação
- `PATCH /familia/invitations/{id}/reject` — owner rejeita

**Regra crítica de segurança:**
Routers nunca retornam `response_model=FamilyMember` (table model direta). Sempre usar schema `FamilyMemberRead` separado. Isso está violado no código atual (`familymember_router.py`).

---

### TS-6: Servidor MCP integrado via fastapi-mcp

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | MCP é cidadão de primeira classe no projeto (PROJECT.md, apps-platform.md §7). É um requisito de M1, não um diferenciador futuro. |
| Complexidade | Baixa — setup é literal 3 linhas se a estrutura estiver correta |
| Dependências | TS-4 (services.py separado), TS-3 (auth), TS-5 (endpoints existentes) |

**O que fastapi-mcp expõe automaticamente (HIGH confidence):**
- Todos os endpoints FastAPI como MCP tools
- Request/response schemas (Pydantic → tool schema)
- Docstrings dos handlers como descrições das tools
- `operation_id` de cada rota como nome da MCP tool — logo, `operation_id` deve ser definido explicitamente em cada rota (não gerado automaticamente pelo FastAPI) para ter nomes legíveis por agentes

**Setup mínimo:**
```python
# main.py
from fastapi_mcp import FastApiMCP, AuthConfig
from fastapi.security import HTTPBearer

mcp = FastApiMCP(
    app,
    name="Caramello MCP",
    auth_config=AuthConfig(dependencies=[Depends(HTTPBearer())]),
)
mcp.mount()
# MCP disponível em /mcp
```

**O que precisa de atenção manual:**
- `operation_id` explícito em cada rota (ex: `operation_id="list_family_members"`)
- Docstrings nos handlers — se não tiver docstring, a tool fica sem descrição
- Filtrar quais endpoints expor via `include_tags` ou `exclude_tags` se necessário (ex: endpoints internos de healthcheck não precisam virar tools)

**Não fazer no M1:** Servidor MCP separado, FastMCP standalone, ou qualquer duplicação de lógica para MCP. O fastapi-mcp via ASGI é a decisão correta para este porte.

---

### TS-7: Docker com multi-stage e non-root user

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | Não existe Dockerfile no projeto (CONCERNS.md). Sem Docker, não há deployment path. Multi-stage e non-root são o standard mínimo aceitável em 2026, não um diferenciador. |
| Complexidade | Baixa |
| Dependências | Nenhuma técnica; bloqueante para produção |

**O que é essencial:**
```dockerfile
# Stage 1: builder
FROM python:3.12-slim AS builder
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system --no-cache .

# Stage 2: production
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN addgroup --system --gid 1001 appgroup \
 && adduser --system --uid 1001 --gid 1001 appuser
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --chown=appuser:appgroup src/ /app/src/
USER appuser
CMD ["uvicorn", "caramello.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Variáveis de ambiente via compose (não baked na imagem):**
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`
- `ENVIRONMENT` (development | production)
- `APP_VERSION` como build arg (padrão do hiring-pipeline)

---

### TS-8: Infraestrutura de testes funcional

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | Tests atuais conectam ao banco de produção (CONCERNS.md). `pytest-asyncio` não está instalado. `conftest.py` está vazio. Sem teste isolado, não há como validar que a fundação funciona. |
| Complexidade | Média |
| Dependências | TS-1 (AsyncSession) — os fixtures de teste dependem de `AsyncSession` isolada |

**Stack mínimo viável (MVP de testes):**

Dependências de dev:
```
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.28        # AsyncClient
sqlalchemy[asyncio]
asyncpg
```

Configuração em `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Fixtures mínimas em `tests/conftest.py`:**

```python
@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(settings.DATABASE_URL_TEST)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await eng.dispose()

@pytest_asyncio.fixture
async def session(engine):
    async with AsyncSession(engine) as s:
        yield s
        await s.rollback()

@pytest_asyncio.fixture
async def client(session):
    app.dependency_overrides[get_session] = lambda: session
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

**O padrão de isolamento correto:** cada teste usa uma `AsyncSession` própria com `rollback()` no teardown — não `drop_all/create_all` por teste (muito lento). Session-scoped `create_all`, function-scoped session com rollback.

**Banco de teste:** `familia_test` (database separado, não o `familia_dev`). Definir `DATABASE_URL_TEST` como variável de ambiente separada.

---

### TS-9: Linting e type-checking configurados

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | `docs/quality_rules.md` exige `ruff` e `mypy`. Ambos estão ausentes do `pyproject.toml` (CONCERNS.md). Fundação sem linting = drift silencioso de qualidade. |
| Complexidade | Baixa |
| Dependências | Nenhuma |

**O que configurar:**
```toml
[dependency-groups]
dev = ["ruff>=0.4", "mypy>=1.10", ...]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "UP"]

[tool.mypy]
python_version = "3.12"
strict = false          # strict é over-engineering para M1
ignore_missing_imports = true
```

`mypy strict = false` para M1 — os modelos SQLModel têm limitações conhecidas com mypy strict que consomem tempo sem valor proporcional em um projeto neste estágio.

---

### TS-10: CORS configurado

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | Sem CORS, o frontend React/Capacitor é bloqueado pelo browser em todos os requests (CONCERNS.md). |
| Complexidade | Mínima |
| Dependências | Nenhuma |

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["*"] em dev, lista explícita em prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### TS-11: Migration Alembic inicial correta

| Atributo | Detalhe |
|----------|---------|
| Porquê esperado | A migration existente foi gerada do modelo errado (com `hashed_password`, `google_id`). Não pode ser base para produção. |
| Complexidade | Baixa — depois de corrigir o DSL |
| Dependências | TS-2 (modelo User correto primeiro) |

**O que fazer:**
- Deletar `alembic/versions/20260104-1044-e667565d64eb-fix_relationships.py`
- Após regenerar modelos do DSL: `alembic revision --autogenerate -m "initial_schema"`
- Convenção de `DB_NAME`: `familia_dev` e `familia_prod` (não `caramello_db`)

---

## Diferenciadores

Features que melhoram a qualidade da fundação mas podem vir depois do M1 ou em fases posteriores sem comprometer a correção técnica.

| Feature | Valor | Quando | Notas |
|---------|-------|--------|-------|
| Health check endpoint (`/health` com DB ping) | Monitoramento de produção | Início do M2 | `GET /health` com `await session.execute(text("SELECT 1"))`. Não é bloqueante para M1 — sem usuários reais ainda. |
| `APP_VERSION` exposto no health check | Rastreabilidade de deploy | Com health check | Build arg `APP_VERSION` injetado via `docker build --build-arg`. Padrão do hiring-pipeline. |
| Structured logging (JSON) | Observabilidade | M2 | `structlog` ou `python-json-logger`. Hoje `print()` basta para dev. |
| Error tracking (Sentry) | Rastreamento de erros em prod | M2 | `sentry-sdk[fastapi]`. |
| `pytest-postgresql` com DatabaseJanitor | Isolamento de teste mais robusto | M2 | Cria e destrói banco real por suite. Para M1, rollback por sessão é suficiente. |
| `mypy strict=True` | Cobertura de tipos completa | Após M1 estabilizar | SQLModel tem incompatibilidades conhecidas com strict; resolve-se gradualmente. |
| SSL no DATABASE_URL em produção | Segurança de conexão | Antes do primeiro deploy em prod | `postgresql+asyncpg://...?ssl=require`. Trivial de adicionar mas sem usuários reais ainda. |
| `include_operations` / `exclude_operations` no fastapi-mcp | Controle fino de tools MCP | Quando houver endpoints internos | Para M1 com apenas endpoints do domínio familia, o default de expor tudo funciona. |
| Rate limiting por IP/usuário | DDoS básico | Nunca para este projeto | 1-5 usuários numa infra pessoal — over-engineering absoluto. |
| Paginação cursor-based | Performance de listas | M2+ | Com 1-5 usuários e famílias pequenas, `LIMIT/OFFSET` simples é suficiente para sempre. |

---

## Anti-Features

Features a deliberadamente NÃO construir no M1. Algumas são arquiteturalmente erradas; outras são over-engineering para este contexto específico.

### AF-1: Autenticação local com senha

**Por quê evitar:** Removida intencionalmente da arquitetura. Keycloak é o único provedor de identidade. Construir qualquer infraestrutura de hash de senha, reset por e-mail, ou verificação de e-mail seria trabalho desperdiçado e contraditório com a decisão registrada.

**Ao invés de:** `UserCreate` com `password` → `idp_sub` extraído do JWT.

---

### AF-2: Middleware global de autenticação

**Por quê evitar:** FastAPI `Depends(get_current_user)` aplicado por router é o padrão canônico. Middleware global para auth em FastAPI cria problemas: não tem acesso fácil a parâmetros de rota, dificulta testes com `dependency_overrides`, e acopla auth ao ciclo de vida da request antes dos validators do Pydantic.

**Ao invés de:** `router = APIRouter(dependencies=[Depends(get_current_user)])` para proteger todo o router de uma vez.

---

### AF-3: Token introspection remota em cada request

**Por quê evitar:** Chamar o endpoint `/introspect` do Keycloak a cada request cria latência e acoplamento de disponibilidade com o Keycloak. RS256 com JWKS cacheado localmente é a abordagem correta — valida assinatura, `exp`, `iss`, `aud` localmente. Não precisa de roundtrip ao Keycloak por request.

**Ao invés de:** `PyJWKClient(cache_keys=True)` + `jwt.decode()` local.

---

### AF-4: Servidor MCP separado (FastMCP standalone)

**Por quê evitar:** `fastapi-mcp` integra via ASGI diretamente na mesma app FastAPI. Um servidor MCP separado dobraria o overhead operacional (segundo processo, segundo port, segunda configuração de auth) sem ganho real para 1-5 usuários e domínios pequenos.

**Ao invés de:** `FastApiMCP(app).mount()` — disponível em `/mcp` na mesma app.

---

### AF-5: Tabela `users` compartilhada entre grupos

**Por quê evitar:** Decisão arquitetural documentada e registrada em `docs/apps-platform.md` §6. Cada grupo é uma ilha completa. O `plataforma-core` foi descartado explicitamente. User vive em `src/caramello/shared/` (cross-domain dentro do monolito do Grupo Família), não em infraestrutura compartilhada.

---

### AF-6: Schemas PostgreSQL por domínio

**Por quê evitar:** Complexidade sem benefício para este porte. Isolamento por convenção de nomenclatura de tabelas (prefixo por domínio: `familia_members`, `financeiro_lancamentos`) é suficiente dentro de um único banco. Documentado em `docs/apps-platform.md` §5.

---

### AF-7: Lógica de negócio inline nos handlers FastAPI

**Por quê evitar:** Handlers que fazem queries + transformações + regras de negócio diretamente no handler não podem ser reusados pelo servidor MCP sem duplicação. `services.py` por domínio é obrigatório, não opcional — especialmente porque MCP é um requisito de M1.

**Ao invés de:**
```python
# ERRADO — lógica inline no handler
@router.post("/families")
async def create_family(data: FamilyCreate, session: AsyncSession = Depends(get_session)):
    family = Family(**data.model_dump())
    session.add(family)
    await session.commit()
    return family

# CORRETO — handler é wrapper fino sobre service
@router.post("/families")
async def create_family(data: FamilyCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await familia_service.create_family(session, owner=user, data=data)
```

---

### AF-8: `response_model=SQLModel_TableClass` direto

**Por quê evitar:** Retornar a table model SQLModel diretamente expõe qualquer campo futuro automaticamente, incluindo campos sensíveis. `docs/security_rules.md` §3 proíbe isso explicitamente. Violado hoje no `familymember_router.py`. Cada entidade precisa de um schema `*Read` separado.

---

## Dependências entre Features

```
TS-1 (asyncpg/AsyncSession)
    └── TS-2 (modelo User correto)
        └── TS-3 (shared/auth.py + JIT provisioning)
            └── TS-4 (estrutura por domínios)
                └── TS-5 (endpoints familia funcionais + protegidos)
                    ├── TS-6 (fastapi-mcp integrado)
                    └── TS-8 (testes integrados)
TS-7 (Docker) — independente, mas pré-requisito para deploy
TS-9 (ruff/mypy) — independente, adicionar cedo
TS-10 (CORS) — independente, trivial
TS-11 (migration) — depende de TS-2, independente de TS-3+
```

**Ordem de implementação sugerida:**
1. TS-9 + TS-10 (triviais, sem dependências — fazer primeiro)
2. TS-1 (desbloqueador de tudo)
3. TS-2 + TS-11 (modelo correto + migration correta em conjunto)
4. TS-4 (reorganizar estrutura enquanto os modelos ainda são poucos)
5. TS-3 (auth — depende de TS-2 e TS-4 no lugar)
6. TS-5 (endpoints — depende de tudo acima)
7. TS-8 (testes — mais eficiente quando a estrutura está estável)
8. TS-6 (MCP — literalmente 3 linhas se TS-5 estiver correto)
9. TS-7 (Docker — last step antes de considerar deployável)

---

## MVP da Fundação

Para que M1 possa ser considerado completo, todos os table stakes (TS-1 a TS-11) devem estar presentes.
Não há table stake que possa ser movida para "depois" sem comprometer a correção técnica da fundação.

Os diferenciadores (health check, structured logging, SSL em prod, etc.) podem entrar no início do M2
como "polimento de infra" antes de começar o domínio financeiro.

---

## Gaps a Endereçar em Fases Subsequentes

- **Decisão sobre o DSL generator:** TS-4 assume que o gerador evoluirá para outputar em `domains/{domain}/`. Para M1, o domínio `familia` pode ser escrito manualmente. A evolução do generator é um item de M1 mas pode ser o último — após o padrão estar estabelecido manualmente, o generator replica esse padrão.
- **Refresh token handling:** fastapi-mcp + Keycloak com tokens de curta duração — o cliente MCP precisa renovar tokens. Não é problema do M1 (agentes podem usar tokens de longa duração em dev), mas será relevante em M2+ com uso real.
- **Filtros MCP por tag:** quando houver mais domínios, `include_tags=["familia"]` no `FastApiMCP` evita que todos os endpoints de todos os domínios virem tools por padrão. Arquitetar com tags desde o início.

---

## Fontes

- FastAPI official docs: security, dependencies, bigger-applications — https://fastapi.tiangolo.com/
- Context7 FastAPI (/fastapi/fastapi) — HIGH confidence
- fastapi-best-practices (zhanymkanov, Netflix Dispatch-inspired): https://github.com/zhanymkanov/fastapi-best-practices
- fastapi-mcp official docs + README: https://github.com/tadata-org/fastapi_mcp, https://fastapi-mcp.tadata.com/advanced/auth
- Keycloak + PyJWT + FastAPI (skycloak.io): https://skycloak.io/blog/keycloak-fastapi-python-api-authentication/
- FastAPI async SQLAlchemy pytest (praciano.com.br): https://praciano.com.br/fastapi-and-async-sqlalchemy-20-with-pytest-done-right.html
- FastAPI Docker multi-stage best practices: https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/
- docs/apps-platform.md §3, §5, §6, §7 — normativo para decisões arquiteturais do projeto
- .planning/codebase/CONCERNS.md — mapeamento dos gaps críticos (G1, G2, G3)
