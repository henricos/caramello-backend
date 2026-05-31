---
status: partial
phase: 06-fundacao-dsl-schema
source: [06-VERIFICATION.md]
started: 2026-05-31T09:30:00Z
updated: 2026-05-31T09:30:00Z
---

## Current Test

[aguardando verificação humana no banco caramello_dev]

## Tests

### 1. SC-1: alembic upgrade head sem erro

expected: `uv run alembic upgrade head` retorna código 0 e cria as 5 tabelas
result: [pending]

### 2. SC-2: alembic downgrade -1 reverte limpo

expected: `uv run alembic downgrade -1` remove as 5 tabelas sem erro
result: [pending]

### 3. SC-3: schema correto via psql

expected: `\d+ movement` mostra amount como numeric(15,2), UNIQUE em import_hash; `\d+ financial_entry` mostra UNIQUE em movement_id, sem colunas amount/type
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
