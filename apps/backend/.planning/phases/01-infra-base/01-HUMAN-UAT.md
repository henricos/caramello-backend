---
status: partial
phase: 01-infra-base
source: [01-VERIFICATION.md]
started: 2026-05-24T12:00:00Z
updated: 2026-05-24T12:00:00Z
---

## Current Test

[aguardando validação humana]

## Tests

### 1. Verificar que `alembic upgrade head` aplica a migration corretamente no banco `familia_dev`

expected: Comando conclui sem erro; `\dt` lista as tabelas user, family, family_member, family_invitation; `\d user` mostra colunas id, uuid, idp_sub, email, name, created_at, updated_at — SEM hashed_password, google_id, phone_number, is_active
result: [pending]

**Passos:**
1. Garantir PostgreSQL rodando com banco `familia_dev` (`bin/setup_db` se necessário)
2. Copiar credenciais: `cp .env.example .env` e preencher `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`
3. Aplicar migration: `uv run alembic upgrade head`
4. Verificar schema:
   ```
   psql -U $DB_USER -d familia_dev -c "\dt"
   psql -U $DB_USER -d familia_dev -c "\d user"
   ```
5. Confirmar que a tabela `user` não contém `hashed_password`, `google_id`, `phone_number`, `is_active`

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
