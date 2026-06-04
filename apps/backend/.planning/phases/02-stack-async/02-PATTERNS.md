# Phase 2: Stack Async - Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 5 files (new/modified)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/caramello/shared/database.py` (new) | service/infrastructure | request-response | `src/caramello/database/session.py` | role-match (sync → async rewrite) |
| `src/caramello/core/config.py` (modify) | config | — | `src/caramello/core/config.py` (si mesmo) | exact |
| `alembic/env.py` (modify) | config/migration | batch | `alembic/env.py` (si mesmo) | exact |
| `scripts/generate_code.py` (modify) | utility/generator | transform | `scripts/generate_code.py` (si mesmo) | exact |
| `src/caramello/main.py` (modify) | config/entrypoint | request-response | `src/caramello/main.py` (si mesmo) | exact |

> Nota: Os 4 routers em `src/caramello/api/generated/` são artefatos de saída do generator — não são editados diretamente.
> O diretório `src/caramello/shared/` e `src/caramello/shared/__init__.py` precisam ser criados.

---

## Pattern Assignments

### `src/caramello/shared/database.py` (novo — infrastructure, request-response)

**Analog:** `src/caramello/database/session.py`

**Analog — imports e estrutura atual** (linhas 1-17):
```python
# ATUAL (sync) — src/caramello/database/session.py
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from caramello.core.config import settings

engine = create_engine(settings.DATABASE_URL)  # type: ignore[arg-type]


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

**Padrão alvo (async) — substituição completa:**
```python
# NOVO — src/caramello/shared/database.py
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
    expire_on_commit=False,  # OBRIGATÓRIO: evita MissingGreenlet após commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

**Pontos críticos de diferença:**
- `create_engine` → `create_async_engine`
- `Session` (sqlmodel) → `AsyncSession` (sqlmodel.ext.asyncio.session — NÃO sqlalchemy.ext.asyncio)
- `Generator[Session, None, None]` → `AsyncGenerator[AsyncSession, None]`
- `async_sessionmaker` com `expire_on_commit=False` obrigatório
- `create_db_and_tables()` **removida** — schema gerenciado pelo Alembic (D-05)
- O `type: ignore[arg-type]` do engine atual não é necessário com `str(settings.DATABASE_URL)` e `create_async_engine`

---

### `src/caramello/core/config.py` (modificação pontual)

**Analog:** `src/caramello/core/config.py` (si mesmo)

**Trecho a modificar — model_post_init** (linhas 28-34):
```python
# ATUAL (linha 33):
self.DATABASE_URL = (
    f"postgresql://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
)

# NOVO (substituir apenas o prefixo):
self.DATABASE_URL = (
    f"postgresql+asyncpg://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
)
```

**Tudo mais permanece idêntico** — estrutura `BaseSettings`, campos `DB_*`, `CORS_ORIGINS`, `model_config`, e o singleton `settings = Settings()` na linha 37 não mudam.

---

### `alembic/env.py` (modificação — modo online vira async)

**Analog:** `alembic/env.py` (si mesmo)

**Bloco de imports atual** (linhas 1-7) — adicionar imports async:
```python
# ATUAL:
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# NOVO (substituir apenas a linha de engine_from_config e adicionar asyncio):
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context
```

**Bloco que NÃO muda** (linhas 18-23) — manter exatamente:
```python
from sqlmodel import SQLModel
from caramello.core.config import settings
from caramello.models import *  # Import all models for autogenerate

target_metadata = SQLModel.metadata
```

**`run_migrations_offline()` — NÃO muda** (linhas 31-52): manter comportamento síncrono idêntico ao atual.

**`run_migrations_online()` — substituição completa** (linhas 55-82):
```python
# ATUAL (sync):
def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

# NOVO (async):
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
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

**Bloco condicional no final** (linhas 79-82) — NÃO muda:
```python
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### `scripts/generate_code.py` — função `generate_router()` (modificação)

**Analog:** `scripts/generate_code.py` (si mesmo)

**Função `generate_router()` atual** (linhas 256-320) — substituir o template f-string por versão async:

```python
# ATUAL — linhas 261-320 (template da string retornada):
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlmodel import Session, select
# from typing import List
# from uuid import UUID
# from caramello.database.session import get_session
# ...
# def create_{var_name}(..., session: Session = Depends(get_session)):
#     ...
#     session.commit()
#     session.refresh(db_obj)
#     ...

# NOVO — template async (substituição da string retornada por generate_router):
def generate_router(entity_data: Dict[str, Any]) -> str:
    name = entity_data['name']
    var_name = name.lower()
    table_name = entity_data['table_name']

    return f"""from collections.abc import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from typing import AsyncGenerator
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.{var_name} import {name}, {name}Read, {name}Create, {name}Update

router = APIRouter(prefix="/{table_name}", tags=["{name}"])


@router.post("/", response_model={name}Read)
async def create_{var_name}({var_name}_in: {name}Create, session: AsyncSession = Depends(get_session)):
    db_obj = {name}.model_validate({var_name}_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[{name}Read])
async def read_{var_name}s(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select({name}).offset(offset).limit(limit))
    return result.all()


@router.get("/{{uuid}}", response_model={name}Read)
async def read_{var_name}(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    {var_name} = result.first()
    if not {var_name}:
        raise HTTPException(status_code=404, detail="{name} not found")
    return {var_name}


@router.patch("/{{uuid}}", response_model={name}Read)
async def update_{var_name}(
    uuid: UUID, {var_name}_in: {name}Update, session: AsyncSession = Depends(get_session)
):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")
    hero_data = {var_name}_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{{uuid}}")
async def delete_{var_name}(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")
    await session.delete(db_obj)
    await session.commit()
    return {{"ok": True}}
"""
```

**Diferenças críticas em relação ao template sync:**
1. `from sqlmodel import Session, select` → `from sqlmodel import select` + import separado de `AsyncSession`
2. `from caramello.database.session import get_session` → `from caramello.shared.database import get_session`
3. `from typing import List` + `List[{name}Read]` → `list[{name}Read]` nativo (Python 3.10+)
4. `def` → `async def` em todos os endpoints
5. `session.exec(...)` → `result = await session.exec(...)` + `result.first()` / `result.all()` em dois passos
6. `session.commit()` → `await session.commit()`
7. `session.refresh(db_obj)` → `await session.refresh(db_obj)`
8. `session.delete(db_obj)` → `await session.delete(db_obj)`

**Resto do arquivo `generate_code.py`** — `generate_models()`, `generate_test()`, `load_yaml()`, `map_type_to_python()`, `get_field_definition()`, `generate_relationships()`, `main()` e constantes de path **não mudam nesta fase**.

---

### `src/caramello/main.py` (modificação mínima)

**Analog:** `src/caramello/main.py` (si mesmo)

**Verificação necessária** (linhas 1-36): o arquivo atual **não importa** `database.session` diretamente nem chama `create_db_and_tables()`. Os imports na linha 4-9 são apenas dos routers gerados. Após a regeneração dos routers (que passarão a importar de `shared.database`), `main.py` não precisa de alteração de imports.

**Único cenário de mudança:** se no futuro for necessário adicionar um lifespan event (startup/shutdown) para o engine async — mas isso está fora de escopo desta fase.

**Estado atual que deve ser preservado** (linhas 1-36):
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
# ... CORS middleware e include_router permanecem idênticos
```

---

## Shared Patterns

### Padrão de imports async — aplicar a `shared/database.py` e routers gerados

**Fonte:** RESEARCH.md Pattern 1 + validação local do projeto
**Aplicar a:** `src/caramello/shared/database.py`

```python
# Import de AsyncSession — SEMPRE do sqlmodel, nunca do sqlalchemy diretamente
from sqlmodel.ext.asyncio.session import AsyncSession
# Motivo: AsyncSession do SQLModel sobrescreve exec() como async;
# o do SQLAlchemy puro não tem exec() — obrigaria a usar execute() + .scalars()

# Import do engine e factory — do sqlalchemy (não do sqlmodel)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Type hint do generator — necessário para mypy com disallow_untyped_defs = true
from collections.abc import AsyncGenerator
```

### Padrão de qualidade (ruff + mypy)

**Fonte:** `pyproject.toml` linhas 46-71
**Aplicar a:** `src/caramello/shared/database.py` (está no escopo do ruff e mypy — não está nos diretórios excluídos)

```toml
# pyproject.toml — ruff exclui api/generated e models, MAS inclui shared/
exclude = [
    "src/caramello/api/generated",
    "src/caramello/models",
    "src/caramello/schemas/generated",
]

# mypy — disallow_untyped_defs = true é a restrição mais relevante:
disallow_untyped_defs = true
ignore_missing_imports = true  # cobre asyncpg-stubs ausente
```

Implicações para `shared/database.py`:
- `get_session()` DEVE ter type hint de retorno explícito: `async def get_session() -> AsyncGenerator[AsyncSession, None]`
- `do_run_migrations` no `env.py` (se em shared) também precisa de type hint; como está em `alembic/` (excluído), mypy não verifica

### Padrão de construção de DATABASE_URL

**Fonte:** `src/caramello/core/config.py` linhas 28-34
**Aplicar a:** `src/caramello/core/config.py` (modificação pontual)

```python
# Padrão estabelecido — manter estrutura, mudar apenas o prefixo:
def model_post_init(self, __context: object) -> None:
    """Constrói DATABASE_URL a partir dos campos individuais."""
    password = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
    port = f":{self.DB_PORT}" if self.DB_PORT else ""
    self.DATABASE_URL = (
        f"postgresql+asyncpg://{self.DB_USER}{password}@{self.DB_HOST}{port}/{self.DB_NAME}"
        # ^^^^^^^^^^^^ única mudança: postgresql:// → postgresql+asyncpg://
    )
```

---

## No Analog Found

Nenhum arquivo desta fase fica sem analog — todas as modificações têm como ponto de partida os próprios arquivos existentes ou o analog direto `database/session.py`.

| File | Role | Data Flow | Situação |
|------|------|-----------|----------|
| `src/caramello/shared/__init__.py` | package init | — | Arquivo vazio — sem padrão necessário |

---

## Metadata

**Analog search scope:** `src/caramello/`, `alembic/`, `scripts/`
**Files scanned:** 6 arquivos lidos diretamente
**Pattern extraction date:** 2026-05-25

**Resumo das mudanças por arquivo:**

| Arquivo | Tipo de mudança | Escopo |
|---------|-----------------|--------|
| `src/caramello/shared/__init__.py` | criar (vazio) | trivial |
| `src/caramello/shared/database.py` | criar (rewrite de session.py) | total |
| `src/caramello/database/session.py` | deletar | — |
| `src/caramello/core/config.py` | modificar 1 linha | mínimo |
| `alembic/env.py` | modificar função online + imports | parcial |
| `scripts/generate_code.py` | modificar função `generate_router()` | parcial |
| `src/caramello/main.py` | verificar; provável noop | nenhum |
| `src/caramello/api/generated/*_router.py` | regenerar (4 arquivos) | via generator |
