---
phase: 02-stack-async
plan: "03"
subsystem: migrations
tags:
  - alembic
  - async
  - asyncpg
  - migrations
dependency_graph:
  requires:
    - 02-01  # asyncpg instalado (D-01)
  provides:
    - alembic/env.py com modo online async (D-06)
    - import models preservado para autogenerate (D-07)
    - Pitfall 5 mitigado: await connectable.dispose()
  affects:
    - alembic/env.py
tech_stack:
  added: []
  patterns:
    - "Alembic async pattern: do_run_migrations() síncrono + run_async_migrations() async + asyncio.run() como entrypoint"
    - "NullPool no engine de migrations (operação única — sem pool persistente)"
    - "await connectable.dispose() obrigatório ao final para evitar connection leak no asyncpg"
key_files:
  modified:
    - alembic/env.py — modo online reescrito para async_engine_from_config + NullPool + asyncio.run(); modo offline preservado
decisions:
  - "noqa comments adicionados (E402, F403) para suprimir avisos de ruff esperados no padrão Alembic — imports de models ficam após fileConfig() por design"
  - "do_run_migrations(connection) mantém assinatura sem type hint de Connection para evitar import de tipo alembic; noqa: ANN001 aplicado"
  - "Ordem dos imports no bloco mid-file ajustada para satisfazer isort (sqlmodel antes de caramello.*)"
metrics:
  duration: "~8 minutos"
  completed: "2026-05-25T01:38:32Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 02 Plan 03: Alembic async env.py Summary

**One-liner:** Migração de alembic/env.py para engine async com NullPool e asyncio.run(), implementando D-06 e D-07 e mitigando Pitfall 5 (connection leak asyncpg).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Reescrever modo online de alembic/env.py para async com NullPool e dispose() | 1fa8d2b | alembic/env.py |

## What Was Built

O arquivo `alembic/env.py` foi reescrito para usar o padrão async canônico do Alembic com SQLAlchemy/asyncpg:

**Estrutura nova do modo online:**

1. `do_run_migrations(connection) -> None` — helper síncrono que recebe conexão via `run_sync()` e executa o configure + begin_transaction + run_migrations
2. `run_async_migrations() -> None` (async) — cria engine via `async_engine_from_config` com `NullPool`, faz `async with connectable.connect()`, chama `await connection.run_sync(do_run_migrations)`, e chama `await connectable.dispose()` ao final
3. `run_migrations_online() -> None` — wrapper síncrono que chama `asyncio.run(run_async_migrations())`

**Preservado intacto:**
- Modo offline (`run_migrations_offline`) — sem mudanças (síncrono por design, não há engine para tornar async)
- Import de models: `from caramello.models import *` (D-07)
- `target_metadata = SQLModel.metadata`
- Bloco condicional final `if context.is_offline_mode()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Ruff compliance] Adicionados noqa comments para E402 e F403**
- **Found during:** Task 1 — verificação pós-edição com `uv run ruff check alembic/env.py`
- **Issue:** O arquivo original já apresentava E402 (module level import not at top of file) e F403 (import *) que o plano não mencionava explicitamente. O arquivo original também não passava em ruff — o plano afirmava que deveria passar após a edição.
- **Fix:** Adicionados `# noqa: E402` nos imports que ficam após `fileConfig()` (padrão Alembic), `# noqa: E402, F403` no `from caramello.models import *`, e `# noqa: ANN001` em `do_run_migrations` para evitar import de tipo alembic.Connection. Ordem dos imports no bloco mid-file ajustada para satisfazer isort (sqlmodel antes de caramello.*).
- **Files modified:** alembic/env.py
- **Commit:** 1fa8d2b (incluído no commit da task)

**2. [Nota] Falso positivo na spec de verificação do plano**
- A spec `<verification>` afirma que `grep -c "create_engine\|engine_from_config[^_]" alembic/env.py` retornaria `0` porque "o regex usa `[^_]` após `engine_from_config`". Esta afirmação está incorreta — `engine_from_config[^_]` também captura `async_engine_from_config(` porque `(` não é `_`. Retorna `1` (apenas `async_engine_from_config`), mas sem presença de engine sync. Comportamento correto, spec imprecisa.

## Verification Results

| Check | Result |
|-------|--------|
| `import asyncio` presente | PASS |
| `async_engine_from_config` importado de `sqlalchemy.ext.asyncio` | PASS |
| `engine_from_config` sync removido | PASS |
| `async def run_async_migrations` existe | PASS |
| `await connectable.dispose()` presente | PASS |
| `asyncio.run(run_async_migrations())` presente | PASS |
| `poolclass=pool.NullPool` presente | PASS |
| `def do_run_migrations(connection)` presente | PASS |
| `await connection.run_sync(do_run_migrations)` presente | PASS |
| `from caramello.models import *` preservado | PASS |
| `target_metadata = SQLModel.metadata` preservado | PASS |
| `def run_migrations_offline` preservado | PASS |
| `literal_binds=True` preservado no modo offline | PASS |
| `context.is_offline_mode()` preservado | PASS |
| `uv run ruff check alembic/env.py` | PASS |
| Sintaxe Python válida | PASS |

## Known Stubs

Nenhum stub identificado — o arquivo é infra de migrations, não expõe dados ao frontend.

## Threat Flags

Nenhuma nova superfície de segurança introduzida além do que está documentado no `<threat_model>` do plano.

## Self-Check: PASSED

- `alembic/env.py` existe: FOUND
- Commit `1fa8d2b` existe: FOUND
- `SUMMARY.md` criado em `.planning/phases/02-stack-async/02-03-SUMMARY.md`
