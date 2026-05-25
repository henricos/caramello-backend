import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Set
from caramello.core.config import settings

# Define base paths
ROOT_DIR = Path(__file__).parent.parent
DSL_DIR = ROOT_DIR / "dsl"
ENTITIES_DIR = DSL_DIR / "entities"
MODELS_OUTPUT_DIR = ROOT_DIR / "src" / "caramello" / "models"
API_OUTPUT_DIR = ROOT_DIR / "src" / "caramello" / "api" / "generated"
TESTS_OUTPUT_DIR = ROOT_DIR / "tests" / "generated"

# Standard Python types that don't need special imports or quotes
STANDARD_TYPES = {"int", "str", "bool", "float", "list", "dict"}

def load_yaml(file_path: Path) -> Any:
    """Loads a YAML file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def map_type_to_python(dsl_type: str) -> str:
    """Maps DSL types to Python/SQLModel types."""
    clean_type = dsl_type.strip()
    
    # Handle list[T] or List[T]
    if clean_type.lower().startswith("list["):
        inner = clean_type[5:-1]
        # Keep inner as string ref for forward declarations if it's an entity
        if inner not in STANDARD_TYPES and inner not in ["UUID", "datetime", "EmailStr"]:
             return f"list['{inner}']"
        return f"list[{inner}]"

    type_map = {
        "uuid": "UUID",
        "string": "str",
        "text": "str",
        "integer": "int",
        "boolean": "bool",
        "datetime": "datetime",
        "emailstr": "EmailStr",
    }
    
    mapped = type_map.get(clean_type.lower())
    if mapped:
        return mapped
        
    # Assume it's an entity class name -> forward ref
    return f"'{clean_type}'"

def get_field_definition(field: Dict[str, Any], is_optional: bool = False, force_optional: bool = False) -> str:
    fname = field['name']
    ftype = map_type_to_python(field['type'])
    
    # Determine nullability
    is_nullable = field.get('nullable', True)
    if field.get('primary_key'):
        is_nullable = False
        force_optional = True
    
    if force_optional:
        is_nullable = True
        
    # Construct type string
    type_str = ftype
    
    # Handle Optional wrapper
    if is_nullable:
        # Check if it's a forward ref string, needing special handling?
        # Standard typing: Optional['Entity'] is valid
        if not type_str.startswith("Optional"):
            type_str = f"Optional[{type_str}]"
    
    # Build Field() args
    field_args = []
    
    if field.get('primary_key'):
        field_args.append("primary_key=True")
    if field.get('foreign_key'):
        field_args.append(f"foreign_key='{field['foreign_key']}'")
    if field.get('unique'):
        field_args.append("unique=True")
    if field.get('max_length'):
        field_args.append(f"max_length={field['max_length']}")
    
    # Defaults
    if field.get('default_factory'):
        if field['default_factory'] == 'uuid4':
            field_args.append("default_factory=uuid4")
        elif field['default_factory'] == 'now_utc':
            field_args.append("default_factory=lambda: datetime.now(timezone.utc)")
    elif 'default' in field:
         val = field['default']
         if isinstance(val, str):
             field_args.append(f"default='{val}'")
         else:
             field_args.append(f"default={val}")
    elif is_nullable or force_optional:
        field_args.append("default=None")
        
    # Nullable constraint in DB
    if not is_nullable:
        field_args.append("nullable=False")
        
    field_def = f"    {fname}: {type_str} = Field({', '.join(field_args)})"
    return field_def

def generate_relationships(relationships: List[Dict], entity_name: str) -> List[str]:
    lines = []
    for rel in relationships:
        rname = rel['name']
        rtype = map_type_to_python(rel['type'])
        
        args = []
        if rel.get('back_populates'):
            args.append(f"back_populates='{rel['back_populates']}'")
        if rel.get('link_model'):
            args.append(f"link_model={rel['link_model']}")
            
        lines.append(f"    {rname}: {rtype} = Relationship({', '.join(args)})")
    return lines

def generate_models(entity_data: Dict[str, Any]) -> str:
    name = entity_data['name']
    table_name = entity_data['table_name']
    fields = entity_data.get('fields', [])
    relationships = entity_data.get('relationships', [])
    description = entity_data.get('description', '')

    imports = [
        "from typing import Optional, List",
        "from uuid import UUID, uuid4",
        "from datetime import datetime, timezone",
        "from sqlmodel import SQLModel, Field, Relationship",
        "from pydantic import EmailStr"
    ]
    
    # Check for link_model imports
    for rel in relationships:
        if rel.get('link_model'):
            lm = rel['link_model']
            imports.append(f"from caramello.models.{lm.lower()} import {lm}")

    code = "\n".join(imports) + "\n\n"

    # 1. Base Model (Common Fields)
    # Exclude system fields (id, created_at, updated_at) and secrets (hashed_password) usually?
    # Actually, Base usually has business fields. Let's separate carefully.
    
    base_fields = []
    table_fields = [] # Extra fields just for table
    
    for f in fields:
        fname = f['name']
        # ID and Timestamp usually managed by system, but good to have in Table.
        # UUID is common.
        # Secrets like hashed_password should NOT be in Base if we use Base for Read/Create indiscriminately.
        # Strategy:
        # Base: Public regular fields (name, email, etc)
        # Table: Base + ID + Timestamp + Secrets + Relationships
        # Read: Base + ID + UUID + Timestamp
        # Create: Base + Secrets (plain) - logic needed here.
        
        # Let's keep it simple: Define explicit sets.
        pass

    # Simplified generation strategy:
    # Everything is defined in Table Model.
    # Read/Create/Update are subsets generated dynamically.
    
    # -- MODEL (TABLE) --
    code += f"class {name}(SQLModel, table=True):\n"
    code += f"    \"\"\"{description}\"\"\"\n"
    code += f"    __tablename__ = \"{table_name}\"\n\n"
    
    for f in fields:
        code += get_field_definition(f) + "\n"
        
    # Relationships
    rel_lines = generate_relationships(relationships, name)
    if rel_lines:
        code += "\n" + "\n".join(rel_lines) + "\n"
        
    code += "\n"
    
    # -- READ MODEL --
    # Omit sensitive fields (like hashed_password)
    # Include all others + ID/UUID/Timestamps
    code += f"class {name}Read(SQLModel):\n"
    for f in fields:
        if f['name'] in ["hashed_password", "id"]: continue
        # Force optional? No, Read should reflect data state.
        # We need types but without Field(table_args...)
        # Just use simple annotation
        ftype = map_type_to_python(f['type'])
        if f.get('nullable', False) and not ftype.startswith("Optional"):
            ftype = f"Optional[{ftype}]"
        code += f"    {f['name']}: {ftype}\n"
    code += "\n"

    # -- CREATE MODEL --
    # Omit ID, CreatedAt, UpdatedAt (system managed)
    # Include password (plain) if it exists as hashed_password? 
    # For this generator, let's assume 'hashed_password' implies inputting 'password'. 
    # But usually DSL defines 'hashed_password'. We'd need a 'password' field in Create.
    # Let's just expose what is in DSL fields that are not system.
    
    code += f"class {name}Create(SQLModel):\n"
    for f in fields:
        if f['name'] in ['id', 'created_at', 'updated_at', 'uuid']: continue
        
        fname = f['name']
        ftype = map_type_to_python(f['type'])
        
        # Special handling for password
        if fname == 'hashed_password':
            code += f"    password: str\n"
            continue
            
        is_optional = f.get('nullable', False) or 'default' in f
        if is_optional and not ftype.startswith("Optional"):
            ftype = f"Optional[{ftype}]"
            
        line = f"    {fname}: {ftype}"
        if is_optional:
            line += " = None"
        code += line + "\n"
    code += "\n"

    # -- UPDATE MODEL --
    # All fields optional
    code += f"class {name}Update(SQLModel):\n"
    for f in fields:
        if f['name'] in ['id', 'uuid', 'created_at', 'updated_at']: continue
        
        fname = f['name']
        ftype = map_type_to_python(f['type'])
        
        if fname == 'hashed_password':
            code += f"    password: Optional[str] = None\n"
            continue
            
        if not ftype.startswith("Optional"):
            ftype = f"Optional[{ftype}]"
            
        code += f"    {fname}: {ftype} = None\n"
    code += "\n"

    return code

def generate_router(entity_data: Dict[str, Any]) -> str:
    name = entity_data['name']
    var_name = name.lower()
    table_name = entity_data['table_name']

    return f"""from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from uuid import UUID
from sqlmodel.ext.asyncio.session import AsyncSession
from caramello.shared.database import get_session
from caramello.models.{var_name} import {name}, {name}Read, {name}Create, {name}Update

router = APIRouter(prefix="/{table_name}", tags=["{name}"])


@router.post("/", response_model={name}Read)
async def create_{var_name}({var_name}_in: {name}Create, session: AsyncSession = Depends(get_session)):
    db_obj = {name}.model_validate({var_name}_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.get("/", response_model=list[{name}Read])
async def read_{var_name}s(
    session: AsyncSession = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    result = await session.exec(select({name}).offset(offset).limit(limit))
    return result.all()


@router.get("/{{uuid}}", response_model={name}Read)
async def read_{var_name}(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    {var_name} = result.first()
    if not {var_name}:
        raise HTTPException(status_code=404, detail="{name} not found")
    return {var_name}


@router.patch("/{{uuid}}", response_model={name}Read)
async def update_{var_name}(uuid: UUID, {var_name}_in: {name}Update, session: AsyncSession = Depends(get_session)):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")

    hero_data = {var_name}_in.model_dump(exclude_unset=True)
    for key, value in hero_data.items():
        setattr(db_obj, key, value)

    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


@router.delete("/{{uuid}}")
async def delete_{var_name}(uuid: UUID, session: AsyncSession = Depends(get_session)):
    statement = select({name}).where({name}.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="{name} not found")

    await session.delete(db_obj)
    await session.commit()
    return {{"ok": True}}
"""

def generate_test(entity_data: Dict[str, Any]) -> str:
    name = entity_data['name']
    var_name = name.lower()
    table_name = entity_data['table_name']
    
    # Need sample data for create
    # Naive sample data generation
    sample_data = {}
    for f in entity_data.get('fields', []):
        if f['name'] not in ['id', 'uuid', 'created_at', 'updated_at']:
            # dumb defaults
            if f['type'] == 'int': val = 1
            elif f['type'] == 'str': val = "test_string"
            elif f['type'] == 'EmailStr': val = "test@example.com"
            elif f['type'] == 'bool': val = True
            elif f['type'] == 'float': val = 1.0
            elif f['type'] == 'datetime': val = "2026-01-01T00:00:00"
            else: val = None
            
            if f['name'] == 'hashed_password':
                sample_data['password'] = "secret123"
            else:
                sample_data[f['name']] = val
    
    return f"""import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from uuid import uuid4
from caramello.main import app
from caramello.models.{var_name} import {name}

@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)

def test_create_{var_name}(client: TestClient):
    # Dynamic sample data
    data = {sample_data}
    # Fix unique constraints
    if "email" in data: data["email"] = f"test_{{uuid4()}}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{{uuid4()}}"
    if "uuid" in data: del data["uuid"] # Should not send UUID on create usually?
    
    response = client.post(
        "/{table_name}/",
        json=data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] is not None

def test_read_{var_name}(client: TestClient):
    # Dynamic sample data
    data = {sample_data}
    if "email" in data: data["email"] = f"test_{{uuid4()}}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{{uuid4()}}"
    
    # Create first
    create_res = client.post(
        "/{table_name}/",
        json=data
    )
    assert create_res.status_code == 200, create_res.text
    uuid = create_res.json()["uuid"]
    
    response = client.get(f"/{table_name}/{{uuid}}")
    assert response.status_code == 200
    assert response.json()["uuid"] == uuid

def test_read_{var_name}_list(client: TestClient):
    # Dynamic sample data
    data = {sample_data}
    if "email" in data: data["email"] = f"test_{{uuid4()}}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{{uuid4()}}"

    client.post("/{table_name}/", json=data)
    response = client.get("/{table_name}/")
    assert response.status_code == 200
    assert len(response.json()) > 0
"""

def main():
    print("🚀 Starting Code Generation...")
    
    MODELS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    API_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    (MODELS_OUTPUT_DIR / "__init__.py").touch()
    (API_OUTPUT_DIR / "__init__.py").touch()
    (TESTS_OUTPUT_DIR / "__init__.py").touch()
    
    manifest_path = DSL_DIR / "manifest.yaml"
    manifest = load_yaml(manifest_path)
    
    if not manifest:
        return

    entity_ids = manifest.get('x-caramello-entities', [])
    
    for entity_file in entity_ids:
        print(f"Processing {entity_file}...")
        entity_path = ENTITIES_DIR / entity_file
        data = load_yaml(entity_path)
        if not data: continue
        
        name = data['name']
        is_link = data.get('is_link_model', False)
        
        # 1. Model
        model_code = generate_models(data)
        with open(MODELS_OUTPUT_DIR / f"{name.lower()}.py", 'w') as f:
            f.write(model_code)
            
        if is_link:
            continue
            
        # 2. Router (Only for Main Entities)
        router_code = generate_router(data)
        with open(API_OUTPUT_DIR / f"{name.lower()}_router.py", 'w') as f:
            f.write(router_code)
            
        # 3. Tests
        test_code = generate_test(data)
        with open(TESTS_OUTPUT_DIR / f"test_{name.lower()}.py", 'w') as f:
            f.write(test_code)
            
    print("✅ Generation Complete.")

if __name__ == "__main__":
    main()
