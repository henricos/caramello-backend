---
phase: 9
slug: concilia-o-relat-rios-mcp
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1 + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| LAN-01 | 01 | 1 | LAN-01 | — | POST /reconcile cria FinancialEntry, retorna 201 + schema rico | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_reconcile_movement -x` | ❌ Wave 0 | ⬜ pending |
| LAN-02 | 01 | 1 | LAN-02 | — | POST /reconcile retorna 409 se movement já tem entry | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_reconcile_409_duplicate -x` | ❌ Wave 0 | ⬜ pending |
| LAN-03 | 01 | 1 | LAN-03 | — | GET /suggest-category retorna top-5 com score | unit (mock) + service unit | `uv run pytest tests/test_finances_operations.py::test_suggest_category tests/test_services/test_finances_service.py::test_suggest_category_service -x` | ❌ Wave 0 | ⬜ pending |
| LAN-04 | 01 | 1 | LAN-04 | — | POST /reconcile aceita is_recorrente=true | unit (coberto por LAN-01 variação) | (coberto por test_reconcile_movement) | ❌ Wave 0 | ⬜ pending |
| LAN-05 | 01 | 1 | LAN-05 | — | PATCH /entries/{uuid} atualiza subcategoria, competência, notas, responsável | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_update_entry -x` | ❌ Wave 0 | ⬜ pending |
| REL-01 | 02 | 2 | REL-01 | — | GET /accounts/{uuid}/balance retorna saldo calculado correto | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_account_balance -x` | ❌ Wave 0 | ⬜ pending |
| REL-02 | 02 | 2 | REL-02 | — | GET /families/{uuid}/balance retorna saldo consolidado | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_family_balance -x` | ❌ Wave 0 | ⬜ pending |
| REL-03 | 03 | 2 | REL-03 | — | GET /reports/monthly retorna breakdown por categoria pai | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_monthly_report -x` | ❌ Wave 0 | ⬜ pending |
| REL-04 | 03 | 2 | REL-04 | — | GET /reports/monthly inclui detalhamento por subcategoria | unit (coberto por REL-03) | (coberto por test_monthly_report) | ❌ Wave 0 | ⬜ pending |
| REL-05 | 03 | 2 | REL-05 | — | Relatórios filtram por competencia_year/month, não Movement.date | unit | `uv run pytest tests/test_finances_operations.py::test_report_uses_competencia -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_finances_operations.py` — adicionar stubs Nyquist para LAN-01/02/03/05, REL-01/02/03/05 + atualizar `test_finances_router_paths` com novos paths da fase 9
- [ ] `tests/test_services/test_finances_service.py` — adicionar stubs para `suggest_category`, `account_balance`, `family_balance`, `monthly_breakdown`, `by_member_breakdown`
- [ ] `uv add rapidfuzz>=3.14.5` — obrigatório antes dos testes de sugestão de categoria

**Testes adicionais de caminho crítico:**

| Teste | Behavior | File Exists? |
|-------|----------|-------------|
| `test_entry_responsible_user_uuid` | Atribuição + remoção de responsável via PATCH | ❌ Wave 0 |
| `test_suggest_category_empty_history` | `[]` quando sem lançamentos anteriores | ❌ Wave 0 |
| `test_movement_entry_uuid_field` | MovementReadPublic inclui entry_uuid | ❌ Wave 0 |
| `test_movement_reconciled_filter` | GET movements?reconciled=false retorna apenas pendentes | ❌ Wave 0 |

*Infraestrutura existente de testes (conftest.py, AsyncMock pattern) cobre todos os novos testes — sem novas fixtures globais necessárias.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nenhuma verificação manual nesta fase | — | D-MCP-01 defere ferramentas MCP para M3 | — |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
