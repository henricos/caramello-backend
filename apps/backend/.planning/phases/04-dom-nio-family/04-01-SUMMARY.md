---
phase: "04-dom-nio-family"
plan: "01"
subsystem: "tests"
tags: [tdd, wave-0, family-domain, test-contracts]
dependency_graph:
  requires: []
  provides:
    - "Wave 0 TDD seed para FAMILY-01, FAMILY-02, FAMILY-03, FAMILY-07"
    - "Contratos de test para planos 04-02, 04-03, 04-04"
  affects:
    - "tests/test_family_operations.py"
    - "tests/test_auth.py"
    - "tests/test_generator.py"
    - ".planning/phases/04-dom-nio-family/04-VALIDATION.md"
tech_stack:
  added: []
  patterns:
    - "pytest.importorskip para TDD seed — testes skipam até módulo existir"
    - "dependency_overrides + TestClient sem lifespan para testes de ops"
    - "xfail para contratos de invariantes ainda não implementados"
key_files:
  created:
    - path: "tests/test_family_operations.py"
      description: "8 testes skeleton para FAMILY-01/02/03/07 + router paths + anotação"
  modified:
    - path: "tests/test_auth.py"
      description: "Adiciona test_auto_join_on_login (D-02) com mock de session"
    - path: "tests/test_generator.py"
      description: "Adiciona 6 invariantes xfail para plano 04-02 (D-01/D-09/D-10/D-11)"
    - path: ".planning/phases/04-dom-nio-family/04-VALIDATION.md"
      description: "Frontmatter nyquist_compliant=true, wave_0_complete=true; Wave 0 items ✅"
decisions:
  - "Usar pytest.importorskip em vez de pytest.skip global — garante coleta limpa sempre"
  - "Testes de generator usam xfail em vez de skip — documenta expectativa de comportamento futuro"
  - "Sub-paths do router verificados sem o prefix (route.path relativo, não absoluto)"
metrics:
  duration: "~7min"
  completed_date: "2026-05-26"
  tasks_completed: 2
  files_changed: 4
---

# Phase 04 Plan 01: TDD Seed Wave 0 — Family Domain Test Contracts

Cria contratos de teste (Wave 0) que guiarão a implementação dos planos 04-02, 04-03 e 04-04. Todos os testes são estruturalmente válidos (coletáveis pelo pytest) mas funcionalmente skipados/xfailed enquanto a implementação ainda não existe.

## Tasks Executadas

### Task 1: Criar tests/test_family_operations.py

Commit: `2c8657c`
Arquivo criado: `tests/test_family_operations.py` (8 funções de teste)

**Testes adicionados:**

| Função | Requisito | Comportamento esperado |
|--------|-----------|------------------------|
| `test_families_operations_module_exists` | D-07 | Módulo families/operations existe |
| `test_operations_annotation_is_implemented` | D-07 | Primeira linha == `# CARAMELLO-GENERATED: implemented` |
| `test_families_operations_router_paths` | D-07 | 6 sub-paths exatos registrados no router |
| `test_registry_creates_family_and_owner` | FAMILY-01 / D-13 | POST cria Family + FamilyMember(role='owner') |
| `test_list_families_only_mine` | FAMILY-02 | GET filtra por membership do usuário |
| `test_get_family_detail_non_member_returns_403` | FAMILY-03 | 403 para usuário não-membro |
| `test_pre_register_member_non_owner_returns_403` | D-07 | 403 sem role owner |
| `test_remove_member_non_owner_returns_403` | FAMILY-07 | 403 sem role owner |

Padrão: `pytest.importorskip("caramello.families.operations")` em cada teste funcional — skip limpo até plano 04-04.

### Task 2: Ampliar test_auth.py, test_generator.py e atualizar 04-VALIDATION.md

Commit: `26ca20e`

**tests/test_auth.py — 1 função adicionada:**

| Função | Requisito | Comportamento esperado |
|--------|-----------|------------------------|
| `test_auto_join_on_login` | D-02 | Auto-join cria FamilyMember(role="member") + invitation.status="joined" |

Skipa via `pytest.importorskip("caramello.families.models")` até plano 04-03.

**tests/test_generator.py — 6 funções adicionadas:**

| Função | Requisito | Comportamento esperado |
|--------|-----------|------------------------|
| `test_user_yaml_domain_is_users` | D-09 | user.yaml.domain == "users" (xfail) |
| `test_family_yamls_domain_is_families` | D-09 | family*.yaml.domain == "families" (xfail) |
| `test_family_invitation_yaml_uses_pending_login_status` | D-01 | Campos redesenhados (xfail) |
| `test_router_url_has_domain_prefix_and_hyphens` | D-09/D-10/D-11 | prefix="/families/family-invitation" (xfail) |
| `test_operations_user_yaml_path_is_users_me` | D-11 | get_me.path == "/users/me" (xfail) |
| `test_operations_family_yaml_exists_with_six_operations` | D-05/D-07 | 6 operações em family.yaml (xfail) |

**04-VALIDATION.md atualizado:**
- `nyquist_compliant: true`
- `wave_0_complete: true`
- 3 itens Wave 0 marcados como `[x] ✅`
- Tabela Per-Task Verification Map: `❌ Wave 0` → `✅ Wave 0 done`

## Verificações de Suite

```
uv run pytest tests/test_family_operations.py -q
→ 8 skipped (todos passam skip corretamente)

uv run pytest tests/test_auth.py tests/test_generator.py -q
→ 1 failed, 11 passed, 2 skipped, 6 xfailed, 2 errors
  (failures/errors são pré-existentes — sem ENV do banco configurado;
   nenhum FAIL novo introduzido por este plano)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrige docstrings longas (E501) pré-existentes em test_generator.py**
- **Found during:** Task 2 — ruff check no arquivo modificado
- **Issue:** 4 docstrings em testes pré-existentes ultrapassavam 88 chars e fariam ruff falhar no arquivo modificado
- **Fix:** Shortenou docstrings nas linhas 36, 58, 91, 121 do test_generator.py para ficar dentro do limite
- **Files modified:** `tests/test_generator.py`
- **Commit:** `26ca20e`

## Known Stubs

Nenhum. Este plano produz apenas arquivos de teste com contratos intencionalmente skipados/xfailed — não há stubs de dados em código de produção.

## Threat Flags

Nenhuma superfície nova de segurança introduzida. Verificação T-04-02:
- `grep -c "KEYCLOAK" tests/test_auth.py` == 0 ✅
- Tokens mockados com strings estáticas sem segredos reais

## Próximo Plano

04-02: Generator + DSL updates — implementa `domain` plural, URLs com hifens, redesenha family_invitation.yaml. Destrava os 6 xfails do test_generator.py adicionados neste plano.

## Self-Check: PASSED

Arquivos criados/modificados verificados:
- `tests/test_family_operations.py` — FOUND ✅
- `tests/test_auth.py` — FOUND ✅
- `tests/test_generator.py` — FOUND ✅
- `.planning/phases/04-dom-nio-family/04-VALIDATION.md` — FOUND ✅

Commits verificados:
- `2c8657c` — FOUND ✅
- `26ca20e` — FOUND ✅
