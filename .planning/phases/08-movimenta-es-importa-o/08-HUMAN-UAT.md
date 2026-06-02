---
status: partial
phase: 08-movimenta-es-importa-o
source: [08-VERIFICATION.md]
started: 2026-06-02T22:05:00Z
updated: 2026-06-02T22:05:00Z
---

## Current Test

[aguardando teste humano]

## Tests

### 1. Aplicar e reverter migration 0003 em banco PostgreSQL real

expected: `uv run alembic upgrade head` executa sem erro; colunas `type` e `is_duplicate` ausentes na tabela `movement`; `uv run alembic downgrade -1` reverte sem erro
result: [pending]

**Passos:**
```bash
# 1. Subir para 0003
uv run alembic upgrade head

# 2. Verificar schema
psql -d caramello_dev -c "\d movement" | grep -E "type|is_duplicate"  # deve retornar vazio

# 3. Reverter
uv run alembic downgrade -1

# 4. Subir novamente
uv run alembic upgrade head
```

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
