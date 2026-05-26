# Phase 4: Domínio Family - Research

**Pesquisado:** 2026-05-26
**Domínio:** FastAPI/SQLModel — domain refactoring, family business endpoints, auto-join logic, Alembic migration
**Confiança:** HIGH — toda a base de código foi inspecionada diretamente; padrões verificados no código existente

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `FamilyInvitation` redesenhado: campos removidos `invitee_email` e `expires_at`; campos adicionados `email` (str) e `status` (default `"pending_login"`, valores válidos: `"pending_login"` e `"joined"`). Campos mantidos: `id`, `uuid`, `family_id`, `inviter_id`, `created_at`.
- **D-02:** Auto-join integrado em `get_current_user()` em `shared/auth.py`. Após JIT provisioning, busca `FamilyInvitation` com `email == token_email AND status == "pending_login"`. Se existir: cria `FamilyMember(role="member", joined_at=now)` e atualiza `FamilyInvitation.status = "joined"`. Operação atômica.
- **D-03:** Duplo cadastro manual — sem integração com Keycloak Admin API nesta fase.
- **D-04:** FAMILY-04/05/06 (código convite reutilizável, join request, aprovação) deferidos para M2.
- **D-05:** DSL First para operações: criar `dsl/operations/family.yaml` → generator produz stubs → implementar → anotar `implemented`.
- **D-06:** `operations.py` exporta `APIRouter` próprio, registrado separado em `main.py`.
- **D-07:** Endpoints: `POST /families/registry`, `GET /families/families`, `GET /families/families/{uuid}`, `POST /families/families/{uuid}/pre-register`, `GET /families/families/{uuid}/members`, `DELETE /families/families/{uuid}/members/{user_uuid}`.
- **D-08:** CRUD gerado permanece com auth básico (token válido), sem filtros por família.
- **D-09:** Campo `domain` determina diretório e prefixo URL. `user.yaml`: `domain: user` → `domain: users`; `family*.yaml`: `domain: family` → `domain: families`.
- **D-10:** URLs usam hifens: `table_name.replace("_", "-")`. Generator deve implementar esta tradução.
- **D-11:** Estrutura de URL: `/{domain}/{table_name_with_hyphens}/` para CRUD; `/{domain}/{operacao}` para operações.
- **D-12:** FamilyMember permanece `is_link_model: true` — sem CRUD gerado.
- **D-13:** Role `"owner"` para criador; `"member"` para pré-cadastrados.

### Claude's Discretion

Nenhuma área explicitamente delegada ao discretion. Todos os itens são decisões travadas ou deferidos.

### Deferred Ideas (OUT OF SCOPE)

- FAMILY-04/05/06: código convite reutilizável, join request, aprovação (M2)
- Integração Keycloak Admin API (M2+)
- Family-scoped CRUD automático no generator (M2+, conceito D-08-DEFERRED)
- `GET /health` com ping ao banco (OPS-01)
- Logging estruturado em JSON com `structlog` (OPS-02)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Descrição | Suporte de Research |
|----|-----------|---------------------|
| FAMILY-01 | Usuário autenticado cria família e torna-se owner automaticamente (`POST /families/registry`) | D-07, D-13: endpoint de negócio em operations.py; transação Family + FamilyMember(role="owner") |
| FAMILY-02 | Usuário autenticado lista suas famílias (`GET /families/families`) | D-07: filtro por membership via JOIN com family_member; apenas famílias onde user é membro |
| FAMILY-03 | Usuário autenticado consulta detalhes de família da qual é membro (`GET /families/families/{uuid}`) | D-07: verifica membership antes de retornar; 403 se não for membro |
| FAMILY-07 | Owner lista e remove membros (`GET /families/families/{uuid}/members`, `DELETE /families/families/{uuid}/members/{user_uuid}`) | D-07, D-13: verificação de role="owner" antes de DELETE; 403 para não-owner |
| FAMILY-04 | (DEFERIDO M2 — fora de escopo desta fase) | — |
| FAMILY-05 | (DEFERIDO M2 — fora de escopo desta fase) | — |
| FAMILY-06 | (DEFERIDO M2 — fora de escopo desta fase) | — |
</phase_requirements>

---

## Summary

A Phase 4 envolve quatro trabalhos distintos que devem ser executados em sequência: (1) refatoração de diretórios e URLs em todo o codebase — renomear `src/caramello/user/` → `src/caramello/users/`, `src/caramello/family/` → `src/caramello/families/`, atualizar o generator para emitir prefixos de URL com hifens, e atualizar `main.py` com os novos imports; (2) redesenho da entidade `FamilyInvitation` no DSL (remover `invitee_email`/`expires_at`, adicionar `email`/`status`) e geração da migration Alembic correspondente; (3) implementação das operações de negócio do domínio family via `dsl/operations/family.yaml` + `families/operations.py`; e (4) extensão de `shared/auth.py` para incluir auto-join no fluxo de `get_current_user()`.

A ordem importa: a refatoração de diretórios e o generator com hifens nas URLs devem vir antes da geração do código family, pois o generator vai escrever nos novos paths. A migration de schema para `family_invitation` deve ser gerada após o redesenho do modelo no DSL. O auto-join em `shared/auth.py` depende dos modelos `FamilyInvitation` e `FamilyMember` já existirem nos novos paths.

**Recomendação principal:** Planejar em 3 waves: Wave 1 (generator + refatoração de domínios), Wave 2 (migration + operações de negócio), Wave 3 (auto-join + tests). O generator é o bloqueador de tudo — resolver primeiro.

---

## Architectural Responsibility Map

| Capacidade | Tier Primário | Tier Secundário | Raciocínio |
|------------|--------------|-----------------|------------|
| CRUD gerado (Family, FamilyInvitation) | API/Backend — `families/router.py` | — | Gerado pelo DSL, endpoints simples, sem lógica de negócio |
| Criação de família + owner | API/Backend — `families/operations.py` | Database | Transação atômica: INSERT family + INSERT family_member(role="owner") |
| Listagem de famílias do usuário | API/Backend — `families/operations.py` | Database | JOIN entre family e family_member com filtro por user_id |
| Pré-registro de membro | API/Backend — `families/operations.py` | Database | INSERT family_invitation(status="pending_login"); verifica role="owner" antes |
| Auto-join no primeiro login | API/Backend — `shared/auth.py` | Database | Estende get_current_user(): busca FamilyInvitation pendente + INSERT family_member atômico |
| Verificação de ownership | API/Backend — inline em operations.py | — | Query SELECT family_member WHERE role="owner" → 403 se não encontrar |
| Listagem/remoção de membros | API/Backend — `families/operations.py` | Database | GET sem restrição de role; DELETE requer role="owner" |
| URL routing com hifens | API/Backend — `scripts/generate_code.py` | — | Generator deve traduzir `table_name.replace("_", "-")` no prefix do APIRouter |

---

## Standard Stack

### Core
| Biblioteca | Versão | Propósito | Por que padrão |
|------------|--------|-----------|----------------|
| FastAPI | 0.118.0 | Framework HTTP, routing | Já em uso; APIRouter com prefix e tags |
| SQLModel | >=0.0.38 | ORM + schemas Pydantic | Já em uso; AsyncSession para todas as queries |
| SQLAlchemy asyncio | (via sqlmodel) | Async engine, pg_insert | `pg_insert` para upserts atômicos (padrão JIT provisioning) |
| Alembic | 1.16.5 | Migration de schema | Já configurado; nova migration para alterar `family_invitation` |
| PyJWT[crypto] | >=2.13.0 | Validação JWT | Já em uso em `shared/auth.py` |

### Supporting
| Biblioteca | Versão | Propósito | Quando usar |
|------------|--------|-----------|-------------|
| `sqlalchemy.dialects.postgresql.insert` (pg_insert) | (via sqlalchemy) | INSERT ON CONFLICT | Auto-join atômico em family_member — mesmo padrão do JIT provisioning |
| `from __future__ import annotations` | stdlib | Evitar import circular | Em `shared/auth.py` e `families/operations.py` onde há imports entre domínios |

### Alternativas Consideradas
| Em vez de | Poderia usar | Tradeoff |
|-----------|-------------|----------|
| pg_insert ON CONFLICT para auto-join | INSERT simples + SELECT | Não é race-condition-safe; pg_insert é o padrão estabelecido no JIT provisioning |
| Verificação de owner via query extra | Incluir role no JWT/claims | Query extra é mais simples nesta fase; JWT enrichment é M2+ |

**Instalação:** sem novas dependências nesta fase — todo o stack já está em `pyproject.toml`.

---

## Architecture Patterns

### System Architecture Diagram

```
Request HTTP
    │
    ▼
FastAPI app (main.py)
    │
    ├─► Lifespan: fetch_jwks() ────────────────► Keycloak JWKS endpoint
    │
    ├─► shared/auth.py: get_current_user()
    │       │
    │       ├─ Valida JWT (JWKS cache)
    │       ├─ JIT provisioning User (pg_insert ON CONFLICT DO NOTHING)
    │       └─ AUTO-JOIN: busca FamilyInvitation pendente
    │               └─ se encontrou: INSERT family_member + UPDATE invitation.status
    │
    ├─► users/operations.py (APIRouter prefix="/users")
    │       └─ GET /users/me → retorna User autenticado
    │
    ├─► users/router.py (APIRouter aggregator)
    │       └─ users_router prefix="/users/user"  ← CRUD gerado
    │
    ├─► families/operations.py (APIRouter prefix="/families")
    │       ├─ POST /families/registry
    │       ├─ GET  /families/families
    │       ├─ GET  /families/families/{uuid}
    │       ├─ POST /families/families/{uuid}/pre-register
    │       ├─ GET  /families/families/{uuid}/members
    │       └─ DELETE /families/families/{uuid}/members/{user_uuid}
    │
    └─► families/router.py (APIRouter aggregator)
            ├─ family_router prefix="/families/family"  ← CRUD gerado
            └─ familyinvitation_router prefix="/families/family-invitation"  ← CRUD gerado
```

### Estrutura de Projeto Recomendada (após refatoração)

```
src/caramello/
├── core/
│   └── config.py               # Settings (inalterado)
├── shared/
│   ├── auth.py                 # get_current_user() + auto-join (ESTENDER)
│   └── database.py             # get_session() (inalterado)
├── users/                      # RENOMEAR de user/
│   ├── __init__.py
│   ├── models.py               # REGENERAR (domain: users)
│   ├── operations.py           # CARAMELLO-GENERATED: implemented — NÃO TOCAR
│   └── router.py               # REGENERAR (prefix="/users/user")
└── families/                   # RENOMEAR de family/
    ├── __init__.py
    ├── models.py               # REGENERAR (redesenho FamilyInvitation)
    ├── operations.py           # CRIAR VIA DSL (dsl/operations/family.yaml)
    └── router.py               # REGENERAR (prefixes com hifens)

dsl/
├── entities/
│   ├── user.yaml               # ATUALIZAR: domain: user → users
│   ├── family.yaml             # ATUALIZAR: domain: family → families
│   ├── family_member.yaml      # ATUALIZAR: domain: family → families
│   └── family_invitation.yaml  # ATUALIZAR: domain + redesenho de campos
├── operations/
│   ├── user.yaml               # ATUALIZAR: paths /user → /users
│   └── family.yaml             # CRIAR: 6 operações D-07
└── manifest.yaml               # inalterado (não referencia domain)

alembic/versions/
└── 20260524_0138_initial_schema.py   # existente
    + [nova migration]                # alterar family_invitation
```

### Pattern 1: Generator com URL de hifens

**O que é:** O `_consolidate_routers()` em `generate_code.py` usa `table_name` como prefixo do APIRouter. Atualmente emite `prefix="/family_invitation"`. Deve emitir `prefix="/families/family-invitation"`.

**Como implementar:**

O `generate_router()` já recebe `entity_data` com os campos `domain` e `table_name`. A mudança necessária é duas alterações no código do generator:

```python
# ANTES (generate_router, linha ~364):
router = APIRouter(prefix="/{table_name}", tags=["{name}"])

# DEPOIS:
url_table_name = table_name.replace("_", "-")
router = APIRouter(prefix="/{domain}/{url_table_name}", tags=["{name}"])
```

E no `_run_ruff_fix` (linha ~885), adicionar `"users"` e `"families"` à lista de diretórios:

```python
dirs = [str(src_dir / d) for d in ("users", "families") if (src_dir / d).exists()]
```

[VERIFIED: leitura direta de `scripts/generate_code.py`]

### Pattern 2: operations.py com APIRouter próprio

**O que é:** O padrão estabelecido em `user/operations.py` exporta um `router = APIRouter(prefix="/user", ...)`. Para `families/operations.py`, o prefix será `/families` e as rotas terão sub-paths `/families`, `/registry`, `/families/{uuid}/members`, etc.

**Exemplo — estrutura de families/operations.py:**

```python
# CARAMELLO-GENERATED: implemented
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from caramello.shared.auth import get_current_user
from caramello.shared.database import get_session
from caramello.users.models import User
from caramello.families.models import (
    Family, FamilyCreate, FamilyMember, FamilyInvitation
)

router = APIRouter(prefix="/families", tags=["Family"])

@router.post("/registry", ...)
async def registry_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ...:
    # INSERT family + INSERT family_member(role="owner") na mesma sessão
    ...
```

[VERIFIED: leitura direta de `src/caramello/user/operations.py`]

### Pattern 3: Verificação de Ownership

**O que é:** Antes de operações restritas (pre-register, remover membro), verificar se o usuário autenticado é owner da família.

```python
# Padrão de verificação de owner — replicar em todas as ops restritas
async def _get_owner_membership(
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

[ASSUMED: estrutura da query — padrão natural do SQLModel/SQLAlchemy para JOIN com filtro]

### Pattern 4: Auto-join em get_current_user()

**O que é:** Extensão da lógica existente em `shared/auth.py` após o JIT provisioning. O auto-join acontece na mesma sessão, logo após o SELECT que recupera o User provisionado.

```python
# Após o SELECT do user (linha ~188 de auth.py):
# AUTO-JOIN: verificar FamilyInvitation pendente pelo email do token
from caramello.families.models import FamilyInvitation, FamilyMember  # import lazy

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

**Atenção import circular:** `shared/auth.py` já usa `from __future__ import annotations` e `TYPE_CHECKING` para `User`. O mesmo padrão deve ser aplicado para `FamilyInvitation` e `FamilyMember`. Usar import lazy dentro do `if TYPE_CHECKING:` para type hints e imports diretos dentro do corpo da função.

[VERIFIED: leitura direta de `src/caramello/shared/auth.py` — padrão `TYPE_CHECKING` já estabelecido]

### Pattern 5: Alembic migration para FamilyInvitation

**O que é:** Migration de ALTER TABLE que remove `invitee_email` e `expires_at`, e adiciona `email` e `status` com novo default.

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
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending_login",
        ),
    )
    # Remover server_default após aplicar (padrão Alembic)
    op.alter_column("family_invitation", "email", server_default=None)
    op.alter_column("family_invitation", "status", server_default=None)

def downgrade() -> None:
    op.drop_column("family_invitation", "email")
    op.drop_column("family_invitation", "status")
    op.add_column("family_invitation", sa.Column("invitee_email", sa.String(), nullable=False, server_default=""))
    op.add_column("family_invitation", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
```

[ASSUMED: estrutura da migration — verificar schema atual no migration existente antes de gerar]

### Anti-Patterns a Evitar

- **Editar `models.py` ou `router.py` diretamente:** esses arquivos são gerados. Sempre editar o YAML e rodar `bin/generate_code`. Exceção: `operations.py` com anotação `CARAMELLO-GENERATED: implemented`.
- **Alterar anotação CARAMELLO-GENERATED antes de implementar:** o generator sobrescreve arquivos com anotação `stub`. Alterar para `implemented` somente após o stub estar funcional.
- **Registrar operations router depois do CRUD router em main.py:** rotas estáticas (ex: `/families/registry`) devem ser registradas ANTES de rotas com parâmetro (`/families/family/{uuid}`). Ver comentário existente em `main.py` linhas 49-51 para o mesmo problema em `/user/me`.
- **Usar import direto de families.models em shared/auth.py no topo do arquivo:** causa import circular porque families/models.py importa users/models.py que por sua vez pode importar de shared. Usar imports lazy dentro do corpo da função.

---

## Don't Hand-Roll

| Problema | Não Construir | Usar | Por quê |
|----------|---------------|------|---------|
| INSERT atômico race-condition-safe | SELECT + INSERT condicional | `pg_insert(...).on_conflict_do_nothing()` | Race condition: requests concorrentes podem criar duplicatas; pg_insert é atômico no PostgreSQL |
| Hash/comparação de email | Normalização manual | Email direto do JWT (`email` claim) | Consistência garantida pelo Keycloak; normalizar no JWT source, não na app |
| UUID gerado manualmente | `str(uuid4())` | `default_factory=uuid4` no Field | Garante unicidade e geração server-side pelo SQLModel |
| Validação de role string | `if role not in ["owner", "member"]` | Verificação direta `FamilyMember.role == "owner"` na query | Simples e suficiente para 2 roles; enum ou Literal seria over-engineering nesta fase |

---

## Runtime State Inventory

> Esta fase altera nomes de diretórios (`user/` → `users/`, `family/` → `families/`), prefixos de URL, e o schema da tabela `family_invitation`. Todos os cinco itens abaixo foram verificados.

| Categoria | Itens Encontrados | Ação Necessária |
|-----------|-------------------|-----------------|
| Stored data | Tabela `family_invitation` em PostgreSQL tem colunas `invitee_email` e `expires_at` (schema inicial aplicado) | Migration Alembic: DROP COLUMN + ADD COLUMN |
| Live service config | Nenhum serviço externo referencia paths `/user/` ou `/family/` por config fora do git — apenas Keycloak JWKS URL que não muda | Nenhuma |
| OS-registered state | Nenhum — sem Task Scheduler, pm2, systemd tasks referenciando os paths | Nenhuma |
| Secrets/env vars | Nenhuma variável de ambiente referencia os caminhos de domínio — apenas `DB_*` e `KEYCLOAK_*` | Nenhuma |
| Build artifacts | Diretórios `src/caramello/user/__pycache__/` e `src/caramello/family/__pycache__/` serão stale após renomear | `find src -name "__pycache__" -exec rm -rf {} +` antes de regenerar |

[VERIFIED: leitura direta de `alembic/versions/20260524_0138_initial_schema.py`, `src/caramello/core/config.py`, estrutura de arquivos do projeto]

---

## Common Pitfalls

### Pitfall 1: Renomear diretórios sem atualizar todos os imports

**O que vai errar:** Renomear `src/caramello/user/` para `src/caramello/users/` sem atualizar `main.py`, `shared/auth.py`, e qualquer outro arquivo com `from caramello.user.models import ...` causa `ModuleNotFoundError` imediato.

**Por que acontece:** Python resolve imports por path de arquivo; renomear o diretório invalida todos os `from caramello.user.*` sem aviso prévio.

**Como evitar:** Fazer o rename e grep por `caramello.user.` e `caramello.family.` em todo o codebase antes de rodar o generator. Lista completa de arquivos afetados: `main.py`, `shared/auth.py`, `family/models.py` (import de `User`), `family/router.py` (import de `User`).

**Sinais de alerta:** `ImportError: No module named 'caramello.user'` ou `'caramello.family'` ao iniciar a app ou rodar testes.

[VERIFIED: leitura de todos os arquivos com imports cross-domain]

### Pitfall 2: Registrar operations router DEPOIS do CRUD router — rota estática mascarada por rota com parâmetro

**O que vai errar:** Se `families.operations.router` (que tem `GET /families/families`) for registrado DEPOIS de `families.router` (que tem `GET /families/family/{uuid}`), FastAPI pode interpretar `/families/families` como um UUID inválido em vez de chamar a rota correta.

**Por que acontece:** FastAPI faz matching em ordem de registro. Rotas estáticas (`/families/families`) devem vir antes de rotas com parâmetro (`/families/family/{uuid}`). O código em `main.py` já documenta este comportamento nas linhas 49-51 para `/user/me`.

**Como evitar:** Em `main.py`, registrar `families_operations.router` ANTES de `families_router.router`. Replicar o padrão existente das linhas 52-54.

[VERIFIED: leitura de `src/caramello/main.py` linhas 49-54]

### Pitfall 3: Import circular ao estender shared/auth.py com FamilyInvitation/FamilyMember

**O que vai errar:** Adicionar `from caramello.families.models import FamilyInvitation, FamilyMember` no topo de `shared/auth.py` → Python tenta importar `families.models` → que importa `users.models` → que pode já estar importando de `shared` → `ImportError: cannot import name 'get_current_user'` (circular).

**Por que acontece:** Grafo de dependências: `shared/auth.py` → `users/models.py` (TYPE_CHECKING, ok). Se `families/models.py` também importa de `users/models.py`, o ciclo pode fechar dependendo da ordem de carregamento do Python.

**Como evitar:** `shared/auth.py` já usa o padrão correto: `if TYPE_CHECKING: from caramello.user.models import User`. Aplicar o mesmo para `FamilyInvitation` e `FamilyMember`. Os imports diretos (usados em runtime) devem ser feitos DENTRO do corpo da função `get_current_user()`, não no nível de módulo. O arquivo já tem `from __future__ import annotations`.

[VERIFIED: leitura de `src/caramello/shared/auth.py` linhas 21-36]

### Pitfall 4: Generator sobrescreve operations.py que já está implementado

**O que vai errar:** Se `families/operations.py` tiver anotação `stub` e `bin/generate_code` for rodado após a implementação manual, o conteúdo implementado é perdido.

**Por que acontece:** O generator em `generate_code.py` linhas 867-870 só pula o arquivo se a primeira linha for `# CARAMELLO-GENERATED: implemented`. Se for `stub`, sobrescreve.

**Como evitar:** Alterar a anotação de `stub` para `implemented` IMEDIATAMENTE após implementar o stub. Não deixar para depois. Confirmar com `head -1 src/caramello/families/operations.py` antes de rodar o generator.

[VERIFIED: leitura de `scripts/generate_code.py` linhas 867-870]

### Pitfall 5: Migration com `server_default` deixado permanentemente

**O que vai errar:** Colunas adicionadas via `op.add_column` com `server_default` para tabelas existentes ficam com o constraint de server_default no banco. Isso pode causar inconsistências quando a app tenta inserir valores diferentes.

**Por que acontece:** Alembic mantém o `server_default` no banco mesmo após a migration se não for explicitamente removido.

**Como evitar:** Adicionar `op.alter_column(..., server_default=None)` logo após o `op.add_column` na migration de upgrade. Ver Pattern 5 acima.

[ASSUMED: comportamento padrão de Alembic com server_default — verificar contra documentação oficial antes de aplicar]

### Pitfall 6: `_run_ruff_fix` não cobre os novos diretórios `users/` e `families/`

**O que vai errar:** Após renomear os diretórios, `_run_ruff_fix` em `generate_code.py` linha 885 ainda referencia `"user"` e `"family"`. O ruff não roda nos arquivos gerados em `users/` e `families/`, causando falha de lint nos arquivos gerados.

**Como evitar:** Atualizar `_run_ruff_fix` para usar `("users", "families")` em vez de `("user", "family")`.

[VERIFIED: leitura de `scripts/generate_code.py` linha 885]

---

## Code Examples

### Transação atômica de criação de família + owner

```python
# Source: padrão pg_insert de src/caramello/shared/auth.py + lógica de negócio
async def registry_family(
    family_in: FamilyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FamilyRead:
    """FAMILY-01: Cria família e registra o usuário como owner."""
    # Criar Family
    db_family = Family.model_validate(family_in)
    session.add(db_family)
    await session.flush()  # flush para obter db_family.id sem commit

    # Criar FamilyMember com role="owner"
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

### Listagem de famílias do usuário autenticado

```python
# Source: padrão SQLModel select com JOIN
async def list_my_families(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[FamilyRead]:
    """FAMILY-02: Lista famílias onde o usuário é membro."""
    result = await session.exec(
        select(Family)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(FamilyMember.user_id == current_user.id)
    )
    return list(result.all())
```

### Formato do dsl/operations/family.yaml

```yaml
# dsl/operations/family.yaml
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

**Atenção:** O `generate_operations()` atual usa `response_model={domain_class}Read` hardcoded. Como `families` não tem uma classe `FamiliesRead`, o stub gerado precisará de ajuste manual antes de implementar. Isso é normal — stubs gerados são pontos de partida, não código final.

[VERIFIED: leitura de `scripts/generate_code.py` `generate_operations()` função]

---

## State of the Art

| Abordagem Anterior | Abordagem Atual | Quando Mudou | Impacto |
|--------------------|-----------------|-------------|---------|
| `domain: user` / `domain: family` | `domain: users` / `domain: families` | Phase 4 (esta fase) | Diretórios e URLs mudam; todos os imports devem ser atualizados |
| URL `/family_invitation/` (underscore) | URL `/families/family-invitation/` (hifens) | Phase 4 (esta fase) | Breaking change de URL — qualquer cliente hard-coded deve ser atualizado |
| FamilyInvitation com `invitee_email` + `expires_at` | FamilyInvitation com `email` + `status` | Phase 4 (esta fase) | Breaking change de schema — migration obrigatória |
| CRUD gerado sem prefixo de domínio (`/family/`) | CRUD com prefixo de domínio (`/families/family/`) | Phase 4 (esta fase) | Estrutura de URL agora é `/{domain}/{table}/` |

**Depreciado/obsoleto:**
- Diretório `src/caramello/user/` → substituído por `src/caramello/users/` após regeneração
- Diretório `src/caramello/family/` → substituído por `src/caramello/families/` após regeneração
- URLs sem prefixo de domínio (`/user/`, `/family/`, `/family_invitation/`) → substituídas pelo novo padrão

---

## Assumptions Log

| # | Claim | Seção | Risco se Errado |
|---|-------|-------|-----------------|
| A1 | Query JOIN de `select(Family).join(FamilyMember, ...).where(FamilyMember.user_id == current_user.id)` funciona com SQLModel async select | Code Examples — Listagem de famílias | Pode precisar de `join()` com sintaxe alternativa; baixo risco — padrão SQLAlchemy Core amplamente documentado |
| A2 | `session.flush()` antes de `session.commit()` retorna o `id` gerado pelo PostgreSQL para uso imediato | Code Examples — Transação atômica | Se flush não popular `db_family.id`, o INSERT de FamilyMember ficará sem `family_id`; verificar comportamento do asyncpg com autoincrement |
| A3 | Estrutura da migration de upgrade com `server_default` temporário e posterior `alter_column(..., server_default=None)` | Pattern 5 — Alembic migration | Se Alembic não suportar este padrão na versão 1.16.5, a migration precisará de abordagem diferente |
| A4 | `generate_operations()` do generator precisa de ajuste manual no stub de families porque usa `{domain_class}Read` que não existe para `families` | Code Examples — formato family.yaml | O stub gerado pode causar NameError; identificado como ponto de atenção, não bloqueador — stub é ponto de partida |

---

## Open Questions

1. **Comportamento do `session.flush()` com asyncpg e autoincrement**
   - O que sabemos: SQLAlchemy async com asyncpg suporta `flush()` para obter PKs geradas antes do commit
   - O que não está claro: se o SQLModel tem quirks que mudam esse comportamento com `table=True` models
   - Recomendação: testar no Wave 2 com um caso simples antes de comitar ao padrão; alternativa é usar `RETURNING id` via pg_insert se flush não funcionar

2. **Como o generator trata `domain: families` em `generate_operations()`**
   - O que sabemos: `generate_operations()` linha 448 usa `domain.title()` para derivar o class name → `Families` (plural com maiúscula) que não corresponde a nenhuma classe
   - O que não está claro: se isso vai causar erro de geração ou apenas stubs com import incorreto
   - Recomendação: inspecionar o stub gerado após `bin/generate_code` e corrigir manualmente os imports no `operations.py` antes de implementar; a anotação `stub` permite sobrescrever

3. **Comportamento de `FamilyInvitation.email` para usuários JÁ autenticados (não primeiro login)**
   - O que sabemos: o auto-join busca `email == token_email AND status == "pending_login"` em TODA chamada a `get_current_user()`
   - O que não está claro: se o auto-join deve rodar apenas no "primeiro login" (quando o User é criado) ou em toda chamada
   - Recomendação: conforme D-02, o auto-join acontece em toda chamada enquanto existir um invitation `pending_login`; após a primeira execução, o status muda para `"joined"` e não roda mais — design correto

---

## Environment Availability

| Dependência | Requerida por | Disponível | Versão | Fallback |
|-------------|--------------|------------|--------|---------|
| Python 3.10+ | Runtime | ✓ | 3.12.3 | — |
| uv | Build/install | ✓ | (disponível no env) | — |
| PostgreSQL | Alembic migration, testes | N/A | Externo | Banco dev/prod fora do repo — operador deve ter `familia_dev` acessível |
| pytest | Testes | ✓ | 9.0.1 | — |
| ruff | Linting gerado | ✓ | >=0.9.0 | — |
| mypy | Type check | ✓ | >=1.0.0 | — |

**Dependências ausentes sem fallback:**
- PostgreSQL `familia_dev`: necessário para rodar a migration e testes de integração. Não pode ser verificado aqui — operador deve garantir disponibilidade antes de executar Wave 2.

[VERIFIED: leitura de `pyproject.toml` para dependências]

---

## Validation Architecture

### Test Framework

| Propriedade | Valor |
|------------|-------|
| Framework | pytest 9.0.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Comando rápido | `uv run pytest tests/ -x -q` |
| Suite completa | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Comportamento | Tipo de Teste | Comando | Arquivo Existe? |
|--------|--------------|---------------|---------|-----------------|
| FAMILY-01 | `POST /families/registry` cria Family + FamilyMember(role="owner") | unit (mock) | `uv run pytest tests/test_family_operations.py::test_registry_creates_family_and_owner -x` | ❌ Wave 0 |
| FAMILY-02 | `GET /families/families` retorna apenas famílias do usuário | unit (mock) | `uv run pytest tests/test_family_operations.py::test_list_families_only_mine -x` | ❌ Wave 0 |
| FAMILY-03 | `GET /families/families/{uuid}` retorna 403 se não for membro | unit (mock) | `uv run pytest tests/test_family_operations.py::test_get_family_detail_non_member_403 -x` | ❌ Wave 0 |
| FAMILY-07 | `DELETE .../members/{uuid}` com não-owner retorna 403 | unit (mock) | `uv run pytest tests/test_family_operations.py::test_remove_member_non_owner_403 -x` | ❌ Wave 0 |
| D-02 | Auto-join cria FamilyMember quando FamilyInvitation pending existe | unit (mock) | `uv run pytest tests/test_auth.py::test_auto_join_on_login -x` | ❌ Wave 0 |
| D-09/D-10 | URLs geradas usam hifens e prefixo de domínio | unit | `uv run pytest tests/test_generator.py::test_router_url_has_domain_prefix_and_hyphens -x` | ❌ Wave 0 |

### Sampling Rate

- **Por task commit:** `uv run pytest tests/ -x -q --ignore=tests/test_api`
- **Por wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_family_operations.py` — cobre FAMILY-01, 02, 03, 07; usa `app.dependency_overrides[get_current_user]` (padrão estabelecido em `tests/test_user_operations.py`)
- [ ] `tests/test_auth.py` — adicionar `test_auto_join_on_login` ao arquivo existente
- [ ] `tests/test_generator.py` — adicionar `test_router_url_has_domain_prefix_and_hyphens` ao arquivo existente

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Aplica | Controle Padrão |
|---------------|--------|-----------------|
| V2 Authentication | Sim | `get_current_user()` via PyJWT + JWKS — já implementado em Phase 3 |
| V3 Session Management | Não | JWT stateless — sem sessão server-side |
| V4 Access Control | Sim | Verificação de role="owner" antes de operações restritas (pre-register, remove-member) |
| V5 Input Validation | Sim | Pydantic/FastAPI valida automaticamente bodies e path params; EmailStr para campo `email` de FamilyInvitation |
| V6 Cryptography | Não | Sem operações cripto nesta fase |

### Known Threat Patterns

| Pattern | STRIDE | Mitigação Padrão |
|---------|--------|-----------------|
| Acesso a família de outro usuário | Spoofing/Escalação | Verificar membership em TODOS os endpoints de detalhe/membership |
| Remoção de membro por não-owner | Escalação de Privilégio | Verificação `role == "owner"` antes de DELETE — retorna 403 explicitamente |
| Pre-registro por não-owner | Escalação de Privilégio | Mesma verificação de owner em `POST .../pre-register` |
| Enumeração de famílias | Information Disclosure | `GET /families/families` filtra por membership — nunca retorna famílias de terceiros |
| Auto-join com email falsificado | Spoofing | Email vem do JWT validado pelo Keycloak — não pode ser injetado pelo cliente |

---

## Sources

### Primary (HIGH confidence)

- Leitura direta de `src/caramello/shared/auth.py` — padrão JIT provisioning, TYPE_CHECKING, import circular
- Leitura direta de `scripts/generate_code.py` — toda a lógica do generator, `generate_operations()`, `_run_ruff_fix`
- Leitura direta de `src/caramello/user/operations.py` — padrão APIRouter com anotação CARAMELLO-GENERATED
- Leitura direta de `src/caramello/main.py` — ordem de registro de routers, lifespan
- Leitura direta de `alembic/versions/20260524_0138_initial_schema.py` — schema atual das tabelas
- Leitura direta de `src/caramello/family/models.py` — modelos atuais FamilyInvitation com campos a remover
- Leitura direta de `.planning/phases/04-dom-nio-family/04-CONTEXT.md` — decisões travadas D-01 a D-13
- Leitura direta de `tests/test_user_operations.py` — padrão `dependency_overrides` para testes sem Keycloak

### Secondary (MEDIUM confidence)

- `.planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-CONTEXT.md` — contexto de decisões da Phase 3

### Tertiary (LOW confidence)

- Nenhum — todas as afirmações críticas verificadas diretamente no código

---

## Metadata

**Breakdown de confiança:**
- Standard stack: HIGH — verificado em `pyproject.toml` e código existente
- Architecture: HIGH — verificado via leitura direta de todos os módulos afetados
- Pitfalls: HIGH para pitfalls 1-4 e 6 (verificados no código); MEDIUM para pitfall 5 (Alembic server_default — ASSUMED)
- Assumptions: 4 items marcados — todos de baixo risco ou com alternativa documentada

**Data de research:** 2026-05-26
**Válido até:** 2026-06-26 (stack estável)
