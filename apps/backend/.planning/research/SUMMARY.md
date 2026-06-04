# Research Summary — M2: Domínio Financeiro

**Projeto:** caramello-api (Grupo Família backend)
**Pesquisado:** 2026-05-30
**Confiança geral:** HIGH

---

## Executive Summary

O M2 adiciona um domínio financeiro completo sobre a fundação FastAPI async do v1.0. O padrão recomendado pela indústria (GnuCash, hledger, YNAB) é a separação em duas camadas: `Movimentação` (fato bancário bruto, imutável) e `Lançamento` (interpretação classificada, recategorizável). Quatro libs novas são suficientes — `ofxparse`, `openpyxl`, `python-multipart` e `rapidfuzz`. Toda lógica de deduplicação usa SHA-256 da stdlib; toda agregação usa `func.sum` do SQLAlchemy 2.0 já instalado.

Os riscos principais são preveníveis: (1) `float` para valores monetários acumula erro — obrigatório `NUMERIC(15,2)` + `Decimal`; (2) Category self-referencial exige `remote_side` + `foreign_keys` explícitos; (3) lazy loading async causa `MissingGreenlet` na serialização; (4) batch insert sem `ON CONFLICT DO NOTHING` aborta o lote inteiro na primeira duplicata.

---

## Stack Additions

| Biblioteca | Versão | Propósito |
|------------|--------|-----------|
| `ofxparse` | 0.21 | Parser OFX/QFX bancário |
| `openpyxl` | 3.1.5 | Leitura XLSX com `read_only=True` |
| `python-multipart` | 0.0.29 | Upload multipart (provavelmente já instalado) |
| `rapidfuzz` | 3.14.5 | `token_set_ratio` para sugestão de categoria |

**O que NÃO adicionar:** pandas, aiofiles, scikit-learn, xlrd, fuzzywuzzy.

---

## Feature Table Stakes vs Differentiators

### Table Stakes (M2 obrigatório)
- CRUD de Conta por família
- Registro manual de Movimentação
- Categorias 2 níveis por família
- Criação de Lançamento com categoria + competência
- Saldo por conta (derivado de movimentações)
- Importação em lote CSV com deduplicação
- Breakdown mensal por categoria pai e subcategoria
- Competência (ano/mês) como campo independente da data

### Differentiators (incluir no M2)
- Saldo consolidado familiar
- Sugestão semi-automática de categoria (rapidfuzz + ILIKE)
- Importação OFX/XLSX

### Definitivamente fora do M2
Budget/forecast, ciclos de fatura automáticos, splits de movimentação, notificações, ML/embeddings.

---

## Architecture Decisions

### Modelo de domínio

```
Account      id, uuid, family_id (FK→family), name, type, currency, is_active
Movement     id, uuid, account_id (FK→account), type (credit/debit), date,
             amount (NUMERIC 15,2), description, is_duplicate,
             import_hash (UNIQUE, SHA-256), import_batch_id
Entry        id, uuid, movement_id (FK→movement, UNIQUE), category_id (nullable),
             competencia_year, competencia_month, notes, is_recurring
Category     id, uuid, family_id (FK→family), name,
             parent_id (FK→category, nullable — nível 2 aponta para nível 1)
```

### Padrões chave

- **Self-referential Category:** `sa_relationship_kwargs={"remote_side": "Category.id", "foreign_keys": "[Category.parent_id]"}` em ambos os lados. O gerador DSL não suporta isso — `models.py` de Category pós-processado manualmente e marcado `# CARAMELLO-GENERATED: implemented`.
- **1:1 Movement→Entry:** `unique=True` na FK `movement_id` + `uselist=False` no ORM. Constraint no banco, não só no ORM.
- **Precisão monetária:** `Column(Numeric(15, 2))` + `Decimal`. asyncpg decodifica NUMERIC como Decimal nativamente. Nenhum `float` em campo monetário.
- **Competência:** `competencia_year: int | None` + `competencia_month: int | None`. Sem inferência automática.
- **Deduplicação:** SHA-256 de `(conta_id|date|amount|descricao_normalizada)` como `import_hash UNIQUE`. `pg_insert(...).on_conflict_do_nothing()`.
- **Agregações:** `session.execute()` (não `session.exec()`) com `func.sum + group_by`. Índices em `movement.account_id`, `entry.competencia_year`, `entry.competencia_month`, `entry.category_id`, `account.family_id`.
- **Autorização:** helper `_require_account_access()` via JOIN `Account → Family → FamilyMember`.
- **Import circular:** `finances/` importa de `families/` e `users/`. Nenhum dos dois importa de `finances/`.
- **Ordem em main.py:** todos os routers de finances ANTES de `FastApiMCP(...)`.

---

## Critical Pitfalls

| # | Pitfall | Prevenção |
|---|---------|-----------|
| P1 | `float` para valores monetários | `Column(Numeric(15, 2))` + `Decimal` desde a modelagem |
| P2 | Category self-referencial sem `remote_side`/`foreign_keys` | `sa_relationship_kwargs` explícito em ambos os lados |
| P3 | Lazy loading async → `MissingGreenlet` na serialização | `selectinload` explícito nas queries que serializam relacionamentos |
| P4 | Batch insert sem `ON CONFLICT` → aborta lote inteiro | `pg_insert(...).on_conflict_do_nothing(index_elements=["import_hash"])` |
| P5 | 1:1 enforçado só no ORM — banco aceita múltiplos Entry | `UniqueConstraint("movement_id")` na migration |
| P6 | `down_revision` incorreto bifurca o grafo Alembic | Verificar manualmente + `alembic history --verbose` após gerar |
| P7 | Router financeiro após `FastApiMCP(...)` — tools não aparecem | Registrar todos routers finances ANTES de `mcp = FastApiMCP(...)` |

---

## Recommended Build Order

### Fase 6: Fundação DSL + Schema
Naming convention em env.py → 4 YAMLs DSL → gerar models.py + router.py → pós-processar Category (self-referencial) → migration 0002.
**Pitfalls:** P2, P5, P6

### Fase 7: CRUD Account + Category
`finances/operations.py` com CRUD de Account e Category + `_require_account_access()` + validação max 2 níveis.
**Pitfalls:** P3, P7

### Fase 8: Movimentações + Importação
`finances/services.py` com `import_movements()` + `ON CONFLICT DO NOTHING`. Endpoints individual + lote (CSV/OFX/XLSX).
**Pitfalls:** P1, P4

### Fase 9: Conciliação + Relatórios + MCP
`PATCH .../reconcile`, `suggest_category()` (rapidfuzz), `monthly_breakdown()`, `account_balance()`, `family_balance()`. Expor via MCP.
**Pitfalls:** P1 (serialização Decimal), P3

---

## Gaps a Resolver Durante Implementação

- Encoding OFX de bancos BR: testar com extrato real antes de finalizar Fase 8; fallback `ofxparse2`
- Convenção Decimal no JSON: string ou float — definir na Fase 6 e documentar no schema
- Score threshold rapidfuzz: ajustar empiricamente após dados reais

---
*Research completed: 2026-05-30*
