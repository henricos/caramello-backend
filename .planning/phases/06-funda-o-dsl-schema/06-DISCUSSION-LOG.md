# Phase 6: Fundação DSL + Schema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 6 — Fundação DSL + Schema
**Areas discussed:** Campos monetários no DSL, Competência em FinancialEntry, Campo 'level' em Category, Constraints especiais nos YAMLs vs migration

---

## Campos Monetários no DSL

| Option | Description | Selected |
|--------|-------------|----------|
| Adicionar 'Decimal' ao gerador | Tipo DSL nativo → Numeric(15,2) + Decimal Python. Phase 6 já toca no gerador. | ✓ |
| Pós-processamento manual | Declarar `float` no YAML, sobrescrever em models.py. Todo campo monetário futuro exige edição manual. | |
| Claude decide | Claude escolhe a abordagem. | |

**User's choice:** Adicionar 'Decimal' ao gerador
**Notes:** Decidido também que NUMERIC(15,2) é fixo — sem precision/scale configurável no YAML (YAGNI).

---

## Competência em FinancialEntry

| Option | Description | Selected |
|--------|-------------|----------|
| Dois campos int (year + month) | `competencia_year: int` + `competencia_month: int`. Alinhado com ROADMAP. | ✓ |
| Um campo date (dia=1 por convenção) | `competencia: date` = 2026-05-01. Simplifica range queries mas exige convenção não-óbvia. | |
| String 'YYYY-MM' | Legível, sem constraints de banco, ordering requer cast. | |

**User's choice:** Dois campos int
**Follow-up — valor próprio no FinancialEntry:**

| Option | Description | Selected |
|--------|-------------|----------|
| Herda da Movimentação | FinancialEntry só classifica; valor vem de Movement via JOIN. | ✓ |
| Campo de valor próprio | `amount: Decimal` no FinancialEntry para suportar valor de competência diferente do bruto. | |

**Notes:** FinancialEntry é puramente um registro de classificação (subcategoria + competência + notas + is_recorrente). Valor sempre da Movement.

---

## Campo 'level' em Category / Hierarquia

Esta área passou por uma mudança de direção significativa durante a discussão.

**Pergunta inicial:** Incluir campo `level: int` ou derivar via parent_id?

**User's choice (livre):** "Separar em 2 entidades — Category (pai) + Subcategory (filha)."

Isso representou uma mudança de paradigma: de uma entidade self-referencial para duas entidades distintas. O usuário foi proativo em sugerir uma solução mais limpa que o ROADMAP original.

**Follow-up — nomenclatura das duas entidades:**

| Option | Description | Selected |
|--------|-------------|----------|
| CategoryGroup + Category | CategoryGroup = pai, Category = filha. | |
| CategoryParent + Category | Explícito mas redundante. | |
| Category + Subcategory | Category = nível 1, Subcategory = nível 2. Explicitamente hierárquico. | ✓ |

**Follow-up — nome da FK em Subcategory:**

| Option | Description | Selected |
|--------|-------------|----------|
| category_id: int (FK obrigatória) | Subcategory.category_id → Category.id. Obrigatório. | ✓ |
| Claude decide | Claude define o nome. | |

**Notes:** A decisão de usar duas entidades elimina o pós-processamento manual de `sa_relationship_kwargs` que o ROADMAP previa. CAT-03 (máximo 2 níveis) vira restrição estrutural do modelo — Subcategory não tem campo para apontar para outra Subcategory.

---

## Constraints Especiais nos YAMLs vs Migration

**Pergunta inicial:** UniqueConstraint de tabela e índices: extensão do DSL ou só na migration?

| Option | Description | Selected |
|--------|-------------|----------|
| Só na migration manual | YAMLs só declaram unique por campo. Constraints de tabela e índices ficam na migration. | |
| Extender o DSL com table_constraints | Novo bloco no YAML. Gerador emite `__table_args__`. | ✓ |

**User's choice:** Extender o DSL

**Follow-up — nome do bloco de índices:**
O usuário levantou que o DSL é multi-camada (banco + API + UI), não apenas banco. "Index" é conceito de banco; o DSL deve expressar a intenção abstrata.

| Option | Description | Selected |
|--------|-------------|----------|
| filters: | Representa "este campo é um filtro natural da entidade". | ✓ |
| query_by: | Mais técnico. Descreve como a entidade é consultada. | |

**Follow-up — unique composto:**
O usuário perguntou se há caso de uso para `unique_together` no Phase 6. Identificado que não há: todos os unique constraints do Phase 6 são de coluna única (expressáveis via `unique: true` por campo).

| Option | Description | Selected |
|--------|-------------|----------|
| Só 'filters:' agora | YAGNI — implementar apenas o que Phase 6 usa. | ✓ |
| Adicionar 'unique_together' também | Future-proof mas sem uso imediato. | |

**Notes:** Sintaxe final do bloco `filters:`:
```yaml
filters:
  - fields: [account_id]
  - fields: [competencia_year, competencia_month]
```
Gera `Index('ix_{table}_{fields}', ...)` em `__table_args__`.

---

## Claude's Discretion

Nenhuma área foi delegada ao Claude. Todas as decisões foram tomadas pelo usuário.

## Deferred Ideas

- **`unique_together:` no DSL** — unique composto de múltiplas colunas. Nenhum caso de uso em Phase 6. Implementar quando surgir o primeiro caso real.
- **`filters:` → query params automáticos** — usar o bloco `filters:` para auto-gerar query params nos routers. Ideia para Phases 7+.
- **Decisão sobre registrar routers de finances em `main.py`** — pode ser Phase 6 ou Phase 7. Deixado para o planner decidir.
