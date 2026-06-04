---
phase: 03-estrutura-por-dominios-e-autenticacao
reviewed: 2026-05-25T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - scripts/generate_code.py
  - src/caramello/shared/auth.py
  - src/caramello/core/config.py
  - src/caramello/main.py
  - src/caramello/user/models.py
  - src/caramello/user/router.py
  - src/caramello/user/operations.py
  - src/caramello/family/models.py
  - src/caramello/family/router.py
  - alembic/env.py
  - tests/test_auth.py
  - tests/test_generator.py
  - tests/test_user_operations.py
  - tests/conftest.py
findings:
  critical: 5
  warning: 6
  info: 3
  total: 14
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-25
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

This phase introduces domain-based structure (user/, family/), a Keycloak JWT authentication layer, and a DSL code generator. The auth layer (shared/auth.py) is sound in its core approach — JWKS caching, RS256 enforcement, JIT provisioning via `INSERT ON CONFLICT DO NOTHING`. However, five blockers were found that expose security weaknesses or guarantee broken behavior at runtime: audience verification is permanently disabled, internal identity data leaks through public schemas, all list endpoints have zero authorization filtering, an empty operations file crashes the generator, and the conftest test fixture bypasses lifespan (meaning auth tests do not actually trigger JWKS loading). Six additional warnings cover logic gaps that will surface in production.

---

## Critical Issues

### CR-01: JWT Audience Verification Permanently Disabled

**File:** `src/caramello/shared/auth.py:152-153`
**Issue:** `options={"verify_aud": False}` is passed with no conditional — audience is never checked. The comment says "começar com verify_aud=False" and defers activation to a future plan, but there is no mechanism (no config flag, no feature toggle) that would ever enable it without a manual code edit. Any RS256-signed token from the same Keycloak realm issued to *any* client (mobile app, admin console, another service) will be accepted by this API. This violates OIDC security requirements and allows token reuse across services.
**Fix:**
```python
# In core/config.py, add:
KEYCLOAK_VERIFY_AUD: bool = True

# In shared/auth.py:
payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    options={"verify_aud": settings.KEYCLOAK_VERIFY_AUD},
    audience=settings.KEYCLOAK_CLIENT_ID if settings.KEYCLOAK_VERIFY_AUD else None,
)
```

---

### CR-02: `idp_sub` (Keycloak internal sub claim) Exposed in UserRead and UserCreate

**File:** `src/caramello/user/models.py:37,45,51`
**Issue:** `UserRead` includes `idp_sub: str` (line 37), `UserCreate` includes `idp_sub: str` (line 45), and `UserUpdate` includes `idp_sub: str | None = None` (line 51). The `idp_sub` field is the Keycloak `sub` claim — an internal identity provider identifier that clients have no legitimate reason to read or set. Exposing it in `UserRead` leaks implementation details and cross-correlates identity. Allowing it in `UserCreate`/`UserUpdate` lets any authenticated user set or change the idp_sub of any user record, enabling account takeover — any user can `PATCH /user/{uuid}` with `{"idp_sub": "victim-sub"}` and hijack that identity for JIT provisioning.
**Fix:**
```python
class UserRead(SQLModel):
    uuid: UUID
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime

class UserCreate(SQLModel):
    email: EmailStr
    name: str

class UserUpdate(SQLModel):
    email: EmailStr | None = None
    name: str | None = None
```

---

### CR-03: All List Endpoints Return All Records — Zero Authorization Filtering

**File:** `src/caramello/user/router.py:36`, `src/caramello/family/router.py:45`, `src/caramello/family/router.py:125`
**Issue:** `GET /user/` returns every user in the database. `GET /family/` returns every family. `GET /family_invitation/` returns every invitation. The `get_current_user` dependency proves the caller is authenticated but the result (`_`) is discarded — no ownership or membership check is applied. On a multi-family system any authenticated member can enumerate all other users, families they do not belong to, and invitations addressed to other users. This is a broken access control (OWASP A01).
**Fix:** Filter by the current user's context, for example for families:
```python
@family_router.get("/", response_model=list[FamilyRead])
async def read_familys(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[Family]:
    stmt = (
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == current_user.id)
        .offset(offset)
        .limit(limit)
    )
    result = await session.exec(stmt)
    return list(result.all())
```
Apply an equivalent ownership filter to `/user/` (only same family members) and `/family_invitation/` (only invitations where `inviter_id == current_user.id` or `invitee_email == current_user.email`).

---

### CR-04: `FamilyInvitationRead` Leaks Internal Integer IDs

**File:** `src/caramello/family/models.py:96-103`
**Issue:** `FamilyInvitationRead` exposes `family_id: int` and `inviter_id: int` — the raw internal database primary keys. Project conventions (CLAUDE.md: "External URLs and API responses use `uuid`, never `id`") explicitly forbid this. Internal integer IDs allow enumeration attacks and break the abstraction layer. Similarly, `FamilyInvitationCreate` accepts `family_id: int` and `inviter_id: int` as direct inputs (lines 107-108), meaning any caller can forge an invitation on behalf of any user (any `inviter_id`) for any family (`family_id`), bypassing membership checks.
**Fix:**
```python
class FamilyInvitationRead(SQLModel):
    uuid: UUID
    family_uuid: UUID      # resolved from family.uuid
    inviter_uuid: UUID     # resolved from inviter.uuid
    invitee_email: EmailStr
    status: str
    created_at: datetime
    expires_at: datetime

class FamilyInvitationCreate(SQLModel):
    family_uuid: UUID      # looked up; caller cannot forge a raw id
    invitee_email: EmailStr
    expires_at: datetime
    # inviter resolved from current_user in the endpoint, not accepted from client
```

---

### CR-05: Generator Crashes on Empty Operations File

**File:** `scripts/generate_code.py:790`
**Issue:** When checking whether to skip re-generation, the generator reads the first line of the existing file with `ops_path.read_text().splitlines()[0]`. If `ops_path` is an empty file (zero bytes or only whitespace), `splitlines()` returns an empty list and `[0]` raises `IndexError`, crashing the entire generation run. This also applies to any future `operations.py` created by an editor without content.
**Fix:**
```python
if ops_path.exists():
    lines = ops_path.read_text().splitlines()
    if lines and lines[0].strip() == ANNOTATION_IMPLEMENTED:
        print(f"  skipping {ops_path} (implemented)")
        continue
```

---

## Warnings

### WR-01: `fetch_jwks()` Failure at Startup Crashes the App Without Useful Context

**File:** `src/caramello/main.py:28`, `src/caramello/shared/auth.py:72-74`
**Issue:** `fetch_jwks()` is called in the lifespan without a try/except. An `httpx.ConnectError` (Keycloak unreachable), `httpx.HTTPStatusError` (non-200 response from Keycloak), or `jwt.algorithms.RSAAlgorithm` parse failure will propagate as an unhandled exception, crashing startup. The error message will not distinguish "Keycloak URL misconfigured" from "Keycloak server temporarily unavailable", making incident diagnosis harder.
**Fix:**
```python
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        await fetch_jwks()
    except Exception as exc:
        # Log and fail fast with actionable message
        raise RuntimeError(
            f"Failed to fetch JWKS from Keycloak at startup: {exc}"
        ) from exc
    yield
```

---

### WR-02: `updated_at` Is Never Updated on PATCH Operations

**File:** `src/caramello/user/router.py:66-68`, `src/caramello/family/router.py:75-77`, `src/caramello/family/router.py:155-157`
**Issue:** The PATCH handlers call `model_dump(exclude_unset=True)` and apply the result with `setattr`. Because `updated_at` is not in `UserUpdate`/`FamilyUpdate`/`FamilyInvitationUpdate`, it is never included in `update_data`, so the field retains its creation timestamp after every update. The field is misleading and non-functional.
**Fix:** Explicitly refresh `updated_at` in every PATCH handler:
```python
update_data = user_in.model_dump(exclude_unset=True)
update_data["updated_at"] = datetime.now(timezone.utc)
for key, value in update_data.items():
    setattr(db_obj, key, value)
```

---

### WR-03: `TestClient` in `conftest.py` Does Not Trigger Lifespan

**File:** `tests/conftest.py:12-13`
**Issue:** `TestClient(app)` is returned directly without using it as a context manager (`with TestClient(app) as client`). FastAPI's lifespan events (including `fetch_jwks()`) only execute when the client is used as a context manager. Tests that call `client.get("/user/me")` etc. run against an app with an empty `_jwks_cache`, meaning any test that reaches real JWT validation will fail with "kid não reconhecido" rather than testing actual auth logic. This also means `test_me_unauthenticated` in `test_auth.py` (once the `xfail` is removed) will fail for the wrong reason.
**Fix:**
```python
@pytest.fixture
def client():
    from caramello.main import app
    with TestClient(app) as c:
        yield c
```

---

### WR-04: `_run_ruff_fix` Hardcodes Domain List — New Domains Will Not Be Formatted

**File:** `scripts/generate_code.py:808`
**Issue:** `dirs = [str(src_dir / d) for d in ("user", "family") if (src_dir / d).exists()]` hardcodes `("user", "family")`. When a new domain is added (e.g., `finance`, `health`), its generated code will not be formatted by ruff. The rest of the generator dynamically discovers domains from the manifest; this function contradicts that pattern and will silently produce unformatted output for new domains.
**Fix:**
```python
def _run_ruff_fix(src_dir: Path, domains: list[str]) -> None:
    dirs = [str(src_dir / d) for d in domains if (src_dir / d).exists()]
    ...

# In main(), pass discovered domains:
_run_ruff_fix(SRC_DIR, list(entities_by_domain.keys()))
```

---

### WR-05: `DB_PORT=0` Incorrectly Omitted from DATABASE_URL

**File:** `src/caramello/core/config.py:38`
**Issue:** `port = f":{self.DB_PORT}" if self.DB_PORT else ""` uses truthiness to check an integer. When `DB_PORT=0`, `self.DB_PORT` evaluates to `False` and the port is omitted from the URL, producing a connection string without a port. Port 0 is not a valid PostgreSQL port and would indicate a misconfiguration, but the silent omission means a misleading connection error at engine creation time rather than a clear startup error.
**Fix:**
```python
port = f":{self.DB_PORT}" if self.DB_PORT is not None else ""
```
Or, since `DB_PORT: int` is required, validate the range:
```python
@field_validator("DB_PORT")
@classmethod
def validate_port(cls, v: int) -> int:
    if not 1 <= v <= 65535:
        raise ValueError(f"DB_PORT must be 1-65535, got {v}")
    return v
```

---

### WR-06: `domain_class` Derivation Breaks for Multi-Word Domains

**File:** `scripts/generate_code.py:398-400`
**Issue:** `domain_class = domain.title()` is used to derive the model class name from the domain string. For a future domain like `family_member` or `family_invitation`, `"family_invitation".title()` produces `"Family_Invitation"` — not a valid Python class name. The special-case for `"user"` (line 400) proves this was noticed for single-word domains but the general case remains broken. Adding any domain whose name does not match its primary model class exactly will generate syntactically invalid Python.
**Fix:**
```python
# Accept an explicit primary_class in the operations YAML, or map via the entities:
domain_class = op_data.get("primary_class") or domain.title().replace("_", "")
```
Better: require `primary_class` as a field in `dsl/operations/*.yaml`.

---

## Info

### IN-01: Duplicate `type:` Keys in `dsl/entities/family_member.yaml`

**File:** `dsl/entities/family_member.yaml:38-43`
**Issue:** The `relationships` section of `family_member.yaml` contains duplicate `type:` keys within each relationship mapping:
```yaml
  - name: user
    type: "User"
    type: "User"   # duplicate key
  - name: family
    type: "Family"
    type: "Family" # duplicate key
```
YAML parsers typically keep the last value, so behavior is accidentally correct here. However, this is a DSL authoring error that should be caught. The generator's `load_yaml` using `yaml.safe_load` silently discards the first occurrence.
**Fix:** Remove the duplicate `type:` lines in `dsl/entities/family_member.yaml`. Add a YAML lint step or schema validation to catch this class of error during CI.

---

### IN-02: `generate_router` Produces a Wrong Type Annotation for `get_current_user` Dependency

**File:** `scripts/generate_code.py:321-322`
**Issue:** The generated router template uses `_: {name} = Depends(get_current_user)` (line 321 in the f-string). `get_current_user` always returns a `User`, not a `Family` or `FamilyInvitation`. While FastAPI ignores the type annotation on `_` at runtime (the dependency resolves correctly regardless), the annotation is semantically wrong, misleading to readers, and will cause mypy/pyright errors when type-checking is enabled. The family router already exhibits this (family/router.py:29: `_: Family = Depends(get_current_user)`).
**Fix:** Change the generated template to use `User`:
```python
_: User = Depends(get_current_user),
```
And add `from caramello.user.models import User` to the generated imports.

---

### IN-03: `read_familys` — Incorrect Pluralization in Generated Endpoint Function Name

**File:** `src/caramello/family/router.py:39`
**Issue:** The generator produces function names by appending `s` to the lowercased entity name: `read_{var_name}s`. For `Family` this yields `read_familys` rather than `read_families`. This is a cosmetic issue that does not affect routing or correctness (FastAPI uses path, not function name, for routing), but it shows up in OpenAPI docs and log output.
**Fix:** Apply English pluralization in `generate_router` or `_consolidate_routers` before constructing the function name. A minimal fix: `var_plural = var_name + "ies" if var_name.endswith("y") else var_name + "s"`.

---

_Reviewed: 2026-05-25_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
