---
phase: 2
slug: stack-async
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 |
| **Config file** | nenhum — sem `[tool.pytest.ini_options]` em pyproject.toml |
| **Quick run command** | `uv run ruff check src/ && uv run mypy src/` |
| **Full suite command** | `uv run ruff check src/ && uv run mypy src/ && grep -r "create_engine" src/` |
| **Estimated runtime** | ~10 seconds (sem banco) |

---

## Sampling Rate

- **After every task commit:** Run `uv run ruff check src/ && uv run mypy src/`
- **After every plan wave:** Run `uv run ruff check src/ && uv run mypy src/ && grep -r "create_engine" src/` (deve retornar vazio)
- **Before `/gsd-verify-work`:** Full suite must be green + `alembic upgrade head` manual (requer banco)
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | INFRA-01 | — | N/A | smoke | `grep psycopg2 uv.lock` (deve retornar vazio) | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | INFRA-01 | — | N/A | smoke | `grep -r "create_engine" src/` (deve retornar vazio) | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | INFRA-01 | T-2-01 | `echo=False` previne leakage de DB URL nos logs | smoke | `grep "AsyncSession" src/caramello/shared/database.py` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | INFRA-01 | — | N/A | type-check | `uv run mypy src/caramello/shared/database.py` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | INFRA-01 | — | N/A | smoke | `grep "async_engine_from_config" alembic/env.py` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | INFRA-01 | — | N/A | smoke | `grep -r "async def" src/caramello/api/generated/` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 3 | INFRA-01 | — | N/A | linting | `uv run ruff check src/` | ✅ (ruff instalado) | ⬜ pending |
| 02-04-03 | 04 | 3 | INFRA-01 | — | N/A | type-check | `uv run mypy src/` | ✅ (mypy instalado) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Nenhum arquivo de teste novo precisa ser criado nesta fase.
- Os testes existentes (`tests/test_api/test_user_router.py`, `tests/test_services/test_user_service.py`) estão vazios — preenchidos na Phase 5.
- A validação desta fase é estrutural: greps, ruff, mypy, e `alembic upgrade head` manual.

---

## Threat Model (ASVS L1)

| # | Threat | STRIDE | Mitigation | Plan |
|---|--------|--------|------------|------|
| T-2-01 | Connection string leakage via engine logs | Information Disclosure | `echo=False` em `create_async_engine` | 02 |
| T-2-02 | SQL injection via ORM | Tampering | SQLModel/SQLAlchemy usa queries parametrizadas — padrão mantido | N/A |
