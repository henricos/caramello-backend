# Phase 4: Domínio Family - Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 13 new/modified files
**Analogs found:** 12 / 13

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `dsl/entities/user.yaml` | config | transform | `dsl/entities/family.yaml` | exact |
| `dsl/entities/family.yaml` | config | transform | `dsl/entities/user.yaml` | exact |
| `dsl/entities/family_member.yaml` | config | transform | `dsl/entities/family.yaml` | exact |
| `dsl/entities/family_invitation.yaml` | config | transform | `dsl/entities/user.yaml` | exact |
| `dsl/operations/family.yaml` | config | request-response | `dsl/operations/user.yaml` | exact |
| `scripts/generate_code.py` | utility | transform | self (modificar) | exact |
| `src/caramello/families/models.py` | model | CRUD | `src/caramello/family/models.py` | exact |
| `src/caramello/families/router.py` | route | request-response | `src/caramello/family/router.py` | exact |
| `src/caramello/families/operations.py` | controller | request-response | `src/caramello/user/operations.py` | exact |
| `src/caramello/users/models.py` | model | CRUD | `src/caramello/user/models.py` (via regeneração) | exact |
| `src/caramello/users/router.py` | route | request-response | `src/caramello/user/router.py` (via regeneração) | exact |
| `src/caramello/shared/auth.py` | middleware | request-response | self (modificar) | exact |
| `src/caramello/main.py` | config | request-response | self (modificar) | exact |
| `alembic/versions/[nova_migration].py` | migration | batch | `alembic/versions/20260524_0138_initial_schema.py` | role-match |
| `tests/test_family_operations.py` | test | request-response | `tests/test_user_operations.py` | exact |
| `tests/test_auth.py` | test | request-response | self (modificar) | exact |
| `tests/test_generator.py` | test | transform | self (modificar) | exact |

---

## Pattern Assignments

### `dsl/entities/user.yaml` e `dsl/entities/family*.yaml` (config, transform)

**Analog:** `dsl/entities/user.yaml` e `dsl/entities/family.yaml` (arquivos atuais)

**Mudança necessária — apenas alterar o campo `domain`:**
```yaml
# dsl/entities/user.yaml — linha 5
# ANTES:
domain: user
# DEPOIS:
domain: users

# dsl/entities/family.yaml, family_member.yaml, family_invitation.yaml — linha correspondente
# ANTES:
domain: family
# DEPOIS:
domain: families
```

**Redesenho de `dsl/entities/family_invitation.yaml` (D-01):**

Campos a remover (linhas 33-38 e 53-55 do arquivo atual):
```yaml
# REMOVER estes campos:
  - name: invitee_email
    type: EmailStr
    nullable: false
    description: "Email of the invited user."

  - name: expires_at
    type: datetime
    nullable: false
    description: "Timestamp of the invitation's expiration."
```

Campos a adicionar (no lugar dos removidos):
```yaml
# ADICIONAR estes campos:
  - name: email
    type: str
    nullable: false
    description: "Email para matching automático no login (pré-registro)."

  - name: status
    type: str
    max_length: 20
    default: "pending_login"
    nullable: false
    description: "Status do pré-registro: pending_login ou joined."
```

---

### `dsl/operations/family.yaml` (config, request-response)

**Analog:** `dsl/operations/user.yaml` (linhas 1-11)

**Estrutura a copiar de `dsl/operations/user.yaml`:**
```yaml
# dsl/operations/user.yaml (linhas 1-11)
# dsl/operations/user.yaml
# Operações de negócio do domínio user.
# Gera src/caramello/user/operations.py (stub que será implementado nesta fase — D-10).

domain: user
operations:
  - name: get_me
    method: GET
    path: /user/me
    description: "Retorna o perfil do usuário autenticado."
```

**Conteúdo completo a criar em `dsl/operations/family.yaml`** (D-07):
```yaml
# dsl/operations/family.yaml
# Operações de negócio do domínio families.
# Gera src/caramello/families/operations.py (stub para implementação manual).

domain: families
operations:
  - name: registry_family
    method: POST
    path: /families/registry
    description: "Cria família e registra o usuário autenticado como owner (role='owner')."

  - name: list_my_families
    method: GET
    path: /families/families
    description: "Lista famílias das quais o usuário autenticado é membro."

  - name: get_family_detail
    method: GET
    path: /families/families/{family_uuid}
    description: "Retorna detalhes de uma família se o usuário for membro."

  - name: pre_register_member
    method: POST
    path: /families/families/{family_uuid}/pre-register
    description: "Owner pré-registra email para adesão automática. Não-owner recebe 403."

  - name: list_members
    method: GET
    path: /families/families/{family_uuid}/members
    description: "Lista membros da família (qualquer membro pode ver)."

  - name: remove_member
    method: DELETE
    path: /families/families/{family_uuid}/members/{user_uuid}
    description: "Remove membro da família (owner only). Não-owner recebe 403."
```

---

### `scripts/generate_code.py` (utility, transform)

**Analog:** self — arquivo existente em `/home/claude/work/caramello-api/scripts/generate_code.py`

**Alteração 1 — `generate_router()`, linha 364 (URL prefix com domain e hifens):**
```python
# ANTES (linha 364):
router = APIRouter(prefix="/{table_name}", tags=["{name}"])

# DEPOIS (inserir url_table_name antes e usar nas duas posições):
url_table_name = table_name.replace("_", "-")
router = APIRouter(prefix="/{domain}/{url_table_name}", tags=["{name}"])
```

**Alteração 2 — `_run_ruff_fix()`, linha 885 (cobrir novos diretórios):**
```python
# ANTES (linha 885):
dirs = [str(src_dir / d) for d in ("user", "family") if (src_dir / d).exists()]

# DEPOIS:
dirs = [str(src_dir / d) for d in ("users", "families") if (src_dir / d).exists()]
```

**Atenção:** `generate_operations()` (linhas 443-483) usa `domain.title()` para derivar o nome da classe, produzindo `Families` (não existente). O stub gerado para `families/operations.py` precisará de imports corrigidos manualmente antes de implementar. Isso é esperado — a anotação `stub` permite sobrescrever.

---

### `src/caramello/families/models.py` (model, CRUD)

**Analog:** `src/caramello/family/models.py` (gerado via DSL após redesenho dos YAMLs)

**Padrão de modelo com tabela — copiar de `src/caramello/family/models.py` linhas 30-50:**
```python
# src/caramello/family/models.py linhas 30-50
class Family(SQLModel, table=True):
    """Represents a family group in the system."""

    __tablename__ = "family"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    name: str = Field(max_length=100, nullable=False)
    description: str | None = Field(max_length=255, default=None)
    status: str = Field(max_length=20, default="active", nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
```

**Padrão de link model — copiar de `src/caramello/family/models.py` linhas 10-28:**
```python
# src/caramello/family/models.py linhas 10-28
class FamilyMember(SQLModel, table=True):
    __tablename__ = "family_member"

    user_id: int | None = Field(primary_key=True, foreign_key="user.id", default=None)
    family_id: int | None = Field(
        primary_key=True, foreign_key="family.id", default=None
    )
    role: str = Field(max_length=20, default="member", nullable=False)
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
```

**FamilyInvitation redesenhado (D-01) — campos novos `email` + `status`, sem `invitee_email`/`expires_at`:**
```python
# Estrutura alvo após redesenho — gerada pelo generator após atualizar YAML
class FamilyInvitation(SQLModel, table=True):
    __tablename__ = "family_invitation"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: int = Field(foreign_key="family.id", nullable=False)
    inviter_id: int = Field(foreign_key="user.id", nullable=False)
    email: str = Field(nullable=False)           # novo — substitui invitee_email
    status: str = Field(                          # novo default — era "pending"
        max_length=20, default="pending_login", nullable=False
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    # expires_at REMOVIDO
```

---

### `src/caramello/families/router.py` (route, request-response)

**Analog:** `src/caramello/family/router.py` (gerado via DSL)

**Padrão de CRUD handler — copiar de `src/caramello/family/router.py` linhas 1-98:**

Imports padrão (linhas 1-22):
```python
# src/caramello/family/router.py linhas 1-22
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.family.models import (
    Family,
    FamilyCreate,
    FamilyInvitation,
    FamilyInvitationCreate,
    FamilyInvitationRead,
    FamilyInvitationUpdate,
    FamilyRead,
    FamilyUpdate,
)
from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.user.models import User
```

Padrão de handler GET único com 404 (linhas 50-62):
```python
# src/caramello/family/router.py linhas 50-62
@family_router.get("/{uuid}", response_model=FamilyRead)
async def read_family(
    uuid: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    family = result.first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family
```

Padrão de PATCH com `model_dump(exclude_unset=True)` (linhas 64-82):
```python
# src/caramello/family/router.py linhas 64-82
@family_router.patch("/{uuid}", response_model=FamilyRead)
async def update_family(
    uuid: UUID,
    family_in: FamilyUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
) -> Family:
    statement = select(Family).where(Family.uuid == uuid)
    result = await session.exec(statement)
    db_obj = result.first()
    if not db_obj:
        raise HTTPException(status_code=404, detail="Family not found")
    update_data = family_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
```

Padrão de aggregator router (linhas 181-183):
```python
# src/caramello/family/router.py linhas 181-183
router = APIRouter()
router.include_router(family_router)
router.include_router(familyinvitation_router)
```

**Mudança de URL após refatoração:** prefixos mudam de `"/family"` e `"/family_invitation"` para `"/families/family"` e `"/families/family-invitation"` (produzidos automaticamente pelo generator com as alterações de D-09/D-10).

---

### `src/caramello/families/operations.py` (controller, request-response)

**Analog:** `src/caramello/user/operations.py` (arquivo completo, 15 linhas)

**Padrão de cabeçalho com anotação e APIRouter próprio — copiar de `src/caramello/user/operations.py` linhas 1-15:**
```python
# src/caramello/user/operations.py linhas 1-15
# CARAMELLO-GENERATED: implemented
from __future__ import annotations

from fastapi import APIRouter, Depends

from caramello.shared.auth import get_current_user
from caramello.user.models import User, UserRead

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Retorna o perfil do usuário autenticado."""
    return current_user
```

**Padrão de imports expandido para `families/operations.py`** (após stub gerado + correção manual):
```python
# CARAMELLO-GENERATED: implemented   ← alterar de stub para implemented ANTES de rodar generator
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.users.models import User
from caramello.families.models import (
    Family, FamilyCreate, FamilyMember, FamilyInvitation,
    FamilyRead, FamilyMember,
)

router = APIRouter(prefix="/families", tags=["Family"])
```

**Padrão de verificação de ownership (a extrair como helper privado):**
```python
# Padrão a usar antes de toda operação restrita a owner
async def _require_owner(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> FamilyMember:
    result = await session.exec(
        select(FamilyMember)
        .join(Family, FamilyMember.family_id == Family.id)
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
            FamilyMember.role == "owner",
        )
    )
    member = result.first()
    if not member:
        raise HTTPException(status_code=403, detail="Apenas owner pode realizar esta operação")
    return member
```

**Padrão de transação atômica Family + FamilyMember (FAMILY-01):**
```python
# Padrão: session.flush() para obter id antes do commit
@router.post("/registry", response_model=FamilyRead)
async def registry_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Family:
    db_family = Family.model_validate(family_in)
    session.add(db_family)
    await session.flush()          # obtém db_family.id sem commit
    member = FamilyMember(
        user_id=current_user.id,
        family_id=db_family.id,
        role="owner",
    )
    session.add(member)
    await session.commit()
    await session.refresh(db_family)
    return db_family
```

**Padrão de listagem com JOIN (FAMILY-02):**
```python
# Padrão: select com join e where por user_id
@router.get("/families", response_model=list[FamilyRead])
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[Family]:
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == current_user.id)
    )
    return list(result.all())
```

---

### `src/caramello/shared/auth.py` (middleware, request-response)

**Analog:** self — arquivo existente em `/home/claude/work/caramello-api/src/caramello/shared/auth.py`

**Padrão de import lazy com TYPE_CHECKING (linhas 36-37 — já estabelecido para User):**
```python
# src/caramello/shared/auth.py linhas 36-37
if TYPE_CHECKING:
    from caramello.user.models import User
```

**Padrão de import lazy dentro do corpo da função (linha 115):**
```python
# src/caramello/shared/auth.py linha 115
# Import lazy do User para evitar import circular
from caramello.user.models import User
```

**Extensão para auto-join (D-02) — inserir após linha 188 (após SELECT do user):**
```python
# Inserir após: result = await session.exec(select(User).where(User.idp_sub == idp_sub))
# AUTO-JOIN: verificar FamilyInvitation pendente pelo email do token
# Import lazy para evitar circular (mesma estratégia do import de User acima)
from caramello.families.models import FamilyInvitation, FamilyMember  # noqa: PLC0415

inv_result = await session.exec(
    select(FamilyInvitation).where(
        FamilyInvitation.email == email,
        FamilyInvitation.status == "pending_login",
    )
)
pending_inv = inv_result.first()
if pending_inv:
    new_member = FamilyMember(
        user_id=user.id,
        family_id=pending_inv.family_id,
        role="member",
    )
    session.add(new_member)
    pending_inv.status = "joined"
    session.add(pending_inv)
    await session.commit()
```

**Padrão de pg_insert para inserção atômica (linhas 179-184 — base para FamilyMember se flush não funcionar):**
```python
# src/caramello/shared/auth.py linhas 179-184
insert_stmt = (
    pg_insert(User.__table__)  # type: ignore[attr-defined]
    .values(idp_sub=idp_sub, email=email, name=name)
    .on_conflict_do_nothing(index_elements=["idp_sub"])
)
await session.execute(insert_stmt)
await session.commit()
```

---

### `src/caramello/main.py` (config, request-response)

**Analog:** self — arquivo existente em `/home/claude/work/caramello-api/src/caramello/main.py`

**Padrão atual de imports e registro de routers (linhas 20-54):**
```python
# src/caramello/main.py linhas 20-54
from caramello.shared.auth import fetch_jwks
from caramello.user import operations as user_operations
from caramello.user import router as user_router
from caramello.family import router as family_router  # noqa: E402

# [...]

# IMPORTANTE: user_operations deve ser registrado ANTES de user_router para que
# rotas estáticas como GET /user/me tenham prioridade sobre GET /user/{uuid}.
# FastAPI faz correspondência em ordem de registro; rotas estáticas devem vir
# antes das rotas com parâmetro para evitar que /user/me seja interpretado como uuid.
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(family_router.router)
```

**Imports atualizados após renomear diretórios:**
```python
# ANTES (linhas 20-22):
from caramello.user import operations as user_operations
from caramello.user import router as user_router
from caramello.family import router as family_router

# DEPOIS:
from caramello.users import operations as user_operations
from caramello.users import router as user_router
from caramello.families import operations as families_operations
from caramello.families import router as families_router
```

**Ordem de registro atualizada (D-06 — operations ANTES do CRUD):**
```python
# DEPOIS — families_operations antes de families_router (mesmo princípio das linhas 49-54)
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)   # /families/registry etc. — ANTES
app.include_router(families_router.router)       # /families/family/{uuid} etc. — DEPOIS
```

---

### `alembic/versions/[nova_migration].py` (migration, batch)

**Analog:** `alembic/versions/20260524_0138_initial_schema.py`

**Padrão de cabeçalho de migration — copiar de linhas 1-26:**
```python
# alembic/versions/20260524_0138_initial_schema.py linhas 1-26
"""initial_schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-24 01:38:00.000000
...
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**Schema atual de `family_invitation` (para referência na migration — linhas 60-73 do migration existente):**
```python
# alembic/versions/20260524_0138_initial_schema.py linhas 60-73
op.create_table('family_invitation',
sa.Column('id', sa.Integer(), nullable=False),
sa.Column('uuid', sa.Uuid(), nullable=False),
sa.Column('family_id', sa.Integer(), nullable=False),
sa.Column('inviter_id', sa.Integer(), nullable=False),
sa.Column('invitee_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
# ...
)
```

**Padrão de upgrade/downgrade da nova migration (D-01):**
```python
def upgrade() -> None:
    op.drop_column("family_invitation", "invitee_email")
    op.drop_column("family_invitation", "expires_at")
    op.add_column(
        "family_invitation",
        sa.Column("email", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "family_invitation",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending_login"),
    )
    # Remover server_default após popular colunas (evita constraint permanente)
    op.alter_column("family_invitation", "email", server_default=None)
    op.alter_column("family_invitation", "status", server_default=None)

def downgrade() -> None:
    op.drop_column("family_invitation", "email")
    op.drop_column("family_invitation", "status")
    op.add_column("family_invitation", sa.Column("invitee_email", sa.String(), nullable=False, server_default=""))
    op.add_column("family_invitation", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.alter_column("family_invitation", "invitee_email", server_default=None)
    op.alter_column("family_invitation", "expires_at", server_default=None)
```

---

### `tests/test_family_operations.py` (test, request-response)

**Analog:** `tests/test_user_operations.py` (arquivo completo, 58 linhas)

**Padrão de `dependency_overrides` para mock de `get_current_user` — copiar de `tests/test_user_operations.py` linhas 9-46:**
```python
# tests/test_user_operations.py linhas 9-46
def test_get_me_returns_user_fields():
    from datetime import datetime, timezone
    from uuid import uuid4

    from caramello.shared.auth import get_current_user
    from caramello.user.models import User
    from fastapi.testclient import TestClient

    from caramello.main import app

    fake_user = User(
        id=42,
        uuid=uuid4(),
        idp_sub="fake-keycloak-sub",
        email="user@example.com",
        name="Usuario Teste",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    def _override():
        return fake_user

    app.dependency_overrides[get_current_user] = _override
    try:
        client = TestClient(app)
        response = client.get("/user/me")
        assert response.status_code == 200, response.text
        # ...
    finally:
        app.dependency_overrides.clear()
```

**Padrão de teste de anotação — copiar de `tests/test_user_operations.py` linhas 49-58:**
```python
# tests/test_user_operations.py linhas 49-58
def test_operations_annotation_is_implemented():
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    ops_path = repo_root / "src/caramello/user/operations.py"
    first_line = ops_path.read_text().splitlines()[0].strip()
    assert first_line == "# CARAMELLO-GENERATED: implemented", (
        f"Anotação deve ser 'implemented' após Wave 4; foi: {first_line!r}"
    )
```

**Estrutura dos testes novos para `test_family_operations.py` (mock de session + override):**
```python
# Padrão para testes que precisam mockar session (FAMILY-01, 02, 03, 07):
# 1. Criar fake_user via User(id=..., uuid=..., ...)
# 2. Mockar get_session para retornar AsyncMock com exec/add/commit/refresh
# 3. app.dependency_overrides[get_current_user] = lambda: fake_user
# 4. app.dependency_overrides[get_session] = lambda: mock_session
# 5. TestClient(app).post/get/delete(...)
# 6. finally: app.dependency_overrides.clear()
```

---

### `tests/test_generator.py` (test, transform) — adições

**Analog:** self — arquivo existente `tests/test_generator.py`

**Padrão de teste de campo YAML — copiar linhas 18-32:**
```python
# tests/test_generator.py linhas 18-32
def test_user_yaml_has_domain_field():
    """Wave 1 (Plan 02): dsl/entities/user.yaml contém `domain: user`."""
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") == "user", (
        f"user.yaml deve declarar domain: user; encontrado: {data.get('domain')!r}"
    )
```

**Novos testes a adicionar:**
```python
# Testar que domain foi atualizado para plural
def test_user_yaml_domain_is_users():
    data = yaml.safe_load((DSL_ENTITIES_DIR / "user.yaml").read_text())
    assert data.get("domain") == "users"

def test_family_yamls_domain_is_families():
    for fname in ("family.yaml", "family_member.yaml", "family_invitation.yaml"):
        data = yaml.safe_load((DSL_ENTITIES_DIR / fname).read_text())
        assert data.get("domain") == "families"

# Testar que o generator emite URL com domain prefix e hifens
def test_router_url_has_domain_prefix_and_hyphens():
    from scripts.generate_code import generate_router
    entity_data = {
        "name": "FamilyInvitation",
        "table_name": "family_invitation",
        "domain": "families",
        "fields": [],
        "relationships": [],
    }
    code = generate_router(entity_data)
    assert 'prefix="/families/family-invitation"' in code
```

---

## Shared Patterns

### Auth Guard (`Depends(get_current_user)`)
**Source:** `src/caramello/shared/auth.py` — função `get_current_user`
**Aplicar a:** todos os endpoints em `families/operations.py`, `families/router.py`, `users/router.py`
```python
# Padrão de uso em qualquer endpoint protegido
from caramello.shared.auth import get_current_user
from caramello.users.models import User

@router.get("/algum-endpoint")
async def algum_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ...:
    ...
```

### AsyncSession via Depends
**Source:** `src/caramello/shared/database.py` — função `get_session`
**Aplicar a:** todos os endpoints de `families/operations.py` e `families/router.py`
```python
from caramello.shared.database import get_session
from sqlmodel.ext.asyncio.session import AsyncSession

# Em qualquer handler com acesso ao banco:
session: AsyncSession = Depends(get_session)
```

### Erro 404 padrão
**Source:** `src/caramello/family/router.py` linhas 57-61
**Aplicar a:** todos os GET/{uuid} em `families/router.py`
```python
if not family:
    raise HTTPException(status_code=404, detail="Family not found")
```

### Erro 403 para operações restritas (novo padrão — Phase 4)
**Source:** padrão a estabelecer em `families/operations.py`
**Aplicar a:** `POST /families/families/{uuid}/pre-register` e `DELETE .../members/{user_uuid}`
```python
raise HTTPException(status_code=403, detail="Apenas owner pode realizar esta operação")
```

### Import order em `main.py`
**Source:** `src/caramello/main.py` linhas 47-54 (comentário e `include_router`)
**Aplicar a:** registro de `families_operations.router` — deve vir ANTES de `families_router.router`
```python
# Rotas estáticas (operations) ANTES de rotas com parâmetro (CRUD)
app.include_router(families_operations.router)
app.include_router(families_router.router)
```

### Anotação CARAMELLO-GENERATED
**Source:** `src/caramello/user/operations.py` linha 1
**Aplicar a:** `src/caramello/families/operations.py` — alterar de `stub` para `implemented` imediatamente após implementar
```python
# CARAMELLO-GENERATED: implemented  ← linha 1 obrigatória após implementação
```

---

## No Analog Found

Nenhum arquivo desta fase está completamente sem analog. O arquivo mais distante do padrão existente é `src/caramello/families/operations.py` na parte de operações de negócio com JOIN e verificação de ownership — esses padrões específicos não existem ainda no codebase, mas o scaffold/boilerplate vem de `src/caramello/user/operations.py` e os padrões de query vêm dos `Code Examples` em `04-RESEARCH.md`.

---

## Metadata

**Analog search scope:** `src/caramello/`, `dsl/`, `tests/`, `scripts/`, `alembic/`
**Files scanned:** 19
**Pattern extraction date:** 2026-05-26
