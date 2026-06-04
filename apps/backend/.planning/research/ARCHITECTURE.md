# Architecture Patterns

**Domain:** Backend FastAPI organizado por domínios — adição do domínio financeiro ao codebase existente
**Researched:** 2026-05-30
**Confidence:** HIGH — baseado em codebase inspecionado + documentação oficial SQLAlchemy 2.0 + SQLModel GitHub discussions

---

## Contexto: Estado Atual (v1.0)

```
src/caramello/
├── main.py                        # App factory: routers, MCP, CORS, lifespan
├── shared/
│   ├── auth.py                    # JWT Keycloak + get_current_user
│   └── database.py                # AsyncEngine (asyncpg) + get_session
├── users/
│   ├── models.py                  # User (gerado DSL)
│   ├── router.py                  # CRUD gerado
│   └── operations.py              # GET /users/me (implementado)
├── families/
│   ├── models.py                  # Family, FamilyMember, FamilyInvitation (gerado DSL)
│   ├── router.py                  # CRUD gerado
│   ├── operations.py              # 6 endpoints de negócio (implementado)
│   └── services.py                # list_my_families (puro, MCP-exposable)
└── core/
    └── config.py                  # Settings pydantic-settings
```

Padrão estabelecido:
- `models.py` + `router.py` — gerados pelo DSL (nunca editar diretamente)
- `operations.py` — router de negócio com lógica inline ou delegando a `services.py`
- `services.py` — funções puras (sem FastAPI imports), reusáveis via MCP
- `main.py` — registra `operations.router` ANTES de `router.router` (rota estática antes de `{uuid}`)

---

## Estrutura Proposta para o Domínio Finances

```
src/caramello/
├── finances/
│   ├── __init__.py
│   ├── models.py                  # Account, Movement, Entry, Category (gerado DSL)
│   ├── router.py                  # CRUD gerado
│   ├── operations.py              # endpoints de negócio (manual — CARAMELLO-GENERATED: implemented)
│   └── services.py                # lógica pura MCP-exposable (aggregações, sugestão, resumos)
```

Domínio único `finances/` (não subdividir em `finances/accounts/` + `finances/entries/`).
**Rationale:** 4 entidades são poucas para justificar subdomínios; as queries de aggregação cruzam Account→Movement→Entry→Category em uma única operação — separar criaria imports circulares desnecessários. O padrão do projeto já suporta múltiplas entidades por arquivo `models.py` (ver `families/models.py` com 3 entidades).

---

## Respostas às Questões Arquiteturais

### Q1: Self-referential Category (parent/child) no SQLModel com async

**Padrão verificado** (SQLModel GitHub discussions #691, #1509 — MEDIUM confidence, padrão confirmado por múltiplas fontes):

```python
class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    family_id: int = Field(foreign_key="family.id", nullable=False)
    name: str = Field(max_length=100, nullable=False)
    parent_id: int | None = Field(
        foreign_key="category.id",
        default=None,
        nullable=True,        # nullable=True explícito — categoria raiz não tem pai
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    # Self-referential: remote_side como string com nome da CLASSE (maiúsculo)
    # FK usa nome da TABELA (minúsculo)
    parent: "Category | None" = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Category.id"},
    )
    children: list["Category"] = Relationship(back_populates="parent")
    entries: list["Entry"] = Relationship(back_populates="category")
```

**Pontos críticos:**
- `foreign_key="category.id"` usa nome da TABELA (lowercase), não da classe
- `remote_side="Category.id"` usa nome da CLASSE (PascalCase) como string
- `nullable=True` explícito no Field para o `parent_id` — sem isso SQLModel pode inferir NOT NULL
- Compatível com AsyncSession: as queries em services.py usam `selectinload` para carregar filhos quando necessário; sem `selectinload`, não acessar `.children` dentro de endpoint async (causaria MissingGreenlet error)
- Para 2 níveis fixos (raiz + folha): restringir em operações/validação, não em schema de banco

**No DSL YAML**, a auto-referência deve ser declarada manualmente em `models.py` (o gerador DSL atual não suporta `remote_side` — exceção à regra "não editar models.py").
Ou: gerar o bloco base via DSL e pós-processar o relacionamento parent/children manualmente, marcando o arquivo como `# CARAMELLO-GENERATED: implemented` para proteger de sobrescrita.

---

### Q2: Relacionamento 1:1 Movement → Entry no SQLModel

SQLModel não tem açúcar sintático específico para 1:1. O padrão usa `uselist=False` via `sa_relationship_kwargs` (MEDIUM confidence — SQLModel issue #132 + SQLAlchemy docs):

```python
class Movement(SQLModel, table=True):
    __tablename__ = "movement"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    account_id: int = Field(foreign_key="account.id", nullable=False)
    type: str = Field(max_length=10, nullable=False)       # "credit" | "debit"
    date: datetime = Field(nullable=False)
    amount: float = Field(nullable=False)                   # ou Numeric — ver Pitfall 1
    description: str | None = Field(max_length=500, default=None)
    is_duplicate: bool = Field(default=False, nullable=False)
    import_batch_id: str | None = Field(max_length=100, default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    account: "Account | None" = Relationship(back_populates="movements")
    entry: "Entry | None" = Relationship(
        back_populates="movement",
        sa_relationship_kwargs={"uselist": False},
    )


class Entry(SQLModel, table=True):
    __tablename__ = "entry"

    id: int | None = Field(primary_key=True, default=None)
    uuid: UUID = Field(unique=True, default_factory=uuid4, nullable=False)
    movement_id: int = Field(foreign_key="movement.id", unique=True, nullable=False)  # unique=True força 1:1
    category_id: int | None = Field(foreign_key="category.id", default=None, nullable=True)
    competencia_year: int = Field(nullable=False)
    competencia_month: int = Field(nullable=False)           # 1-12
    notes: str | None = Field(max_length=500, default=None)
    is_recurring: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    movement: "Movement | None" = Relationship(back_populates="entry")
    category: "Category | None" = Relationship(back_populates="entries")
```

**Pontos críticos:**
- `unique=True` em `movement_id` é o que garante 1:1 no banco — o `uselist=False` é apenas ORM
- `category_id` nullable: Lançamento pode existir sem categoria (movimento conciliado mas não categorizado ainda)
- Para async: mesma precaução — não acessar `.movement` ou `.category` sem ter carregado via `selectinload`

---

### Q3: Endpoint de importação em lote

**Recomendação: `POST /finances/accounts/{uuid}/movements/import` com body JSON `list[MovementImportItem]`** — não UploadFile/CSV.

**Justificativa:**
- O frontend mobile (React/Capacitor) é o chamador. Enviar JSON é mais simples que multipart/form-data no mobile
- O cliente já tem os dados parseados do extrato bancário antes de enviar
- JSON lista permite validação Pydantic por item antes de qualquer insert
- CSV upload exige decodificação + parsing server-side + tratamento de encoding (UTF-8/Latin1) — complexidade sem ganho para este escopo

```python
class MovementImportItem(BaseModel):
    type: str                        # "credit" | "debit"
    date: datetime
    amount: float
    description: str | None = None

class MovementImportResponse(BaseModel):
    imported: int
    duplicates_flagged: int
    batch_id: str
    items: list[MovementRead]

@router.post("/accounts/{account_uuid}/movements/import", response_model=MovementImportResponse)
async def import_movements(
    account_uuid: UUID,
    items: list[MovementImportItem],
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MovementImportResponse:
    ...
```

**Alternativa se precisar importar arquivos:** `UploadFile` + pandas/csv.reader. Para OFX/QIF (formatos bancários brasileiros), adicionar parser de terceiro. Mas o escopo atual não requer isso — adiar para iteração futura.

---

### Q4: Onde vive a lógica de deduplicação

**Em `services.py`, executada DURANTE o insert, ANTES do commit.**

Não em step separado. Não em background task. Rationale:

1. Deduplicação síncrona ao import dá feedback imediato ao usuário ("3 de 10 já existiam")
2. A família tem no máximo centenas de movimentações por conta — não há volume que justifique queue/background
3. Fingerprint de deduplicação: `(account_id, date, amount, description)` — hash ou comparação direta. `import_batch_id` armazena o UUID do lote para rollback manual se necessário

```python
# finances/services.py
async def import_movements(
    session: AsyncSession,
    account: Account,
    items: list[MovementImportItem],
    batch_id: str,
) -> MovementImportResponse:
    """Importa movimentações, flagando duplicatas. Lógica pura, sem FastAPI."""
    imported = 0
    duplicates = 0
    results = []

    for item in items:
        # Checar duplicata: mesmo account, mesma data, mesmo valor, mesma descrição
        existing = await session.exec(
            select(Movement).where(
                Movement.account_id == account.id,
                Movement.date == item.date,
                Movement.amount == item.amount,
                Movement.description == item.description,
            )
        )
        is_dup = existing.first() is not None

        mov = Movement(
            account_id=account.id,
            type=item.type,
            date=item.date,
            amount=item.amount,
            description=item.description,
            is_duplicate=is_dup,
            import_batch_id=batch_id,
        )
        session.add(mov)
        results.append(mov)
        if is_dup:
            duplicates += 1
        else:
            imported += 1

    await session.commit()
    for mov in results:
        await session.refresh(mov)

    return MovementImportResponse(
        imported=imported,
        duplicates_flagged=duplicates,
        batch_id=batch_id,
        items=[MovementRead.model_validate(m) for m in results],
    )
```

**Nota:** duplicatas são salvas com `is_duplicate=True`, não rejeitadas — permite revisão manual. O usuário pode limpar depois.

---

### Q5: Lógica de sugestão de categoria

**Em `services.py`, exposta via MCP.**

Mesma estratégia de `list_my_families`: função pura em `services.py`, chamada em `operations.py` via endpoint HTTP e também acessível via MCP:

```python
# finances/services.py
async def suggest_category(
    session: AsyncSession,
    family: Family,
    description: str,
) -> list[Category]:
    """
    Sugere categorias baseado em similaridade com entradas anteriores.
    Estratégia v1: ILIKE na descrição de movimentações já categorizadas.
    Estratégia v2: embeddings (fase posterior).
    """
    # v1: busca categorias usadas em entradas com descrição similar
    result = await session.exec(
        select(Category)
        .join(Entry, Entry.category_id == Category.id)
        .join(Movement, Movement.id == Entry.movement_id)
        .where(
            Category.family_id == family.id,
            Movement.description.ilike(f"%{description}%"),
        )
        .distinct()
        .limit(5)
    )
    return list(result.all())
```

**Exposição MCP:** registrar `operation_id="suggest_category"` no endpoint e adicionar em `include_operations` no `main.py`. Agentes de IA poderão sugerir categorias diretamente.

---

### Q6: Performance de agregações com SQLAlchemy async

**Veredicto: func.sum + group_by via `session.execute()` (não `session.exec()`) — performance adequada para 1-5 usuários.**

`session.exec()` (SQLModel helper) funciona bem para queries de ORM que retornam instâncias de modelo. Para queries com agregações (`func.sum`, `group_by`, colunas calculadas), usar `session.execute()` nativo do SQLAlchemy 2.0 que retorna `Row` objects (HIGH confidence — SQLAlchemy 2.0 asyncio docs):

```python
# finances/services.py
async def monthly_breakdown(
    session: AsyncSession,
    family_id: int,
    year: int,
    month: int,
) -> list[dict]:
    """Retorna breakdown de gastos por categoria pai no mês."""
    stmt = (
        select(
            Category.name.label("category_name"),
            func.sum(Movement.amount).label("total"),
        )
        .join(Entry, Entry.category_id == Category.id)
        .join(Movement, Movement.id == Entry.movement_id)
        .join(Account, Account.id == Movement.account_id)
        .where(
            Account.family_id == family_id,
            Entry.competencia_year == year,
            Entry.competencia_month == month,
            Movement.is_duplicate.is_(False),
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Movement.amount).desc())
    )
    result = await session.execute(stmt)
    rows = result.all()
    return [{"category": row.category_name, "total": float(row.total or 0)} for row in rows]
```

**Considerações de performance:**
- Índices obrigatórios: `movement.account_id`, `entry.competencia_year`, `entry.competencia_month`, `entry.category_id`, `account.family_id`
- Para o escopo (1-5 usuários, centenas de lançamentos por família por mês), PostgreSQL executa a agregação em milissegundos — sem necessidade de materializar views ou caching
- `func.sum` em asyncpg é executado server-side no PostgreSQL, não client-side — sem overhead de trazer todas as linhas para Python

---

### Q7: Um diretório ou subdividir o domínio finances

**Diretório único `src/caramello/finances/`** — não subdividir.

| Critério | Argumento |
|----------|-----------|
| Volume de entidades | 4 entidades (Account, Movement, Entry, Category) — não justifica subdivisão |
| Queries entre entidades | `monthly_breakdown` junta as 4 entidades — subdivisão criaria imports cruzados internos |
| Padrão do projeto | `families/` já tem 3 entidades (Family, FamilyMember, FamilyInvitation) em um único diretório |
| Fricção operacional | Subdivisão = 2 pares de `models.py + router.py`, 2 entradas em `main.py`, 2 entradas no `alembic/env.py` — sem ganho |
| DSL generator | Gera por `domain:` field — "finances" como domínio único se encaixa nativamente |

Se o domínio crescer para 8+ entidades (ex: orçamento mensal, metas, investimentos), subdividir então faz sentido.

---

## Modelo de Domínio Completo

```
Account
  id, uuid, family_id (FK→family.id), name, type, currency, is_active
  created_at, updated_at
  → movements: list[Movement]
  → family: Family

Movement
  id, uuid, account_id (FK→account.id), type, date, amount, description
  is_duplicate, import_batch_id
  created_at, updated_at
  → account: Account
  → entry: Entry | None (1:1, uselist=False)

Entry
  id, uuid, movement_id (FK→movement.id, UNIQUE), category_id (FK→category.id, nullable)
  competencia_year, competencia_month, notes, is_recurring
  created_at, updated_at
  → movement: Movement (back_populates)
  → category: Category | None

Category
  id, uuid, family_id (FK→family.id), name, parent_id (FK→category.id, nullable)
  created_at, updated_at
  → parent: Category | None (self-ref, remote_side=Category.id)
  → children: list[Category]
  → entries: list[Entry]
  → family: Family
```

**Fluxo de conciliação:**
```
1. Movement inserida (bruta, sem Entry)
2. services.suggest_category() → sugere categoria por similaridade
3. Usuário confirma categoria via PATCH /finances/movements/{uuid}/reconcile
4. Entry criada com movement_id + category_id + competencia
5. monthly_breakdown() agrega Entry+Movement+Category por mês/família
```

---

## Integração com Arquitetura Existente

### Pontos de integração

| Componente | O que muda | Ação |
|------------|-----------|------|
| `main.py` | Adicionar imports e `include_router` para finances | Manual — após geração DSL |
| `alembic/env.py` | Importar Account, Movement, Entry, Category para metadata | Adicionar 4 imports |
| `dsl/manifest.yaml` | Adicionar 4 novos entity files | Adicionar entradas |
| `scripts/generate_code.py` | Adicionar `"finances"` em `DOMAIN_TO_ENTITY_NAME` | 1 linha |
| `scripts/generate_code.py` | Adicionar `finances` em `_run_ruff_fix` dirs list | 1 linha |
| `main.py` MCP `include_operations` | Adicionar `suggest_category`, outros operations IDs financeiros | Após implementação |

### O que NÃO muda

- `shared/auth.py`, `shared/database.py` — reutilizados sem modificação
- `users/`, `families/` — sem toque
- Padrão de testes (savepoint rollback contra `caramello_dev`)
- DSL YAML → geração → operações manuais

### Novo componente: Account como escopo de autorização

Diferente de Family (acesso irrestrito a membros), Account é scoped por `family_id`. O padrão de autorização em `operations.py`:

```python
async def _require_account_access(
    account_uuid: UUID,
    current_user: User,
    session: AsyncSession,
) -> Account:
    """Garante que current_user é membro da família dona da conta."""
    result = await session.exec(
        select(Account)
        .join(Family, Family.id == Account.family_id)
        .join(FamilyMember, FamilyMember.family_id == Family.id)
        .where(
            Account.uuid == account_uuid,
            FamilyMember.user_id == current_user.id,
        )
    )
    account = result.first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
```

---

## Build Order para o Domínio Finances

Dependências ditam a ordem:

```
1. DSL YAMLs (4 arquivos em dsl/entities/)
   └── depende de: definição do modelo de domínio

2. generate_code.py atualizado (DOMAIN_TO_ENTITY_NAME + _run_ruff_fix)
   └── depende de: nada novo

3. bin/generate_code → gera finances/models.py + finances/router.py
   └── depende de: DSL YAMLs + generator atualizado

4. Category.parent/children — pós-processar manualmente em finances/models.py
   └── marcar arquivo como # CARAMELLO-GENERATED: implemented
   └── depende de: geração DSL (3)

5. Alembic migration 0002_finances_schema.py
   └── depende de: models.py completo (3+4)
   └── alembic/env.py deve importar as 4 entidades

6. finances/operations.py — CRUD de Account (criação, listagem por família)
   └── depende de: models.py (3), auth helpers existentes

7. finances/operations.py — Movement: insert individual + reconcile (criar Entry)
   └── depende de: Account (6), Category (9)

8. finances/operations.py — import em lote + deduplicação (via services.py)
   └── depende de: Movement (7)

9. finances/operations.py — Category: CRUD hierárquico
   └── depende de: models.py (3+4)

10. finances/services.py — suggest_category, monthly_breakdown, account_balance
    └── depende de: todas as entidades (3-9)

11. main.py — include_router finances_operations + finances_router
    └── depende de: operations.py (6-9)
    └── operations ANTES de router (padrão estabelecido — D-06)

12. MCP — adicionar operation_ids financeiros em include_operations
    └── depende de: main.py (11)

13. Testes unitários + integração
    └── depende de: tudo acima
```

**Fases naturais de entrega:**
- **Fase A (fundação):** passos 1-5 — DSL, geração, migration
- **Fase B (contas e categorias):** passos 6, 9 — CRUD Account + Category
- **Fase C (movimentações):** passos 7-8 — insert individual + bulk import
- **Fase D (conciliação e relatórios):** passos 10-12 — Entry, aggregações, MCP

---

## Anti-Patterns Específicos do Domínio Finances

### Anti-Pattern 1: float para valores monetários
**O que é:** `amount: float` em vez de `Numeric(10, 2)` no banco
**Por que é ruim:** ponto flutuante perde precisão em somas acumuladas — R$ 0.1 + R$ 0.2 ≠ R$ 0.3
**Em vez disso:** `sa_column=Column(Numeric(10, 2))` no SQLModel Field, ou `Decimal` no Python. Para o DSL, adicionar suporte a tipo `decimal` ou usar `float` no Python mas `Numeric` no banco via `sa_column`.

### Anti-Pattern 2: Lazy loading em endpoint async
**O que é:** acessar `movement.entry` ou `category.children` dentro de endpoint async sem ter carregado via `selectinload`
**Por que é ruim:** SQLAlchemy async não suporta lazy loading implícito — resulta em `MissingGreenlet` error
**Em vez disso:** quando a response inclui relacionamentos, usar `options(selectinload(Movement.entry))` na query, ou estruturar a response para não incluir relacionamentos (use IDs/UUIDs em vez de objetos aninhados)

### Anti-Pattern 3: Criar Entry sem verificar Movement já conciliada
**O que é:** `POST /entries` sem checar se `movement.entry` já existe
**Por que é ruim:** viola o 1:1 — SQLModel não impede a criação de múltiplas Entries para o mesmo Movement em nível de aplicação (só o unique constraint no banco pega)
**Em vez disso:** verificar existência em `operations.py` antes de inserir, retornar 409 Conflict se já existir

### Anti-Pattern 4: Agregação via Python loop
**O que é:** carregar todas as Entry do mês e somar em Python
**Por que é ruim:** traz dados desnecessários para a memória; PostgreSQL faz SUM server-side muito mais eficiente
**Em vez disso:** `func.sum()` com `group_by()` via `session.execute()` como demonstrado em Q6

### Anti-Pattern 5: Categoria raiz com parent_id = parent_id (ciclo)
**O que é:** Category.parent_id apontando para si mesma (id == parent_id)
**Por que é ruim:** cria ciclo na hierarquia — queries de traversal entram em loop
**Em vez disso:** validar em operations.py que `parent_id != id` antes de salvar; validar também que parent não tem pai (max 2 níveis)

---

## Considerações de Escalabilidade

Para 1-5 usuários, todas as decisões acima são adequadas e não precisam revisão.

| Preocupação | Escala atual (1-5 usuários) | Se crescer |
|-------------|----------------------------|-----------|
| Aggregações mensais | SQL GROUP BY direto — centenas de linhas | Materialized view ou Redis cache |
| Deduplicação síncrona | Loop Python + queries individuais | Bulk INSERT ON CONFLICT |
| Sugestão de categoria | ILIKE query | Embeddings + pgvector |
| Import em lote | JSON list síncrono | Background task + WebSocket status |

---

## Sources

- SQLModel GitHub Discussion #691 (self-referential): `remote_side` com string da classe — MEDIUM confidence
- SQLModel GitHub Discussion #1509 (self-referential): padrão confirmado com `nullable=True` — MEDIUM confidence
- SQLModel GitHub Issue #132 (one-to-one): `uselist=False` via `sa_relationship_kwargs` — MEDIUM confidence
- SQLAlchemy 2.0 asyncio docs (`docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html`): `session.execute()` para aggregações — HIGH confidence
- SQLAlchemy 2.0 self-referential docs (`docs.sqlalchemy.org/en/20/orm/self_referential.html`): adjacency list, `remote_side` — HIGH confidence
- Codebase inspecionado: families/models.py, families/operations.py, scripts/generate_code.py — HIGH confidence (fonte primária)
