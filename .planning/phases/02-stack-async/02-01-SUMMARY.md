---
phase: 02-stack-async
plan: "01"
subsystem: dependencies
tags:
  - python
  - asyncpg
  - sqlmodel
  - dependencies
dependency_graph:
  requires: []
  provides:
    - asyncpg instalado e psycopg2-binary removido (D-01)
    - sqlmodel 0.0.38 instalado (D-02)
    - base para shared/database.py (Wave 2, Plan 02)
    - base para alembic async env.py (Wave 2, Plan 03)
  affects:
    - pyproject.toml
    - uv.lock
tech_stack:
  added:
    - asyncpg 0.31.0 — driver PostgreSQL async nativo
    - sqlmodel 0.0.38 — ORM com AsyncSession e exec() como API canônica
  patterns:
    - uv remove / uv add para gerenciamento de dependências (nunca editar uv.lock manualmente)
key_files:
  modified:
    - pyproject.toml — psycopg2-binary removido; asyncpg>=0.31.0 e sqlmodel>=0.0.38 adicionados
    - uv.lock — lockfile resolvido sem psycopg2 e com asyncpg 0.31.0 + sqlmodel 0.0.38
decisions:
  - "asyncpg 0.31.0 instalado via uv add — versão mais recente disponível; uv escreveu 'asyncpg>=0.31.0' em pyproject.toml (com constraint de versão mínima)"
  - "sqlmodel 0.0.38 instalado — zero breaking changes para este projeto (confirma RESEARCH.md §Breaking Changes)"
metrics:
  duration: "~2 minutos"
  completed: "2026-05-25T01:32:14Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase 02 Plan 01: Substituição de Driver de Banco (psycopg2 → asyncpg) Summary

**One-liner:** Troca de psycopg2-binary (sync) por asyncpg 0.31.0 (async nativo) com atualização de SQLModel para 0.0.38, desbloqueando a Wave 2 da Phase 2.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Substituir psycopg2-binary por asyncpg e atualizar sqlmodel | 4c48afe | pyproject.toml, uv.lock |

## Acceptance Criteria Verified

- `asyncpg>=0.31.0` presente em `pyproject.toml` dependencies
- `psycopg2-binary` ausente de `pyproject.toml` (exit 1 no grep)
- `sqlmodel>=0.0.38` presente em `pyproject.toml`
- `psycopg2-binary` ausente de `uv.lock` (exit 1 no grep)
- `asyncpg` presente em `uv.lock` (version = "0.31.0")
- `sqlmodel` em `uv.lock` com version = "0.0.38"
- `uv run python -c "import asyncpg"` retorna 0.31.0
- `from sqlmodel.ext.asyncio.session import AsyncSession` importa com sucesso
- `import psycopg2` levanta `ModuleNotFoundError` (confirmado)
- `uv sync --frozen` conclui sem erros (lockfile coerente)
- Blocos `[tool.ruff]`, `[tool.mypy]`, `[build-system]`, `[dependency-groups]` intactos

## Deviations from Plan

### Comportamento do uv add (informativo, não é bug)

**Encontrado durante:** Task 1
**Observação:** O plano esperava `"asyncpg"` (sem constraint de versão) em `pyproject.toml`. O `uv add asyncpg` escreveu `"asyncpg>=0.31.0"` — com constraint explícita de versão mínima igual à instalada.
**Impacto:** Semanticamente mais correto (garante que upgrades futuros resolvem para >= 0.31.0). Não é uma regressão — todos os critérios substanciais do plano são satisfeitos. O critério literal `grep -c '"asyncpg"' pyproject.toml` não funciona com o padrão exato mas `grep "asyncpg" pyproject.toml` retorna a linha correta.
**Ação:** Nenhuma correção necessária — comportamento intencional do uv.

## Known Stubs

Nenhum. Este plano é exclusivamente de dependências — sem código Python criado ou modificado.

## Threat Flags

Nenhuma superfície nova introduzida. Apenas troca de dependência de infraestrutura conforme T-2-02 do threat model do plano (mitigação: uv add/remove em vez de edição manual do lockfile — aplicado corretamente).

## Self-Check: PASSED

- pyproject.toml: existe e contém asyncpg>=0.31.0, sqlmodel>=0.0.38, sem psycopg2-binary
- uv.lock: existe e contém asyncpg 0.31.0, sqlmodel 0.0.38, sem psycopg2-binary
- Commit 4c48afe: presente em git log
- Imports funcionando: asyncpg 0.31.0, AsyncSession de sqlmodel.ext.asyncio.session
