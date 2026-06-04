---
phase: 06-funda-o-dsl-schema
reviewed: 2026-05-31T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - scripts/generate_code.py
  - dsl/schema.yaml
  - dsl/entities/account.yaml
  - dsl/entities/movement.yaml
  - dsl/entities/financial_entry.yaml
  - dsl/entities/category.yaml
  - dsl/entities/subcategory.yaml
  - dsl/manifest.yaml
  - dsl/operations/finances.yaml
  - src/caramello/finances/__init__.py
  - src/caramello/finances/models.py
  - src/caramello/finances/router.py
  - src/caramello/finances/operations.py
  - alembic/env.py
  - alembic/versions/0002_finances_schema.py
  - tests/test_generator.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-31
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 6 delivered DSL generator extensions (Decimal→Numeric, filters→Index), five financial
domain YAML entities, generated SQLModel models, a CRUD router, an operations stub, Alembic
`naming_convention` in `env.py`, and migration `0002_finances_schema.py`.

The Alembic migration is structurally correct — FK creation order is right, NUMERIC(15,2) is
used for `amount`, and the downgrade cascade is reversed properly. The `naming_convention` setup
in `env.py` is in the correct order (before model imports). The generator's Decimal handling and
`__table_args__` emission are also correct.

However, four blockers require attention before this code can serve real traffic: the entire
finances domain is unreachable (router never registered), the generated `operations.py` has a
type annotation that would crash at runtime, all list endpoints expose cross-family data, and
the generator silently discards the `unique` constraint on any `Decimal` field without raising
an error. There are also five warnings covering naming, missing validation, and test gaps.

---

## Critical Issues

### CR-01: Finances router never registered — all CRUD endpoints are unreachable

**File:** `src/caramello/main.py`
**Issue:** `src/caramello/finances/router.py` is generated but never imported or registered with
`app.include_router()` in `main.py`. All five entities' CRUD routes (`/finances/account`,
`/finances/movement`, `/finances/financial-entry`, `/finances/category`, `/finances/subcategory`)
are dead. The CLAUDE.md explicitly flags this as a required manual step after generation: "After
generating a new entity, the router import and `app.include_router()` call in
`src/caramello/main.py` must be added by hand." The step was skipped.

**Fix:**
```python
# src/caramello/main.py — add after families imports
from caramello.finances import operations as finances_operations
from caramello.finances import router as finances_router

# inside the router registration block, operations before CRUD (same D-06 rule):
app.include_router(finances_operations.router)
app.include_router(finances_router.router)
```

---

### CR-02: `operations.py` uses wrong type for `current_user` — runtime crash

**File:** `src/caramello/finances/operations.py:13`
**Issue:** The generated stub annotates the dependency parameter as `current_user: Account =
Depends(get_current_user)`. `get_current_user` (in `shared/auth.py`) always returns a `User`
object, not an `Account`. FastAPI validates the return type of a dependency against the declared
parameter type at injection time — passing a `User` where `Account` is expected will raise a
`422` or `500` once any other endpoint in this operations module is implemented. The root cause
is in the generator at `scripts/generate_code.py:557`:

```python
f"current_user: {domain_class} = Depends(get_current_user)"
```

`domain_class` is `Account` for the `finances` domain — it should always be `User`.

**Fix in generator (`scripts/generate_code.py`, `generate_operations` function):**
```python
# Replace the body_parts.append block, changing the parameter signature
body_parts.append(
    f'@router.{method}("{decorator_path}", response_model={domain_class}Read)\n'
    f"async def {name}("
    f"current_user: User = Depends(get_current_user)"
    f") -> {domain_class}:\n"
    f'    """{description}"""\n'
    f"    raise NotImplementedError\n"
)
```

Also update the header to always import `User`:
```python
header = f"""{ANNOTATION_STUB}
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.users.models import User
from caramello.{domain}.models import {domain_class}, {domain_class}Read

router = APIRouter(prefix="/{domain}", tags=["{domain_class}"])

"""
```

**Fix in generated file (`src/caramello/finances/operations.py`):** Regenerate after fixing
generator, or manually correct immediately:
```python
from caramello.users.models import User

async def list_accounts(current_user: User = Depends(get_current_user)) -> AccountRead:
```

---

### CR-03: All list endpoints return cross-family data — authorization bypass

**File:** `src/caramello/finances/router.py:52-59, 130-137, 209-217, 288-295, 365-372`
**Issue:** Every `GET /` list endpoint calls `select(<Entity>)` with no family filter. An
authenticated user from Family A can retrieve accounts, movements, categories, and subcategories
belonging to Family B. The `Account` and `Category` tables both have a `family_id` column that
should be used to scope results to the authenticated user's family. `Movement` has an
`account_id` FK that links back to `account.family_id`. `Subcategory` links via
`category_id → category.family_id`. This is a systematic authorization gap generated uniformly
by the CRUD template in `generate_router`.

This is a structural limitation of the generic CRUD generator — it cannot emit family-scoped
queries without knowing the family membership of the current user. The operations stub in
`operations.py` is intended to hold such domain-specific logic. However, the generic CRUD
router must at minimum not be exposed publicly while this gap exists.

**Fix (immediate — restrict account list to authenticated user's family):**
```python
# read_accounts — requires joining current user's family memberships
from caramello.families.models import FamilyMember

@account_router.get("/", response_model=list[AccountRead])
async def read_accounts(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Account]:
    # Scope to families the authenticated user belongs to
    member_stmt = select(FamilyMember.family_id).where(
        FamilyMember.user_id == current_user.id
    )
    statement = (
        select(Account)
        .where(Account.family_id.in_(member_stmt))
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(statement)
    return list(result.all())
```

The same scoping must be applied to Category (direct `family_id`), Movement (via
`account_id → account.family_id`), Subcategory (via `category_id → category.family_id`),
and FinancialEntry (via `subcategory_id → subcategory.category_id → category.family_id`).

---

### CR-04: `Decimal` field with `unique=True` silently discards the uniqueness constraint in the generator

**File:** `scripts/generate_code.py:93-125`
**Issue:** In `get_field_definition`, `unique=True` is appended to `field_args` at line 99.
However, when `ftype == "Decimal"`, the function returns early at line 117-122 using only
`sa_column=Column(Numeric(15, 2), ...)`, completely ignoring `field_args`. Any YAML field of
type `Decimal` with `unique: true` will have its uniqueness constraint silently dropped in the
generated model without any warning to the developer. No current financial field is affected
(the `amount` field correctly lacks `unique`), but the generator is broken for this combination
and will produce incorrect output in a future entity without any diagnostic.

**Fix (`scripts/generate_code.py`, `get_field_definition`, around line 117):**
```python
if ftype == "Decimal":
    if field.get("unique"):
        raise ValueError(
            f"Field '{fname}': Decimal fields cannot use unique=True with sa_column "
            f"(Pitfall 3). Use a separate UniqueConstraint in filters: instead."
        )
    nullable_kw = "nullable=False" if not is_nullable else "nullable=True"
    return (
        f"    {fname}: {type_str} = "
        f"Field(sa_column=Column(Numeric(15, 2), {nullable_kw}))"
    )
```

---

## Warnings

### WR-01: All five financial entity YAMLs violate their own schema — `id` field missing `nullable`

**File:** `dsl/entities/account.yaml:11-14`, `dsl/entities/movement.yaml:11-14`,
`dsl/entities/financial_entry.yaml:11-14`, `dsl/entities/category.yaml:11-14`,
`dsl/entities/subcategory.yaml:11-14`
**Issue:** `dsl/schema.yaml` declares `nullable` as required for every field item. All five
financial entity YAMLs define their `id` primary-key field without a `nullable` key. The
generator handles this silently (`field.get("nullable", True)`) because primary-key logic
overrides the value anyway, but the YAML is invalid against the declared schema. If a linter
or CI schema-validation step is added, all five files will fail.

**Fix:** Add `nullable: false` to the `id` field in each financial entity YAML:
```yaml
  - name: id
    type: int
    primary_key: true
    nullable: false
    description: "Chave primária interna (numérica)."
```

---

### WR-02: `generate_operations` does not guard against `NotImplementedError` reaching production

**File:** `src/caramello/finances/operations.py:15` (generated stub)
**Issue:** The stub endpoint `list_accounts` raises `NotImplementedError` unconditionally. If
the finances router and this operations router are both registered in `main.py`, any client
hitting `GET /finances/account` (without trailing slash — matching operations.py) will receive
an unhandled `500 Internal Server Error` instead of a `501 Not Implemented`. FastAPI does not
catch `NotImplementedError` by default. This creates user-facing 500s that leak internal
implementation state.

**Fix:** Change the stub body to return a proper HTTP 501:
```python
from fastapi import HTTPException

raise HTTPException(status_code=501, detail="Not implemented")
```

Or update the generator template in `scripts/generate_code.py:560` to emit this pattern.

---

### WR-03: Route conflict between `operations.py` and `router.py` for `GET /finances/account`

**File:** `src/caramello/finances/operations.py:12`, `src/caramello/finances/router.py:51`
**Issue:** `operations.py` registers `GET /finances/account` (no trailing slash, via
`APIRouter(prefix="/finances")` + `@router.get("/account")`). `router.py` registers
`GET /finances/account/` (with trailing slash, via `APIRouter(prefix="/finances/account")` +
`@account_router.get("/")`). FastAPI treats these as different routes, but some HTTP clients
normalize trailing slashes. When both routers are registered (see CR-01 fix), users calling
`GET /finances/account` will hit the stub that raises `NotImplementedError` (WR-02), masking
the working CRUD list endpoint. The stub's path should be distinct from CRUD paths, or the
operations stub should be removed once the business logic operations supersede CRUD.

**Fix:** Change the operations stub path to avoid overlapping with CRUD:
```yaml
# dsl/operations/finances.yaml
operations:
  - name: list_accounts
    method: GET
    path: /finances/accounts  # plural or a distinct path
```

---

### WR-04: `competencia_month` accepts values outside 1-12 — no DB-level check constraint

**File:** `dsl/entities/financial_entry.yaml:41-44`, `src/caramello/finances/models.py:136`
**Issue:** `competencia_month` is declared as `type: int` with no validation constraints.
PostgreSQL will accept `0`, `-5`, or `13` without error. There is no check constraint in the
migration (`alembic/versions/0002_finances_schema.py`) and no Pydantic validator in the
`FinancialEntry` or `FinancialEntryCreate` models. This allows storing logically invalid
month values that would corrupt period-based financial reports.

**Fix:** Add a check constraint to the migration:
```python
# In 0002_finances_schema.py upgrade(), after creating financial_entry table:
op.create_check_constraint(
    "ck_financial_entry_competencia_month",
    "financial_entry",
    "competencia_month >= 1 AND competencia_month <= 12",
)
```

And add a Pydantic validator to `FinancialEntryCreate` (or extend the DSL schema to support
`min`/`max` constraints that generate both the DB check and the Pydantic validator).

---

### WR-05: `_run_ruff_fix` swallows subprocess errors silently

**File:** `scripts/generate_code.py:978-986`
**Issue:** Both `subprocess.run` calls in `_run_ruff_fix` use `capture_output=True` without
`check=True`. If `ruff` fails (not installed, syntax error in generated code, or path issues),
the error is silently discarded and the generator exits with "Generation Complete." as if
everything succeeded. A developer would not know that the generated code was not linted or
formatted.

**Fix:**
```python
def _run_ruff_fix(src_dir: Path) -> None:
    import subprocess

    dirs = [...]
    if not dirs:
        return
    result = subprocess.run(
        ["python", "-m", "ruff", "check", "--fix", "--unsafe-fixes", *dirs],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):  # ruff exits 1 on unfixed issues (acceptable)
        print(f"  WARNING: ruff check exited {result.returncode}: {result.stderr}")

    result = subprocess.run(
        ["python", "-m", "ruff", "format", *dirs],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  WARNING: ruff format exited {result.returncode}: {result.stderr}")
```

---

## Info

### IN-01: `read_financialentrys`, `read_categorys`, `read_subcategorys` — incorrect English pluralization

**File:** `src/caramello/finances/router.py:210, 288, 365`
**Issue:** The generator pluralizes by appending `s` to the entity name lowercased, producing
`financialentrys`, `categorys`, `subcategorys`. These are incorrect English plurals and appear
in the OpenAPI spec as operation IDs, affecting API discoverability and client SDK generation.
The same pattern affects `FamilyInvitation` → `familyinvitations` (two s's produces one), but
for irregular plurals the output is wrong.

**Fix:** Add irregular plurals to the generator (similar to the `DOMAIN_TO_ENTITY_NAME` map):
```python
ENTITY_PLURAL: dict[str, str] = {
    "FinancialEntry": "financialentries",
    "Category": "categories",
    "Subcategory": "subcategories",
    "Family": "families",
}
# Use in generate_router: var_name_plural = ENTITY_PLURAL.get(name, f"{var_name}s")
```

---

### IN-02: No test for finances router registration in `main.py`

**File:** `tests/test_generator.py`
**Issue:** There is no test that verifies `src/caramello/finances/router.py` and
`src/caramello/finances/operations.py` are imported and registered in `main.py`. The existing
test `test_generated_router_requires_auth` only checks `users/router.py`. This allowed CR-01
to land undetected.

**Fix:** Add a test:
```python
def test_finances_router_registered_in_main():
    """Phase 6: finances router and operations must be registered in main.py."""
    main_path = REPO_ROOT / "src/caramello/main.py"
    content = main_path.read_text()
    assert "from caramello.finances import router as finances_router" in content, (
        "finances router must be imported in main.py"
    )
    assert "app.include_router(finances_router.router)" in content, (
        "finances router must be registered with app.include_router"
    )
```

---

### IN-03: No DSL schema validation at generation time — `dsl/schema.yaml` is decorative

**File:** `scripts/generate_code.py:41-48` (`load_yaml`)
**Issue:** The generator loads YAML files and uses them directly without validating against
`dsl/schema.yaml`. The schema file documents required fields (`nullable`, `domain`, etc.) but
is never enforced. The five financial entity YAMLs (WR-01) would fail validation if it were
applied, and future developers may omit required fields without realizing it until a runtime
error surfaces.

**Fix:** Add schema validation in the generator using `jsonschema` (already indirectly available
via `datamodel-code-generator` dependency tree) or `pydantic`:
```python
# In load_yaml or in main() after loading each entity file:
import jsonschema
schema = load_yaml(DSL_DIR / "schema.yaml")
try:
    jsonschema.validate(data, schema)
except jsonschema.ValidationError as exc:
    raise ValueError(f"{entity_file} fails schema validation: {exc.message}") from exc
```

---

_Reviewed: 2026-05-31_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
