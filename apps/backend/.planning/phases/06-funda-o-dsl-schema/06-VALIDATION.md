---
phase: 6
slug: funda-o-dsl-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-31
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_generator.py -v` |
| **Full suite command** | `uv run pytest -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_generator.py -v`
- **After every plan wave:** Run `uv run pytest -v`
- **Before `/gsd-verify-work`:** Full suite must be green + `uv run alembic upgrade head` + `uv run alembic downgrade -1`
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | SC-7 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_generator_decimal_emits_numeric -v` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | SC-8 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_generator_filters_emits_table_args -v` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | SC-5 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_finances_yamls_have_domain_finances -v` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | SC-6 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_finances_models_no_float -v` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | SC-4 | — | N/A | unit | `uv run python -c "from caramello.finances import models; print('OK')"` | ✅ | ⬜ pending |
| 06-03-02 | 03 | 2 | SC-4 | — | N/A | unit | `uv run pytest tests/test_generator.py::test_finances_models_import_ok -v` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 3 | SC-1 | — | N/A | integração | `uv run alembic upgrade head` | ✅ | ⬜ pending |
| 06-04-02 | 04 | 3 | SC-2 | — | N/A | integração | `uv run alembic downgrade -1` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_generator.py::test_generator_decimal_emits_numeric` — `generate_models` com campo `Decimal` emite `Column(Numeric(15, 2))`
- [ ] `tests/test_generator.py::test_generator_filters_emits_table_args` — entidade com `filters:` gera `__table_args__` com `Index`
- [ ] `tests/test_generator.py::test_finances_yamls_have_domain_finances` — verifica `domain: finances` nos 5 YAMLs
- [ ] `tests/test_generator.py::test_finances_models_no_float` — `finances/models.py` não contém `float` em campos de valor
- [ ] `tests/test_generator.py::test_finances_models_import_ok` — `from caramello.finances import models` não levanta `ImportError`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `alembic upgrade head` aplica 0002 sem erros em banco limpo | SC-1 | Requer conexão PostgreSQL real (`caramello_dev`) | 1. Garantir banco acessível; 2. `uv run alembic upgrade head`; 3. Verificar saída sem erro |
| `alembic downgrade -1` reverte completamente | SC-2 | Requer conexão PostgreSQL real | 1. `uv run alembic downgrade -1`; 2. Verificar que tabelas `account`, `movement`, `financial_entry`, `category`, `subcategory` foram removidas |
| Tabelas com tipos e constraints corretos | SC-3 | Inspeção SQL via psql ou similar | `\d+ account`, `\d+ movement`, `\d+ financial_entry` — verificar `NUMERIC(15,2)`, `UNIQUE` em `movement_id` e `import_hash` |
| `down_revision = "0001"` correto na migration 0002 | SC-P6 | Verificação manual de arquivo | Após gerar 0002: `alembic history --verbose` mostra cadeia linear `None → 0001 → 0002 (head)` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
