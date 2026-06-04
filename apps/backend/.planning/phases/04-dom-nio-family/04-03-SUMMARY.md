---
phase: 04-dom-nio-family
plan: "03"
subsystem: domain-restructuring
tags: [dsl, code-generation, domain-plural, alembic, migration, tests]
dependency_graph:
  requires: ["04-02"]
  provides: ["04-04"]
  affects:
    - src/caramello/users/
    - src/caramello/families/
    - src/caramello/main.py
    - src/caramello/shared/auth.py
    - alembic/env.py
    - alembic/versions/
    - tests/
tech_stack:
  added: []
  patterns:
    - "Regeneração DSL: bin/generate_code gera users/ e families/ a partir de YAMLs plurais"
    - "Anotação CARAMELLO-GENERATED: implemented protege users/operations.py contra sobrescrita"
    - "Migration manual cirúrgica com server_default temporário (Pitfall 5 do RESEARCH)"
    - "pytest.xfail para testes funcionais que aguardam plano 04-04"
key_files:
  created:
    - src/caramello/users/__init__.py
    - src/caramello/users/models.py
    - src/caramello/users/router.py
    - src/caramello/users/operations.py
    - src/caramello/families/__init__.py
    - src/caramello/families/models.py
    - src/caramello/families/router.py
    - src/caramello/families/operations.py
    - alembic/versions/20260526_1500_redesign_family_invitation_pre_register.py
  modified:
    - src/caramello/main.py
    - src/caramello/shared/auth.py
    - alembic/env.py
    - tests/test_auth.py
    - tests/test_user_operations.py
    - tests/test_generator.py
    - tests/test_family_operations.py
  deleted:
    - src/caramello/user/ (diretório completo — 4 arquivos)
    - src/caramello/family/ (diretório completo — 3 arquivos)
decisions:
  - "Generator rodado no main repo — arquivos copiados para worktree (isolamento de worktree)"
  - "users/operations.py preservado com anotação 'implemented' antes do generator (CARAMELLO-GENERATED protected)"
  - "families/operations.py stub com caminho feliz: DOMAIN_TO_ENTITY_NAME do 04-02 funcionou (sem sed necessário)"
  - "Migration manual em vez de autogenerate — evita ruído de diff (T-04-09)"
  - "test_auto_join_on_login marcado xfail — módulo families/ agora existe mas auto-join aguarda plano 04-04"
  - "test_families_operations_router_paths corrigido: route.path em FastAPI é path completo (inclui decorator path)"
  - "Bug Rule 1: generate_router emitia 'from caramello.user.models import User' para domain='users' (condição checava só 'user'); corrigido nos routers gerados"
  - "Bug Rule 1: shared/auth.py importava caramello.user.models (TYPE_CHECKING e runtime); corrigido para caramello.users.models"
metrics:
  duration: "~15min"
  completed: "2026-05-26T19:05:51Z"
  tasks: 5
  files: 16
---

# Phase 4 Plan 03: Regeneração de Código e Migração Estrutural Summary

Executa o "ponto sem volta" da Phase 4: diretórios `user/` e `family/` removidos; `users/` e `families/` criados com código regenerado pelo DSL; `main.py` e `alembic/env.py` atualizados; migration para `family_invitation` criada; suite de testes verde.

## Tasks Completadas

### Task 1 — Preservar users/operations.py + Regenerar + Deletar antigos (commit `cc773f4`)

Sub-tasks 1A-1C executadas em sequência:

- **1A**: `src/caramello/users/__init__.py` e `src/caramello/users/operations.py` criados com anotação `# CARAMELLO-GENERATED: implemented` e prefix `/users` (adaptado de `user/operations.py`)
- **1B**: `bin/generate_code` rodado no main repo (worktree compartilha o código fonte); arquivos gerados copiados para worktree. Output:
  ```
  wrote src/caramello/users/models.py
  wrote src/caramello/users/router.py
  wrote src/caramello/families/models.py
  wrote src/caramello/families/router.py
  wrote src/caramello/families/operations.py
  wrote src/caramello/users/operations.py  ← gerou em main repo mas worktree preservou 'implemented'
  ```
- **1C**: `src/caramello/user/` e `src/caramello/family/` removidos; caches Python limpos

### Task 2 — Verificar invariantes + correção defensiva (sem commit separado — verificação pura)

**Sub-task 2A** — Invariantes confirmados:
- `users/router.py`: `prefix="/users/user"` ✓
- `families/router.py`: `prefix="/families/family"` e `prefix="/families/family-invitation"` ✓
- `users/operations.py`: `prefix="/users"`, anotação `implemented` ✓
- `families/operations.py`: `prefix="/families"`, anotação `stub` ✓
- `families/models.py`: sem `invitee_email`, sem `expires_at`; tem `email` e `status` ✓

**Sub-task 2B** — Verificação defensiva: **caminho feliz**. O fix do plano 04-02 (DOMAIN_TO_ENTITY_NAME) funcionou — o stub gerou `FamilyRead/FamilyCreate/FamilyUpdate` diretamente sem necessidade de `sed`.

Módulo importa sem erro:
```
OK module imports
router prefix: /families
source: .../src/caramello/families/operations.py
```

### Task 3 — Atualizar main.py + alembic/env.py (commit `3119c22`)

- `main.py`: imports `caramello.users.*` e `caramello.families.*`; ordem `operations` antes de `router` (D-06); 27 rotas registradas; `/families/registry` (idx 10) antes de `/families/family/{uuid}` (idx 18) ✓
- `alembic/env.py`: imports `caramello.users.models` e `caramello.families.models`
- **Desvio (Rule 1)**: `users/router.py` e `families/router.py` tinham `from caramello.user.models import User` (bug do generator: condição `if domain == "user"` não cobria `domain == "users"`). Corrigido inline.

### Task 4 — Migration Alembic para family_invitation (commit `620eeff`)

Migration `20260526_1500_redesign_family_invitation_pre_register.py` criada manualmente:
- `down_revision = "a1b2c3d4e5f6"` (revision do initial_schema)
- `revision = "0b1c2d3e4f5a"`
- `upgrade()`: drop `invitee_email` + drop `expires_at`; add `email` (NOT NULL) + add `status` (NOT NULL, default `pending_login`)
- Server defaults temporários para satisfazer NOT NULL em linhas pré-existentes (PATTERNS.md Pattern 5)
- `downgrade()`: reverte adicionando `invitee_email` e `expires_at`
- Migration validada estaticamente com importlib; ruff limpo

### Task 5 — Atualizar testes (commit `1403605`)

4 arquivos de teste atualizados + 1 arquivo de produção corrigido:

| Arquivo | Mudança |
|---------|---------|
| `tests/test_auth.py` | `/user/me` → `/users/me`; `/user/` → `/users/user/`; xfail em `test_auto_join_on_login` |
| `tests/test_user_operations.py` | `/user/me` → `/users/me`; imports `caramello.users.models`; path `src/caramello/users/operations.py` |
| `tests/test_generator.py` | Todos os paths singulares → plurais; `test_legacy_paths_removed` verifica remoção de `user/` e `family/` |
| `tests/test_family_operations.py` | `test_families_operations_router_paths` corrigido para paths completos; 5 testes funcionais + annotation marcados `xfail` |
| `src/caramello/shared/auth.py` | **Desvio (Rule 1)**: imports `caramello.user.models` → `caramello.users.models` (TYPE_CHECKING + runtime lazy import) |

**Estado final da suite pytest:** 24 passed, 1 skipped, 7 xfailed, 0 failed

## Saída do bin/generate_code

```
Starting Code Generation...
  wrote .../src/caramello/users/models.py
  wrote .../src/caramello/users/router.py
  wrote .../src/caramello/families/models.py
  wrote .../src/caramello/families/router.py
  wrote .../src/caramello/families/operations.py
  wrote .../src/caramello/users/operations.py  ← em main repo; worktree preservou 'implemented'
Generation Complete.
```

## Task 2 — Confirmação

**Caminho feliz:** fix do 04-02 (DOMAIN_TO_ENTITY_NAME) produziu imports corretos desde a primeira execução. Nenhuma correção via `sed` necessária.

## Migration (Task 4) — Confirmação

- `revision = "0b1c2d3e4f5a"`
- `down_revision = "a1b2c3d4e5f6"` (initial_schema)
- Aplicação: `alembic upgrade head` (operador em ambiente dev `familia_dev`)

## Estado dos Testes Phase 4

| Teste | Estado | Razão |
|-------|--------|-------|
| `test_auth_module` | PASS | módulo importa ✓ |
| `test_me_unauthenticated` | PASS | `/users/me` sem token → 403 ✓ |
| `test_user_crud_requires_auth` | PASS | `/users/user/` sem token → 403 ✓ |
| `test_jwt_decode_only_accepts_rs256` | PASS | código não alterado |
| `test_auto_join_on_login` | XFAIL | auto-join aguarda plano 04-04 |
| `test_get_me_returns_user_fields` | PASS | mock get_current_user → `/users/me` ✓ |
| `test_operations_annotation_is_implemented` (user) | PASS | anotação `implemented` ✓ |
| `test_families_operations_module_exists` | PASS | módulo criado ✓ |
| `test_operations_annotation_is_implemented` (family) | XFAIL | ainda é stub (04-04) |
| `test_families_operations_router_paths` | PASS | 6 paths corretos ✓ |
| `test_registry_creates_family_and_owner` | XFAIL | stub (04-04) |
| `test_list_families_only_mine` | XFAIL | stub (04-04) |
| `test_get_family_detail_non_member_returns_403` | XFAIL | stub (04-04) |
| `test_pre_register_member_non_owner_returns_403` | XFAIL | stub (04-04) |
| `test_remove_member_non_owner_returns_403` | XFAIL | stub (04-04) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] generate_router emitia import caramello.user.models para domain=users**
- **Encontrado durante:** Task 3 (app não bootava — ModuleNotFoundError)
- **Causa raiz:** `generate_router()` em `scripts/generate_code.py` tem condição `if domain == "user": user_import_line = ""` que não cobre `domain == "users"`. Para `users`, emitia `from caramello.user.models import User` (singular) além do import correto `caramello.users.models`.
- **Fix:** Removida a linha duplicada/incorreta de `users/router.py` e `families/router.py` (arquivos gerados, não o generator — fix permanente do generator fica para plano 04-04 ou como deferred item).
- **Arquivos modificados:** `src/caramello/users/router.py`, `src/caramello/families/router.py`
- **Commit:** `3119c22`

**2. [Rule 1 - Bug] shared/auth.py importava caramello.user.models (singular)**
- **Encontrado durante:** Task 5 (test_auto_join_on_login falhava com ModuleNotFoundError)
- **Causa raiz:** `src/caramello/shared/auth.py` nunca foi atualizado para usar o path plural quando o plano 03-05 criou a estrutura.
- **Fix:** Substituído `from caramello.user.models import User` por `from caramello.users.models import User` em 2 locais: bloco `TYPE_CHECKING` (linha 37) e import lazy em `get_current_user` (linha 115).
- **Arquivos modificados:** `src/caramello/shared/auth.py`
- **Commit:** `1403605`

**3. [Rule 1 - Bug] test_families_operations_router_paths com paths incorretos**
- **Encontrado durante:** Task 5 (teste falhava — paths esperados não batiam com os reais)
- **Causa raiz:** Comentário no teste dizia que `route.path` é sub-path relativo ao prefix, mas FastAPI/Starlette armazena o decorator path completo. O teste esperava `/registry` mas o router tem `/families/registry`.
- **Fix:** Atualizado o conjunto `expected` para usar paths completos.
- **Arquivos modificados:** `tests/test_family_operations.py`
- **Commit:** `1403605`

**4. [Rule 2 - Funcionalidade ausente] test_auto_join_on_login desbloqueado sem implementação**
- **Encontrado durante:** Task 5 (teste passou do skip para FAIL com módulo families/ existindo)
- **Contexto:** O teste usava `importorskip("caramello.families.models")` como guard. Com o módulo criado, o guard passou e o teste executou — mas a lógica de auto-join ainda não está em `shared/auth.py` (aguarda plano 04-04).
- **Fix:** Adicionado `pytest.xfail(...)` após `importorskip`, documentando que a implementação vem no 04-04.
- **Arquivos modificados:** `tests/test_auth.py`
- **Commit:** `1403605`

## Known Stubs

`src/caramello/families/operations.py` — 6 endpoints como `NotImplementedError`. Intencional: implementação real no plano 04-04. Testes correspondentes marcados como `xfail`.

## Próximo Plano

**04-04** — Implementar `src/caramello/families/operations.py` (lógica real dos 6 endpoints de negócio) + estender `shared/auth.py` com auto-join automático ao detectar `FamilyInvitation` pendente para o email do usuário.

## Self-Check: PASSED

- `src/caramello/users/` existe: FOUND
- `src/caramello/families/` existe: FOUND
- `src/caramello/user/` removido: CONFIRMED
- `src/caramello/family/` removido: CONFIRMED
- `head -1 src/caramello/users/operations.py` == `# CARAMELLO-GENERATED: implemented`: CONFIRMED
- `head -1 src/caramello/families/operations.py` == `# CARAMELLO-GENERATED: stub`: CONFIRMED
- `alembic/versions/20260526_1500_redesign_family_invitation_pre_register.py`: FOUND
- Commits: `cc773f4`, `3119c22`, `620eeff`, `1403605`: CONFIRMED
- pytest: 24 passed, 1 skipped, 7 xfailed, 0 failed: CONFIRMED
