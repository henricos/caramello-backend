---
phase: 8
slug: movimenta-es-importa-o
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| **Quick run command** | `uv run python -m pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -v` |
| **Full suite command** | `uv run python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -v`
- **After every plan wave:** Run `uv run python -m pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | MOV-01 | — | N/A | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_movement -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 0 | MOV-01 | — | 409 se hash duplicado | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_movement_409_duplicate -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 0 | MOV-02 | — | N/A | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_csv -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 0 | MOV-03 | — | N/A | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_ofx -x` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 0 | MOV-03 | — | N/A | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_xlsx -x` | ❌ W0 | ⬜ pending |
| 08-01-06 | 01 | 0 | MOV-04 | — | Reimportar não duplica | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_deduplication -x` | ❌ W0 | ⬜ pending |
| 08-01-07 | 01 | 0 | MOV-05 | — | potential_duplicates[] retornados | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_potential_duplicates -x` | ❌ W0 | ⬜ pending |
| 08-01-08 | 01 | 0 | MOV-05 | — | confirm insere sem collision | unit | `uv run python -m pytest tests/test_finances_operations.py::test_import_confirm -x` | ❌ W0 | ⬜ pending |
| 08-01-09 | 01 | 0 | D-15 | — | N/A | unit | `uv run python -m pytest tests/test_finances_operations.py::test_list_movements -x` | ❌ W0 | ⬜ pending |
| 08-01-10 | 01 | 0 | AUTH-FIN-01/02 | — | 401 sem token, 403 família alheia | unit | `uv run python -m pytest tests/test_finances_operations.py::test_movements_require_auth -x` | ❌ W0 | ⬜ pending |
| 08-01-11 | 01 | 0 | MOV-02 | — | N/A | unit puro | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv -x` | ❌ W0 | ⬜ pending |
| 08-01-12 | 01 | 0 | MOV-02 | — | Linhas inválidas → error_lines[] | unit puro | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv_error_lines -x` | ❌ W0 | ⬜ pending |
| 08-01-13 | 01 | 0 | MOV-02 | — | >50% erros aborta com 422 | unit puro | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv_abort_threshold -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_finances_operations.py` — estender com testes de Movement (MOV-01..05, D-15, AUTH-FIN-01/02)
- [ ] `tests/test_services/test_finances_service.py` — novo arquivo; cobre parsers _parse_csv/_parse_ofx/_parse_xlsx sem mock session
- [ ] Instalar `ofxparse` e `openpyxl` via `uv add` antes dos testes de MOV-03 (já no Wave 0 plan)
