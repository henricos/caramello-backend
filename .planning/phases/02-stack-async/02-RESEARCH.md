# Phase 2: Stack Async - Research

**Researched:** 2026-05-25
**Domain:** Python async stack — asyncpg, SQLAlchemy async, SQLModel async, Alembic async
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Driver e dependências**
- D-01: Remover `psycopg2-binary` das dependências. Adicionar `asyncpg` via `uv add asyncpg`. Verificar que `uv.lock` reflete a remoção — `grep psycopg2 uv.lock` deve retornar vazio após a troca.
- D-02: Atualizar o SQLModel para a versão mais recente (`uv add sqlmodel` sem pin de versão). O researcher deve verificar o changelog da versão instalada para identificar breaking changes antes de planejar o migration path.

**Módulo de database**
- D-03: Criar `src/caramello/shared/database.py` como novo módulo de session — não migrar in-place em `database/session.py`. O arquivo `database/session.py` é removido. Esta fase cria o diretório `shared/` que a Phase 3 vai expandir com `auth.py`.
- D-04: `shared/database.py` expõe: `engine` (via `create_async_engine`), `async_session_factory` (via `async_sessionmaker`), e `get_session()` como generator assíncrono usando `AsyncGenerator[AsyncSession, None]` — compatível com `Depends()` do FastAPI.
- D-05: `create_db_and_tables()` é removida. O schema é gerenciado exclusivamente pelo Alembic.

**Alembic async**
- D-06: `alembic/env.py` migrado para usar `asyncio.run()` + `async_engine_from_config` com `poolclass=NullPool`. Modo offline (`run_migrations_offline`) mantém comportamento síncrono.
- D-07: `alembic/env.py` mantém o import `from caramello.models import *` para autogenerate.

**DSL generator — escopo mínimo async**
- D-08: O generator (`scripts/generate_code.py`) tem seu template de router atualizado para emitir: `async def`, `AsyncSession`, `await session.exec(select(...))`, e import de `from caramello.shared.database import get_session`.
- D-09: Campo `domain` no YAML e mudança de output path para `domains/{domain}/` NÃO entram nesta fase.
- D-10: Após atualizar o generator, rodar `bin/generate_code` para regenerar os 4 routers. Código gerado deve passar em `ruff check src/` e `mypy src/` sem erros.

**Routers existentes**
- D-11: Os 4 routers em `src/caramello/api/generated/` são regenerados com o generator atualizado. Ao final, nenhum arquivo importa `Session` síncrona ou `create_engine`.
- D-12: `src/caramello/main.py` é atualizado para remover imports de `database.session`.

**Compatibilidade com ruff/mypy**
- D-13: O generator emite código que passa em ruff/mypy nativamente. Com `AsyncSession`, tipos devem ser anotados explicitamente (`AsyncGenerator[AsyncSession, None]` no `get_session`).

### Claude's Discretion

Nenhuma área de discrição explicitamente marcada nesta fase.

### Deferred Ideas (OUT OF SCOPE)

- Campo `domain:` no YAML do DSL generator e output para `domains/{domain}/` — escopo da Phase 3
- `GET /health` com ping ao banco (OPS-01) — v2 requirements, milestone posterior
- SSL no `DATABASE_URL` em produção (`sslmode=require`) — Phase 5 deploy
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Todas as queries ao banco são executadas de forma assíncrona via `asyncpg` — o event loop não é bloqueado em nenhuma operação de I/O de banco | Verificado: `asyncpg` 0.31.0 disponível no registry; `create_async_engine` + `AsyncSession` disponíveis em SQLAlchemy 2.0.43 (já instalado); `sqlmodel.ext.asyncio.session.AsyncSession` funciona com `await session.exec()` já em SQLModel 0.0.25 |
</phase_requirements>

---

## Summary

A Phase 2 migra o driver de banco de `psycopg2-binary` (síncrono) para `asyncpg` (assíncrono) e reconstrói toda a camada de acesso ao banco com `AsyncSession` + `async_sessionmaker`. O projeto já tem SQLAlchemy 2.0.43 instalado, que inclui suporte async completo. O SQLModel 0.0.25 já suporta `AsyncSession` com `await session.exec()` — `session.execute()` foi marcado como deprecated na versão mais recente (0.0.38), confirmando `session.exec()` como API canônica.

A principal mudança estrutural é a criação de `src/caramello/shared/database.py` substituindo `src/caramello/database/session.py`, com `create_async_engine` e `async_sessionmaker`. O Alembic precisa de migração no `env.py` para usar `async_engine_from_config` + `asyncio.run()`, mantendo o modo offline síncrono. O `DATABASE_URL` em `config.py` precisa ter o prefixo alterado de `postgresql://` para `postgresql+asyncpg://`. O DSL generator recebe atualização mínima no template de router para emitir `async def` e `await session.exec()`.

Dois pontos críticos identificados: (1) `expire_on_commit=False` é obrigatório no `async_sessionmaker` para evitar lazy loading errors em contextos async após commit; (2) o type hint correto para o `get_session()` é `AsyncGenerator[AsyncSession, None]` onde `AsyncSession` é importado de `sqlmodel.ext.asyncio.session` — não de `sqlalchemy.ext.asyncio` diretamente, para manter a API `exec()` do SQLModel.

**Primary recommendation:** `await session.exec()` é o padrão correto para routers — já funciona em SQLModel 0.0.25 e é a API canônica em 0.0.38 (onde `session.execute()` foi marcado deprecated).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Driver de banco (asyncpg) | API / Backend | — | Dependência de infraestrutura; sem camada intermediária |
| Session async (`shared/database.py`) | API / Backend | — | Módulo de infraestrutura interna; exposto via `Depends()` |
| Alembic async env.py | API / Backend | — | Ferramenta de schema; executa no mesmo processo que a app |
| DSL generator template | API / Backend | — | Geração de código para routers FastAPI |
| URL scheme (`postgresql+asyncpg://`) | API / Backend | — | Construído em `config.py` no startup |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncpg | 0.31.0 | Driver PostgreSQL async | Driver nativo async para PostgreSQL; suportado pelo SQLAlchemy como dialeto `postgresql+asyncpg` |
| SQLModel | 0.0.38 (upgrade de 0.0.25) | ORM + Pydantic + FastAPI | `AsyncSession` com `session.exec()` — API canônica confirmada; `execute()` deprecated em 0.0.38 |
| SQLAlchemy (já instalado) | 2.0.43 | Base async engine | `create_async_engine`, `async_sessionmaker`, `AsyncSession` — já no lockfile |
| sqlmodel.ext.asyncio.session | (parte do SQLModel) | `AsyncSession` com API `exec()` | Import path canônico para manter `session.exec()` em vez do SQLAlchemy nativo |

[VERIFIED: npm registry / uv pip index] — asyncpg 0.31.0 é a versão mais recente disponível
[VERIFIED: uv pip index] — SQLModel 0.0.38 é a versão mais recente disponível
[VERIFIED: instalado localmente] — SQLAlchemy 2.0.43 já presente no ambiente

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| greenlet | 3.2.4 (já no lock) | Permite SQLModel async usar greenlet_spawn | Já instalado como dependência do SQLAlchemy; não requer instalação adicional |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sqlmodel.ext.asyncio.session.AsyncSession` | `sqlalchemy.ext.asyncio.AsyncSession` | O SQLAlchemy nativo não tem `session.exec()` — usaria `session.execute()` + `.scalars()`. Usar o SQLModel AsyncSession mantém a API consistente |
| `async_sessionmaker` (SQLAlchemy 2.0) | `sessionmaker(class_=AsyncSession)` padrão antigo | `async_sessionmaker` é o padrão moderno; o antigo ainda funciona mas é desencorajado |

**Installation:**
```bash
uv add asyncpg
uv add "sqlmodel>=0.0.38"
uv remove psycopg2-binary
```

**Version verification:**
```bash
# Versões confirmadas em 2026-05-25
uv run pip index versions asyncpg    # → 0.31.0 latest
uv run pip index versions sqlmodel   # → 0.0.38 latest
```

---

## Architecture Patterns

### System Architecture Diagram

```
.env (DB_HOST/PORT/USER/PASSWORD/DB_NAME)
         │
         ▼
src/caramello/core/config.py
  Settings.model_post_init()
  → DATABASE_URL = "postgresql+asyncpg://..."
         │
         ▼
src/caramello/shared/database.py
  create_async_engine(DATABASE_URL)
  async_sessionmaker(..., expire_on_commit=False)
  get_session() → AsyncGenerator[AsyncSession, None]
         │
         ├──── FastAPI Depends() → routers (CRUD async)
         │
         └──── alembic/env.py
                asyncio.run(run_async_migrations())
                async_engine_from_config(..., NullPool)
                connection.run_sync(do_run_migrations)
```

### Recommended Project Structure

```
src/caramello/
├── shared/
│   ├── __init__.py
│   └── database.py          # engine + async_session_factory + get_session()
├── core/
│   └── config.py            # Settings — URL prefix muda para postgresql+asyncpg
├── api/
│   └── generated/           # Regenerado pelo DSL generator atualizado
│       ├── user_router.py   # async def + await session.exec()
│       ├── family_router.py
│       ├── familymember_router.py
│       └── familyinvitation_router.py
└── models/                  # Não muda nesta fase
```

```
alembic/
└── env.py                   # run_migrations_online → asyncio.run()
```

### Pattern 1: shared/database.py — Engine e Session Async

**What:** Módulo central que expõe engine, factory e dependency para routers.
**When to use:** Único ponto de criação do engine — todos os routers importam `get_session` daqui.

```python
# Source: https://deepwiki.com/fastapi/sqlmodel/5.4-async-support
# Source: https://github.com/fastapi/sqlmodel/blob/main/sqlmodel/ext/asyncio/session.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.core.config import settings

engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # OBRIGATÓRIO: evita lazy loading após commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

**ATENÇÃO — import de AsyncSession:** Usar `from sqlmodel.ext.asyncio.session import AsyncSession`, NÃO `from sqlalchemy.ext.asyncio import AsyncSession`. O import do SQLModel é necessário para que `session.exec()` esteja disponível como método async.

### Pattern 2: config.py — Mudança de prefixo de URL

**What:** O `DATABASE_URL` precisa de prefixo `postgresql+asyncpg://` em vez de `postgresql://`.
**When to use:** Alterar apenas a linha de construção em `model_post_init`.

```python
# Atual (sync):
self.DATABASE_URL = f"postgresql://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"

# Async:
self.DATABASE_URL = f"postgresql+asyncpg://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
```

### Pattern 3: alembic/env.py — Modo online async

**What:** `run_migrations_online` migrado para usar `asyncio.run()` + `async_engine_from_config`.
**When to use:** Apenas o modo online vira async; `run_migrations_offline` mantém comportamento síncrono.

```python
# Source: https://alembic.sqlalchemy.org/en/latest/cookbook.html
import asyncio

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context

# [imports de models e metadata permanecem iguais]

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

**Modo offline permanece síncrono** — `run_migrations_offline()` não muda.

### Pattern 4: Router gerado pelo DSL — template async

**What:** Template que o generator emite para cada entidade (não-link).
**When to use:** `generate_router()` em `scripts/generate_code.py` — substituir o template atual.

```python
# Exemplo para entidade User (gerado pelo DSL, não editar diretamente)
from collections.abc import AsyncGenerator
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.user import User, UserRead, UserCreate, UserUpdate

router = APIRouter(prefix="/user", tags=["User"])

@router.post("/", response_model=UserRead)
async def create_user(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    db_obj = User.model_validate(user_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

@router.get("/", response_model=list[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select(User).offset(offset).limit(limit))
    return result.all()

@router.get("/{uuid}", response_model=UserRead)
async def read_user(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    user = result.first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{uuid}", response_model=UserRead)
async def update_user(
    uuid: UUID, user_in: UserUpdate, session: AsyncSession = Depends(get_session)
):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    hero_data = user_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

@router.delete("/{uuid}")
async def delete_user(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select(User).where(User.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(db_obj)
    await session.commit()
    return {"ok": True}
```

**Diferenças críticas em relação ao template sync atual:**
1. `async def` em todos os endpoints
2. `from sqlmodel.ext.asyncio.session import AsyncSession` (não `from sqlmodel import Session`)
3. `from caramello.shared.database import get_session` (path novo)
4. `result = await session.exec(statement)` + `result.first()` / `result.all()` — dois passos
5. `await session.commit()`, `await session.refresh()`, `await session.delete()`
6. Sem import de `Session` ou `create_engine` do sqlmodel

### Anti-Patterns to Avoid

- **Usar `from sqlalchemy.ext.asyncio import AsyncSession` nos routers:** Perde o método `exec()` do SQLModel — seria necessário `session.execute()` + `.scalars().all()` em todos os lugares.
- **Usar `session.exec()` sem await:** `exec` em `AsyncSession` do SQLModel é uma coroutine — omitir `await` retorna um objeto coroutine não executado.
- **`expire_on_commit=True` (padrão):** Após `await session.commit()`, objetos expiram e acessar atributos dispara lazy loading síncrono — erro em contexto async. Sempre `expire_on_commit=False`.
- **Não chamar `await connectable.dispose()` no env.py:** Pode deixar conexões abertas no pool após migrations.
- **Engine global criado no import time sem .env:** O `settings` é instanciado no import; se `.env` não estiver presente ao iniciar, o engine falha. Padrão existente é mantido — sem mudança aqui.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pool async para migrations | Não criar pool customizado | `NullPool` nativo do SQLAlchemy | Migrations são operações únicas — pool persistente causa lock no Alembic |
| Conversão de resultado de exec | Não fazer `.scalars()` manualmente | `await session.exec()` do SQLModel | `session.exec()` já retorna `ScalarResult` — não precisa de `.scalars()` |
| Gerenciamento de lifecycle do engine | Não fechar engine manualmente nos routers | `async_session_factory as session` (context manager) | Sessão é fechada automaticamente ao sair do bloco `async with` |
| URL do banco para migrations | Não hardcodar URL no alembic.ini | Injetar via `configuration["sqlalchemy.url"] = settings.DATABASE_URL` | Já é o padrão atual — manter |

**Key insight:** SQLModel's `AsyncSession.exec()` elimina o boilerplate de `.scalars()` que seria necessário com SQLAlchemy puro — essa é a razão de usar o import de `sqlmodel.ext.asyncio.session` e não de `sqlalchemy.ext.asyncio`.

---

## Common Pitfalls

### Pitfall 1: Import errado de AsyncSession

**What goes wrong:** Importar `AsyncSession` de `sqlalchemy.ext.asyncio` faz com que `session.exec()` não exista — apenas `session.execute()` está disponível, que retorna `Row` objects precisando de `.scalars()`.
**Why it happens:** Há dois `AsyncSession`: um do SQLAlchemy puro e um do SQLModel que sobrescreve `exec()`. São classes diferentes.
**How to avoid:** Sempre `from sqlmodel.ext.asyncio.session import AsyncSession` em qualquer arquivo que usa `session.exec()`.
**Warning signs:** `AttributeError: 'coroutine' object has no attribute 'all'` ao tentar `session.exec(...).all()` sem await; ou `'AsyncSession' object has no attribute 'exec'`.

### Pitfall 2: Esquecer await em session.exec()

**What goes wrong:** `session.exec(select(User))` retorna uma coroutine não executada; chamar `.first()` ou `.all()` nela dá `AttributeError`.
**Why it happens:** Em SQLModel sync, `session.exec()` é síncrono. Na versão async, é `async def` e precisa de `await`.
**How to avoid:** Sempre `result = await session.exec(statement)` → depois `result.first()` ou `result.all()`.
**Warning signs:** `AttributeError: 'coroutine' object has no attribute 'first'` ou `'coroutine' object has no attribute 'all'`.

### Pitfall 3: expire_on_commit padrão

**What goes wrong:** Após `await session.commit()`, objetos SQLModel expiram (padrão do SQLAlchemy). O próximo acesso a um atributo tenta carregar do banco de forma lazy — o que é síncrono e lança `MissingGreenlet: greenlet_spawn has not been called`.
**Why it happens:** Lazy loading de SQLAlchemy não funciona em contexto async sem greenlet ativo.
**How to avoid:** `async_sessionmaker(..., expire_on_commit=False)` em `shared/database.py`. Ou chamar `await session.refresh(obj)` explicitamente antes de retornar o objeto.
**Warning signs:** `sqlalchemy.exc.MissingGreenlet` após commit ao acessar atributos de um objeto.

### Pitfall 4: URL sem prefixo +asyncpg

**What goes wrong:** `create_async_engine("postgresql://...")` levanta `ArgumentError: Could not parse rfc1738 URL from string`.
**Why it happens:** O prefixo `postgresql://` resolve para psycopg2 (sync). O async engine exige `postgresql+asyncpg://` explicitamente.
**How to avoid:** Alterar `model_post_init` em `config.py` para construir `postgresql+asyncpg://`.
**Warning signs:** Erro de URL no startup da aplicação.

### Pitfall 5: alembic env.py sem await connectable.dispose()

**What goes wrong:** O pool de conexões do asyncpg não é fechado após as migrations, causando warnings de "connection was not properly closed" ou hang.
**Why it happens:** `async_engine_from_config` cria um engine com pool; `dispose()` fecha todas as conexões.
**How to avoid:** Sempre `await connectable.dispose()` ao final de `run_async_migrations()`.
**Warning signs:** Warnings de "asyncpg" sobre conexões não fechadas no output do alembic.

### Pitfall 6: SQLModel upgrade — Pydantic v1 removido em 0.0.31

**What goes wrong:** O projeto usa Pydantic v2 (confirmado em pyproject.toml — `pydantic` sem pin, lockfile tem Pydantic 2.x). Não há impacto.
**Why it happens:** Breaking change em 0.0.31 remove suporte a Pydantic v1.
**How to avoid:** Confirmar que Pydantic 2.x está instalado (já está — verificado).
**Warning signs:** Erros de import de `pydantic.v1` se o projeto ainda usasse Pydantic v1.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `sessionmaker(class_=AsyncSession)` | `async_sessionmaker(...)` | SQLAlchemy 2.0 | `async_sessionmaker` é type-safe e explícito para async |
| `session.execute()` em SQLModel | `session.exec()` (deprecated) | SQLModel 0.0.38 | `execute()` marcado deprecated — confirma `exec()` como API canônica |
| `engine_from_config` no Alembic | `async_engine_from_config` + `asyncio.run()` | Alembic suporte async há anos | Migrations não travam o event loop |

**Deprecated/outdated:**
- `session.execute()` no SQLModel: não é erro, mas emite `DeprecationWarning` a partir de 0.0.38. Usar `session.exec()`.
- `sessionmaker(class_=AsyncSession)` padrão antigo: funciona, mas `async_sessionmaker` é o padrão SQLAlchemy 2.0.

---

## Breaking Changes: SQLModel 0.0.25 → 0.0.38

[VERIFIED: sqlmodel.tiangolo.com/release-notes]

| Versão | Breaking Change | Impacto neste projeto |
|--------|----------------|----------------------|
| 0.0.31 | Drop suporte a Pydantic v1 | **Nenhum** — projeto já usa Pydantic v2 (confirmado em lockfile) |
| 0.0.35 | Drop suporte a Python 3.9 | **Nenhum** — pyproject.toml requer `>=3.10`; runtime é Python 3.12.3 |
| 0.0.30 | Drop suporte a Python 3.8 | **Nenhum** — idem acima |

**Conclusão:** O upgrade de 0.0.25 → 0.0.38 não tem breaking changes para este projeto. O upgrade é seguro e recomendado.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `async_sessionmaker` é o padrão recomendado no SQLAlchemy 2.0 (vs `sessionmaker(class_=AsyncSession)`) | Standard Stack | Baixo — ambos funcionam; A1 é preferência de estilo |
| A2 | `await session.exec(statement)` retorna objeto com `.all()` e `.first()` diretamente (sem `.scalars()` adicional) | Code Examples | Médio — verificado em docs e DeepWiki, mas não testado ao vivo pois asyncpg não está instalado |

**Nota sobre A2:** Confirmado via inspeção da signature de `AsyncSession.exec` no SQLModel 0.0.25 instalado localmente — retorna `ScalarResult[T]` ou `TupleResult[T]` conforme o tipo de statement. `ScalarResult` tem `.all()` e `.first()` diretamente.

---

## Open Questions

1. **mypy com `AsyncSession` do SQLModel**
   - O que sabemos: mypy com `disallow_untyped_defs = true` (configuração atual) vai verificar o tipo de retorno de `get_session()`. O type hint `AsyncGenerator[AsyncSession, None]` é necessário.
   - O que é incerto: se mypy levanta erros específicos com a `AsyncSession` do SQLModel (há issues históricos no GitHub sobre isso). A configuração atual tem `ignore_missing_imports = true` que pode mascarar problemas.
   - Recomendação: O planner deve incluir `uv run mypy src/` como critério de aceitação explícito após o Wave que cria `shared/database.py`, antes de continuar.

2. **asyncpg-stubs para mypy**
   - O que sabemos: `asyncpg-stubs` não está instalado. `ignore_missing_imports = true` deve mascarar erros de stub.
   - O que é incerto: se a ausência de stubs causa erros em algum path de código que passa por asyncpg.
   - Recomendação: Não instalar por padrão; se mypy reclamar, adicionar `asyncpg-stubs` como dev dependency.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| asyncpg | Driver banco async | ✗ (não instalado) | — | Instalar via `uv add asyncpg` |
| SQLModel 0.0.38 | API `exec()` + sem breaking changes | ✗ (0.0.25 instalado) | 0.0.38 disponível | Funciona com 0.0.25 também — upgrade é recomendado |
| SQLAlchemy 2.0+ async | `create_async_engine`, `async_sessionmaker` | ✓ | 2.0.43 | — |
| greenlet | SQLModel async internals | ✓ (no lockfile) | 3.2.4 | — |
| Python 3.12 | Runtime | ✓ | 3.12.3 | — |
| uv | Package manager | ✓ | 0.11.11 | — |
| PostgreSQL (banco) | Alembic + runtime | ✗ (não testado no ambiente de pesquisa) | — | Banco externo via .env |

**Missing dependencies with no fallback:**
- `asyncpg` — blocking para execução. Deve ser instalado no Wave 0 do plano.

**Missing dependencies with fallback:**
- `sqlmodel 0.0.38` — 0.0.25 funciona tecnicamente para esta fase. Upgrade recomendado por D-02.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.1 |
| Config file | none — sem `[tool.pytest.ini_options]` em pyproject.toml |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/` |

### Observação sobre testes nesta fase

Os arquivos de teste existentes (`tests/test_api/test_user_router.py`, `tests/test_services/test_user_service.py`) estão vazios (0 linhas). A Phase 2 não cria testes — o foco é na migração de infraestrutura. A validação desta fase é estrutural: verificar que o código produzido passa em `ruff` e `mypy`, que `alembic upgrade head` conclui sem erros, e que `grep -r "create_engine" src/` retorna vazio.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `grep -r "create_engine" src/` retorna vazio | smoke (grep) | `grep -r "create_engine" src/` | ❌ Wave 0 (verificação manual no critério de sucesso) |
| INFRA-01 | `shared/database.py` usa `AsyncSession` | smoke (grep) | `grep "AsyncSession" src/caramello/shared/database.py` | ❌ Wave 0 |
| INFRA-01 | `alembic upgrade head` conclui sem travar | integration (manual) | `uv run alembic upgrade head` | N/A — requer banco |
| INFRA-01 | Routers gerados usam `async def` | smoke (grep) | `grep -r "async def" src/caramello/api/generated/` | ❌ Wave 0 |
| INFRA-01 | `ruff check src/` passa | linting | `uv run ruff check src/` | ✅ (ruff instalado) |
| INFRA-01 | `mypy src/` passa | type-check | `uv run mypy src/` | ✅ (mypy instalado) |

### Sampling Rate
- **Por tarefa commit:** `uv run ruff check src/ && uv run mypy src/`
- **Por wave merge:** `uv run ruff check src/ && uv run mypy src/ && grep -r "create_engine" src/` (deve retornar vazio)
- **Phase gate:** Todos os critérios acima + `alembic upgrade head` manual antes de `/gsd-verify-work`

### Wave 0 Gaps
- Nenhum arquivo de teste novo precisa ser criado nesta fase. Os testes existentes estão vazios por design — serão preenchidos na Phase 5.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | não | Fora de escopo — Phase 3 |
| V3 Session Management | não | Fora de escopo — Phase 3 |
| V4 Access Control | não | Fora de escopo — Phase 3 |
| V5 Input Validation | sim (mantido) | Pydantic via SQLModel — não muda |
| V6 Cryptography | não | Sem operações criptográficas nesta fase |

### Known Threat Patterns for async stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Connection string leakage via logs | Information Disclosure | `echo=False` em `create_async_engine` em produção (default); não logar `DATABASE_URL` |
| SQL injection via ORM | Tampering | SQLModel/SQLAlchemy usa queries parametrizadas — não muda |

---

## Project Constraints (from CLAUDE.md)

- **Stack obrigatório:** Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL — SQLite explicitamente não suportado
- **Código gerado:** arquivos em `src/caramello/api/generated/` e `src/caramello/models/` não devem ser editados diretamente — editar generator e regenerar
- **ruff + mypy:** todo código deve passar sem erros — `pyproject.toml` exclui `api/generated/` e `models/` do check, mas `shared/database.py` está no escopo
- **DSL first:** atualizar `scripts/generate_code.py` e rodar `bin/generate_code` — nunca editar routers diretamente
- **Idioma:** código e configs em inglês; commits e documentação em pt-BR

---

## Sources

### Primary (HIGH confidence)
- [sqlmodel.tiangolo.com/release-notes](https://sqlmodel.tiangolo.com/release-notes) — breaking changes 0.0.25→0.0.38 verificados
- [alembic.sqlalchemy.org/en/latest/cookbook.html](https://alembic.sqlalchemy.org/en/latest/cookbook.html) — padrão async env.py com `async_engine_from_config` + `asyncio.run()`
- [github.com/fastapi/sqlmodel/blob/main/sqlmodel/ext/asyncio/session.py](https://github.com/fastapi/sqlmodel/blob/main/sqlmodel/ext/asyncio/session.py) — implementação de `exec()` como `async def`; `execute()` como deprecated
- Verificação local: `uv run python -c "from sqlmodel.ext.asyncio.session import AsyncSession; import asyncio; print(asyncio.iscoroutinefunction(AsyncSession.exec))"` → `True`
- Verificação local: `uv run pip index versions sqlmodel` → `0.0.38 latest`; `asyncpg` → `0.31.0 latest`

### Secondary (MEDIUM confidence)
- [deepwiki.com/fastapi/sqlmodel/5.4-async-support](https://deepwiki.com/fastapi/sqlmodel/5.4-async-support) — `session.exec()` vs `session.execute()` — verificado contra source no GitHub
- [deepwiki.com/fastapi/sqlmodel/2.4-session-and-asyncsession](https://deepwiki.com/fastapi/sqlmodel/2.4-session-and-asyncsession) — implementação interna com greenlet_spawn

### Tertiary (LOW confidence)
- [testdriven.io/blog/fastapi-sqlmodel/](https://testdriven.io/blog/fastapi-sqlmodel/) — padrão `expire_on_commit=False` — cross-verificado com docs SQLAlchemy
- [daniel.feldroy.com/posts/til-2025-08-using-sqlmodel-asynchronously-with-fastapi-and-air-with-postgresql](https://daniel.feldroy.com/posts/til-2025-08-using-sqlmodel-asynchronously-with-fastapi-and-air-with-postgresql) — exemplo prático com asyncpg

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — versões verificadas via `uv pip index`; imports verificados localmente
- Architecture: HIGH — padrão do Alembic verificado em docs oficiais; SQLModel AsyncSession verificado em source
- Pitfalls: HIGH — verificados via inspeção de código-fonte e docs; pitfall de `expire_on_commit` é documentado no SQLAlchemy

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (stack estável; asyncpg e SQLModel têm releases frequentes mas API async é estável)
