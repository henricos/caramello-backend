---
phase: 01-infra-base
plan: "02"
subsystem: codebase/cleanup
tags: [cleanup, dead-code, artefatos-obsoletos, schemas, testes]
dependency_graph:
  requires: [01-01]
  provides: [codebase-limpo-sem-artefatos-mortos]
  affects: [lint-mypy-ruff, pytest-collect]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified: []
  deleted:
    - src/caramello/api/v1/__init__.py
    - src/caramello/api/v1/routes.py
    - src/caramello/api/v1/users.py
    - src/caramello/exceptions.py
    - src/caramello/http_errors.py
    - src/caramello/repositories/user.py
    - src/caramello/services/user.py
    - src/caramello/schemas/__init__.py
    - src/caramello/schemas/user.py
    - src/caramello/schemas/generated/api_schemas.py
    - tests/generated/__init__.py
    - tests/generated/test_user.py
    - tests/generated/test_family.py
    - tests/generated/test_familyinvitation.py
    - tests/test_generated_api.py
decisions:
  - "Diretórios services/ e repositories/ mantidos (apenas __init__.py) para uso na arquitetura futura de domínios"
  - "main.py não precisou de ajustes — já importava apenas os routers gerados em api/generated/"
metrics:
  duration: "2 min"
  completed_date: "2026-05-24"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 0
  files_deleted: 15
---

# Phase 01 Plan 02: Limpeza de Artefatos Obsoletos — Summary

Remoção de 15 arquivos mortos (gerados por ferramentas anteriores, sem uso real) para deixar o codebase limpo antes das fases de implementação: api/v1 vazia, schemas do datamodel-codegen, testes sem fixtures isoladas, arquivos vazios de services e repositories.

## Tasks Executadas

| Task | Nome | Commit | Arquivos |
|------|------|--------|----------|
| 1 | Remover arquivos vazios de services, repositories, exceptions e api/v1 | `fa88cd7` | 7 arquivos removidos |
| 2 | Remover src/caramello/schemas/ e tests/generated/ e tests/test_generated_api.py | `874707e` | 8 arquivos removidos |
| 3 | Verificar que a aplicação ainda sobe após as remoções | (sem commit — somente verificação) | `src/caramello/main.py` (sem alterações) |

## Arquivos/Diretórios Removidos

### Task 1 — api/v1, services, repositories, exceptions

| Arquivo | Motivo da remoção |
|---------|------------------|
| `src/caramello/api/v1/__init__.py` | Arquivo vazio; diretório legado pré-DSL |
| `src/caramello/api/v1/routes.py` | Arquivo vazio; diretório legado pré-DSL |
| `src/caramello/api/v1/users.py` | Arquivo vazio; diretório legado pré-DSL |
| `src/caramello/exceptions.py` | Arquivo vazio; sem uso em nenhum módulo |
| `src/caramello/http_errors.py` | Arquivo vazio; sem uso em nenhum módulo |
| `src/caramello/repositories/user.py` | Arquivo vazio; placeholder sem implementação |
| `src/caramello/services/user.py` | Arquivo vazio; placeholder sem implementação |

### Task 2 — schemas, tests/generated, teste legado

| Arquivo | Motivo da remoção |
|---------|------------------|
| `src/caramello/schemas/__init__.py` | Gerado pelo datamodel-codegen; desconectado da arquitetura atual |
| `src/caramello/schemas/user.py` | Gerado pelo datamodel-codegen; desconectado da arquitetura atual |
| `src/caramello/schemas/generated/api_schemas.py` | Gerado pelo datamodel-codegen; desconectado da arquitetura atual |
| `tests/generated/__init__.py` | Parte dos testes gerados sem fixtures isoladas |
| `tests/generated/test_user.py` | Testes sem fixtures de banco isoladas; causaria falhas em pytest |
| `tests/generated/test_family.py` | Testes sem fixtures de banco isoladas; causaria falhas em pytest |
| `tests/generated/test_familyinvitation.py` | Testes sem fixtures de banco isoladas; causaria falhas em pytest |
| `tests/test_generated_api.py` | Usa paths de API do legado pré-DSL (`/users/`, `/family/`); incorretos |

## Confirmação de que a Aplicação Ainda Sobe

```
$ DB_HOST=localhost DB_PORT=5432 DB_USER=test DB_PASSWORD=test DB_NAME=test \
  uv run python -c "from caramello.main import app; print('app: OK')"
app: OK
```

Nota: O erro observado sem variáveis de ambiente (`ValidationError: 5 validation errors for Settings`) é pré-existente e independente das remoções — ocorre porque `session.py` inicializa o `engine` no import e exige as variáveis de banco. Não é um ImportError introduzido por este plano.

## Ajustes em main.py

Nenhum ajuste necessário. O `main.py` já importava exclusivamente os routers de `src/caramello/api/generated/`:

```python
from caramello.api.generated import user_router, family_router, familymember_router, familyinvitation_router
```

Nenhum dos arquivos removidos era referenciado em main.py.

## Estado Final do Codebase

```
src/caramello/
├── api/
│   ├── generated/          # routers DSL — mantidos
│   └── __init__.py
├── core/                   # config.py — mantido
├── database/               # session.py — mantido
├── models/                 # modelos DSL — mantidos
├── repositories/           # apenas __init__.py (para arquitetura futura)
├── services/               # apenas __init__.py (para arquitetura futura)
├── __init__.py
└── main.py

tests/
├── conftest.py             # mantido (arquivo vazio)
├── test_api/               # mantido (test_user_router.py vazio)
└── test_services/          # mantido (test_user_service.py vazio)
```

## Deviations from Plan

None — plano executado exatamente como escrito. `main.py` não precisou de ajustes conforme previsto como hipótese no plano.

## Known Stubs

None — plano de limpeza, sem código introduzido.

## Threat Flags

None — remoção de arquivos mortos não introduz nova superfície de ataque. A ameaça T-02-01 (import quebrado em main.py) foi verificada e mitigada: main.py funcional após remoções.

## Self-Check: PASSED

Arquivos verificados como removidos:
- `src/caramello/exceptions.py` — REMOVED
- `src/caramello/http_errors.py` — REMOVED
- `src/caramello/api/v1/` — REMOVED
- `src/caramello/schemas/` — REMOVED
- `tests/generated/` — REMOVED
- `tests/test_generated_api.py` — REMOVED

Aplicação verificada:
- `from caramello.main import app` — executa sem ImportError

Commits verificados:
- `fa88cd7` — FOUND
- `874707e` — FOUND
