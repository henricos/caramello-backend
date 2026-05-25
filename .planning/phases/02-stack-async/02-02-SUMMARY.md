---
phase: 02-stack-async
plan: "02"
subsystem: database
tags:
  - python
  - async
  - sqlmodel
  - asyncpg
  - session
dependency_graph:
  requires:
    - 02-01  # asyncpg instalado no pyproject.toml
  provides:
    - shared/database.py  # engine async, session factory, get_session
    - config.py com prefixo postgresql+asyncpg://
  affects:
    - 02-03  # Alembic env.py consome engine async
    - 02-04  # generator atualizado para importar de shared/database
tech_stack:
  added:
    - create_async_engine (sqlalchemy.ext.asyncio) — engine async singleton
    - async_sessionmaker (sqlalchemy.ext.asyncio) — factory de sessões async
    - AsyncSession (sqlmodel.ext.asyncio.session) — session com exec() async
  patterns:
    - async generator com yield para injeção de dependência FastAPI
    - expire_on_commit=False para evitar MissingGreenlet após commit
key_files:
  created:
    - src/caramello/shared/__init__.py
    - src/caramello/shared/database.py
  modified:
    - src/caramello/core/config.py
decisions:
  - "AsyncSession importado de sqlmodel.ext.asyncio.session (NÃO de sqlalchemy.ext.asyncio) — garante session.exec() async disponível"
  - "echo=False em create_async_engine — mitigação T-2-01 (não vazar connection string em logs)"
  - "expire_on_commit=False obrigatório em async_sessionmaker — evita MissingGreenlet após commit"
  - "database/session.py legado mantido intacto — deleção adiada para Plan 04 após regeneração dos routers"
metrics:
  duration: "2 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 02 Plan 02: Async Session Module Summary

**One-liner:** Módulo `shared/database.py` com engine asyncpg, session factory e `get_session` async generator; `config.py` atualizado para `postgresql+asyncpg://`

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Atualizar prefixo DATABASE_URL para postgresql+asyncpg:// | 7c62995 | src/caramello/core/config.py |
| 2 | Criar shared/__init__.py e shared/database.py async | f28a013 | src/caramello/shared/__init__.py, src/caramello/shared/database.py |

## What Was Built

O plano implementa a camada de session async que os planos subsequentes (Alembic env.py e regeneração de routers) vão consumir:

- **`src/caramello/core/config.py`**: prefixo da URL de banco alterado de `postgresql://` para `postgresql+asyncpg://`, tornando-a compatível com `create_async_engine`.

- **`src/caramello/shared/__init__.py`**: arquivo vazio que marca o diretório como pacote Python.

- **`src/caramello/shared/database.py`**: módulo novo com três símbolos públicos:
  - `engine`: singleton criado via `create_async_engine` com `echo=False` e `future=True`
  - `async_session_factory`: `async_sessionmaker` com `class_=AsyncSession` e `expire_on_commit=False`
  - `get_session()`: async generator tipado como `AsyncGenerator[AsyncSession, None]` para uso via `Depends(get_session)` nos routers

## Deviations from Plan

Nenhuma — plano executado exatamente conforme especificado.

## Verification Results

- `uv run ruff check src/` — passou (0 violações)
- `uv run mypy src/` — passou (0 erros em 11 arquivos fonte)
- `src/caramello/database/session.py` — ainda existe, intacto (deleção é responsabilidade do Plan 04)
- Testes de import com `.env` — pulados (sem `.env` no ambiente de worktree, comportamento esperado pelo plano)

## Known Stubs

Nenhum. O módulo expõe implementação completa e funcional.

## Threat Flags

Nenhuma superfície nova não prevista no threat model do plano.

## Self-Check

- [x] `src/caramello/shared/__init__.py` existe e está vazio
- [x] `src/caramello/shared/database.py` existe com todos os símbolos esperados
- [x] `src/caramello/core/config.py` contém `postgresql+asyncpg://` (1 ocorrência)
- [x] Commit 7c62995 existe (Task 1)
- [x] Commit f28a013 existe (Task 2)
- [x] ruff e mypy passam em todo o pacote `src/`

## Self-Check: PASSED
