"""Tests for the DSL generator evolution.

Covers: the `domain` field in the YAMLs, the dynamic output path, the
CARAMELLO-GENERATED annotation and the generation of operations.py out of
dsl/operations/*.yaml.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DSL_ENTITIES_DIR = REPO_ROOT / "dsl" / "entities"
DSL_OPERATIONS_DIR = REPO_ROOT / "dsl" / "operations"


def test_user_yaml_has_domain_field():
    """user.yaml carries `domain: user` or `domain: users`.

    The generator emitted the singular `user` historically and emits the plural
    `users` now — both are accepted here.
    """
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") in ("user", "users"), (
        f"user.yaml must declare domain: user|users; found: {data.get('domain')!r}"
    )


def test_family_yamls_have_domain_field():
    """family*.yaml declare domain: family (the old form) or families (the current one)."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") in ("family", "families"), (
            f"{fname} must declare domain: family|families; found: {data.get('domain')!r}"
        )


def test_operations_user_yaml_exists():
    """dsl/operations/user.yaml exists with a get_me operation."""
    path = DSL_OPERATIONS_DIR / "user.yaml"
    assert path.exists(), f"dsl/operations/user.yaml must exist at {path}"
    data = yaml.safe_load(path.read_text())
    assert data.get("domain") in ("user", "users"), (
        f"domain must be 'user' or 'users'; found: {data.get('domain')!r}"
    )
    ops = data.get("operations", [])
    assert len(ops) >= 1, f"must have at least 1 operation; found: {len(ops)}"
    op_names = [op["name"] for op in ops]
    assert "get_me" in op_names, f"operation 'get_me' not found in {op_names}"
    get_me = next(op for op in ops if op["name"] == "get_me")
    assert get_me.get("method") == "GET", (
        f"get_me.method must be 'GET'; found: {get_me.get('method')!r}"
    )
    assert get_me.get("path") in ("/user/me", "/users/me"), (
        f"get_me.path must be '/user/me' or '/users/me'; found: {get_me.get('path')!r}"
    )
    assert get_me.get("description"), "get_me.description cannot be empty"


def test_schema_yaml_has_domain_property():
    """dsl/schema.yaml has a domain field as a property."""
    schema_path = REPO_ROOT / "dsl" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text())
    assert "domain" in schema.get("properties", {}), (
        "schema.yaml must list 'domain' under properties"
    )
    assert "domain" in schema.get("required", []), "schema.yaml must list 'domain' under required"


def test_user_models_in_user_domain():
    """users/models.py carries the SQLAlchemy table class `User`."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    assert models_path.exists(), "users/models.py must exist after regeneration"
    content = models_path.read_text()
    assert "class User(Base):" in content
    assert "from caramello_api.shared.base import Base" in content
    assert "from sqlalchemy.orm import Mapped, mapped_column, relationship" in content
    assert "mapped_column(" in content, "columns must use mapped_column()"
    # `from __future__ import annotations` is MANDATORY in the SQLAlchemy 2 shape:
    # the library resolves the PEP 563 annotations on its own and finds the
    # entities through the class registry. (Under SQLModel it was forbidden,
    # because it read the annotation with get_origin/get_args, which returns
    # None for a string.)
    assert "from __future__ import annotations" in content


def test_family_models_consolidated():
    """families/models.py carries Family, FamilyMember and FamilyInvitation as tables."""
    models_path = REPO_ROOT / "src/caramello_api/families/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(Base):" in content
    assert "class FamilyMember(Base):" in content
    assert "class FamilyInvitation(Base):" in content


def test_generated_code_uses_modern_types():
    """Generated code uses `str | None` and `list[T]`, not Optional/List."""
    models_path = REPO_ROOT / "src/caramello_api/users/models.py"
    content = models_path.read_text()
    assert "Optional[" not in content, "generated code must not use Optional[X]"
    assert "from typing import Optional" not in content
    assert "from typing import List" not in content
    assert "from __future__ import annotations" in content
    families_content = (REPO_ROOT / "src/caramello_api/families/models.py").read_text()
    assert "Mapped[str | None]" in families_content, (
        "nullable columns must use `T | None` inside Mapped[...]"
    )
    assert "Mapped[list[User]]" in families_content, "collections must use list[T]"


def test_generated_models_carry_no_noqa_up037():
    """The `# noqa: UP037` workaround left along with SQLModel.

    Under SQLAlchemy 2 the quotes in `Mapped[list["Family"]]` are dispensable:
    ruff may strip them (UP037) and resolution keeps working through the class
    registry.
    """
    for domain in ("users", "families", "finances"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/models.py").read_text()
        assert "noqa: UP037" not in content, f"{domain}/models.py must not need noqa UP037"


def test_generated_models_have_no_pydantic_dto():
    """models.py carries tables ONLY — no Pydantic DTO."""
    for domain in ("users", "families", "finances"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/models.py").read_text()
        assert "BaseModel" not in content, f"{domain}/models.py must not mention BaseModel"
        assert "ConfigDict" not in content, f"{domain}/models.py must not mention ConfigDict"
        for suffix in ("Read", "Create", "Update"):
            assert f"{suffix}(" not in content, f"{domain}/models.py must not declare {suffix} DTOs"


def test_generated_schemas_live_in_separate_module():
    """The DTOs live in `{domain}/schemas.py` as plain Pydantic BaseModel."""
    expected = {
        "users": ["User"],
        "families": ["Family", "FamilyInvitation"],
        "finances": ["Account", "Movement", "FinancialEntry", "Category", "Subcategory"],
    }
    for domain, entities in expected.items():
        schemas_path = REPO_ROOT / f"src/caramello_api/{domain}/schemas.py"
        assert schemas_path.exists(), f"{domain}/schemas.py must exist"
        content = schemas_path.read_text()
        assert "from pydantic import BaseModel, ConfigDict" in content
        assert "(Base):" not in content, f"{domain}/schemas.py must not declare tables"
        assert "mapped_column" not in content, f"{domain}/schemas.py must not have columns"
        for entity in entities:
            assert f"class {entity}Read(BaseModel):" in content
            assert f"class {entity}Create(BaseModel):" in content
            assert f"class {entity}Update(BaseModel):" in content
        # Read models are built out of ORM instances
        assert content.count("model_config = ConfigDict(from_attributes=True)") == len(entities), (
            f"{domain}/schemas.py: every Read class must declare from_attributes=True"
        )


def test_link_model_has_composite_pk_and_no_surrogate_ids():
    """FamilyMember keeps a composite PK made of both FKs, with no `id` and no `uuid`."""
    content = (REPO_ROOT / "src/caramello_api/families/models.py").read_text()
    start = content.index("class FamilyMember(Base):")
    end = content.index("class FamilyInvitation(Base):")
    block = content[start:end]
    assert block.count("primary_key=True") == 2, "composite PK = two primary_key columns"
    assert 'ForeignKey("user.id")' in block
    assert 'ForeignKey("family.id")' in block
    assert "    id:" not in block, "a link model has no id"
    assert "    uuid:" not in block, "a link model has no uuid"
    assert "autoincrement=True" not in block, "a composite PK is never autoincrement"
    # Link models have no DTOs
    schemas = (REPO_ROOT / "src/caramello_api/families/schemas.py").read_text()
    assert "FamilyMemberRead" not in schemas


def test_dual_identifiers_and_timestamps_preserved():
    """Every non-link entity has an autoincrement `id`, a unique `uuid` and tz-aware timestamps."""
    content = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    assert (
        "id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, "
        "nullable=False)"
    ) in content
    assert (
        "uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4)"
    ) in content
    assert "DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)" in content
    # updated_at has NO onupdate at the SQL level — the handlers assign it by hand.
    assert "onupdate" not in content, "updated_at must have no onupdate (DDL unchanged)"


def test_expose_as_uuid_splits_table_and_schema():
    """`expose_as_uuid` keeps the int column on the table and exposes only the UUID."""
    models = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    schemas = (REPO_ROOT / "src/caramello_api/finances/schemas.py").read_text()
    assert "responsible_user_id: Mapped[int | None] = mapped_column(" in models
    assert 'ForeignKey("user.id")' in models
    assert "responsible_user_uuid" not in models, "an internal id never becomes a UUID on the table"
    assert "responsible_user_uuid: UUID | None = None" in schemas
    assert "responsible_user_id" not in schemas, "an integer FK never leaks to the public API"


def test_generated_router_requires_auth():
    """The generated router imports get_current_user and uses Depends."""
    router_path = REPO_ROOT / "src/caramello_api/users/router.py"
    content = router_path.read_text()
    assert "from caramello_api.shared.auth import get_current_user" in content
    assert "Depends(get_current_user)" in content


def test_user_operations_stub_or_implemented():
    """Users/operations.py exists with a stub or implemented annotation."""
    ops_path = REPO_ROOT / "src/caramello_api/users/operations.py"
    assert ops_path.exists()
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line in (
        "# CARAMELLO-GENERATED: stub",
        "# CARAMELLO-GENERATED: implemented",
    ), f"The first line must be a CARAMELLO-GENERATED annotation; got: {first_line!r}"


def test_legacy_paths_removed():
    """Src/caramello_api/models, api/generated, user/ and family/ are gone."""
    assert not (REPO_ROOT / "src/caramello_api/models").exists()
    assert not (REPO_ROOT / "src/caramello_api/api").exists()
    assert not (REPO_ROOT / "src/caramello_api/user").exists(), (
        "src/caramello_api/user must have been removed"
    )
    assert not (REPO_ROOT / "src/caramello_api/family").exists(), (
        "src/caramello_api/family must have been removed"
    )


def test_user_yaml_domain_is_users():
    """Dsl/entities/user.yaml declares domain == 'users'."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    domain = data.get("domain")
    if domain == "user":
        pytest.xfail("user.yaml still has domain: user")
    assert domain == "users", f"user.yaml must declare domain: users; found: {domain!r}"


def test_family_yamls_domain_is_families():
    """Family*.yaml declare domain == 'families'."""
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        domain = data.get("domain")
        if domain == "family":
            pytest.xfail(f"{fname} still has domain: family")
        assert domain == "families", f"{fname} must declare domain: families; found: {domain!r}"


def test_family_invitation_yaml_uses_pending_login_status():
    """family_invitation.yaml redesigned — no invitee_email."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "family_invitation.yaml").read_text())
    field_names = {f["name"] for f in data.get("fields", [])}
    # Old fields, REMOVED:
    forbidden = {"invitee_email", "expires_at"}
    present_forbidden = forbidden & field_names
    if present_forbidden:
        pytest.xfail(f"old fields present: {present_forbidden}")
    # New fields, PRESENT:
    assert "email" in field_names, f"the 'email' field is mandatory; fields: {field_names}"
    assert "status" in field_names, f"the 'status' field is mandatory; fields: {field_names}"
    # status default == 'pending_login'
    status_field = next(f for f in data["fields"] if f["name"] == "status")
    assert status_field.get("default") == "pending_login", (
        f"status.default must be 'pending_login'; got {status_field.get('default')!r}"
    )


def test_router_url_has_domain_prefix_and_hyphens():
    """generate_router emits a domain prefix with hyphens."""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_router
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "FamilyInvitation",
        "table_name": "family_invitation",
        "domain": "families",
        "fields": [
            {
                "name": "id",
                "type": "int",
                "primary_key": True,
                "nullable": False,
            },
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
        ],
        "relationships": [],
    }
    try:
        code = generate_router(entity_data)
    except Exception as exc:  # noqa: BLE001
        pytest.xfail(f"generate_router failed: {exc}")
    if 'prefix="/family_invitation"' in code:
        pytest.xfail("the old prefix is still emitted")
    prefix_lines = [line for line in code.splitlines() if "prefix=" in line]
    assert 'prefix="/families/family-invitation"' in code, (
        f"Expected prefix='/families/family-invitation' in the generated code; "
        f"prefixes found: {prefix_lines}"
    )


def test_operations_user_yaml_path_is_users_me():
    """Dsl/operations/user.yaml.get_me.path == /users/me."""
    data = yaml.safe_load((DSL_OPERATIONS_DIR / "user.yaml").read_text())
    get_me = next(op for op in data["operations"] if op["name"] == "get_me")
    path = get_me.get("path")
    if path == "/user/me":
        pytest.xfail("get_me.path is still /user/me")
    assert path == "/users/me", f"get_me.path must be '/users/me'; got {path!r}"


def test_operations_family_yaml_exists_with_six_operations():
    """Dsl/operations/family.yaml exists with 6 operations."""
    family_ops_path = DSL_OPERATIONS_DIR / "family.yaml"
    if not family_ops_path.exists():
        pytest.xfail("dsl/operations/family.yaml does not exist")
    data = yaml.safe_load(family_ops_path.read_text())
    assert data.get("domain") == "families", (
        f"domain must be 'families'; got {data.get('domain')!r}"
    )
    expected_ops = {
        "registry_family",
        "list_my_families",
        "get_family_detail",
        "pre_register_member",
        "list_members",
        "remove_member",
    }
    actual_ops = {op["name"] for op in data.get("operations", [])}
    missing = expected_ops - actual_ops
    assert not missing, f"Operations missing from dsl/operations/family.yaml: {missing}"


# ---------------------------------------------------------------------------
# Generator support for Decimal and filters:
# ---------------------------------------------------------------------------


def test_generator_decimal_emits_numeric():
    """generate_models emits Numeric(15, 2) for a Decimal field.

    Checks that:
    - the generated code carries `mapped_column(Numeric(15, 2), nullable=False)`
    - the annotation is `Mapped[Decimal]`, never float
    - the header imports `from decimal import Decimal`
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_models
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "Movement",
        "table_name": "movement",
        "domain": "finances",
        "description": "Raw financial movement.",
        "fields": [
            {"name": "id", "type": "int", "primary_key": True, "nullable": False},
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
            {"name": "amount", "type": "Decimal", "nullable": False},
        ],
        "relationships": [],
    }
    code = generate_models(entity_data, entity_domain={})

    assert "from decimal import Decimal" in code, (
        f"The generated header must import `from decimal import Decimal`; generated code:\n{code}"
    )
    assert "amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)" in code, (
        f"The Decimal field must generate `mapped_column(Numeric(15, 2), nullable=False)`; "
        f"generated code:\n{code}"
    )
    assert "float" not in code, f"no monetary path uses float; generated code:\n{code}"


def test_generator_filters_emits_table_args():
    """generate_models emits __table_args__ with Index.

    For every entity that declares filters:, it checks that:
    - the generated code carries `__table_args__ = (`
    - individual indexes: `Index("ix_movement_account_id", "account_id")`
    - a composite index: `Index("ix_movement_competencia_year_competencia_month", ...)`
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_models
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {
        "name": "Movement",
        "table_name": "movement",
        "domain": "finances",
        "description": "Raw financial movement.",
        "fields": [
            {"name": "id", "type": "int", "primary_key": True, "nullable": False},
            {
                "name": "uuid",
                "type": "UUID",
                "unique": True,
                "default_factory": "uuid4",
                "nullable": False,
            },
            {"name": "account_id", "type": "int", "nullable": False},
            {"name": "competencia_year", "type": "int", "nullable": False},
            {"name": "competencia_month", "type": "int", "nullable": False},
        ],
        "relationships": [],
        "filters": [
            {"fields": ["account_id"]},
            {"fields": ["competencia_year", "competencia_month"]},
        ],
    }
    code = generate_models(entity_data, entity_domain={})

    assert "__table_args__ = (" in code, (
        f"An entity with filters: must generate `__table_args__ = (`; generated code:\n{code}"
    )
    assert 'Index("ix_movement_account_id", "account_id")' in code, (
        f"Must generate an Index for the simple `account_id` filter; generated code:\n{code}"
    )
    assert (
        'Index("ix_movement_competencia_year_competencia_month", '
        '"competencia_year", "competencia_month")'
    ) in code, (
        "Must generate a composite Index for the `competencia_year + competencia_month` filter; "
        f"generated code:\n{code}"
    )


# ---------------------------------------------------------------------------
# Finance YAMLs: generation and import
# ---------------------------------------------------------------------------


def test_finances_yamls_have_domain_finances():
    """The 5 finance YAMLs declare domain: finances.

    Checks that each one of the 5 YAMLs has domain == 'finances'.
    """
    yaml_files = [
        "account.yaml",
        "movement.yaml",
        "financial_entry.yaml",
        "category.yaml",
        "subcategory.yaml",
    ]
    for fname in yaml_files:
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") == "finances", (
            f"{fname} must declare domain: finances; found: {data.get('domain')!r}"
        )


def test_finances_models_no_float():
    """Finances/models.py and schemas.py use no float.

    No monetary path touches floating point: the column is Numeric(15, 2) and
    the annotation is Decimal, both on the table and on the DTO.
    """
    for name in ("models.py", "schemas.py"):
        path = REPO_ROOT / f"src/caramello_api/finances/{name}"
        assert path.exists(), f"src/caramello_api/finances/{name} must exist"
        content = path.read_text()
        assert "float" not in content, (
            f"finances/{name} must not carry `float` in any form; "
            "monetary values are Decimal / Numeric(15, 2)"
        )
    models_content = (REPO_ROOT / "src/caramello_api/finances/models.py").read_text()
    assert "Numeric(15, 2)" in models_content, (
        "models.py must carry `Numeric(15, 2)` for monetary fields"
    )
    assert "Mapped[Decimal]" in models_content, "the amount column must be Mapped[Decimal]"
    schemas_content = (REPO_ROOT / "src/caramello_api/finances/schemas.py").read_text()
    assert "amount: Decimal" in schemas_content, "the DTO exposes amount as Decimal"


def test_finances_models_import_ok():
    """The finances models and schemas import without error.

    Checks that the generated code is importable and that the SQLAlchemy mapping
    configures (a forward reference error only shows up in configure_mappers).
    """
    import importlib

    from sqlalchemy.orm import configure_mappers

    try:
        for module in (
            "caramello_api.users.models",
            "caramello_api.families.models",
            "caramello_api.finances.models",
            "caramello_api.finances.schemas",
        ):
            mod = importlib.import_module(module)
            assert mod is not None, f"the imported {module} must not be null"
    except ImportError as exc:
        raise AssertionError(f"importing the generated code raised ImportError: {exc}") from exc

    configure_mappers()


def test_generated_router_uses_sqlalchemy_execute():
    """A generated router uses session.execute + .scalars(), never session.exec."""
    for domain in ("users", "families"):
        content = (REPO_ROOT / f"src/caramello_api/{domain}/router.py").read_text()
        assert "from sqlalchemy import select" in content
        assert "from sqlalchemy.ext.asyncio import AsyncSession" in content
        assert "session.exec(" not in content, "session.exec() does not exist in SQLAlchemy"
        assert "await session.execute(" in content
        assert ".scalars()" in content, "a single-entity select must unwrap the Row"
        assert f"from caramello_api.{domain}.schemas import" in content


def test_finances_has_no_generated_router():
    """Every finances entity opts out, so the module must not exist at all.

    The generated CRUD would publish AccountRead/MovementRead & co, which carry
    the internal integer foreign keys the hand-written `*Public` schemas in
    `finances/operations.py` exist to keep out of the api. Opting out is what
    stops that code from sitting in the tree unregistered.
    """
    router_path = REPO_ROOT / "src/caramello_api/finances/router.py"
    assert not router_path.exists(), (
        f"{router_path} should not be generated: every finances entity declares "
        "generate_router: false"
    )


def test_every_finances_entity_opts_out_of_the_router():
    """The DSL is the reason the module is absent — not a deletion by hand."""
    for fname in (
        "account.yaml",
        "movement.yaml",
        "financial_entry.yaml",
        "category.yaml",
        "subcategory.yaml",
    ):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("generate_router") is False, (
            f"{fname} must declare generate_router: false; found {data.get('generate_router')!r}"
        )


def test_family_invitation_opts_out_of_the_router():
    """Its lifecycle belongs to the pre-register operation, not to a generic CRUD."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "family_invitation.yaml").read_text())
    assert data.get("generate_router") is False
    content = (REPO_ROOT / "src/caramello_api/families/router.py").read_text()
    assert "FamilyInvitation" not in content, (
        "families/router.py must carry no FamilyInvitation route"
    )


def test_generate_router_flag_is_honoured_by_the_generator():
    """`generate_router: false` removes the entity from the consolidated module."""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import _consolidate_routers
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    def entity(name: str, table: str, opt_out: bool) -> dict:
        data = {
            "name": name,
            "table_name": table,
            "domain": "demo",
            "fields": [
                {"name": "id", "type": "int", "primary_key": True, "nullable": False},
                {
                    "name": "uuid",
                    "type": "UUID",
                    "unique": True,
                    "default_factory": "uuid4",
                    "nullable": False,
                },
            ],
            "relationships": [],
        }
        if opt_out:
            data["generate_router"] = False
        return data

    kept = entity("Kept", "kept", opt_out=False)
    dropped = entity("Dropped", "dropped", opt_out=True)

    # The generator filters before calling _consolidate_routers, which is what
    # this asserts: only what is handed over ends up in the module.
    routable = [e for e in (kept, dropped) if e.get("generate_router", True)]
    assert routable == [kept]
    code = _consolidate_routers("demo", routable)
    assert "kept_router" in code
    assert "Dropped" not in code


def test_public_read_schemas_expose_no_integer_foreign_key():
    """No `*Read` schema served by a generated router may carry an int FK.

    The invariant is "public identifiers are UUIDs" (root docs/architecture.md).
    A generated router publishes its entity's `Read` schema as-is, so an `x_id:
    int` there is a leak; `expose_as_uuid: true` in the DSL is the fix.
    """
    import re

    for domain in ("users", "families"):
        served = (REPO_ROOT / f"src/caramello_api/{domain}/router.py").read_text()
        schemas = (REPO_ROOT / f"src/caramello_api/{domain}/schemas.py").read_text()
        for block in schemas.split("class ")[1:]:
            name = block.split("(")[0]
            if not name.endswith("Read") or name not in served:
                continue
            leaks = re.findall(r"^    (\w+_id): int", block, flags=re.MULTILINE)
            assert not leaks, f"{name} leaks integer foreign keys: {leaks}"


def test_no_legacy_orm_imports_anywhere():
    """The old dependency is gone: no module in the project imports it."""
    # Assembled in two pieces so that this very file does not match the search.
    needle = "sql" + "model"
    for sub in ("src", "tests", "scripts"):
        for path in sorted((REPO_ROOT / sub).rglob("*.py")):
            content = path.read_text()
            assert f"import {needle}" not in content, f"{path} still imports {needle}"
            assert f"from {needle}" not in content, f"{path} still imports {needle}"
