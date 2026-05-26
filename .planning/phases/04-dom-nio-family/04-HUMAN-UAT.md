---
status: partial
phase: 04-dom-nio-family
source: [04-VERIFICATION.md]
started: 2026-05-26T00:00:00Z
updated: 2026-05-26T00:00:00Z
---

## Current Test

[aguardando teste humano]

## Tests

### 1. Aplicação da migration Alembic

expected: `alembic upgrade head` executa contra `familia_dev` sem erro (exit 0); colunas `invitee_email` e `expires_at` removidas; colunas `email` e `status` (default `pending_login`) adicionadas na tabela `family_invitation`.
result: [pending]

### 2. Fluxo E2E de auto-join (D-02)

expected: Pré-registrar um email via `POST /families/families/{uuid}/pre-register`, autenticar esse usuário via Keycloak, e confirmar que ele automaticamente se torna `FamilyMember(role=member)` na primeira requisição autenticada — sem nenhuma ação explícita de join.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
