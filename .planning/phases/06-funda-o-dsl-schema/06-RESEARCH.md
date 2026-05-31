# Phase 6: Fundação DSL + Schema — Research

**Pesquisado:** 2026-05-31
**Domínio:** Extensão do gerador DSL + schema financeiro no PostgreSQL via Alembic
**Confiança geral:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** `Decimal` como tipo nativo no gerador. YAML `Decimal` → Python `Decimal`, coluna SA `sa_column(Column(Numeric(15, 2)))`. Precisão `NUMERIC(15,2)` fixo.
**D-02:** Nenhum campo monetário usa `float`. Todo campo de valor usa `Decimal`.
**D-03:** `from decimal import Decimal` adicionado ao cabeçalho dos `models.py` gerados quando ao menos um campo `Decimal` estiver presente.
**D-04:** Competência como dois inteiros: `competencia_year: int` + `competencia_month: int` (1-12).
**D-05:** `FinancialEntry` não tem campo de valor próprio — herda `amount` e `type` de `Movement` via relação.
**D-06:** Hierarquia de categorias com duas entidades distintas: `Category` (pai) e `Subcategory` (filha com FK `category_id → Category.id`).
**D-07:** Elimina self-referencial — gerador não precisa de suporte a `self_referential`.
**D-08:** `FinancialEntry.subcategory_id` referencia `Subcategory`.
**D-09:** `Subcategory` simplesmente não tem campo para apontar para outra `Subcategory` — CAT-03 enforced pelo schema.
**D-10:** Constraints de coluna única (`import_hash`, `movement_id`) declaradas como `unique: true` no campo.
**D-11:** Novo bloco `filters:` nos YAMLs gera `Index` no banco. Sintaxe:
```yaml
filters:
  - fields: [account_id]
  - fields: [competencia_year, competencia_month]
```
Gerador emite `Index('ix_{table}_{fields}', '{field1}', '{field2}')` em `__table_args__`.
**D-12:** `unique_together:` deferido — não implementar nesta fase.

### Claude's Discretion

Nenhum item marcado como Claude's Discretion nesta fase.

### Deferred Ideas (OUT OF SCOPE)

- `unique_together:` no DSL — UniqueConstraint composta de múltiplas colunas.
- `filters:` como base para query params automáticos na API (Phase 7+).
- Registro dos routers financeiros em `main.py` — pode ir para Phase 7 (decisão do planner).
</user_constraints>

---

## Summary

Esta fase é puramente técnica: não entrega requisitos funcionais visíveis ao usuário, mas constrói o fundamento de schema e geração de código que todas as fases seguintes do M2 precisam. O trabalho cobre três eixos simultâneos que devem ser coordenados na ordem certa: (1) extensão do gerador DSL em `scripts/generate_code.py` para suportar `Decimal`, `sa_column`, `__table_args__` com `Index`, e o bloco `filters:`; (2) criação dos 5 YAMLs DSL em `dsl/entities/` e registro no `dsl/manifest.yaml`; (3) preparação do Alembic (naming_convention em `alembic/env.py`, importação dos novos modelos) e geração/aplicação da migration `0002`.

O gerador atual (SQLModel 0.0.38, SQLAlchemy 2.0.43, Python 3.12.3) já suporta domínios multi-entidade, relacionamentos cross-domain, link models e imports via `TYPE_CHECKING`. A extensão desta fase é incremental: adicionar tratamento de `Decimal`, suporte a `__table_args__` com `Index`, e registrar `finances` no `DOMAIN_TO_ENTITY_NAME`. O ponto crítico de sequência é: `naming_convention` deve ser adicionada ao `alembic/env.py` **antes** de gerar a migration 0002 — se a migration for gerada primeiro, as constraints terão nomes automáticos do PostgreSQL (não os nomes padronizados) e isso não pode ser corrigido sem dropar e recriar as constraints.

**Recomendação primária:** Executar em 3 ondas sequenciais — Wave 1: extender gerador + criar YAMLs + gerar código; Wave 2: configurar Alembic + importar modelos + gerar + aplicar migration 0002; Wave 3: testes de validação (importação Python OK, `alembic upgrade/downgrade` OK).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tipo Decimal no DSL | Gerador (`scripts/generate_code.py`) | — | O gerador mapeia tipos DSL para Python/SA; Decimal requer tratamento especial com `sa_column` |
| Bloco `filters:` → `Index` | Gerador (`scripts/generate_code.py`) | Migration (Alembic) | O gerador emite `__table_args__`; o Alembic captura via autogenerate |
| 5 YAMLs DSL | `dsl/entities/` | `dsl/manifest.yaml` | Fonte de verdade dos schemas financeiros |
| Código gerado (`models.py`, `router.py`, `operations.py`) | `src/caramello/finances/` | — | Gerado automaticamente; não editar diretamente |
| naming_convention | `alembic/env.py` | — | Deve ser configurado antes de qualquer migration nova |
| Migration 0002 | `alembic/versions/` | Banco PostgreSQL | Alembic autogenerate a partir dos modelos importados |
| Registro de novos modelos no Alembic | `alembic/env.py` | — | Alembic autogenerate requer que todos os SQLModel table=True estejam importados no env.py |

---

## Standard Stack

### Core (verificado no ambiente)
| Biblioteca | Versão | Propósito | Por que padrão |
|------------|--------|-----------|----------------|
| `sqlmodel` | 0.0.38 | ORM + validação Pydantic | Já instalado; `Field(sa_column=...)` suportado |
| `sqlalchemy` | 2.0.43 | Backend SA; `Column`, `Numeric`, `Index` | Já instalado via sqlmodel |
| `alembic` | 1.16.5 | Migrations incrementais | Já instalado; suporta async |
| `decimal` (stdlib) | — | Precisão arbitrária para valores monetários | Stdlib Python |
| `pyyaml` | — | Leitura dos YAMLs DSL | Já instalado |

[VERIFIED: uv run python -c "import sqlmodel; print(sqlmodel.__version__)"]

### Sem pacotes novos nesta fase
Nenhuma dependência nova precisa ser instalada para a Phase 6. As libs necessárias para fases posteriores (`ofxparse`, `openpyxl`, `rapidfuzz`) são explicitamente **fora de escopo**.

---

## Package Legitimacy Audit

Nenhum pacote externo novo é instalado nesta fase. Seção não aplicável.

---

## Architecture Patterns

### System Architecture Diagram

```
dsl/entities/*.yaml (5 novos)
        |
        v
scripts/generate_code.py  (EXTENDIDO)
  - map_type_to_python: + Decimal → Decimal (sa_column path)
  - get_field_definition: + sa_column=Column(Numeric(15,2)) para Decimal
  - _consolidate_models: + needs_decimal → imports (decimal.Decimal, sqlalchemy.Column/Numeric)
  - novo: _build_table_args: filters: → __table_args__ = (Index(...), ...)
  - DOMAIN_TO_ENTITY_NAME: + 'finances' entry
  - _run_ruff_fix: + descoberta dinâmica de domínios
        |
        v
src/caramello/finances/
  ├── __init__.py
  ├── models.py    (5 entidades × 4 classes = até 20 classes)
  ├── router.py    (CRUD gerado — sem lógica de negócio)
  └── operations.py (stub: # CARAMELLO-GENERATED: stub)
        |
        v
alembic/env.py  (MODIFICADO)
  - SQLModel.metadata.naming_convention = {...}  ← ANTES dos imports de modelos
  - import Account, Movement, FinancialEntry, Category, Subcategory
        |
        v
alembic/versions/0002_finances_schema.py  (GERADO via autogenerate)
  - down_revision = "0001"
  - Tabelas: account, movement, financial_entry, category, subcategory
  - Tipos: NUMERIC(15,2), VARCHAR, INTEGER, BOOLEAN, UUID, TIMESTAMP
  - Constraints: UNIQUE(movement_id), UNIQUE(import_hash)
  - Índices: ix_account_family_id, ix_movement_account_id, ix_financial_entry_year_month, etc.
        |
        v
PostgreSQL (caramello_dev)
  - alembic upgrade head → 5 novas tabelas
  - alembic downgrade -1 → reverte completamente
```

### Estrutura de Projeto Após Phase 6
```
dsl/
├── entities/
│   ├── account.yaml          (NOVO — domain: finances)
│   ├── movement.yaml         (NOVO — domain: finances)
│   ├── financial_entry.yaml  (NOVO — domain: finances)
│   ├── category.yaml         (NOVO — domain: finances)
│   └── subcategory.yaml      (NOVO — domain: finances)
├── manifest.yaml             (ATUALIZADO — +5 entries)
└── operations/
    └── finances.yaml         (NOVO — stub operations)

scripts/
└── generate_code.py          (MODIFICADO — Decimal, filters:, ruff dinâmico)

src/caramello/finances/
├── __init__.py
├── models.py
├── router.py
└── operations.py

alembic/
├── env.py                    (MODIFICADO — naming_convention + finances imports)
└── versions/
    └── 0002_finances_schema.py (NOVO)
```

### Pattern 1: Campo Decimal no DSL e no Modelo Gerado

**O que é:** Campos monetários no YAML usam tipo `Decimal`. O gerador emite `sa_column=Column(Numeric(15, 2))` para garantir precisão NUMERIC(15,2) no banco.

**Quando usar:** Todo campo de valor financeiro (`amount`, etc.).

```yaml
# No YAML DSL:
- name: amount
  type: Decimal
  nullable: false
  description: "Valor da movimentação."
```

```python
# O que o gerador deve emitir em models.py:
# Source: verificado via uv run python (SQLModel 0.0.38)
from decimal import Decimal
from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel

class Movement(SQLModel, table=True):
    __tablename__ = "movement"
    # ...
    amount: Decimal = Field(sa_column=Column(Numeric(15, 2), nullable=False))
```

**Por que `sa_column` e não `Field(ge=0)`:** `Field(...)` sozinho sem `sa_column` para Decimal produziria `FLOAT` no banco (SA infere por mapeamento default). `sa_column=Column(Numeric(15, 2))` garante `NUMERIC(15,2)` explicitamente. [VERIFIED: testes locais com SQLModel 0.0.38]

### Pattern 2: Bloco `filters:` → `__table_args__` com `Index`

**O que é:** O bloco YAML `filters:` declara filtros naturais da entidade. O gerador emite `__table_args__` com `Index(...)` para cada entrada.

```yaml
# No YAML DSL:
filters:
  - fields: [account_id]
  - fields: [competencia_year, competencia_month]
```

```python
# O que o gerador deve emitir:
# Source: verificado via uv run python (SQLModel 0.0.38 + SQLAlchemy 2.0.43)
from sqlalchemy import Column, Index, Numeric
from sqlmodel import Field, SQLModel

class FinancialEntry(SQLModel, table=True):
    __tablename__ = "financial_entry"
    __table_args__ = (
        Index("ix_financial_entry_account_id", "account_id"),
        Index("ix_financial_entry_year_month", "competencia_year", "competencia_month"),
    )
    # ...
```

**Nomenclatura do Index:** `ix_{table_name}_{field1}_{field2}` — consistente com o `naming_convention` a ser configurado no Alembic.

**Importante:** `__table_args__` deve ser uma tupla de constraints/indexes. Se nenhum `filters:` for declarado, não emitir `__table_args__`. [VERIFIED: testes locais com SQLModel 0.0.38]

### Pattern 3: naming_convention no Alembic

**O que é:** Configurar `SQLModel.metadata.naming_convention` em `alembic/env.py` **antes** das importações de modelos garante que todas as constraints geradas pelo autogenerate recebam nomes determinísticos.

```python
# alembic/env.py — ANTES de qualquer import de modelo
# Source: padrão SQLAlchemy + Alembic, verificado [ASSUMED] + padrão do ecossistema
from sqlmodel import SQLModel

SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# DEPOIS: imports de modelos (para autogenerate)
from caramello.families.models import ...  # noqa já existente
from caramello.finances.models import (    # NOVO
    Account,
    Category,
    FinancialEntry,
    Movement,
    Subcategory,
)
```

[VERIFIED: `SQLModel.metadata.naming_convention = {...}` aceito sem erro — testado localmente]

### Pattern 4: Operações stub para `finances`

**O que é:** `dsl/operations/finances.yaml` com domínio `finances`. O gerador produz `src/caramello/finances/operations.py` com anotação `# CARAMELLO-GENERATED: stub`.

**Pré-requisito:** Adicionar `'finances': 'Account'` em `DOMAIN_TO_ENTITY_NAME` (ou a entidade principal do domínio — `Account` é a âncora mais lógica para o stub inicial). [ASSUMED — o valor da classe canônica para o domínio `finances` não tem impacto funcional nesta fase, pois o stub não é registrado em `main.py`]

### Anti-Patterns a Evitar

- **Editar `src/caramello/finances/models.py` diretamente:** Arquivo gerado — qualquer edição manual será sobrescrita na próxima geração. Editar YAML + gerar.
- **Gerar a migration 0002 antes de configurar naming_convention:** As constraints geradas receberão nomes automáticos do PostgreSQL (`constraint_n`) em vez de nomes padronizados. Corrigi-los depois requer DROP + CREATE constraint — complexidade desnecessária.
- **Usar `float` em campos de valor monetário:** `FLOAT` no banco perde precisão (`0.10 + 0.20 ≠ 0.30`). Apenas `NUMERIC(15,2)` + `Decimal` Python.
- **Deixar `_run_ruff_fix` hardcoded sem `finances`:** A função atual lista explicitamente `("user", "family", "users", "families")`. O domínio `finances` não será formatado com ruff após a geração. Corrigir para descoberta dinâmica.
- **Registrar `finances.router` em `main.py` antes do `FastApiMCP`:** Os routers financeiros registrados depois de `mcp.mount_http()` não aparecem como ferramentas MCP (Pitfall P7 do ROADMAP). Se registrar nesta fase, registrar ANTES do bloco `mcp = FastApiMCP(...)`.

---

## Don't Hand-Roll

| Problema | Não construir | Usar em vez disso | Por quê |
|----------|---------------|-------------------|---------|
| Precisão monetária | Arredondamento manual de float | `Column(Numeric(15,2))` + `Decimal` Python | NUMERIC(15,2) é a solução padrão SQL para valores monetários |
| Nomenclatura de constraints | Nomes manuais por constraint | `MetaData(naming_convention={...})` no Alembic | Nomes determinísticos = migrations seguras e reversíveis |
| Índices compostos | `CREATE INDEX` manual em migration | `Index(...)` em `__table_args__` capturado pelo autogenerate | Autogenerate detecta e emite `op.create_index` automaticamente |
| Ordenação de entidades no `models.py` | Reordenação manual pós-geração | Link models primeiro (`is_link_model: true`) | O gerador já faz isso em `_consolidate_models` via `sorted()` |

---

## Common Pitfalls

### Pitfall 1: `down_revision` incorreto na migration 0002

**O que falha:** A migration `0002` é gerada com `down_revision = None` ou com valor errado, causando branch no histórico do Alembic.

**Por que acontece:** Alembic usa o `head` do momento da geração. Se houver múltiplas heads ou se o banco estiver em estado inesperado, o valor pode ser incorreto.

**Como evitar:** Após gerar `0002_finances_schema.py`, executar `alembic history --verbose` e verificar que a cadeia é `None → 0001 → 0002 (head)`. Confirmar que `down_revision = "0001"` no arquivo gerado. [VERIFIED: `alembic history --verbose` executado — revisão atual é `0001 (head)`]

**Sinais de alerta:** `alembic history` mostra dois heads; `alembic upgrade head` falha com `Multiple head revisions are present`.

### Pitfall 2: `_run_ruff_fix` não aplica ruff em `finances/`

**O que falha:** O código gerado em `src/caramello/finances/` não é formatado pelo ruff. Pode conter linhas longas ou problemas de isort.

**Por que acontece:** A função `_run_ruff_fix` em `generate_code.py` hardcodes os diretórios `("user", "family", "users", "families")` — `finances` não está na lista.

**Como evitar:** Modificar `_run_ruff_fix` para descobrir dinamicamente todos os subdiretórios existentes em `src/caramello/` (ou adicionar `"finances"` explicitamente). Recomendado: descoberta dinâmica via `[d.name for d in src_dir.iterdir() if d.is_dir() and not d.name.startswith("_") and not d.name == "shared" and not d.name == "core"]`.

### Pitfall 3: `sa_column` e `unique=True` no mesmo Field

**O que falha:** `Field(unique=True, sa_column=Column(...))` — quando `sa_column` está presente, o `Field` passa o controle da coluna SA inteiramente para o `Column()` fornecido. O parâmetro `unique=True` do Field é ignorado. A constraint `UNIQUE` precisa ser declarada dentro do `Column(...)` ou em `__table_args__`.

**Como evitar:**
```python
# ERRADO — unique=True no Field é ignorado quando sa_column está presente:
amount: Decimal = Field(unique=True, sa_column=Column(Numeric(15, 2)))

# CORRETO — unique dentro do Column():
import_hash: str | None = Field(sa_column=Column(sa.String, unique=True, nullable=True))
# OU para Decimal sem unique: basta sa_column=Column(Numeric(15, 2))
```
Para campos `Decimal` que não precisam de `UNIQUE` (ex: `amount`), usar `sa_column=Column(Numeric(15, 2), nullable=False)`. Para campos `str` com `unique: true` no YAML (ex: `import_hash`), o gerador atual emite `Field(unique=True)` que funciona para `str` (sem `sa_column`). [ASSUMED — comportamento com unique: true + Decimal não testado em combinação]

### Pitfall 4: Import de `finances.models` cria ciclo com `users/` ou `families/`

**O que falha:** `finances/models.py` importa `User` e `Family` (via FKs). Se `users/models.py` importar de `finances/`, haveria ciclo. O grafo de dependência atual não tem ciclo se `finances` só importa de `users`/`families` e não o contrário.

**Como evitar:** Os 5 YAMLs financeiros referenciam `user.id` e `family.id` apenas via `foreign_key:` em campos, não via `relationships:` cross-domain para User/Family. Relacionamentos cross-domain devem ir apenas de `finances` → `users`/`families`, nunca o inverso. O gerador detecta ciclos via `_build_domain_fk_graph` e usaria `TYPE_CHECKING` se necessário — mas com a estrutura planejada, não deve haver ciclo.

### Pitfall 5: `__table_args__` conflita com herança de `SQLModel`

**O que falha:** SQLModel com `table=True` herda `__table_args__` de classes pai de forma inesperada. Se duas entidades no mesmo `models.py` definirem `__table_args__`, pode haver colisão.

**Como evitar:** `__table_args__` definido diretamente na classe, não em `SQLModel` base. O gerador atual não emite `__table_args__` — a extensão para `filters:` deve emiti-lo na classe concreta (model com `table=True`), não nas classes `Read`/`Create`/`Update`. [VERIFIED: testado localmente — múltiplas classes com `__table_args__` no mesmo módulo funcionam corretamente]

### Pitfall 6: naming_convention definida DEPOIS dos imports de modelo

**O que falha:** Se `SQLModel.metadata.naming_convention` for definida depois que qualquer classe `SQLModel, table=True` for importada, as constraints de tabelas já importadas não herdarão a naming_convention.

**Como evitar:** Em `alembic/env.py`, a linha `SQLModel.metadata.naming_convention = {...}` deve vir imediatamente após `from sqlmodel import SQLModel`, **antes** de qualquer `from caramello.*.models import ...`.

---

## Code Examples

### Exemplo completo: Account YAML

```yaml
# dsl/entities/account.yaml
# Source: baseado em family.yaml (padrão estabelecido) + decisões D-01/D-02
name: Account
domain: finances
description: "Conta bancária, cartão, poupança ou investimento de um membro da família."
table_name: account

fields:
  - name: id
    type: int
    primary_key: true
    description: "Chave primária interna."

  - name: uuid
    type: UUID
    unique: true
    default_factory: uuid4
    nullable: false
    description: "Identificador público único."

  - name: family_id
    type: int
    foreign_key: "family.id"
    nullable: false
    description: "FK para família dona da conta."

  - name: name
    type: str
    max_length: 100
    nullable: false
    description: "Nome descritivo da conta (ex: Nubank PF)."

  - name: type
    type: str
    max_length: 20
    nullable: false
    description: "Tipo: corrente, poupanca, cartao, investimento."

  - name: currency
    type: str
    max_length: 3
    default: "BRL"
    nullable: false
    description: "Código ISO 4217 da moeda."

  - name: is_active
    type: bool
    default: true
    nullable: false
    description: "Conta ativa (false = arquivada)."

  - name: created_at
    type: datetime
    default_factory: now_utc
    nullable: false
    description: "Data de criação."

  - name: updated_at
    type: datetime
    default_factory: now_utc
    nullable: false
    description: "Data da última atualização."

filters:
  - fields: [family_id]
```

### Exemplo: extensão em `map_type_to_python` para Decimal

```python
# scripts/generate_code.py — modificação em map_type_to_python
# Source: verificado via testes locais com SQLModel 0.0.38
type_map = {
    # ... tipos existentes ...
    "decimal": "Decimal",  # NOVO: Decimal nativo
}
```

### Exemplo: extensão em `get_field_definition` para Decimal

```python
# scripts/generate_code.py — modificação em get_field_definition
# Source: verificado via testes locais
def get_field_definition(field: dict[str, Any], force_optional: bool = False) -> str:
    # ... lógica existente ...
    if ftype == "Decimal":
        # Decimal usa sa_column para garantir NUMERIC(15,2)
        nullable_kw = "nullable=False" if not is_nullable else "nullable=True"
        return f"    {fname}: {type_str} = Field(sa_column=Column(Numeric(15, 2), {nullable_kw}))"
    # ... restante da lógica ...
```

### Exemplo: geração de `__table_args__` a partir de `filters:`

```python
# Novo helper em scripts/generate_code.py
# Source: verificado via testes locais com SQLAlchemy 2.0.43
def _build_table_args(entity_data: dict[str, Any]) -> str | None:
    """Gera __table_args__ a partir do bloco filters: do YAML."""
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
    args_block = "    __table_args__ = (\n" + "\n".join(index_lines) + "\n    )\n"
    return args_block
```

### Exemplo: `alembic/env.py` com naming_convention (trecho)

```python
# alembic/env.py — TRECHO MODIFICADO
# Source: padrão SQLAlchemy/Alembic — verificado [ASSUMED padrão de ecossistema]
from sqlmodel import SQLModel  # noqa: E402

# naming_convention DEVE vir antes de qualquer import de modelo
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

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

## Estado da Arte

| Abordagem Antiga | Abordagem Atual | Impacto Nesta Fase |
|------------------|-----------------|--------------------|
| `float` para valores monetários | `NUMERIC(15,2)` + `Decimal` | D-01/D-02 mandatório — gerador deve implementar |
| `Category` self-referencial (1 entidade) | `Category` + `Subcategory` (2 entidades) | D-06 — ROADMAP desatualizado; CONTEXT.md prevalece |
| `__table_args__` manual pós-geração | Bloco `filters:` → autogenerate via `__table_args__` | D-11 — extensão nova do gerador |
| Domínios hardcoded em `_run_ruff_fix` | Descoberta dinâmica de domínios | Bugfix necessário para incluir `finances` |
| Nenhum `naming_convention` no Alembic | `MetaData(naming_convention={...})` antes de migrations | Constraint antes da migration 0002 |

**Obsoleto/não usar:**
- `category.yaml` com `parent_id: int` self-referencial — abordagem ROADMAP original substituída por D-06.
- `is_link_model: true` sem `id`/`uuid` — correto para join tables M:M; não aplicável às 5 entidades financeiras (todas têm `id` + `uuid`).

---

## Assumptions Log

| # | Claim | Seção | Risco se Errado |
|---|-------|-------|-----------------|
| A1 | `'finances': 'Account'` é a classe canônica certa para `DOMAIN_TO_ENTITY_NAME` | Standard Stack / Pattern 4 | O stub de operations.py usa esse mapeamento para o import; se errado, o stub gera import incorreto. Impacto baixo: stub não é registrado em `main.py` nesta fase. |
| A2 | `naming_convention` padrão `{'ix': 'ix_%(column_0_label)s', ...}` é suficiente para este projeto | Pattern 3 | Se o projeto já tiver constraints sem nome padronizado em 0001, o Alembic pode gerar migrations de rename desnecessárias. Mitigação: verificar output do autogenerate antes de aplicar. |
| A3 | `unique: true` em campos `str` sem `sa_column` continua funcionando corretamente (ex: `import_hash`) | Common Pitfalls / Pitfall 3 | Comportamento verificado para SQLModel 0.0.25 (CLAUDE.md) mas não para 0.0.38. Se comportamento mudou, campos `UNIQUE` podem não ser capturados pelo autogenerate. |

**Se esta tabela estivesse vazia:** Todas as claims foram verificadas ou citadas.

---

## Open Questions

1. **Registrar `finances.router` em `main.py` nesta fase ou deixar para Phase 7?**
   - O que sabemos: CONTEXT.md marca como deferred/decisão do planner; ROADMAP Phase 7 lista o registro como constraint técnica.
   - O que está incerto: se registrar agora, os endpoints CRUD gerados ficam expostos sem lógica de negócio (retornam 200 com dados vazios). Se deixar para Phase 7, a Phase 6 não tem integração testável.
   - Recomendação: **não registrar em `main.py` nesta fase** — manter o escopo da fase técnico. Phase 7 registra os routers de operações reais.

2. **`dsl/operations/finances.yaml` — quais operações listar no stub?**
   - O que sabemos: Phase 7 implementará Account + Category CRUD. O stub de Phase 6 é apenas o scaffolding.
   - O que está incerto: o gerador usa `DOMAIN_TO_ENTITY_NAME` para inferir o import principal — mas `finances` tem 5 entidades, não uma.
   - Recomendação: criar `finances.yaml` com `domain: finances` e uma operação placeholder; ou simplesmente criar o arquivo `operations.py` manualmente como stub sem passar pelo gerador. O gerador de operations foi projetado para domínios mono-entidade.

3. **`schema.yaml` precisa ser atualizado com `filters:` e `Decimal`?**
   - O que sabemos: `dsl/schema.yaml` define o schema de validação dos YAMLs; `test_schema_yaml_has_domain_property` valida que `domain` está em `properties`.
   - O que está incerto: o gerador não usa `schema.yaml` para validar YAMLs na geração — é apenas documentação/validação externa. Não bloqueia a geração.
   - Recomendação: atualizar `schema.yaml` para incluir `filters:` e documentar `Decimal` como tipo válido — boa prática de manutenção, mas não bloqueante.

---

## Environment Availability

| Dependência | Requerida por | Disponível | Versão | Fallback |
|-------------|---------------|------------|--------|---------|
| PostgreSQL | Migration 0002 (upgrade/downgrade) | Depende do ambiente — não verificado nesta análise | — | Sem fallback; PostgreSQL é obrigatório (CLAUDE.md) |
| `uv` | Geração de código, testes | Sim (ambiente de dev) | — | — |
| `alembic` | Migrations | Sim | 1.16.5 | — |
| `ruff` | Formatação pós-geração | Sim (presente via `uv run python -m ruff`) | — | Geração funciona sem ruff; só falta formatação |

**Dependências sem fallback que podem bloquear:** PostgreSQL para validar `alembic upgrade head`. Se o banco não estiver disponível no ambiente de execução, o planner deve incluir instrução para configurar conexão.

---

## Validation Architecture

### Test Framework
| Propriedade | Valor |
|-------------|-------|
| Framework | pytest 9.0.1 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) ou auto-discovery |
| Comando rápido | `uv run pytest tests/test_generator.py -v` |
| Suite completa | `uv run pytest -v` |

### Phase Requirements → Test Map

Esta fase é técnica sem requisitos funcionais numerados. Os critérios de sucesso do ROADMAP §Phase 6 mapeiam para os seguintes testes:

| Critério | Comportamento | Tipo de Teste | Comando | Arquivo |
|----------|--------------|---------------|---------|---------|
| SC-1 | `alembic upgrade head` aplica 0002 sem erro | integração (requer banco) | `uv run alembic upgrade head` | manual |
| SC-2 | `alembic downgrade -1` reverte sem erro | integração (requer banco) | `uv run alembic downgrade -1` | manual |
| SC-3 | Tabelas + constraints + tipos corretos | integração (requer banco) | SQL inspect manual | manual |
| SC-4 | `from caramello.finances import models` sem ImportError | unit (sem banco) | `uv run python -c "from caramello.finances import models; print('OK')"` | inline |
| SC-5 | YAMLs financeiros com `domain: finances` | unit | `uv run pytest tests/test_generator.py::test_finances_yamls_have_domain_finances` | ❌ Wave 0 |
| SC-6 | `models.py` não usa `float` em campos monetários | unit | `uv run pytest tests/test_generator.py::test_finances_models_no_float` | ❌ Wave 0 |
| SC-7 | Gerador emite `Numeric(15, 2)` para tipo `Decimal` | unit | `uv run pytest tests/test_generator.py::test_generator_decimal_emits_numeric` | ❌ Wave 0 |
| SC-8 | `__table_args__` emitido para entidades com `filters:` | unit | `uv run pytest tests/test_generator.py::test_generator_filters_emits_table_args` | ❌ Wave 0 |

### Sampling Rate
- **Por commit de tarefa:** `uv run pytest tests/test_generator.py -v`
- **Por merge de wave:** `uv run pytest -v` (suite completa)
- **Phase gate:** `uv run pytest -v` verde + `uv run alembic upgrade head` + `uv run alembic downgrade -1`

### Wave 0 Gaps (testes a criar)
- [ ] `tests/test_generator.py::test_finances_yamls_have_domain_finances` — verifica `domain: finances` nos 5 YAMLs
- [ ] `tests/test_generator.py::test_finances_models_no_float` — `finances/models.py` não contém `float` em campos de valor
- [ ] `tests/test_generator.py::test_generator_decimal_emits_numeric` — `generate_models` com campo `Decimal` emite `Column(Numeric(15, 2))`
- [ ] `tests/test_generator.py::test_generator_filters_emits_table_args` — entidade com `filters:` gera `__table_args__` com `Index`
- [ ] `tests/test_generator.py::test_finances_models_import_ok` — `from caramello.finances import models` não levanta `ImportError`

---

## Security Domain

Esta fase não expõe endpoints funcionais nem processa dados de usuário. Os modelos gerados não têm lógica de autenticação ou autorização — isso é responsabilidade de Phase 7. O router gerado usa `Depends(get_current_user)` (herdado do template do gerador), o que é correto se os routers forem registrados em `main.py` futuramente.

AUTH-FIN-01 e AUTH-FIN-02 (requisitos de autorização para o domínio finances) são responsabilidade de Phase 7, não desta fase.

### ASVS Aplicável

| Categoria ASVS | Aplica | Controle Padrão |
|----------------|--------|-----------------|
| V2 Autenticação | Não (Phase 7) | — |
| V3 Sessão | Não | — |
| V4 Controle de Acesso | Não (Phase 7) | — |
| V5 Validação de Input | Parcial — Pydantic valida tipos nos schemas gerados | SQLModel/Pydantic |
| V6 Criptografia | Não | — |

---

## Sources

### Primary (HIGH confidence)
- Testes locais com `uv run python` (SQLModel 0.0.38, SQLAlchemy 2.0.43) — padrões `sa_column`, `Index`, `__table_args__`, `naming_convention`
- `scripts/generate_code.py` — código atual do gerador lido integralmente
- `alembic/versions/0001_initial_schema.py` — padrão de migration existente; `revision = "0001"`
- `alembic/env.py` — estrutura atual para extensão
- `src/caramello/families/models.py` — padrão de modelos gerados
- `src/caramello/families/operations.py` — padrão de operations stub/implemented
- `.planning/phases/06-funda-o-dsl-schema/06-CONTEXT.md` — decisões locked

### Secondary (MEDIUM confidence)
- `docs/dsl_rules.md` — regras de nomenclatura DSL (referência interna do projeto)
- `dsl/entities/family.yaml` — template de referência para YAMLs novos
- `tests/test_generator.py` — baseline de testes existentes (16 passando)

### Tertiary (LOW confidence)
- Padrão `naming_convention` do Alembic: baseado em conhecimento de treinamento [ASSUMED] — amplamente documentado no ecossistema SA/Alembic mas não verificado via Context7 nesta sessão

---

## Metadata

**Breakdown de confiança:**
- Gerador (`generate_code.py`): HIGH — código lido + testado localmente
- Padrão `sa_column` + `Numeric`: HIGH — verificado com uv run python
- Padrão `__table_args__` + `Index`: HIGH — verificado com uv run python
- naming_convention Alembic: MEDIUM — padrão do ecossistema, testado localmente, mas não verificado em docs oficiais nesta sessão
- YAMLs DSL (conteúdo): MEDIUM — baseado nos padrões existentes + decisões do CONTEXT.md
- Migration 0002 (autogenerate): MEDIUM — depende de banco disponível para validação final

**Data da pesquisa:** 2026-05-31
**Válido até:** 2026-06-30 (stack estável)
