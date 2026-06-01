---
phase: 07-crud-account-category
verified: 2026-06-01T17:30:00Z
status: human_needed
score: 9/9
overrides_applied: 0
human_verification:
  - test: "AUTH-FIN-01 — confirmar se 403 (em vez de 401) para token ausente é aceitável como comportamento final do requisito"
    expected: "Equipe decide se REQUIREMENTS.md deve ser atualizado de '401 sem token' para '401 ou 403 sem token', ou se HTTPBearer deve ser substituído por uma dependência customizada que retorne 401"
    why_human: "Discrepância documental entre REQUIREMENTS.md (especifica 401) e implementação real (HTTPBearer retorna 403). A pesquisa da fase e test_auth.py documentam o comportamento atual como 403. A decisão de aceitar ou corrigir é de produto/arquitetura, não verificável automaticamente."
---

# Phase 7: CRUD Account + Category — Verification Report

**Phase Goal:** Usuário autenticado pode gerenciar contas e categorias hierárquicas da sua família
**Verified:** 2026-06-01T17:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /finances/accounts` cria conta com nome, tipo e moeda; resposta inclui `uuid`, sem `id`/`family_id` | VERIFIED | `test_create_account_returns_uuid` PASSED. `AccountReadPublic` schema confirms fields: `uuid`, `family_uuid`, `name`, `type`, `currency`, `is_active`, `created_at`, `updated_at` — no `id` or `family_id`. |
| 2 | `GET /finances/accounts` retorna contas da família do usuário autenticado; 403 sem token; 403 para família alheia | VERIFIED | `test_list_accounts_scoped_to_family`, `test_accounts_require_auth`, `test_accounts_403_non_member` all PASSED. Scoped query: `select(Account).where(Account.family_id == family.id)`. |
| 3 | `PATCH /finances/accounts/{uuid}` arquiva conta com `is_active=false`; movimentações existentes permanecem | VERIFIED | `test_archive_account` PASSED. No `session.delete` call in handler. `AccountUpdatePublic` includes `is_active: bool | None = None`. |
| 4 | `POST /finances/categories` cria categoria pai (nível 1) | VERIFIED | `test_create_category` PASSED. `create_category` handler at line 270. `CategoryReadPublic` has `family_uuid`, no `id`/`family_id`. |
| 5 | `POST /finances/subcategory` com `category_uuid` válido cria subcategoria (nível 2); não existe rota de nível 3 (CAT-03 estrutural) | VERIFIED | `test_create_subcategory` PASSED. `test_finances_router_paths` confirms exactly 6 paths — no sub-subcategory route. `Subcategory.category_id` FK to `Category.id` structurally prevents level 3. |

**Score:** 5/5 ROADMAP success criteria verified

### Additional Plan Must-Haves

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 6 | Arquivo `tests/test_finances_operations.py` existe, coletável pelo pytest, >= 9 funções de teste | VERIFIED | 11 test functions present. `uv run python -m pytest tests/test_finances_operations.py -v` → 11 passed. |
| 7 | Helper `_require_family_access` em `shared/auth.py` com import lazy de FamilyMember; levanta 403 para não-membros | VERIFIED | `src/caramello/shared/auth.py` lines 233–258. Lazy import at line 246. Raises `HTTP_403_FORBIDDEN` when `result.first() is None`. |
| 8 | Router `finances_operations.router` registrado em `main.py` ANTES de `mcp.mount_http()` | VERIFIED | `app.include_router(finances_operations.router)` at line 60; `mcp.mount_http()` at line 73. Ratio: 60 < 73. |
| 9 | Schemas públicos `*Public` sem `id`/`family_id`/`category_id` internos | VERIFIED | `AccountReadPublic` (lines 42–51), `CategoryReadPublic` (lines 65–71), `SubcategoryReadPublic` (lines 82–88). None contain `id`, `family_id`, or `category_id` fields. |

**Combined Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_finances_operations.py` | Wave 0 test scaffold, >= 9 functions, pytest.importorskip | VERIFIED | 11 test functions. `_skip_if_stub()` used (deviation from pure importorskip — documented and justified). Exists at 732 lines. |
| `src/caramello/shared/auth.py` | Contains `_require_family_access` | VERIFIED | Function at line 233. Lazy import, 403 on non-member. |
| `src/caramello/finances/operations.py` | CRUD Account + Category + Subcategory, `AccountReadPublic`, `SubcategoryReadPublic`, >= 120 lines, `# CARAMELLO-GENERATED: implemented` | VERIFIED | 565 lines. First line is `# CARAMELLO-GENERATED: implemented`. Contains `AccountReadPublic`, `CategoryReadPublic`, `SubcategoryReadPublic`. 12 calls to `_require_family_access`. |
| `src/caramello/main.py` | Contains `finances_operations.router` import and `include_router` | VERIFIED | Import at line 26. `include_router` at line 60. Generated `finances/router.py` NOT imported (confirmed). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_finances_operations.py` | `caramello.finances.operations` | `pytest.importorskip` + `_skip_if_stub()` | VERIFIED | `_skip_if_stub()` calls `importorskip` as first step; deviation documented in 07-01-SUMMARY.md |
| `src/caramello/finances/operations.py` | `caramello.shared.auth._require_family_access` | import + call after resolving family/category UUID | VERIFIED | 12 calls to `await _require_family_access(` in operations.py. Imported at line 22. |
| `src/caramello/main.py` | `finances_operations.router` | `app.include_router` before `mcp.mount_http()` | VERIFIED | Line 60 < line 73. |
| `src/caramello/finances/operations.py` (subcategory) | `Category.uuid` | `Category.uuid ==` pattern for resolving category_uuid | VERIFIED | `select(Category).where(Category.uuid == subcategory_in.category_uuid)` at line 426. |

### Data-Flow Trace (Level 4)

This phase delivers CRUD endpoints backed by async SQLModel sessions with mocked sessions in tests. No static/hardcoded data detected in public schemas or handlers. Data flows: client payload → UUID resolution → family membership check → ORM create/query → `*ReadPublic` response. All data paths use `session.exec()` + real ORM models.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `AccountReadPublic` response | `db_account` | `session.exec(select(Account)...)` → `session.add` + `commit` + `refresh` | Yes — ORM instance | FLOWING |
| `CategoryReadPublic` response | `db_category` | `session.exec(select(Category)...)` | Yes — ORM instance | FLOWING |
| `SubcategoryReadPublic` response | `db_subcategory` | `session.exec(select(Subcategory)...)` | Yes — ORM instance | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 11 finances tests pass | `uv run python -m pytest tests/test_finances_operations.py -v` | 11 passed, 0 failed | PASS |
| Router exposes exactly 6 finance paths | `uv run python -c "from caramello.main import app; paths=..."` | `/finances/accounts`, `/finances/accounts/{account_uuid}`, `/finances/categories`, `/finances/categories/{category_uuid}`, `/finances/subcategory`, `/finances/subcategory/{subcategory_uuid}` | PASS |
| App imports cleanly | `uv run python -c "from caramello.main import app; print('ok')"` | ok | PASS |
| Full test suite not regressed | `uv run python -m pytest -q` | 52 passed, 1 skipped, 1 xpassed, 4 pre-existing DB integration errors (no new failures) | PASS |

### Probe Execution

No probe scripts declared or found for Phase 7. Skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ACC-01 | 07-02 | Criar conta (nome, tipo, moeda) com resposta contendo uuid sem id/family_id | SATISFIED | `POST /finances/accounts`, `AccountReadPublic` schema, `test_create_account_returns_uuid` PASSED |
| ACC-02 | 07-02 | Listar, detalhar e atualizar contas da família | SATISFIED | `GET /finances/accounts`, `GET /finances/accounts/{account_uuid}`, `PATCH /finances/accounts/{account_uuid}`, `test_list_accounts_scoped_to_family` PASSED |
| ACC-03 | 07-02 | Arquivar conta via `is_active=false` sem perder histórico | SATISFIED | PATCH handler uses `setattr`, no `session.delete`. `test_archive_account` PASSED. |
| CAT-01 | 07-03 | Criar categoria de nível 1 para a família | SATISFIED | `POST /finances/categories`, `test_create_category` PASSED |
| CAT-02 | 07-03 | Criar subcategoria de nível 2 vinculada a categoria pai via `category_uuid` | SATISFIED | `POST /finances/subcategory`, `test_create_subcategory` PASSED |
| CAT-03 | 07-03 | Sistema rejeita nível 3 — máximo 2 níveis | SATISFIED | Structural enforcement: `Subcategory.category_id → Category.id`. No sub-subcategory endpoint exists. `test_finances_router_paths` confirms 6 paths only. |
| CAT-04 | 07-03 | Listar e atualizar categorias da família | SATISFIED | `GET /finances/categories`, `PATCH /finances/categories/{uuid}`, `GET/PATCH /subcategory/*` all implemented. `test_list_update_categories` PASSED. |
| AUTH-FIN-01 | 07-02 | Todos os endpoints exigem Bearer token válido (401 sem token) | PARTIAL | Bearer requirement enforced via `Depends(get_current_user)` + `HTTPBearer(auto_error=True)`. However, HTTPBearer returns **403**, not 401 as specified in REQUIREMENTS.md. This is a documented project-wide behavior (see `test_auth.py`, `07-RESEARCH.md` Open Question 2). Requires human decision. |
| AUTH-FIN-02 | 07-02 | Usuário só acessa recursos de famílias das quais é membro (403 caso contrário) | SATISFIED | `_require_family_access` raises 403 for non-members. `test_accounts_403_non_member` PASSED. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX markers found in phase-modified files | — | — |
| — | — | No placeholder/stub comments found | — | — |
| — | — | No `return null`/empty return stubs found | — | — |
| — | — | No `session.delete` in PATCH handlers | — | — |

No blockers found.

### Human Verification Required

#### 1. AUTH-FIN-01: 401 vs 403 for Missing Token

**Test:** Make an unauthenticated GET request to `/finances/accounts?family_uuid=<any-uuid>` (no Authorization header) and observe the HTTP status code.

**Expected (per REQUIREMENTS.md):** HTTP 401

**Actual behavior:** HTTP 403 (due to `HTTPBearer(auto_error=True)` — this is the FastAPI default when the Authorization header is missing)

**Why human:** The discrepancy between the requirement specification (401) and the project-wide implementation behavior (403) requires a product/architecture decision:
- **Option A:** Accept 403 as correct for this project — update REQUIREMENTS.md AUTH-FIN-01 to say "401 ou 403 sem token" (consistent with existing `test_auth.py` which already accepts both)
- **Option B:** Fix to return 401 — replace `HTTPBearer` with a custom security dependency in `shared/auth.py` that raises `HTTP_401_UNAUTHORIZED` instead of relying on HTTPBearer's default

This is the same open question documented in `07-RESEARCH.md §Open Question 2` and `07-PATTERNS.md §AUTH-FIN-01`. The test `test_accounts_require_auth` currently asserts `status_code == 403`, which passes but encodes the deviation. The decision affects all future phases (8, 9) that reuse `get_current_user`.

### Gaps Summary

No blocking gaps. All 9/9 truths verified. All ROADMAP success criteria satisfied. All 9 requirement IDs accounted for.

The only open item is AUTH-FIN-01's 401 vs 403 discrepancy — this is a documented, pre-existing project-wide behavior (also present in M1 auth layer), not a regression introduced by Phase 7. It surfaces here because REQUIREMENTS.md formally specifies 401. A human decision is required to either update the requirement text or fix the implementation.

---

_Verified: 2026-06-01T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
