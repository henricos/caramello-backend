---
phase: 01-infra-base
plan: "01"
subsystem: dsl/user-model
tags: [dsl, user, keycloak, datetime, code-generation]
dependency_graph:
  requires: []
  provides: [user-model-keycloak-aligned, dsl-datetime-modern]
  affects: [alembic-migration, keycloak-jit-provisioning]
tech_stack:
  added: []
  patterns: [dsl-first, keycloak-idp-sub]
key_files:
  created: []
  modified:
    - dsl/entities/user.yaml
    - scripts/generate_code.py
    - src/caramello/models/user.py
    - src/caramello/models/family.py
    - src/caramello/models/familyinvitation.py
    - src/caramello/models/familymember.py
    - tests/generated/test_user.py
decisions:
  - "Campo idp_sub adicionado como str unique not-null para JIT provisioning via Keycloak (Phase 3)"
  - "full_name renomeado para name para consistência com naming conventions"
  - "Campos de auth local removidos: hashed_password, phone_number, google_id, avatar_url, is_active"
  - "datetime.utcnow substituído por lambda: datetime.now(timezone.utc) em todos os modelos gerados"
metrics:
  duration: "2 min"
  completed_date: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 7
---

# Phase 01 Plan 01: User Model Keycloak Alignment — Summary

Correção da definição do modelo User no DSL YAML para alinhamento com Keycloak (sem campos de auth local, com `idp_sub`), correção do gerador DSL para emitir `datetime.now(timezone.utc)` em vez do `datetime.utcnow` deprecated, e regeneração de todos os artefatos derivados.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Corrigir dsl/entities/user.yaml — modelo alinhado com Keycloak | `01b3da5` | `dsl/entities/user.yaml` |
| 2 | Corrigir scripts/generate_code.py — datetime moderno e imports | `72b68d6` | `scripts/generate_code.py` |
| 3 | Regenerar artefatos — executar bin/generate_code | `779f60b` | `src/caramello/models/user.py`, + 4 arquivos |

## Campos Finais do Modelo User

| Campo | Tipo | Restrições | Observação |
|-------|------|-----------|------------|
| `id` | `int` | primary_key | PK interno |
| `uuid` | `UUID` | unique, not null | Identificador público |
| `idp_sub` | `str` | unique, not null | Subject JWT do Keycloak (NOVO) |
| `email` | `EmailStr` | unique, not null | E-mail único do usuário |
| `name` | `str` | max_length=100, not null | Nome do usuário (era `full_name`) |
| `created_at` | `datetime` | not null | Timestamp criação |
| `updated_at` | `datetime` | not null | Timestamp última atualização |

Campos **removidos**: `hashed_password`, `phone_number`, `google_id`, `avatar_url`, `is_active`

## Fix de datetime no Gerador

**Antes:**
```python
field_args.append("default_factory=datetime.utcnow")
"from datetime import datetime"
```

**Depois:**
```python
field_args.append("default_factory=lambda: datetime.now(timezone.utc)")
"from datetime import datetime, timezone"
```

A correção elimina o `DeprecationWarning` do Python 3.12+ e se aplica a todos os modelos gerados (User, Family, FamilyInvitation, FamilyMember).

## Deviations from Plan

None — plano executado exatamente como escrito.

## Known Stubs

None — nenhum stub ou placeholder introduzido neste plano.

## Threat Flags

None — sem nova superfície de ataque introduzida. A remoção de `hashed_password` do schema Read (ameaça T-01-02 do threat model) foi confirmada: o campo não existe mais no YAML, portanto não pode ser emitido em nenhum schema gerado.

## Self-Check: PASSED

Arquivos verificados:
- `dsl/entities/user.yaml` — FOUND, contém `idp_sub`, sem `hashed_password`
- `scripts/generate_code.py` — FOUND, contém `timezone.utc`, sem `utcnow`
- `src/caramello/models/user.py` — FOUND, sintaxe válida, contém `idp_sub`, sem `hashed_password`

Commits verificados:
- `01b3da5` — FOUND
- `72b68d6` — FOUND
- `779f60b` — FOUND
