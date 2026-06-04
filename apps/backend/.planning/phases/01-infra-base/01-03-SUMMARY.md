---
phase: 01-infra-base
plan: "03"
subsystem: tooling/cors
tags: [ruff, mypy, linting, cors, config]
dependency_graph:
  requires: [01-01]
  provides: [linting-gate, cors-config, env-docs]
  affects: [pyproject.toml, src/caramello/main.py, src/caramello/core/config.py, .env.example]
tech_stack:
  added: [ruff>=0.9.0, mypy>=1.0.0]
  patterns: [pydantic-settings CORS_ORIGINS list, CORSMiddleware com origens do settings]
key_files:
  created: []
  modified:
    - pyproject.toml
    - src/caramello/core/config.py
    - src/caramello/database/session.py
    - src/caramello/main.py
    - .env.example
    - uv.lock
decisions:
  - Código gerado (api/generated, models, schemas/generated) excluído do ruff e mypy — não pode ser editado diretamente per AGENTS.md
  - type ignore[call-arg] em Settings() é necessário pois pydantic-settings popula campos obrigatórios do env em runtime
  - type ignore[arg-type] em create_engine() pois DATABASE_URL é str|None em mypy mas sempre str após model_post_init
metrics:
  duration: "~5min"
  completed_date: "2026-05-24"
  tasks_completed: 3
  files_modified: 6
---

# Phase 01 Plan 03: Linting, CORS e .env.example Summary

Configura ruff e mypy com postura strict em `pyproject.toml`, corrige todo o código existente para passar nessas regras, adiciona `CORSMiddleware` em `main.py` com origens lidas de `settings.CORS_ORIGINS`, e atualiza `.env.example` com as variáveis corretas de banco e Keycloak.

## O que foi feito

### Task 1 — Configurar ruff e mypy em pyproject.toml e corrigir código
**Commit:** 908c692

Adicionou ruff e mypy ao grupo de dependências dev e configurou postura de linting e type-checking. Corrigiu todos os erros nos arquivos não-gerados do projeto.

**Regras ruff configuradas:** `E, F, I, UP, B, SIM` com `ignore = ["B008"]` (FastAPI Depends em argumentos é padrão).

**Exclusões de código gerado:** `src/caramello/api/generated`, `src/caramello/models`, `src/caramello/schemas/generated` estão excluídos do ruff e mypy. Esses diretórios são regenerados pelo DSL e não devem ser editados diretamente per `AGENTS.md`.

**Erros corrigidos em `config.py`:**
- Removidos imports não usados: `PostgresDsn`, `field_validator`, `ValidationInfo`
- `Optional[str]` → `str | None` (UP045)
- `__context` recebe anotação `object` para mypy com `disallow_untyped_defs`
- `type: ignore[call-arg]` adicionado em `Settings()` — pydantic-settings popula campos obrigatórios do ambiente/arquivo .env em runtime

**Erros corrigidos em `session.py`:**
- `from typing import Generator` → `from collections.abc import Generator` (UP035)
- Funções recebem anotações de retorno (`-> None`, `-> Generator[...]`)
- `type: ignore[arg-type]` em `create_engine(settings.DATABASE_URL)` — `DATABASE_URL` é `str | None` em mypy mas sempre `str` após `model_post_init`
- Ordem de imports corrigida (I001)

### Task 2 — Adicionar CORS_ORIGINS ao Settings e CORSMiddleware ao main.py
**Commit:** ae10db9

Adicionou suporte a CORS no FastAPI para habilitar integração com frontend React/Capacitor.

- `CORS_ORIGINS: list[str]` adicionado a `Settings` com default `["http://localhost:3000", "http://localhost:5173"]`
- `CORSMiddleware` adicionado em `main.py` antes dos `include_router`
- `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
- `root()` recebe anotação de retorno `dict[str, str]` para satisfazer mypy `disallow_untyped_defs`

### Task 3 — Atualizar .env.example com variáveis corretas
**Commit:** 20814b1

Atualizou o arquivo de documentação de variáveis de ambiente.

- `DB_NAME=caramello_db` → `DB_NAME=familia_dev` (convenção `docs/apps-platform.md §5`)
- Adicionado bloco CORS com `CORS_ORIGINS=http://localhost:3000,http://localhost:5173`
- Adicionado bloco Keycloak com placeholders: `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Config] Exclusão de código gerado do ruff/mypy**
- **Found during:** Task 1
- **Issue:** O plano não mencionava que `api/generated` e `models` contêm erros F821 (forward references SQLModel), E501 (linhas longas) e UP035 que não podem ser corrigidos sem editar código gerado
- **Fix:** Adicionado `exclude` no `[tool.ruff]` e `[tool.mypy]` para os três diretórios de código gerado — sem isso, ruff e mypy falhariam em cada CI run
- **Files modified:** `pyproject.toml`
- **Commit:** 908c692

**2. [Rule 2 - Missing type annotation] type: ignore em Settings() e create_engine()**
- **Found during:** Task 1
- **Issue:** mypy com `disallow_untyped_defs=true` reporta falsos positivos em dois locais: (a) `Settings()` não recebe args obrigatórios em código (pydantic-settings popula do env); (b) `create_engine(DATABASE_URL)` onde `DATABASE_URL` é `str | None` no type system mas sempre `str` após `model_post_init`
- **Fix:** Adicionado `# type: ignore[call-arg]` e `# type: ignore[arg-type]` cirúrgicos com comentários explicativos
- **Files modified:** `src/caramello/core/config.py`, `src/caramello/database/session.py`
- **Commit:** 908c692

**3. [Rule 1 - Bug] main.py foi incluído no commit da Task 1 em vez da Task 2**
- **Found during:** Task 1
- **Razão:** As correções de `main.py` eram necessárias para que o ruff passasse (erros I001 e E501 no main.py antigo) — Tasks 1 e 2 foram executadas juntas para garantir que `ruff check src/ && mypy src/` passassem ao final da Task 1. A Task 2 commitou apenas as mudanças residuais (CORSMiddleware e CORS_ORIGINS) que não faziam parte do pyproject.toml

## Known Stubs

Nenhum stub identificado.

## Threat Flags

Nenhuma nova superfície de segurança introduzida além do que está documentado no `<threat_model>` do plano.

As mitigações T-03-01, T-03-02 e T-03-03 foram implementadas conforme especificado:
- `allow_origins=settings.CORS_ORIGINS` — nunca `"*"` com credentials=True
- Default de CORS aponta apenas para localhost — produção deve definir explicitamente
- `DB_NAME=familia_dev` corrigido no `.env.example`

## Self-Check: PASSED

Todos os arquivos existem, todos os commits foram encontrados, e o conteúdo esperado está presente em cada arquivo.
