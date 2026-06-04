---
phase: 03-estrutura-por-dom-nios-e-autentica-o
verified: 2026-05-25T20:00:00Z
status: gaps_found
score: 5/8 must-haves verified
overrides_applied: 0
re_verification: null
gaps:
  - truth: "get_current_user executa select(User) sem erro de mapper — AUTH-02 e USER-01 dependem disso em produção"
    status: failed
    reason: "configure_mappers() falha com InvalidRequestError: 'relationship(\"list[Family]\")' usa classe genérica como argumento. User.families usa TYPE_CHECKING guard para importar Family, o que faz SQLAlchemy armazenar 'list[Family]' como string que não consegue resolver durante configuração do mapper. Qualquer session.exec(select(User)) em runtime real vai disparar esta falha."
    artifacts:
      - path: "src/caramello/user/models.py"
        issue: "Linha 31: `families: list[Family] = Relationship(back_populates='members')` — Family está apenas sob TYPE_CHECKING, então SQLAlchemy armazena 'list[Family]' como string não-resolvível. Precisa de `Mapped[list['Family']]` ou importação não-condicional."
    missing:
      - "Corrigir user/models.py linha 31: `families: list['Family'] = Relationship(back_populates='members')` — usar string literal 'Family' em vez de referência direta que depende de TYPE_CHECKING"
      - "Alternativamente: remover TYPE_CHECKING guard e usar importação direta com `from __future__ import annotations` para evitar import circular"
      - "Atualizar generator em scripts/generate_code.py para emitir o padrão correto de relationship annotation para entidades cross-domain"

  - truth: "GET /user/me com token Keycloak válido retorna 200 com uuid, email, name (ROADMAP SC3, USER-01)"
    status: failed
    reason: "Verificação E2E com Keycloak real foi DIFERIDA — o checkpoint humano (Task 7 do Plan 05) foi marcado como 'aprovado sem testar' pelo operador. O teste test_get_me_returns_user_fields (que valida o fluxo end-to-end com mock) permanece XFAIL devido ao bug de mapper acima. Não há evidência programável de que o endpoint funciona com token real."
    artifacts:
      - path: "src/caramello/user/operations.py"
        issue: "Arquivo implementado corretamente (annotation=implemented, return current_user), mas o fluxo depende de get_current_user que usa select(User) — que falha por bug de mapper."
      - path: "tests/test_user_operations.py"
        issue: "test_get_me_returns_user_fields ainda é XFAIL (falha com mapper error, não por falta de implementação)."
    missing:
      - "Resolver bug de mapper (ver gap anterior) para que get_current_user possa executar select(User)"
      - "Executar verificação E2E com Keycloak real e banco PostgreSQL (Task 7 do Plan 05 pendente)"

  - truth: "JIT provisioning cria usuário na primeira request com token válido — operação atômica (ROADMAP SC5, AUTH-02)"
    status: failed
    reason: "Verificação E2E não realizada. O código de JIT provisioning (pg_insert + on_conflict_do_nothing + select(User)) existe em shared/auth.py, mas o select(User) vai falhar em runtime por bug de mapper. Nenhuma evidência de teste integrado."
    artifacts:
      - path: "src/caramello/shared/auth.py"
        issue: "Código estruturalmente correto, mas select(User) na linha 188 vai disparar configure_mappers() que falha."
    missing:
      - "Resolver bug de mapper (ver primeiro gap)"
      - "Executar teste de JIT provisioning com banco real (test_jit_provisioning está @pytest.mark.skip)"

human_verification:
  - test: "E2E boot com Keycloak real"
    expected: "uv run uvicorn caramello.main:app --reload arranca sem erro; JWKS fetch no lifespan completa em < 10s"
    why_human: "Requer Keycloak real e .env com credenciais; sem infraestrutura disponível no ambiente de verificação"

  - test: "GET /user/me com token Keycloak válido"
    expected: "HTTP 200 com JSON contendo uuid, email, name, idp_sub"
    why_human: "Requer token JWT emitido pelo Keycloak real"

  - test: "JIT provisioning idempotente"
    expected: "Primeira chamada cria registro em tabela user; segunda chamada não duplica"
    why_human: "Requer banco PostgreSQL real + Keycloak"

  - test: "alembic upgrade head em familia_dev"
    expected: "Aplica migrations sem erro; tabelas user, family, family_member, family_invitation criadas"
    why_human: "Requer banco PostgreSQL familia_dev acessível"
---

# Phase 3: Estrutura por Domínios e Autenticação — Relatório de Verificação

**Phase Goal:** Reorganizar o código em domínios de negócio (user, family) e adicionar autenticação JWT via Keycloak com JIT provisioning, de modo que cada domínio tenha sua pasta, cada endpoint exija token válido, e o generator suporte o campo `domain`.
**Verificado:** 2026-05-25
**Status:** GAPS FOUND
**Re-verificação:** Não — verificação inicial

## Resumo Executivo

A maior parte da Phase 3 foi implementada com qualidade técnica alta: estrutura de domínios está correta, autenticação JWT está implementada com as salvaguardas de segurança corretas, generator foi evoluído, e os checks automatizados (ruff, mypy, pytest) passam. Porém, há um **bug de mapper SQLAlchemy** no modelo `User` que bloqueia qualquer query real ao banco de dados, tornando AUTH-02 (JIT provisioning) e USER-01 (GET /user/me) não verificáveis em produção. Além disso, a verificação E2E humana (Task 7) foi adiada sem ser executada.

---

## Observable Truths

| # | Truth | Status | Evidência |
|---|-------|--------|-----------|
| 1 | Código organizado em src/caramello/user/, family/, shared/ — models/ e api/ removidos (STRUCT-01) | VERIFIED | `ls src/caramello/`: core, family, shared, user. models/ e api/ ausentes. `grep -r "from caramello.models\|from caramello.api" src/` → 0 resultados |
| 2 | DSL generator lê campo `domain` e produz output em src/caramello/{domain}/ (STRUCT-02) | VERIFIED | `grep "^domain:" dsl/entities/*.yaml` confirma todos os 4 YAMLs. `scripts/generate_code.py` tem `entity_domain` (15 ocorrências), `def generate_operations`, sem referências a paths antigos |
| 3 | Cada endpoint exige token Bearer — sem token retorna 401/403 (AUTH-01) | VERIFIED | TestClient: GET /user/me → 403, GET /user/ → 403, GET /family/ → 403, GET /family_invitation/ → 403. `grep -c "Depends(get_current_user)" user/router.py` = 5; family/router.py = 10 |
| 4 | shared/auth.py isola JWT validation com RS256, JWKS cache, sem PyJWKClient bloqueante (AUTH-03) | VERIFIED | Arquivo existe (197 linhas), expõe fetch_jwks/get_current_user/http_bearer/_jwks_cache. `algorithms=["RS256"]`: 1 ocorrência. `on_conflict_do_nothing`: 1. `httpx.AsyncClient`: 2. `PyJWKClient`: 0 |
| 5 | main.py tem lifespan com await fetch_jwks e inclui routers de user/family | VERIFIED | `@asynccontextmanager lifespan`, `await fetch_jwks()`, 3x `app.include_router()` (user_router, user_operations, family_router). `# isort: skip_file` para preservar ordem crítica |
| 6 | configure_mappers() para User passa sem erro — precondição para queries reais | FAILED | `configure_mappers()` levanta `InvalidRequestError: relationship("list[Family]")`. Cause: `families: list[Family] = Relationship(...)` em user/models.py usa TYPE_CHECKING guard que deixa Family não-resolvível pelo SQLAlchemy class registry |
| 7 | GET /user/me com token Keycloak válido retorna 200 com uuid, email, name (USER-01 / ROADMAP SC3) | FAILED | E2E não testado. Bug de mapper bloqueia select(User) em runtime. test_get_me_returns_user_fields é XFAIL (falha por mapper error, não por falta de implementação) |
| 8 | JIT provisioning cria usuário na primeira request com token válido (AUTH-02 / ROADMAP SC5) | FAILED | E2E não testado. Código existe mas select(User) no final de get_current_user vai falhar pelo mesmo bug de mapper |

**Score:** 5/8 truths verified

---

## Deferred Items

Nenhum item adiado para fases posteriores — os gaps identificados pertencem à Phase 3.

---

## Required Artifacts

| Artifact | Expected | Status | Detalhes |
|----------|----------|--------|----------|
| `src/caramello/user/models.py` | User, UserRead, UserCreate, UserUpdate | VERIFIED | Existe, `class User(SQLModel, table=True)` presente. BUG: relationship families usa tipo não-resolvível |
| `src/caramello/user/router.py` | Router CRUD com Depends(get_current_user) | VERIFIED | 5 endpoints com `_: User = Depends(get_current_user)` |
| `src/caramello/user/operations.py` | GET /user/me implementado, annotation=implemented | VERIFIED | `# CARAMELLO-GENERATED: implemented`, `return current_user`, `Depends(get_current_user)` |
| `src/caramello/family/models.py` | Family, FamilyMember, FamilyInvitation + variants | VERIFIED | Todas as classes presentes, cross-domain import de User correto |
| `src/caramello/family/router.py` | Routers CRUD de Family e FamilyInvitation com auth | VERIFIED | 10x `Depends(get_current_user)`. Nota: tipo anotado como `_: Family` mas get_current_user retorna User — warning de design, não blocker de runtime |
| `src/caramello/shared/auth.py` | fetch_jwks, get_current_user, http_bearer | VERIFIED | Implementado conforme especificação, 197 linhas |
| `src/caramello/main.py` | Lifespan + routers dos domínios | VERIFIED | asynccontextmanager, await fetch_jwks, 3 include_router |
| `alembic/env.py` | Imports de caramello.user.models e caramello.family.models | VERIFIED | Linha 22-26: imports corretos dos novos paths; `from caramello.models import *` removido |
| `scripts/generate_code.py` | Generator com domain, operations, auth, sem paths antigos | VERIFIED | entity_domain (15x), generate_operations (1x), ANNOTATION_IMPLEMENTED (2x), sem refs a api/generated ou models/ |
| `dsl/operations/user.yaml` | Define operação get_me em /user/me | VERIFIED | Arquivo existe com domain=user, operations=[{name: get_me, method: GET, path: /user/me}] |

---

## Key Link Verification

| From | To | Via | Status | Detalhes |
|------|----|----|--------|----------|
| `src/caramello/main.py` | `fetch_jwks()` | asynccontextmanager lifespan | WIRED | `await fetch_jwks()` presente no lifespan |
| `src/caramello/main.py` | routers user/family | app.include_router | WIRED | 3 chamadas: user_router.router, user_operations.router, family_router.router |
| `src/caramello/user/router.py` | `get_current_user` | Depends | WIRED | 5 endpoints com `Depends(get_current_user)` |
| `src/caramello/user/operations.py` | `get_current_user` | Depends + return | WIRED | `Depends(get_current_user)`, `return current_user` |
| `src/caramello/shared/auth.py` | `settings.KEYCLOAK_URL` | f-string JWKS URL | WIRED | `settings.KEYCLOAK_URL.rstrip('/')` + realm + path |
| `src/caramello/shared/auth.py` | PostgreSQL via pg_insert | on_conflict_do_nothing | WIRED (code) | Código presente; broken runtime por mapper bug |
| `src/caramello/shared/auth.py` | User model | import lazy + select | PARTIAL | Import lazy existe; select(User) falha em runtime por mapper bug |
| `alembic/env.py` | caramello.user.models, caramello.family.models | import | WIRED | Imports explícitos nas linhas 22-26 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `user/operations.py` GET /user/me | `current_user` | `get_current_user()` dependency | Depende de DB | HOLLOW — `get_current_user` usa `select(User)` que falha por mapper bug; sem DB real não testado |
| `shared/auth.py` get_current_user | `user` result | `session.exec(select(User).where(...))` | Requer DB | HOLLOW — mapper bug bloqueia execução |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| AUTH-01: /user/me sem token → 401/403 | TestClient.get('/user/me') | 403 | PASS |
| AUTH-01: /family/ sem token → 401/403 | TestClient.get('/family/') | 403 | PASS |
| STRUCT-01: models/ e api/ ausentes | test -d src/caramello/models (etc) | REMOVED | PASS |
| configure_mappers() válido | configure_mappers() | InvalidRequestError: list[Family] | FAIL |
| Ruff em src/ | uv run ruff check src/ | All checks passed | PASS |
| Mypy em src/ | uv run mypy src/ | Success: 14 source files | PASS |
| pytest suite | uv run pytest tests/test_generator.py tests/test_auth.py tests/test_user_operations.py | 4 passed, 1 skipped, 1 xfailed, 11 xpassed | PASS (mas xfail=mapper bug) |

---

## Requirements Coverage

| Requisito | Planos | Descrição | Status | Evidência |
|-----------|--------|-----------|--------|-----------|
| STRUCT-01 | 03-05 | Código por domínio, models/ e api/ removidos | SATISFIED | src/caramello/{user,family,shared}/; models/ e api/ ausentes |
| STRUCT-02 | 03-02, 03-03 | Generator emite em domain dir quando YAML tem campo `domain` | SATISFIED | dsl/entities/*.yaml têm domain; generator usa entity_domain; outputs em user/ e family/ |
| AUTH-01 | 03-04, 03-05 | Endpoints rejeitam sem token → 401/403 | SATISFIED | HTTPBearer com auto_error=True; TestClient confirma 403 em /user/me e /family/ |
| AUTH-02 | 03-04, 03-05 | JIT provisioning com ON CONFLICT DO NOTHING | BLOCKED | Código correto em auth.py mas select(User) falha por mapper bug; E2E não testado |
| AUTH-03 | 03-04 | shared/auth.py isola JWT validation | SATISFIED | Módulo dedicado, RS256 explícito, PyJWKClient ausente, JWKS async |
| USER-01 | 03-05 | GET /user/me retorna perfil autenticado | BLOCKED | operations.py correto mas fluxo falha por mapper bug; E2E não testado |

---

## Anti-Patterns Encontrados

| Arquivo | Linha | Pattern | Severidade | Impacto |
|---------|-------|---------|------------|---------|
| `src/caramello/user/models.py` | 31 | `families: list[Family] = Relationship(...)` com Family sob TYPE_CHECKING | BLOCKER | SQLAlchemy armazena 'list[Family]' como string não-resolvível; configure_mappers() falha; qualquer session.exec(select(User)) em produção vai falhar |
| `src/caramello/family/router.py` | 29, 41, 53, 68, 88 | `_: Family = Depends(get_current_user)` — tipo anotado incorreto (get_current_user retorna User) | WARNING | FastAPI ignora anotação de tipo em _ para Depends; funciona em runtime mas é confuso e enganoso para leitores do código |
| `.planning/ROADMAP.md` | SC2 Phase 3 | ROADMAP diz "models.py e schemas.py" mas generator só produz models.py | INFO | schemas.py nunca foi gerado; documentação do ROADMAP desatualizada; intent do SC2 satisfeito (modelos em dir correto) |

---

## Human Verification Required

### 1. Boot da aplicação com Keycloak real

**Test:** `uv run uvicorn caramello.main:app --reload` com .env configurado (KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID)
**Expected:** App inicia sem traceback; JWKS fetch completa em < 10s; `curl http://localhost:8000/` retorna `{"message":"Welcome to Caramello API"}`
**Why human:** Requer Keycloak real na infraestrutura; sem acesso no ambiente de verificação

### 2. GET /user/me com token válido (USER-01)

**Test:** `curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/user/me`
**Expected:** HTTP 200 com JSON contendo uuid, email, name, idp_sub
**Why human:** Requer token JWT do Keycloak real + banco PostgreSQL. Nota: RESOLVE o bug de mapper também (quando todos os módulos carregam na ordem correta via uvicorn, o mapper pode configurar)

### 3. JIT provisioning idempotente (AUTH-02)

**Test:** Fazer GET /user/me duas vezes com mesmo token; verificar `SELECT * FROM "user"` no banco
**Expected:** Apenas 1 linha criada após 2 chamadas; idp_sub = claim sub do token
**Why human:** Requer banco PostgreSQL + Keycloak + token real

### 4. alembic upgrade head em familia_dev

**Test:** `bin/manage_db upgrade` com .env configurado
**Expected:** Migrations aplicadas sem erro; tabelas user, family, family_member, family_invitation existem
**Why human:** Requer banco PostgreSQL familia_dev acessível

---

## Gaps Summary

**3 gaps bloqueiam o objetivo da fase:**

**Gap 1 — BUG CRÍTICO: Mapper SQLAlchemy inválido em user/models.py [BLOCKER para AUTH-02 e USER-01]**

O modelo `User` declara `families: list[Family] = Relationship(back_populates="members")` onde `Family` só está disponível sob `TYPE_CHECKING`. Em runtime, SQLAlchemy armazena a string `'list[Family]'` como argumento do relationship e não consegue resolvê-la durante `configure_mappers()`. Isso bloqueia qualquer ORM query que envolva o mapper de `User` — incluindo o `select(User).where(User.idp_sub == idp_sub)` em `shared/auth.py`.

**Fix:** Alterar `user/models.py` linha 31 para usar string literal: `families: list["Family"] = Relationship(back_populates="members")`, ou melhor, usar `from __future__ import annotations` (já presente) que torna todas as anotações strings lazy — mas requer testar se resolve o problema no contexto SQLModel 0.0.38. Atualizar também `scripts/generate_code.py` para emitir o padrão correto.

**Gap 2 — E2E humano não executado (BLOCKER para SC3, SC5 do ROADMAP)**

O checkpoint humano (Task 7 do Plan 05) foi marcado como "aprovado (diferido)" sem execução real. Não há evidência de que o app bootou com Keycloak, que GET /user/me retornou 200 com token real, ou que o JIT provisioning funcionou.

**Gap 3 — ROADMAP SC2 menciona schemas.py que nunca foi gerado (INFO)**

O ROADMAP diz "produz models.py e schemas.py" mas o generator só produz models.py (que contém tanto o modelo ORM quanto os schemas Read/Create/Update). O intent está satisfeito mas a documentação do ROADMAP está desatualizada. Este é um gap documental, não de implementação.

**Nota importante sobre o Gap 1:** O bug de mapper é real e demonstrável via `configure_mappers()`, mas pode não impedir o app de funcionar em determinadas condições de importação — o SUMMARY afirma que os testes passaram em ambiente do agente. A verificação humana (Gap 2) deve incluir teste explícito de query ao banco para confirmar se o mapper bug afeta o runtime de produção ou apenas ambientes de teste isolados.

---

_Verificado: 2026-05-25_
_Verificador: Claude (gsd-verifier)_
