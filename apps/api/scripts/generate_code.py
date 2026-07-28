"""DSL code generator for the Caramello backend.

Reads `dsl/entities/*.yaml` and `dsl/operations/*.yaml`, emits code at
`src/caramello_api/{domain}/`:

  - `models.py`   — SQLAlchemy 2 table classes only (`Mapped[...] = mapped_column(...)`)
  - `schemas.py`  — plain Pydantic DTOs only (`{X}Read`, `{X}Create`, `{X}Update`)
  - `router.py`   — async CRUD routes guarded by `get_current_user`
  - `operations.py` — business-operation stubs (never overwritten once implemented)

The table/schema split is deliberate and is the reason the module does not use
SQLModel: the public schema must be free to diverge from the table, because
integer foreign keys may never leak into the API (see `expose_as_uuid` below and
the "Public identifiers are UUIDs" decision in the root `docs/architecture.md`).

See `docs/dsl-rules.md` for the normative DSL specification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).parent.parent
DSL_DIR = ROOT_DIR / "dsl"
ENTITIES_DIR = DSL_DIR / "entities"
OPERATIONS_DIR = DSL_DIR / "operations"
SRC_DIR = ROOT_DIR / "src" / "caramello_api"

STANDARD_TYPES = {"int", "str", "bool", "float", "list", "dict"}

# Types that are neither DSL primitives nor entity names — they resolve to a
# concrete Python class that the generated module imports directly.
SPECIAL_TYPES = {"UUID", "datetime", "EmailStr", "Decimal"}

ANNOTATION_STUB = "# CARAMELLO-GENERATED: stub"
ANNOTATION_IMPLEMENTED = "# CARAMELLO-GENERATED: implemented"

# Maps the domain (from the DSL, possibly plural) to the canonical entity name of
# that domain. Needed because domain.title() produces wrong names for plural
# domains (e.g. "families".title() == "Families", but the class is "Family").
# When a new domain is added (e.g. "finances" -> "Account"), add its entry here.
DOMAIN_TO_ENTITY_NAME: dict[str, str] = {
    "user": "User",
    "users": "User",
    "family": "Family",
    "families": "Family",
    "finances": "Account",
}

# DSL type -> Python annotation used inside `Mapped[...]` on the table class.
# `EmailStr` collapses to `str`: e-mail validation belongs to the Pydantic
# schema, and SQLAlchemy cannot map an Annotated pydantic type.
_TABLE_ANNOTATION_BY_DSL: dict[str, str] = {
    "int": "int",
    "integer": "int",
    "str": "str",
    "string": "str",
    "text": "str",
    "emailstr": "str",
    "bool": "bool",
    "boolean": "bool",
    "float": "float",
    "datetime": "datetime",
    "uuid": "UUID",
    "decimal": "Decimal",
}

# DSL type -> SQLAlchemy column type expression. Every one of these must emit the
# exact DDL the applied migrations already produced: changing an entry here is a
# schema change and needs its own Alembic revision.
_SA_TYPE_BY_DSL: dict[str, str] = {
    "int": "Integer",
    "integer": "Integer",
    "bool": "Boolean",
    "boolean": "Boolean",
    "float": "Float",
    "datetime": "DateTime(timezone=True)",
    "uuid": "Uuid",
    "decimal": "Numeric(15, 2)",
}


def load_yaml(file_path: Path) -> Any:
    """Carrega um arquivo YAML de forma segura."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def map_type_to_python(dsl_type: str) -> str:
    """Maps DSL types to Python annotations (modern syntax).

    Used for the Pydantic schemas and for the `Mapped[...]` payload of
    relationships. Entity names come back quoted so they stay forward
    references; ruff may unquote them (UP037) once the module carries
    `from __future__ import annotations`, which is harmless — SQLAlchemy
    resolves the name through its own class registry either way.
    """
    clean_type = dsl_type.strip()
    if clean_type.lower().startswith("list["):
        inner = clean_type[5:-1].strip()
        if inner not in STANDARD_TYPES and inner not in SPECIAL_TYPES:
            return f'list["{inner}"]'
        return f"list[{inner}]"
    type_map = {
        "uuid": "UUID",
        "string": "str",
        "str": "str",
        "text": "str",
        "integer": "int",
        "int": "int",
        "boolean": "bool",
        "bool": "bool",
        "datetime": "datetime",
        "emailstr": "EmailStr",
        "decimal": "Decimal",
    }
    mapped = type_map.get(clean_type.lower())
    if mapped:
        return mapped
    # Assume entity class name -> forward ref string
    return f'"{clean_type}"'


def _table_annotation(field: dict[str, Any]) -> str:
    """Python type used inside `Mapped[...]` for a table column."""
    dsl_type = field["type"].strip().lower()
    annotation = _TABLE_ANNOTATION_BY_DSL.get(dsl_type)
    if annotation is None:
        raise ValueError(
            f"campo {field['name']!r}: tipo {field['type']!r} não é mapeável para uma coluna. "
            f"Tipos aceitos: {sorted(_TABLE_ANNOTATION_BY_DSL)}"
        )
    return annotation


def _sa_type_expr(field: dict[str, Any]) -> str:
    """SQLAlchemy column type expression for a field (e.g. `String(100)`)."""
    dsl_type = field["type"].strip().lower()
    if dsl_type in ("str", "string", "text", "emailstr"):
        max_length = field.get("max_length")
        return f"String({max_length})" if max_length else "String"
    expr = _SA_TYPE_BY_DSL.get(dsl_type)
    if expr is None:
        raise ValueError(
            f"campo {field['name']!r}: tipo {field['type']!r} não tem tipo SQLAlchemy mapeado."
        )
    return expr


def _default_expr(field: dict[str, Any]) -> str | None:
    """Python-side column default, or None when the column has none.

    A Python-side default emits no DDL `DEFAULT` clause — it is evaluated at
    INSERT time by SQLAlchemy. `default=None` is deliberately never emitted:
    it is already the behaviour of an unset nullable attribute and adding it
    would only be noise.
    """
    factory = field.get("default_factory")
    if factory == "uuid4":
        return "uuid4"
    if factory == "now_utc":
        return "lambda: datetime.now(UTC)"
    if factory:
        raise ValueError(f"campo {field['name']!r}: default_factory {factory!r} desconhecido.")
    if "default" in field:
        value = field["default"]
        if value is None:
            return None
        return repr(value)
    return None


def get_column_definition(field: dict[str, Any], *, autoincrement: bool = False) -> str:
    """Emite a linha `nome: Mapped[T] = mapped_column(...)` de uma coluna."""
    name = field["name"]
    is_pk = bool(field.get("primary_key"))
    # A primary key is never nullable, whatever the YAML says.
    nullable = False if is_pk else bool(field.get("nullable", True))

    annotation = _table_annotation(field)
    if nullable:
        annotation = f"{annotation} | None"

    args: list[str] = [_sa_type_expr(field)]
    if field.get("foreign_key"):
        args.append(f'ForeignKey("{field["foreign_key"]}")')
    if is_pk:
        args.append("primary_key=True")
        if autoincrement:
            args.append("autoincrement=True")
    if field.get("unique"):
        args.append("unique=True")
    args.append("nullable=True" if nullable else "nullable=False")
    default = _default_expr(field)
    if default is not None:
        args.append(f"default={default}")

    return f"    {name}: Mapped[{annotation}] = mapped_column({', '.join(args)})"


def generate_relationships(
    relationships: list[dict[str, Any]],
    entity_table: dict[str, str] | None = None,
) -> list[str]:
    """Gera as linhas de `relationship()` para uma entidade.

    M:M relationships pass the association table by NAME
    (`secondary="family_member"`), never the link-model class: SQLAlchemy
    resolves the string through `Base.metadata`, so no cross-domain class
    import is needed and no import cycle can appear. The linked entity type is
    likewise a forward reference resolved through the class registry, which is
    why the order in which the classes are defined does not matter.
    """
    tables = entity_table or {}
    lines: list[str] = []
    for rel in relationships:
        rname = rel["name"]
        rtype = map_type_to_python(rel["type"])

        args: list[str] = []
        link_model = rel.get("link_model")
        if link_model:
            secondary = tables.get(link_model, link_model.lower())
            args.append(f'secondary="{secondary}"')
        if rel.get("back_populates"):
            args.append(f"back_populates={rel['back_populates']!r}")
        if rel.get("overlaps"):
            args.append(f"overlaps={rel['overlaps']!r}")

        lines.append(f"    {rname}: Mapped[{rtype}] = relationship({', '.join(args)})")
    return lines


def _build_table_args(entity_data: dict[str, Any]) -> str | None:
    """Gera o bloco __table_args__ a partir do campo filters: do YAML.

    Retorna None quando não há filters declarados. O bloco pertence à classe de
    tabela — os schemas Pydantic nunca o recebem.
    """
    filters = entity_data.get("filters", [])
    if not filters:
        return None
    table_name = entity_data["table_name"]
    index_lines = []
    for f in filters:
        fields = f["fields"]
        index_name = f"ix_{table_name}_{'_'.join(fields)}"
        field_args = ", ".join(f'"{col}"' for col in fields)
        index_lines.append(f'        Index("{index_name}", {field_args}),')
    return "    __table_args__ = (\n" + "\n".join(index_lines) + "\n    )\n"


def _docstring_block(description: str) -> str:
    """Docstring de classe, quebrada em múltiplas linhas quando excederia E501."""
    single_line = f'    """{description}"""'
    if len(single_line) <= 88:
        return f'    """{description}"""\n'
    return f'    """\n    {description}\n    """\n'


def generate_models(
    entity_data: dict[str, Any],
    entity_domain: dict[str, str],
    entity_table: dict[str, str] | None = None,
) -> str:
    """Gera imports + a classe de tabela SQLAlchemy de uma entidade.

    Only the table class: the `{X}Read/{X}Create/{X}Update` DTOs are emitted by
    `generate_schemas` into `{domain}/schemas.py`.
    """
    name = entity_data["name"]
    table_name = entity_data["table_name"]
    fields = entity_data.get("fields", [])
    relationships = entity_data.get("relationships", [])
    description = entity_data.get("description", "")
    domain = entity_data.get("domain", "")

    # A single-column integer primary key is the autoincrement surrogate key; a
    # composite primary key (link models) must never carry autoincrement.
    pk_fields = [f for f in fields if f.get("primary_key")]
    single_int_pk = (
        len(pk_fields) == 1
        and _table_annotation(pk_fields[0]) == "int"
        and not pk_fields[0].get("foreign_key")
    )

    stdlib_imports: list[str] = []
    if any(f["type"].strip().lower() == "decimal" for f in fields):
        stdlib_imports.append("from decimal import Decimal")
    if any(
        f["type"].strip().lower() == "datetime" or f.get("default_factory") == "now_utc"
        for f in fields
    ):
        needs_utc = any(f.get("default_factory") == "now_utc" for f in fields)
        stdlib_imports.append(
            "from datetime import UTC, datetime" if needs_utc else "from datetime import datetime"
        )
    if any(f["type"].strip().lower() == "uuid" for f in fields):
        needs_uuid4 = any(f.get("default_factory") == "uuid4" for f in fields)
        stdlib_imports.append(
            "from uuid import UUID, uuid4" if needs_uuid4 else "from uuid import UUID"
        )

    # SQLAlchemy symbols actually referenced by the emitted class.
    sa_symbols: set[str] = set()
    for f in fields:
        sa_symbols.add(_sa_type_expr(f).split("(")[0])
        if f.get("foreign_key"):
            sa_symbols.add("ForeignKey")
    if entity_data.get("filters"):
        sa_symbols.add("Index")

    orm_symbols = ["Mapped", "mapped_column"]
    if relationships:
        orm_symbols.append("relationship")

    # Cross-domain imports for the classes referenced by relationship types.
    # Link models are never imported: `secondary=` takes the table name.
    cross_imports: list[str] = []
    for rel in relationships:
        inner = _relationship_target(rel)
        if not inner:
            continue
        rel_domain = entity_domain.get(inner, "")
        if rel_domain and rel_domain != domain:
            line = f"from caramello_api.{rel_domain}.models import {inner}"
            if line not in cross_imports:
                cross_imports.append(line)

    code = ""
    if stdlib_imports:
        code += "\n".join(stdlib_imports) + "\n\n"
    code += f"from sqlalchemy import {', '.join(sorted(sa_symbols))}\n"
    code += f"from sqlalchemy.orm import {', '.join(orm_symbols)}\n\n"
    code += "from caramello_api.shared.base import Base\n"
    if cross_imports:
        code += "\n".join(cross_imports) + "\n"
    code += "\n\n"

    code += f"class {name}(Base):\n"
    code += _docstring_block(description)
    code += f'    __tablename__ = "{table_name}"\n\n'

    table_args_block = _build_table_args(entity_data)
    if table_args_block:
        code += table_args_block + "\n"

    for f in fields:
        code += get_column_definition(f, autoincrement=single_int_pk) + "\n"

    rel_lines = generate_relationships(relationships, entity_table)
    if rel_lines:
        code += "\n" + "\n".join(rel_lines) + "\n"

    code += "\n"
    return code


def _relationship_target(rel: dict[str, Any]) -> str:
    """Nome da classe referenciada por um relacionamento (sem `list[...]`)."""
    raw = rel["type"].strip()
    inner = raw[5:-1].strip().strip('"') if raw.lower().startswith("list[") else raw.strip('"')
    if not inner or inner in STANDARD_TYPES or inner in SPECIAL_TYPES:
        return ""
    return inner


def generate_schemas(entity_data: dict[str, Any]) -> str:
    """Gera imports + os três DTOs Pydantic (`Read`, `Create`, `Update`) de uma entidade.

    `expose_as_uuid: true` substitui a FK inteira (`x_id`) pelo seu equivalente
    público (`x_uuid: UUID`) nos três schemas, enquanto a tabela mantém a coluna
    inteira. Isso é uma invariante do projeto: um id inteiro nunca aparece na
    API pública.
    """
    name = entity_data["name"]
    fields = entity_data.get("fields", [])

    needs_uuid = any(f["type"].strip().lower() == "uuid" or f.get("expose_as_uuid") for f in fields)
    needs_datetime = any(f["type"].strip().lower() == "datetime" for f in fields)
    needs_decimal = any(f["type"].strip().lower() == "decimal" for f in fields)
    needs_emailstr = any(f["type"].strip().lower() == "emailstr" for f in fields)

    code = ""
    stdlib_imports: list[str] = []
    if needs_datetime:
        stdlib_imports.append("from datetime import datetime")
    if needs_decimal:
        stdlib_imports.append("from decimal import Decimal")
    if needs_uuid:
        stdlib_imports.append("from uuid import UUID")
    if stdlib_imports:
        code += "\n".join(stdlib_imports) + "\n\n"

    pydantic_symbols = ["BaseModel", "ConfigDict"]
    if needs_emailstr:
        pydantic_symbols.append("EmailStr")
    code += f"from pydantic import {', '.join(pydantic_symbols)}\n"
    code += "\n\n"

    # --- READ ---
    # from_attributes lets the DTO be built straight from an ORM instance.
    code += f"class {name}Read(BaseModel):\n"
    code += "    model_config = ConfigDict(from_attributes=True)\n\n"
    read_skip = {"id"}
    any_read_field = False
    for f in fields:
        if f["name"] in read_skip:
            continue
        any_read_field = True
        if f.get("expose_as_uuid"):
            base = f["name"].removesuffix("_id")
            nullable = f.get("nullable", True)
            suffix = " | None = None" if nullable else ""
            code += f"    {base}_uuid: UUID{suffix}\n"
            continue
        ftype = map_type_to_python(f["type"])
        if f.get("nullable", True):
            ftype = f"{ftype} | None"
        code += f"    {f['name']}: {ftype}\n"
    if not any_read_field:
        code += "    pass\n"
    code += "\n"

    # --- CREATE ---
    code += f"class {name}Create(BaseModel):\n"
    create_skip = {"id", "created_at", "updated_at", "uuid"}
    any_create_field = False
    for f in fields:
        if f["name"] in create_skip:
            continue
        any_create_field = True
        if f.get("expose_as_uuid"):
            base = f["name"].removesuffix("_id")
            nullable = f.get("nullable", True) or "default" in f or f.get("default_factory")
            code += (
                f"    {base}_uuid: UUID | None = None\n" if nullable else f"    {base}_uuid: UUID\n"
            )
            continue
        ftype = map_type_to_python(f["type"])
        is_optional = f.get("nullable", False) or "default" in f or f.get("default_factory")
        if is_optional:
            ftype = f"{ftype} | None"
        line = f"    {f['name']}: {ftype}"
        if is_optional:
            line += " = None"
        code += line + "\n"
    if not any_create_field:
        code += "    pass\n"
    code += "\n"

    # --- UPDATE ---
    code += f"class {name}Update(BaseModel):\n"
    update_skip = {"id", "uuid", "created_at", "updated_at"}
    any_update_field = False
    for f in fields:
        if f["name"] in update_skip:
            continue
        any_update_field = True
        if f.get("expose_as_uuid"):
            base = f["name"].removesuffix("_id")
            code += f"    {base}_uuid: UUID | None = None\n"
            continue
        ftype = map_type_to_python(f["type"])
        code += f"    {f['name']}: {ftype} | None = None\n"
    if not any_update_field:
        code += "    pass\n"
    code += "\n"

    return code


def generate_router(entity_data: dict[str, Any]) -> str:
    """Gera o router CRUD async com auth para uma entidade."""
    name = entity_data["name"]
    var_name = name.lower()
    table_name = entity_data["table_name"]
    domain = entity_data.get("domain", "")
    url_table_name = table_name.replace("_", "-")

    # `User` is needed for `_: User = Depends(get_current_user)`. In the users
    # domain the class already comes in via the domain's own model import.
    if domain in ("user", "users"):
        user_import_line = ""
    else:
        user_import_line = "from caramello_api.users.models import User\n"

    model_import = f"from caramello_api.{domain}.models import {name}"
    schema_import = (
        f"from caramello_api.{domain}.schemas import {name}Read, {name}Create, {name}Update"
    )

    return f"""from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caramello_api.shared.auth import get_current_user
from caramello_api.shared.database import get_session
{user_import_line}{model_import}
{schema_import}

router = APIRouter(prefix="/{domain}/{url_table_name}", tags=["{name}"])


@router.post("/", response_model={name}Read)
async def create_{var_name}(
    {var_name}_in: {name}Create,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> {name}:
    db_obj = {name}(**{var_name}_in.model_dump(exclude_unset=True))
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[{name}Read])
async def read_{var_name}s(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[{name}]:
    result = await session.execute(select({name}).offset(offset).limit(limit))
    return list(result.scalars().all())


@router.get("/{{uuid}}", response_model={name}Read)
async def read_{var_name}(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> {name}:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.execute(statement)
    {var_name} = result.scalars().first()
    if not {var_name}:
        raise HTTPException(status_code=404, detail="{name} not found")
    return {var_name}


@router.patch("/{{uuid}}", response_model={name}Read)
async def update_{var_name}(
    uuid: UUID,
    {var_name}_in: {name}Update,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> {name}:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")
    update_data = {var_name}_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{{uuid}}")
async def delete_{var_name}(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.execute(statement)
    db_obj = result.scalars().first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")
    await session.delete(db_obj)
    await session.commit()
    return {{"ok": True}}
"""


def generate_operations(op_data: dict[str, Any]) -> str:
    """Gera stub de operations.py a partir de dsl/operations/{domain}.yaml."""
    domain = op_data["domain"]
    operations = op_data.get("operations", [])
    # Deriva o nome da classe canônica do domínio via mapeamento explícito.
    # NÃO usar domain.title(): para "families" produziria "Families" (classe
    # inexistente).
    if domain not in DOMAIN_TO_ENTITY_NAME:
        raise ValueError(
            f"domain {domain!r} não mapeado em DOMAIN_TO_ENTITY_NAME. "
            f"Adicione a entrada para o domínio antes de gerar operations.py."
        )
    domain_class = DOMAIN_TO_ENTITY_NAME[domain]

    header = f"""{ANNOTATION_STUB}
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello_api.shared.auth import get_current_user
from caramello_api.{domain}.models import {domain_class}
from caramello_api.{domain}.schemas import {domain_class}Read

router = APIRouter(prefix="/{domain}", tags=["{domain_class}"])

"""
    body_parts: list[str] = []
    for op in operations:
        name = op["name"]
        method = op["method"].lower()
        path = op["path"]
        # Remove prefix do path para o decorator (prefix já está no APIRouter)
        decorator_path = path
        if decorator_path.startswith(f"/{domain}"):
            decorator_path = decorator_path[len(f"/{domain}") :]
        if not decorator_path:
            decorator_path = "/"
        description = op.get("description", "")
        body_parts.append(
            f'@router.{method}("{decorator_path}", response_model={domain_class}Read)\n'
            f"async def {name}("
            f"current_user: {domain_class} = Depends(get_current_user)"
            f") -> {domain_class}:\n"
            f'    """{description}"""\n'
            f"    raise NotImplementedError\n"
        )
    return header + "\n\n".join(body_parts) + "\n"


def _build_domain_fk_graph(
    all_entities: list[dict[str, Any]],
) -> dict[str, set[str]]:
    """Constrói grafo de dependências reais entre domínios via FKs nos fields.

    Retorna: {domain_A: {domain_B}} — domain_A tem FK para domain_B.
    """
    table_to_domain: dict[str, str] = {
        entity_data["table_name"]: entity_data["domain"] for entity_data in all_entities
    }

    graph: dict[str, set[str]] = {}
    for entity_data in all_entities:
        src_domain = entity_data["domain"]
        for field in entity_data.get("fields", []):
            fk = field.get("foreign_key", "")
            if fk:
                # FK format: "table.column" e.g. "user.id"
                fk_table = fk.split(".")[0]
                dst_domain = table_to_domain.get(fk_table, "")
                if dst_domain and dst_domain != src_domain:
                    graph.setdefault(src_domain, set()).add(dst_domain)
    return graph


def _split_imports_and_classes(block: str, domain: str) -> tuple[list[str], list[str]]:
    """Separa as linhas de import das linhas de classe em um bloco gerado."""
    import_lines: list[str] = []
    class_lines: list[str] = []
    in_classes = False
    for line in block.split("\n"):
        if line.startswith("from __future__"):
            continue
        if line.startswith("class "):
            in_classes = True
            class_lines.append(line)
        elif in_classes:
            class_lines.append(line)
        elif line.startswith(("from ", "import ")):
            # A module never imports from itself.
            if f"from caramello_api.{domain}." not in line:
                import_lines.append(line)
    while class_lines and not class_lines[-1].strip():
        class_lines.pop()
    return import_lines, class_lines


def _assemble_module(
    imports: set[str],
    late_bind_imports: set[str],
    class_blocks: list[str],
) -> str:
    """Monta um módulo a partir dos imports coletados e dos blocos de classe.

    Ruff (isort) reordena os imports depois; o que importa aqui é que cada
    import apareça uma única vez e que o bloco `TYPE_CHECKING` fique separado.
    """
    result = ""
    # Generated modules DO carry `from __future__ import annotations`.
    # SQLAlchemy 2 de-stringifies PEP 563 annotations itself and resolves the
    # entity names through its class registry, so a deferred annotation such as
    # `Mapped[list[Family]]` maps correctly even when `Family` only exists under
    # TYPE_CHECKING. (SQLModel could not: it read the annotation with
    # get_origin/get_args, which returns None for a string — hence the former
    # prohibition, and the UP037 suppressions that kept ruff from unquoting the
    # forward references. Both are gone.)
    result += "from __future__ import annotations\n\n"
    if late_bind_imports:
        result += "from typing import TYPE_CHECKING\n\n"
    if imports:
        result += "\n".join(sorted(imports)) + "\n"
    if late_bind_imports:
        result += "\nif TYPE_CHECKING:\n"
        for imp in sorted(late_bind_imports):
            result += f"    {imp}\n"
    result += "\n\n"
    result += "\n\n\n".join(class_blocks)
    result += "\n"
    return result


def _consolidate_models(
    entities: list[dict[str, Any]],
    entity_domain: dict[str, str],
    all_entities: list[dict[str, Any]] | None = None,
) -> str:
    """Consolida as classes de tabela de todas as entidades de um domínio.

    Detecta ciclos de import entre domínios pelo grafo real de FKs e coloca os
    imports que fechariam o ciclo sob `TYPE_CHECKING`. Isso é seguro porque
    SQLAlchemy só precisa do NOME da classe (resolvido pelo registry) e do nome
    da tabela secundária (resolvido por `Base.metadata`) — nenhuma referência de
    runtime é necessária, e a ordem em que as classes são definidas é
    irrelevante.
    """
    if not entities:
        return ""

    domain = entities[0].get("domain", "")
    fk_graph = _build_domain_fk_graph(all_entities) if all_entities else {}

    def _would_create_cycle(import_domain: str) -> bool:
        """True se importar de import_domain fecharia um ciclo com este domínio."""
        return domain in fk_graph.get(import_domain, set())

    entity_table: dict[str, str] = {e["name"]: e["table_name"] for e in (all_entities or entities)}

    all_imports: set[str] = set()
    late_bind_imports: set[str] = set()
    class_blocks: list[str] = []

    for entity_data in entities:
        block = generate_models(entity_data, entity_domain, entity_table)
        import_lines, class_lines = _split_imports_and_classes(block, domain)

        for imp in import_lines:
            # A cross-domain import that would close a cycle goes under
            # TYPE_CHECKING: only the class NAME is needed at runtime, and the
            # SQLAlchemy registry supplies it.
            if imp.startswith("from caramello_api."):
                imp_domain = imp.split(".")[1]
                if _would_create_cycle(imp_domain):
                    late_bind_imports.add(imp)
                    continue
            all_imports.add(imp)

        if class_lines:
            class_blocks.append("\n".join(class_lines))

    return _assemble_module(all_imports, late_bind_imports, class_blocks)


def _consolidate_schemas(entities: list[dict[str, Any]]) -> str:
    """Consolida os DTOs Pydantic de todas as entidades não-link de um domínio."""
    if not entities:
        return ""
    domain = entities[0].get("domain", "")

    all_imports: set[str] = set()
    class_blocks: list[str] = []
    for entity_data in entities:
        block = generate_schemas(entity_data)
        import_lines, class_lines = _split_imports_and_classes(block, domain)
        all_imports.update(import_lines)
        if class_lines:
            class_blocks.append("\n".join(class_lines))

    return _assemble_module(all_imports, set(), class_blocks)


def _consolidate_routers(
    domain: str,
    non_link_entities: list[dict[str, Any]],
) -> str:
    """Consolida os routers de todas as entidades não-link de um domínio."""
    if not non_link_entities:
        return ""

    # Coletar todos os imports únicos
    all_imports: set[str] = set()
    router_vars: list[str] = []
    endpoint_blocks: list[str] = []

    for entity_data in non_link_entities:
        router_code = generate_router(entity_data)
        lines = router_code.split("\n")

        import_lines: list[str] = []
        router_def_lines: list[str] = []
        endpoint_lines: list[str] = []
        in_endpoints = False
        router_var = ""

        for line in lines:
            if line.startswith("from __future__"):
                continue
            is_import = line.startswith("from ") or line.startswith("import ")
            if is_import and not in_endpoints:
                import_lines.append(line)
            elif line.startswith("router = APIRouter"):
                # Renomear o router para evitar conflito de nomes
                name = entity_data["name"]
                var = f"{name.lower()}_router"
                router_var = var
                router_def_lines.append(line.replace("router = ", f"{var} = "))
            elif in_endpoints or (line.startswith("@") and not line.startswith("@router")):
                in_endpoints = True
                # Substituir @router. pelo nome específico
                if line.startswith("@router."):
                    line = line.replace("@router.", f"@{router_var}.")
                endpoint_lines.append(line)
            elif router_def_lines and line.startswith("@router"):
                in_endpoints = True
                line = line.replace("@router.", f"@{router_var}.")
                endpoint_lines.append(line)
            elif router_def_lines:
                # Estamos após a definição do router
                if line.startswith("@"):
                    in_endpoints = True
                    line = line.replace("@router.", f"@{router_var}.")
                    endpoint_lines.append(line)
                else:
                    endpoint_lines.append(line)

        for imp in import_lines:
            if imp:
                all_imports.add(imp)

        if router_var:
            router_vars.append(router_var)
            router_def = "\n".join(router_def_lines)
            # Remover linhas vazias no final dos endpoints
            while endpoint_lines and not endpoint_lines[-1].strip():
                endpoint_lines.pop()
            endpoint_block = "\n".join(endpoint_lines)
            endpoint_blocks.append(f"{router_def}\n\n{endpoint_block}")

    # Montar arquivo final
    result = "from __future__ import annotations\n\n"
    result += "\n".join(sorted(all_imports)) + "\n"
    result += "\n\n"
    result += "\n\n\n".join(endpoint_blocks)
    result += "\n\n\n"

    # Router raiz que agrega todos
    result += "router = APIRouter()\n"
    for var in router_vars:
        result += f"router.include_router({var})\n"
    result += "\n"

    return result


def main() -> None:
    """Ponto de entrada do generator DSL."""
    print("Starting Code Generation...")

    manifest = load_yaml(DSL_DIR / "manifest.yaml")
    if not manifest:
        return
    entity_files: list[str] = manifest.get("x-caramello-entities", [])

    # Passo 1: construir entity_domain antes de gerar nada
    entity_domain: dict[str, str] = {}
    entities_by_domain: dict[str, list[dict[str, Any]]] = {}
    for entity_file in entity_files:
        data = load_yaml(ENTITIES_DIR / entity_file)
        if not data:
            continue
        domain = data.get("domain")
        if not domain:
            raise ValueError(f"{entity_file} missing 'domain' field")
        entity_domain[data["name"]] = domain
        entities_by_domain.setdefault(domain, []).append(data)

    # Coletar todas as entidades em lista plana para análise de ciclos
    all_entities_flat = [
        e for domain_entities in entities_by_domain.values() for e in domain_entities
    ]

    # Passo 2: gerar models.py, schemas.py e router.py por domínio (passagem única)
    for domain, entities in entities_by_domain.items():
        domain_dir = SRC_DIR / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        (domain_dir / "__init__.py").touch()

        models_code = _consolidate_models(entities, entity_domain, all_entities_flat)
        (domain_dir / "models.py").write_text(models_code)
        print(f"  wrote {domain_dir}/models.py")

        # schemas.py e router.py: apenas entidades não-link (link models não têm DTOs)
        non_link = [e for e in entities if not e.get("is_link_model")]
        if non_link:
            schemas_code = _consolidate_schemas(non_link)
            (domain_dir / "schemas.py").write_text(schemas_code)
            print(f"  wrote {domain_dir}/schemas.py")

            router_code = _consolidate_routers(domain, non_link)
            (domain_dir / "router.py").write_text(router_code)
            print(f"  wrote {domain_dir}/router.py")

    # Passo 3: gerar operations.py por domínio (respeitando anotação)
    if OPERATIONS_DIR.exists():
        for op_file in sorted(OPERATIONS_DIR.glob("*.yaml")):
            op_data = load_yaml(op_file)
            if not op_data:
                continue
            domain = op_data["domain"]
            ops_path = SRC_DIR / domain / "operations.py"
            if ops_path.exists():
                first_line = ops_path.read_text().splitlines()[0].strip()
                if first_line == ANNOTATION_IMPLEMENTED:
                    print(f"  skipping {ops_path} (implemented)")
                    continue
            ops_code = generate_operations(op_data)
            ops_path.write_text(ops_code)
            print(f"  wrote {ops_path}")

    # Passo 4: formatar código gerado com ruff (fix + format) para garantir conformidade
    _run_ruff_fix(SRC_DIR)

    print("Generation Complete.")


def _run_ruff_fix(src_dir: Path) -> None:
    """Executa ruff --fix e ruff format nos arquivos gerados.

    Descobre dinamicamente os diretórios de domínio em src_dir,
    excluindo diretórios internos (_*) e os que não contêm código gerado:
    shared, core, i18n e migrations (as revisions do Alembic são histórico
    imutável e não devem ser reformatadas).
    """
    import subprocess

    dirs = [
        str(d)
        for d in sorted(src_dir.iterdir())
        if d.is_dir()
        and not d.name.startswith("_")
        and d.name not in ("shared", "core", "i18n", "migrations")
    ]
    if not dirs:
        return
    # 1. Aplicar fixes automáticos (isort, UP037, etc.)
    subprocess.run(
        ["python", "-m", "ruff", "check", "--fix", "--unsafe-fixes", *dirs],
        capture_output=True,
    )
    # 2. Formatar (line length)
    subprocess.run(
        ["python", "-m", "ruff", "format", *dirs],
        capture_output=True,
    )


if __name__ == "__main__":
    main()
