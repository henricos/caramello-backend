# Project Directory Structure

### Main folders:
- **`alembic/`**: Database migration scripts (Alembic).
- **`docs/`**: Detailed project documentation.
- **`dsl/`**: Domain objects definitions in YAML (DSL). Generates code and OpenAPI.
- **`src/caramello/`**: Main application package.
  - **`api/`**: FastAPI routers (endpoints).
  - **`core/`**: Global settings, environment variables, utilities.
  - **`database/`**: Database connection and session configuration.
  - **`models/`**: SQLModel models (database tables).
  - **`repositories/`**: Data access layer (queries).
  - **`schemas/`**: Pydantic schemas for validation.
  - **`services/`**: Business logic layer.
- **`tests/`**: Automated tests.
