# Python Style Guide

## Language

* **All code (identifiers, functions, classes, variables, modules, packages): English + ASCII only.**
* **Domain terms from Brazil (CPF, CNPJ, boleto, pix):** allowed, but always lowercase/ASCII and combined with English style → `cpf_validator`, `pix_webhook_handler`.
* **Comments and docstrings:** English only, consistent across the project.

## Naming Conventions

* **Packages/Modules:** `snake_case` → `repositories`, `user.py`.
* **Classes:** `PascalCase` → `UserRepository`, `UserService`.
* **Functions/Variables:** `snake_case` → `create_user`, `max_retries`.
* **Constants:** `UPPER_CASE` → `DEFAULT_PAGE_SIZE`.
* **Endpoints:** paths in `kebab-case`, functions in `snake_case`.

## Docstrings

* Follow **PEP 257**:

  * First line: summary.
  * Blank line.
  * Details, args, return, exceptions.

```python
def create_user(data: UserCreate) -> User:
    """Create a new user.

    Args:
        data: Validated user input.

    Returns:
        The persisted User entity.
    """
```

## Code Style and Quality

* **Line length:** max 88 chars (Black).
* **Imports:** stdlib / third-party / local (Ruff organizes).
* **Type hints:** always for public functions and domain objects (checked with mypy).
* **Tools:**

  * `ruff` → lint/isort/docstyle
  * `black` → format
  * `mypy` → type check
  * `pytest` → tests
* Run tools via **uv scripts**.

## Project Structure (under `src/caramello`)

* `api/` → routes and routers (versioned, e.g. `v1/`).
* `core/` → config and constants.
* `database/` → engine and session (SQLModel).
* `models/` → tables (SQLModel).
* `schemas/` → I/O (Pydantic models).
* `repositories/` → CRUD with `Session`.
* `services/` → business logic.
* `exceptions.py` / `http_errors.py` → domain errors and handlers.
* `main.py` → FastAPI app, include routers.

## Database

* Provide `Session` per request via dependency (`yield`) in `database/session.py`.
* Configure Alembic with `target_metadata = SQLModel.metadata` in `env.py`.

## API

* `api/v1/routes.py`: mount routers.
* `api/v1/users.py`: user routes.
* Use `response_model`, `status_code`, `HTTPException`.

## Repositories and Services

* **Repository:** data access only.
* **Service:** orchestration and business rules.
* Naming: `UserRepository`, `UserService`.

## Testing

* `tests/` mirrors project structure.
* Use fixtures for isolated DB `Session`.
* Pre-commit hooks: `ruff`, `black`, `mypy`, `pytest`.
