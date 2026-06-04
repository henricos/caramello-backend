---
phase: 09-concilia-o-relat-rios-mcp
fixed_at: 2026-06-04T10:28:16Z
review_path: .planning/phases/09-concilia-o-relat-rios-mcp/09-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-06-04T10:28:16Z
**Source review:** .planning/phases/09-concilia-o-relat-rios-mcp/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (5 Critical, 6 Warning)
- Fixed: 11
- Skipped: 0

## Fixed Issues

### CR-01: `update_entry` performs a meaningless account lookup — IDOR and auth bypass

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** 81bc9e7
**Applied fix:** Substituiu a consulta falsa `Account.id.isnot(None)` pela cadeia correta
`db_entry.movement_id → Movement.account_id → Account.family_id`. Agora resolve `Movement`
via `session.exec(select(Movement).where(Movement.id == entry_movement_id))` com 404 se não
encontrado, resolve `Account` via `Account.id == db_movement.account_id` com 404 se ausente,
e acessa `family_id` diretamente do objeto (resolvendo WR-01 implicitamente). Reutiliza
`db_movement_for_auth` como `db_movement` para o schema rico, eliminando a segunda consulta.

---

### CR-02: `by_member_breakdown` query is missing the leading FROM table — SQL error at runtime

**Files modified:** `src/caramello/finances/services.py`
**Commit:** 2d1fe0e
**Applied fix:** Inseriu `.select_from(FinancialEntry)` antes dos joins em `by_member_breakdown`,
garantindo que `FinancialEntry` seja a tabela raiz explícita do SELECT e evitando
`ProgrammingError` em runtime por falta de cláusula FROM.

---

### CR-03: `FinancialEntryRead`, `FinancialEntryCreate`, `FinancialEntryUpdate` missing `responsible_user_uuid`

**Files modified:** `src/caramello/finances/models.py`
**Commit:** 3f1be59
**Applied fix:** Adicionou `responsible_user_uuid: UUID | None = None` nas três classes de schema
DSL. Também corrigiu `is_recorrente` em `FinancialEntryCreate` de `bool | None = None` para
`bool = False`, consistente com a definição DSL (IN-01 resolvido no mesmo commit).

---

### CR-04: `account_balance` does not guard against `func.sum` returning a Python `float`

**Files modified:** `src/caramello/finances/services.py`
**Commit:** 25ae3a8
**Applied fix:** Substituiu `return total if total is not None else Decimal("0.00")` por duas
linhas: guarda `None` retornando `Decimal("0.00")`, e converte via `Decimal(str(total))` para
qualquer tipo numérico retornado pelo driver (float, Decimal, int).

---

### CR-05: `reconcile_movement` and `update_entry` fabricate `category_uuid` when Category lookup fails

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** ac9ce2c
**Applied fix:** Substituiu `uuid4()` como fallback por `raise HTTPException(status_code=404,
detail="Categoria não encontrada")` em ambas as funções `reconcile_movement` (linha ~1202) e
`update_entry` (linha ~1433). Remove os `getattr` fallbacks e acessa `db_category.uuid` e
`db_category.name` diretamente.

---

### WR-01: `update_entry` null-guard ordered after attribute access

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** 81bc9e7
**Applied fix:** Resolvido implicitamente pelo fix CR-01 — a reestruturação do bloco de auth
coloca a guarda `if db_account is None` antes do acesso a `db_account.family_id` e não usa
mais `getattr` com valor padrão 0.

---

### WR-02: `monthly_breakdown` member filter uses `session.execute` causing row-wrapping issues

**Files modified:** `src/caramello/finances/services.py`
**Commit:** 3a1f3be
**Applied fix:** Substituiu `session.execute()` + `fetchone()` + `user_row[0].id` por
`session.exec()` + `first()` + `user.id` para o lookup de membro em `monthly_breakdown`,
evitando `TypeError` quando o driver retorna Row escalar.

---

### WR-03: `import_movements_endpoint` sets `updated_at` from `created_at`

**Files modified:** `src/caramello/finances/operations.py`, `src/caramello/finances/services.py`
**Commit:** f78ad22
**Applied fix:** Em `operations.py`, substituiu `m.get("created_at", ...)` por
`m.get("updated_at", m.get("created_at", datetime.now(timezone.utc)))` no campo `updated_at`
do `MovementReadPublic`. Em `services.py`, adicionou `"updated_at": mvt.updated_at.isoformat()`
ao dict de movimento retornado por `import_movements`.

---

### WR-04: `FinancialEntryUpdatePublic.notes` cannot clear a note

**Files modified:** `src/caramello/finances/operations.py`
**Commit:** 91aaabe
**Applied fix:** Substituiu `if entry_in.notes is not None:` por
`if "notes" in entry_in.model_fields_set:` em `update_entry`, aplicando o mesmo padrão sentinel
já usado para `responsible_user_uuid`. Agora `{"notes": null}` limpa a nota e campo ausente
não toca o valor existente.

---

### WR-05: `test_import_deduplication` mock hash never matches computed hash

**Files modified:** `tests/test_finances_operations.py`
**Commit:** fd89d05
**Applied fix:** Calcula o hash real via `_compute_hash(account_id=10, row=real_row)` antes de
configurar o mock, usando `ParsedRow` com os mesmos dados do CSV. O mock de `fetchall` agora
retorna `[(real_hash,)]` em vez do hash fixo arbitrário. Adicionou import local de `Decimal`
e de `ParsedRow`, `_compute_hash` de `caramello.finances.services`.

Também reestruturou o mock `session.execute` para distinguir as duas chamadas distintas:
pre-check (retorna hash) e busca de UUID para `potential_duplicates` (retorna hash+uuid).

---

### WR-06: `test_update_entry` accepts 404 as a passing result — masks CR-01

**Files modified:** `tests/test_finances_operations.py`
**Commit:** fd89d05
**Applied fix:** Reestruturou o mock `_exec` com contador de chamadas, retornando os objetos
corretos em ordem: `FinancialEntry`, `Movement` (auth), `Account`, `FamilyMember` (para
`_require_family_access`), `Subcategory` (lookup + reload), `Category` (reload pós-commit).
Alterou `assert response.status_code in (200, 404)` para `assert response.status_code == 200`
e adicionou verificações de campos `subcategory_uuid` e `category_uuid` no body.

---

_Fixed: 2026-06-04T10:28:16Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
