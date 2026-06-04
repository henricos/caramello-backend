---
phase: 7
slug: crud-account-category
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-01
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 + pytest-asyncio |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run python -m pytest tests/test_finances_operations.py -q` |
| **Full suite command** | `uv run python -m pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/test_finances_operations.py -q`
- **After every plan wave:** Run `uv run python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | ACC-01..ACC-03, CAT-01..CAT-04, AUTH-FIN-01..02 | T-7-01 | Arquivo de testes com stubs criado | Wave 0 | `uv run python -m pytest tests/test_finances_operations.py -q` | ❌ Wave 0 | ⬜ pending |
| 7-02-01 | 02 | 1 | ACC-01 | T-7-01 | POST /finances/accounts retorna uuid sem id/family_id interno | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_account_returns_uuid -x` | ❌ Wave 0 | ⬜ pending |
| 7-02-02 | 02 | 1 | ACC-02, AUTH-FIN-01, AUTH-FIN-02 | T-7-02 | GET /finances/accounts filtra por família; 403 sem token; 403 família alheia | unit | `uv run python -m pytest tests/test_finances_operations.py::test_list_accounts_scoped_to_family tests/test_finances_operations.py::test_accounts_require_auth tests/test_finances_operations.py::test_accounts_403_non_member -x` | ❌ Wave 0 | ⬜ pending |
| 7-02-03 | 02 | 1 | ACC-03 | — | PATCH is_active=false arquiva sem deletar dados | unit | `uv run python -m pytest tests/test_finances_operations.py::test_archive_account -x` | ❌ Wave 0 | ⬜ pending |
| 7-03-01 | 03 | 1 | CAT-01, CAT-04 | T-7-03 | POST /finances/categories cria categoria pai; scoped por família | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_category tests/test_finances_operations.py::test_list_update_categories -x` | ❌ Wave 0 | ⬜ pending |
| 7-03-02 | 03 | 1 | CAT-02 | — | POST /finances/subcategory com category_uuid válido cria subcategoria | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_subcategory -x` | ❌ Wave 0 | ⬜ pending |
| 7-03-03 | 03 | 1 | CAT-03 | — | Estrutura impede nível 3 — paths de router verificados | path check | `uv run python -m pytest tests/test_finances_operations.py::test_finances_router_paths -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_finances_operations.py` — stubs para ACC-01, ACC-02, ACC-03, CAT-01, CAT-02, CAT-03, CAT-04, AUTH-FIN-01, AUTH-FIN-02
  - Seguir padrão de `tests/test_family_operations.py`: `dependency_overrides`, `AsyncMock`, `TestClient(app)` sem context manager
  - `pytest.importorskip("caramello.finances.operations")` no início de cada teste

*Infraestrutura existente (conftest.py, AsyncMock, TestClient) já cobre o resto.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AUTH-FIN-01: 401 vs 403 para token ausente | AUTH-FIN-01 | HTTPBearer retorna 403 por padrão; REQUIREMENTS especifica 401 — desvio documentado | Confirmar que comportamento real é 403 e documentar nos testes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
