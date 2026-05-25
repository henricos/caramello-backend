---
phase: 03-estrutura-por-dominios-e-autenticacao
plan: "03"
subsystem: generator
tags: [generator, dsl, domain, auth, ruff, mypy, wave-2]

dependency_graph:
  requires:
    - 03-02 (campo domain nos YAMLs de entidade; dsl/operations/user.yaml)
  provides:
    - scripts/generate_code.py evoluído com suporte a domain + operations + auth
    - entity_domain map construído antes do loop principal
    - generate_operations() produz stub de operations.py com ANNOTATION_STUB
    - _consolidate_models() e _consolidate_routers() agrupam por domínio
    - Código gerado ruff-compliant (X | None, list[T], from __future__ import annotations)
    - Router gerado inclui get_current_user em todos os endpoints
  affects:
    - Plan 05 (usa o generator atualizado para regeneração efetiva do codebase)
    - src/caramello/{domain}/models.py e router.py (produzidos pelo generator no Plan 05)

tech_stack:
  added: []
  patterns:
    - entity_domain map pré-computado antes do loop de geração para resolver imports cross-domain
    - Consolidação por domínio — um models.py e um router.py por domínio com deduplicação de imports
    - ANNOTATION_STUB / ANNOTATION_IMPLEMENTED como mecanismo de proteção de regeneração
    - yaml.safe_load obrigatório (T-3-T08) — bloqueia execução arbitrária em YAMLs maliciosos
    - from __future__ import annotations em todo arquivo gerado — habilita tipos modernos

key_files:
  created: []
  modified:
    - scripts/generate_code.py

decisions:
  - Generator atualizado mas NÃO executa geração — regeneração efetiva fica para o Plan 05
  - _consolidate_models e _consolidate_routers como helpers internos (prefixo _) pois não são API pública
  - Router consolidado usa variáveis renomeadas ({entity}_router) para evitar conflito de nomes no domínio family
  - Link models (FamilyMember) não geram Read/Create/Update nem router

metrics:
  duration: "~25 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 1
---

# Phase 3 Plan 03: Evolução do Generator DSL com Suporte a Domain, Operations e Código Ruff-Clean

Generator DSL reescrito com entity_domain map, consolidação por domínio, generate_operations() para stubs de operations.py, router com auth em todos os endpoints, e código ruff-clean (tipos modernos, sem Optional/List do typing).

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Reescrever scripts/generate_code.py | 752e484 | scripts/generate_code.py |

## Verificação Final

```
uv run ruff check scripts/generate_code.py
```
Resultado: **All checks passed!**

```
uv run mypy scripts/generate_code.py
```
Resultado: **Success: no issues found in 1 source file**

```
uv run python -c "from scripts.generate_code import generate_operations, map_type_to_python, ANNOTATION_STUB, ANNOTATION_IMPLEMENTED; ..."
```
Resultado: **smoke OK**

### Critérios de aceite verificados

| Critério | Resultado |
|----------|-----------|
| `from __future__ import annotations` presente | 6 ocorrências |
| `entity_domain` referenciado | 11 ocorrências |
| `def generate_operations` definida | 1 ocorrência |
| `ANNOTATION_IMPLEMENTED` verificado | 2 ocorrências |
| `from caramello.shared.auth import get_current_user` no template | 2 ocorrências |
| `Depends(get_current_user)` nos endpoints | 6 ocorrências |
| `TESTS_OUTPUT_DIR` ausente | 0 ocorrências |
| `from typing import Optional` ausente | 0 ocorrências |
| `Optional[` ausente | 0 ocorrências |
| Referências a `src/caramello/api/generated` ausentes | 0 ocorrências |
| Referências ao path antigo `src/caramello/models` ausentes | 0 ocorrências |

## Deviations from Plan

None — plano executado exatamente como escrito. O generator foi reescrito integralmente com todas as seis mudanças explícitas documentadas no plano:

1. Imports do script limpos + docstring
2. Paths e constantes atualizados (OPERATIONS_DIR, ANNOTATION_*)
3. generate_models() com entity_domain, tipos modernos, cross-domain imports
4. generate_router() com auth e domain path
5. generate_operations() nova função
6. main() reescrito com entity_domain map e consolidação por domínio

## Known Stubs

Nenhum stub identificado. O generator é um script de tooling; não expõe stubs em runtime.

## Threat Flags

Nenhuma superfície nova de segurança introduzida. O generator é executado apenas em desenvolvimento (não em runtime). Threat register do plano:

- T-3-T07 (aceito): Anotação CARAMELLO-GENERATED editável — trade-off intencional documentado
- T-3-T08 (mitigado): `yaml.safe_load` verificado na linha 33 do arquivo

## Self-Check: PASSED

- [x] scripts/generate_code.py existe e foi modificado
- [x] Commit 752e484 existe no git log
- [x] `uv run ruff check scripts/generate_code.py` → All checks passed
- [x] `uv run mypy scripts/generate_code.py` → Success: no issues found
- [x] Smoke test imprime "smoke OK"
- [x] entity_domain map e ANNOTATION_IMPLEMENTED presentes
- [x] Nenhuma referência a paths antigos ou tipos legacy
