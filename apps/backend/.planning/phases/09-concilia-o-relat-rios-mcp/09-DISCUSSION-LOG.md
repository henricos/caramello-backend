# Phase 9: Conciliação + Relatórios + MCP - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 09-Conciliação + Relatórios + MCP
**Areas discussed:** Schema/Atribuição, Splits, Resposta da conciliação, Shape dos relatórios, Sugestão de categoria, MCP tools

---

## Schema/Atribuição de responsável

| Option | Description | Selected |
|--------|-------------|----------|
| responsible_user_uuid em Movement | Campo no fato bancário bruto | |
| responsible_user_uuid em FinancialEntry | Campo de classificação no lançamento | ✓ |

**User's choice:** FamilyMember como referência (mas implementado via user_id FK por limitação de schema — FamilyMember não tem UUID próprio)
**Uso escolhido:** Filtro nos relatórios mensais + Breakdown por membro da família (Phase 9)
**Notes:** Usuário descreveu casos de uso: Uber, assinatura de serviço, compras — identificar quem gerou o gasto. Gastos coletivos sem responsável são válidos (campo nullable). Novo relatório `GET /finances/reports/by-member` incluído nesta fase.

---

## Splits de movimentação

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-relacionamento em Movement | Movement pode ter filhos | |
| FinancialEntry 1:N com amount por split | Mudar UNIQUE constraint | |
| Defer para M3 | Manter 1:1 nesta fase | ✓ |

**User's choice:** Defer para M3
**Notes:** Usuário descreveu o caso: supermercado R$500 → R$150 ração, R$200 fralda, R$150 "geral". Arquitetura documentada em CONTEXT.md D-SPLITS-DEFER. Phase 9 mantém 1:1 sem fechar portas.

---

## Resposta da conciliação

| Option | Description | Selected |
|--------|-------------|----------|
| Apenas FinancialEntry | Só campos do lançamento | |
| FinancialEntry + Movement embutida | date, amount, description embutidos | ✓ |

**User's choice:** FinancialEntry + dados da Movement embutidos
**Endpoint adicional:** GET /finances/entries/{uuid} incluído (sim — necessário para edição LAN-05 e exibição)
**Notes:** Schema rico aplicado a todos os endpoints de FinancialEntry (POST reconcile, GET by UUID, PATCH, GET list).

---

## Shape dos relatórios mensais

| Option | Description | Selected |
|--------|-------------|----------|
| Hierarquia aninhada | categories com subcategories nested | |
| Lista plana | rows com category_name + subcategory_name + total | ✓ |

**User's choice:** Lista plana (freeform — não selecionou opção predefinida)
**Motivo:** "plana dá mais liberdade para o componente do front agrupar como preferir"
**Filtros:** year + month + family_uuid (obrigatórios) + member_uuid (opcional)
**Relatório by-member:** year + month obrigatórios; lançamentos sem responsável agrupados em linha "Não atribuído"

---

## Sugestão de categoria

| Option | Description | Selected |
|--------|-------------|----------|
| Top 3 | Suficiente para casos comuns | |
| Top 5 | Mais opções quando scores parecidos | ✓ |
| Todas acima de threshold | Quantidade variável | |

**User's choice:** Top 5
**Scores expostos:** Sim — score de 0-100 incluído na resposta
**Notes:** Score exposto para frontend indicar confiança visualmente. Lista vazia `[]` quando sem histórico.

---

## MCP tools

| Option | Description | Selected |
|--------|-------------|----------|
| list_my_financial_entries (Phase 9) | Padrão similar ao list_my_families | |
| suggest_category (Phase 9) | Valida integração com rapidfuzz | |
| Nenhuma — defer tudo para M3 | APIs primeiro, MCP depois | ✓ |

**User's choice:** Defer ALL para M3
**Motivo:** "APIs e services devem amadurecer antes de expor via MCP; podem mudar muito ainda"
**Notes:** Whitelist de main.py não modificada nesta fase.

---

## Listagem e filtro de pendentes

| Option | Description | Selected |
|--------|-------------|----------|
| ?reconciled=false server-side | LEFT JOIN com FinancialEntry | ✓ |
| Frontend filtra no cliente | Backend só retorna tudo | |

**User's choice:** ?reconciled=false server-side
**entry_uuid no MovementReadPublic:** Sim — UUID do lançamento se conciliada, null se pendente
**GET /finances/entries:** Sim — listagem por família/período incluída

---

## Claude's Discretion

- Estrutura interna de `FinancialEntryRichPublic` (schema Pydantic ou inline em operations.py)
- Organização das funções de agregação em `services.py`
- Tratamento de `responsible_user_uuid=None` no PATCH (sentinela para "limpar" vs. "não atualizar")

## Deferred Ideas

- MCP tools financeiras (`suggest_category`, `list_my_financial_entries`) → M3
- Splits de movimentação (1:N) → M3 (arquitetura documentada)
- Filtros avançados em GET /entries (subcategory, responsible_user, faixa de valor) → fase futura
- Auto-sugestão de responsável por conta de origem → M3 backlog
- Relatório acumulado anual por membro (month opcional) → após validar uso mensal
