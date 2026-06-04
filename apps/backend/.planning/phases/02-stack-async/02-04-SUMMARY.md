---
phase: 02-stack-async
plan: "04"
subsystem: codegen
tags:
  - python
  - async
  - fastapi
  - codegen
  - dsl
  - cleanup
dependency_graph:
  requires:
    - 02-02  # shared/database.py com get_session async
    - 02-03  # alembic/env.py com async_engine_from_config
  provides:
    - scripts/generate_code.py com template async (D-08)
    - 4 routers regenerados em async (D-10)
    - remoção de database/session.py (D-11, D-12)
  affects:
    - Phase 3+  # novos domínios gerados já nascem async
tech_stack:
  added:
    - generate_router() emite AsyncSession de sqlmodel.ext.asyncio.session
    - generate_router() importa get_session de caramello.shared.database
    - Template async com await session.exec/commit/refresh/delete
  patterns:
    - Template DSL async com dois passos para exec()+first() e exec()+all()
    - Link models (is_link_model=true) não têm router regenerado — atualização manual
key_files:
  modified:
    - scripts/generate_code.py  # generate_router() reescrito para async
    - src/caramello/api/generated/user_router.py
    - src/caramello/api/generated/family_router.py
    - src/caramello/api/generated/familymember_router.py  # atualizado manualmente
    - src/caramello/api/generated/familyinvitation_router.py
    - src/caramello/models/user.py  # trailing newline (sem mudança funcional)
    - src/caramello/models/family.py  # trailing newline (sem mudança funcional)
    - src/caramello/models/familymember.py  # trailing newline (sem mudança funcional)
    - src/caramello/models/familyinvitation.py  # trailing newline (sem mudança funcional)
  deleted:
    - src/caramello/database/session.py  # módulo sync legado removido
    - src/caramello/database/__init__.py  # diretório database/ removido por completo
  created:
    - tests/generated/__init__.py  # efeito colateral do generate_code
    - tests/generated/test_user.py
    - tests/generated/test_family.py
    - tests/generated/test_familyinvitation.py
decisions:
  - "generate_router() reescreve apenas o template de routers — generate_models/generate_test/main intocados (D-09)"
  - "familymember_router.py atualizado manualmente porque FamilyMember é is_link_model=true (generator pula routers de link models)"
  - "Testes gerados em tests/generated/ ainda usam Session sync — migração para async fica para Phase 5"
  - "Contagem de async def nos routers é 17 (não 20) porque familymember tem 2 endpoints (link model sem CRUD completo)"
metrics:
  duration: "8 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 9
  files_deleted: 2
---

# Phase 02 Plan 04: Code Generator Async + Database Cleanup Summary

**One-liner:** Template `generate_router()` migrado para async; 4 routers regenerados com `AsyncSession` e `await session.exec`; módulo `database/session.py` sync removido; gates finais da Phase 2 passam.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Atualizar template em scripts/generate_code.py::generate_router() para emitir routers async | 9d21918 | scripts/generate_code.py |
| 2 | Regenerar os 4 routers via bin/generate_code, deletar database/session.py, validar main.py | e3c8d88 | src/caramello/api/generated/*.py, src/caramello/database/ (deletado), src/caramello/models/*.py |
| 2b | Adicionar testes gerados pelo DSL como efeito colateral | dd44a01 | tests/generated/ |

## What Was Built

**Task 1 — Template async no gerador:**

A função `generate_router()` em `scripts/generate_code.py` foi reescrita para emitir routers async conforme D-08:
- Remove `Session` sync e `from typing import List` do template
- Adiciona `from sqlmodel.ext.asyncio.session import AsyncSession`
- Troca `from caramello.database.session import get_session` por `from caramello.shared.database import get_session`
- Converte todos os endpoints de `def` para `async def`
- Adiciona `await` em `session.exec`, `session.commit`, `session.refresh`, `session.delete`
- Usa dois passos para consultas: `result = await session.exec(...)` + `result.all()` / `result.first()`
- Substitui `List[X]` por `list[X]` nativo (Python 3.10+)
- `generate_models`, `generate_test`, `main` permanecem intocados (D-09)

**Task 2 — Regeneração e limpeza:**

- `bash bin/generate_code` regenerou os 3 routers de entidades full (`user`, `family`, `familyinvitation`) com o novo template async
- `familymember_router.py` atualizado manualmente (link model — generator não emite router para link models)
- `src/caramello/database/session.py` e `src/caramello/database/__init__.py` deletados; diretório `database/` removido por completo
- `src/caramello/main.py` confirmado limpo — sem referências a `caramello.database` (noop)
- Gates finais da Phase 2 todos passam

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] familymember_router.py não regenerado pelo DSL (link model)**
- **Found during:** Task 2, Gate 2
- **Issue:** `grep -rn "from caramello.database" src/` retornou uma linha em `familymember_router.py`. O generator pula a geração de routers para entidades com `is_link_model: true`, então o arquivo legado não foi atualizado automaticamente.
- **Fix:** Arquivo reescrito manualmente com `AsyncSession`, `from caramello.shared.database import get_session` e endpoints `async def` com `await session.exec`. Mantido com 2 endpoints apenas (GET / e GET /{user_id}) — link models não têm CRUD completo.
- **Files modified:** `src/caramello/api/generated/familymember_router.py`
- **Commit:** e3c8d88

**2. [Efeito colateral documentado] tests/generated/ criado pelo generate_code**
- **Found during:** Task 2, pós-regeneração
- **Issue:** `generate_code.py::main()` cria `TESTS_OUTPUT_DIR` e gera testes — efeito colateral previsto no plano ("Phase 5 trata dos testes").
- **Fix:** Arquivos commitados como estado intencional. Os testes gerados ainda usam `Session` sync e `TestClient` — migração para async é responsabilidade da Phase 5.
- **Files created:** `tests/generated/__init__.py`, `tests/generated/test_user.py`, `tests/generated/test_family.py`, `tests/generated/test_familyinvitation.py`
- **Commit:** dd44a01

## Verification Results

### Gates Finais Phase 2

| Gate | Comando | Resultado |
|------|---------|-----------|
| 1 — nenhum create_engine sync | `grep -rn "create_engine\b" src/ | grep -v create_async_engine` | PASSOU — vazio |
| 2 — nenhum import caramello.database | `grep -rn "from caramello.database" src/ scripts/` | PASSOU — vazio |
| 3 — AsyncSession em shared/database.py | `grep -c "AsyncSession" src/caramello/shared/database.py` | PASSOU — 3 |
| 4 — async_engine_from_config em alembic | `grep -c "async_engine_from_config" alembic/env.py` | PASSOU — 2 |
| 5 — async def nos routers | `grep -rn "async def" src/caramello/api/generated/` | 17 linhas (ver nota) |
| 6 — ruff check | `uv run ruff check src/` | PASSOU — 0 violações |
| 7 — mypy | `uv run mypy src/` | PASSOU — 9 source files |
| 8 — app.routes | `from caramello.main import app; len(app.routes)` | PASSOU — 22 routes |

**Nota sobre Gate 5:** O critério do plano é >= 20 linhas (5 endpoints x 4 routers). O total real é 17 porque `familymember_router.py` é um link model com apenas 2 endpoints (sem POST, PATCH, DELETE de entidade individual). Esse é o comportamento correto — link models não expõem CRUD completo.

## Known Stubs

Nenhum. Todos os routers têm implementação async completa. `familymember_router.py` tem 2 endpoints por design (link model), não por stub.

## Threat Flags

Nenhuma superfície nova além da prevista no threat model do plano:
- T-2-11 (Tampering via codegen): template gerado interpola apenas `name`, `var_name`, `table_name` — tokens controlados pelo DSL. Mitigação confirmada na inspeção do template reescrito.

## Self-Check

- [x] `scripts/generate_code.py` existe com template async em `generate_router()`
- [x] `src/caramello/api/generated/user_router.py` existe com `async def create_user`
- [x] `src/caramello/api/generated/family_router.py` existe com `async def create_family`
- [x] `src/caramello/api/generated/familymember_router.py` existe com `async def`
- [x] `src/caramello/api/generated/familyinvitation_router.py` existe com `async def`
- [x] `src/caramello/database/session.py` DELETADO (confirmado)
- [x] `src/caramello/database/` DELETADO (confirmado)
- [x] Commit 9d21918 existe (Task 1)
- [x] Commit e3c8d88 existe (Task 2)
- [x] Commit dd44a01 existe (testes gerados)
- [x] `02-04-SUMMARY.md` criado em .planning/phases/02-stack-async/

## Self-Check: PASSED
