---
phase: 04-dom-nio-family
plan: "04"
subsystem: domain-families
tags: [fastapi, sqlmodel, async, auth, families, keycloak, auto-join, rbac]
dependency_graph:
  requires:
    - phase: "04-03"
      provides: "families/ e users/ gerados pelo DSL, migration family_invitation, testes com xfail"
  provides:
    - "6 endpoints funcionais do domínio families (FAMILY-01, FAMILY-02, FAMILY-03, FAMILY-07 + D-07)"
    - "auto-join transparente em get_current_user (D-02)"
    - "ROADMAP e REQUIREMENTS atualizados com deferimento de FAMILY-04/05/06 (D-04)"
  affects:
    - src/caramello/families/operations.py
    - src/caramello/shared/auth.py
    - tests/test_family_operations.py
    - tests/test_auth.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
tech_stack:
  added: []
  patterns:
    - "session.add() é síncrono em SQLAlchemy async — usar MagicMock (não AsyncMock) nos testes"
    - "_require_owner / _require_member: helpers privados para verificação de role via query ao banco a cada request (T-04-11)"
    - "Import lazy PLC0415 (from caramello.families.models import ...) dentro da função para evitar ciclo shared/ <-> families/"
    - "Family.model_validate recebe model_dump(exclude_none=True) para não sobrescrever defaults do modelo"
    - "type: ignore[arg-type] nas chamadas .join() do SQLAlchemy — limitação conhecida de tipo do DSL SQLAlchemy com mypy"
key_files:
  created: []
  modified:
    - src/caramello/families/operations.py
    - src/caramello/shared/auth.py
    - tests/test_family_operations.py
    - tests/test_auth.py
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
key_decisions:
  - "model_dump(exclude_none=True) em registry_family para respeitar defaults do modelo Family (status='active')"
  - "type: ignore[arg-type] em chamadas .join() SQLAlchemy — limitação de tipos do DSL, comportamento em runtime correto"
  - "MagicMock para session.add() nos testes (era AsyncMock) — session.add() é síncrono em SQLAlchemy async; AsyncMock não executa side_effect sem await"
  - "FAMILY-04, FAMILY-05, FAMILY-06 deferidos para M2 conforme D-04; rastreabilidade via requirements_deferred no frontmatter do plano"
requirements-completed: [FAMILY-01, FAMILY-02, FAMILY-03, FAMILY-07]
duration: "~7min"
completed: "2026-05-26T19:19:00Z"
---

# Phase 4 Plan 04: Operações families e auto-join Summary

**6 endpoints de negócio do domínio families implementados com RBAC (owner/member) + auto-join transparente em get_current_user via FamilyInvitation pendente**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-26T19:12:00Z
- **Completed:** 2026-05-26T19:19:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `src/caramello/families/operations.py` reescrito com 6 endpoints funcionais (FAMILY-01/02/03/07 + D-07 pre-register/members), helpers `_require_owner` e `_require_member`, schemas locais `PreRegisterBody` e `FamilyMemberRead`. Anotação muda de `stub` para `implemented`.
- `src/caramello/shared/auth.py` estendido com bloco 7 (AUTO-JOIN): a cada login, se existe `FamilyInvitation` com `status='pending_login'` para o email do usuário, cria `FamilyMember(role='member')` e atualiza `invitation.status='joined'` — transparente para o cliente (D-02).
- Suite pytest 100% verde: 31 passed, 1 skipped (integration), 0 failed. Todos os testes que estavam XFAIL no plano 04-03 desbloqueados e passando.

## Endpoints implementados

| Path | Método | Status code | Autorização | Requisito |
|------|--------|-------------|-------------|-----------|
| `POST /families/registry` | POST | 201 | JWT | FAMILY-01 |
| `GET /families/families` | GET | 200 | JWT | FAMILY-02 |
| `GET /families/families/{uuid}` | GET | 200 / 403 | JWT + membro | FAMILY-03 |
| `POST /families/families/{uuid}/pre-register` | POST | 201 / 403 | JWT + owner | D-07 |
| `GET /families/families/{uuid}/members` | GET | 200 / 403 | JWT + membro | D-07 |
| `DELETE /families/families/{uuid}/members/{user_uuid}` | DELETE | 200 / 403 | JWT + owner | FAMILY-07 |

## Task Commits

1. **Task 1: Implementar families/operations.py com 6 operações + helpers** — `631b2fe` (feat)
2. **Task 2: Estender shared/auth.py com auto-join + ROADMAP/REQUIREMENTS** — `3746708` (feat)

## Files Created/Modified

- `src/caramello/families/operations.py` — reescrito: 6 endpoints com `_require_owner`/`_require_member`, `PreRegisterBody`, `FamilyMemberRead`; anotação `# CARAMELLO-GENERATED: implemented`
- `src/caramello/shared/auth.py` — bloco AUTO-JOIN inserido após SELECT do User; docstring atualizada com passo 7
- `tests/test_family_operations.py` — 6 linhas `pytest.xfail(...)` removidas; `session.add` corrigido para `MagicMock`
- `tests/test_auth.py` — `pytest.xfail` de `test_auto_join_on_login` removido; `session.add` corrigido para `MagicMock`
- `.planning/ROADMAP.md` — Phase 4: Requirements e Success Criteria atualizados; 04-04 marcado completo
- `.planning/REQUIREMENTS.md` — FAMILY-01/02/03/07 implementados; FAMILY-04/05/06 Deferred (D-04); nota explicativa adicionada

## Decisions Made

- `model_dump(exclude_none=True)` em `registry_family` para não sobrescrever `Family.status='active'` (default do modelo) quando `FamilyCreate.status=None` — sem essa proteção, `model_validate` falha com ValidationError.
- `# type: ignore[arg-type]` em chamadas `.join(FamilyMember, FamilyMember.family_id == Family.id)` — limitação conhecida do mypy com SQLAlchemy DSL; comportamento em runtime correto.
- `session.add = MagicMock(...)` nos testes: `AsyncMock` para um método síncrono cria coroutine que nunca é awaited → side_effect nunca executa. Corrigido em `test_family_operations.py` e `test_auth.py`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] model_validate(family_in) falha quando FamilyCreate.status=None**
- **Encontrado durante:** Task 1 (test_registry_creates_family_and_owner)
- **Issue:** `Family.status` é `str` (non-optional, default="active"), mas `FamilyCreate.status: str | None`. Ao chamar `Family.model_validate(family_in)` com `status=None`, SQLModel/Pydantic propaga o None e levanta `ValidationError`.
- **Fix:** Substituído `Family.model_validate(family_in)` por `Family.model_validate(family_in.model_dump(exclude_none=True))`.
- **Arquivos modificados:** `src/caramello/families/operations.py`
- **Commit:** `631b2fe`

**2. [Rule 1 - Bug] Testes com session.add como AsyncMock não capturam objetos adicionados**
- **Encontrado durante:** Tasks 1 e 2 (testes com XFAIL removidos)
- **Issue:** `mock_session = AsyncMock()` define `session.add` como `AsyncMock`. Em SQLAlchemy async, `session.add()` é SÍNCRONO (não awaited). Chamar `AsyncMock` sem `await` cria uma coroutine que nunca é consumida → `side_effect` nunca executa → lista `added` fica vazia.
- **Fix:** `mock_session.add = MagicMock(side_effect=lambda o: added.append(o))` em `test_family_operations.py` (test_registry) e `test_auth.py` (test_auto_join_on_login).
- **Arquivos modificados:** `tests/test_family_operations.py`, `tests/test_auth.py`
- **Commit:** `631b2fe`, `3746708`

**3. [Rule 3 - Blocking] Worktree estava em base antiga (pré-04-03) ao iniciar**
- **Encontrado durante:** Início da execução
- **Issue:** O worktree estava no commit `cf79e73` (pré-04-03), sem os diretórios `families/` e `users/`. O `reset --hard` para a base especificada pelo orchestrador (`ddb2d6c`) foi necessário.
- **Fix:** `git reset --hard ddb2d6c` (conforme instrução `<worktree_branch_check>`).
- **Arquivos modificados:** N/A (reset de estado do worktree)
- **Commit:** N/A

---

**Total deviations:** 3 auto-fixados (2 Rule 1 — Bug, 1 Rule 3 — Blocking)
**Impact on plan:** Todos os fixes necessários para corretude. Sem scope creep. Os bugs nos testes eram latentes (mascarados pelo xfail) — revelados ao remover os xfails.

## Issues Encountered

- Worktree iniciou em base antiga; resolvido com reset para base do orchestrador antes da primeira edição.
- mypy reportou 4 erros `arg-type` em chamadas `.join()` do SQLAlchemy — padrão conhecido; resolvido com `# type: ignore[arg-type]`.

## Known Stubs

Nenhum — todas as operações têm implementação real. `# CARAMELLO-GENERATED: implemented` na primeira linha confirma que o generator respeitará o arquivo em gerações futuras.

## Threat Flags

Nenhuma superfície nova além do que está no `<threat_model>` do plano 04-04. Os 8 threats (T-04-11 a T-04-18) estão cobertos pelas mitigações implementadas ou aceitos conforme documentado.

## Next Phase Readiness

- Phase 4 completa: FAMILY-01/02/03/07 entregues; FAMILY-04/05/06 deferidos para M2.
- Próximo passo: `/gsd-verify-work` para verificar a Phase 4 contra os Success Criteria atualizados, ou iniciar Phase 5 (MCP, Testes e Docker).

---
*Phase: 04-dom-nio-family*
*Completed: 2026-05-26*
