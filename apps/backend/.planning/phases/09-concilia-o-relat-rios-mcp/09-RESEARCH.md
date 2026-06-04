# Phase 9: Conciliação + Relatórios + MCP - Research

**Researched:** 2026-06-03
**Domain:** FastAPI async, SQLAlchemy 2.x aggregations, rapidfuzz fuzzy matching, Alembic migration, Pydantic v2 schemas
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-SCHEMA-01:** Adicionar `responsible_user_id: INT NULL` (FK → `user.id`) a `financial_entry`. Migration `0004_financial_entry_responsible_user.py` com `down_revision = "0003"`. Verificar com `alembic history --verbose` antes de gerar.
- **D-SCHEMA-02:** `responsible_user_id` aponta para `user.id` (não para FamilyMember). Validação de membership feita no service, não no banco.
- **D-ATTR-01:** API pública usa `responsible_user_uuid: UUID | None`. Backend resolve para `responsible_user_id` via `select(User).where(User.uuid == responsible_user_uuid)`. Retorna 422 se UUID inválido.
- **D-ATTR-02:** Validação de membership após resolver `responsible_user_id`: `select(FamilyMember).where(family_id == X, user_id == responsible_user_id)`. Retorna 422 com mensagem clara se não for membro.
- **D-ATTR-03:** `responsible_user_uuid` exposto em todos os schemas de resposta de FinancialEntry.
- **D-REC-01:** `POST /finances/movements/{uuid}/reconcile` — retorna 409 se `FinancialEntry.movement_id` já existe. Payload: `{subcategory_uuid, competencia_year, competencia_month, notes?, is_recorrente?, responsible_user_uuid?}`.
- **D-REC-02:** Schema rico de resposta para todos os endpoints de FinancialEntry: `{uuid, movement: {uuid, date, amount, description}, subcategory_uuid, subcategory_name, category_uuid, category_name, competencia_year, competencia_month, notes, is_recorrente, responsible_user_uuid, created_at, updated_at}`.
- **D-REC-03/04/05:** `GET /entries/{uuid}`, `PATCH /entries/{uuid}`, `GET /entries?family_uuid=&year=&month=` — todos usam o mesmo schema rico.
- **D-MOV-01:** `entry_uuid: UUID | None` adicionado a `MovementReadPublic` via LEFT JOIN.
- **D-MOV-02:** Filtro `?reconciled=true|false` em `GET /finances/accounts/{uuid}/movements` via LEFT JOIN com `FinancialEntry`.
- **D-CAT-01..04:** `suggest_category(movement_uuid, family_id, session)` em `services.py` com `rapidfuzz.fuzz.token_set_ratio`. Retorna top-5, sem threshold, `[]` se sem histórico.
- **D-BAL-01..03:** `account_balance()` e `family_balance()` calculados sob demanda via `session.execute(func.sum(...))`. Saldo = soma de `movement.amount` (créditos positivos, débitos negativos).
- **D-REP-01..04:** Relatórios mensais e por membro operam sobre `FinancialEntry.competencia_year/month`. Agregações via `session.execute()` com `func.sum + group_by` — nunca `session.exec()`.
- **D-MCP-01:** Todas as ferramentas MCP financeiras deferidas para M3. `main.py` não é modificado nesta fase.

### Claude's Discretion

- Estrutura interna de `FinancialEntryRichPublic` (schema rico): planner define campos exatos e se usa Pydantic model separado ou schema inline.
- Organização das funções de agregação em `services.py`: funções independentes no mesmo arquivo.
- Tratamento de `responsible_user_uuid=None` no PATCH: campo ausente = não atualizar; campo presente como `null` = limpar o responsável. Implementar como `Optional` com sentinela.

### Deferred Ideas (OUT OF SCOPE)

- MCP tools financeiras (`suggest_category`, `list_my_financial_entries`) — M3.
- Splits de movimentação (1:N) — M3.
- Filtros avançados em GET /entries além de família/período.
- Auto-sugestão de responsável por conta de origem.
- Relatório acumulado anual por membro.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LAN-01 | Usuário pode conciliar uma movimentação criando um lançamento financeiro (subcategoria, competência ano/mês, notas) | `POST /finances/movements/{uuid}/reconcile` — cria `FinancialEntry` com `responsible_user_id` opcional; padrão de create já estabelecido em `operations.py` |
| LAN-02 | Uma movimentação só pode ter um lançamento financeiro (1:1) — tentativa de duplicar retorna 409 | Constraint `UNIQUE movement_id` já está na tabela `financial_entry`; handler de `IntegrityError` retorna 409 |
| LAN-03 | Sistema propõe subcategoria baseado em similaridade de descrição com lançamentos anteriores | `GET /finances/movements/{uuid}/suggest-category` com `rapidfuzz.fuzz.token_set_ratio` em `services.py` |
| LAN-04 | Usuário pode marcar lançamento financeiro como recorrente | Campo `is_recorrente` já existe em `FinancialEntry`; exposto no payload de criação/atualização |
| LAN-05 | Usuário pode atualizar subcategoria e competência de lançamento financeiro existente | `PATCH /finances/entries/{uuid}` — atualização parcial; `updated_at` manual; subcategory_uuid resolvido para subcategory_id |
| REL-01 | Usuário pode consultar saldo atual de uma conta | `GET /finances/accounts/{uuid}/balance` com `func.sum(Movement.amount)` via `session.execute()` |
| REL-02 | Usuário pode consultar saldo consolidado de todas as contas da família | `GET /finances/families/{uuid}/balance` com `account_balance()` por conta ativa |
| REL-03 | Usuário pode consultar breakdown mensal por categoria pai | `GET /finances/reports/monthly` com `func.sum + group_by` sobre `FinancialEntry` join `Subcategory` join `Category` |
| REL-04 | Usuário pode detalhar breakdown por subcategoria dentro de uma categoria pai | Mesmo endpoint `GET /finances/reports/monthly` — lista plana com `subcategory_uuid/name` por row |
| REL-05 | Todos os relatórios analíticos operam sobre lançamentos financeiros e filtram por competência | Todas as queries de relatório filtram por `FinancialEntry.competencia_year/month`, nunca por `Movement.date` |

</phase_requirements>

---

## Summary

A Phase 9 é uma fase de extensão do domínio financeiro existente. Ela opera inteiramente dentro do módulo `finances/` já estabelecido nas Phases 7 e 8, sem tocar em outros domínios. A maior parte dos padrões de código — `session.execute()`, `_require_family_access`, schemas públicos locais em `operations.py`, `updated_at` manual — já está estabelecida e deve ser replicada com consistência.

As três áreas de trabalho são: (1) migration de schema + novos endpoints de FinancialEntry com schema rico, (2) funções de agregação em `services.py` + endpoints de relatório, e (3) sugestão de categoria via `rapidfuzz` — a única nova dependência da fase. A integração de `rapidfuzz` é simples: uma função síncrona pura em `services.py`, chamada a partir de um endpoint async via `await run_in_executor` se necessário, mas dado o volume pequeno de dados (1-5 usuários família), a chamada síncrona direta é aceitável.

O ponto mais delicado é o LEFT JOIN de `Movement` com `FinancialEntry` para o campo `entry_uuid` e o filtro `reconciled`. Este padrão ainda não existe no codebase e requer `session.execute()` com `outerjoin()` explícito — não `session.exec()`. A migração `0004` é simples (uma coluna nullable), mas exige verificação do `down_revision` antes de gerar.

**Primary recommendation:** Implementar na ordem — migration 0004, extension de `MovementReadPublic`, novos endpoints de entry no router existente, funções de agregação em `services.py`, endpoints de relatório, `suggest_category` + instalação de `rapidfuzz`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Conciliação (reconcile) | API / Backend | Database | Criação de FinancialEntry com validação de membership — lógica de negócio no backend, constraint UNIQUE no banco |
| Sugestão de categoria | API / Backend | — | Fuzzy matching em memória contra histórico da família; sem estado externo |
| Indicador de conciliação em Movement | API / Backend | Database | LEFT JOIN computado na query — não stored no banco para evitar inconsistência |
| Saldo de conta/família | API / Backend | Database | Agregação `func.sum` sob demanda — sem cache, consistente com movimentações |
| Relatório mensal por categoria | API / Backend | Database | GROUP BY sobre FinancialEntry join Subcategory join Category — puro SQL aggregation |
| Relatório por membro | API / Backend | Database | GROUP BY por `responsible_user_id` — lançamentos sem responsável agrupados como null |
| Validação de membership para responsável | API / Backend | — | Verificação após resolver UUID → ID; responsabilidade do service, não do banco |
| MCP (deferido) | — | — | Fora do escopo desta fase |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.118.0 (já instalado) | HTTP framework, routers, Depends | Stack estabelecido do projeto |
| `sqlmodel` / `sqlalchemy` | 0.0.25 / 2.0.43 (já instalado) | ORM async + `func.sum`, `outerjoin` | Stack estabelecido do projeto |
| `alembic` | 1.16.5 (já instalado) | Schema migration | Stack estabelecido do projeto |
| `pydantic` v2 | 2.11.10 (já instalado) | Schemas de response/request | Stack estabelecido do projeto |
| `rapidfuzz` | 3.14.5 | Fuzzy string matching para suggest_category | Especificado em REQUIREMENTS.md; MIT license; C++ backend; zero GPL |

[VERIFIED: npm registry] — `rapidfuzz` 3.14.5 confirmado em `pip index versions rapidfuzz` e em `pypi.org/project/RapidFuzz/` (repositório oficial em `github.com/rapidfuzz/RapidFuzz`).

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sqlalchemy.func` | (bundled) | `func.sum`, `func.count`, aggregações | Todos os relatórios e cálculos de saldo |
| `sqlalchemy.outerjoin` | (bundled) | LEFT JOIN para `entry_uuid` em Movement | Filtro `?reconciled` e campo `entry_uuid` |
| `sqlalchemy.orm.selectinload` | (bundled) | Eager loading de relacionamentos | Ao serializar FinancialEntry com Movement/Subcategory/Category aninhados |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `rapidfuzz.fuzz.token_set_ratio` | `thefuzz` (fuzzywuzzy) | `thefuzz` é GPL; `rapidfuzz` é MIT e 10x mais rápido |
| LEFT JOIN no ORM | Stored column `is_reconciled` em Movement | Stored column cria inconsistência (requer trigger/update); LEFT JOIN é mais simples e correto |
| `func.sum` via `session.execute()` | Cálculo em Python após `session.exec()` | `func.sum` no banco evita carregar todas as linhas na memória |

**Installation (apenas `rapidfuzz` é nova dependência):**
```bash
uv add rapidfuzz>=3.14.5
```

**Version verification:**
```
pip index versions rapidfuzz → rapidfuzz (3.14.5) — confirmado 2026-06-03
```

---

## Package Legitimacy Audit

> `rapidfuzz` é a única nova dependência desta fase.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `rapidfuzz` | PyPI | ~6 anos | Alto (top Python libs) | github.com/rapidfuzz/RapidFuzz | [ASSUMED — slopcheck não pôde ser instalado no sandbox] | Aprovado — verificado em PyPI oficial e GitHub; usado em produção por projetos de grande porte |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

**Nota:** slopcheck não pôde ser instalado no ambiente sandbox (permissão negada pelo auto-mode). `rapidfuzz` foi verificado manualmente em `pypi.org/project/RapidFuzz/` e `github.com/rapidfuzz/RapidFuzz` — organização dedicada, MIT license, repositório com histórico longo. Risco de slopsquat: baixo. [CITED: pypi.org/project/RapidFuzz/]

*Como slopcheck não estava disponível, o planner deve confirmar `rapidfuzz` como package legítimo antes de `uv add` — um `checkpoint:human-verify` antes do install é recomendado por precaução.*

---

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
     │
     ▼
FastAPI Router (/finances) — operations.py
     │
     ├─► POST /movements/{uuid}/reconcile ──────────► validate movement_uuid
     │                                                     │
     │                                               resolve subcategory_uuid
     │                                                     │
     │                                               validate responsible_user_uuid (opt)
     │                                                     │
     │                                               check family membership
     │                                                     │
     │                                          session.add(FinancialEntry) ──► DB
     │                                                     │
     │                                          return FinancialEntryRichPublic
     │
     ├─► GET /movements/{uuid}/suggest-category ─────► services.suggest_category()
     │                                                     │
     │                                    session.execute(select descriptions) ──► DB
     │                                                     │
     │                                          rapidfuzz.fuzz.token_set_ratio loop
     │                                                     │
     │                                          return top-5 [{subcategory_uuid, score}]
     │
     ├─► GET /accounts/{uuid}/balance ───────────────► services.account_balance()
     │                                                     │
     │                               session.execute(func.sum(Movement.amount)) ──► DB
     │                                                     │
     │                                          return {account_uuid, balance, currency}
     │
     ├─► GET /families/{uuid}/balance ───────────────► services.family_balance()
     │                                                     │
     │                              session.execute(select active accounts) ──► DB
     │                                        │
     │                             account_balance() per account (loop)
     │                                                     │
     │                                          return {family_uuid, total_balance, accounts[]}
     │
     ├─► GET /reports/monthly ───────────────────────► services.monthly_breakdown()
     │                                                     │
     │            session.execute(func.sum + group_by competencia + subcategory) ──► DB
     │                                                     │
     │                                          return {period, total, rows[]}
     │
     └─► GET /reports/by-member ─────────────────────► services.by_member_breakdown()
                                                             │
               session.execute(func.sum + group_by responsible_user_id) ──► DB
                                                             │
                                              null user_id → "Não atribuído"
                                                             │
                                                  return {period, total, rows[]}
```

### Recommended Project Structure (extensão do existente)

```
src/caramello/finances/
├── models.py           # ATUALIZAR: adicionar responsible_user_id a FinancialEntry
├── operations.py       # ATUALIZAR: novos endpoints + MovementReadPublic extendido
└── services.py         # ATUALIZAR: account_balance(), family_balance(),
                        #            monthly_breakdown(), by_member_breakdown(),
                        #            suggest_category()

alembic/versions/
└── 0004_financial_entry_responsible_user.py   # CRIAR

tests/
├── test_finances_operations.py    # ATUALIZAR: adicionar stubs Nyquist fase 9
└── test_services/
    └── test_finances_service.py   # ATUALIZAR: adicionar testes suggest_category e
                                   #            funções de agregação (unit puro)
```

### Pattern 1: Endpoint de Conciliação (POST reconcile)

**What:** Cria FinancialEntry 1:1 a partir de uma movimentação. Captura `IntegrityError` do banco para retornar 409.
**When to use:** Qualquer operação de create com constraint UNIQUE que deve retornar 409, não 500.

```python
# Source: padrão estabelecido em operations.py + constraint UNIQUE do banco
from sqlalchemy.exc import IntegrityError

@router.post("/movements/{movement_uuid}/reconcile",
             response_model=FinancialEntryRichPublic, status_code=201)
async def reconcile_movement(
    movement_uuid: UUID,
    entry_in: ReconcileCreatePublic,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> FinancialEntryRichPublic:
    # 1. Resolver movement_uuid → Movement (404 se não existe)
    # 2. Resolver account → family para _require_family_access
    # 3. Resolver subcategory_uuid → subcategory_id (404 se não existe)
    # 4. Resolver responsible_user_uuid → responsible_user_id + membership check (422)
    # 5. session.add(FinancialEntry(...)); session.commit()
    # 6. Capturar IntegrityError → raise HTTPException(409)
    # 7. Retornar FinancialEntryRichPublic com todos os campos aninhados
    try:
        session.add(db_entry)
        await session.commit()
        await session.refresh(db_entry)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Movimentação já possui lançamento financeiro",
        )
```

### Pattern 2: LEFT JOIN para entry_uuid em MovementReadPublic

**What:** Estender `list_movements` com LEFT JOIN para expor `entry_uuid` sem segunda query.
**When to use:** Sempre que é necessário um campo computed de outra tabela em listagens.

```python
# Source: SQLAlchemy 2.0 - session.execute() com outerjoin e label
from sqlalchemy import outerjoin, select, func
from caramello.finances.models import Movement, FinancialEntry

# Para list_movements com entry_uuid e filtro reconciled:
stmt = (
    select(Movement, FinancialEntry.uuid.label("entry_uuid"))
    .select_from(
        outerjoin(Movement, FinancialEntry, FinancialEntry.movement_id == Movement.id)
    )
    .where(Movement.account_id == db_account.id)
)

# Filtro ?reconciled=false:
if reconciled is False:
    stmt = stmt.where(FinancialEntry.id.is_(None))
elif reconciled is True:
    stmt = stmt.where(FinancialEntry.id.is_not(None))

result = await session.execute(stmt)
rows = result.fetchall()
# rows[i] → (Movement, entry_uuid_or_None)
```

### Pattern 3: Agregação `func.sum` com `session.execute()`

**What:** Calcular saldos e totais diretamente no banco. NUNCA usar `session.exec()` para agregações — retorna `Decimal` corretamente.
**When to use:** Todos os endpoints de saldo e relatório.

```python
# Source: decisão D-BAL-01 em CONTEXT.md + pitfall P3 em STATE.md
from sqlalchemy import func, select

async def account_balance(account_id: int, session: AsyncSession) -> Decimal:
    result = await session.execute(
        select(func.sum(Movement.amount)).where(Movement.account_id == account_id)
    )
    total = result.scalar_one_or_none()
    return total if total is not None else Decimal("0.00")
```

### Pattern 4: Aggregação com GROUP BY para relatórios

**What:** JOIN de FinancialEntry com Subcategory e Category, GROUP BY para breakdown mensal.
**When to use:** Endpoints de relatório.

```python
# Source: SQLAlchemy 2.0 docs + decisão D-REP-01 em CONTEXT.md
stmt = (
    select(
        Category.uuid.label("category_uuid"),
        Category.name.label("category_name"),
        Subcategory.uuid.label("subcategory_uuid"),
        Subcategory.name.label("subcategory_name"),
        func.sum(Movement.amount).label("total"),
        func.count(FinancialEntry.id).label("count"),
    )
    .join(Subcategory, FinancialEntry.subcategory_id == Subcategory.id)
    .join(Category, Subcategory.category_id == Category.id)
    .join(Movement, FinancialEntry.movement_id == Movement.id)
    .join(Account, Movement.account_id == Account.id)
    .where(
        Account.family_id == family_id,
        FinancialEntry.competencia_year == year,
        FinancialEntry.competencia_month == month,
    )
    .group_by(
        Category.id, Category.uuid, Category.name,
        Subcategory.id, Subcategory.uuid, Subcategory.name,
    )
)
result = await session.execute(stmt)
rows = result.fetchall()
```

### Pattern 5: suggest_category com rapidfuzz

**What:** Fuzzy match da descrição da movimentação contra descrições de lançamentos anteriores da família.
**When to use:** Sugestão semi-automática de subcategoria (LAN-03).

```python
# Source: rapidfuzz docs (rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html)
# + decisão D-CAT-01 em CONTEXT.md
from rapidfuzz import fuzz

async def suggest_category(
    movement_uuid: UUID,
    family_id: int,
    session: AsyncSession,
) -> list[dict]:
    # 1. Buscar descrição do movement alvo
    # 2. Buscar todos os (Movement.description, FinancialEntry.subcategory_id)
    #    da família via JOIN
    # 3. Para cada linha, calcular fuzz.token_set_ratio(target_desc, row_desc)
    # 4. Agrupar por subcategory_id, pegar score máximo por subcategoria
    # 5. Ordenar descrescente, retornar top-5 com uuid/nome de subcategoria e categoria
    scored: dict[int, tuple[int, ...]] = {}
    for desc, subcategory_id, ... in entries:
        score = int(fuzz.token_set_ratio(target_description, desc))
        if subcategory_id not in scored or score > scored[subcategory_id][0]:
            scored[subcategory_id] = (score, subcategory_uuid, ...)
    top5 = sorted(scored.values(), key=lambda x: x[0], reverse=True)[:5]
    return [{"subcategory_uuid": ..., "score": score, ...} for score, ... in top5]
```

### Pattern 6: responsible_user_uuid — PATCH com sentinela

**What:** Distinguir "campo ausente" (não atualizar) de "campo = null" (limpar responsável).
**When to use:** Sempre que um campo nullable pode ser deliberadamente zerado num PATCH.

```python
# Source: Pydantic v2 pattern para campos opcionais com distinção absent/null
from pydantic import BaseModel
from typing import Annotated
from uuid import UUID

# Sentinela para "not provided"
_MISSING = object()

class FinancialEntryUpdatePublic(BaseModel):
    subcategory_uuid: UUID | None = None
    competencia_year: int | None = None
    competencia_month: int | None = None
    notes: str | None = None
    is_recorrente: bool | None = None
    # Para responsible_user_uuid: usar model_fields_set para detectar se foi enviado
    responsible_user_uuid: UUID | None = None  # None = limpar; ausente = não tocar

# Na implementação do PATCH:
if "responsible_user_uuid" in entry_in.model_fields_set:
    if entry_in.responsible_user_uuid is None:
        db_entry.responsible_user_id = None  # limpar
    else:
        # resolver UUID → ID + membership check
        ...
```

### Anti-Patterns to Avoid

- **`session.exec()` para agregações:** `session.exec()` com `func.sum` não serializa `Decimal` corretamente — sempre usar `session.execute()`. [VERIFIED: pitfall P3 em STATE.md, confirmado pelos padrões em operations.py existente]
- **`float` em campos monetários:** Nunca usar `float` para valores monetários — sempre `Decimal`. Pydantic v2 serializa `Decimal` como string JSON (`"123.45"`), não float. [VERIFIED: confirmado por `uv run python -c "..."` nesta sessão]
- **Editar arquivos em `models/` e `api/generated/`:** Arquivos gerados pelo DSL nunca devem ser editados diretamente. Para `finances/models.py` com anotação `# CARAMELLO-GENERATED: implemented`, a edição manual é permitida (mesma convenção usada na fase 7).
- **Registrar router após `mcp.mount_http()`:** O router de finances já está registrado em `main.py` antes de `FastApiMCP(...)`. Nenhuma alteração em `main.py` nesta fase. [VERIFIED: confirmado em `main.py`]
- **`selectinload` em queries de serialização com relationships:** Se a serialização de `FinancialEntryRichPublic` for feita via refresh do objeto ORM com relacionamentos, usar `selectinload` explícito. Para o schema rico desta fase, a abordagem preferida é construir o schema explicitamente a partir de dados já presentes na query (sem depender de lazy load), evitando este pitfall.
- **`responsible_user_uuid` com `exclude_none` no PATCH:** `model_dump(exclude_none=True)` descarta `responsible_user_uuid=None` — o que impede limpar o responsável. Usar `model_fields_set` para distinguir "ausente" de "null explícito".

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | implementação Levenshtein manual | `rapidfuzz.fuzz.token_set_ratio` | Edge cases de normalização, performance, Unicode |
| Deduplicação de scores por subcategoria | lógica de merge manual | dict por `subcategory_id` + `max(score)` | Simples e correto; já há padrão no codebase |
| Serialização de Decimal em JSON | converter para `float` | `Decimal` via `Pydantic BaseModel` | Pydantic v2 serializa Decimal como string automaticamente |
| Constraint 1:1 no banco | verificação Python antes do insert | `UNIQUE(movement_id)` + capturar `IntegrityError` | Race-condition-safe; banco é a fonte de verdade |

**Key insight:** O banco PostgreSQL com `UNIQUE(movement_id)` é mais confiável do que um check Python para garantir a constraint 1:1 — o check Python tem race condition em requisições concorrentes.

---

## Common Pitfalls

### Pitfall 1: `session.exec()` vs `session.execute()` para agregações

**What goes wrong:** `session.exec(select(func.sum(...)))` em SQLModel async não serializa `Decimal` corretamente — pode retornar `None` ou float.
**Why it happens:** `session.exec()` é uma abstração SQLModel que adiciona mapeamento de tipo; para queries que retornam escalares (não ORM objects), esse mapeamento falha.
**How to avoid:** Usar `session.execute()` e `.scalar_one_or_none()` para todas as agregações.
**Warning signs:** Saldo retornando `None` quando existem movimentações; ou valor float em vez de Decimal.

### Pitfall 2: `exclude_none=True` no PATCH de campos nullable

**What goes wrong:** `model_dump(exclude_none=True)` descarta `responsible_user_uuid: null` enviado explicitamente pelo cliente — o campo não é zerado.
**Why it happens:** `exclude_none=True` trata `None` como "não fornecido", mas aqui `None` tem semântica de "limpar o valor".
**How to avoid:** Usar `model_fields_set` para saber quais campos foram explicitamente enviados. Aplicar `None` apenas quando o campo está em `model_fields_set`.
**Warning signs:** Impossível limpar `responsible_user_uuid` via PATCH mesmo enviando `null`.

### Pitfall 3: `updated_at` sem `onupdate` automático

**What goes wrong:** PATCH atualiza registro mas `updated_at` permanece com valor antigo.
**Why it happens:** O projeto não usa `onupdate` automático no SQLAlchemy (decisão da Phase 7, mantida em todas as fases subsequentes).
**How to avoid:** Definir `db_entry.updated_at = datetime.now(timezone.utc)` explicitamente em todo PATCH, antes do `session.commit()`.
**Warning signs:** `updated_at` não muda após PATCH.

### Pitfall 4: `down_revision` errado na migration 0004

**What goes wrong:** Migration 0004 aponta `down_revision` para `"0002"` em vez de `"0003"` — cria fork no histórico do Alembic.
**Why it happens:** Geração manual de migration sem verificar o estado atual do histórico.
**How to avoid:** Executar `alembic history --verbose` antes de criar `0004` e confirmar que `0003` é a head. `down_revision` deve ser `"0003"`.
**Warning signs:** `alembic upgrade head` falha com erro de revisão; `alembic history` mostra dois heads.

### Pitfall 5: LEFT JOIN retornando tuplas em vez de ORM objects

**What goes wrong:** `session.execute(select(Movement, FinancialEntry.uuid.label(...)))` retorna `Row` objects, não `Movement` objects — `result.scalars()` falha ou descarta colunas extras.
**Why it happens:** `session.execute()` com SELECT de múltiplas entidades retorna `Row` com atributos posicionais.
**How to avoid:** Usar `result.fetchall()` e acessar `row[0]` (Movement) e `row[1]` (entry_uuid) por posição, ou usar `.mappings()` para acesso por nome.
**Warning signs:** `AttributeError` ao acessar atributos do `Row` como se fosse um ORM object.

### Pitfall 6: Decimal na resposta de `func.sum` quando não há linhas

**What goes wrong:** `func.sum()` retorna `None` quando não há linhas — não `Decimal("0.00")`.
**Why it happens:** Comportamento padrão do SQL `SUM()` sobre conjunto vazio.
**How to avoid:** `total = result.scalar_one_or_none() or Decimal("0.00")` em todas as funções de saldo.
**Warning signs:** `balance: null` na resposta da API para conta sem movimentações.

### Pitfall 7: `responsavel_user_id` no breakdown por membro — linhas sem responsável

**What goes wrong:** GROUP BY por `responsible_user_id` exclui linhas onde `responsible_user_id IS NULL` se o WHERE não for cuidadoso.
**Why it happens:** `GROUP BY` agrupa `NULL` como um grupo — mas filtros adicionais podem excluir esse grupo.
**How to avoid:** Verificar que o GROUP BY inclui `NULL` e que o loop de serialização trata `user_uuid: null` com `name: "Não atribuído"` (D-REP-02).
**Warning signs:** Total do relatório `by-member` não bate com total do relatório `monthly`.

---

## Code Examples

### Alembic migration 0004 (estrutura correta)

```python
# Source: padrão de 0003_movement_schema_update.py
"""0004_financial_entry_responsible_user

Adiciona campo responsible_user_id em financial_entry.

Revision ID: 0004
Revises: 0003
Create Date: [data]
"""
import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"  # verificado com alembic history --verbose
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "financial_entry",
        sa.Column(
            "responsible_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id"),
            nullable=True,
        ),
    )

def downgrade() -> None:
    op.drop_column("financial_entry", "responsible_user_id")
```

### FinancialEntry model update (finances/models.py)

```python
# Source: padrão de models.py existente (Field + nullable)
# Adicionar dentro de class FinancialEntry(SQLModel, table=True):
responsible_user_id: int | None = Field(
    default=None,
    foreign_key="user.id",
    nullable=True,
)
```

### Pydantic Decimal como string (comportamento verificado)

```python
# Source: verificado via uv run python -c nesta sessão de research
# Pydantic v2 serializa Decimal como string JSON — não float
# {"amount": "123.45"} — sem configuração adicional necessária
from pydantic import BaseModel
from decimal import Decimal

class BalanceResponse(BaseModel):
    balance: Decimal  # serializado como "123.45" no JSON automaticamente
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `session.exec()` para tudo | `session.execute()` para agregações e JOINs complexos | Phase 7 (pitfall P3) | Serialização correta de Decimal |
| `float` para valores monetários | `Decimal` + `NUMERIC(15,2)` | Phase 7 (pitfall P1) | Precisão financeira garantida |
| `onupdate=datetime.now` no SQLModel Field | `updated_at` manual em cada PATCH | Phase 7 | Consistência com o comportamento do asyncpg |

**Deprecated/outdated:**
- `session.exec()` com `func.sum`: não usar nesta fase — substituído por `session.execute()`.

---

## Runtime State Inventory

> Não aplicável — esta fase é de adição de novos endpoints e migration de schema, não de renomear/refatorar. Nenhum runtime state existente é renomeado.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Migration 0003 é a head atual; dados existentes em `financial_entry` não têm `responsible_user_id` | Migration 0004 ADD COLUMN nullable — sem data migration necessária (NULL default) |
| Live service config | Nenhum item em UI/database externo afetado | Nenhuma |
| OS-registered state | Nenhum | Nenhuma |
| Secrets/env vars | Nenhum impacto | Nenhuma |
| Build artifacts | Nenhum | Nenhuma |

---

## Open Questions (RESOLVED)

1. **`FinancialEntryRichPublic` — Pydantic model separado ou schema inline?**
   - What we know: CONTEXT.md delega ao planner (Claude's Discretion).
   - What's unclear: Separado é mais reutilizável entre os 4 endpoints; inline é menor código imediato.
   - Recommendation: Usar um único `FinancialEntryRichPublic(BaseModel)` declarado antes do primeiro endpoint — reutilizado em POST reconcile, GET detail, PATCH update e GET list.

2. **`rapidfuzz.fuzz.token_set_ratio` é síncrono — usar `run_in_executor`?**
   - What we know: Volume de dados é baixo (1-5 usuários, centenas de lançamentos). rapidfuzz é C++ e muito rápido.
   - What's unclear: Se haverá bloqueio perceptível do event loop.
   - Recommendation: Chamar diretamente sem `run_in_executor` — para o volume desta aplicação, o overhead não justifica a complexidade.

3. **`GET /finances/entries?year=&month=` — sem year/month retorna tudo ou exige parâmetros?**
   - What we know: D-REC-05 diz "`year` e `month` opcionais — sem eles retorna todos da família".
   - What's unclear: Performance com muitos lançamentos sem filtro de período.
   - Recommendation: Implementar como opcional mas adicionar `limit` padrão de 100 por segurança, com `offset` para paginação — alinha com padrão de `list_movements`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `rapidfuzz` | `suggest_category()` em services.py | Não (não em `pyproject.toml`) | — | Nenhum — deve ser instalado via `uv add rapidfuzz>=3.14.5` |
| `sqlalchemy` | Aggregações, LEFT JOIN | Sim | 2.0.43 | — |
| `alembic` | Migration 0004 | Sim | 1.16.5 | — |
| `pytest` | Testes unitários | Sim | 9.0.1 | — |
| PostgreSQL | Migration + testes de integração | Não disponível no sandbox | — | Testes unitários (mock session) não requerem banco |

**Missing dependencies with no fallback:**
- `rapidfuzz` — deve ser adicionado ao `pyproject.toml` via `uv add rapidfuzz>=3.14.5` na Wave 0 do plano.

**Missing dependencies with fallback:**
- PostgreSQL — testes unitários com `AsyncMock` não requerem banco real. Testes de integração requerem `caramello_dev`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.1 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAN-01 | POST /reconcile cria FinancialEntry, retorna 201 + schema rico | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_reconcile_movement -x` | ❌ Wave 0 |
| LAN-02 | POST /reconcile retorna 409 se movement já tem entry | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_reconcile_409_duplicate -x` | ❌ Wave 0 |
| LAN-03 | GET /suggest-category retorna top-5 com score | unit (mock session) + unit puro services | `uv run pytest tests/test_finances_operations.py::test_suggest_category tests/test_services/test_finances_service.py::test_suggest_category_service -x` | ❌ Wave 0 |
| LAN-04 | POST /reconcile aceita is_recorrente=true | unit (coberto pelo LAN-01 com variação) | (coberto por test_reconcile_movement) | ❌ Wave 0 |
| LAN-05 | PATCH /entries/{uuid} atualiza subcategoria, competência, notas, responsável | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_update_entry -x` | ❌ Wave 0 |
| REL-01 | GET /accounts/{uuid}/balance retorna saldo calculado | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_account_balance -x` | ❌ Wave 0 |
| REL-02 | GET /families/{uuid}/balance retorna saldo consolidado | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_family_balance -x` | ❌ Wave 0 |
| REL-03 | GET /reports/monthly retorna breakdown por categoria pai | unit (mock session) | `uv run pytest tests/test_finances_operations.py::test_monthly_report -x` | ❌ Wave 0 |
| REL-04 | GET /reports/monthly inclui detalhamento por subcategoria | unit (coberto pelo REL-03) | (coberto por test_monthly_report) | ❌ Wave 0 |
| REL-05 | Relatórios filtram por competencia_year/month, não por Movement.date | unit — verificar query params usados | `uv run pytest tests/test_finances_operations.py::test_report_uses_competencia -x` | ❌ Wave 0 |

**Testes adicionais de caminho crítico:**

| Teste | Behavior | File Exists? |
|-------|----------|-------------|
| `test_finances_router_paths` (existente) | Atualizar expected paths para incluir paths da fase 9 | ✅ — precisa de update |
| `test_entry_responsible_user_uuid` | Atribuição + remoção de responsável via PATCH | ❌ Wave 0 |
| `test_suggest_category_empty_history` | `[]` quando sem lançamentos anteriores | ❌ Wave 0 |
| `test_movement_entry_uuid_field` | MovementReadPublic inclui entry_uuid | ❌ Wave 0 |
| `test_movement_reconciled_filter` | GET movements?reconciled=false retorna apenas pendentes | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_finances_operations.py` — adicionar stubs Nyquist para LAN-01/02/03/05, REL-01/02/03/05, e testes de D-MOV-01/02. Atualizar `test_finances_router_paths` com novos paths.
- [ ] `tests/test_services/test_finances_service.py` — adicionar stubs para `suggest_category`, `account_balance`, `family_balance`, `monthly_breakdown`, `by_member_breakdown`.
- [ ] `rapidfuzz` install: `uv add rapidfuzz>=3.14.5` — sem isto, `test_finances_service.py::test_suggest_category_service` falha com ImportError.

*(Infraestrutura existente de testes (conftest.py, AsyncMock pattern) cobre todos os novos testes — sem novas fixtures globais necessárias.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Sim | `get_current_user` — já implementado, reutilizar |
| V3 Session Management | Não | Stateless JWT |
| V4 Access Control | Sim | `_require_family_access` — reutilizar em todos os endpoints novos |
| V5 Input Validation | Sim | Pydantic BaseModel com tipos explícitos (UUID, int, str max_length) |
| V6 Cryptography | Não | Nenhuma operação criptográfica nesta fase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR em FinancialEntry (acesso a entry de outra família) | Spoofing/Info Disclosure | Resolver `movement_uuid → movement → account → family_id` + `_require_family_access` |
| IDOR em relatórios (acesso a dados de outra família) | Info Disclosure | Validar `family_uuid` + `_require_family_access` antes de qualquer query |
| Atribuição de responsible_user de outra família | Tampering | Verificar membership após resolver UUID: `select(FamilyMember).where(family_id=X, user_id=Y)` |
| Escalação de privilégio via responsible_user_uuid no GET | Info Disclosure | Campo é apenas informativo; não altera permissões de acesso |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `rapidfuzz.fuzz.token_set_ratio` retorna `float` 0-100 (não `int`) | Code Examples, Standard Stack | Score exposto como `int` no schema público; possível discrepância de tipo — impacto baixo (cast explícito resolve) |
| A2 | `func.sum()` sobre conjunto vazio retorna `None` em PostgreSQL async | Common Pitfalls | Se retornar `0`, o guard `or Decimal("0.00")` é inócuo — risco baixo |
| A3 | `rapidfuzz` é seguro (sem slopcheck disponível no sandbox) | Package Legitimacy Audit | Se for slopsquatted, supply chain risk — verificar manualmente antes do install |

**Nota sobre A1:** A documentação oficial de rapidfuzz confirma `float` — o cast `int(fuzz.token_set_ratio(...))` no code example está correto para expor como inteiro no schema público.

---

## Sources

### Primary (HIGH confidence)

- Codebase `src/caramello/finances/operations.py` — padrões de endpoints, schemas, session.execute
- Codebase `src/caramello/finances/services.py` — padrão de service functions
- Codebase `src/caramello/finances/models.py` — estado atual de FinancialEntry (sem responsible_user_id)
- Codebase `src/caramello/shared/auth.py` — implementação de `_require_family_access`
- Codebase `alembic/versions/0003_movement_schema_update.py` — down_revision = "0003" confirmado
- Codebase `src/caramello/main.py` — estrutura MCP e ordem de router registration
- Codebase `tests/test_finances_operations.py` — padrões de teste (mock session, dependency_overrides)
- `.planning/phases/09-concilia-o-relat-rios-mcp/09-CONTEXT.md` — decisões do usuário
- `.planning/STATE.md` — pitfalls P1/P3/P6/P7 acumulados
- `.planning/REQUIREMENTS.md` — requisitos LAN-01..05, REL-01..05
- Verificação runtime: `uv run python -c "..."` para Decimal JSON serialization, SQLAlchemy imports

### Secondary (MEDIUM confidence)

- [pypi.org/project/RapidFuzz/](https://pypi.org/project/RapidFuzz/) — package legítimo, MIT license [CITED]
- [rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) — API de `token_set_ratio` [CITED]
- `pip index versions rapidfuzz` — versão 3.14.5 confirmada no registro PyPI [VERIFIED via tool]

### Tertiary (LOW confidence)

- Nenhuma.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tudo exceto `rapidfuzz` já está instalado e em uso
- Architecture: HIGH — extensão direta de padrões estabelecidos nas Phases 7/8
- Pitfalls: HIGH — derivados de decisões documentadas em STATE.md e verificados no código existente
- `rapidfuzz` API: MEDIUM — confirmado em docs oficiais, mas `token_set_ratio` retorna `float` (não `int`) conforme docs

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stack estável; rapidfuzz muda apenas em minor versions)
