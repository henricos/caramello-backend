# Conventions

_Last updated: 2026-05-23_

## Naming

**Files and modules:** `snake_case` — `user.py`, `family_member.py`, `user_router.py`

**Classes:** `PascalCase` — `UserRepository`, `UserService`, `FamilyInvitation`

**Schema variants follow a fixed suffix pattern on the entity class name:**
- `User` — ORM/table model (SQLModel with `table=True`)
- `UserRead` — response schema
- `UserCreate` — creation payload schema
- `UserUpdate` — partial update payload schema (all fields `Optional`)

**Functions and variables:** `snake_case` — `create_user`, `read_familys`, `get_session`

**Constants:** `UPPER_CASE` — `DEFAULT_PAGE_SIZE`

**API route prefixes:** `snake_case` — `/user`, `/family`, `/family_member`, `/family_invitation`

**Router function names:** `snake_case` verbs — `create_user`, `read_users`, `read_user`, `update_user`, `delete_user`

**Database table names:** singular `snake_case` — `user`, `family`, `family_member`, `family_invitation`
- All entities expose `id` (int, internal PK) and `uuid` (UUID, public identifier)
- External URLs and API responses use `uuid`, never `id`

**DSL entity files:** `snake_case` — `user.yaml`, `family_invitation.yaml`

## Code Style

**Formatter:** `black` — max line length 88 characters (configured in `docs/style_guide.md`; no `pyproject.toml` section present yet)

**Linter:** `ruff` — handles lint, isort-style import ordering, and docstyle checks. Run: `ruff check .` and `ruff format .`

**Type checker:** `mypy` — goal is 100% static type coverage. Run: `mypy .`

**Python version target:** 3.10+ — use built-in generics (`list[str]`, not `List[str]`), but generated code currently uses `from typing import List` (known inconsistency in generated files).

**Type hints:** Required on all public function signatures (arguments and return type).

```python
# Correct
def get_user(user_id: UUID) -> UserRead | None:

# Wrong
def get_user(user_id):
```

## Module Patterns

**Models** (`src/caramello/models/`): One file per DSL entity. Each file defines the SQLModel table class and its Read/Create/Update schema variants. Co-located in the same file because they are generated together.

```python
class User(SQLModel, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    ...

class UserRead(SQLModel): ...
class UserCreate(SQLModel): ...
class UserUpdate(SQLModel): ...
```

**Generated routers** (`src/caramello/api/generated/`): One file per entity, produced by `./bin/generate_code`. Implements five operations — `POST /`, `GET /`, `GET /{uuid}`, `PATCH /{uuid}`, `DELETE /{uuid}`. Uses `APIRouter` with `prefix` and `tags`.

**Session dependency:** Injected via `Depends(get_session)` from `src/caramello/database/session.py`. A `Generator`-based yield pattern gives one `Session` per request.

**Settings:** `src/caramello/core/config.py` — `pydantic_settings.BaseSettings` singleton (`settings = Settings()`). Loaded once at import time. DB URL is constructed from individual `DB_*` env vars in `model_post_init`.

**Repositories** (`src/caramello/repositories/`): Intended for data-access-only logic — stub files exist (`user.py` is empty). Not yet implemented.

**Services** (`src/caramello/services/`): Intended for business logic orchestration — stub files exist (`user.py` is empty). Not yet implemented.

**Imports ordering** (as prescribed by ruff/isort):
1. Standard library (`os`, `uuid`, `datetime`)
2. Third-party (`fastapi`, `sqlmodel`, `pydantic`)
3. Local (`caramello.*`)

## Error Handling

**HTTP errors in routers:** `HTTPException` raised inline with `status_code` and `detail` string.

```python
if not user:
    raise HTTPException(status_code=404, detail="User not found")
```

**`exceptions.py` and `http_errors.py`** exist in `src/caramello/` but are currently empty stubs. Custom exception classes are not yet defined.

**No try/except blocks** exist in the current generated code — errors from the database layer propagate unhandled.

## Documentation

**Docstrings:** PEP 257 style with Google-flavor Args/Returns sections.

```python
def create_user(data: UserCreate) -> User:
    """Creates a new user.

    Args:
        data: Validated user input data.

    Returns:
        The persisted User entity.
    """
```

**Model-level docstrings:** Single-line strings on the ORM class describing the entity — `"""Represents a system user."""`

**Inline comments:** English, used sparingly. In generated files, comments explain generation intent (e.g., `# Fix unique constraints`, `# Dynamic sample data`).

**Language policy:** Code identifiers (variable names, function names, file names, comments inside code) in English. Narrative documentation (docs/, commit messages, chat) in Brazilian Portuguese (pt-BR).
