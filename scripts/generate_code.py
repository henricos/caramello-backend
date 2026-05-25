"""DSL code generator for the Caramello backend.

Reads `dsl/entities/*.yaml` and `dsl/operations/*.yaml`, emits code at
`src/caramello/{domain}/` (models.py, router.py, operations.py).

See .planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-RESEARCH.md
for the design (Generator Evolution section).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).parent.parent
DSL_DIR = ROOT_DIR / "dsl"
ENTITIES_DIR = DSL_DIR / "entities"
OPERATIONS_DIR = DSL_DIR / "operations"
SRC_DIR = ROOT_DIR / "src" / "caramello"

STANDARD_TYPES = {"int", "str", "bool", "float", "list", "dict"}

ANNOTATION_STUB = "# CARAMELLO-GENERATED: stub"
ANNOTATION_IMPLEMENTED = "# CARAMELLO-GENERATED: implemented"


def load_yaml(file_path: Path) -> Any:
    """Carrega um arquivo YAML de forma segura."""
    try:
        with open(file_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None


def map_type_to_python(dsl_type: str) -> str:
    """Maps DSL types to Python/SQLModel types (modern syntax)."""
    clean_type = dsl_type.strip()
    if clean_type.lower().startswith("list["):
        inner = clean_type[5:-1].strip()
        special = {"UUID", "datetime", "EmailStr"}
        if inner not in STANDARD_TYPES and inner not in special:
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
    }
    mapped = type_map.get(clean_type.lower())
    if mapped:
        return mapped
    # Assume entity class name -> forward ref string
    return f'"{clean_type}"'


def get_field_definition(field: dict[str, Any], force_optional: bool = False) -> str:
    """Gera a definição de um campo SQLModel com Field(...)."""
    fname = field["name"]
    ftype = map_type_to_python(field["type"])
    is_nullable = field.get("nullable", True)
    if field.get("primary_key"):
        is_nullable = False
        force_optional = True
    if force_optional:
        is_nullable = True
    type_str = ftype
    if is_nullable:
        type_str = f"{type_str} | None"
    field_args: list[str] = []
    if field.get("primary_key"):
        field_args.append("primary_key=True")
    if field.get("foreign_key"):
        field_args.append(f"foreign_key={field['foreign_key']!r}")
    if field.get("unique"):
        field_args.append("unique=True")
    if field.get("max_length"):
        field_args.append(f"max_length={field['max_length']}")
    if field.get("default_factory"):
        if field["default_factory"] == "uuid4":
            field_args.append("default_factory=uuid4")
        elif field["default_factory"] == "now_utc":
            field_args.append("default_factory=lambda: datetime.now(timezone.utc)")
    elif "default" in field:
        val = field["default"]
        if isinstance(val, str):
            field_args.append(f"default={val!r}")
        else:
            field_args.append(f"default={val}")
    elif is_nullable or force_optional:
        field_args.append("default=None")
    if not is_nullable:
        field_args.append("nullable=False")
    return f"    {fname}: {type_str} = Field({', '.join(field_args)})"


def generate_relationships(
    relationships: list[dict[str, Any]],
    entity_name: str,
    entity_domain: dict[str, str],
) -> list[str]:
    """Gera as linhas de Relationship() para uma entidade."""
    lines = []
    for rel in relationships:
        rname = rel["name"]
        rtype = map_type_to_python(rel["type"])

        args: list[str] = []
        if rel.get("back_populates"):
            args.append(f"back_populates={rel['back_populates']!r}")
        if rel.get("link_model"):
            args.append(f"link_model={rel['link_model']}")

        lines.append(f"    {rname}: {rtype} = Relationship({', '.join(args)})")
    return lines


def generate_models(
    entity_data: dict[str, Any],
    entity_domain: dict[str, str],
) -> str:
    """Gera o bloco de 4 classes (Table, Read, Create, Update) para uma entidade."""
    name = entity_data["name"]
    table_name = entity_data["table_name"]
    fields = entity_data.get("fields", [])
    relationships = entity_data.get("relationships", [])
    description = entity_data.get("description", "")
    is_link = entity_data.get("is_link_model", False)
    domain = entity_data.get("domain", "")

    # Calcular quais imports serão necessários
    needs_uuid = any(
        f.get("type", "").lower() in ("uuid",) or f.get("default_factory") == "uuid4"
        for f in fields
    )
    needs_datetime = any(
        f.get("type", "").lower() == "datetime"
        or f.get("default_factory") in ("now_utc",)
        for f in fields
    )
    needs_emailstr = any(f.get("type", "").lower() == "emailstr" for f in fields)

    # Imports cross-domain para link_models
    cross_imports: list[str] = []
    for rel in relationships:
        if rel.get("link_model"):
            lm = rel["link_model"]
            lm_domain = entity_domain.get(lm, "")
            if lm_domain and lm_domain != domain:
                cross_imports.append(
                    f"from caramello.{lm_domain}.models import {lm}"
                )

    # Imports cross-domain em relacionamentos (ex: User em family/models.py)
    for rel in relationships:
        rtype_raw = rel["type"].strip()
        # Extrair nome base do tipo (sem list[...])
        if rtype_raw.lower().startswith("list["):
            inner = rtype_raw[5:-1].strip().strip('"')
        else:
            inner = rtype_raw.strip('"')
        special2 = {"UUID", "datetime", "EmailStr"}
        if inner and inner not in STANDARD_TYPES and inner not in special2:
            rel_domain = entity_domain.get(inner, "")
            if rel_domain and rel_domain != domain:
                ci = f"from caramello.{rel_domain}.models import {inner}"
                if ci not in cross_imports:
                    cross_imports.append(ci)

    code = "from __future__ import annotations\n\n"

    # Imports de stdlib e terceiros
    stdlib_imports: list[str] = []
    if needs_datetime:
        stdlib_imports.append("from datetime import datetime, timezone")
    if needs_uuid:
        stdlib_imports.append("from uuid import UUID, uuid4")
    if stdlib_imports:
        code += "\n".join(stdlib_imports) + "\n\n"

    third_party: list[str] = []
    if needs_emailstr:
        third_party.append("from pydantic import EmailStr")
    third_party.append("from sqlmodel import Field, Relationship, SQLModel")
    code += "\n".join(third_party) + "\n"

    if cross_imports:
        code += "\n" + "\n".join(cross_imports) + "\n"

    code += "\n\n"

    # --- TABLE MODEL ---
    code += f"class {name}(SQLModel, table=True):\n"
    code += f'    """{description}"""\n'
    code += f'    __tablename__ = "{table_name}"\n\n'

    for f in fields:
        code += get_field_definition(f) + "\n"

    rel_lines = generate_relationships(relationships, name, entity_domain)
    if rel_lines:
        code += "\n" + "\n".join(rel_lines) + "\n"

    code += "\n"

    if is_link:
        # Link models não têm Read/Create/Update
        return code

    # --- READ MODEL ---
    code += f"class {name}Read(SQLModel):\n"
    read_skip = {"id"}
    any_read_field = False
    for f in fields:
        if f["name"] in read_skip:
            continue
        any_read_field = True
        ftype = map_type_to_python(f["type"])
        nullable = f.get("nullable", True)
        if nullable:
            ftype = f"{ftype} | None"
        code += f"    {f['name']}: {ftype}\n"
    if not any_read_field:
        code += "    pass\n"
    code += "\n"

    # --- CREATE MODEL ---
    code += f"class {name}Create(SQLModel):\n"
    create_skip = {"id", "created_at", "updated_at", "uuid"}
    any_create_field = False
    for f in fields:
        if f["name"] in create_skip:
            continue
        any_create_field = True
        fname = f["name"]
        ftype = map_type_to_python(f["type"])
        is_optional = (
            f.get("nullable", False) or "default" in f or f.get("default_factory")
        )
        if is_optional:
            ftype = f"{ftype} | None"
        line = f"    {fname}: {ftype}"
        if is_optional:
            line += " = None"
        code += line + "\n"
    if not any_create_field:
        code += "    pass\n"
    code += "\n"

    # --- UPDATE MODEL ---
    code += f"class {name}Update(SQLModel):\n"
    update_skip = {"id", "uuid", "created_at", "updated_at"}
    any_update_field = False
    for f in fields:
        if f["name"] in update_skip:
            continue
        any_update_field = True
        fname = f["name"]
        ftype = map_type_to_python(f["type"])
        code += f"    {fname}: {ftype} | None = None\n"
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

    return f"""from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.{domain}.models import {name}, {name}Read, {name}Create, {name}Update

router = APIRouter(prefix="/{table_name}", tags=["{name}"])


@router.post("/", response_model={name}Read)
async def create_{var_name}(
    {var_name}_in: {name}Create,
    session: AsyncSession = Depends(get_session),
    _: {name} = Depends(get_current_user),
) -> {name}:
    db_obj = {name}.model_validate({var_name}_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[{name}Read])
async def read_{var_name}s(
    session: AsyncSession = Depends(get_session),
    _: {name} = Depends(get_current_user),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
) -> list[{name}]:
    result = await session.exec(select({name}).offset(offset).limit(limit))
    return list(result.all())


@router.get("/{{uuid}}", response_model={name}Read)
async def read_{var_name}(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: {name} = Depends(get_current_user),
) -> {name}:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    {var_name} = result.first()
    if not {var_name}:
        raise HTTPException(status_code=404, detail="{name} not found")
    return {var_name}


@router.patch("/{{uuid}}", response_model={name}Read)
async def update_{var_name}(
    uuid: UUID,
    {var_name}_in: {name}Update,
    session: AsyncSession = Depends(get_session),
    _: {name} = Depends(get_current_user),
) -> {name}:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
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
    _: {name} = Depends(get_current_user),
) -> dict[str, bool]:
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
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
    # Deriva o nome da classe principal do domínio
    domain_class = domain.title()
    if domain == "user":
        domain_class = "User"

    header = f"""{ANNOTATION_STUB}
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.{domain}.models import {domain_class}, {domain_class}Read

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
            decorator_path = decorator_path[len(f"/{domain}"):]
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


def _consolidate_models(
    entities: list[dict[str, Any]],
    entity_domain: dict[str, str],
) -> str:
    """Consolida os modelos de todas as entidades de um domínio em um único arquivo."""
    if not entities:
        return ""

    domain = entities[0].get("domain", "")

    # Coletar imports únicos de cada entidade
    all_imports: set[str] = set()
    class_blocks: list[str] = []

    for entity_data in entities:
        block = generate_models(entity_data, entity_domain)
        lines = block.split("\n")

        # Separar imports do bloco de classes
        import_lines: list[str] = []
        class_lines: list[str] = []
        in_classes = False

        for line in lines:
            if line.startswith("from __future__"):
                # Sempre vai no topo — gerenciado separadamente
                continue
            if (
                line.startswith("from ")
                or line.startswith("import ")
                or line == ""
            ) and not in_classes:
                circular = f"from caramello.{domain}.models import"
                if (
                    (line.startswith("from ") or line.startswith("import "))
                    and circular not in line
                ):
                    import_lines.append(line)
            elif line.startswith("class "):
                in_classes = True
                class_lines.append(line)
            elif in_classes:
                class_lines.append(line)

        for imp in import_lines:
            if imp:
                all_imports.add(imp)

        if class_lines:
            # Remover linhas vazias no final
            while class_lines and not class_lines[-1].strip():
                class_lines.pop()
            class_blocks.append("\n".join(class_lines))

    # Montar arquivo final
    result = "from __future__ import annotations\n\n"

    # Ordenar imports: stdlib depois terceiros depois locais
    stdlib = sorted(
        i
        for i in all_imports
        if i.startswith("from datetime") or i.startswith("from uuid")
    )
    third_party = sorted(
        i
        for i in all_imports
        if not i.startswith("from datetime")
        and not i.startswith("from uuid")
        and not i.startswith("from caramello")
    )
    local_imports = sorted(i for i in all_imports if i.startswith("from caramello"))

    if stdlib:
        result += "\n".join(stdlib) + "\n"
    if third_party:
        if stdlib:
            result += "\n"
        result += "\n".join(third_party) + "\n"
    if local_imports:
        result += "\n"
        result += "\n".join(local_imports) + "\n"

    result += "\n\n"
    result += "\n\n\n".join(class_blocks)
    result += "\n"

    return result


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
            elif in_endpoints or (
                line.startswith("@") and not line.startswith("@router")
            ):
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

    stdlib = sorted(i for i in all_imports if i.startswith("from uuid"))
    third_party = sorted(
        i
        for i in all_imports
        if not i.startswith("from uuid") and not i.startswith("from caramello")
    )
    local_imports = sorted(i for i in all_imports if i.startswith("from caramello"))

    if stdlib:
        result += "\n".join(stdlib) + "\n"
    if third_party:
        if stdlib:
            result += "\n"
        result += "\n".join(third_party) + "\n"
    if local_imports:
        result += "\n"
        result += "\n".join(local_imports) + "\n"

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

    # Passo 2: gerar models.py e router.py por domínio
    for domain, entities in entities_by_domain.items():
        domain_dir = SRC_DIR / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        (domain_dir / "__init__.py").touch()

        # models.py: concatenar classes de todas as entidades do domínio
        models_code = _consolidate_models(entities, entity_domain)
        (domain_dir / "models.py").write_text(models_code)
        print(f"  wrote {domain_dir}/models.py")

        # router.py: concatenar routers das entidades não-link
        non_link = [e for e in entities if not e.get("is_link_model")]
        if non_link:
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

    print("Generation Complete.")


if __name__ == "__main__":
    main()
