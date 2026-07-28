# Rules for Creating DSL Files (Caramello API)

This document defines the strict rules for creating and maintaining the definition files in `dsl/`. It applies to entities (`dsl/entities/*.yaml`) and to business operations (`dsl/operations/{domain}.yaml`). These rules must be followed by AI agents and developers to guarantee correct code generation.

---

## Part I — Entities (`dsl/entities/*.yaml`)

### 1. Naming

- **Files**: snake_case (e.g. `user_profile.yaml`).
- **Entity (`name`)**: PascalCase, singular (e.g. `UserProfile`).
- **Table (`table_name`)**: snake_case, **SINGULAR** (e.g. `user_profile`, `family`).

### 2. Mandatory Structure

Every entity (except link models) must contain the standard fields:

```yaml
- name: id
  type: int
  primary_key: true
  description: "Internal primary key (numeric)."

- name: uuid
  type: UUID
  unique: true
  default_factory: uuid4
  nullable: false
  description: "Unique public identifier (UUID)."
```

### 3. Field Typing

Use modern Python types (lowercase):

- ✅ `str`, `int`, `bool`, `float`, `Decimal`
- ✅ `list[T]` (Python 3.10+ style)
- ✅ `UUID`, `datetime`, `EmailStr`
- ❌ `String`, `Integer`, `List[T]` (old `typing` module)

### 4. Foreign Keys and Public Exposure

FK int columns must never leak into public API schemas. Use the `expose_as_uuid: true` flag to replace the FK field (`_id`) with a UUID field (`_uuid`) in the Read, Create and Update schemas, while keeping the FK in the table.

```yaml
- name: responsible_user_id
  type: int
  foreign_key: "user.id"
  nullable: true
  expose_as_uuid: true          # table: responsible_user_id (int)
  description: "..."            # schemas: responsible_user_uuid (UUID | None)
```

**What the generator produces:**

> **Note:** the emitted shape below is currently being migrated (the ORM layer is moving to SQLAlchemy 2 + Pydantic). The table describes what the generator emits **today**; this section will be updated when the migration lands.

| Class | Generated field |
|--------|-------------|
| `Entity` (table) | `responsible_user_id: int \| None = Field(foreign_key="user.id", ...)` |
| `EntityRead` | `responsible_user_uuid: UUID \| None = None` |
| `EntityCreate` | `responsible_user_uuid: UUID \| None = None` |
| `EntityUpdate` | `responsible_user_uuid: UUID \| None = None` |

> **Rule:** any FK that is optional or that points to `user` must use `expose_as_uuid: true`. Mandatory FKs of internal structure (e.g. `movement_id` in `FinancialEntry`) may go without the flag when they are not exposed directly in the public business schemas.

### 5. Association Tables (Link Models)

M:M entities with `is_link_model: true`:
- Do **not** need `id` or `uuid`
- Have two composite primary keys (FKs)

### 6. Relationships

- Use `list[EntityName]` for "to many"
- Always define `back_populates` for bidirectional navigation
- For M:M, specify `link_model`

### 7. Filters and Indexes

Declare indexes via `filters:` — never add `Index(...)` manually in `models.py`:

```yaml
filters:
  - fields: [competencia_year, competencia_month]
  - fields: [subcategory_id]
```

### 8. Complete Entity Example

```yaml
name: FinancialEntry
domain: finances
table_name: financial_entry

fields:
  - name: id
    type: int
    primary_key: true
  - name: uuid
    type: UUID
    unique: true
    default_factory: uuid4
    nullable: false
  - name: movement_id
    type: int
    foreign_key: "movement.id"
    unique: true
    nullable: false
  - name: responsible_user_id
    type: int
    foreign_key: "user.id"
    nullable: true
    expose_as_uuid: true
  - name: notes
    type: str
    max_length: 500
    nullable: true

filters:
  - fields: [competencia_year, competencia_month]
```

---

## Part II — Business Operations (`dsl/operations/{domain}.yaml`)

### 9. Fundamental Rule: DSL Always First

**Never write an endpoint in `{domain}/operations.py` without first declaring the operation in the DSL.**

The `operations.py` file may be marked as `# CARAMELLO-GENERATED: implemented` (the generator skips it to protect implementations). That is **not** a license to add routes directly — it is only protection for implementations already declared in the DSL.

### 10. Structure of the Operations File

```yaml
domain: finances          # must be one of the domains in DOMAIN_TO_ENTITY_NAME
operations:
  - name: create_account  # snake_case — becomes the Python function name
    method: POST          # GET | POST | PATCH | DELETE | PUT
    path: /finances/accounts   # always starts with /{domain}/
    description: "..."    # appears as the docstring in the generated stub
```

### 11. Mandatory Flow for New Endpoints

1. **Declare** the operation in `dsl/operations/{domain}.yaml`
2. **Generate** the stub: `bin/generate_code` (only generates if the file does not exist or is a `stub`)
3. **Implement** the stub by replacing `raise NotImplementedError`
4. When finished, change `# CARAMELLO-GENERATED: stub` to `# CARAMELLO-GENERATED: implemented`

### 12. Route Paths

- Always use the domain prefix: `/finances/accounts`, `/families/families/{uuid}`
- The generator removes the prefix automatically for the router decorator
- Use `{snake_case_uuid}` for path params (e.g. `{account_uuid}`, `{family_uuid}`)

### 13. Forbidden Anti-Patterns

- ❌ Adding `@router.get(...)` in `operations.py` without an entry in the DSL
- ❌ Creating `operations.py` from scratch without going through the generator
- ❌ Editing the decorator path without updating the DSL
- ❌ Adding an int FK field (e.g. `user_id`) to a public schema without `expose_as_uuid: true`
- ❌ Editing `models.py` manually after generation — every fix goes back to the YAML
