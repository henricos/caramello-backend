# Phase 7: CRUD Account + Category — Pattern Map

**Mapped:** 2026-06-01
**Files analyzed:** 4 (3 modified, 1 new)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/caramello/finances/operations.py` | service + controller | CRUD + request-response | `src/caramello/families/operations.py` | exact |
| `src/caramello/shared/auth.py` | middleware/utility | request-response | `src/caramello/shared/auth.py` (extensão) | self-extension |
| `src/caramello/main.py` | config/entrypoint | — | `src/caramello/main.py` (extensão) | self-extension |
| `tests/test_finances_operations.py` | test | CRUD | `tests/test_family_operations.py` | exact |

---

## Pattern Assignments

### `src/caramello/finances/operations.py` (service + controller, CRUD)

**Analog:** `src/caramello/families/operations.py`

**Cabeçalho e imports pattern** (linhas 1-40 do analog):
```python
# CARAMELLO-GENERATED: implemented
"""Operações de negócio do domínio finances — Phase 7.

Cobre:
  - ACC-01/02/03: CRUD de Account scoped por família
  - CAT-01/02/04: CRUD de Category e Subcategory scoped por família
  - AUTH-FIN-01/02: 401/403 via get_current_user + _require_family_access
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.finances.models import Account, Category, Subcategory
from caramello.families.models import Family
from caramello.shared.auth import get_current_user, _require_family_access
from caramello.shared.database import get_session
from caramello.users.models import User

router = APIRouter(prefix="/finances", tags=["Finances"])
```

**Schemas públicos locais pattern** (linhas 44-61 do analog — `PreRegisterBody`, `FamilyMemberRead`):
```python
# Schemas locais — NÃO usam os schemas gerados (AccountRead, CategoryRead)
# porque esses expõem family_id interno. Schemas *Public usam UUIDs públicos.

class AccountCreatePublic(BaseModel):
    family_uuid: UUID
    name: str
    type: Literal["corrente", "poupanca", "cartao", "investimento"]
    currency: str = "BRL"

class AccountReadPublic(BaseModel):
    uuid: UUID
    family_uuid: UUID
    name: str
    type: str
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class AccountUpdatePublic(BaseModel):
    name: str | None = None
    type: Literal["corrente", "poupanca", "cartao", "investimento"] | None = None
    currency: str | None = None
    is_active: bool | None = None

class CategoryCreatePublic(BaseModel):
    family_uuid: UUID
    name: str

class CategoryReadPublic(BaseModel):
    uuid: UUID
    family_uuid: UUID
    name: str
    created_at: datetime
    updated_at: datetime

class CategoryUpdatePublic(BaseModel):
    name: str | None = None

class SubcategoryCreatePublic(BaseModel):
    category_uuid: UUID
    name: str

class SubcategoryReadPublic(BaseModel):
    uuid: UUID
    category_uuid: UUID
    name: str
    created_at: datetime
    updated_at: datetime

class SubcategoryUpdatePublic(BaseModel):
    name: str | None = None
```

**Helper de acesso — pattern `_require_member`** (linhas 95-118 do analog):
```python
# families/operations.py linhas 95-118 — _require_member como referência de assinatura
async def _require_member(
    family_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> Family:
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(
            Family.uuid == family_uuid,
            FamilyMember.user_id == current_user.id,
        )
    )
    family = result.first()
    if family is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não é membro desta família",
        )
    return family
```

**Core pattern — POST com resolução UUID → ID** (linhas 126-153 do analog — `registry_family`):
```python
# Padrão de resolução family_uuid → family_id para Account.
# Baseado em como families/operations.py resolve e persiste com ID interno.
@router.post("/accounts", response_model=AccountReadPublic, status_code=201)
async def create_account(
    account_in: AccountCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    # 1. Resolver UUID público → objeto ORM
    family_result = await session.exec(
        select(Family).where(Family.uuid == account_in.family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    # 2. Verificar membership (403 se não-membro)
    await _require_family_access(family.id, current_user, session)

    # 3. Persistir com ID interno (nunca com UUID)
    db_account = Account(
        family_id=family.id,
        name=account_in.name,
        type=account_in.type,
        currency=account_in.currency,
    )
    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)

    # 4. Retornar schema público (sem id, sem family_id)
    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=account_in.family_uuid,
        name=db_account.name,
        type=db_account.type,
        currency=db_account.currency,
        is_active=db_account.is_active,
        created_at=db_account.created_at,
        updated_at=db_account.updated_at,
    )
```

**Core pattern — GET com JOIN para obter UUID do pai** (linhas 160-173 do analog — `list_my_families`):
```python
# Padrão de listagem com family_uuid como query param obrigatório.
# Após resolver family → verificar membership → filtrar por family.id.
@router.get("/accounts", response_model=list[AccountReadPublic])
async def list_accounts(
    family_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[AccountReadPublic]:
    family_result = await session.exec(
        select(Family).where(Family.uuid == family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")
    await _require_family_access(family.id, current_user, session)

    accounts_result = await session.exec(
        select(Account).where(Account.family_id == family.id)
    )
    accounts = list(accounts_result.all())
    return [
        AccountReadPublic(
            uuid=a.uuid,
            family_uuid=family_uuid,
            name=a.name,
            type=a.type,
            currency=a.currency,
            is_active=a.is_active,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in accounts
    ]
```

**Core pattern — PATCH com `updated_at` manual** (linhas 260-293 do analog — `remove_member` como referência de lookup por UUID):
```python
# Padrão PATCH: lookup por uuid público → verificar acesso → aplicar campos opcionais.
# ATENÇÃO: updated_at deve ser definido manualmente (Pitfall 4 — sem onupdate automático).
@router.patch("/accounts/{account_uuid}", response_model=AccountReadPublic)
async def update_account(
    account_uuid: UUID,
    account_in: AccountUpdatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    # Lookup por UUID público
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Resolver family para obter UUID e verificar acesso
    family_result = await session.exec(
        select(Family).where(Family.id == db_account.family_id)
    )
    family = family_result.first()
    await _require_family_access(db_account.family_id, current_user, session)

    # Aplicar apenas campos fornecidos (exclude_unset)
    update_data = account_in.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(db_account, key, value)
    # Pitfall 4: updated_at não tem onupdate automático — definir manualmente
    db_account.updated_at = datetime.now(timezone.utc)

    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)
    return AccountReadPublic(
        uuid=db_account.uuid,
        family_uuid=family.uuid,
        ...
    )
```

**Core pattern — GET detail por UUID** (linhas 181-188 do analog — `get_family_detail`):
```python
# Padrão GET /{uuid}: lookup → verificar acesso → retornar schema público.
@router.get("/accounts/{account_uuid}", response_model=AccountReadPublic)
async def get_account(
    account_uuid: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    result = await session.exec(select(Account).where(Account.uuid == account_uuid))
    db_account = result.first()
    if db_account is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    family_result = await session.exec(
        select(Family).where(Family.id == db_account.family_id)
    )
    family = family_result.first()
    await _require_family_access(db_account.family_id, current_user, session)

    return AccountReadPublic(uuid=db_account.uuid, family_uuid=family.uuid, ...)
```

---

### `src/caramello/shared/auth.py` — extensão com `_require_family_access`

**Analog:** `src/caramello/shared/auth.py` (auto-extensão)

**Import lazy pattern para evitar ciclo** (linhas 201-205 do arquivo existente):
```python
# shared/auth.py linhas 201-205 — padrão de import lazy já estabelecido
# Import lazy para evitar ciclo entre shared/ e families/ (pitfall #3 RESEARCH.md).
from caramello.families.models import (  # noqa: PLC0415
    FamilyInvitation,
    FamilyMember,
)
```

**Assinatura do novo helper — derivado de `get_current_user`** (linha 95 como referência de estilo):
```python
# Novo helper — inserir APÓS as funções existentes (fetch_jwks, get_current_user)
# Segue o estilo de get_current_user: async def, recebe session, levanta HTTPException.
async def _require_family_access(
    family_id: int,
    current_user: "User",
    session: AsyncSession,
) -> None:
    """Verifica que current_user é membro de family_id. Levanta 403 se não for.

    Import lazy de FamilyMember para evitar ciclo shared/ ↔ families/
    (mesmo padrão de get_current_user, linhas 201-205).

    Reutilizável nas Phases 7, 8 e 9.
    """
    from caramello.families.models import FamilyMember  # noqa: PLC0415

    result = await session.exec(
        select(FamilyMember).where(
            FamilyMember.family_id == family_id,
            FamilyMember.user_id == current_user.id,
        )
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não é membro desta família",
        )
```

**Nota:** `select` e `AsyncSession` já importados no topo de `shared/auth.py` (linhas 29-32). Verificar se `status` também já está importado — sim, linha 27.

---

### `src/caramello/main.py` — registro do finances router

**Analog:** `src/caramello/main.py` (auto-extensão)

**Pattern de import e registro de router** (linhas 24-58 do arquivo existente):
```python
# main.py linhas 24-25 — padrão de import de operations
from caramello.families import operations as families_operations  # noqa: E402
from caramello.families import router as families_router  # noqa: E402

# Adicionar import do finances/operations (NÃO finances/router — D-01):
from caramello.finances import operations as finances_operations  # noqa: E402
```

**Ponto de inserção do `include_router`** (linhas 55-58 e comentário na linha 60):
```python
# main.py linhas 55-58 — registrar finances ANTES de mcp.mount_http()
app.include_router(user_operations.router)
app.include_router(user_router.router)
app.include_router(families_operations.router)
app.include_router(families_router.router)
app.include_router(finances_operations.router)  # ← adicionar aqui (antes do MCP)

# MCP — montar DEPOIS de todos os include_router. (linhas 60-71)
mcp = FastApiMCP(...)
mcp.mount_http()
```

**Pitfall P7 (linhas 60-61 do arquivo existente — comentário sobre MCP):**
```python
# MCP — montar DEPOIS de todos os include_router. Routers registrados após
# mount_http() não aparecem como ferramentas (RESEARCH.md Pitfall 2).
```

---

### `tests/test_finances_operations.py` (test, CRUD)

**Analog:** `tests/test_family_operations.py`

**Helper `_make_fake_user`** (linhas 22-36 do analog):
```python
# Copiar _make_fake_user diretamente do analog — idêntico
def _make_fake_user(user_id: int = 42):
    """Constrói User válido — importa lazy."""
    try:
        from caramello.users.models import User
    except ModuleNotFoundError:
        from caramello.user.models import User
    return User(
        id=user_id,
        uuid=uuid4(),
        idp_sub=f"fake-sub-{user_id}",
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
```

**Padrão de mock de sessão** (linhas 107-132 do analog — `test_registry_creates_family_and_owner`):
```python
# Padrão de mock usado em TODOS os testes — copiar e adaptar por teste
async def _exec(_stmt):
    r = MagicMock()
    r.first.return_value = None   # ajustar por teste (ex: retornar Family/Account mock)
    r.all.return_value = []
    return r

mock_session = AsyncMock()
mock_session.exec.side_effect = _exec
mock_session.add = MagicMock(side_effect=lambda o: added.append(o))  # se precisar rastrear adds
mock_session.flush = AsyncMock()
mock_session.commit = AsyncMock()
mock_session.refresh = AsyncMock()
mock_session.execute = AsyncMock()

def _session_override():
    yield mock_session
```

**Padrão de override de dependências e TestClient** (linhas 135-155 do analog):
```python
# Padrão de override + TestClient SEM context manager (evita lifespan/fetch_jwks)
app.dependency_overrides[get_current_user] = lambda: fake_user
app.dependency_overrides[get_session] = _session_override
try:
    client = TestClient(app)
    response = client.post("/finances/accounts", json={...})
    assert response.status_code == 201, response.text
    # assertions sobre o body e sobre objetos adicionados
finally:
    app.dependency_overrides.clear()
```

**Padrão de `pytest.importorskip`** (linhas 39-41 e 71 do analog):
```python
# Cada teste começa com importorskip — padrão obrigatório
def test_finances_module_exists():
    pytest.importorskip("caramello.finances.operations")

def test_create_account_returns_uuid():
    pytest.importorskip("caramello.finances.operations")
    # ...
```

**Padrão para teste de 403 (non-member)** (linhas 206-238 do analog — `test_get_family_detail_non_member_returns_403`):
```python
# Para simular non-member: _exec retorna first()=None em todas as queries
async def _exec(_stmt):
    r = MagicMock()
    r.first.return_value = None   # FamilyMember não encontrado → 403
    r.all.return_value = []
    return r
```

**Padrão para teste de router paths** (linhas 61-87 do analog):
```python
def test_finances_router_paths():
    """Verifica que as rotas esperadas existem no router."""
    ops_mod = pytest.importorskip("caramello.finances.operations")
    router = ops_mod.router
    paths = {getattr(r, "path", None) for r in router.routes}
    expected = {
        "/finances/accounts",
        "/finances/accounts/{account_uuid}",
        "/finances/categories",
        "/finances/categories/{category_uuid}",
        "/finances/subcategory",
        "/finances/subcategory/{subcategory_uuid}",
    }
    missing = expected - paths
    assert not missing, f"Paths faltando: {missing}. Encontrados: {paths}"
```

---

## Shared Patterns

### Autenticação — Bearer token obrigatório
**Fonte:** `src/caramello/shared/auth.py` linha 50 + linhas 95-98
**Aplicar a:** todos os endpoints de `finances/operations.py`
```python
# Injetar em TODOS os handlers de finances/operations.py
current_user: User = Depends(get_current_user)
```
`HTTPBearer(auto_error=True)` retorna **403** (não 401) para token ausente — comportamento documentado e esperado neste projeto (ver `test_auth.py::test_me_unauthenticated`).

### Controle de acesso por família (403)
**Fonte:** `src/caramello/families/operations.py` linhas 95-118 (`_require_member`)
**Aplicar a:** todos os endpoints de Account, Category e Subcategory
```python
# Após resolver family_uuid → family.id:
await _require_family_access(family.id, current_user, session)
# Levanta HTTPException(403) se current_user.id não estiver em FamilyMember para family.id
```

### UUID público no path, nunca `id` interno
**Fonte:** `src/caramello/families/operations.py` linhas 181, 197, 228, 261 (todos os path params)
**Aplicar a:** todos os path params e payloads de criação em `finances/operations.py`
```python
# path param: account_uuid: UUID (não account_id: int)
# payload create: family_uuid: UUID (não family_id: int)
# resposta: uuid: UUID (sem id, sem family_id)
```

### Import lazy para evitar ciclo `shared/ ↔ families/`
**Fonte:** `src/caramello/shared/auth.py` linhas 201-205
**Aplicar a:** `_require_family_access` em `shared/auth.py`
```python
# Dentro do corpo da função, não no topo do arquivo
from caramello.families.models import FamilyMember  # noqa: PLC0415
```

### `updated_at` manual no PATCH
**Fonte:** Pitfall 4 documentado em RESEARCH.md; campo `updated_at` em `finances/models.py` linhas 26-28 (sem `onupdate`)
**Aplicar a:** todos os handlers PATCH em `finances/operations.py`
```python
db_obj.updated_at = datetime.now(timezone.utc)
session.add(db_obj)
await session.commit()
```

### Resposta 404 para recurso não encontrado
**Fonte:** `src/caramello/families/operations.py` linhas 86-90, 276-278, 288-291
```python
if db_obj is None:
    raise HTTPException(status_code=404, detail="<Entidade> não encontrada")
```

---

## No Analog Found

Nenhum arquivo sem analog — todos os 4 arquivos têm referência direta no código existente.

---

## Metadata

**Analog search scope:** `src/caramello/families/`, `src/caramello/shared/`, `src/caramello/main.py`, `tests/`
**Files scanned:** 6 (families/operations.py, shared/auth.py, finances/models.py, finances/operations.py, main.py, tests/test_family_operations.py)
**Pattern extraction date:** 2026-06-01
