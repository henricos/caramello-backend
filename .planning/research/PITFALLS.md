# Domain Pitfalls — Domínio Financeiro

**Domain:** FastAPI async + SQLModel + asyncpg — adição de domínio financeiro a app existente
**Researched:** 2026-05-30
**Context:** Milestone 2 (Domínio Financeiro) adicionado sobre fundação existente (M1 shipped). Stack: Python 3.12, FastAPI async, SQLModel, SQLAlchemy 2.0, asyncpg, PostgreSQL, Alembic async.

---

## 1. Relacionamento Auto-Referencial (Category.parent) com Async

### PITFALL-F1: `remote_side` e `foreign_keys` ausentes em relacionamento self-referencial

**O que vai errado:** Definir `Relationship(back_populates="children")` sem `sa_relationship_kwargs={"remote_side": ..., "foreign_keys": ...}` faz o SQLAlchemy não saber qual lado da relação é "one" vs "many". O resultado é um `AmbiguousForeignKeysError` na inicialização da app, ou pior: joins silenciosamente incorretos que retornam a categoria como própria filha.

**Por que acontece:** Em relacionamentos normais (tabelas distintas), o SQLAlchemy infere os lados da relação pelos nomes das tabelas. Em relacionamentos self-referencial, ambos os lados apontam para a mesma tabela — a inferência falha.

**Padrão obrigatório:**
```python
class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: int | None = Field(default=None, primary_key=True)
    parent_id: int | None = Field(default=None, foreign_key="category.id")

    parent: "Category | None" = Relationship(
        back_populates="children",
        sa_relationship_kwargs={
            "remote_side": "Category.id",   # lado "one" — o pai
            "foreign_keys": "[Category.parent_id]",
        },
    )
    children: list["Category"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            "foreign_keys": "[Category.parent_id]",
        },
    )
```

Os valores de `remote_side` e `foreign_keys` são strings avaliadas como expressões Python — necessário porque a classe ainda está sendo definida.

**Fase:** Fase de modelagem (Category CRUD).

---

### PITFALL-F2: Lazy loading em relacionamento self-referencial dispara `MissingGreenlet`

**O que vai errado:** Acessar `category.children` ou `category.parent` fora de um `await` em contexto async levanta `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`. Isso ocorre *depois* da query principal, durante serialização pela FastAPI — o erro aparece tarde e o stack trace é confuso.

**Por que acontece:** SQLAlchemy async elimina lazy loading implícito. Todo acesso a relacionamento não carregado tenta IO implícito, que é proibido em async. O padrão síncrono de acessar `.children` funciona normalmente; o mesmo código em async explode em runtime.

**Prevenção — duas opções:**

Opção 1 (preferida para endpoints que precisam dos filhos): `selectinload` explícito na query:
```python
from sqlalchemy.orm import selectinload

stmt = select(Category).where(Category.family_id == family_id).options(
    selectinload(Category.children)
)
result = await session.exec(stmt)
```

Opção 2 (para uso no DSL generator): configurar `lazy="selectin"` no relacionamento, carregando sempre os filhos automaticamente:
```python
sa_relationship_kwargs={
    "foreign_keys": "[Category.parent_id]",
    "lazy": "selectin",   # carrega filhos automaticamente em toda query
}
```

Opção 2 é conveniente mas cria N+1 implícito para queries que não precisam dos filhos. Para `Category` com apenas 2 níveis e uso familiar (< 100 categorias), é aceitável.

**Sinal de alerta:** `greenlet_spawn has not been called; can't call await_()` no log com stack trace dentro de `fastapi/routing.py` (durante serialização).

**Fase:** Fase de modelagem (Category CRUD) e geração DSL.

---

### PITFALL-F3: Constraint de profundidade não enforçado no banco

**O que vai errado:** O modelo aceita Category com `parent_id` de uma categoria que já é filha — criando 3+ níveis. Sem check constraint no banco, o sistema aceita silenciosamente hierarquias arbitrariamente profundas, quebrando relatórios que assumem exatamente 2 níveis (pai → subcategoria).

**Prevenção:** Check constraint via `__table_args__`:
```python
class Category(SQLModel, table=True):
    __table_args__ = (
        # enforça: se tem parent, o parent NÃO pode ter parent (evita 3+ níveis)
        # implementado via trigger ou validação em service
    )
```

Na prática, para este projeto, a validação mais simples é no service layer: ao criar uma subcategoria, verificar que o pai não tem `parent_id`. Mais simples e suficiente para 1-5 usuários.

**Fase:** Fase de modelagem (Category CRUD) — verificar antes de criar Lançamentos.

---

## 2. Batch Insert com Deduplicação (Movimentações)

### PITFALL-F4: `session.add_all()` em loop não deduplica — viola unique constraint em runtime

**O que vai errado:** Carregar CSV, mapear para objetos `Movimentacao`, e fazer `await session.add_all(movimentacoes)` sem deduplicação prévia. Se o arquivo contém duplicatas internas (duas linhas idênticas no mesmo CSV), ou se o usuário reimporta o mesmo arquivo, o PostgreSQL lança `IntegrityError: duplicate key value violates unique constraint` na primeira linha duplicada — e a transação inteira é abortada, perdendo as movimentações únicas do lote.

**Por que acontece:** `add_all` não tem semântica de "inserir se não existir". A transação falha atomicamente — zero linhas são inseridas se houver qualquer conflito.

**Prevenção obrigatória — `INSERT ... ON CONFLICT DO NOTHING`:**
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

async def bulk_insert_movimentacoes(
    session: AsyncSession, rows: list[dict]
) -> int:
    if not rows:
        return 0
    stmt = (
        pg_insert(Movimentacao)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["dedup_hash"])
        # dedup_hash: coluna UNIQUE calculada como hash(data + descricao_normalizada + valor + conta_id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount  # linhas efetivamente inseridas (excluindo duplicatas)
```

**Hash de deduplicação:** calcular antes do insert, não depender de unicidade por combinação de colunas individuais (datas e valores podem coincidir legitimamente):
```python
import hashlib

def calc_dedup_hash(data: date, descricao: str, valor: Decimal, conta_id: int) -> str:
    raw = f"{data}|{descricao.strip().lower()}|{valor}|{conta_id}"
    return hashlib.md5(raw.encode()).hexdigest()
```

**Fase:** Fase de importação de Movimentações.

---

### PITFALL-F5: Lote grande carregado inteiro em memória antes do insert

**O que vai errado:** `await file.read()` + `csv.reader(StringIO(content))` para arquivos CSV de extrato bancário anual (tipicamente 300-2000 linhas, raramente > 10 MB) não é problema de memória, mas a prática de `read()` inteiro bloqueia o event loop durante o parsing. Em uploads de arquivos maiores (extratos de vários anos, OFX), o bloqueio se torna visível.

**Prevenção:** Usar `SpooledTemporaryFile` (comportamento padrão do `UploadFile` do FastAPI — arquivos < 1MB em memória, > 1MB em disco). Para parsing, usar streaming line-by-line:
```python
async def import_csv(file: UploadFile) -> list[dict]:
    content = await file.read()  # OK para extratos < 5MB
    # Para arquivos maiores: iterar linha a linha via file.file (sync handle)
    lines = content.decode("utf-8").splitlines()
    reader = csv.DictReader(lines)
    return list(reader)
```

Para extratos bancários domésticos (escopo deste projeto: 1-5 usuários), `read()` inteiro é aceitável. O risco real é inserir em lote sem chunking — para > 5.000 linhas, usar `executemany` em chunks de 500.

**Fase:** Fase de importação de Movimentações.

---

### PITFALL-F6: Tipo do arquivo não validado — `UploadFile` aceita qualquer conteúdo

**O que vai errado:** FastAPI não valida o `Content-Type` do arquivo uploadado por padrão. Um cliente pode enviar um arquivo `.exe` com `Content-Type: text/csv`. O endpoint tenta fazer `csv.DictReader` no conteúdo binário e lança `UnicodeDecodeError` não tratado — HTTP 500 sem mensagem útil.

**Prevenção:**
```python
async def import_movimentacoes(file: UploadFile = File(...)):
    if file.content_type not in ("text/csv", "text/plain", "application/octet-stream"):
        raise HTTPException(422, "Formato de arquivo não suportado. Envie um CSV.")
    try:
        content = await file.read()
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(422, "Arquivo não é texto UTF-8 válido.")
```

**Fase:** Fase de importação de Movimentações.

---

## 3. Agregações Financeiras (GROUP BY mês/categoria)

### PITFALL-F7: ORM relationships carregados para calcular agregações — N+1 query

**O que vai errado:** Calcular saldo de conta iterando sobre `conta.movimentacoes` em Python:
```python
# ERRADO — N+1: uma query por conta + uma por lista de movimentações
contas = await session.exec(select(Conta)).all()
for conta in contas:
    saldo = sum(m.valor for m in conta.movimentacoes)  # lazy load por conta
```

**Prevenção — agregar no banco:**
```python
from sqlalchemy import func, select

stmt = (
    select(
        Movimentacao.conta_id,
        func.sum(Movimentacao.valor).label("saldo"),
    )
    .group_by(Movimentacao.conta_id)
)
result = await session.execute(stmt)
saldos = {row.conta_id: row.saldo for row in result}
```

**Fase:** Fase de relatórios e agregações.

---

### PITFALL-F8: `func.date_trunc` sem label causa ambiguidade no GROUP BY

**O que vai errado:** Usar `func.date_trunc("month", Lancamento.competencia)` no `select()` e `group_by()` sem `.label()` pode gerar SQL com referência ambígua à expressão — alguns backends retornam o resultado corretamente, outros levantam `ProgrammingError: column must appear in GROUP BY clause`.

**Prevenção — sempre usar `.label()` para expressões em GROUP BY:**
```python
competencia_mes = func.date_trunc("month", Lancamento.competencia).label("mes")

stmt = (
    select(
        competencia_mes,
        Categoria.nome.label("categoria"),
        func.sum(Movimentacao.valor).label("total"),
    )
    .join(Lancamento.movimentacao)
    .join(Lancamento.categoria)
    .where(Lancamento.familia_id == familia_id)
    .group_by(competencia_mes, Categoria.nome)
    .order_by(competencia_mes)
)
```

**Alternativa recomendada:** usar `competencia` como campo `year + month` inteiro (ex: `202501`) em vez de datetime. Evita `date_trunc` completamente, simplifica GROUP BY, e a coluna é indexável de forma simples.

**Fase:** Fase de relatórios e agregações.

---

### PITFALL-F9: `expire_on_commit=False` mascara dados obsoletos em sessões longas de relatório

**O que vai errado:** O `async_session_factory` do projeto já usa `expire_on_commit=False` (necessário para async). Em endpoints de relatório que fazem múltiplas queries na mesma sessão (ex: buscar contas, depois somar movimentações por conta), um objeto `Conta` lido antes de uma modificação concorrente não será recarregado automaticamente — os cálculos usam o estado stale.

**Mitigação:** Para relatórios financeiros, usar `await session.refresh(obj)` explicitamente se o objeto foi carregado em step anterior da mesma sessão. Ou, mais simples: estruturar relatórios como queries agregadas únicas (uma só `SELECT` com JOINs e GROUP BY) em vez de múltiplas queries seguidas.

**Fase:** Fase de relatórios e agregações.

---

## 4. Constraint 1:1 Movimentação → Lançamento

### PITFALL-F10: 1:1 enforçado apenas no ORM — banco permite múltiplos Lançamentos por Movimentação

**O que vai errado:** Definir `Relationship()` como 1:1 no SQLModel sem constraint de unicidade no banco. O SQLAlchemy ORM respeitará a semântica 1:1 em código Python, mas inserções diretas via SQL (migrations, fixtures de teste, imports de dados) podem criar múltiplos `Lançamento` para a mesma `Movimentacao`. Relatórios de saldo ficam duplicados silenciosamente.

**Prevenção — constraint no banco é obrigatório:**
```python
class Lancamento(SQLModel, table=True):
    __tablename__ = "lancamento"

    movimentacao_id: int = Field(
        foreign_key="movimentacao.id",
        unique=True,    # enforça 1:1 no banco — não apenas no ORM
        nullable=False,
    )
```

A cláusula `unique=True` em SQLModel cria `UNIQUE CONSTRAINT` na coluna via Alembic autogenerate. Verificar que a migration gerada inclui `sa.UniqueConstraint("movimentacao_id")`.

**Fase:** Fase de modelagem (Lançamento) — verificar na migration antes de popular dados.

---

### PITFALL-F11: Tentativa de criar segundo Lançamento para mesma Movimentação vira HTTP 500

**O que vai errado:** Sem tratamento explícito de `IntegrityError`, tentar criar um segundo `Lançamento` para uma `Movimentacao` já conciliada levanta `sqlalchemy.exc.IntegrityError` não tratado — FastAPI retorna HTTP 500 em vez de HTTP 409 Conflict com mensagem útil.

**Prevenção:**
```python
from sqlalchemy.exc import IntegrityError

async def create_lancamento(movimentacao_id: int, ..., session: AsyncSession):
    try:
        lancamento = Lancamento(movimentacao_id=movimentacao_id, ...)
        session.add(lancamento)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Movimentação {movimentacao_id} já possui um lançamento associado.",
        )
```

**Fase:** Fase de Lançamentos (service layer).

---

## 5. Precisão Monetária

### PITFALL-F12: Usar `float` para valores monetários — erro de ponto flutuante acumula

**O que vai errado:** Armazenar valor como `float` no Python/SQLAlchemy e `DOUBLE PRECISION` ou `REAL` no PostgreSQL. Exemplos de erro real:
- `0.1 + 0.2 == 0.30000000000000004` em Python
- Saldo acumulado de 100 transações de `R$ 1,10` resulta em `R$ 109,99999999` em vez de `R$ 110,00`
- Comparações de igualdade em deduplicação por valor falham para valores com casas decimais

**Por que acontece:** `float` é IEEE 754 binário — não consegue representar `0.1` exatamente. Após centenas de somas, o erro acumula.

**Prevenção obrigatória — `NUMERIC` no banco + `Decimal` no Python:**
```python
from decimal import Decimal
from sqlmodel import Field
from sqlalchemy import Numeric

class Movimentacao(SQLModel, table=True):
    valor: Decimal = Field(
        sa_column=Column(Numeric(precision=15, scale=2), nullable=False)
    )
    # precision=15 suporta até R$ 9.999.999.999.999,99 — suficiente para uso familiar
    # scale=2 = centavos
```

**asyncpg e Decimal:** asyncpg decodifica `NUMERIC` como `Decimal` nativamente (confirmado na documentação oficial). SQLAlchemy 2.0 com `Numeric(asdecimal=True)` (padrão) retorna `Decimal` — nenhuma conversão manual necessária.

**Alternativa (integer cents):** armazenar como `INTEGER` em centavos (`R$ 10,50` → `1050`). Elimina risco de float completamente, é mais eficiente em storage (4 bytes vs 10 bytes de NUMERIC). Desvantagem: toda leitura/escrita requer divisão/multiplicação por 100. Para este projeto com frontends React/IA que esperam valores decimais, `NUMERIC` é mais ergonômico.

**Sinal de alerta:** qualquer uso de `float` ou `Float` no modelo financeiro é bug.

**Fase:** Modelagem de Movimentação e Lançamento — deve ser enforçado na DSL.

---

### PITFALL-F13: Pydantic serializa `Decimal` como string em alguns contextos

**O que vai errado:** `Decimal` não é JSON-serializable por padrão. FastAPI/Pydantic 2 serializa `Decimal` como string (`"10.50"`) em alguns contextos e como number (`10.50`) em outros, dependendo da configuração do schema. Clientes que esperam número recebem string — comparações falham no frontend.

**Prevenção:** Configurar serialização explícita no schema de resposta:
```python
class MovimentacaoRead(SQLModel):
    model_config = {"json_encoders": {Decimal: float}}
    valor: Decimal
```

Ou, mais simples: aceitar que o valor vai como string no JSON (`"10.50"`) e documentar isso no OpenAPI. O frontend deve usar `parseFloat()` ao receber.

**Fase:** Fase de schemas (MovimentacaoRead, LancamentoRead).

---

## 6. Integração com Domínios Existentes

### PITFALL-F14: Migration do domínio financeiro sem `down_revision` correto quebra sequência de migrações

**O que vai errado:** Criar migration `0002_financial_domain.py` com `down_revision = None` (esquecido ou gerado incorretamente) em vez de `down_revision = "0001"`. O Alembic aceita a migration mas o grafo de revisões fica bifurcado — `alembic upgrade head` sobe ambas as branches independentemente, podendo criar tabelas em ordem errada ou falhar com FK violation.

**Por que acontece:** `alembic revision --autogenerate` geralmente detecta o `down_revision` correto, mas se o `env.py` não importa os modelos do domínio financeiro (PITFALL-1D), ele pode gerar a migration sem perceber que é uma branch.

**Prevenção:**
- Verificar `down_revision = "0001"` manualmente após gerar a migration.
- Rodar `alembic history --verbose` para visualizar o grafo — deve ser linear, não bifurcado.
- Garantir que `env.py` importa os novos modelos antes de gerar a migration:
```python
# alembic/env.py
from caramello.users import models as _  # noqa
from caramello.families import models as _  # noqa
from caramello.finances import models as _  # noqa  <- adicionar ao criar o domínio
```

**Fase:** Fase inicial do domínio financeiro (primeira migration).

---

### PITFALL-F15: Constraint `create_foreign_key(None, ...)` no autogenerate — downgrade quebrado

**O que vai errado:** Alembic autogenerate pode produzir `op.create_foreign_key(None, ...)` com `constraint_name=None` para foreign keys sem nome explícito. O `upgrade()` funciona (PostgreSQL gera nome automático), mas o `downgrade()` tenta `op.drop_constraint(None, ...)` — lança `TypeError` porque o banco registrou o constraint com nome gerado, não `None`.

**Prevenção:** Adicionar naming convention global no `env.py` para que Alembic gere nomes determinísticos:
```python
# alembic/env.py
from sqlalchemy import MetaData

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

target_metadata = SQLModel.metadata
target_metadata.naming_convention = convention
```

**Fase:** Antes de gerar a primeira migration do domínio financeiro.

---

### PITFALL-F16: Imports circulares entre domínio financeiro e domínio families

**O que vai errado:** `finances/models.py` importa `Family` de `families/models.py` para o FK `Movimentacao.family_id`. Se `families/models.py` em algum momento importar algo de `finances/` (ex: para um related property), o Python levanta `ImportError: cannot import name 'X' from partially initialized module`.

**Por que acontece:** Ao adicionar um novo domínio com FKs para domínios existentes, a tentação é adicionar back-references no domínio existente — criando ciclos.

**Regra de ouro para este projeto:** `finances/` importa de `families/` e `users/`. Nenhum dos dois importa de `finances/`. Relacionamentos reversos (ex: "listar movimentações de uma família") são implementados via query, não via `Relationship()` no model de `Family`.

**Para referências de tipo apenas:**
```python
# finances/models.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from caramello.families.models import Family
```

**Fase:** Fase de modelagem do domínio financeiro.

---

### PITFALL-F17: Registrar routers do domínio financeiro após FastApiMCP — tools não aparecem no MCP

**O que vai errado:** Adicionar `app.include_router(finances_router)` após `mcp.mount_http()` em `main.py`. O fastapi-mcp descobre ferramentas no momento da inicialização — routers registrados depois não aparecem.

**Sinal de alerta documentado no projeto:** O comentário em `main.py` já documenta isso: "MCP — montar DEPOIS de todos os include_router."

**Prevenção:** Adicionar os novos routers do domínio financeiro ANTES da linha `mcp = FastApiMCP(...)` em `main.py`. Também manter a ordem operations antes de router para evitar rota `/{uuid}` interceptando rotas estáticas (PITFALL documentado em M1).

**Fase:** Fase de integração — registro dos routers em `main.py`.

---

## 7. Upload de Arquivo (Importação de Extrato)

### PITFALL-F18: `file.file.read()` síncrono bloqueia o event loop em async handler

**O que vai errado:** Em handlers `async def`, `UploadFile.file` é um objeto `SpooledTemporaryFile` síncrono. Chamar `file.file.read()` diretamente em async context bloqueia o event loop durante a leitura do arquivo do disco (se > 1MB foi spoolado em arquivo temporário).

**Prevenção:** Usar `await file.read()` (método async do `UploadFile`, não do `.file` interno):
```python
# CORRETO
content = await file.read()

# ERRADO — bloqueia event loop se arquivo > 1MB
content = file.file.read()
```

`UploadFile.read()` é awaitable e não bloqueia.

**Fase:** Fase de importação de Movimentações.

---

## Matrix de Pitfalls por Fase

| Fase | Tópico | Pitfall principal | Mitigação |
|------|--------|-------------------|-----------|
| Modelagem (Categoria) | Relacionamento self-referencial | `remote_side`/`foreign_keys` ausentes | Padrão obrigatório com `sa_relationship_kwargs` |
| Modelagem (Categoria) | Lazy loading async | `MissingGreenlet` na serialização | `selectinload` explícito ou `lazy="selectin"` |
| Modelagem (Categoria) | Profundidade máxima | 3+ níveis sem constraint | Validação no service layer |
| Modelagem (Movimentação) | Precisão decimal | `float` em vez de `Decimal` | `NUMERIC(15,2)` + `Decimal` — obrigatório |
| Modelagem (Movimentação) | Deduplicação | `IntegrityError` em lote | `INSERT ... ON CONFLICT DO NOTHING` com `dedup_hash` |
| Modelagem (Lançamento) | Constraint 1:1 | Múltiplos Lançamentos por Movimentação | `unique=True` na FK `movimentacao_id` |
| Modelagem (Lançamento) | Erro de constraint | HTTP 500 em vez de 409 | Capturar `IntegrityError`, retornar 409 |
| Importação CSV | Upload | `file.file.read()` bloqueia event loop | Usar `await file.read()` |
| Importação CSV | Validação | Arquivo binário crashando `DictReader` | Validar `content_type` + capturar `UnicodeDecodeError` |
| Importação CSV | Lote grande | Lote inteiro em memória | Chunk de 500 linhas para `executemany` |
| Relatórios | Agregação | N+1 via ORM relationships | Agregar no banco com `func.sum` + `GROUP BY` |
| Relatórios | GROUP BY | Expressão sem label | Sempre usar `.label()` em `date_trunc`/`func.*` |
| Migration | Nova migration | `down_revision` incorreto | Verificar manualmente + `alembic history` |
| Migration | FK sem nome | `create_foreign_key(None, ...)` | Naming convention em `env.py` |
| Integração | Imports circulares | `finances` ↔ `families` | Fluxo unidirecional; `TYPE_CHECKING` para tipos |
| Integração | MCP + routers | Router registrado após `mcp.mount_http()` | Routers ANTES de `FastApiMCP(...)` |
| Schemas | Decimal JSON | `Decimal` serializado como string | Configurar `json_encoders` ou documentar comportamento |

---

## Sources

- SQLAlchemy async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- SQLModel self-referential issue: https://github.com/fastapi/sqlmodel/issues/127
- SQLModel async relationship issue: https://github.com/fastapi/sqlmodel/issues/74
- SQLModel async relationships part 2: https://dev.to/arunanshub/the-async-side-of-sqlmodel-relationships-part-2-4ebc
- asyncpg Decimal/NUMERIC: https://magicstack.github.io/asyncpg/current/usage.html
- PostgreSQL money types: https://www.crunchydata.com/blog/working-with-money-in-postgres
- SQLAlchemy Numeric precision: https://github.com/sqlalchemy/sqlalchemy/issues/1625
- Alembic FK naming convention: https://peerlist.io/saish_naik/articles/alembic-migration-issue-createforeignkeynone---and-why-your-
- Alembic FK table ordering: https://github.com/sqlalchemy/alembic/issues/1059
- FastAPI file upload streaming: https://medium.com/@connect.hashblock/async-file-uploads-in-fastapi-handling-gigabyte-scale-data-smoothly-aec421335680
- SQLAlchemy ON CONFLICT batch: https://docs.sqlalchemy.org/en/21/dialects/postgresql.html
- expire_on_commit async: https://github.com/sqlalchemy/sqlalchemy/discussions/11495
- SQLAlchemy GROUP BY aggregation: https://sqlalchemy-utils.readthedocs.io/en/latest/aggregates.html
