---
phase: 03-estrutura-por-dom-nios-e-autentica-o
plan: "02"
subsystem: dsl-inputs
tags: [dependencies, keycloak, dsl, yaml, configuration]
dependency_graph:
  requires: []
  provides:
    - PyJWT[crypto] disponível no venv para shared/auth.py
    - httpx em project.dependencies para uso em produção (Docker)
    - Settings com KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID
    - dsl/entities/*.yaml com campo domain para generator evolution
    - dsl/operations/user.yaml com operação GET /user/me para Plan 03
    - dsl/schema.yaml atualizado com campo domain obrigatório
  affects:
    - Plan 03 (generator evolution) — consome campo domain dos YAMLs e dsl/operations/*.yaml
    - Plan 04 (auth implementation) — consome PyJWT[crypto], httpx e Settings.KEYCLOAK_*
tech_stack:
  added:
    - PyJWT[crypto] 2.13.0 — validação JWT RS256/ES256 para shared/auth.py
    - cryptography 48.0.0 — dependência transitiva de PyJWT[crypto]
    - httpx 0.28.1 — movido de dev para main deps; busca assíncrona de JWKS
  patterns:
    - pydantic-settings sem default para campos obrigatórios (fail-fast no boot)
    - YAML DSL com campo domain para roteamento de output do generator
    - dsl/operations/{domain}.yaml como novo conceito DSL para operações de negócio
key_files:
  created:
    - dsl/operations/user.yaml
    - tests/test_generator.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/caramello/core/config.py
    - dsl/entities/user.yaml
    - dsl/entities/family.yaml
    - dsl/entities/family_member.yaml
    - dsl/entities/family_invitation.yaml
    - dsl/schema.yaml
decisions:
  - PyJWT[crypto] adicionado via uv add com versão mínima >=2.13.0 (D-04)
  - httpx movido de dependency-groups.dev para project.dependencies — necessário em container Docker
  - Campos KEYCLOAK_* sem valor default em Settings — ValidationError no boot se .env incompleto (T-3-T05)
  - Campo domain em dsl/schema.yaml marcado como required — generator pode validar YAMLs contra schema
metrics:
  duration: "3 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 4
  tasks_total: 4
  files_modified: 10
---

# Phase 3 Plan 02: Pré-requisitos de Dependências, Configuração e DSL Summary

**One-liner:** PyJWT[crypto] e httpx em project.dependencies, KEYCLOAK_URL/REALM/CLIENT_ID no Settings, campo `domain` nos 4 YAMLs de entidade com dsl/operations/user.yaml criado para GET /user/me.

## O que foi feito

Este plano preparou todos os inputs necessários para os dois planos que o consomem em paralelo na Wave 1: o Plan 03 (evolução do generator DSL) e o Plan 04 (implementação de autenticação Keycloak). As quatro tasks são independentes entre si e não têm overlap de arquivos.

## Tasks Executadas

| Task | Nome | Commit | Arquivos Principais |
|------|------|--------|---------------------|
| 1 | Adicionar PyJWT[crypto] e mover httpx para project.dependencies | 127e2c7 | pyproject.toml, uv.lock |
| 2 | Adicionar campos KEYCLOAK_* ao Settings em config.py | 9b142d2 | src/caramello/core/config.py |
| 3 | Adicionar campo domain nos 4 YAMLs + atualizar dsl/schema.yaml | d693eaa | dsl/entities/*.yaml, dsl/schema.yaml, tests/test_generator.py |
| 4 | Criar dsl/operations/user.yaml com operação get_me | 6a9f6ae | dsl/operations/user.yaml |

## Verificação Final

Todos os critérios do plano foram atendidos:

- `uv run python -c "import jwt, httpx; from jwt.algorithms import RSAAlgorithm"` — exit 0
- `grep '"pyjwt[crypto]' pyproject.toml` — encontrado em project.dependencies
- `grep -c '"httpx' pyproject.toml` — retorna 1 (apenas em project.dependencies, não em dependency-groups.dev)
- `uv run ruff check src/caramello/core/config.py` — exit 0
- `uv run mypy src/caramello/core/config.py` — exit 0
- `uv run pytest tests/test_generator.py::test_user_yaml_has_domain_field tests/test_generator.py::test_family_yamls_have_domain_field tests/test_generator.py::test_operations_user_yaml_exists` — 3 passed

## Deviations from Plan

### Auto-added Missing Functionality

**1. [Rule 2 - Missing Critical] Criação de tests/test_generator.py**
- **Found during:** Task 3 e Task 4
- **Issue:** O plano referenciam testes em `tests/test_generator.py` (ex: `test_user_yaml_has_domain_field`, `test_family_yamls_have_domain_field`, `test_operations_user_yaml_exists`) mas este arquivo não existia no codebase
- **Fix:** Criado `tests/test_generator.py` com 4 testes de validação dos artefatos DSL: os 3 requeridos pelo plano mais um adicional `test_schema_yaml_has_domain_property` para cobertura do schema.yaml
- **Files modified:** tests/test_generator.py (criado)
- **Commit:** d693eaa (incluído no commit da Task 3)

## Known Stubs

Nenhum stub identificado nos arquivos criados/modificados. Todos os arquivos têm conteúdo funcional e completo.

## Threat Flags

Nenhuma superfície de segurança nova além da já documentada no threat model do plano (T-3-T03, T-3-T04, T-3-T05, T-3-T06). Os campos KEYCLOAK_* são apenas configuração de URL/realm/client_id — nenhuma credencial em código.

## Self-Check: PASSED

Verificações:

- [x] `pyproject.toml` contém `"pyjwt[crypto]>=2.13.0"` em project.dependencies
- [x] `pyproject.toml` contém `"httpx>=0.28.1"` em project.dependencies (não em dev)
- [x] `src/caramello/core/config.py` contém KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID sem defaults
- [x] `dsl/entities/user.yaml` contém `domain: user`
- [x] `dsl/entities/family.yaml` contém `domain: family`
- [x] `dsl/entities/family_member.yaml` contém `domain: family`
- [x] `dsl/entities/family_invitation.yaml` contém `domain: family`
- [x] `dsl/schema.yaml` contém domain em properties e required
- [x] `dsl/operations/user.yaml` contém get_me com GET /user/me
- [x] `tests/test_generator.py` existe com 4 testes passando
- [x] Commits 127e2c7, 9b142d2, d693eaa, 6a9f6ae existem no git log
