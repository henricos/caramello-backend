---
phase: 03-estrutura-por-dom-nios-e-autentica-o
plan: "05"
subsystem: integration
tags: [integration, domain, auth, alembic, ruff, mypy, cleanup, wave-3]

dependency_graph:
  requires:
    - 03-03 (generator evoluído com suporte a domain + operations)
    - 03-04 (shared/auth.py com Keycloak JWT)
  provides:
    - src/caramello/user/{__init__.py,models.py,router.py,operations.py}
    - src/caramello/family/{__init__.py,models.py,router.py}
    - main.py com lifespan + fetch_jwks + routers dos domínios
    - alembic/env.py com imports dos novos paths
    - pyproject.toml sem excludes obsoletos para ruff/mypy
    - generator corrigido: sem import circular, ruff-fix automático no pipeline
  affects:
    - Keycloak real (Task 7 — validação E2E pelo operador)
    - Alembic migrations (alembic upgrade head verifica schemas)

tech_stack:
  added: []
  patterns:
    - Late-bind de link_model cross-domain via RelationshipInfo.link_model = _Class após definição
    - TYPE_CHECKING para imports que causariam ciclo (user ← family)
    - Link models definidos antes de entidades que os referenciam no arquivo consolidado
    - isort skip_file em main.py para preservar ordem de importação intencional
    - Ruff --fix + ruff format como etapa final do pipeline de geração

key_files:
  created:
    - src/caramello/user/__init__.py
    - src/caramello/user/models.py
    - src/caramello/user/router.py
    - src/caramello/user/operations.py
  modified:
    - src/caramello/family/__init__.py
    - src/caramello/family/models.py
    - src/caramello/family/router.py
    - src/caramello/main.py
    - alembic/env.py
    - pyproject.toml
    - scripts/generate_code.py

decisions:
  - Import circular user<->family resolvido com TYPE_CHECKING + late-bind em user/models.py
  - isort skip_file em main.py para manter ordem de import intencional (user antes de family)
  - Generator corrigido: _build_domain_fk_graph() detecta ciclos; _consolidate_models() gera late-bind
  - Link models reordenados para aparecer antes das entidades que os referenciam
  - ruff --fix integrado ao pipeline do generator para garantir conformidade automática

metrics:
  duration: "~90 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 6
  tasks_total: 7
  files_created: 5
  files_modified: 7
---

# Phase 3 Plan 05: Integração Final — Wiring do Codebase por Domínio Summary

**One-liner:** Wiring completo da Phase 3: código regenerado em src/caramello/{user,family}/, main.py com lifespan + JWKS fetch, diretórios obsoletos removidos, ruff e mypy passando em src/ inteiro.

## Tasks Executadas

| Task | Nome | Commit | Arquivos Principais |
|------|------|--------|---------------------|
| 1 | Atualizar alembic/env.py para novos paths | 13fcbe2 | alembic/env.py |
| 2 | Limpar pyproject.toml — remover excludes obsoletos | a6c709f | pyproject.toml |
| 3 | Rodar bin/generate_code + corrigir generator | edd2524 | src/caramello/user/*, src/caramello/family/* |
| 4 (mypy fix) | Corrigir erros mypy — type: ignore em RelationshipInfo e User.__table__ | cefffc8 | user/models.py, shared/auth.py |
| 3 (generator fix) | Corrigir generator para evitar imports circulares + ruff-fix | 42c2f3c | scripts/generate_code.py + arquivos gerados |
| 5 | Implementar GET /user/me — anotação implemented | 42c2f3c | src/caramello/user/operations.py |
| 6 | Remover diretórios obsoletos + main.py com lifespan | 76d34b9 | src/caramello/main.py + remoção de 17 arquivos |
| 7 | Checkpoint humano E2E | — | Aguardando operador |

## Verificação Final

```
uv run ruff check src/
```
Resultado: **All checks passed!** (14 source files, sem exclusões)

```
uv run mypy src/
```
Resultado: **Success: no issues found in 14 source files**

```
uv run pytest tests/test_generator.py tests/test_auth.py tests/test_user_operations.py -x -q
```
Resultado: **4 passed, 1 skipped, 1 xfailed, 11 xpassed**

### Critérios de aceitação verificados

| Critério | Resultado |
|----------|-----------|
| `src/caramello/user/` contém models.py, router.py, operations.py | OK |
| `src/caramello/family/` contém models.py e router.py | OK |
| `src/caramello/models/` não existe mais | OK |
| `src/caramello/api/` não existe mais | OK |
| `tests/generated/` não existe mais | OK |
| `alembic/env.py` importa de caramello.user.models e caramello.family.models | OK |
| `main.py` registra lifespan que chama fetch_jwks no startup | OK |
| `main.py` inclui routers de user.router, user.operations e family.router | OK |
| `user/operations.py` tem anotação `# CARAMELLO-GENERATED: implemented` no topo | OK |
| `user/operations.py` GET /user/me retorna current_user | OK |
| `pyproject.toml` [tool.ruff] e [tool.mypy] sem excludes para paths antigos | OK |
| `ruff check src/` e `mypy src/` passam sem erros | OK |
| `alembic upgrade head` (verificado pelo operador no Task 7) | Pendente |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Import circular entre user/models.py e family/models.py**
- **Found during:** Task 3 (bin/generate_code gerou imports no DOIS sentidos)
- **Issue:** O generator gerava `from caramello.family.models import Family` em `user/models.py` E `from caramello.user.models import User` em `family/models.py`, criando ImportError circular
- **Fix:** Corrigido `_consolidate_models` para usar `_build_domain_fk_graph()` detectando ciclos; gerado bloco `TYPE_CHECKING` para tipos circulares e bloco late-bind no final do arquivo para `link_model`; link models reordenados para aparecer antes das entidades que os referenciam
- **Files modified:** scripts/generate_code.py, src/caramello/user/models.py, src/caramello/family/models.py
- **Commit:** 42c2f3c

**2. [Rule 1 - Bug] NameError em family/models.py: FamilyMember não definido antes de Family**
- **Found during:** Task 3 (ordem de entidades no arquivo gerado)
- **Issue:** O generator gerava as entidades na ordem do manifest (Family antes de FamilyMember), mas Family usava `link_model=FamilyMember` que não estava definido ainda
- **Fix:** Adicionado `sorted(entities, key=lambda e: (0 if e.get("is_link_model") else 1))` — link models gerados primeiro
- **Files modified:** scripts/generate_code.py
- **Commit:** 42c2f3c

**3. [Rule 1 - Bug] Ruff não conseguia corrigir linhas longas em docstrings e routers gerados**
- **Found during:** Task 3 (verificação ruff dos arquivos gerados)
- **Issue:** O generator gerava docstrings > 88 chars e imports longos no router; `ruff --fix` não consegue quebrar docstrings automaticamente
- **Fix:** Adicionado `_run_ruff_fix()` ao final do pipeline de geração (`ruff check --fix --unsafe-fixes` + `ruff format`); corrigido template de docstring para formato multi-linha quando excede 88 chars; routers corrigidos com imports em bloco parentesado
- **Files modified:** scripts/generate_code.py
- **Commit:** 42c2f3c

**4. [Rule 1 - Bug] Mypy: RelationshipInfo.link_model e User.__table__ não reconhecidos**
- **Found during:** Task 4 (mypy src/caramello/shared/ src/caramello/core/ src/caramello/user/ src/caramello/family/)
- **Issue:** mypy reportou `"RelationshipProperty[Any]" has no attribute "link_model"` e `"type[User]" has no attribute "__table__"`
- **Fix:** Adicionado `# type: ignore[attr-defined]` nas linhas correspondentes
- **Files modified:** src/caramello/user/models.py, src/caramello/shared/auth.py
- **Commit:** cefffc8

**5. [Rule 3 - Blocker] Import circular em main.py ao importar family antes de user**
- **Found during:** Task 6 (import caramello.main)
- **Issue:** `main.py` importava `family.router` antes de `user.router`; o late-bind em `user.models` executava durante a inicialização de `family.models`, encontrando o módulo parcialmente inicializado
- **Fix:** Reordenados imports em `main.py` — user importado antes de family; adicionado `# isort: skip_file` para preservar a ordem intencional
- **Files modified:** src/caramello/main.py
- **Commit:** 76d34b9

**6. [Rule 3 - Blocker] .env ausente no ambiente de execução**
- **Found during:** Task 3 (verificação de imports com caramello.shared.auth)
- **Issue:** O worktree não tinha `.env`; Settings falhava ao inicializar por falta de variáveis obrigatórias
- **Fix:** Criado `.env` com valores de desenvolvimento (gitignored)
- **Files modified:** .env (não rastreado)
- **Commit:** N/A (gitignored)

## Known Stubs

Nenhum stub identificado. O `user/operations.py` está marcado como `implemented` e retorna `current_user` diretamente.

## Status do Checkpoint (Task 7)

O agente executou tasks 1-6 automaticamente. O **Task 7 aguarda verificação humana E2E** com Keycloak real e banco PostgreSQL.

Itens a verificar pelo operador:
1. Boot da app com `uv run uvicorn caramello.main:app --reload` — JWKS fetch no startup
2. `GET /user/me` sem token → 401/403
3. `GET /user/me` com Bearer token Keycloak válido → 200 com uuid/email/name/idp_sub
4. JIT provisioning: verificar registro na tabela `user`
5. Idempotência: segunda chamada não duplica
6. Claim `aud` do token — decidir se ativa validação em shared/auth.py
7. `alembic upgrade head` concluindo sem erro em `familia_dev`

## Threat Flags

Nenhuma superfície nova além do documentado no threat model do plano. As mitigações T-3-11, T-3-12 e T-3-13 foram implementadas:
- T-3-11: diretórios antigos removidos na Task 6
- T-3-12: `Depends(get_current_user)` em todos os endpoints (verificado via grep: 5 ocorrências em user/router.py)
- T-3-13: anotação `CARAMELLO-GENERATED: implemented` protege operations.py; re-execução do generator verificada

## Self-Check: PASSED

- [x] `src/caramello/user/models.py` existe: `test -f src/caramello/user/models.py` ✓
- [x] `src/caramello/user/operations.py` existe e tem `# CARAMELLO-GENERATED: implemented` ✓
- [x] `src/caramello/family/models.py` existe ✓
- [x] `src/caramello/main.py` tem lifespan e imports de user/family ✓
- [x] `src/caramello/models/` não existe ✓
- [x] `src/caramello/api/` não existe ✓
- [x] Commits existem: 13fcbe2, a6c709f, edd2524, cefffc8, 42c2f3c, 76d34b9 ✓
- [x] `uv run ruff check src/` → All checks passed ✓
- [x] `uv run mypy src/` → Success: no issues found in 14 source files ✓
- [x] `uv run pytest tests/test_generator.py tests/test_auth.py tests/test_user_operations.py` → 4 passed, 11 xpassed ✓
