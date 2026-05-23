# Testing

_Last updated: 2026-05-23_

## Test Framework

**Runner:** `pytest` >= 9.0.1 (declared in `pyproject.toml` under `[dependency-groups].dev`)

**HTTP client:** `httpx` >= 0.28.1 + `fastapi.testclient.TestClient` for endpoint tests

**No separate assertion library** — uses plain `assert` with pytest.

**Run commands:**
```bash
uv run pytest           # Run all tests
uv run pytest -v        # Verbose output
# No coverage config present — no coverage target enforced yet
```

## Test Organization

Tests live in `tests/` and mirror the source structure:

```
tests/
├── __init__.py
├── conftest.py                         # Currently empty — no shared fixtures defined
├── test_generated_api.py               # Smoke tests for app startup and router registration
├── generated/                          # Auto-generated CRUD tests per entity
│   ├── __init__.py
│   ├── test_user.py
│   ├── test_family.py
│   └── test_familyinvitation.py
├── test_api/                           # Manual API tests (router-level)
│   ├── __init__.py
│   └── test_user_router.py             # Empty stub
└── test_services/                      # Service-layer unit tests
    ├── __init__.py
    └── test_user_service.py            # Empty stub
```

**Generated tests** in `tests/generated/` are produced by `./bin/generate_code` alongside generated models/routers. They should not be edited directly.

**Manual tests** in `tests/test_api/` and `tests/test_services/` are human-authored and intended for non-generated behavior.

## Test Types Present

**Smoke tests** (`tests/test_generated_api.py`):
- Verify the root endpoint returns the expected welcome message
- Verify all four entity routers are registered on the app

**Integration tests — generated CRUD** (`tests/generated/test_*.py`):
- Test `POST /entity/` (create)
- Test `GET /entity/{uuid}` (read by id — create-then-read pattern)
- Test `GET /entity/` (list — create-then-list pattern)
- Use a real database connection (not mocked) — tests require a running PostgreSQL instance
- Each test file defines its own local `client_fixture` returning `TestClient(app)`

**Unit tests** — not yet implemented. `tests/test_services/test_user_service.py` and `tests/test_api/test_user_router.py` are empty stubs.

## Coverage

**No coverage tooling configured** — no `pytest-cov`, no coverage thresholds in `pyproject.toml`.

**What is covered:**
- Root health-check endpoint
- Router registration (all four entity routers)
- Create, read-by-uuid, and list operations for `User`, `Family`, and `FamilyInvitation` entities

**What is NOT covered:**
- `PATCH /{uuid}` (update) — no test exists for any entity
- `DELETE /{uuid}` — no test exists for any entity
- 404 error paths — not tested
- `FamilyMember` entity — no generated test file
- All service-layer logic (`tests/test_services/` is empty)
- All manual API router tests (`tests/test_api/` is empty)
- Configuration loading (`src/caramello/core/config.py`)
- Database session management (`src/caramello/database/session.py`)

## Test Utilities

**Fixtures:** `tests/conftest.py` exists but is empty. No shared fixtures are defined.

**Per-file client fixture pattern** (used in every generated test file):
```python
@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)
```

**Unique-value helpers** (inline, not extracted to a helper):
```python
from uuid import uuid4
if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
```

**No factories, no fixture files, no database isolation.** Tests run against a real PostgreSQL connection using the same `DATABASE_URL` from environment. Tests are not transactionally isolated — each create test writes permanent rows. This means tests can accumulate data across runs and the list tests assert `len(...) > 0` rather than exact counts.

## Running Tests

```bash
# Prerequisites: PostgreSQL must be running with credentials in .env
uv run pytest

# Single test file
uv run pytest tests/generated/test_user.py

# Single test
uv run pytest tests/test_generated_api.py::test_read_main
```

Tests will fail if the database is unreachable or not migrated. Run `./bin/manage_db init` before the first test run.
