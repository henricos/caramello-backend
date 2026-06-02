# Phase 8: Movimentações + Importação - Research

**Pesquisado em:** 2026-06-02
**Domínio:** Importação de arquivos financeiros, deduplicação por hash, FastAPI UploadFile, Alembic migration
**Confiança geral:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: `amount` com sinal** — Positivo = crédito, negativo = débito. Remover campo `type: str` do DSL YAML. Migration: `ALTER TABLE movement DROP COLUMN type`.
- **D-02: Remover `is_duplicate`** — Campo removido do DSL YAML e da migration. Duplicatas suspeitas nunca são inseridas — são retornadas para confirmação.
- **D-03: Migration 0003** — DROP COLUMN `type`, DROP COLUMN `is_duplicate`. Verificar `down_revision` com `alembic history --verbose`.
- **D-04: OFX com FITID = deduplicação definitiva** — `transaction.id` (FITID) usado como `import_hash`. Hash match = duplicata certa. Não inserir, não perguntar.
- **D-05: CSV/XLSX sem ID bancário = duplicata suspeita** — SHA-256 de `(account_id|date|amount|description_normalizada)`. Hash match → `potential_duplicates[]` para confirmação.
- **D-06: Normalização conservadora** — `description.strip().lower()` + colapsar espaços múltiplos.
- **D-07: Hash de `(account_id|date|amount|description_normalizada)`** — Sem campo `type`.
- **D-08: Endpoint de confirmação** — `POST /import/confirm` recebe `potential_duplicates` confirmadas; insere com `import_hash=None`.
- **D-09: Detecção por query param** — `?format=csv|ofx|xlsx`.
- **D-10: Auto-detect separador CSV** — `csv.Sniffer` antes de parsear.
- **D-11: Colunas obrigatórias CSV** — `date`, `amount`, `description` (case-insensitive, por header).
- **D-12: Formatos de data** — ISO 8601 (`YYYY-MM-DD`) e BR (`DD/MM/YYYY`). Tentar ISO primeiro.
- **D-13: Linhas inválidas não abortam o lote** — Reportadas em `error_lines[]`. Abortar se >50% das linhas falharem (422).
- **D-14: Shape da resposta de importação** — `{inserted, duplicates_skipped, potential_duplicates[], error_lines[], movements[]}`.
- **D-15: GET incluído nesta fase** — `GET /finances/accounts/{uuid}/movements?limit=50&offset=0&date_from=&date_to=`.
- **D-16: MovementReadPublic** — Expõe `uuid`, `date`, `amount`, `description`, `import_hash` (opcional), `created_at`, `updated_at`. Sem `account_uuid` na resposta.
- **D-17: POST individual — 409 se hash match** — Retorna UUID da movimentação existente. Endpoint de confirmação disponível para insistir.

### Claude's Discretion

- Estrutura dos parsers: arquivo separado `finances/parsers/` ou funções em `finances/services.py`.
- Tratamento de encoding OFX: testar com extrato real de banco BR.
- Limiar de 50% de erros pode ser ajustado.

### Deferred Ideas (OUT OF SCOPE)

- Filtros avançados no GET /movements além de `date_from/date_to`.
- Soft delete de movimentação.
- Preview antes de confirmar (importação sem persistência).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Descrição | Suporte da pesquisa |
|----|-----------|---------------------|
| MOV-01 | Usuário pode registrar movimentação individual (data, valor, descrição) | D-17: hash SHA-256, 409 se duplicata. Padrão session.add + await session.commit. |
| MOV-02 | Usuário pode importar movimentações em lote via CSV | D-10/11/12/13: csv.Sniffer, headers case-insensitive, datas ISO+BR, error_lines[]. |
| MOV-03 | Usuário pode importar movimentações em lote via OFX ou XLSX | `ofxparse` (0.21) para OFX com FITID; `openpyxl` (3.1.5) com `read_only=True` para XLSX. |
| MOV-04 | Importação detecta duplicatas via hash — reimportar o mesmo arquivo não duplica | SHA-256 de `(account_id\|date\|amount\|desc_norm)`. Pre-check via `SELECT import_hash IN (...)`. |
| MOV-05 | Duplicatas marcadas — redesenhado: retornadas em `potential_duplicates[]` para confirmação | D-05/D-08: endpoint `/import/confirm` insere confirmadas com `import_hash=None`. |
</phase_requirements>

---

## Resumo

A Phase 8 implementa registro e importação de movimentações financeiras brutas no domínio `finances`. O trabalho tem três frentes paralelas: (1) modificar o schema DSL e gerar migration 0003 removendo `type` e `is_duplicate`; (2) implementar os parsers de importação (CSV/OFX/XLSX) em `finances/services.py`; (3) adicionar os endpoints no `finances/operations.py` existente.

O padrão de código já foi estabelecido nas Phases 6 e 7 — todos os endpoints de Movement seguem exatamente o mesmo estilo de `operations.py` (schemas públicos locais `*Public`, `session.exec()` para queries, `_require_family_access` para autorização, `from __future__ import annotations` no topo). A deduplicação usa pre-check via `SELECT import_hash IN (...)` como mecanismo primário; `on_conflict_do_nothing` como rede de segurança para race conditions. Duplicatas confirmadas pelo usuário são inseridas com `import_hash=None` (PostgreSQL permite múltiplos NULLs em coluna UNIQUE).

As duas bibliotecas novas (`ofxparse>=0.21` e `openpyxl>=3.1.5`) precisam ser adicionadas ao `pyproject.toml`. `python-multipart` já está no `uv.lock` (v0.0.29) pois é dependência transitiva do FastAPI — `UploadFile` já funciona.

**Recomendação primária:** Implementar parsers em `finances/services.py` (sem subpasta separada) — mantém consistência com a estrutura existente do projeto onde `services.py` já existe como stub esperando exatamente esta lógica.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Receber upload de arquivo | API / Backend (FastAPI endpoint) | — | `UploadFile` é dependency FastAPI; parsing acontece no mesmo processo |
| Autorização por família | API / Backend (`_require_family_access`) | — | Mesmo padrão das Phases 7; account → family_id → membership check |
| Parsing CSV/OFX/XLSX | API / Backend (`finances/services.py`) | — | Parsing é CPU-bound mas síncrono e rápido para extratos típicos (<10MB) |
| Deduplicação por hash | API / Backend + Database | — | Pre-check no banco (`SELECT ... IN`), hash computado em memória |
| Persistência com on_conflict_do_nothing | Database (PostgreSQL) | — | Constraint UNIQUE `import_hash` na tabela `movement` já existe |
| Serialização Decimal | API / Backend (schema Pydantic) | Database NUMERIC(15,2) | `Decimal` no Python ↔ `NUMERIC(15,2)` no PostgreSQL |
| Schema migration | Database (Alembic) | — | DROP COLUMN `type` e `is_duplicate` via migration 0003 |

---

## Standard Stack

### Core (verificado no projeto)

| Biblioteca | Versão atual | Propósito | Status |
|-----------|-------------|-----------|--------|
| FastAPI | 0.118.0 | Framework HTTP, `UploadFile`, roteamento | Instalado |
| SQLModel / SQLAlchemy async | 0.0.25 | ORM + queries; `session.exec()` e `session.execute()` | Instalado |
| asyncpg | >=0.31.0 | Driver PostgreSQL async | Instalado |
| Alembic | 1.16.5 | Migrations — migration 0003 a criar | Instalado |
| pydantic | 2.11.10 | Schemas públicos locais `*Public` | Instalado |
| python-multipart | 0.0.29 | Suporte a `UploadFile` multipart | Instalado (uv.lock) |

### Novas dependências (a adicionar ao pyproject.toml)

| Biblioteca | Versão no PyPI | Propósito | Por que usar |
|-----------|---------------|-----------|--------------|
| `ofxparse` | 0.21 | Parser OFX — expõe `transaction.id` (FITID) | Única lib OFX Python amplamente usada; cuida de encoding automaticamente; ~22k downloads/semana [ASSUMED — dados Snyk] |
| `openpyxl` | 3.1.5 | Parser XLSX — modo `read_only=True` para memória eficiente | 22M+ downloads/semana; padrão de fato para Excel em Python; suporte oficial [VERIFIED: pip index] |

**Instalação:**
```bash
uv add ofxparse>=0.21 openpyxl>=3.1.5
```

**Verificação de versão:**
```bash
pip index versions ofxparse   # → 0.21 (latest)
pip index versions openpyxl   # → 3.1.5 (latest)
```

### Stdlib (sem instalação adicional)

| Módulo | Uso |
|--------|-----|
| `csv` + `csv.Sniffer` | Parsing CSV, detecção automática de separador (`;` ou `,`) |
| `hashlib.sha256` | Cálculo do `import_hash` |
| `io.BytesIO` / `io.StringIO` | Wrapper para parsers que precisam de file-like object |
| `re` | Colapso de espaços em `description` (D-06) |
| `decimal.Decimal` | Precisão monetária — zero `float` |

---

## Package Legitimacy Audit

> `slopcheck` não pôde ser instalado nesta sessão (bloqueado por sandbox). Todos os pacotes abaixo são marcados como [ASSUMED] e devem ser verificados antes da instalação.

| Package | Registry | Idade | Downloads/semana | Source Repo | slopcheck | Disposição |
|---------|----------|-------|-----------------|-------------|-----------|------------|
| `ofxparse` | PyPI | ~15 anos (desde 2010) | ~22k [ASSUMED] | github.com/jseutter/ofxparse | não verificado | [ASSUMED] — planner deve add checkpoint:human-verify |
| `openpyxl` | PyPI | ~15 anos (desde 2010) | ~22M [ASSUMED] | foss.heptapod.net/openpyxl/openpyxl | não verificado | [ASSUMED] — planner deve add checkpoint:human-verify |
| `python-multipart` | PyPI | já no uv.lock (0.0.29) | — | — | — | Já presente — sem instalação |

**Observação:** `ofxparse` está marcado como "maintenance inactive" (sem nova versão em >12 meses conforme Snyk). O projeto está estável e a API não muda, mas vale conferir se a versão 0.21 é adequada. `openpyxl` é projeto ativo e amplamente utilizado.

**Packages removed due to slopcheck [SLOP] verdict:** nenhum
**Packages flagged as suspicious [SUS]:** nenhum — mas ambos marcados [ASSUMED] por ausência de verificação via slopcheck.

*Como slopcheck não estava disponível, o planner DEVE adicionar uma tarefa `checkpoint:human-verify` antes de executar `uv add ofxparse openpyxl`.*

---

## Architecture Patterns

### System Architecture Diagram

```
UploadFile (multipart/form-data)
         │
         ▼
finances/operations.py
  POST /accounts/{uuid}/movements/import?format=csv|ofx|xlsx
         │
         ├── 1. account_uuid → Account (session.exec)
         ├── 2. _require_family_access(account.family_id)
         ├── 3. content = await file.read()  [bytes]
         │
         ▼
finances/services.py → import_movements(content, format, account_id, account_uuid)
         │
         ├── parse_csv(content)   ─── csv.Sniffer + csv.DictReader
         ├── parse_ofx(content)   ─── ofxparse.OfxParser.parse(BytesIO)
         └── parse_xlsx(content)  ─── openpyxl.load_workbook(BytesIO, read_only=True)
                  │
                  ▼
           rows: list[ParsedRow]  {date, amount: Decimal, description, fitid?}
                  │
                  ▼
         compute_hash(account_id, row)
         ├── OFX: hash = sha256(fitid)   [D-04: deduplicação definitiva]
         └── CSV/XLSX: hash = sha256(f"{account_id}|{date}|{amount}|{norm_desc}")  [D-05]
                  │
                  ▼
         SELECT import_hash FROM movement
         WHERE import_hash IN (all_computed_hashes)
         [batch pre-check — uma query só]
                  │
                  ├── hash exists → duplicates_skipped (OFX) OU potential_duplicates[] (CSV/XLSX)
                  └── hash absent → insert
                           │
                           ▼
              session.add(Movement(...)) × N
              await session.commit()
              [pg_insert.on_conflict_do_nothing como safety net]
                           │
                           ▼
              ImportResponse {inserted, duplicates_skipped,
                              potential_duplicates[], error_lines[], movements[]}
```

### Estrutura de arquivos recomendada

```
src/caramello/finances/
├── __init__.py
├── models.py          ← gerado; será regenerado após editar movement.yaml
├── router.py          ← gerado; NÃO registrado em main.py (D-01 da Phase 7)
├── operations.py      ← implementado; estender com endpoints de Movement
└── services.py        ← implementar import_movements() e parsers aqui
```

> Decisão do planner (Claude's Discretion): parsers ficam dentro de `services.py` como funções privadas `_parse_csv`, `_parse_ofx`, `_parse_xlsx`. Mantém coesão: `services.py` é o módulo de lógica de negócio do domínio finances. Não justifica subpasta `parsers/` para apenas 3 funções.

### Padrão 1: UploadFile async em FastAPI

```python
# Source: FastAPI docs + verificado em .venv com UploadFile.read() async
from fastapi import UploadFile, File
import io

@router.post("/accounts/{account_uuid}/movements/import")
async def import_movements(
    account_uuid: UUID,
    file: UploadFile = File(...),
    format: Literal["csv", "ofx", "xlsx"] = Query(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    content: bytes = await file.read()
    # ... resolve account, check access, call services.import_movements()
```

### Padrão 2: Parsing CSV com Sniffer

```python
# Source: Python stdlib csv — verificado com Sniffer detectando ; e ,
import csv, io, re
from decimal import Decimal

def _parse_csv(content: bytes) -> list[ParsedRow]:
    text = content.decode("utf-8", errors="replace")
    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(text[:1024])
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    # headers case-insensitive: normalize to lowercase
    rows = []
    for i, row in enumerate(reader, start=2):  # linha 2 = primeira de dados
        norm = {k.strip().lower(): v for k, v in row.items()}
        # parse date: ISO primeiro, depois BR
        date = _parse_date(norm.get("date", ""), line=i)
        amount = _parse_amount(norm.get("amount", ""), line=i)
        rows.append(ParsedRow(date=date, amount=amount,
                              description=norm.get("description", ""), fitid=None))
    return rows
```

### Padrão 3: Parsing OFX com ofxparse

```python
# Source: github.com/jseutter/ofxparse — transaction.id é o FITID
from ofxparse import OfxParser
import io

def _parse_ofx(content: bytes) -> list[ParsedRow]:
    # ofxparse cuida de encoding (iso-8859-1, utf-8, cp1252)
    try:
        ofx = OfxParser.parse(io.BytesIO(content))
    except Exception:
        # Fallback: tentar com encoding explícito para bancos BR problemáticos
        text = content.decode("iso-8859-1", errors="replace")
        ofx = OfxParser.parse(io.StringIO(text))
    rows = []
    for txn in ofx.account.statement.transactions:
        rows.append(ParsedRow(
            date=txn.date,
            amount=Decimal(str(txn.amount)),
            description=str(txn.memo or txn.payee or ""),
            fitid=txn.id,  # FITID — usado como hash direto (D-04)
        ))
    return rows
```

### Padrão 4: Parsing XLSX com openpyxl read_only

```python
# Source: openpyxl docs — read_only=True para eficiência de memória
import openpyxl, io

def _parse_xlsx(content: bytes) -> list[ParsedRow]:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows_iter = iter(ws.rows)
    header_row = next(rows_iter, None)
    if header_row is None:
        wb.close()
        return []
    headers = [str(c.value or "").strip().lower() for c in header_row]
    # mapear índices das colunas obrigatórias
    try:
        date_idx = headers.index("date")
        amount_idx = headers.index("amount")
        desc_idx = headers.index("description")
    except ValueError as e:
        wb.close()
        raise ValueError(f"Coluna obrigatória ausente: {e}") from e
    rows = []
    for i, row in enumerate(rows_iter, start=2):
        cells = [c.value for c in row]
        # ... parse date, amount, description
        rows.append(ParsedRow(...))
    wb.close()  # OBRIGATÓRIO em read_only mode
    return rows
```

### Padrão 5: Deduplicação por hash — pre-check em lote

```python
# Source: padrão derivado de shared/auth.py + docs SQLAlchemy
# Pre-check: uma query para todos os hashes do lote
from sqlmodel import select

async def _check_existing_hashes(
    session: AsyncSession,
    hashes: list[str],
) -> set[str]:
    result = await session.execute(
        select(Movement.import_hash).where(Movement.import_hash.in_(hashes))
    )
    return {row[0] for row in result.fetchall()}
```

### Padrão 6: Inserção com on_conflict_do_nothing (safety net)

```python
# Source: shared/auth.py linhas 193-198 — mesmo padrão para Movement
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Inserção normal (após pre-check), com safety net para race conditions:
stmt = (
    pg_insert(Movement.__table__)
    .values([row.to_dict() for row in to_insert])
    .on_conflict_do_nothing(index_elements=["import_hash"])
)
await session.execute(stmt)
await session.commit()
```

### Padrão 7: 409 Conflict para movimentação individual duplicada

```python
# Source: HTTPException pattern — verificado no projeto
from fastapi import HTTPException

# Em create_movement (D-17):
existing = await session.exec(
    select(Movement).where(Movement.import_hash == computed_hash)
)
dup = existing.first()
if dup is not None:
    raise HTTPException(
        status_code=409,
        detail={"message": "Movimentação já existe", "existing_uuid": str(dup.uuid)},
    )
```

### Anti-Patterns a Evitar

- **`float` em campo monetário:** Sempre `Decimal`. `float(0.10) + float(0.20) = 0.30000000000000004`. [VERIFIED: testado no projeto]
- **`session.exec()` para queries com `IN`:** Usar `session.execute()` com `select(Movement.import_hash).where(Movement.import_hash.in_(...))`. `session.exec()` não lida bem com projeções parciais.
- **Editar `models.py` diretamente:** É gerado pelo DSL. Editar `dsl/entities/movement.yaml` e regenerar.
- **`import_hash` com valor duplicado no `/import/confirm`:** Inserir com `import_hash=None`. PostgreSQL permite múltiplos NULLs em coluna UNIQUE.
- **Fechar workbook openpyxl:** `read_only=True` requer `wb.close()` explícito — sem isso, leak de file handle.
- **`OfxParser.parse()` recebendo `str`:** Requer file-like object. Usar `io.BytesIO(content)` ou `io.StringIO(decoded)`.

---

## Don't Hand-Roll

| Problema | Não construir | Usar | Por quê |
|----------|--------------|------|---------|
| Parsing OFX | Parser OFX customizado | `ofxparse` | Lida com encoding (ISO-8859-1, UTF-8, cp1252), múltiplos formatos de data OFX, edge cases de extrato |
| Parsing XLSX | Leitura manual de ZIP/XML | `openpyxl` com `read_only=True` | XLSX é um ZIP de XMLs; parsear manualmente é frágil e lento |
| Detecção de separador CSV | Heurística manual | `csv.Sniffer` | Stdlib Python; cuida de `,`, `;`, `\t` e outros |
| Precisão monetária | `float` | `Decimal` | Erros de ponto flutuante são inaceitáveis em valores financeiros |
| Deduplicação de inserção | Verificação em Python loop | `on_conflict_do_nothing` (safety net) + pre-check SQL | Atômico, safe para concorrência, sem round-trips extras |

---

## Runtime State Inventory

> Esta fase modifica o schema de uma tabela existente. Aplicável o inventário de estado de runtime.

| Categoria | Itens encontrados | Ação necessária |
|-----------|------------------|-----------------|
| Stored data | Tabela `movement` já existe no banco `caramello_dev` com colunas `type` e `is_duplicate`. Pode ter dados de testes anteriores. | Migration 0003 `DROP COLUMN type, DROP COLUMN is_duplicate` — irreversível em produção se houver dados |
| Live service config | Nenhum serviço externo referencia o schema `movement` diretamente | Nenhuma |
| OS-registered state | Nenhum | Nenhum — verificado |
| Secrets/env vars | Nenhum segredo referencia `type` ou `is_duplicate` | Nenhuma |
| Build artifacts | `src/caramello/finances/models.py` gerado — será sobrescrito após editar `movement.yaml` | Regenerar com `bin/generate_code` |

**Nota crítica:** Se o banco `caramello_dev` tiver movimentações de testes com `type` preenchido, `DROP COLUMN type` é irreversível. Em desenvolvimento isso é aceitável (dados de teste). Em produção não há dados reais ainda (Phase 8 é a primeira implementação de `movement`).

---

## Common Pitfalls

### Pitfall 1: `float` em campo de valor monetário
**O que dá errado:** `0.10 + 0.20 == 0.30000000000000004` no Python/IEEE 754.
**Por que acontece:** Representação binária de ponto flutuante não representa decimais exatos.
**Como evitar:** `Decimal` em todo campo monetário. Ao parsear CSV: `Decimal(str(cell_value))`, nunca `float(cell_value)`.
**Sinais de alerta:** `isinstance(amount, float)` no código de parsing.

### Pitfall 2: `type` ainda presente no ORM após regeneração
**O que dá errado:** `models.py` regenerado reflete o YAML, mas se o YAML não foi editado antes de gerar, `type` permanece no ORM.
**Por que acontece:** A geração sobrescreve `models.py` com base no YAML — se o YAML não foi atualizado, o modelo antigo persiste.
**Como evitar:** Editar `dsl/entities/movement.yaml` ANTES de rodar `bin/generate_code`. Verificar que `type` e `is_duplicate` sumiram do `models.py` gerado.
**Sinais de alerta:** `Movement.type` ainda importável após regeneração.

### Pitfall 3: `down_revision` errado na migration 0003
**O que dá errado:** Alembic não consegue construir o grafo de migrations; `alembic upgrade head` falha.
**Por que acontece:** `down_revision` deve apontar para `"0002"` (a última migration existente).
**Como evitar:** Verificar com `uv run alembic history --verbose` após gerar — confirmar que 0003 aponta para 0002.
**Sinais de alerta:** `alembic history` mostra branch ou `down_revision: None` inesperado.

### Pitfall 4: `import_hash` UNIQUE violation ao inserir confirmadas
**O que dá errado:** `POST /import/confirm` tenta inserir com o mesmo hash do registro original → `UniqueViolation`.
**Por que acontece:** O hash da movimentação confirmada é igual ao existente no banco.
**Como evitar:** Inserir movimentações confirmadas com `import_hash=None`. PostgreSQL permite múltiplos NULLs em coluna UNIQUE (verificado).
**Sinais de alerta:** `asyncpg.UniqueViolationError` no endpoint de confirmação.

### Pitfall 5: openpyxl sem `wb.close()` em `read_only=True`
**O que dá errado:** File handles abertos não são liberados; em ambiente de alta carga, processo esgota file descriptors.
**Por que acontece:** `read_only=True` usa lazy loading via file handle; não fecha automaticamente.
**Como evitar:** Sempre `wb.close()` após iterar as rows, inclusive em caminhos de erro (`try/finally`).
**Sinais de alerta:** `ResourceWarning: unclosed file` nos logs de teste.

### Pitfall 6: encoding OFX de bancos brasileiros
**O que dá errado:** `UnicodeDecodeError` ao parsear OFX com `CHARSET:1252` ou `ENCODING:USASCII` que na prática usa ISO-8859-1.
**Por que acontece:** Bancos BR frequentemente geram OFX com acentos em ISO-8859-1 mesmo declarando outro encoding.
**Como evitar:** Wrap o `OfxParser.parse()` em `try/except`; no fallback, decodificar explicitamente com `content.decode("iso-8859-1", errors="replace")` e passar `io.StringIO`. `ofxparse` cuida internamente na maioria dos casos (verificado na doc), mas o fallback é necessário para bancos que violam o padrão.
**Sinais de alerta:** `UnicodeDecodeError` ou `OfxParserException` no endpoint OFX.

### Pitfall 7: `csv.Sniffer` falhando em arquivo pequeno ou single-column
**O que dá errado:** `csv.Sniffer().sniff(sample)` levanta `csv.Error: Could not determine delimiter` para arquivos com apenas uma coluna ou poucos caracteres.
**Por que acontece:** Sniffer precisa de variação suficiente no sample para detectar o delimitador.
**Como evitar:** Envolver em `try/except csv.Error`; fallback para vírgula (`,`) quando Sniffer falha.
**Sinais de alerta:** `csv.Error: Could not determine delimiter`.

### Pitfall 8: `session.exec()` vs `session.execute()` para queries com `.in_()`
**O que dá errado:** `session.exec(select(Movement.import_hash).where(...in_(...)))` pode retornar objetos ORM completos em vez de scalars, ou falhar com projeções parciais.
**Por que acontece:** `session.exec()` é o wrapper do SQLModel; `session.execute()` é o SQLAlchemy puro — para queries com `func.`, projeções e `IN`, usar `session.execute()`.
**Como evitar:** Pre-check de hashes usa `session.execute()` conforme padrão do projeto (STATE.md § Decisions).

---

## Code Examples

### Hash computation (D-07)

```python
# Source: verificado com hashlib no projeto
import hashlib, re
from decimal import Decimal
from datetime import datetime

def _normalize_description(desc: str) -> str:
    return re.sub(r'\s+', ' ', desc.strip().lower())

def _compute_hash(account_id: int, date: datetime, amount: Decimal, description: str) -> str:
    norm_desc = _normalize_description(description)
    raw = f"{account_id}|{date.date().isoformat()}|{amount}|{norm_desc}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

### Date parsing com fallback BR (D-12)

```python
# Source: verificado com datetime.strptime no projeto
from datetime import datetime, timezone

def _parse_date(value: str, line: int) -> datetime:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Linha {line}: data inválida {value!r}")
```

### Pre-check em lote (Padrão 5)

```python
# Source: padrão session.execute() + .in_() — conforme STATE.md decisions
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

async def _existing_hashes(session: AsyncSession, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    result = await session.execute(
        select(Movement.import_hash).where(Movement.import_hash.in_(hashes))
    )
    return {row[0] for row in result.fetchall()}
```

---

## State of the Art

| Abordagem antiga | Abordagem atual | Quando mudou | Impacto |
|-----------------|-----------------|-------------|---------|
| `is_duplicate=True` para marcar duplicatas no banco | `potential_duplicates[]` na resposta para confirmação pelo usuário | Phase 8 (redesign no CONTEXT.md) | Nunca persiste duplicata silenciosamente; UX de revisão explícita |
| Campo `type: str` (credito/debito) separado do `amount` | `amount` com sinal (positivo=crédito, negativo=débito) | Phase 8 (D-01) | `SUM(amount)` para saldo sem `CASE WHEN`; hash sem `type` é suficiente |
| `on_conflict_do_nothing` como mecanismo primário de dedup | Pre-check via `SELECT import_hash IN (...)` + `on_conflict_do_nothing` como safety net | Phase 8 (D-04/D-05) | Permite distinguir OFX (dedup definitiva) de CSV/XLSX (dedup suspeita) |

**Deprecated nesta fase:**
- Campo `movement.type` (str): removido do DSL e via migration 0003.
- Campo `movement.is_duplicate` (bool): removido do DSL e via migration 0003.

---

## Assumptions Log

| # | Claim | Seção | Risco se errado |
|---|-------|-------|-----------------|
| A1 | `ofxparse` versão 0.21 — ~22k downloads/semana | Package Legitimacy Audit | Baixo: PyPI confirma existência; metadados de download são aproximados |
| A2 | `openpyxl` versão 3.1.5 — ~22M downloads/semana | Package Legitimacy Audit | Baixo: PyPI confirma existência; é a lib de fato para Excel em Python |
| A3 | Encoding OFX: `ofxparse` cuida da maioria dos casos; fallback ISO-8859-1 necessário para alguns bancos BR | Common Pitfalls §6 | Médio: validar com extrato real de banco BR conforme pendente no STATE.md |
| A4 | PostgreSQL permite múltiplos NULLs em coluna UNIQUE (`import_hash`) | Padrão 7 / Pitfall 4 | Baixo: comportamento padrão SQL e PostgreSQL verificado com raciocínio sobre spec |

---

## Open Questions

1. **Encoding OFX com extrato real de banco BR**
   - O que sabemos: `ofxparse` lida com a maioria dos encodings; fallback ISO-8859-1 previsto.
   - O que está incerto: qual banco BR específico e se ele viola o padrão de header `ENCODING:`.
   - Recomendação: implementar o fallback e testar na task de validação com arquivo real (STATE.md §Pending Todos).

2. **`import_hash` para movimentações confirmadas**
   - O que sabemos: `import_hash=None` é a solução (PostgreSQL permite múltiplos NULLs em UNIQUE).
   - O que está incerto: o frontend pode querer identificar qual `hash` foi confirmado para auditoria.
   - Recomendação: inserir com `import_hash=None` conforme D-08; se rastreabilidade for necessária, adicionar campo separado `confirmed_from_hash` na Phase 9.

3. **`Decimal` serializado como string ou número no JSON**
   - O que sabemos: STATE.md §Pending Todos menciona "Definir convenção Decimal no JSON (string vs float)".
   - O que está incerto: Pydantic por padrão serializa `Decimal` como string em JSON v2.
   - Recomendação: manter padrão Pydantic (string) e documentar na `MovementReadPublic`. Confirmar no Wave 0 de testes.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Todo o código | ✓ | 3.12.3 | — |
| PostgreSQL | Banco de dados | ✓ (dev) | caramello_dev | — |
| `ofxparse` | Parser OFX | ✗ | — | Adicionar ao pyproject.toml: `uv add ofxparse>=0.21` |
| `openpyxl` | Parser XLSX | ✗ | — | Adicionar ao pyproject.toml: `uv add openpyxl>=3.1.5` |
| `python-multipart` | UploadFile (FastAPI) | ✓ | 0.0.29 (uv.lock) | — |
| `asyncpg` | SQLAlchemy async | ✓ | >=0.31.0 | — |

**Dependências faltantes com fallback (instalação necessária):**
- `ofxparse>=0.21` — sem esta lib, importação OFX não funciona.
- `openpyxl>=3.1.5` — sem esta lib, importação XLSX não funciona.

**Dependências faltantes sem fallback:**
- Nenhuma que bloqueie implementação do núcleo (CSV e MOV-01 funcionam sem as libs novas).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.1 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `uv run python -m pytest tests/test_finances_operations.py -v` |
| Full suite command | `uv run python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Comportamento | Tipo de teste | Comando automatizado | Arquivo existe? |
|--------|--------------|--------------|---------------------|-----------------|
| MOV-01 | POST /accounts/{uuid}/movements cria movimentação individual; retorna UUID | unit (mock session) | `uv run python -m pytest tests/test_finances_operations.py::test_create_movement -x` | ❌ Wave 0 |
| MOV-01 | 409 se hash de movimentação já existe | unit (mock session) | `uv run python -m pytest tests/test_finances_operations.py::test_create_movement_409_duplicate -x` | ❌ Wave 0 |
| MOV-02 | POST /import?format=csv retorna contagem inserted + movements[] | unit (mock session + BytesIO) | `uv run python -m pytest tests/test_finances_operations.py::test_import_csv -x` | ❌ Wave 0 |
| MOV-03 | POST /import?format=ofx retorna resultado correto | unit (mock session + OFX sample) | `uv run python -m pytest tests/test_finances_operations.py::test_import_ofx -x` | ❌ Wave 0 |
| MOV-03 | POST /import?format=xlsx retorna resultado correto | unit (mock session + XLSX BytesIO) | `uv run python -m pytest tests/test_finances_operations.py::test_import_xlsx -x` | ❌ Wave 0 |
| MOV-04 | Reimportar mesmo arquivo não duplica | unit (mock hash pre-check) | `uv run python -m pytest tests/test_finances_operations.py::test_import_deduplication -x` | ❌ Wave 0 |
| MOV-05 | potential_duplicates[] retornados para CSV com hash match | unit (mock session) | `uv run python -m pytest tests/test_finances_operations.py::test_import_potential_duplicates -x` | ❌ Wave 0 |
| MOV-05 | POST /import/confirm insere confirmadas sem hash collision | unit (mock session) | `uv run python -m pytest tests/test_finances_operations.py::test_import_confirm -x` | ❌ Wave 0 |
| D-15 | GET /accounts/{uuid}/movements retorna lista paginada | unit (mock session) | `uv run python -m pytest tests/test_finances_operations.py::test_list_movements -x` | ❌ Wave 0 |
| AUTH-FIN-01/02 | 401 sem token, 403 para família alheia em endpoints de Movement | unit (já coberto para accounts — replicar) | `uv run python -m pytest tests/test_finances_operations.py::test_movements_require_auth -x` | ❌ Wave 0 |
| MOV-02 | Parser de services.py: _parse_csv detecta separador ; e , | unit puro (sem mock session) | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv -x` | ❌ Wave 0 |
| MOV-02 | _parse_csv: linhas inválidas vão para error_lines[] sem abortar | unit puro | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv_error_lines -x` | ❌ Wave 0 |
| MOV-02 | _parse_csv: >50% de erros aborta com ValueError | unit puro | `uv run python -m pytest tests/test_services/test_finances_service.py::test_parse_csv_abort_threshold -x` | ❌ Wave 0 |

### Sampling Rate

- **Por task commit:** `uv run python -m pytest tests/test_finances_operations.py tests/test_services/test_finances_service.py -v`
- **Por wave merge:** `uv run python -m pytest tests/ -v`
- **Phase gate:** Suite completa verde antes de `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_finances_operations.py` — estender com testes de Movement (MOV-01..05, D-15)
- [ ] `tests/test_services/test_finances_service.py` — novo arquivo; cobre parsers sem mock session
- [ ] Instalar `ofxparse` e `openpyxl` antes dos testes de MOV-03

*(Os testes existentes de Account/Category/Subcategory — 11 passing — não são afetados.)*

---

## Security Domain

### ASVS Categories Aplicáveis

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | sim | `Depends(get_current_user)` em todos os endpoints — já implementado |
| V3 Session Management | não | Sem sessão de usuário; autenticação stateless via JWT |
| V4 Access Control | sim | `_require_family_access` — reutilizado de Phase 7 |
| V5 Input Validation | sim | Pydantic schemas + validação manual nos parsers (date, amount) |
| V6 Cryptography | não aplicável | SHA-256 para hash de dedup — não é criptografia de segredo |

### Known Threat Patterns

| Padrão | STRIDE | Mitigação padrão |
|--------|--------|-----------------|
| Upload de arquivo malicioso (zip bomb, XML bomb no XLSX) | Tampering | `openpyxl read_only=True` limita exposição; adicionar limite de tamanho (`file.size`) |
| IDOR via `account_uuid` de outra família | Elevation of Privilege | `_require_family_access(account.family_id)` resolve — mesmo padrão de Phase 7 |
| Injeção via `description` no CSV | Tampering | `Decimal(str(amount))` para valores; `description` é str salvo sem exec; sem ORM raw SQL |
| Flooding por importação (DoS) | Denial of Service | Limiar de 50% de erros aborta lote; considerar limit de linhas por arquivo (planner decide) |

---

## Sources

### Primary (HIGH confidence)
- `src/caramello/finances/operations.py` — padrões de código vigentes (schemas públicos, session.exec, _require_family_access)
- `src/caramello/shared/auth.py` linhas 193-198 — padrão pg_insert + on_conflict_do_nothing já em uso no projeto
- `alembic/versions/0002_finances_schema.py` — schema atual, colunas a remover na 0003
- `dsl/entities/movement.yaml` — campos atuais a editar (type, is_duplicate)
- Python stdlib: `hashlib`, `csv`, `csv.Sniffer`, `decimal.Decimal`, `io` — verificados via `uv run python`
- `pyproject.toml` + `uv.lock` — dependências instaladas verificadas

### Secondary (MEDIUM confidence)
- [ofxparse GitHub (jseutter/ofxparse)](https://github.com/jseutter/ofxparse/blob/master/ofxparse/ofxparse.py) — API de `transaction.id`, `transaction.amount`, handling de encoding
- [openpyxl docs — Optimised Modes](https://openpyxl.readthedocs.io/en/stable/optimized.html) — `read_only=True`, `wb.close()` obrigatório
- [FastAPI docs UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/) — `await file.read()` retorna bytes

### Tertiary (LOW confidence)
- Snyk Advisor para estatísticas de downloads de `ofxparse` (~22k/semana, maintenance inactive)
- WebSearch sobre encoding OFX + bancos BR — múltiplas fontes concordam com problema, solução via fallback ISO-8859-1

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verificado no projeto (instalados/uv.lock) + pip index para versões novas
- Architecture: HIGH — derivado diretamente dos padrões de operations.py existente
- Pitfalls: HIGH (P1-P5) / MEDIUM (P6 encoding OFX) — P1-P5 verificados via código; P6 baseado em docs + websearch
- Migration: HIGH — 0002 lida, campos a remover identificados, down_revision confirmado como "0002"

**Research date:** 2026-06-02
**Valid until:** 2026-08-01 (stack estável; só muda se FastAPI/SQLModel tiver breaking change)
