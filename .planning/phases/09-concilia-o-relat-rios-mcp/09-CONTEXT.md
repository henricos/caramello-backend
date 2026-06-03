# Phase 9: Conciliação + Relatórios + MCP - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementar conciliação de movimentações em lançamentos financeiros classificados, relatórios analíticos (saldos, breakdown mensal, breakdown por membro) e estender o schema de Movement com indicador de conciliação.

**Entregáveis concretos:**
- `src/caramello/finances/operations.py` estendido com endpoints de FinancialEntry e relatórios
- `src/caramello/finances/services.py` estendido com `suggest_category()` e funções de agregação
- Schema `MovementReadPublic` estendido com `entry_uuid: UUID | None`
- Migration `0004_financial_entry_responsible_user.py`: adiciona `responsible_user_id` em `financial_entry`
- Requisitos LAN-01..05 e REL-01..05 implementados

**Endpoints desta fase:**
- `POST /finances/movements/{uuid}/reconcile` — cria FinancialEntry 1:1 (LAN-01/02)
- `GET /finances/movements/{uuid}/suggest-category` — top-5 sugestões com score (LAN-03)
- `GET /finances/entries/{uuid}` — detalhe de lançamento (schema rico)
- `PATCH /finances/entries/{uuid}` — atualiza subcategoria, competência, notas, responsável (LAN-05)
- `GET /finances/entries?family_uuid=&year=&month=` — listagem de lançamentos por família/período
- `GET /finances/accounts/{uuid}/movements?reconciled=false|true` — filtro de pendência (extensão Phase 8)
- `GET /finances/accounts/{uuid}/balance` — saldo da conta (REL-01)
- `GET /finances/families/{uuid}/balance` — saldo consolidado familiar (REL-02)
- `GET /finances/reports/monthly?family_uuid=&year=&month=[&member_uuid=]` — breakdown mensal plano (REL-03/04)
- `GET /finances/reports/by-member?family_uuid=&year=&month=` — breakdown por membro da família (novo)

**Fora de escopo desta fase:**
- MCP tools financeiras (`suggest_category`, `list_my_financial_entries`) — deferidas para M3
- Splits de movimentação (1:N) — deferidos para M3
- Listagem de lançamentos com filtros avançados além de família/período

</domain>

<decisions>
## Implementation Decisions

### Schema — FinancialEntry (migration necessária)

- **D-SCHEMA-01:** Adicionar `responsible_user_id: INT NULL` (FK → `user.id`) a `financial_entry`. Nullable — não obrigatório. Migration `0004_financial_entry_responsible_user.py` com `down_revision` apontando para `0003_movement_schema_update`. Verificar com `alembic history --verbose` antes de gerar (pitfall P6 do STATE.md).
- **D-SCHEMA-02:** `FamilyMember` é link table com PK composta (`user_id + family_id`) sem UUID próprio — referência direta não é prática. `responsible_user_id` aponta para `user.id`, com validação de membership no service (não no banco).

### Atribuição de responsável

- **D-ATTR-01:** API pública usa `responsible_user_uuid: UUID | None` no payload de criação/atualização. Backend resolve para `responsible_user_id` via `session.execute(select(User).where(User.uuid == responsible_user_uuid))`. Retorna 422 se UUID inválido.
- **D-ATTR-02:** Validação de membership: após resolver `responsible_user_id`, verificar que o usuário é membro da família da conta (via `select(FamilyMember).where(family_id == X, user_id == responsible_user_id)`). Retorna 422 com mensagem clara se não for membro.
- **D-ATTR-03:** `responsible_user_uuid` exposto em todos os schemas de resposta de FinancialEntry. Null quando não atribuído.

### Endpoint de conciliação

- **D-REC-01:** `POST /finances/movements/{uuid}/reconcile` cria FinancialEntry. Retorna 409 se `FinancialEntry.movement_id` já existe (constraint UNIQUE do banco). Payload: `{subcategory_uuid, competencia_year, competencia_month, notes?, is_recorrente?, responsible_user_uuid?}`.
- **D-REC-02:** Resposta rica — todos os endpoints de FinancialEntry retornam o mesmo schema: `{uuid, movement: {uuid, date, amount, description}, subcategory_uuid, subcategory_name, category_uuid, category_name, competencia_year, competencia_month, notes, is_recorrente, responsible_user_uuid, created_at, updated_at}`. Evita GET extra para montar tela de confirmação.
- **D-REC-03:** `GET /finances/entries/{uuid}` — mesmo schema rico do POST reconcile.
- **D-REC-04:** `PATCH /finances/entries/{uuid}` — campos opcionais: `subcategory_uuid`, `competencia_year`, `competencia_month`, `notes`, `is_recorrente`, `responsible_user_uuid`. Retorna schema rico. `updated_at` definido manualmente (sem `onupdate` automático, padrão Phase 7/8).
- **D-REC-05:** `GET /finances/entries?family_uuid=&year=&month=` — lista plana de lançamentos da família para o período. Mesma estrutura rica por item. `year` e `month` opcionais (sem eles retorna todos da família).

### Movement — indicador de conciliação

- **D-MOV-01:** Campo `entry_uuid: UUID | None` adicionado a `MovementReadPublic` em `operations.py`. Computado via LEFT JOIN com `FinancialEntry`. `null` = movimentação pendente de conciliação; UUID = já conciliada.
- **D-MOV-02:** Filtro `?reconciled=true|false` adicionado ao endpoint `GET /finances/accounts/{uuid}/movements` existente (Phase 8). Implementado como LEFT JOIN + condição `IS NULL` / `IS NOT NULL` em `financial_entry.movement_id`. Parâmetro opcional — sem ele retorna todas.

### Sugestão de categoria

- **D-CAT-01:** `GET /finances/movements/{uuid}/suggest-category` — busca `Movement.description` pelo UUID, roda `rapidfuzz.token_set_ratio` contra `Movement.description` de todas as `FinancialEntry` da mesma família, retorna top-5 subcategorias únicas ordenadas por score decrescente.
- **D-CAT-02:** Resposta: `[{subcategory_uuid, subcategory_name, category_uuid, category_name, score: int}]`. Score de 0-100. Scores expostos — úteis para o frontend indicar confiança.
- **D-CAT-03:** Sem histórico de lançamentos → retorna `[]` (lista vazia, sem erro). Sem threshold mínimo — top-5 do que existir.
- **D-CAT-04:** `suggest_category(movement_uuid, family_id, session)` implementada em `finances/services.py`.

### Relatórios — saldos

- **D-BAL-01:** `GET /finances/accounts/{uuid}/balance` → `{account_uuid, balance: Decimal (string), currency}`. `balance = SUM(movement.amount)` para conta (créditos positivos, débitos negativos — convenção Phase 8 D-01). Aggregação via `session.execute(select(func.sum(Movement.amount)).where(...))`.
- **D-BAL-02:** `GET /finances/families/{uuid}/balance` → `{family_uuid, total_balance: Decimal, accounts: [{account_uuid, name, currency, balance}]}`. Apenas contas ativas (`is_active=true`). `total_balance = sum(account balances)`.
- **D-BAL-03:** Saldo calculado sob demanda — sem cache em `Account`. Consistência com movimentações em tempo real.

### Relatórios — mensal e por membro

- **D-REP-01:** `GET /finances/reports/monthly?family_uuid=&year=&month=[&member_uuid=]` — lista plana de entradas por subcategoria. O frontend agrupa como preferir. `member_uuid` opcional — filtra por `responsible_user_id`. Retorna:
  ```json
  {
    "period": {"year": 2026, "month": 5},
    "total": "1200.00",
    "rows": [
      {"category_uuid": "...", "category_name": "Transporte",
       "subcategory_uuid": "...", "subcategory_name": "Gasolina",
       "total": "300.00", "count": 5}
    ]
  }
  ```
- **D-REP-02:** `GET /finances/reports/by-member?family_uuid=&year=&month=` — breakdown por responsável. `year` e `month` obrigatórios. Retorna:
  ```json
  {
    "period": {"year": 2026, "month": 5},
    "total": "1200.00",
    "rows": [
      {"user_uuid": "...", "name": "João", "total": "500.00", "count": 8},
      {"user_uuid": null, "name": "Não atribuído", "total": "700.00", "count": 12}
    ]
  }
  ```
  Lançamentos sem `responsible_user_id` agrupados em linha `user_uuid: null, name: "Não atribuído"`.
- **D-REP-03:** Todos os relatórios operam sobre `FinancialEntry.competencia_year/month` — não sobre `Movement.date` (REL-05 obrigatório).
- **D-REP-04:** Agregações via `session.execute()` com `func.sum + group_by` — nunca `session.exec()` (pitfall P3).

### MCP

- **D-MCP-01** [informational]: Todas as ferramentas MCP financeiras (`suggest_category`, `list_my_financial_entries`) deferidas para M3. Phase 9 não modifica a whitelist de `main.py`. Motivo: APIs e services devem amadurecer antes de expor via MCP.

### Splits (deferidos para M3)

- **D-SPLITS-DEFER** [informational]: Splits (1:N) fora do escopo desta fase. Arquitetura para M3: remover constraint `UNIQUE` em `financial_entry.movement_id` + adicionar campo `amount: NUMERIC(15,2) NOT NULL` por split + adicionar `responsible_user_id` por split. Phase 9 mantém 1:1 — nenhuma porta fechada.

### Claude's Discretion

- Estrutura interna de `FinancialEntryRichPublic` (schema rico): planner define campos exatos e se usa um Pydantic model separado ou schema inline.
- Organização das funções de agregação em `services.py`: `account_balance()`, `family_balance()`, `monthly_breakdown()`, `suggest_category()` podem ser funções independentes no mesmo arquivo.
- Tratamento de `responsible_user_uuid=None` no PATCH: campo ausente = não atualizar; campo presente como `null` = limpar o responsável (None no banco). Planner implementa como `Optional` com sentinela.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos funcionais
- `.planning/ROADMAP.md` §Phase 9 — goal, technical constraints (pitfalls P1/P3/P7, selectinload, success criteria). **LEITURA OBRIGATÓRIA.**
- `.planning/REQUIREMENTS.md` §Lançamentos Financeiros (LAN-01..05) — requisitos de conciliação. Nota: LAN-03 (suggest) implementado como endpoint REST nesta fase (não MCP).
- `.planning/REQUIREMENTS.md` §Relatórios e Saldos (REL-01..05) — REL-05 obrigatório: relatórios sobre competência, não data da movimentação.
- `.planning/REQUIREMENTS.md` §Autorização (AUTH-FIN-01/02) — 401 sem token, 403 para família alheia (já implementado, reutilizar).

### Schema e migration
- `alembic/versions/0003_movement_schema_update.py` — migration mais recente; `down_revision` da nova migration `0004` deve apontar para ela. Verificar com `alembic history --verbose` (pitfall P6).
- `src/caramello/finances/models.py` — `FinancialEntry` (campos existentes: movement_id UNIQUE, subcategory_id, competencia_year/month, notes, is_recorrente). **Nova coluna:** `responsible_user_id INT NULL FK → user.id`.
- `dsl/entities/financial_entry.yaml` — atualizar com campo `responsible_user` se gerador for reusado; caso contrário adicionar manualmente em `models.py` com `# CARAMELLO-GENERATED: implemented`.

### Padrões de código existentes
- `src/caramello/finances/operations.py` — **referência direta** para todos os novos endpoints (schemas públicos locais, router prefix `/finances`, `_require_family_access`, `session.execute()`). **LER ANTES de implementar.**
- `src/caramello/finances/services.py` — `import_movements()` como referência de como serviços com lógica de negócio são estruturados neste domínio.
- `src/caramello/shared/auth.py:_require_family_access` — reutilizar para todos os endpoints de FinancialEntry e relatórios.
- `src/caramello/families/models.py:FamilyMember` — para validação de membership de `responsible_user_uuid`.

### Integração
- `src/caramello/main.py` — NÃO modificar whitelist MCP nesta fase (D-MCP-01). Confirmar que router de finances ainda está registrado ANTES de `FastApiMCP(...)`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `finances/operations.py:router` — mesmo `APIRouter(prefix="/finances")`. Todos os endpoints de FinancialEntry e relatórios são adicionados a este router existente.
- `shared/auth.py:_require_family_access(family_id, current_user, session)` — reutilizar para todos os endpoints. Para FinancialEntry: resolver `movement_uuid → movement → account.family_id`.
- `finances/services.py:import_movements` — padrão de como serviços complexos são organizados; `suggest_category()` segue estrutura similar.
- `finances/models.py:FinancialEntry` — já tem `movement_id (UNIQUE)`, `subcategory_id`. **Adição necessária:** `responsible_user_id INT NULL FK → user.id`.
- `finances/operations.py:MovementReadPublic` — schema a estender com `entry_uuid: UUID | None`.

### Established Patterns
- `session.execute()` para queries com JOIN e agregações — nunca `session.exec()` (pitfall P3).
- UUID público em todos os paths e payloads, nunca `id` interno.
- `Decimal` em todos os campos monetários — zero `float` (pitfall P1).
- `from __future__ import annotations` no topo de cada arquivo de operations.
- Schemas públicos definidos localmente em `operations.py` — sobrescrevem os schemas gerados em `models.py`.
- `updated_at` definido manualmente no PATCH (sem `onupdate` automático — padrão Phase 7/8).
- `selectinload` explícito ao retornar objetos com relacionamentos (pitfall P3 do ROADMAP Phase 7).

### Integration Points
- `finances/operations.py`: adicionar endpoints de FinancialEntry ao router existente. Não criar router separado.
- `finances/services.py`: adicionar `account_balance()`, `family_balance()`, `monthly_breakdown()`, `by_member_breakdown()`, `suggest_category()`.
- `finances/operations.py:MovementReadPublic`: adicionar `entry_uuid: UUID | None` ao schema existente + atualizar `list_movements` com LEFT JOIN.
- `main.py`: sem alterações (MCP deferido, router já registrado).

</code_context>

<specifics>
## Specific Ideas

- **`responsible_user_uuid` no breakdown por membro:** lançamentos sem responsável são agrupados em linha `{user_uuid: null, name: "Não atribuído"}` — não descartados dos totais.
- **Resposta rica do reconcile:** o campo `movement` embutido expõe `uuid`, `date`, `amount` (Decimal como string), `description` — suficiente para o frontend montar a tela de confirmação sem GET extra.
- **Score da sugestão de categoria:** score de 0-100 (rapidfuzz); exposto na resposta para que o frontend possa indicar visualmente a confiança da sugestão (ex: badge "Alta confiança" acima de 80).
- **Filtro `?reconciled=false`:** implementado como LEFT JOIN de `Movement` com `FinancialEntry` onde `financial_entry.id IS NULL`. Eficiente com o índice já existente em `financial_entry.movement_id`.

</specifics>

<deferred>
## Deferred Ideas

- **MCP tools financeiras** (`suggest_category`, `list_my_financial_entries`) — M3. Motivo: APIs devem amadurecer antes de expor via MCP; mudanças de schema ainda prováveis.
- **Splits de movimentação (1:N)** — M3. Arquitetura documentada em D-SPLITS-DEFER. Não fecha portas com a implementação 1:1 desta fase.
- **Filtros avançados em GET /entries** (por subcategory, por responsible_user, por faixa de valor) — próxima iteração após validar uso básico.
- **Auto-sugestão de responsável** — heurística por conta de origem (ex: conta do João → sugerir João como responsável). Backlog M3.
- **Relatório acumulado anual por membro** — `year` obrigatório, `month` opcional no `by-member`. Deferido para quando uso mensal estiver validado.

</deferred>

---

*Phase: 9-Conciliação + Relatórios + MCP*
*Context gathered: 2026-06-03*
