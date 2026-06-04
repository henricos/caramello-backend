# Feature Landscape — M2: Domínio Financeiro

**Domain:** Personal family financial tracking — closed group, 1-5 users
**Researched:** 2026-05-30
**Confidence:** HIGH (table stakes / two-layer model / deduplication), MEDIUM (categorization specifics)

---

## Context

This is a **subsequent milestone** on an existing backend. Authentication (Keycloak), family groups,
and user provisioning already exist in v1.0. M2 adds a financial tracking domain. The audience is a
single household, not a SaaS product. All complexity decisions are biased toward simplicity.

---

## Table Stakes

Features that must exist for the domain to be usable. Missing any of these makes the product
functionally incomplete.

| Feature | Why Expected | Complexity | Dependency |
|---------|--------------|------------|------------|
| CRUD de contas (bank/card/savings) | Without accounts there is nowhere to attach movements | Low | Family (existing) |
| Registro manual de movimentação | Core data entry; without it nothing works | Low | Conta |
| Categorias 2 níveis por família | Without categories there is no analysis; 2 levels is the minimum for useful reporting | Low | Family (existing) |
| Criação de lançamento a partir de movimentação | The 2-layer model (raw → classified) is the correct separation; merging them creates rigid coupling and prevents re-categorization without losing raw data | Medium | Movimentação + Categoria |
| Saldo por conta (derivado de movimentações) | Any financial app must show current balance | Low | Movimentações |
| Importação em lote (CSV) com deduplicação | Re-importing the same file must not create duplicates | Medium | Conta |
| Breakdown mensal por categoria | Core utility: "how much did I spend on X in March?" | Medium | Lançamentos + competência |
| Competência (ano/mês) no lançamento | Enables analysis by accounting period rather than debit date | Low (single field) | Lançamento |

---

## Differentiators

Features that go beyond baseline but add real value for this specific use case (family, small group).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Sugestão semi-automática de categoria | Reduces friction at reconciliation — system suggests, user confirms | Medium | See detailed section below |
| Saldo consolidado familiar | Single view across all accounts of all family members | Low | Aggregate query only |
| Importação OFX/OFXSGML | Native format of Brazilian banks; more reliable than free-text CSV | Medium | OFX parsing is well-defined |
| Regras de categorização persistentes (keyword → category) | User defines "Posto Ipiranga → Transporte > Gasolina" once; applies on future imports | Medium | Persisted in DB, applied at lançamento creation |
| Competência independente da data da movimentação | Credit card purchase on Jan 28th appears in Feb statement — user can assign Feb competência without altering original date | Low (optional field) | `competencia_ano` + `competencia_mes` nullable fields on lançamento |

---

## Anti-Features

Features that seem useful but are unnecessary scope for 1-5 users or require disproportionate
infrastructure.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Orçamento/budget por categoria | Increases data complexity (goals vs actuals) before the base question — "where does money go?" — is answered | Monthly breakdown reports already answer the base question; budget is M3+ |
| ML/embedding-based categorization | For 1-5 users with limited history, local model training is infeasible; remote models add cost and latency with no benefit at this scale | Keyword rules + string similarity (rapidfuzz) cover ~75-85% of cases at this volume |
| Open Banking / bank feed integration | Heavy infrastructure (per-bank OAuth, certificates, compliance), high cost for personal use | CSV/OFX statement import is sufficient |
| Splits de movimentação (1 expense → N categories) | Increases model cardinality; 1:1 (movimentação ↔ lançamento) is correct and sufficient for the vast majority of cases | Defer until a concrete real case arises |
| Relatórios de ano fiscal / exportação contábil | This is not accounting software | Permanently out of scope |
| Metas de poupança / projeções | Requires rich temporal model and accumulated historical data | At least one full data cycle before any projection feature |
| Notificações / alertas | Delivery layer (push, email) without a deployed frontend is useless now | Wait for React/Capacitor frontend |
| Ciclos de fatura automáticos (corte_dia, vencimento_dia) | Adds a configuration entity and inference logic; user can set competência manually without it | Defer to M3 if demand arises |
| Contas compartilhadas entre famílias | Multi-tenant scope is absent by design | Permanently out of scope |
| Paginação cursor-based | At 1-5 users, LIMIT/OFFSET is sufficient forever | Never needed at this scale |

---

## Semi-Automatic Categorization — What Works Without ML

### The problem

Bank statements produce descriptions like `"POSTO IPIRANGA *004521 SP"` or `"PG FATURA NUAN BR"`.
The system needs to suggest the correct category without an ML model.

### Recommended approach: two-pass rule engine

**Pass 1 — Explicit keyword rules (deterministic)**
- Table `categoria_regra` per family: `{keyword, categoria_id, priority}`
- Match: case-insensitive substring search on `movimentacao.descricao`
- Confidence: HIGH — deterministic result; can be applied automatically without user confirmation
- Processing order: rules sorted by `priority` descending; first match wins

**Pass 2 — History-based similarity (fallback)**
- Triggered only when no explicit rule matches
- Query recent `lancamentos` for the same family where `movimentacao.descricao` is similar
- Algorithm: `rapidfuzz.token_sort_ratio()` (stdlib `SequenceMatcher` is acceptable if avoiding extra deps)
- Minimum threshold: 80/100 for a suggestion to surface
- Return top-3 candidates with score so the user can confirm
- On confirmation: optionally ask if a new keyword rule should be created for this pattern

### Why `token_sort_ratio` specifically

Bank descriptions reorder tokens between transactions from the same merchant:
- `"MERCADO LIVRE PAGAMENTO 001"` vs `"PAGAMENTO MERCADO LIVRE 002"`

`token_sort_ratio` normalizes token order before comparing — handles this correctly. `partial_ratio`
captures substrings when the description contains the merchant name plus variable suffixes.

### Expected accuracy at this scale

| Approach | Estimated Accuracy | Cost |
|----------|--------------------|------|
| Keyword rules alone (initial) | 60-70% initially; 85-90% after regular use | Low |
| History + similarity fallback | +10-15% additional coverage | Low |
| ML/embeddings | 90-95% | High (infeasible here) |

For 1-5 users at low volume (~50-200 entries/month), rules + history are sufficient. The system
improves organically: the more the user categorizes, the better the history becomes for Pass 2.

### Recommended endpoint

`POST /financeiro/movimentacoes/{id}/sugestao-categoria` returns:

```json
{
  "match_type": "rule" | "history" | "none",
  "suggestions": [
    {"categoria_id": 12, "confidence": 0.92, "source": "Regra: IPIRANGA", "tipo": "rule"},
    {"categoria_id": 12, "confidence": 0.85, "source": "Histórico: POSTO SHELL SP", "tipo": "history"}
  ]
}
```

The frontend displays it; the user confirms and calls `POST /financeiro/lancamentos`.

---

## The Two-Layer Model — Mature Pattern

### How mature apps handle this (GnuCash, hledger, Beancount, YNAB)

The universal pattern in serious personal finance software is:

```
Import / manual entry
       |
  Movimentação bruta     <- "what the bank recorded"
  (date, amount, description, account, status)
       |
  Reconciliation / classification
       |
  Lançamento             <- "what I recognize as an expense/income"
  (movimentacao FK, categoria, competencia, note)
```

**Why separate:**
- Raw movement is immutable — represents the banking fact; must not be edited
- Lançamento is the interpretation — can be re-categorized, corrected, or have competência adjusted
  without deleting the original data
- Reports read only lançamentos; import/deduplication operates on movimentações
- Allows "pending" queue: movimentações without a lançamento = reconciliation pending

**Recommended movement status values:**
- `pending` — imported or entered, awaiting reconciliation
- `reconciled` — lançamento created and confirmed
- `ignored` — discarded (internal transfers, IOF charges, fees to exclude from analysis)

---

## Competência — Patterns and Best Practices

### The credit card dilemma

Purchase made on Jan 28th in a billing cycle closing Feb 1st, due Feb 10th. Which competência?

- **Regime de competência (accrual):** expense belongs to January — when consumption occurred
- **Regime de caixa (cash basis):** cash outflow occurs in February — when the bill is paid

Both are valid and used in practice. Brazilian sources confirm both regimes have complementary value.

### Recommended decision for M2

Leave the field **free and optional on the lançamento**:

```
competencia_ano:  int | null
competencia_mes:  int 1-12 | null
```

- Default `null`: reports exclude from competência-based analysis but include in date-based analysis
- When filled: the user has explicitly decided which period the expense belongs to
- Do NOT auto-infer from credit card cycles — each family has different conventions

**Filter modes for reports:**
- `por_data`: aggregate by `movimentacao.data`
- `por_competencia`: aggregate by `lancamento.competencia_ano` + `competencia_mes`
  (excludes lançamentos with null competência)

### Credit card billing cycle model (deferred)

Modeling billing cycles (`corte_dia`, `vencimento_dia` per account) is a valid differentiator but
NOT table stakes for M2. The user can fill competência manually without the system knowing the cycle.
Defer to M3 if demand arises.

---

## Import Deduplication — Recommended Approach

### The problem

Re-importing the same statement (or overlapping date ranges) must not create duplicate movements.

### Fingerprint via composite key

Generate a SHA-256 hash over:
```
SHA256(conta_id + "|" + date_iso + "|" + amount_centavos_str + "|" + normalized_descricao)
```

Where `normalized_descricao` = strip whitespace, uppercase, collapse multiple spaces.

- Store hash on the movement as `import_hash UNIQUE`
- On batch import: `INSERT ... ON CONFLICT (import_hash) DO NOTHING`
- Return `{"imported": N, "skipped": M}` in the response

### Why not use OFX FITID

FITID (Financial Institution Transaction ID) from OFX looks ideal but is unreliable: Brazilian banks
frequently reuse IDs or change them months later (confirmed in hledger community discussions).
The composite key is more resilient.

### Date window tolerance

For small-scale personal use, exact date in the composite key is sufficient. Window-based matching
(±3 days for clearing delays) is a corporate reconciliation concern — unnecessary at this scale.

### Import traceability fields

```
import_hash:     str UNIQUE nullable  -- null for manual entries
import_source:   str nullable         -- "csv", "ofx", "manual"
import_batch_id: uuid nullable        -- groups records from the same upload
```

---

## Feature Dependencies

```
Family (existing v1.0)
  └── Conta
        └── Movimentação
              ├── import_hash (deduplication)
              ├── import_batch_id (traceability)
              └── Lançamento
                    ├── Categoria (2 levels, family-scoped)
                    ├── competencia_ano / competencia_mes (nullable)
                    └── [category suggestion uses lançamento history]

Categoria
  └── Categoria (self-referential, parent optional)
  └── CategoriaRegra (keyword → categoria, optional — M2 late or M3)
```

---

## MVP Recommendation for M2

### Priority 1 — Core (must exist for domain to have any value)

1. `Conta` — CRUD, family-scoped
2. `Categoria` — 2-level hierarchy, family-scoped, CRUD
3. `Movimentação` — manual entry + CSV batch import with hash-based deduplication
4. `Lançamento` — created from movement, with category + optional competência

### Priority 2 — Basic analysis (must ship with M2 for the domain to be useful)

5. Account balance (derived from movements)
6. Consolidated family balance
7. Monthly breakdown by category (parent and subcategory)

### Priority 3 — Comfort (second iteration of M2 or M3)

8. Category suggestion by history (rapidfuzz, no ML)
9. Persistent keyword rules per family
10. OFX import (beyond CSV)

### Definitively deferred

- Budget / forecast per category
- Automatic billing cycle detection
- Transaction splits (1:N)
- Notifications / alerts
- Savings goals / projections

---

## Sources

- [Transaction Deduplication — hledger community](https://groups.google.com/g/hledger/c/h5uuSLWsd9U)
- [Deduplication at Scale — Modern Treasury](https://www.moderntreasury.com/journal/deduplication-at-scale)
- [How to Auto-Categorize Bank Transactions — bankreconciler.app](https://bankreconciler.app/blogAutoCategorizeBankTransactions)
- [Using Category Rules — PocketSmith](https://learn.pocketsmith.com/article/156-using-category-rules-to-automatically-categorize-transactions)
- [RapidFuzz — PyPI](https://pypi.org/project/RapidFuzz/)
- [Regime de Competência e de Caixa — Transfeera](https://transfeera.com/blog/regime-de-caixa-e-regime-de-competencia/)
- [Fuzzy Matching in Financial Reconciliation — ReconArt](https://www.reconart.com/blog/fuzzy-matching-in-financial-reconciliation/)
- [GnuCash Reconciliation Docs v5](https://www.gnucash.org/docs/v5/C/gnucash-guide/cbook-reconacct1.html)
- [Hierarchical Classification of Financial Transactions — arXiv 2312.07730](https://arxiv.org/pdf/2312.07730)
- [Bank statement import duplicate detection — Manager Forum](https://forum.manager.io/t/bank-statement-import-duplicate-detection/25030)
