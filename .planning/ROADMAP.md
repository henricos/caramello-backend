# Roadmap: Caramello API

## Milestones

- ✅ **[v1.0 — Fundação](milestones/v1.0-ROADMAP.md)** — Stack async, auth Keycloak, estrutura por domínios, domínio families, MCP, Docker, testes _(SHIPPED 2026-05-30 · 5 phases · 25 plans)_
- 🚧 **v2.0 — Domínio Financeiro** — Contas, movimentações, categorias hierárquicas, conciliação, relatórios e MCP financeiro _(Em andamento · Phase 6–9)_

---

## Milestone 2: Domínio Financeiro

### Phases

- [x] **Phase 6: Fundação DSL + Schema** - YAMLs, extensão do gerador (Decimal + filters), Category + Subcategory e migration 0002 (completed 2026-05-31)
- [x] **Phase 7: CRUD Account + Category** - Operações de negócio com controle de acesso e validações (completed 2026-06-01)
- [ ] **Phase 8: Movimentações + Importação** - Registro individual, importação CSV/OFX/XLSX e deduplicação
- [ ] **Phase 9: Conciliação + Relatórios + MCP** - Lançamentos financeiros, saldos, breakdown e ferramentas MCP

---

## Phase Details

### Phase 6: Fundação DSL + Schema

**Goal**: O esquema financeiro está no banco e o código gerado está pronto para receber lógica de negócio
**Depends on**: Phase 5 (M1 completo — stack async, Keycloak, DSL generator, FastApiMCP)
**Requirements**: Nenhum requisito funcional direto — fase técnica que desbloqueia todas as fases do M2
**Technical constraints**:

- Naming convention `MetaData(naming_convention={...})` adicionada em `alembic/env.py` antes de qualquer migration nova
- 4 YAMLs DSL: `account.yaml`, `movement.yaml`, `financial_entry.yaml`, `category.yaml` com campo `domain: finances`
- `Category.parent_id` self-referencial: pós-processamento manual de `models.py` com `sa_relationship_kwargs={"remote_side": "Category.id", "foreign_keys": "[Category.parent_id]"}` — marcado `# CARAMELLO-GENERATED: implemented`
- Migration `0002_finances_schema.py`: `UniqueConstraint("movement_id")` em `FinancialEntry`, `import_hash UNIQUE` em `Movement`, índices em `account.family_id`, `movement.account_id`, `entry.competencia_year/month/category_id`
- Verificar `down_revision` com `alembic history --verbose` após gerar (pitfall P6)

**Success Criteria** (what must be TRUE):

  1. `alembic upgrade head` aplica migration 0002 sem erros em banco limpo
  2. `alembic downgrade -1` reverte completamente sem erro
  3. Tabelas `account`, `movement`, `financial_entry`, `category` existem com todas as colunas e constraints corretas (NUMERIC(15,2), UNIQUE em movement_id e import_hash)
  4. Código gerado em `src/caramello/finances/` passa em `python -c "from caramello.finances import models"` sem ImportError
  5. Hierarquia de categorias em duas entidades (`Category` + `Subcategory`, D-06): `Subcategory.category_id` → `Category.id`; sem self-referencial nem pós-processamento manual

**Plans**: 3 plansPlans:
**Wave 1**

- [x] 06-01-PLAN.md — Estende o gerador DSL: tipo Decimal→Numeric(15,2), bloco filters→__table_args__, finances em DOMAIN_TO_ENTITY_NAME, ruff dinâmico + testes Wave 0

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Cria 5 YAMLs financeiros (Category+Subcategory), manifest, operations stub; gera src/caramello/finances/ + testes Wave 0

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 06-03-PLAN.md — naming_convention em alembic/env.py, imports finances, migration 0002 + verificação upgrade/downgrade em banco real

### Phase 7: CRUD Account + Category

**Goal**: Usuário autenticado pode gerenciar contas e categorias hierárquicas da sua família
**Depends on**: Phase 6
**Requirements**: ACC-01, ACC-02, ACC-03, CAT-01, CAT-02, CAT-03, CAT-04, AUTH-FIN-01, AUTH-FIN-02
**Technical constraints**:

- `finances/operations.py`: CRUD de Account, Category e Subcategory com schemas públicos `*Public` (UUID, nunca `id`/`family_id`)
- Helper `_require_family_access(family_id, current_user, session)` em `shared/auth.py` (import lazy de FamilyMember) — retorna 403 se usuário não é membro; reutilizável nas Phases 8/9
- Hierarquia max 2 níveis (CAT-03) enforced ESTRUTURALMENTE pelo schema de duas tabelas (Subcategory → Category); sem validação de `parent_id`
- Router `finances_operations.router` registrado em `main.py` ANTES de `FastApiMCP(...)` (pitfall P7); `finances/router.py` gerado NÃO registrado (D-01/D-02)
- `updated_at` definido manualmente no PATCH (sem `onupdate` automático)

**Success Criteria** (what must be TRUE):

  1. `POST /finances/accounts` cria conta com nome, tipo e moeda; resposta inclui `uuid`, sem `id`/`family_id`
  2. `GET /finances/accounts` retorna apenas contas da família do usuário autenticado; 403 sem token; 403 para família alheia
  3. `PATCH /finances/accounts/{uuid}` arquiva conta com `is_active=false`; movimentações existentes permanecem
  4. `POST /finances/categories` cria categoria pai (nível 1)
  5. `POST /finances/subcategory` com `category_uuid` válido cria subcategoria (nível 2); não existe rota de nível 3 (CAT-03 estrutural)

**Plans**: 3 plans
**Wave 0**

- [x] 07-01-PLAN.md — Scaffold tests/test_finances_operations.py (Nyquist): testes skipados cobrindo ACC-01..03, CAT-01..04, AUTH-FIN-01..02

**Wave 1** *(blocked on Wave 0 completion)*

- [x] 07-02-PLAN.md — Helper `_require_family_access` em shared/auth.py + CRUD de Account (schemas públicos, arquivamento) + registro do router em main.py antes do MCP

**Wave 2** *(blocked on Wave 1 completion — mesmo arquivo operations.py)*

- [x] 07-03-PLAN.md — CRUD de Category (nível 1) + Subcategory (nível 2, rotas planas) scoped por família; CAT-03 estrutural; 6 paths do router

**UI hint**: no

### Phase 8: Movimentações + Importação

**Goal**: Usuário pode registrar e importar movimentações brutas com deduplicação automática
**Depends on**: Phase 7
**Requirements**: MOV-01, MOV-02, MOV-03, MOV-04, MOV-05
**Technical constraints**:

- `finances/services.py`: `import_movements(file, format, account_uuid, current_user, session)`
- SHA-256 de `(account_id|date|amount|descricao_normalizada)` como `import_hash`
- `pg_insert(Movement).on_conflict_do_nothing(index_elements=["import_hash"])` — não abortar lote (pitfall P4)
- Movimentações cujo hash já existe são inseridas com `is_duplicate=true` via detecção pré-insert
- Parsers: CSV (stdlib `csv`), OFX (`ofxparse`), XLSX (`openpyxl` com `read_only=True`)
- `amount` sempre `Decimal` — nenhum `float` em campo monetário (pitfall P1)
- `python-multipart` necessário para upload de arquivo via FastAPI

**Success Criteria** (what must be TRUE):

  1. `POST /finances/accounts/{uuid}/movements` registra movimentação individual (tipo, data, valor, descrição) e retorna `uuid`
  2. `POST /finances/accounts/{uuid}/movements/import` com CSV retorna contagem de inseridas vs duplicatas
  3. `POST /finances/accounts/{uuid}/movements/import` com OFX e XLSX também funciona
  4. Reimportar o mesmo arquivo não duplica linhas no banco — linhas já existentes ficam com `is_duplicate=true`
  5. Campos de valor persistidos como `NUMERIC(15,2)` — `0.10 + 0.20 == 0.30` sem erro de ponto flutuante

**Plans**: 4 plans
**Wave 0**

- [x] 08-01-PLAN.md — Stubs Nyquist de MOV-01..05 (test_finances_operations + test_finances_service) + deps ofxparse/openpyxl

**Wave 1** *(blocked on Wave 0 completion)*

- [ ] 08-02-PLAN.md — movement.yaml sem type/is_duplicate (D-01/D-02) + regenerar models + migration 0003 (D-03)

**Wave 2** *(blocked on Wave 1 — usa o ORM regenerado)*

- [ ] 08-03-PLAN.md — finances/services.py: parsers CSV/OFX/XLSX, hash, normalização e import_movements com dedup em lote

**Wave 3** *(blocked on Wave 2 — consome import_movements)*

- [ ] 08-04-PLAN.md — Endpoints de Movement em operations.py: POST individual (409), import CSV/OFX/XLSX, import/confirm, GET paginado

### Phase 9: Conciliação + Relatórios + MCP

**Goal**: Usuário pode conciliar movimentações em lançamentos classificados e consultar relatórios analíticos; agentes de IA acessam sugestão de categoria e listagem de lançamentos via MCP
**Depends on**: Phase 8
**Requirements**: LAN-01, LAN-02, LAN-03, LAN-04, LAN-05, REL-01, REL-02, REL-03, REL-04, REL-05
**Technical constraints**:

- `POST /finances/movements/{uuid}/reconcile` — cria `FinancialEntry` 1:1; retorna 409 se já existe (constraint `UNIQUE movement_id`)
- `suggest_category()` em `finances/services.py`: `rapidfuzz.token_set_ratio` contra descrições de lançamentos anteriores da família
- Agregações via `session.execute()` com `func.sum + group_by` — não `session.exec()` (pitfall P1 serialização Decimal)
- `account_balance()`: soma créditos − débitos de `Movement` para conta
- `family_balance()`: soma de `account_balance()` por conta ativa da família
- `monthly_breakdown()`: agrupa `FinancialEntry` por `(competencia_year, competencia_month, category.parent_id)` + detalhe por subcategoria
- Ferramentas MCP: `suggest_category` e `list_my_financial_entries` via whitelist em `main.py`
- `selectinload` em queries de serialização (pitfall P3)

**Success Criteria** (what must be TRUE):

  1. `POST /finances/movements/{uuid}/reconcile` cria lançamento com subcategoria e competência; segunda chamada retorna 409
  2. `GET /finances/movements/{uuid}/suggest-category` retorna subcategorias ordenadas por score de similaridade com a descrição
  3. `GET /finances/accounts/{uuid}/balance` retorna soma correta (Decimal) de créditos − débitos
  4. `GET /finances/families/{uuid}/balance` retorna saldo consolidado de todas as contas ativas
  5. `GET /finances/reports/monthly` agrupa lançamentos por competência e categoria pai; detalhe por subcategoria disponível com filtro de categoria
  6. Ferramenta `suggest_category` e `list_my_financial_entries` aparecem em `GET /mcp` com Bearer token válido

**Plans**: TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 6. Fundação DSL + Schema | 3/3 | Complete    | 2026-05-31 |
| 7. CRUD Account + Category | 3/3 | Complete    | 2026-06-01 |
| 8. Movimentações + Importação | 1/4 | In Progress|  |
| 9. Conciliação + Relatórios + MCP | 0/? | Not started | - |

---

## Backlog

| Item | Origem | Prioridade |
|------|--------|-----------|
| FAMILY-04: código de convite reutilizável | M1 D-04 | Alta |
| FAMILY-05: solicitação de entrada via convite | M1 D-04 | Alta |
| FAMILY-06: aprovação/rejeição de solicitações | M1 D-04 | Alta |
| OPS-01: GET /health com ping ao banco | v2 backlog | Média |
| OPS-02: logging estruturado (structlog) | v2 backlog | Média |
| OPS-03: SSL no DATABASE_URL em produção | v2 backlog | Média |
| OPS-04: CI pipeline (GitHub Actions) | v2 backlog | Baixa |
| MCP-03: ferramentas MCP de escrita | v2 backlog | Baixa |
