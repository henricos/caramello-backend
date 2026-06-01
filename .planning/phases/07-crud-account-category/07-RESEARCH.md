# Phase 7: CRUD Account + Category — Research

**Pesquisado:** 2026-06-01
**Domínio:** FastAPI async — CRUD com controle de acesso por família, hierarquia de categorias
**Confiança:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Business logic implementada em `finances/operations.py` — segue o padrão de `families/operations.py`. O `router.py` gerado **não é registrado em `main.py`** para Account/Category nesta fase.
- **D-02:** `router.py` gerado é **mantido no disco** mas não registrado. Funciona como referência e pode ser registrado parcialmente em fases futuras quando Movement/FinancialEntry precisarem de endpoints.
- **D-03:** Organização interna dos routers em `operations.py` (um router por entidade vs. router unificado) é decisão do planner.
- **D-04:** Helper `_require_family_access(family_id: int, current_user: User, session: AsyncSession) -> None` adicionado a `src/caramello/shared/auth.py`. Levanta 403 se `current_user` não for membro da família.
- **D-05:** Para Account: resolve `family_uuid` → `family_id`, depois chama `_require_family_access`.
- **D-06:** Para Category/Subcategory: resolve `family_uuid` → `family_id` da categoria, depois chama `_require_family_access`.
- **D-07:** IDs internos **nunca** são expostos na API pública. Schemas locais definidos em `operations.py`.
- **D-08:** `AccountCreatePublic(family_uuid: UUID, name: str, type: Literal[...], currency: str)`.
- **D-09:** `AccountReadPublic` expõe `uuid`, `family_uuid`, `name`, `type`, `currency`, `is_active`, `created_at`, `updated_at`. Nunca expõe `id` ou `family_id` internos.
- **D-10:** Mesmo padrão para Category e Subcategory: schemas locais com `family_uuid` (Category) e `category_uuid` (Subcategory).
- **D-11:** Campo `type` de `AccountCreatePublic` usa `Literal["corrente", "poupanca", "cartao", "investimento"]`. Validação automática pelo Pydantic — retorna 422 para valores inválidos.
- **D-12:** Rotas planas para Subcategory: `POST /finances/subcategory`, `GET /finances/subcategory?category_uuid=xxx`, `GET /finances/subcategory/{uuid}`, `PATCH /finances/subcategory/{uuid}`.
- **D-13:** `category_uuid` é parâmetro público (UUID). Backend resolve para `category_id` interno.

### Claude's Discretion

- Organização dos routers em `operations.py` (um APIRouter por entidade ou router unificado `finances`) — planner decide pela abordagem mais limpa dado o padrão `families/operations.py`.
- Padrão de nomenclatura exato dos schemas locais (ex: `AccountPublicCreate` vs `AccountCreatePublic`) — manter consistência com Pydantic conventions.

### Deferred Ideas (OUT OF SCOPE)

- Nenhuma ideia fora do escopo surgiu durante a discussão.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Descrição | Suporte da Pesquisa |
|----|-----------|---------------------|
| ACC-01 | Usuário autenticado pode criar conta para sua família (nome, tipo, moeda) | Schemas `AccountCreatePublic` com `Literal` de tipos; resolução `family_uuid` → `family_id` + `_require_family_access` |
| ACC-02 | Usuário pode listar, detalhar e atualizar contas da família | Queries filtradas por `family_id` resolvido; `AccountReadPublic` sem IDs internos |
| ACC-03 | Usuário pode arquivar conta (`is_active=false`) sem perder histórico | PATCH normal com `AccountUpdatePublic.is_active: bool \| None = None`; sem cascade delete |
| CAT-01 | Usuário pode criar categoria de nível 1 (pai) para a família | `CategoryCreatePublic(family_uuid, name)` → persiste com `family_id` resolvido |
| CAT-02 | Usuário pode criar subcategoria de nível 2 vinculada a categoria pai | `SubcategoryCreatePublic(category_uuid, name)` → resolução `category_uuid` → `category_id` + acesso via `category.family_id` |
| CAT-03 | Sistema rejeita criação de subcategoria filha de subcategoria — máximo 2 níveis | Estrutura enforced pelo schema: `Subcategory` só referencia `Category` (não outra `Subcategory`). Nenhuma validação adicional necessária. |
| CAT-04 | Usuário pode listar e atualizar categorias da família | GET e PATCH de Category e Subcategory scoped por `family_id` |
| AUTH-FIN-01 | Todos os endpoints do domínio finances exigem Bearer token válido (401 sem token) | `Depends(get_current_user)` em todos os endpoints; `HTTPBearer` com `auto_error=True` retorna 403 para ausência de token; comportamento documentado como esperado |
| AUTH-FIN-02 | Usuário só acessa contas e categorias de famílias das quais é membro (403 caso contrário) | Helper `_require_family_access` via JOIN `Family → FamilyMember`; pattern extraído de `families/operations.py` |
</phase_requirements>

---

## Summary

Esta fase implementa os endpoints de CRUD de Account e Category/Subcategory com controle de acesso por família, seguindo o padrão já estabelecido em `families/operations.py`. O código existente fornece um template direto: schemas locais em `operations.py`, helpers de acesso que levantam 403, e `APIRouter` com prefix.

O desafio central é a **resolução de UUIDs públicos para IDs internos**: o payload de criação de Account recebe `family_uuid`, mas o modelo persiste `family_id`. O helper `_require_family_access(family_id, current_user, session)` a ser adicionado em `shared/auth.py` é o componente novo que todas as operações financeiras desta e das fases futuras vão reutilizar.

A estrutura da hierarquia de categorias é simples: o schema do banco usa duas tabelas separadas (`Category` e `Subcategory`) em vez de auto-referência, portanto a regra "máximo 2 níveis" (CAT-03) é enforced estruturalmente — não precisa de validação de lógica de negócio adicional.

**Recomendação principal:** Modelar `finances/operations.py` diretamente sobre `families/operations.py` — usar um `APIRouter` com prefix `/finances`, schemas locais `*Public` com `family_uuid`/`category_uuid`, e o helper `_require_family_access` colocado em `shared/auth.py` para reuso nas fases 8 e 9.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Criação de Account | API / Backend | — | Persistência + validação de membership; nenhuma lógica no cliente |
| Listagem de Accounts por família | API / Backend | — | Filtragem scoped por `family_id`; query segura no servidor |
| Arquivamento de Account (`is_active=false`) | API / Backend | — | PATCH normal; integridade referencial de movimentações preservada no banco |
| Criação de Category (nível 1) | API / Backend | — | Requer resolução `family_uuid` → `family_id` + verificação de membership |
| Criação de Subcategory (nível 2) | API / Backend | — | Requer resolução `category_uuid` → `category_id` + acesso via `category.family_id` |
| Validação máximo 2 níveis (CAT-03) | Database / Storage | — | Enforced estruturalmente pelo schema de duas tabelas; não precisa de lógica no router |
| Controle de acesso 401/403 | API / Backend | — | Bearer token validado em `get_current_user`; membership verificado em `_require_family_access` |
| Registro dos routers antes do MCP | API / Backend | — | Pitfall P7: `include_router` deve preceder `mcp.mount_http()` em `main.py` |

---

## Standard Stack

### Core (já no projeto — sem instalação nova)

| Biblioteca | Versão | Propósito | Status no Projeto |
|------------|--------|-----------|-------------------|
| `fastapi` | 0.118.0 | Framework HTTP; `APIRouter`, `Depends`, `HTTPException` | Instalado [VERIFIED: pyproject.toml] |
| `sqlmodel` | ≥0.0.38 | ORM; `select`, `AsyncSession`, modelos já gerados | Instalado [VERIFIED: pyproject.toml] |
| `pydantic` | 2.11.10 | Validação; `BaseModel`, `Literal`, `model_dump` | Instalado [VERIFIED: uv.lock] |
| `asyncpg` | ≥0.31.0 | Driver PostgreSQL async | Instalado [VERIFIED: pyproject.toml] |

**Nenhum pacote novo a instalar nesta fase.** Toda a implementação usa dependências já presentes.

### Package Legitimacy Audit

Não aplicável — esta fase não instala pacotes externos novos.

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request (Bearer Token)
        │
        ▼
  get_current_user()          ← shared/auth.py — valida JWT, retorna User
        │
        ▼
  finances/operations.py
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  POST /finances/accounts                               │
  │    → resolve family_uuid → Family (404 se inválido)   │
  │    → _require_family_access(family_id, user, session)  │
  │    → Account.model_validate(...)                       │
  │    → session.add / commit / refresh                    │
  │    → AccountReadPublic (sem id, sem family_id)         │
  │                                                         │
  │  GET /finances/accounts                                │
  │    → resolve family_uuid (query param)                │
  │    → _require_family_access(family_id, user, session)  │
  │    → select(Account).where(family_id == ...)          │
  │    → list[AccountReadPublic]                           │
  │                                                         │
  │  POST /finances/categories                             │
  │    → resolve family_uuid → Family                     │
  │    → _require_family_access(...)                       │
  │    → Category persist                                  │
  │                                                         │
  │  POST /finances/subcategory                            │
  │    → resolve category_uuid → Category (404 se inválido)│
  │    → _require_family_access(category.family_id, ...)  │
  │    → Subcategory persist                               │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
        │
        ▼
  _require_family_access()    ← shared/auth.py (novo helper)
    select(FamilyMember).where(family_id == X, user_id == Y)
    → None se OK; HTTPException(403) se não-membro
        │
        ▼
  PostgreSQL (asyncpg)
    tables: account, category, subcategory, family, family_member
```

### Estrutura de Arquivos Relevante

```
src/caramello/
├── finances/
│   ├── models.py          # NÃO EDITAR — gerado DSL (Account, Category, Subcategory, etc.)
│   ├── operations.py      # IMPLEMENTAR — stub atual a substituir
│   └── router.py          # NÃO REGISTRAR em main.py nesta fase
├── shared/
│   └── auth.py            # ESTENDER — adicionar _require_family_access
└── main.py                # ATUALIZAR — registrar finances operations router ANTES de mcp.mount_http()
```

### Pattern 1: Schemas Públicos Locais em operations.py

**O que é:** Schemas `*Public` definidos diretamente no arquivo `operations.py`, não nos modelos gerados. Usam UUIDs públicos em vez de IDs internos.

**Quando usar:** Sempre que a API pública expõe entidades com FKs internas — `family_id`, `category_id` etc. precisam ser substituídos por `family_uuid`, `category_uuid`.

**Exemplo (baseado em `families/operations.py`):**

```python
# Source: src/caramello/families/operations.py (padrão estabelecido no projeto)
from pydantic import BaseModel
from uuid import UUID
from typing import Literal
from datetime import datetime

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
```

### Pattern 2: Helper de Acesso com Raise 403

**O que é:** Função async que verifica membership e levanta `HTTPException(403)` se o usuário não é membro. Retorna `None` se ok — diferente de `_require_owner` que retorna `(family, member)`.

**Quando usar:** Em todos os endpoints que manipulam recursos scoped por família.

**Exemplo:**

```python
# Source: padrão derivado de families/operations.py:_require_member (projeto existente)
async def _require_family_access(
    family_id: int,
    current_user: User,
    session: AsyncSession,
) -> None:
    """Levanta 403 se current_user não é membro de family_id."""
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

### Pattern 3: Resolução de UUID → ID Antes de Persistir

**O que é:** Resolver o UUID público recebido no payload para o ID interno antes de criar o objeto ORM.

**Quando usar:** Em todo endpoint que recebe `family_uuid`, `category_uuid` etc. no payload.

**Exemplo:**

```python
# Source: padrão derivado de families/operations.py (projeto existente)
@router.post("/accounts", response_model=AccountReadPublic, status_code=201)
async def create_account(
    account_in: AccountCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AccountReadPublic:
    # Resolver UUID público → ID interno
    family_result = await session.exec(
        select(Family).where(Family.uuid == account_in.family_uuid)
    )
    family = family_result.first()
    if family is None:
        raise HTTPException(status_code=404, detail="Família não encontrada")

    # Verificar membership antes de persistir
    await _require_family_access(family.id, current_user, session)

    # Persistir com ID interno
    db_account = Account(
        family_id=family.id,
        name=account_in.name,
        type=account_in.type,
        currency=account_in.currency,
    )
    session.add(db_account)
    await session.commit()
    await session.refresh(db_account)

    # Montar resposta pública (sem IDs internos)
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

### Pattern 4: Montagem do `AccountReadPublic` em Queries de Listagem

**O que é:** Para listagens onde não temos `family_uuid` diretamente no objeto `Account`, é preciso fazer JOIN com `Family` para obter o UUID público, ou fazer query separada.

**Opção recomendada:** Fazer JOIN `Account → Family` e construir `AccountReadPublic` com o `family.uuid`.

```python
# Source: padrão derivado de models.py gerado + families/operations.py (projeto existente)
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

### Pattern 5: Registro do Router em main.py (Pitfall P7)

**Regra crítica:** Routers de `finances/operations.py` DEVEM ser registrados ANTES de `mcp.mount_http()` em `main.py`.

```python
# Source: src/caramello/main.py (existente — pattern observado)
from caramello.finances import operations as finances_operations

# ANTES de FastApiMCP / mcp.mount_http()
app.include_router(families_operations.router)
app.include_router(finances_operations.router)   # ← adicionar aqui

mcp = FastApiMCP(...)
mcp.mount_http()   # ← sempre por último
```

### Anti-Patterns a Evitar

- **Expor `id` ou `family_id` na resposta da API:** os schemas Read gerados pelo DSL incluem `family_id: int`. Os schemas `*ReadPublic` em `operations.py` NUNCA devem incluir esses campos.
- **Usar os schemas gerados (`AccountCreate`, `AccountRead`) na API pública:** esses schemas usam IDs internos. A API pública usa schemas `*Public` definidos localmente.
- **Editar `models.py` ou `router.py` gerados:** são sobrescritos a cada regeneração.
- **Registrar `finances/router.py` em `main.py`:** esse router usa schemas gerados com IDs internos e não tem controle de acesso por família. Apenas `operations.py` é registrado nesta fase.
- **Validar "máximo 2 níveis" com lógica em operação de negócio:** a regra é enforced pelo schema do banco — `Subcategory.category_id` aponta para `Category`, não para `Subcategory`. Não é possível criar "subcategoria de subcategoria" porque o tipo não existe.

---

## Don't Hand-Roll

| Problema | Não Construir | Usar Em Vez Disso | Por Que |
|----------|---------------|-------------------|---------|
| Validação de `type` de Account | Enum customizado com `__init__` | `Literal["corrente", "poupanca", "cartao", "investimento"]` no schema Pydantic | Pydantic gera 422 com mensagem clara; zero código extra |
| Controle de acesso por família | Lógica no endpoint (repetida) | Helper `_require_family_access` em `shared/auth.py` | Reutilizável nas Phases 8 e 9; centraliza o pattern |
| Verificação de hierarquia de categorias (máximo 2 níveis) | Lógica de negócio com SELECT + validação | Estrutura de duas tabelas separadas no schema | O banco impede fisicamente a criação de nível 3 |
| Persistência de objetos com FKs | `session.exec(insert(...))` manual | `Account.model_validate(data)` + `session.add()` | SQLModel/Pydantic cuida de validação e coerção de tipos |

**Insight chave:** A maior parte da "lógica" desta fase é resolução de UUID → ID e verificação de membership. Não há lógica de negócio complexa — o valor está em implementar o pattern correto de forma consistente.

---

## Common Pitfalls

### Pitfall 1: Routers Registrados Após `mcp.mount_http()` Não Aparecem no MCP
**O que acontece:** Se `app.include_router(finances_operations.router)` for colocado depois de `mcp.mount_http()`, os endpoints financeiros não aparecerão como ferramentas MCP nas fases futuras que precisarem deles.
**Por que acontece:** `FastApiMCP.mount_http()` captura os routes existentes no momento da chamada. Routes adicionados depois não são observados.
**Como evitar:** Sempre registrar todos os routers ANTES da linha `mcp.mount_http()`.
**Sinais de alerta:** `GET /mcp` não lista os novos endpoints mesmo com token válido.

### Pitfall 2: `AccountRead` Gerado Expõe `family_id` Interno
**O que acontece:** Se o planner usar `AccountRead` do DSL como `response_model`, a resposta inclui `family_id: int` — um ID interno que jamais deve sair da API.
**Por que acontece:** O gerador DSL cria `AccountRead` com todos os campos, incluindo FKs internas.
**Como evitar:** Definir `AccountReadPublic` em `operations.py` sem `id` e sem `family_id`; usar apenas esse schema como `response_model`.

### Pitfall 3: `session.exec()` vs `session.execute()` para JOINs Complexos
**O que acontece:** `session.exec(select(Account, Family).join(...))` com SQLModel async pode produzir comportamento inesperado em JOINs multi-tabela (retorna `Row` em vez dos objetos individuais).
**Por que acontece:** `session.exec()` é wrapper do SQLModel; `session.execute()` é SQLAlchemy puro com `.scalars()` ou `.all()` explícito.
**Como evitar:** Para queries de verificação de membership (JOIN `Family → FamilyMember`), usar `session.exec(select(FamilyMember).where(...))` — query simples em uma tabela, sem JOIN. Para listagens com JOIN, preferir `session.execute()`.

### Pitfall 4: `updated_at` Não É Atualizado Automaticamente no PATCH
**O que acontece:** Ao fazer PATCH de uma Account, o campo `updated_at` permanece com o valor da criação.
**Por que acontece:** O modelo tem `default_factory` apenas para criação; SQLModel/SQLAlchemy não tem `onupdate` configurado no campo gerado.
**Como evitar:** No handler de PATCH, definir explicitamente `db_obj.updated_at = datetime.now(timezone.utc)` antes de `session.add()`.

### Pitfall 5: Import Circular `finances/` ↔ `families/`
**O que acontece:** `finances/operations.py` importa `FamilyMember` de `families/models.py`. Se `families/operations.py` importar algo de `finances/`, temos ciclo.
**Por que acontece:** Python resolve imports no momento de carregamento do módulo.
**Como evitar:** `finances/` pode importar de `families/` e `users/`. O inverso é proibido (documentado em STATE.md).

### Pitfall 6: `_require_family_access` em `shared/auth.py` Causa Import Circular com `families/`
**O que acontece:** `shared/auth.py` já faz import lazy de `FamilyMember` em `get_current_user` (para o auto-join). Adicionar `_require_family_access` com import direto (não lazy) de `FamilyMember` pode quebrar o ciclo.
**Por que acontece:** `shared/auth.py` é carregado antes de `families/models.py` em alguns contextos.
**Como evitar:** Manter o mesmo padrão de import lazy já usado em `get_current_user`: `from caramello.families.models import FamilyMember` dentro do corpo da função, não no topo do arquivo.

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|------------|-------|
| Framework | pytest 9.0.1 + pytest-asyncio |
| Arquivo de config | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Comando rápido | `uv run python -m pytest tests/test_finances_operations.py -q` |
| Suite completa | `uv run python -m pytest -q` |

### Phase Requirements → Test Map

| Req ID | Comportamento | Tipo de Teste | Comando Automatizado | Arquivo Existe? |
|--------|--------------|---------------|---------------------|-----------------|
| ACC-01 | POST /finances/accounts cria conta; resposta inclui `uuid`, sem `id`/`family_id` | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_account_returns_uuid -x` | ❌ Wave 0 |
| ACC-02 | GET /finances/accounts filtra por família do usuário autenticado | unit | `uv run python -m pytest tests/test_finances_operations.py::test_list_accounts_scoped_to_family -x` | ❌ Wave 0 |
| ACC-02 | 401 sem token | unit | `uv run python -m pytest tests/test_finances_operations.py::test_accounts_require_auth -x` | ❌ Wave 0 |
| ACC-02 | 403 para família alheia | unit | `uv run python -m pytest tests/test_finances_operations.py::test_accounts_403_non_member -x` | ❌ Wave 0 |
| ACC-03 | PATCH `is_active=false` arquiva sem deletar | unit | `uv run python -m pytest tests/test_finances_operations.py::test_archive_account -x` | ❌ Wave 0 |
| CAT-01 | POST /finances/categories cria categoria pai | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_category -x` | ❌ Wave 0 |
| CAT-02 | POST /finances/subcategory com `category_uuid` válido cria subcategoria | unit | `uv run python -m pytest tests/test_finances_operations.py::test_create_subcategory -x` | ❌ Wave 0 |
| CAT-03 | Modelo estrutural impede nível 3 — não há endpoint de criação de "sub-subcategoria" | verificação de paths | `uv run python -m pytest tests/test_finances_operations.py::test_finances_router_paths -x` | ❌ Wave 0 |
| CAT-04 | GET e PATCH de categories scoped por família | unit | `uv run python -m pytest tests/test_finances_operations.py::test_list_update_categories -x` | ❌ Wave 0 |
| AUTH-FIN-01 | Bearer ausente → 401/403 (HTTPBearer com auto_error=True retorna 403) | unit | coberto em test_accounts_require_auth | ❌ Wave 0 |
| AUTH-FIN-02 | Membro de outra família → 403 | unit | coberto em test_accounts_403_non_member | ❌ Wave 0 |

**Nota sobre AUTH-FIN-01:** O `HTTPBearer` com `auto_error=True` (comportamento padrão) retorna **403** quando o header `Authorization` está ausente, não 401. O REQUIREMENTS.md especifica 401. Na prática, o comportamento atual do projeto é 403 para token ausente — os testes existentes validam isso (ver `test_auth.py::test_me_unauthenticated`). O planner deve decidir se ajusta o helper ou documenta que 403 é o comportamento esperado para ausência de token.

### Sampling Rate

- **Por task commit:** `uv run python -m pytest tests/test_finances_operations.py -q`
- **Por wave merge:** `uv run python -m pytest -q`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_finances_operations.py` — cobre ACC-01, ACC-02, ACC-03, CAT-01, CAT-02, CAT-03, CAT-04, AUTH-FIN-01, AUTH-FIN-02
  - Seguir exatamente o padrão de `tests/test_family_operations.py`:
    - `dependency_overrides[get_current_user]` com `_make_fake_user()`
    - `dependency_overrides[get_session]` com `AsyncMock`
    - `TestClient(app)` sem context manager (evita disparar lifespan/fetch_jwks)
    - `pytest.importorskip("caramello.finances.operations")` no início de cada teste

*(Infraestrutura de teste existente cobre todo o resto — `conftest.py`, `AsyncMock`, `TestClient` já estabelecidos)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Aplica | Controle Padrão |
|---------------|--------|-----------------|
| V2 Authentication | sim | `get_current_user` via Keycloak JWT — já implementado |
| V3 Session Management | não | Stateless JWT — sem sessões server-side |
| V4 Access Control | sim | `_require_family_access` — novo helper desta fase |
| V5 Input Validation | sim | `Literal["corrente", ...]` no Pydantic + validação automática de UUID |
| V6 Cryptography | não | Sem novo processamento criptográfico nesta fase |

### Known Threat Patterns

| Pattern | STRIDE | Mitigação Padrão |
|---------|--------|-----------------|
| IDOR — acessar Account de outra família via UUID adivinhado | Elevation of Privilege | `_require_family_access` após resolver UUID; UUID v4 (espaço de 2^122) torna adivinhação inviável |
| Injeção de `family_id` interno no payload | Tampering | Schemas `*Public` aceitam apenas `family_uuid`; `family_id` é resolvido no backend |
| Endpoint de listagem sem filtro de família | Information Disclosure | `GET /finances/accounts` requer `family_uuid` como parâmetro + verificação de membership |
| CRUD sem autenticação | Spoofing | `Depends(get_current_user)` em todos os endpoints |

---

## Code Examples

### Estrutura Completa de finances/operations.py (esqueleto)

```python
# CARAMELLO-GENERATED: implemented
# Source: src/caramello/families/operations.py (padrão estabelecido no projeto)
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

# --- Schemas públicos ---

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

class SubcategoryCreatePublic(BaseModel):
    category_uuid: UUID
    name: str

class SubcategoryReadPublic(BaseModel):
    uuid: UUID
    category_uuid: UUID
    name: str
    created_at: datetime
    updated_at: datetime
```

### Extensão de shared/auth.py com _require_family_access

```python
# Source: padrão derivado de get_current_user em shared/auth.py (projeto existente)
async def _require_family_access(
    family_id: int,
    current_user: "User",
    session: AsyncSession,
) -> None:
    """Verifica que current_user é membro de family_id. Levanta 403 se não for.

    Uso: após resolver family_uuid → family.id, chamar este helper.
    Reutilizável em Phases 7, 8, 9.
    """
    # Import lazy para evitar ciclo shared/ ↔ families/ (mesmo padrão de get_current_user)
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

---

## State of the Art

| Abordagem Antiga | Abordagem Atual | Quando Mudou | Impacto |
|-----------------|----------------|--------------|---------|
| `AccountCreate` com `family_id: int` na API | `AccountCreatePublic` com `family_uuid: UUID` | Phase 7 (decisão D-07/D-08) | IDs internos nunca expostos; padrão de segurança |
| `router.py` gerado registrado em `main.py` | Somente `operations.py` registrado | Phase 7 (decisão D-01) | Controle total sobre endpoints e schemas expostos |
| `psycopg2-binary` síncrono (M1 inicial) | `asyncpg` + `AsyncSession` (M1 finalizado) | Phase 3 M1 | Toda query usa `await session.exec(...)` |

**Deprecado/Desatualizado:**
- `router.py` gerado: presente no disco mas **não registrar** em `main.py` para Account/Category. Manter como referência estrutural.
- Schemas gerados (`AccountRead`, `CategoryRead`): usam IDs internos — não usar como `response_model` na API pública.

---

## Open Questions

1. **`family_uuid` como query param obrigatório vs. inferido do usuário**
   - O que sabemos: `GET /finances/accounts` precisa retornar contas scoped por família. Um usuário pode ser membro de múltiplas famílias.
   - O que está indefinido: Se o usuário é membro de só uma família, `family_uuid` poderia ser inferido. Se membro de várias, é obrigatório.
   - Recomendação: Usar `family_uuid` como query param obrigatório em listagens (`GET /finances/accounts?family_uuid=xxx`) — mais explícito e consistente. O planner pode torná-lo opcional com fallback para família única se preferir.

2. **Comportamento de AUTH-FIN-01: 401 vs 403 para token ausente**
   - O que sabemos: O `HTTPBearer` com `auto_error=True` retorna 403 (não 401) quando o header `Authorization` está ausente. O REQUIREMENTS.md especifica 401.
   - O que está indefinido: O projeto aceita 403 para token ausente (comportamento atual do M1) ou deve ajustar para retornar 401?
   - Recomendação: Documentar nos testes que 403 é o comportamento esperado para ausência de token — consistente com o M1. Se o requisito de 401 for hard, trocar `HTTPBearer` por dependência customizada.

---

## Environment Availability

| Dependência | Requerida Por | Disponível | Versão | Fallback |
|-------------|--------------|------------|--------|----------|
| Python 3.12 | Runtime | ✓ | 3.12.3 | — |
| uv | Gestão de pacotes | ✓ | (instalado) | — |
| PostgreSQL (caramello_dev) | Testes de integração | Não verificado | — | Testes unitários com AsyncMock não precisam de banco |
| asyncpg | Driver async | ✓ | ≥0.31.0 | — |

**Dependências faltando sem fallback:** nenhuma — esta fase usa apenas bibliotecas já instaladas.

**Nota:** Testes unitários (Wave 0) usam `AsyncMock` para sessão e não requerem banco real. O banco é necessário somente para testes marcados com `@pytest.mark.integration`.

---

## Assumptions Log

| # | Claim | Seção | Risco se Errado |
|---|-------|-------|-----------------|
| A1 | `updated_at` não tem `onupdate` configurado no modelo gerado — precisa ser definido manualmente no PATCH | Common Pitfalls | Se o campo for auto-atualizado pelo SQLAlchemy, a linha extra é inócua mas desnecessária |
| A2 | `family_uuid` será query param obrigatório em `GET /finances/accounts` | Architecture Patterns | Se o planner preferir inferência de família única, a assinatura do endpoint muda |
| A3 | AUTH-FIN-01 aceita 403 para token ausente (comportamento atual do projeto) | Open Questions | Se 401 for hard requirement, `HTTPBearer` precisa ser substituído por dependência customizada |

---

## Sources

### Primary (HIGH confidence)
- `src/caramello/families/operations.py` — padrão completo de implementação; lido diretamente [VERIFIED: leitura direta do arquivo]
- `src/caramello/shared/auth.py` — estilo de helpers e import lazy; lido diretamente [VERIFIED: leitura direta do arquivo]
- `src/caramello/finances/models.py` — modelos gerados; campos, tipos, FKs confirmados [VERIFIED: leitura direta do arquivo]
- `alembic/versions/0002_finances_schema.py` — schema do banco confirmado [VERIFIED: leitura direta do arquivo]
- `src/caramello/main.py` — ordem de registro de routers e pattern MCP [VERIFIED: leitura direta do arquivo]
- `tests/test_family_operations.py` — padrão de testes unitários com AsyncMock [VERIFIED: leitura direta do arquivo]
- `.planning/phases/07-crud-account-category/07-CONTEXT.md` — decisões locked [VERIFIED: leitura direta do arquivo]

### Secondary (MEDIUM confidence)
- `.planning/ROADMAP.md` — success criteria e technical constraints da Phase 7 [VERIFIED: leitura direta do arquivo]
- `.planning/REQUIREMENTS.md` — ACC-01/02/03, CAT-01/02/03/04, AUTH-FIN-01/02 [VERIFIED: leitura direta do arquivo]

---

## Metadata

**Breakdown de confiança:**
- Stack padrão: HIGH — todo o stack já está instalado e em uso; sem dependências novas
- Arquitetura: HIGH — padrão `families/operations.py` é referência direta e verificada
- Pitfalls: HIGH — P7 (registro antes do MCP), import circular e schemas gerados vs. públicos verificados no código existente
- Testes: HIGH — padrão `test_family_operations.py` é referência direta e funcional

**Data da pesquisa:** 2026-06-01
**Válido até:** 2026-07-01 (stack estável)
