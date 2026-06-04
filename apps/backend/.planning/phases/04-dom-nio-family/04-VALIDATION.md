---
phase: 4
slug: dom-nio-family
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-generator-url | 01 | 1 | D-09, D-10 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_router_url_has_domain_prefix_and_hyphens -x` | ✅ Wave 0 done | ⬜ pending |
| 04-alembic-migration | 02 | 2 | D-01 | — | N/A | manual | `uv run alembic upgrade head` (sem erro) | N/A | ⬜ pending |
| 04-families-models | 02 | 2 | D-01, FAMILY-01 | — | N/A | unit | `uv run pytest tests/ -x -q` | N/A | ⬜ pending |
| 04-families-operations | 03 | 3 | FAMILY-01, FAMILY-02, FAMILY-03, FAMILY-07 | T-04-01 | Endpoint retorna 403 sem owner role; retorna 401 sem token | unit (mock) | `uv run pytest tests/test_family_operations.py -x` | ✅ Wave 0 done | ⬜ pending |
| 04-auto-join | 04 | 3 | D-02 | — | Auto-join só ocorre para convites pending_login | unit (mock) | `uv run pytest tests/test_auth.py::test_auto_join_on_login -x` | ✅ Wave 0 done | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] ✅ `tests/test_family_operations.py` — stubs para FAMILY-01, 02, 03, 07 usando `app.dependency_overrides[get_current_user]` (padrão de `tests/test_user_operations.py`) — concluído no plano 04-01 Task 1
- [x] ✅ `tests/test_auth.py` — `test_auto_join_on_login` adicionado — concluído no plano 04-01 Task 2
- [x] ✅ `tests/test_generator.py` — `test_router_url_has_domain_prefix_and_hyphens` (+5 invariantes) adicionados — concluído no plano 04-01 Task 2

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `alembic upgrade head` em banco limpo | D-01 | Requer PostgreSQL real | `uv run alembic upgrade head` — deve concluir sem erro e tabela `family_invitation` ter colunas `email` + `status` |
| URLs corretas no OpenAPI spec | D-10, D-11 | Validação visual | Checar `/docs` — rotas devem ter hifens e prefixo de domínio correto |
| App inicializa sem ImportError | D-09 | Requer runtime completo | `uv run uvicorn caramello.main:app --reload` — app deve subir sem erro |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
