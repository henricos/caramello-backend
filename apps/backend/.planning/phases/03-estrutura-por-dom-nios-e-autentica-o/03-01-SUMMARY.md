---
phase: 03-estrutura-por-dominios-e-autenticacao
plan: "01"
subsystem: tests
tags: [tests, stubs, xfail, wave-0, tdd]

dependency_graph:
  requires: []
  provides:
    - "tests/test_generator.py — 9 testes stub para STRUCT-02 (DSL domain field)"
    - "tests/test_auth.py — 5 testes stub para AUTH-01, AUTH-02, AUTH-03"
    - "tests/test_user_operations.py — 2 testes stub para USER-01"
    - "tests/conftest.py — fixture client compartilhada"
  affects:
    - "Waves 1-4 da Phase 3 destravam testes ao remover @pytest.mark.xfail"

tech_stack:
  added: []
  patterns:
    - "pytest xfail como contrato de Wave — testes stub destravados conforme waves entregam"
    - "Lazy import em conftest.py — evita falha de import antes da app estar completa"
    - "app.dependency_overrides para mock de get_current_user sem banco real"

key_files:
  created:
    - tests/conftest.py
    - tests/test_generator.py
    - tests/test_auth.py
    - tests/test_user_operations.py
  modified:
    - pyproject.toml

decisions:
  - "Registrar marker 'integration' no pyproject.toml para evitar PytestUnknownMarkWarning"
  - "Usar noqa: E501 em docstrings longas do plano original — manter semântica do texto"
  - "pytest.mark.xfail strict=False — Wave pode entregar parcialmente sem quebrar CI"

metrics:
  duration: "3m 46s"
  completed_date: "2026-05-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 3 Plan 01: Testes Stub Wave 0 — STRUCT-02, AUTH-01/02/03, USER-01

Wave 0 da Phase 3: 16 testes stub criados com xfail para STRUCT-02/AUTH-01-03/USER-01, coletados pelo pytest sem erros de import.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Criar conftest.py + test_generator.py | ddbd937 | tests/conftest.py, tests/test_generator.py |
| 2 | Criar test_auth.py + test_user_operations.py | 0c7e49f | tests/test_auth.py, tests/test_user_operations.py, pyproject.toml |
| — | Corrigir estilo ruff (E501, I001) | 8ec1130 | todos os arquivos de teste |

## Verificação Final

```
uv run pytest tests/test_generator.py tests/test_auth.py tests/test_user_operations.py --collect-only -q
```
Resultado: **16 testes coletados, 0 erros**.

```
uv run ruff check tests/test_generator.py tests/test_auth.py tests/test_user_operations.py tests/conftest.py
```
Resultado: **All checks passed!**

### Contagem por arquivo

| Arquivo | Testes | Ativos | xfail |
|---------|--------|--------|-------|
| test_generator.py | 9 | 3 | 6 |
| test_auth.py | 5 | 0 | 5 |
| test_user_operations.py | 2 | 0 | 2 |
| **Total** | **16** | **3** | **13** |

Os 3 testes ativos (não xfail) em `test_generator.py` verificam que os YAMLs de domínio e
o arquivo `dsl/operations/user.yaml` existem e têm o formato correto — Wave 1 (Plan 02) deve
fazê-los passar.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing config] Marker 'integration' não registrado no pytest**
- **Found during:** Task 2 — pytest emitia `PytestUnknownMarkWarning`
- **Issue:** `@pytest.mark.integration` usado em `test_jit_provisioning` sem registro
- **Fix:** Adicionou `[tool.pytest.ini_options]` com `markers = ["integration: ..."]` em `pyproject.toml`
- **Files modified:** pyproject.toml
- **Commit:** 0c7e49f

**2. [Rule 1 - Style] Violações de ruff E501 e I001 nos arquivos de teste**
- **Found during:** Verificação final após Task 2
- **Issue:** Linhas longas e imports desordenados nas strings do plano original
- **Fix:** `ruff check --fix` para I001; noqa: E501 nas docstrings longas; quebra de decorators
- **Files modified:** todos os 4 arquivos de teste
- **Commit:** 8ec1130

## Known Stubs

Nenhum stub que impeça o objetivo do plano. Os testes `xfail` são intencionalmente stubs
que serão destravados nas waves 1-4. O objetivo da Wave 0 — coletar 16 testes sem erro — foi atingido.

## Threat Flags

Nenhuma superfície nova de segurança introduzida. Os arquivos de teste não são expostos em runtime.

## Self-Check: PASSED

- [x] tests/conftest.py existe
- [x] tests/test_generator.py existe (9 funções test_)
- [x] tests/test_auth.py existe (5 funções test_)
- [x] tests/test_user_operations.py existe (2 funções test_)
- [x] pyproject.toml modificado com marker integration
- [x] Commits ddbd937, 0c7e49f, 8ec1130 existem no git log
- [x] pytest coleta 16 testes sem erros
- [x] ruff passa sem erros
