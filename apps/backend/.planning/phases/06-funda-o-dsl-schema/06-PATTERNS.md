# Phase 6: Fundação DSL + Schema — Mapa de Padrões

**Mapeado:** 2026-05-31
**Arquivos analisados:** 9 novos/modificados
**Análogos encontrados:** 8 / 9

---

## Classificação de Arquivos

| Arquivo Novo/Modificado | Papel | Fluxo de Dados | Análogo Mais Próximo | Qualidade |
|-------------------------|-------|----------------|----------------------|-----------|
| `dsl/entities/account.yaml` | config/dsl | transform | `dsl/entities/family.yaml` | exact |
| `dsl/entities/movement.yaml` | config/dsl | transform | `dsl/entities/family_invitation.yaml` | role-match |
| `dsl/entities/financial_entry.yaml` | config/dsl | transform | `dsl/entities/family_invitation.yaml` | role-match |
| `dsl/entities/category.yaml` | config/dsl | transform | `dsl/entities/family.yaml` | exact |
| `dsl/entities/subcategory.yaml` | config/dsl | transform | `dsl/entities/family_invitation.yaml` | role-match |
| `dsl/manifest.yaml` | config | — | `dsl/manifest.yaml` (existente) | exact |
| `dsl/operations/finances.yaml` | config/dsl | — | `dsl/operations/family.yaml` | exact |
| `scripts/generate_code.py` | utility/generator | transform | `scripts/generate_code.py` (existente) | exact |
| `alembic/env.py` | config/migration | batch | `alembic/env.py` (existente) | exact |
| `alembic/versions/0002_finances_schema.py` | migration | batch | `alembic/versions/0001_initial_schema.py` | exact |
| `src/caramello/finances/models.py` | model | CRUD | `src/caramello/families/models.py` | exact |
| `src/caramello/finances/router.py` | controller | request-response | `src/caramello/families/router.py` | exact |
| `src/caramello/finances/operations.py` | service/stub | request-response | `src/caramello/families/operations.py` | exact |
| `dsl/schema.yaml` | config/validation | — | `dsl/schema.yaml` (existente) | exact |
| `tests/test_generator.py` | test | — | `tests/test_generator.py` (existente) | exact |

---

## Atribuições de Padrões

### `dsl/entities/account.yaml` (config/dsl, transform)

**Análogo:** `dsl/entities/family.yaml`

**Estrutura canônica do YAML** (linhas 1-67):
```yaml
# dsl/entities/family.yaml — template completo
name: Family
domain: families
description: "Represents a family group in the system."
table_name: family

fields:
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

  - name: name
    type: str
    max_length: 100
    nullable: false
    description: "Name of the family."

  - name: created_at
    type: datetime
    default_factory: now_utc
    nullable: false
    description: "Timestamp of the record's creation."

  - name: updated_at
    type: datetime
    default_factory: now_utc
    nullable: false
    description: "Timestamp of the record's last update."

relationships:
  - name: invitations
    type: "list[FamilyInvitation]"
    relationship_type: "OneToMany"
    back_populates: "family"
    foreign_key: "FamilyInvitation.family_id"
    description: "Invitations associated with this family."
```

**Campos obrigatórios em toda entidade:**
- `id` (int, primary_key: true)
- `uuid` (UUID, unique: true, default_factory: uuid4, nullable: false)
- `created_at` (datetime, default_factory: now_utc, nullable: false)
- `updated_at` (datetime, default_factory: now_utc, nullable: false)

**Novidade para Phase 6 — campo monetário:**
```yaml
# Tipo Decimal → NUMERIC(15,2) no banco (D-01/D-02)
- name: amount
  type: Decimal
  nullable: false
  description: "Valor da movimentação."
```

**Novidade para Phase 6 — bloco filters:** (D-11):
```yaml
# Gera __table_args__ com Index no modelo (verificado localmente)
filters:
  - fields: [family_id]
  - fields: [competencia_year, competencia_month]
```

---

### `dsl/entities/movement.yaml` e `dsl/entities/financial_entry.yaml` (config/dsl, transform)

**Análogo:** `dsl/entities/family_invitation.yaml`

**Padrão com FK para outra entidade** (linhas 1-35 de `family_invitation.yaml`):
```yaml
name: FamilyInvitation
domain: families
description: "..."
table_name: family_invitation

fields:
  - name: family_id
    type: int
    foreign_key: "family.id"
    nullable: false
    description: "FK para família dona da conta."
```

**FK cross-domain** — `finances` referenciando `users` e `families`:
```yaml
# Padrão estabelecido: foreign_key aponta para table.column
- name: family_id
  type: int
  foreign_key: "family.id"
  nullable: false

- name: user_id
  type: int
  foreign_key: "user.id"
  nullable: false
```

**Campos unique:** (D-10 — `unique: true` por campo, sem `sa_column`):
```yaml
# Único por campo string — Field(unique=True) emitido pelo gerador
- name: import_hash
  type: str
  unique: true
  nullable: true
  description: "Hash SHA-256 do registro importado (deduplicação)."
```

---

### `dsl/entities/category.yaml` e `dsl/entities/subcategory.yaml` (config/dsl, transform)

**Análogo:** `dsl/entities/family.yaml` para `category.yaml`; `dsl/entities/family_invitation.yaml` para `subcategory.yaml`

Mesma estrutura canônica de campos padrão. `subcategory.yaml` adiciona FK obrigatória:
```yaml
# subcategory.yaml — hierarquia de dois níveis (D-06)
- name: category_id
  type: int
  foreign_key: "category.id"
  nullable: false
  description: "FK para categoria pai (nível 1)."
```

---

### `dsl/manifest.yaml` (config)

**Análogo:** `dsl/manifest.yaml` (existente, linhas 1-13)

**Padrão de registro** — adicionar 5 entradas:
```yaml
# dsl/manifest.yaml — estado atual
x-caramello-entities:
  - user.yaml
  - family.yaml
  - family_member.yaml
  - family_invitation.yaml
# Adicionar após family_invitation.yaml:
  - account.yaml
  - movement.yaml
  - financial_entry.yaml
  - category.yaml
  - subcategory.yaml
```

---

### `dsl/operations/finances.yaml` (config/dsl)

**Análogo:** `dsl/operations/family.yaml` (linhas 1-36)

**Estrutura do arquivo de operações:**
```yaml
# dsl/operations/family.yaml — template
domain: families
operations:
  - name: registry_family
    method: POST
    path: /families/registry
    description: "Descrição da operação."
```

**Padrão para stub de finances** — operações placeholder para Phase 7+:
```yaml
domain: finances
operations:
  - name: list_accounts
    method: GET
    path: /finances/account
    description: "Lista contas bancárias da família autenticada."
```

---

### `scripts/generate_code.py` (utility/generator, transform)

**Análogo:** `scripts/generate_code.py` (existente — modificação incremental)

**Função `map_type_to_python`** (linhas 50-75) — extensão necessária:
```python
# scripts/generate_code.py linhas 59-75 — tipo_map atual
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
    # ADICIONAR (D-01):
    # "decimal": "Decimal",
}
```

**Função `get_field_definition`** (linhas 78-115) — ramificação para Decimal:
```python
# scripts/generate_code.py linhas 78-115 — padrão de get_field_definition
def get_field_definition(field: dict[str, Any], force_optional: bool = False) -> str:
    fname = field["name"]
    ftype = map_type_to_python(field["type"])
    is_nullable = field.get("nullable", True)
    # ... lógica existente ...
    field_args: list[str] = []
    if field.get("primary_key"):
        field_args.append("primary_key=True")
    if field.get("foreign_key"):
        field_args.append(f"foreign_key={field['foreign_key']!r}")
    if field.get("unique"):
        field_args.append("unique=True")
    # ...
    return f"    {fname}: {type_str} = Field({', '.join(field_args)})"
    # MODIFICAR: quando ftype == "Decimal", retornar:
    #   f"    {fname}: {type_str} = Field(sa_column=Column(Numeric(15, 2), {nullable_kw}))"
```

**Constante `DOMAIN_TO_ENTITY_NAME`** (linhas 32-37) — adicionar entry:
```python
# scripts/generate_code.py linhas 32-37
DOMAIN_TO_ENTITY_NAME: dict[str, str] = {
    "user": "User",
    "users": "User",
    "family": "Family",
    "families": "Family",
    # ADICIONAR (D-01/Pattern 4):
    # "finances": "Account",
}
```

**Função `_run_ruff_fix`** (linhas 909-929) — descoberta dinâmica:
```python
# scripts/generate_code.py linhas 909-929 — hardcoded atual
def _run_ruff_fix(src_dir: Path) -> None:
    import subprocess
    dirs = [
        str(src_dir / d)
        for d in ("user", "family", "users", "families")  # ← BUG: hardcoded
        if (src_dir / d).exists()
    ]
    # MODIFICAR para descoberta dinâmica:
    # dirs = [
    #     str(d)
    #     for d in src_dir.iterdir()
    #     if d.is_dir()
    #     and not d.name.startswith("_")
    #     and d.name not in ("shared", "core")
    # ]
```

**Nova função `_build_table_args`** — sem análogo existente (padrão derivado de RESEARCH.md):
```python
# Novo helper a inserir em scripts/generate_code.py
# Emite __table_args__ com Index para entidades com bloco filters:
def _build_table_args(entity_data: dict[str, Any]) -> str | None:
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
```

**Ponto de injeção de `__table_args__`** — dentro de `generate_models` (linha 279):
```python
# scripts/generate_code.py linha 279 — logo após __tablename__
code += f'    __tablename__ = "{table_name}"\n\n'
# ADICIONAR após essa linha:
# table_args = _build_table_args(entity_data)
# if table_args:
#     code += table_args + "\n"
```

**Import de `Index` e `Numeric` nos modelos gerados** — dentro de `generate_models` / `_consolidate_models`:
```python
# scripts/generate_code.py linhas 248-265 — bloco de imports gerados
# Padrão existente para needs_uuid, needs_datetime:
needs_uuid = any(...)
needs_datetime = any(...)
# ADICIONAR:
# needs_decimal = any(f.get("type", "").lower() == "decimal" for f in fields)
# needs_table_args = bool(entity_data.get("filters"))
# → emite: from decimal import Decimal
# → emite: from sqlalchemy import Column, Index, Numeric
```

---

### `alembic/env.py` (config/migration, batch)

**Análogo:** `alembic/env.py` (existente, linhas 1-94)

**Padrão de imports atual** (linhas 19-29):
```python
# alembic/env.py linhas 19-29 — estado atual
from sqlmodel import SQLModel  # noqa: E402

from caramello.core.config import settings  # noqa: E402
from caramello.families.models import (  # noqa: E402, F401
    Family,
    FamilyInvitation,
    FamilyMember,
)
from caramello.users.models import User  # noqa: E402, F401

target_metadata = SQLModel.metadata
```

**Modificação necessária — naming_convention ANTES dos imports de modelo** (D-11/Pitfall 6):
```python
# alembic/env.py — ordem obrigatória após modificação
from sqlmodel import SQLModel  # noqa: E402

# naming_convention DEVE ser definida antes de qualquer import de modelo
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Imports de modelos DEPOIS da naming_convention
from caramello.core.config import settings  # noqa: E402
from caramello.families.models import (  # noqa: E402, F401
    Family, FamilyInvitation, FamilyMember,
)
from caramello.users.models import User  # noqa: E402, F401
from caramello.finances.models import (  # noqa: E402, F401  ← NOVO
    Account, Category, FinancialEntry, Movement, Subcategory,
)
```

---

### `alembic/versions/0002_finances_schema.py` (migration, batch)

**Análogo:** `alembic/versions/0001_initial_schema.py` (linhas 1-98)

**Estrutura do arquivo de migration** (linhas 1-25):
```python
# alembic/versions/0001_initial_schema.py linhas 1-25
"""initial_schema

Schema inicial do domínio família — ...

Revision ID: 0001
Revises:
Create Date: 2026-05-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Padrão de `upgrade`** com tipos, constraints e FKs (linhas 26-90):
```python
# alembic/versions/0001_initial_schema.py linhas 43-90
def upgrade() -> None:
    op.create_table(
        "family",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
    op.create_table(
        "family_invitation",
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    )
```

**Padrão de `downgrade`** — ordem reversa de drop (linhas 93-98):
```python
# alembic/versions/0001_initial_schema.py linhas 93-98
def downgrade() -> None:
    op.drop_table("family_invitation")
    op.drop_table("family_member")
    op.drop_table("family")
    op.drop_table("user")
```

**Campo `down_revision` para 0002:**
```python
# O valor correto a ser verificado em 0001_initial_schema.py:
revision: str = "0001"  # ← confirmar esse valor antes de criar 0002

# Em 0002:
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
```

**Tipo NUMERIC para campos monetários** — novo em 0002:
```python
# Coluna amount em migration 0002 (não presente em 0001)
sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
```

**Índices via `op.create_index`** — novo em 0002:
```python
# Padrão para índices emitidos pelo autogenerate (baseado em __table_args__)
op.create_index("ix_account_family_id", "account", ["family_id"], unique=False)
op.create_index(
    "ix_financial_entry_year_month",
    "financial_entry",
    ["competencia_year", "competencia_month"],
    unique=False,
)
# No downgrade correspondente:
op.drop_index("ix_account_family_id", table_name="account")
```

---

### `src/caramello/finances/models.py` (model, CRUD)

**Análogo:** `src/caramello/families/models.py` (linhas 1-117)

**Padrão de imports no models.py gerado** (linhas 1-6):
```python
# src/caramello/families/models.py linhas 1-6
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from caramello.users.models import User
```

**ADICIONAR para finances** (D-01/D-03):
```python
from decimal import Decimal  # ← obrigatório quando há campo Decimal

from sqlalchemy import Column, Index, Numeric  # ← quando há Decimal ou filters:
```

**Padrão de 4 classes por entidade** (linhas 9-75):
```python
# src/caramello/families/models.py linhas 9-75 — padrão das 4 classes
class FamilyMember(SQLModel, table=True):           # TABLE MODEL
    """docstring."""
    __tablename__ = "family_member"
    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    # ...

class FamilyMemberRead(SQLModel):                   # READ MODEL (sem id)
    uuid: UUID
    name: str
    # ...

class FamilyMemberCreate(SQLModel):                 # CREATE MODEL (sem id/uuid/timestamps)
    name: str
    # ...

class FamilyMemberUpdate(SQLModel):                 # UPDATE MODEL (todos Optional)
    name: str | None = None
    # ...
```

**Campo Decimal — emitido pelo gerador** (padrão verificado, sem análogo direto no código existente):
```python
# Padrão a gerar para campos monetários (D-01, verificado localmente)
amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))
```

**`__table_args__` com Index** — emitido pelo gerador para entidades com `filters:`:
```python
# Padrão a gerar quando entidade tem bloco filters: (D-11, verificado localmente)
class FinancialEntry(SQLModel, table=True):
    """..."""
    __tablename__ = "financial_entry"
    __table_args__ = (
        Index("ix_financial_entry_account_id", "account_id"),
        Index("ix_financial_entry_year_month", "competencia_year", "competencia_month"),
    )
    # ... campos ...
```

**Restrição crítica:** `__table_args__` deve ser emitido APENAS na classe com `table=True`, nunca nas classes `Read`/`Create`/`Update`.

---

### `src/caramello/finances/router.py` (controller, request-response)

**Análogo:** `src/caramello/families/router.py` (linhas 1-184)

**Padrão de imports do router gerado** (linhas 1-22):
```python
# src/caramello/families/router.py linhas 1-22
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.families.models import (
    Family, FamilyCreate, FamilyInvitation, FamilyInvitationCreate,
    FamilyInvitationRead, FamilyInvitationUpdate, FamilyRead, FamilyUpdate,
)
from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.users.models import User
```

**Padrão CRUD async** (linhas 24-98):
```python
# src/caramello/families/router.py linhas 24-98
family_router = APIRouter(prefix="/families/family", tags=["Family"])

@family_router.post("/", response_model=FamilyRead)
async def create_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    db_obj = Family.model_validate(family_in)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

@family_router.get("/{uuid}", response_model=FamilyRead)
async def read_family(uuid: UUID, ...) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    family = result.first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family
```

**Router raiz agregador** (linhas 181-184):
```python
# src/caramello/families/router.py linhas 181-184
router = APIRouter()
router.include_router(family_router)
router.include_router(familyinvitation_router)
```

---

### `src/caramello/finances/operations.py` (service/stub, request-response)

**Análogo:** `src/caramello/families/operations.py` (linhas 1-17) — mas o stub inicial

**Padrão de anotação** — primeira linha obrigatória (linha 1):
```python
# src/caramello/families/operations.py linha 1
# CARAMELLO-GENERATED: stub   ← gerador emite isso; nunca editar diretamente
# (quando implementado manualmente, muda para:)
# CARAMELLO-GENERATED: implemented
```

**Padrão do stub gerado por `generate_operations`** (linhas 466-511 de `generate_code.py`):
```python
# CARAMELLO-GENERATED: stub
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.finances.models import Account, AccountRead

router = APIRouter(prefix="/finances", tags=["Account"])


@router.get("/account", response_model=AccountRead)
async def list_accounts(
    current_user: Account = Depends(get_current_user)
) -> Account:
    """Lista contas bancárias da família autenticada."""
    raise NotImplementedError
```

---

### `dsl/schema.yaml` (config/validation)

**Análogo:** `dsl/schema.yaml` (existente, linhas 1-86)

**Padrão de adição de propriedade nova** — inserir em `fields.items.properties`:
```yaml
# Padrão existente para propriedade de campo:
        max_length:
          type: integer
          description: "Maximum length for string type fields."
# ADICIONAR (para documentar Decimal como tipo válido):
# Não requer schema change — `type` já é `type: string` livre.
# ADICIONAR para filters: (nova chave de topo):
  filters:
    type: array
    description: "Filtros naturais da entidade — geram Index no banco."
    items:
      type: object
      properties:
        fields:
          type: array
          items:
            type: string
      required:
        - fields
```

---

### `tests/test_generator.py` (test)

**Análogo:** `tests/test_generator.py` (existente, linhas 1-266)

**Padrão de teste de existência de YAML** (linhas 26-33):
```python
# tests/test_generator.py linhas 26-33
def test_family_yamls_have_domain_field():
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") in ("family", "families"), (
            f"{fname} deve declarar domain: family|families; ..."
        )
```

**Padrão de teste de conteúdo de models.py** (linhas 82-89):
```python
# tests/test_generator.py linhas 82-89
def test_family_models_consolidated():
    models_path = REPO_ROOT / "src/caramello/families/models.py"
    assert models_path.exists()
    content = models_path.read_text()
    assert "class Family(SQLModel, table=True):" in content
```

**Padrão de teste de função do gerador** (linhas 184-229):
```python
# tests/test_generator.py linhas 184-229
def test_router_url_has_domain_prefix_and_hyphens():
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.generate_code import generate_router
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))

    entity_data = {"name": "...", "table_name": "...", "domain": "...", "fields": [...], "relationships": []}
    code = generate_router(entity_data)
    assert "..." in code
```

---

## Padrões Compartilhados

### Autenticação (get_current_user)

**Fonte:** `src/caramello/shared/auth.py`
**Aplicar em:** Todos os handlers de router em `finances/router.py` e `finances/operations.py`
```python
# Padrão em todos os endpoints — capturado de families/router.py linha 30
_: User = Depends(get_current_user)
# (quando é operação autenticada com uso do user atual:)
current_user: User = Depends(get_current_user)
```

### Sessão de Banco Async

**Fonte:** `src/caramello/shared/database.py`
**Aplicar em:** Todos os handlers de router em `finances/router.py` e `finances/operations.py`
```python
# Padrão em todos os endpoints — capturado de families/router.py linha 29
session: AsyncSession = Depends(get_session)
```

### Tratamento de 404

**Fonte:** `src/caramello/families/router.py` (linhas 54-62)
**Aplicar em:** Todos os handlers GET/{uuid} e PATCH/{uuid} e DELETE/{uuid}
```python
# src/caramello/families/router.py linhas 56-61
result = await session.exec(statement)
family = result.first()
if not family:
    raise HTTPException(status_code=404, detail="Family not found")
return family
```

### Convenção de Nomes de Index no Alembic

**Fonte:** `alembic/env.py` (modificação Phase 6) + RESEARCH.md Pattern 3
**Aplicar em:** `alembic/env.py` e indiretamente em todos os `__table_args__` gerados
```python
# Nomenclatura determinística de constraints (deve estar em env.py antes dos imports de modelo)
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

### Anotação CARAMELLO-GENERATED

**Fonte:** `scripts/generate_code.py` (linhas 25-26) + `src/caramello/families/operations.py` (linha 1)
**Aplicar em:** Primeira linha de `src/caramello/finances/operations.py`
```python
ANNOTATION_STUB = "# CARAMELLO-GENERATED: stub"
ANNOTATION_IMPLEMENTED = "# CARAMELLO-GENERATED: implemented"
# O gerador verifica a primeira linha antes de sobrescrever:
# se == ANNOTATION_IMPLEMENTED → pula (não regenera)
```

### Sem `from __future__ import annotations` em models.py

**Fonte:** `scripts/generate_code.py` (linhas 556-561) + comentário em `test_generator.py` (linhas 79-80)
**Aplicar em:** `src/caramello/finances/models.py`
```python
# NUNCA emitir em arquivos de models:
# from __future__ import annotations
# Razão: com from __future__, list["Family"] vira string lazy;
# SQLModel usa get_origin/get_args — get_origin('list["Family"]') == None.
# Sem from __future__, list["Family"] é GenericAlias real e SA resolve via class registry.
```

---

## Sem Análogo Encontrado

| Arquivo | Papel | Fluxo | Razão |
|---------|-------|-------|-------|
| `src/caramello/finances/__init__.py` | config | — | Arquivo vazio criado pelo gerador via `(domain_dir / "__init__.py").touch()` — sem padrão de conteúdo |

---

## Ordem de Execução (Crítica)

A sequência abaixo deve ser respeitada pelo planner (derivada do RESEARCH.md e pitfalls identificados):

1. **Wave 1:** Estender `scripts/generate_code.py` → criar 5 YAMLs em `dsl/entities/` → atualizar `dsl/manifest.yaml` → criar `dsl/operations/finances.yaml` → executar gerador → código em `src/caramello/finances/` é criado
2. **Wave 2:** Adicionar `naming_convention` em `alembic/env.py` (ANTES dos imports de modelo) → adicionar imports de `finances.models` → executar `alembic revision --autogenerate -m "0002_finances_schema"` → verificar `down_revision = "0001"` → executar `alembic upgrade head`
3. **Wave 3:** Executar testes unitários (`uv run pytest tests/test_generator.py -v`) → verificar `alembic downgrade -1` → verificar `alembic upgrade head` novamente

**Anti-padrão crítico a evitar:** Executar `alembic revision --autogenerate` antes de configurar `naming_convention` em `alembic/env.py`.

---

## Metadados

**Escopo de busca:** `/home/claude/work/caramello-api/dsl/`, `/home/claude/work/caramello-api/scripts/`, `/home/claude/work/caramello-api/src/caramello/`, `/home/claude/work/caramello-api/alembic/`, `/home/claude/work/caramello-api/tests/`
**Arquivos escaneados:** 15
**Data do mapeamento:** 2026-05-31
