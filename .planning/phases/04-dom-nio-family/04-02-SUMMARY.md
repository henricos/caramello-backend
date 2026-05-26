---
phase: 04-dom-nio-family
plan: "02"
subsystem: dsl-generator
tags: [dsl, generator, refactor, url-convention, domain-plural]
dependency_graph:
  requires: ["04-01"]
  provides: ["04-03"]
  affects: ["scripts/generate_code.py", "dsl/entities/*", "dsl/operations/*"]
tech_stack:
  added: []
  patterns:
    - "DOMAIN_TO_ENTITY_NAME lookup explícito para derivação de nome de entidade canônica"
    - "URL prefix /{domain}/{table-with-hyphens} no generate_router"
key_files:
  created:
    - dsl/operations/family.yaml
  modified:
    - dsl/entities/user.yaml
    - dsl/entities/family.yaml
    - dsl/entities/family_member.yaml
    - dsl/entities/family_invitation.yaml
    - dsl/operations/user.yaml
    - scripts/generate_code.py
    - tests/test_generator.py
decisions:
  - "DOMAIN_TO_ENTITY_NAME como lookup explícito no topo do módulo — evita domain.title() producir 'Families' (classe inexistente)"
  - "url_table_name = table_name.replace('_', '-') — URLs usam hifens conforme D-10"
  - "_run_ruff_fix cobre ('user', 'family', 'users', 'families') com filtro exists() para transição gradual"
metrics:
  duration: "~15min"
  completed: "2026-05-26T18:53:16Z"
  tasks: 2
  files: 7
---

# Phase 4 Plan 02: DSL YAMLs e Generator Evolution Summary

Evoluiu os YAMLs do DSL e o generator para suportar domains plurais (`users`/`families`), nova convenção de URL com domain prefix e hifens, e o redesenho de `FamilyInvitation` (D-01).

## Tasks Completadas

### Task 1 — Atualizar YAMLs do DSL (commit `0ffd8ee`)

6 arquivos modificados/criados:

| Arquivo | Mudança |
|---------|---------|
| `dsl/entities/user.yaml` | `domain: user` → `domain: users` |
| `dsl/entities/family.yaml` | `domain: family` → `domain: families` |
| `dsl/entities/family_member.yaml` | `domain: family` → `domain: families` |
| `dsl/entities/family_invitation.yaml` | Redesenho completo (D-01): remove `invitee_email` e `expires_at`; adiciona `email` (str) e `status` com `default: "pending_login"` |
| `dsl/operations/user.yaml` | `domain: user` → `domain: users`; `path: /user/me` → `path: /users/me` |
| `dsl/operations/family.yaml` | **NOVO** — 6 operações: `registry_family`, `list_my_families`, `get_family_detail`, `pre_register_member`, `list_members`, `remove_member` |

### Task 2 — Evoluir scripts/generate_code.py (commit `de96db2`)

3 mudanças cirúrgicas + atualização de testes:

**Sub-task 2.1 — generate_router com domain prefix + hifens:**
- Adiciona `url_table_name = table_name.replace("_", "-")` no escopo da função
- Emite `prefix="/{domain}/{url_table_name}"` em vez de `prefix="/{table_name}"`
- Resultado: `FamilyInvitation` com `domain=families` e `table_name=family_invitation` gera `prefix="/families/family-invitation"`

**Sub-task 2.2 — _run_ruff_fix com dirs expandidos:**
- Cobre `("user", "family", "users", "families")` filtrados por `exists()` — suporta transição gradual sem falhar em dirs ausentes

**Sub-task 2.3 — generate_operations com DOMAIN_TO_ENTITY_NAME:**
- Adiciona constante `DOMAIN_TO_ENTITY_NAME: dict[str, str]` no topo do módulo com entradas para `user`, `users`, `family`, `families`
- Substitui `domain.title()` por `DOMAIN_TO_ENTITY_NAME[domain]` com `ValueError` explícito para domínio não mapeado
- Elimina a necessidade do sed manual previsto na Sub-task 1E do plano 04-03 — o stub gerado para `families` já produz `Family` (não `Families`) desde a primeira execução

**Sub-task 2.4 — testes pré-existentes atualizados:**
- `test_user_yaml_has_domain_field`: aceita `"user"` ou `"users"`
- `test_family_yamls_have_domain_field`: aceita `"family"` ou `"families"`
- `test_operations_user_yaml_exists`: aceita `domain in ("user", "users")` e `path in ("/user/me", "/users/me")`

## Testes do Plano 04-01 Destrabados (XFAIL → PASS)

Os seguintes testes que estavam em XFAIL no plano 04-01 agora passam diretamente:

1. `test_user_yaml_domain_is_users` — `dsl/entities/user.yaml` tem `domain: users`
2. `test_family_yamls_domain_is_families` — `family*.yaml` têm `domain: families`
3. `test_family_invitation_yaml_uses_pending_login_status` — sem `invitee_email`/`expires_at`; `status.default == "pending_login"`
4. `test_router_url_has_domain_prefix_and_hyphens` — `generate_router` emite `prefix="/families/family-invitation"`
5. `test_operations_user_yaml_path_is_users_me` — `get_me.path == "/users/me"`
6. `test_operations_family_yaml_exists_with_six_operations` — `dsl/operations/family.yaml` com 6 operações corretas

**Total: 16 testes passam; 0 falhas; 0 xfail persistentes.**

## Nota sobre Sub-task 1E do 04-03

A Sub-task 1E do plano 04-03 previa um `sed` para corrigir o output de `generate_operations` para domínio `families` (que emitia `Families` em vez de `Family`). Com a correção permanente via `DOMAIN_TO_ENTITY_NAME`, essa sub-task é agora uma verificação defensiva em vez de correção obrigatória — o generator produz stub correto desde a primeira execução.

## Deviations from Plan

None — plano executado exatamente como especificado.

## Known Stubs

Nenhum. Este plano não cria código em `src/caramello/` — apenas YAMLs de input e o generator.

## Threat Flags

Nenhuma nova superfície de segurança introduzida. As ameaças T-04-04, T-04-05 e T-04-20 do threat model foram mitigadas conforme planejado:
- YAMLs validados com `yaml.safe_load` no verify
- `DOMAIN_TO_ENTITY_NAME` explícito previne ImportError silencioso no stub gerado
- Testes em `tests/test_generator.py` asseguram o contrato de output do generator

## Próximo Plano

**04-03** — Regenerar código (cria `src/caramello/users/` e `src/caramello/families/`), migration Alembic, deletar diretórios antigos `user/` e `family/`, atualizar `main.py`.

## Self-Check: PASSED

- `dsl/operations/family.yaml` existe: FOUND
- `scripts/generate_code.py` modificado: commit `de96db2` verificado
- `tests/test_generator.py` modificado: commit `de96db2` verificado
- 16 testes passam: CONFIRMED
- `src/caramello/` não alterado: `git diff src/caramello/` vazio — CONFIRMED
- `alembic/` não alterado: `git diff alembic/` vazio — CONFIRMED
