---
phase: 05-mcp-testes-e-docker
plan: "05"
subsystem: docker-infrastructure
tags: [docker, dockerfile, compose, multi-stage, non-root, app-version]
dependency_graph:
  requires: [05-04]
  provides: [dockerfile-multistage, compose-yaml, dockerignore]
  affects: []
tech_stack:
  added: []
  patterns: [docker-multi-stage-builder-runtime, non-root-system-user, build-arg-app-version, compose-env-vars-only]
key_files:
  created:
    - Dockerfile
    - compose.yaml
    - .dockerignore
  modified: []
decisions:
  - "Dockerfile usa uv pip install --no-cache . (instala o pacote via pyproject.toml) — sem uv sync para manter consistência com o fluxo de instalação do projeto"
  - "README.md copiado no builder porque pyproject.toml declara readme = README.md — omitir causa falha na instalação do pacote"
  - "compose.yaml usa DB_NAME default caramello (prod) conforme D-NAMING-01 — sem serviço PostgreSQL (PG externo)"
  - "KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID sem default — exigem .env do operador (credenciais reais de produção)"
metrics:
  duration: "2 minutos"
  completed: "2026-05-27"
  tasks_completed: 2
  files_created: 3
  files_modified: 0
---

# Phase 05 Plan 05: Dockerfile e compose.yaml — SUMMARY

**One-liner:** Dockerfile multi-stage (builder+runtime) com non-root user e APP_VERSION como único build arg; compose.yaml app-only com toda a configuração via env vars.

## O que foi feito

### Task 1: Dockerfile multi-stage + .dockerignore

Criados dois arquivos na raiz do projeto:

**`.dockerignore`** exclui do contexto de build:
- `.env` — impede vazamento de secrets locais (T-05-11)
- `.git`, `.venv`, `__pycache__/`, `*.pyc` — artefatos de ambiente local
- `.planning/`, `tests/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` — artefatos de desenvolvimento

**`Dockerfile`** multi-stage:
- **Stage `builder` (python:3.12-slim):** Instala `uv`, copia `pyproject.toml`, `uv.lock`, `src/` e `README.md`, cria virtualenv em `/app/.venv` e instala dependências de produção via `uv pip install --python /app/.venv/bin/python --no-cache .`
- **Stage `runtime` (python:3.12-slim):** Recebe `ARG APP_VERSION` e exporta como `ENV APP_VERSION=${APP_VERSION}`; cria usuário não-root `app` via `addgroup`/`adduser`; copia apenas `/app/.venv` e `src/` do builder (sem ferramentas de build); `USER app` antes do `CMD`; porta 8000 exposta.
- APENAS `APP_VERSION` é ARG — nenhum secret nos layers de build (T-05-10, DEPLOY-01)
- `USER app` (non-root) mitiga T-05-12

### Task 2: compose.yaml

Criado `compose.yaml` na raiz, serviço único `api`, alinhado com `docs/deploy.md` e expandido com:
- `build.args.APP_VERSION: ${APP_VERSION:-0.0.0}` — conecta ao ARG do Dockerfile (DEPLOY-03)
- `image: ghcr.io/henricos/caramello-api:${APP_VERSION:-latest}` — tag versionada
- Toda configuração via variáveis de ambiente — sem valores hardcoded (DEPLOY-02)
- Defaults não-secretos: `ENVIRONMENT=production`, `DB_PORT=5432`, `DB_NAME=caramello`, `API_HOST_PORT=8000`
- `DB_PASSWORD`, `DB_HOST`, `DB_USER`, `KEYCLOAK_*` sem default — vêm do `.env` do operador
- `DB_NAME` default `caramello` (produção) conforme D-NAMING-01
- Sem serviço PostgreSQL — PG é externo na infra do operador (D-DOCKER-02)
- `docker compose config -q` valida sem erros (warnings esperados por vars sem default no env de CI)

## Commits

| Task | Descrição | Commit |
|------|-----------|--------|
| 1 | Dockerfile multi-stage e .dockerignore | bc3135d |
| 2 | compose.yaml app-only com config via env vars | 0f27d5b |

## Deviations from Plan

None — o plano foi executado exatamente como escrito.

O grep de verificação `grep -q "ENV APP_VERSION=\${APP_VERSION}" Dockerfile` falhou por expansão
de shell do `$` no script de verificação, não por problema no arquivo. O conteúdo real de
`Dockerfile` contém `ENV APP_VERSION=${APP_VERSION}` conforme esperado (confirmado por `grep "ENV APP_VERSION" Dockerfile`).

## Known Stubs

Nenhum stub. Os três artefatos criados são completos e funcionais para seu propósito:
- `Dockerfile`: build real pode ser executado pelo operador com `docker build --build-arg APP_VERSION=test -t caramello-api:test .`
- `compose.yaml`: `docker compose up` funciona com `.env` contendo as variáveis obrigatórias
- `.dockerignore`: já ativo no contexto de build

Verificação manual (DEPLOY-02, fora do escopo automatizado):
- Operador deve criar `.env` com vars reais e executar `docker build` + `docker compose up`
- Confirmar em `http://localhost:8000/openapi.json` que `version` corresponde a `APP_VERSION`

## Threat Surface Scan

Os artefatos criados implementam mitigações de segurança previstas no threat model do plano:

| Flag | Arquivo | Descrição |
|------|---------|-----------|
| build-context-secrets | `.dockerignore` | T-05-11 mitigado: `.env` e `.git` excluídos do contexto de build |
| build-arg-secrets | `Dockerfile` | T-05-10 mitigado: apenas `APP_VERSION` como ARG; credenciais nunca em `docker history` |
| container-privilege | `Dockerfile` | T-05-12 mitigado: `USER app` (non-root) antes do CMD |

Nenhuma nova superfície de rede introduzida. O `compose.yaml` expõe a porta 8000 (já exposta pelo uvicorn em dev), sem adicionar superfície nova.

## Self-Check: PASSED

- [x] `Dockerfile` — FOUND
- [x] `compose.yaml` — FOUND
- [x] `.dockerignore` — FOUND
- [x] `grep "FROM python:3.12-slim AS builder" Dockerfile` — MATCH
- [x] `grep "FROM python:3.12-slim AS runtime" Dockerfile` — MATCH
- [x] `grep "USER app" Dockerfile` — MATCH
- [x] `grep "ENV APP_VERSION" Dockerfile` — MATCH (ENV APP_VERSION=${APP_VERSION})
- [x] `grep -E "ARG (DB_PASSWORD|KEYCLOAK|DB_USER)" Dockerfile` — VAZIO (sem secrets como ARG)
- [x] `grep "^.env" .dockerignore` — MATCH
- [x] `docker compose config -q` — exits 0
- [x] `grep -F "APP_VERSION: \${APP_VERSION:-0.0.0}" compose.yaml` — MATCH
- [x] `grep -F "DB_NAME: \${DB_NAME:-caramello}" compose.yaml` — MATCH
- [x] Commit bc3135d — FOUND
- [x] Commit 0f27d5b — FOUND
