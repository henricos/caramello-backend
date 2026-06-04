---
status: partial
phase: 09-concilia-o-relat-rios-mcp
source: [09-VERIFICATION.md]
started: 2026-06-04T10:35:00Z
updated: 2026-06-04T10:35:00Z
---

## Current Test

[aguardando testes humanos]

## Tests

### 1. Constraint UNIQUE(movement_id) via banco
expected: Após `alembic upgrade head`, fazer POST reconcile duas vezes com o mesmo movement UUID retorna 409 na segunda chamada (IntegrityError do banco, não check Python)
result: [pending]

### 2. Relatório filtra por competência, não por data de movimentação
expected: GET /finances/reports/monthly?year=2026&month=1 retorna apenas lançamentos com competencia_year=2026 e competencia_month=1, independente da data da movimentação
result: [pending]

### 3. Saldo de família exclui contas inativas
expected: GET /finances/families/{family_uuid}/balance não inclui saldo de contas com is_active=False
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
