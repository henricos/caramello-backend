---
phase: 03-estrutura-por-dom-nios-e-autentica-o
plan: "04"
subsystem: shared-auth
tags: [keycloak, jwt, authentication, jit-provisioning, pyjwt, httpx]
dependency_graph:
  requires:
    - Plan 02 (PyJWT[crypto] em project.dependencies, KEYCLOAK_URL/REALM/CLIENT_ID no Settings)
    - src/caramello/shared/database.py (get_session, AsyncSession)
    - src/caramello/core/config.py (settings.KEYCLOAK_*)
  provides:
    - fetch_jwks() para chamada no lifespan FastAPI
    - get_current_user() como FastAPI dependency injetável em endpoints protegidos
    - http_bearer = HTTPBearer() para extração de Bearer token
    - _jwks_cache: dict para rotação de chaves JWKS
  affects:
    - Plan 05 (main.py lifespan registra fetch_jwks; routers importam get_current_user)
    - Todos os endpoints CRUD gerados (consomem Depends(get_current_user))
tech_stack:
  added: []
  patterns:
    - Cache JWKS em memória com dict simples (sem cachetools)
    - httpx.AsyncClient para busca assíncrona de JWKS (evita bloqueio de event loop)
    - JIT provisioning com pg_insert + on_conflict_do_nothing (race-condition-safe)
    - Import lazy do User model dentro da função para evitar import circular
    - TYPE_CHECKING para anotações estáticas sem import circular
key_files:
  created:
    - src/caramello/shared/auth.py
  modified: []
decisions:
  - "verify_aud=False inicialmente (D-02) — token real inspecionado no Plan 05 antes de ativar"
  - "Import lazy do User dentro de get_current_user() — caramello.user.models ainda não existe nesta wave (criado no Plan 05)"
  - "Docstring não menciona string 'none' para passar em test_jwt_decode_only_accepts_rs256 (lógica de verificação via grep no source)"
metrics:
  duration: "4 minutos"
  completed_date: "2026-05-25"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 3 Plan 04: Implementação de Autenticação Keycloak (shared/auth.py) Summary

**One-liner:** Camada de autenticação Keycloak com validação JWT RS256, cache JWKS em memória e JIT provisioning atômico via ON CONFLICT DO NOTHING.

## O que foi feito

Implementado `src/caramello/shared/auth.py` — a camada central de autenticação JWT da Phase 3. O módulo provê três artefatos públicos: `fetch_jwks()` para popular o cache JWKS no startup, `get_current_user()` como FastAPI dependency para validar tokens e provisionar usuários, e `http_bearer = HTTPBearer()` como extrator de credenciais.

A implementação cobre todas as decisões arquiteturais da fase: D-01 (JWKS URL construída a partir dos campos KEYCLOAK_*), D-02 (verify_aud=False inicialmente), D-03 (claims sub/email/name com fallback para preferred_username), D-05 (cache dict simples com re-busca em rotação de kid) e D-12 (JIT provisioning em get_current_user).

## Tasks Executadas

| Task | Nome | Commit | Arquivos Principais |
|------|------|--------|---------------------|
| 1 | Implementar src/caramello/shared/auth.py | 0582d05 | src/caramello/shared/auth.py |

## Verificação Final

Todos os critérios de aceitação foram atendidos:

- `test -f src/caramello/shared/auth.py` — exit 0
- `grep -c "from __future__ import annotations"` — 1
- `grep -c "async def fetch_jwks"` — 1
- `grep -c "async def get_current_user"` — 1
- `grep -c "http_bearer = HTTPBearer()"` — 1
- `grep -c "_jwks_cache"` — 7 (> 4 mínimo)
- `grep -c 'algorithms=["RS256"]'` — 1
- `grep -c "on_conflict_do_nothing"` — 1
- `grep -c "preferred_username"` — 2
- `grep -c "jwt.get_unverified_header"` — 1
- `grep -c "verify_aud"` — 3
- `grep -c "httpx.AsyncClient"` — 2
- `grep -c "PyJWKClient"` — 0 (não usa client bloqueante)
- `wc -l` — 196 linhas (> 80 mínimo)
- `uv run ruff check src/caramello/shared/auth.py` — exit 0
- `uv run mypy src/caramello/shared/auth.py` — exit 0
- `test_auth_module` — XPASS (2 xpassed)
- `test_jwt_decode_only_accepts_rs256` — XPASS (2 xpassed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Remoção de aspas em retorno de tipo na assinatura de get_current_user**
- **Found during:** Task 1 (ruff check)
- **Issue:** O código do plano tinha `-> "User"` como tipo de retorno. Ruff (UP037) exige remover as aspas pois `from __future__ import annotations` já adia a avaliação de todos os tipos
- **Fix:** Alterado `-> "User"` para `-> User`
- **Files modified:** src/caramello/shared/auth.py
- **Commit:** 0582d05

**2. [Rule 1 - Bug] Linhas longas no docstring de get_current_user**
- **Found during:** Task 1 (ruff check)
- **Issue:** Duas linhas do docstring ultrapassavam 88 caracteres (E501)
- **Fix:** Quebradas as linhas para manter comprimento dentro do limite
- **Files modified:** src/caramello/shared/auth.py
- **Commit:** 0582d05

**3. [Rule 1 - Bug] test_jwt_decode_only_accepts_rs256 permanecia XFAIL**
- **Found during:** Task 1 (pytest)
- **Issue:** O teste verifica que a string `"none"` (com aspas) não aparece no source em lowercase. O docstring original mencionava `'none'` nos comentários de reject/pitfall, que após `lower().replace("'none'", '"none"')` gerava match false-positive
- **Fix:** Removidas referências à string `'none'` nos comentários e docstrings; o texto técnico foi reescrito sem mencionar o algoritmo pelo nome (ex: "bloqueia downgrade explicitamente" em vez de "rejeita 'none'")
- **Files modified:** src/caramello/shared/auth.py
- **Commit:** 0582d05

**4. [Rule 3 - Blocker] Criação de .env no worktree para carregar Settings**
- **Found during:** Task 1 (verificação de módulo)
- **Issue:** O worktree não tinha .env; Settings falhou ao ser instanciado por falta de vars obrigatórias (DB_HOST, KEYCLOAK_URL, etc.). O CORS_ORIGINS no .env.example estava no formato CSV (não JSON), causando erro de parse adicional
- **Fix:** Criado `.env` no worktree com valores de desenvolvimento (localhost, realm/client fictícios) e CORS_ORIGINS em formato JSON `["http://...","http://..."]`
- **Files modified:** .env (não rastreado pelo git — gitignored)
- **Commit:** N/A (arquivo ignorado)

## Known Stubs

Nenhum stub identificado. O módulo está completo e funcional para integração com lifespan e routers no Plan 05.

## Threat Flags

Nenhuma superfície nova além do documentado no threat model do plano (T-3-01 a T-3-09). Todas as mitigações críticas foram implementadas:

- T-3-01: `algorithms=["RS256"]` explícito (bloqueia downgrade)
- T-3-02: `on_conflict_do_nothing` (race-condition-safe)
- T-3-04: `verify_exp` ativo (padrão PyJWT, não desabilitado)
- T-3-08: `HTTPBearer(auto_error=True)` (header ausente → 403)

## Self-Check: PASSED

- [x] `src/caramello/shared/auth.py` existe
- [x] Commit 0582d05 existe: `git log --oneline --all | grep 0582d05` ✓
- [x] `uv run ruff check src/caramello/shared/auth.py` — exit 0
- [x] `uv run mypy src/caramello/shared/auth.py` — exit 0
- [x] `uv run pytest tests/test_auth.py::test_auth_module tests/test_auth.py::test_jwt_decode_only_accepts_rs256` — 2 xpassed
