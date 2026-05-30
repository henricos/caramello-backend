# Technology Stack — caramello-api M2 (Domínio Financeiro)

**Projeto:** caramello-api (Grupo Família backend)
**Pesquisado:** 2026-05-30
**Confiança geral:** HIGH (versões verificadas no PyPI; padrões verificados via Context7 e fontes oficiais)

---

> **Nota:** Este documento cobre apenas as _adições_ necessárias para o Milestone 2.
> O stack base (FastAPI async + SQLModel + asyncpg + Alembic + PyJWT + fastapi-mcp) está implementado e validado — não é reexaminado aqui.

---

## Adições necessárias

### 1. Parsing de arquivos bancários

| Biblioteca | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| `ofxparse` | 0.21 | Parser OFX/QFX | Biblioteca mais usada para OFX; API simples: `OfxParser.parse(fileobj)` retorna objeto com `account.statement.transactions`; versão 0.21 de 2021 — projeto tem PRs em 2024-2025 mas baixa atividade geral |
| `openpyxl` | 3.1.5 | Leitura de XLSX | Alta reputação (Context7); `read_only=True` para memória constante; sem dependências pesadas; suporta Python 3.10+ |
| `python-multipart` | 0.0.29 | Upload multipart/form-data | **Já é dependência indireta do FastAPI** para UploadFile — provavelmente já instalado; adicionar explicitamente ao `pyproject.toml` para clareza |

**Nota sobre OFX:** Bancos brasileiros exportam arquivos `.ofx` com encodings variados e headers não-padrão. A alternativa `ofxparse2` (fork por @pedrin-pedrada, 0.2.2) trata especificamente esses casos. Para uso inicial com CSV e XLSX o problema não se aplica. Se OFX de bancos BR se mostrar problemático, trocar para `ofxparse2`. Por ora: usar `ofxparse` 0.21 como primeira escolha.

**O que NÃO adicionar:**
- `pandas` — dependência de 30+ MB para um parser de CSV. Para família de 1-5 usuários, o módulo `csv` da stdlib é suficiente. Pandas faz sentido só se houvesse análise estatística.
- `xlrd` — para `.xls` (formato antigo pre-2007). Bancos modernos exportam `.xlsx`. Ignorar.
- `aiofiles` — OFX/CSV/XLSX de extratos bancários são tipicamente < 1 MB. `await file.read()` via UploadFile (que já usa SpooledTemporaryFile) é suficiente sem streaming chunked.

---

### 2. Deduplicação de movimentações

**Biblioteca necessária:** nenhuma nova. A stdlib do Python é suficiente.

**Estratégia recomendada — hash de impressão digital (fingerprint):**

```python
import hashlib

def compute_movement_hash(date: str, amount: str, description: str, account_id: int) -> str:
    """Fingerprint determinístico para deduplicação de movimentações importadas."""
    raw = f"{account_id}|{date}|{amount}|{description.strip().upper()}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

- O campo `import_hash` (VARCHAR(64), UNIQUE por conta) é adicionado ao modelo `Movimentacao`.
- Na importação em lote: calcular hash para cada linha → inserir com `INSERT ... ON CONFLICT (import_hash) DO NOTHING` via SQLAlchemy.
- Arquivos OFX já fornecem `FITID` (Financial Institution Transaction ID) único por banco — usar como hash direto quando disponível, mais confiável que campo derivado.

**Por que não fuzzy matching para deduplicação:**
Fuzzy matching é útil para _sugestão de categoria_, não para deduplicação de importação. Para deduplicação, o critério deve ser determinístico (mesmo arquivo importado duas vezes = zero duplicatas). Hash é O(1) por transação e correto.

---

### 3. Sugestão de categoria (semi-automática)

| Biblioteca | Versão | Propósito | Por quê |
|------------|--------|-----------|---------|
| `rapidfuzz` | 3.14.5 | Similaridade de strings para sugestão de categoria | Implementado em C++, mas API Python pura; `process.extractOne()` retorna a melhor correspondência com score; sem dependência de modelo ML; MIT license; alta atividade no PyPI |

**Padrão de uso:**

```python
from rapidfuzz import process, fuzz

def suggest_category(description: str, known_entries: list[tuple[str, int]]) -> int | None:
    """
    known_entries: lista de (description_normalizada, categoria_id) de lancamentos anteriores
    Retorna categoria_id se score >= threshold, None caso contrário.
    """
    if not known_entries:
        return None
    choices = {desc: cat_id for desc, cat_id in known_entries}
    result = process.extractOne(
        description.upper(),
        choices.keys(),
        scorer=fuzz.token_set_ratio,  # ignora ordem de palavras; bom para descrições de extrato
        score_cutoff=75,              # limiar: ajustável, 75 funciona bem para descrições bancárias
    )
    if result:
        _, _score, matched_desc = result
        return choices[matched_desc]
    return None
```

**Por que `token_set_ratio` e não `ratio` simples:**
Descrições de extrato têm tokens na ordem variável (ex: "PIX RECEBIDO JOAO SILVA" vs "JOAO SILVA PIX"). `token_set_ratio` trata o conjunto de tokens como bag-of-words, ignorando ordem e duplicatas — muito mais preciso para esse caso de uso.

**Escala:** Para 1-5 usuários com centenas de lançamentos históricos, a comparação linear contra todos os lançamentos anteriores é negligenciável em performance. Sem necessidade de indexação vetorial.

**O que NÃO adicionar:**
- `scikit-learn` / `sentence-transformers` / qualquer modelo ML — totalmente desnecessário para app familiar. RapidFuzz entrega 80% do valor com 0% da complexidade operacional.
- `fuzzywuzzy` — versão antiga de RapidFuzz, mais lenta, usa `python-Levenshtein` como dependência opcional.

---

### 4. Agregações financeiras

**Biblioteca necessária:** nenhuma nova. SQLAlchemy 2.0 (já em uso) tem suporte completo a `func.sum`, `func.extract`, `group_by` com AsyncSession.

**Padrão recomendado — SQLAlchemy ORM expressions (não SQL raw):**

```python
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

async def monthly_breakdown(session: AsyncSession, family_id: int, year: int, month: int):
    stmt = (
        select(
            Categoria.nome.label("categoria"),
            func.sum(Lancamento.valor).label("total"),
        )
        .join(Lancamento, Lancamento.categoria_id == Categoria.id)
        .where(
            Lancamento.competencia_ano == year,
            Lancamento.competencia_mes == month,
            Categoria.family_id == family_id,
        )
        .group_by(Categoria.id, Categoria.nome)
        .order_by(func.sum(Lancamento.valor).desc())
    )
    result = await session.execute(stmt)
    return result.mappings().all()
```

**Por que ORM expressions e não SQL raw:**
- Reutiliza o async engine já configurado sem abrir conexões separadas.
- Verificação de tipos em tempo de desenvolvimento com mypy.
- Portabilidade caso o banco mude (improvável, mas boa prática).
- Para queries mais complexas (ex: breakdown hierárquico pai/filho), SQL raw via `text()` é aceitável — sem dogma.

**Saldo derivado por conta:**
```python
async def account_balance(session: AsyncSession, account_id: int) -> Decimal:
    stmt = select(func.sum(Movimentacao.valor)).where(
        Movimentacao.conta_id == account_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() or Decimal(0)
```

Créditos são valores positivos, débitos são negativos — convenção a definir no modelo e manter consistente.

---

### 5. Campo `competencia` (período contábil)

**Biblioteca necessária:** nenhuma nova. Padrão de modelagem com dois campos inteiros no banco.

**Por que dois campos inteiros e não um campo `date`:**
- `competencia_ano: int` + `competencia_mes: int` é explícito e sem ambiguidade — não há "dia" em competência.
- Filtragem por período usa `WHERE competencia_ano = 2025 AND competencia_mes = 11` — índice composto em (ano, mes) é trivial.
- Evita o problema de normalizar para `date(2025, 11, 1)` (primeiro do mês? último?) que causa bugs sutis.
- `GROUP BY competencia_ano, competencia_mes ORDER BY competencia_ano, competencia_mes` é legível.

**Índice recomendado no modelo:**
```python
class Lancamento(SQLModel, table=True):
    competencia_ano: int = Field(index=False)   # índice composto abaixo
    competencia_mes: int = Field(index=False)
    ...

# Em alembic migration ou via __table_args__:
# Index("ix_lancamento_competencia", "competencia_ano", "competencia_mes")
```

---

### 6. Endpoint de importação em lote

**Biblioteca necessária:** `python-multipart` 0.0.29 (provavelmente já resolvido pelo FastAPI).

**Padrão recomendado:**

```python
from fastapi import APIRouter, UploadFile, File, Depends
from typing import Annotated

@router.post("/movimentacoes/import")
async def import_movimentacoes(
    conta_id: int,
    file: Annotated[UploadFile, File(description="CSV, OFX ou XLSX")],
    session: SessionDep,
    current_user: CurrentUser,
) -> ImportResult:
    content = await file.read()          # sync-seguro: SpooledTemporaryFile já lido em memória
    filename = file.filename or ""

    if filename.endswith(".ofx") or filename.endswith(".qfx"):
        rows = parse_ofx(content)
    elif filename.endswith(".xlsx"):
        rows = parse_xlsx(content)
    elif filename.endswith(".csv"):
        rows = parse_csv(content)
    else:
        raise HTTPException(status_code=422, detail="Formato não suportado")

    inserted, skipped = await bulk_insert_with_dedup(session, conta_id, rows)
    return ImportResult(inserted=inserted, skipped=skipped)
```

**Decisão síncrona vs. background:** Para arquivos de extrato bancário (tipicamente < 500 linhas, < 200KB), processamento síncrono no endpoint é adequado. Background tasks (via `BackgroundTasks` do FastAPI) adicionam complexidade de estado sem benefício mensurável para este volume. Usar background só se o tempo de resposta for visivelmente lento no uso real.

**Tamanho máximo de upload:** Configurar via `MAX_UPLOAD_SIZE` no uvicorn/nginx se necessário. Para extratos mensais não há necessidade de streaming chunked.

---

## Resumo das instalações

```bash
# Parsing de arquivos bancários
uv add "ofxparse>=0.21" "openpyxl>=3.1.5" "python-multipart>=0.0.29"

# Sugestão de categoria
uv add "rapidfuzz>=3.14.5"

# Sem instalações adicionais para:
# - Deduplicação (hashlib stdlib)
# - Agregações (SQLAlchemy já instalado)
# - Competencia (campos inteiros, sem lib)
```

---

## Alternativas descartadas

| Categoria | Recomendado | Alternativa | Por que não |
|-----------|-------------|-------------|-------------|
| CSV parsing | `csv` (stdlib) | `pandas` | pandas adiciona 30MB de dependência; desnecessário para < 1000 linhas |
| OFX parser | `ofxparse` 0.21 | `ofxtools` 0.9.5 | ofxtools é mais completo (suporta OFX 2.x/XML) mas mais complexo; para extratos simples (OFX 1.x SGML), ofxparse é suficiente |
| OFX BR | `ofxparse` | `ofxparse2` | ofxparse2 é fork específico para bancos BR; trocar se ofxparse falhar em encodings BR reais |
| Similaridade | `rapidfuzz` | `scikit-learn` TF-IDF | Totalmente desproporcional para app familiar; rapidfuzz entrega resultado comparável sem infra de ML |
| Similaridade | `rapidfuzz` | `fuzzywuzzy` | fuzzywuzzy é antecessor abandonado de rapidfuzz; não usar |
| Aggregation | SQLAlchemy ORM | raw SQL via `text()` | ORM expressions para casos simples; raw SQL aceitável se a query ficar ilegível com ORM |
| Deduplicação | hash SHA-256 | fuzzy dedup | Fuzzy dedup introduz falsos positivos/negativos; hash é determinístico e correto para importação |
| Competência | 2 campos inteiros | campo `date` | campo date cria ambiguidade de dia; inteiros são explícitos e indexáveis |
| Upload async | sync `await file.read()` | `aiofiles` streaming | extratos < 200KB não justificam streaming; UploadFile já abstrai SpooledTemporaryFile |

---

## Compatibilidade verificada

| Par | Status | Observação |
|-----|--------|------------|
| `ofxparse` 0.21 + Python 3.12 | OK | Puro Python, sem extensões C |
| `openpyxl` 3.1.5 + Python 3.12 | OK | Verificado no PyPI |
| `rapidfuzz` 3.14.5 + Python 3.12 | OK | Wheels pré-compilados para Python 3.12 disponíveis no PyPI |
| `python-multipart` 0.0.29 + FastAPI | OK | Dependência oficial do FastAPI para UploadFile |
| `rapidfuzz` + asyncio | OK | Chamadas síncronas de CPU-bound; para volumes de app familiar (< 1000 entradas históricas), sem necessidade de `run_in_executor` |

---

## Fontes

- ofxparse PyPI: https://pypi.org/project/ofxparse/ (versão 0.21, MEDIUM — projeto de baixa atividade mas funcional)
- ofxparse2 PyPI: https://pypi.org/project/ofxparse2/ (fallback para bancos BR, LOW confidence — fork pequeno)
- openpyxl docs: https://openpyxl.readthedocs.io/en/stable/optimized.html (HIGH — documentação oficial, Context7)
- rapidfuzz docs: https://rapidfuzz.github.io/RapidFuzz/Usage/process.html (HIGH — Context7)
- FastAPI UploadFile: https://fastapi.tiangolo.com/tutorial/request-files/ (HIGH — documentação oficial)
- SQLAlchemy 2.0 async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html (HIGH — documentação oficial)
- SQLAlchemy func/group_by: https://docs.sqlalchemy.org/en/20/core/functions.html (HIGH — documentação oficial)
- python-multipart PyPI: https://pypi.org/project/python-multipart/ (HIGH — dependência oficial FastAPI)
- rapidfuzz PyPI: https://pypi.org/project/rapidfuzz/ (HIGH — versão 3.14.5 verificada)
