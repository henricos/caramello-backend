---
phase: 04-dom-nio-family
verified: 2026-05-26T20:00:00Z
status: human_needed
score: 13/14 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Executar alembic upgrade head no banco familia_dev e confirmar que a migration 0b1c2d3e4f5a aplica sem erro"
    expected: "drop de invitee_email e expires_at, criação de email e status com default pending_login — alembic upgrade head retorna exit 0"
    why_human: "Requer banco PostgreSQL familia_dev rodando; o agente não pode conectar ao banco de dados externo"
  - test: "Fazer login com token Keycloak real de usuário com email pré-registrado via POST /families/families/{uuid}/pre-register"
    expected: "auto-join transparente: FamilyMember criado com role=member, invitation.status atualizado para joined — usuário vira membro sem nenhuma ação extra"
    why_human: "Requer Keycloak real e banco rodando; test_jit_provisioning está marcado SKIP por esse motivo"
---

# Phase 4: Domínio Family Verification Report

**Phase Goal:** Implementar o Domínio Family completo — entidades, relacionamentos, endpoints CRUD e convites de família — tornando a API funcional para o grupo familiar fechado (1–5 membros).
**Verified:** 2026-05-26T20:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                   | Status     | Evidence                                                                                                      |
|----|-----------------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------------------------------|
| 1  | src/caramello/users/ e src/caramello/families/ existem com models.py, router.py, operations.py | ✓ VERIFIED | Directories present with 4 files each; old src/caramello/user/ and src/caramello/family/ removed              |
| 2  | src/caramello/families/operations.py primeira linha == # CARAMELLO-GENERATED: implemented | ✓ VERIFIED | `head -1` returns `# CARAMELLO-GENERATED: implemented`                                                        |
| 3  | 6 endpoints de negócio implementados: POST /families/registry, GET /families/families, GET /families/families/{uuid}, POST .../pre-register, GET .../members, DELETE .../members/{user_uuid} | ✓ VERIFIED | 27 routes registered; all 6 paths present in app.routes; 6 `@router` decorators in operations.py              |
| 4  | POST /families/registry cria Family + FamilyMember(role='owner') na mesma transação (FAMILY-01) | ✓ VERIFIED | session.flush() + FamilyMember(role="owner") in operations.py lines 142-150; test_registry_creates_family_and_owner PASSES |
| 5  | GET /families/families retorna apenas famílias do usuário via JOIN com family_member (FAMILY-02) | ✓ VERIFIED | SELECT Family JOIN FamilyMember WHERE user_id in operations.py lines 166-171; test_list_families_only_mine PASSES |
| 6  | GET /families/families/{uuid} retorna 200 se membro, 403 se não membro (FAMILY-03)      | ✓ VERIFIED | _require_member helper raises HTTP_403_FORBIDDEN; test_get_family_detail_non_member_returns_403 PASSES         |
| 7  | DELETE /families/families/{uuid}/members/{user_uuid} requer role=owner, 403 caso contrário (FAMILY-07) | ✓ VERIFIED | _require_owner helper raises 403; test_remove_member_non_owner_returns_403 PASSES                              |
| 8  | shared/auth.py implementa auto-join: FamilyInvitation pendente por email → FamilyMember(role=member) (D-02) | ✓ VERIFIED | Block 7 AUTO-JOIN in auth.py lines 199-223; test_auto_join_on_login PASSES                                     |
| 9  | dsl/entities/family_invitation.yaml redesenhado: sem invitee_email/expires_at; com email e status default pending_login | ✓ VERIFIED | Python verification: field_names={uuid,family_id,status,inviter_id,id,email,created_at}; status.default=pending_login |
| 10 | dsl/entities user.yaml/family.yaml/family_member.yaml têm domain plural (users/families) | ✓ VERIFIED | Python verification: all 4 entity YAMLs have correct plural domain                                            |
| 11 | scripts/generate_code.py emite prefix="/{domain}/{url_table_name}" com hifens (D-10)    | ✓ VERIFIED | generate_router produces `prefix="/families/family-invitation"` for FamilyInvitation entity                    |
| 12 | FAMILY-04, FAMILY-05, FAMILY-06 marcados como Deferred (D-04) no REQUIREMENTS.md       | ✓ VERIFIED | Lines 139-141: FAMILY-04/05/06 show "Deferred (D-04)" in traceability table                                   |
| 13 | Suite pytest 100% verde: 31 passed, 1 skipped (integration), 0 failed                   | ✓ VERIFIED | `uv run pytest -q` → 31 passed, 1 skipped, 0 failed                                                           |
| 14 | ROADMAP.md Phase 4 Success Criteria atualizado para refletir fluxo de pré-registro (não código de convite) | ✗ FAILED  | ROADMAP.md lines 88-93 still show OLD SCs with /family/families paths and FAMILY-04/05/06 endpoints; only a note (line 109) was appended, not a replacement |

**Score:** 13/14 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | FAMILY-04: código de convite reutilizável | Phase 4 → M2 | REQUIREMENTS.md traceability; ROADMAP note line 109; decision D-04 in 04-CONTEXT.md |
| 2 | FAMILY-05: solicitação de entrada via convite | Phase 4 → M2 | REQUIREMENTS.md traceability; ROADMAP note line 109; decision D-04 in 04-CONTEXT.md |
| 3 | FAMILY-06: aprovar/rejeitar solicitações | Phase 4 → M2 | REQUIREMENTS.md traceability; ROADMAP note line 109; decision D-04 in 04-CONTEXT.md |

### Required Artifacts

| Artifact                                                                      | Expected                                           | Status     | Details                                                                          |
|-------------------------------------------------------------------------------|----------------------------------------------------|------------|----------------------------------------------------------------------------------|
| `src/caramello/families/operations.py`                                        | 6 endpoints implementados (FAMILY-01/02/03/07)     | ✓ VERIFIED | 295 lines; 6 @router decorators; # CARAMELLO-GENERATED: implemented              |
| `src/caramello/families/models.py`                                            | Family, FamilyMember, FamilyInvitation com redesign| ✓ VERIFIED | FamilyInvitation has email+status fields; no invitee_email or expires_at          |
| `src/caramello/users/operations.py`                                           | GET /users/me implementado                         | ✓ VERIFIED | # CARAMELLO-GENERATED: implemented; prefix="/users"                              |
| `src/caramello/families/router.py`                                            | CRUD com prefixes plurais                          | ✓ VERIFIED | prefix="/families/family" and prefix="/families/family-invitation"               |
| `src/caramello/users/router.py`                                               | prefix="/users/user"                               | ✓ VERIFIED | Confirmed via grep                                                                |
| `src/caramello/main.py`                                                       | Imports plurais; operations antes de router         | ✓ VERIFIED | families_operations registered at idx 10 before families_router idx 18           |
| `src/caramello/shared/auth.py`                                                | AUTO-JOIN block inserido após JIT                  | ✓ VERIFIED | Block 7 AUTO-JOIN lines 199-223; FamilyInvitation.status=pending_login check     |
| `alembic/versions/20260526_1500_redesign_family_invitation_pre_register.py`   | Migration drop invitee_email/expires_at + add email/status | ✓ VERIFIED | revision=0b1c2d3e4f5a; down_revision=a1b2c3d4e5f6; correct upgrade/downgrade     |
| `dsl/operations/family.yaml`                                                  | domain=families + 6 operações                      | ✓ VERIFIED | 6 operations: registry_family, list_my_families, get_family_detail, pre_register_member, list_members, remove_member |
| `scripts/generate_code.py`                                                    | url_table_name, DOMAIN_TO_ENTITY_NAME, ruff dirs   | ✓ VERIFIED | Lines 32 (DOMAIN_TO_ENTITY_NAME), 350 (url_table_name), 376 (prefix pattern)     |
| `.planning/REQUIREMENTS.md`                                                   | FAMILY-01/02/03/07 Implementado; 04/05/06 Deferred | ✓ VERIFIED | Traceability table and requirement checkboxes correctly updated                   |
| `.planning/ROADMAP.md` Phase 4 Success Criteria                               | Updated to reflect pre-registration flow           | ✗ PARTIAL  | Only a note appended (line 109); SCs 1-6 still show old /family/families paths and FAMILY-04/05/06 endpoints |

### Key Link Verification

| From                                         | To                                      | Via                                                                | Status     | Details                                                                     |
|----------------------------------------------|-----------------------------------------|--------------------------------------------------------------------|------------|-----------------------------------------------------------------------------|
| POST /families/registry                      | Family.id → FamilyMember.family_id      | session.add(Family) → session.flush() → FamilyMember(role="owner")| ✓ WIRED    | operations.py lines 136-151                                                 |
| shared/auth.py get_current_user              | FamilyMember (auto-join)                | SELECT FamilyInvitation WHERE email + status=pending_login → INSERT FamilyMember(role=member) | ✓ WIRED    | auth.py lines 199-223; lazy import from caramello.families.models           |
| families_operations.router                  | app routing                             | app.include_router(families_operations.router) line 55 in main.py  | ✓ WIRED    | Registered at idx 10; before families_router at idx 18                      |
| GET /families/families/{uuid} (FAMILY-03)    | 403 for non-members                     | _require_member helper raises HTTP_403_FORBIDDEN                   | ✓ WIRED    | operations.py lines 94-117; test_get_family_detail_non_member_returns_403 PASSES |
| DELETE /families/families/{uuid}/members/{user_uuid} | 403 for non-owners                | _require_owner helper raises HTTP_403_FORBIDDEN                   | ✓ WIRED    | operations.py lines 66-91; test_remove_member_non_owner_returns_403 PASSES  |
| alembic/env.py                              | caramello.families.models              | import caramello.families.models (updated from family)             | ✓ WIRED    | alembic/env.py imports updated in plan 04-03                                |

### Data-Flow Trace (Level 4)

| Artifact                                          | Data Variable    | Source                                           | Produces Real Data    | Status     |
|---------------------------------------------------|------------------|--------------------------------------------------|-----------------------|------------|
| `src/caramello/families/operations.py:list_my_families` | result.all()     | SELECT Family JOIN FamilyMember WHERE user_id    | DB query with JOIN    | ✓ FLOWING  |
| `src/caramello/families/operations.py:registry_family`  | db_family        | session.add(Family) + flush + FamilyMember       | DB insert             | ✓ FLOWING  |
| `src/caramello/shared/auth.py:get_current_user`         | pending_inv      | SELECT FamilyInvitation WHERE email + status     | DB query conditional  | ✓ FLOWING  |

### Behavioral Spot-Checks

| Behavior                                     | Command                                                          | Result                          | Status  |
|----------------------------------------------|------------------------------------------------------------------|---------------------------------|---------|
| App boots and routes registered              | python -c "from caramello.main import app; print(len(app.routes))" | 27 routes                      | ✓ PASS  |
| /families/registry endpoint registered       | Check app.routes for /families/registry                          | Found at idx 10                 | ✓ PASS  |
| families_operations before families_router   | registry_idx=10 < family/{uuid}_idx=18                          | Order correct                   | ✓ PASS  |
| All 31 tests pass                            | uv run pytest -q                                                 | 31 passed, 1 skipped, 0 failed  | ✓ PASS  |
| ruff + mypy clean on operations and auth     | uv run ruff check ... && uv run mypy ...                         | All checks passed               | ✓ PASS  |
| generate_router emits correct prefix         | generate_router(FamilyInvitation entity)                         | prefix="/families/family-invitation" | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                        | Status       | Evidence                                                                  |
|-------------|-------------|--------------------------------------------------------------------|--------------|---------------------------------------------------------------------------|
| FAMILY-01   | 04-04       | POST /families/registry cria família + torna-se owner              | ✓ SATISFIED  | operations.py lines 125-152; test_registry_creates_family_and_owner PASSES |
| FAMILY-02   | 04-04       | GET /families/families lista famílias do usuário                   | ✓ SATISFIED  | operations.py lines 160-171; test_list_families_only_mine PASSES           |
| FAMILY-03   | 04-04       | GET /families/families/{uuid} retorna 200 se membro, 403 senão     | ✓ SATISFIED  | _require_member helper; test_get_family_detail_non_member_returns_403 PASSES |
| FAMILY-04   | 04-04       | Código de convite reutilizável (owner)                             | DEFERRED M2  | Decision D-04; REQUIREMENTS.md Traceability: "Deferred (D-04)"           |
| FAMILY-05   | 04-04       | Solicitação de entrada via convite                                  | DEFERRED M2  | Decision D-04; REQUIREMENTS.md Traceability: "Deferred (D-04)"           |
| FAMILY-06   | 04-04       | Aprovação/rejeição de solicitações                                  | DEFERRED M2  | Decision D-04; REQUIREMENTS.md Traceability: "Deferred (D-04)"           |
| FAMILY-07   | 04-04       | DELETE .../members/{user_uuid} requer role=owner                   | ✓ SATISFIED  | _require_owner helper; test_remove_member_non_owner_returns_403 PASSES    |

### Anti-Patterns Found

| File                                          | Line | Pattern                                                   | Severity  | Impact                                              |
|-----------------------------------------------|------|-----------------------------------------------------------|-----------|-----------------------------------------------------|
| `.planning/ROADMAP.md`                        | 86   | **Requirements** line still lists FAMILY-04/05/06         | ⚠ Warning | Documentation inconsistency; does not affect code   |
| `.planning/ROADMAP.md`                        | 88-93 | Success Criteria block uses old /family/families paths and lists SCs 3-5 covering FAMILY-04/05/06 | ⚠ Warning | Misleading if read without the note on line 109; does not affect code |
| `.planning/REQUIREMENTS.md`                  | 37   | USER-01 still references `/user/me` (old path, was /users/me) | ℹ Info    | Pre-existing from Phase 3; out of scope for Phase 4 |

### Human Verification Required

#### 1. Alembic Migration Application

**Test:** With the `familia_dev` PostgreSQL database running, run `alembic upgrade head` to apply migration `0b1c2d3e4f5a` (redesign_family_invitation_pre_register).
**Expected:** Command exits 0. The `family_invitation` table: columns `invitee_email` and `expires_at` are removed; columns `email` (NOT NULL) and `status` (NOT NULL, default `pending_login`) are added.
**Why human:** Requires the actual PostgreSQL `familia_dev` database to be running and accessible. The agent cannot connect to external databases.

#### 2. Auto-Join End-to-End Flow (D-02)

**Test:**
1. Create a family via `POST /families/registry` with a valid Keycloak token
2. Call `POST /families/families/{uuid}/pre-register` with `{"email": "newuser@example.com"}` (as owner)
3. Obtain a Keycloak JWT for `newuser@example.com` (or simulate their first login)
4. Make any authenticated request with that token (e.g. `GET /families/families`)

**Expected:** After step 4, `newuser@example.com` automatically becomes a FamilyMember with `role=member` in the pre-registered family — no explicit join action required. The `FamilyInvitation.status` changes to `joined`.
**Why human:** Requires a running Keycloak instance with a real JWT token and a connected PostgreSQL database. The existing `test_jit_provisioning` is SKIP for the same reason.

### Gaps Summary

The ROADMAP.md Phase 4 block has **documentation-only gaps**: the `Requirements` line (line 86) still lists all 7 family requirements without marking FAMILY-04/05/06 as deferred, and the `Success Criteria` block (lines 88-93) was not replaced with the new pre-registration flow SCs — only a clarifying note was appended on line 109.

This is a WARNING (not a BLOCKER) because:
1. The actual code fully implements FAMILY-01, FAMILY-02, FAMILY-03, and FAMILY-07
2. The REQUIREMENTS.md traceability table and requirement checkboxes are correctly updated (FAMILY-01/02/03/07 marked implemented; FAMILY-04/05/06 marked Deferred D-04)
3. The ROADMAP note on line 109 explicitly acknowledges the SCs are stale
4. FAMILY-04/05/06 deferral was a deliberate scope decision (D-04) approved during planning

The two human verification items (migration application and E2E auto-join flow) are genuine gaps that cannot be verified without running infrastructure.

---

_Verified: 2026-05-26T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
