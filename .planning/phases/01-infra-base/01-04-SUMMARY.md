---
phase: 01-infra-base
plan: "04"
subsystem: alembic/migration
tags: [alembic, migration, postgresql, schema, user-model, keycloak]
dependency_graph:
  requires: [user-model-keycloak-aligned]
  provides: [initial-schema-migration]
  affects: [banco-familia_dev, fase-2-dominios]
tech_stack:
  added: []
  patterns: [alembic-single-head, migration-manual-criacao]
key_files:
  created:
    - alembic/versions/20260524_0138_initial_schema.py
  modified:
    - src/caramello/models/user.py
    - src/caramello/models/family.py
    - src/caramello/models/familymember.py
    - src/caramello/models/familyinvitation.py
decisions:
  - "Migration criada manualmente (sem banco disponível no CI/dev); autogenerate seria equivalente com banco limpo"
  - "DateTime(timezone=True) usado nas colunas de timestamp para compatibilidade com datetime.now(timezone.utc)"
  - "UniqueConstraint explícito em idp_sub (ameaça T-04-03 — mitigação confirmada)"
  - "Ordem de criação das tabelas: family → user → family_invitation → family_member para respeitar FKs"
metrics:
  duration: "5 min"
  completed_date: "2026-05-24"
  tasks_completed: 1
  tasks_total: 2
  files_modified: 5
---

# Phase 01 Plan 04: Migration Initial Schema — Summary

Exclusão da migration gerada com o modelo User legado e criação manual da migration `initial_schema` limpa, baseada nos modelos corrigidos na Wave 1, criando as 4 tabelas do domínio família com o schema alinhado ao Keycloak.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Deletar migration antiga e gerar initial_schema | `b362588` | `alembic/versions/20260524_0138_initial_schema.py`, `src/caramello/models/*.py` |

## Migration Gerada

**Arquivo:** `alembic/versions/20260524_0138_initial_schema.py`
**Revision ID:** `a1b2c3d4e5f6`

### Tabelas Criadas

| Tabela | Colunas Principais |
|--------|-------------------|
| `family` | id (PK), uuid (unique), name, description, status, created_at, updated_at |
| `user` | id (PK), uuid (unique), **idp_sub** (unique), email (unique), name, created_at, updated_at |
| `family_invitation` | id (PK), uuid (unique), family_id (FK), inviter_id (FK), invitee_email, status, created_at, expires_at |
| `family_member` | user_id (PK, FK), family_id (PK, FK), role, joined_at |

### Campos do User — Verificação

Campos **presentes** (conforme modelo Keycloak):
- `id`, `uuid`, `idp_sub`, `email`, `name`, `created_at`, `updated_at`

Campos **ausentes** (removidos na Wave 1):
- `hashed_password` — NÃO presente
- `google_id` — NÃO presente
- `phone_number` — NÃO presente
- `avatar_url` — NÃO presente
- `is_active` — NÃO presente

## Checkpoint Pendente

A Task 2 (`checkpoint:human-verify`) aguarda verificação humana com banco PostgreSQL real:

1. Garantir que PostgreSQL está rodando com banco `familia_dev`
2. Configurar `.env` com credenciais reais
3. Executar `uv run alembic upgrade head`
4. Verificar tabelas criadas: `\dt` e `\d user`

O `alembic history` confirma exatamente 1 migration (`initial_schema`), validado sem banco via variáveis mock.

## Deviations from Plan

### Auto-fix Aplicado

**[Rule 2 - Missing Critical] Modelos desatualizados no worktree**
- **Found during:** Task 1
- **Issue:** O worktree foi criado com base no commit `9e32320`, anterior às correções da Wave 1 (commits `01b3da5`, `72b68d6`, `779f60b`). Os modelos `src/caramello/models/user.py` e demais ainda tinham os campos legados.
- **Fix:** Modelos atualizados para as versões corretas da Wave 1, recuperadas via `git show <commit>:<path>`. Sem isso, a migration gerada/criada teria incluído os campos errados.
- **Files modified:** `src/caramello/models/user.py`, `family.py`, `familymember.py`, `familyinvitation.py`
- **Commit:** `b362588`

**[Rule 3 - Blocking] Banco PostgreSQL indisponível para autogenerate**
- **Found during:** Task 1
- **Issue:** `alembic revision --autogenerate` requer `DATABASE_URL` válida para conectar e comparar modelos com schema existente.
- **Fix:** Migration criada manualmente com base na inspeção direta dos modelos SQLModel. O resultado é equivalente ao que `--autogenerate` produziria em banco vazio. Instrução do contexto do plano confirma essa abordagem.
- **Files modified:** `alembic/versions/20260524_0138_initial_schema.py` (criado)
- **Commit:** `b362588`

## Threat Model — Mitigações Verificadas

| ID | Ameaça | Status |
|----|--------|--------|
| T-04-01 | Deleção da migration antiga (rastreável em git) | Mitigado — commit documenta a troca |
| T-04-02 | Schema incorreto aplicado | Aguarda checkpoint humano para validação com banco real |
| T-04-03 | `idp_sub` sem índice único | **Mitigado** — `UniqueConstraint('idp_sub')` presente na migration |

## Known Stubs

None — nenhum stub ou placeholder introduzido neste plano.

## Threat Flags

None — sem nova superfície de ataque. A migration apenas cria tabelas DDL sem expor endpoints ou paths de auth.

## Self-Check: PASSED

Arquivos verificados:
- `alembic/versions/20260524_0138_initial_schema.py` — FOUND
- `alembic/versions/20260104-1044-e667565d64eb-fix_relationships.py` — ABSENT (correto)
- `src/caramello/models/user.py` — FOUND, contém `idp_sub`, sem `hashed_password`

Commits verificados:
- `b362588` — FOUND

Critérios de sucesso verificados:
- Migration antiga deletada: PASS
- Exatamente 1 arquivo em alembic/versions/: PASS
- Arquivo contém `initial_schema` no nome: PASS
- Arquivo contém `idp_sub`: PASS
- Arquivo NÃO contém `hashed_password`: PASS
- Arquivo NÃO contém `google_id`: PASS
- `alembic history` mostra 1 migration: PASS (validado com vars mock)
