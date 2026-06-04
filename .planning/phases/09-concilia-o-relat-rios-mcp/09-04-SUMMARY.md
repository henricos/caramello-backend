---
phase: 09-concilia-o-relat-rios-mcp
plan: "04"
subsystem: finances
tags: [analytics, balance, reports, reconciliation, testing]
dependency_graph:
  requires: ["09-03"]
  provides: ["REL-01", "REL-02", "REL-03", "REL-04", "REL-05", "D-MOV-01", "D-MOV-02"]
  affects: ["tests/test_finances_operations.py"]
tech_stack:
  added: []
  patterns:
    - "Remoção de guards Nyquist após implementação completa — testes passam de condicionais para assertivos"
    - "Verificação por assertion direta em vez de pytest.skip condicional"
key_files:
  created: []
  modified:
    - tests/test_finances_operations.py
decisions:
  - "Conteúdo de 09-03 já entregou todos os endpoints de saldo e relatórios (account_balance, family_balance, monthly_breakdown, by_member_breakdown) — 09-04 apenas formaliza a remoção dos guards"
  - "entry_uuid e filtro reconciled em list_movements já estavam implementados pelo 09-03"
  - "test_finances_router_paths_phase9 convertido de skip condicional para assert direto"
metrics:
  duration: "~15 minutos"
  tasks_completed: 3
  files_modified: 1
  completed_date: "2026-06-04"
---

# Phase 09 Plan 04: Endpoints de Saldo, Relatórios e Remoção de Guards — Summary

Implementa e ativa a camada analítica completa da fase 9: endpoints de saldo por conta e família (REL-01/02), relatórios mensais por categoria/subcategoria (REL-03/04/05) e por membro (D-REP-02), campo `entry_uuid` com filtro `?reconciled` em `list_movements` (D-MOV-01/02), e remoção dos guards Nyquist para que todos os testes da fase 9 executem de forma assertiva.

## O que foi construído

### Estado encontrado vs. planejado

Ao iniciar a execução, o worktree estava baseado no commit da fase 7 (stub). Após o reset para o commit base correto (`5b00584`), verificou-se que o plano 09-03 já havia implementado **toda a camada analítica** antes desta execução:

- `services.py`: `account_balance`, `family_balance`, `monthly_breakdown`, `by_member_breakdown` — todos implementados com `func.sum`, `group_by`, `session.execute()`, pitfall P6 (SUM NULL → Decimal("0.00")), filtros por `competencia_year/month` (REL-05)
- `operations.py`: endpoints `GET /finances/accounts/{account_uuid}/balance`, `GET /finances/families/{family_uuid}/balance`, `GET /finances/reports/monthly`, `GET /finances/reports/by-member` — todos com auth via `_require_family_access` e schemas públicos (`AccountBalancePublic`, `FamilyBalancePublic`, `MonthlyReportPublic`, `ByMemberReportPublic`)
- `MovementReadPublic.entry_uuid: UUID | None` — já presente
- `list_movements` com parâmetro `reconciled: bool | None` via LEFT JOIN + `outerjoin(Movement, FinancialEntry)` — já implementado

### Trabalho realizado no plano 09-04

A única mudança efetiva foi a **remoção dos guards `_skip_if_phase9_missing()`** dos 11 testes stub da fase 9 em `tests/test_finances_operations.py`:

- `test_reconcile_movement` — guard removido
- `test_reconcile_409_duplicate` — guard removido
- `test_suggest_category` — guard removido
- `test_update_entry` — guard removido
- `test_entry_responsible_user_uuid` — guard removido
- `test_account_balance` — guard removido
- `test_family_balance` — guard removido
- `test_monthly_report` — guard removido
- `test_report_uses_competencia` — guard removido
- `test_movement_entry_uuid_field` — guard removido
- `test_movement_reconciled_filter` — guard removido
- `test_finances_router_paths_phase9` — convertido de `pytest.skip` condicional para `assert not missing` direto

## Verificação

```
uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -v
→ 44 passed, 0 failed
```

Todos os 44 testes passam, incluindo todos os 11 testes de fase 9 que anteriormente dependiam do guard. `test_finances_router_paths_phase9` valida os 8 paths sem condição de skip.

## Deviations from Plan

### Desvio por antecipação (09-03 entregou parte do escopo de 09-04)

**Tasks 1 e 2:** O plano 09-04 prescrevia implementar `account_balance`, `family_balance`, `monthly_breakdown`, `by_member_breakdown` em `services.py` e os respectivos endpoints em `operations.py`. O plano 09-03, por ter escopo amplo (núcleo de conciliação + relatórios), antecipou toda essa implementação. Os critérios de aceitação das Tasks 1 e 2 foram verificados e estavam todos satisfeitos:
- `grep -q 'def account_balance' services.py` → OK
- `grep -q 'func.sum' services.py` → OK
- `grep -q '/accounts/{account_uuid}/balance' operations.py` → OK
- `grep -q 'entry_uuid' operations.py` → OK
- `grep -q 'outerjoin' operations.py` → OK

**Task 3 (única mudança efetiva):** Remoção dos guards executada conforme especificado. 44/44 testes verdes.

## Known Stubs

Nenhum stub identificado. Todos os endpoints retornam dados reais das funções de agregação.

## Threat Flags

Nenhuma nova superfície de segurança introduzida neste plano (apenas remoção de guards de teste).

## Self-Check: PASSED

- `tests/test_finances_operations.py` modificado e commitado (`66e700d`)
- 44 testes passam sem skip
- Nenhum arquivo de código de produção foi alterado (tudo já estava implementado pelo 09-03)
