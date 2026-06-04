# Phase 7: CRUD Account + Category - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementar os endpoints de CRUD de Account e Category/Subcategory com controle de acesso por família. O usuário autenticado pode criar, listar, detalhar, atualizar e arquivar contas bancárias da sua família, e gerenciar categorias hierárquicas (2 níveis) também scoped por família.

**Entregáveis concretos:**
- `src/caramello/finances/operations.py` implementado (CRUD de Account + Category + Subcategory)
- `src/caramello/shared/auth.py` estendido com `_require_family_access`
- Schemas locais de API pública (AccountCreatePublic, AccountReadPublic, CategoryCreatePublic, etc.)
- Routers financeiros registrados em `main.py` ANTES de `FastApiMCP(...)`

**Fora de escopo desta fase:**
- Movimentações (MOV-01 a MOV-05) — Phase 8
- Lançamentos financeiros e relatórios — Phase 9
- Saldo de conta — Phase 9 (derivado de movimentações)
- Deleção real de Account ou Category (sem histórico de movimentações ainda)

</domain>

<decisions>
## Implementation Decisions

### Localização da lógica de negócio

- **D-01:** Business logic implementada em `finances/operations.py` — segue o padrão de `families/operations.py`. O `router.py` gerado **não é registrado em `main.py`** para Account/Category nesta fase.
- **D-02:** `router.py` gerado é **mantido no disco** mas não registrado. Funciona como referência e pode ser registrado parcialmente em fases futuras quando Movement/FinancialEntry precisarem de endpoints.
- **D-03:** Organização interna dos routers em `operations.py` (um router por entidade vs. router unificado) é decisão do planner.

### Controle de acesso por família

- **D-04:** Helper `_require_family_access(family_id: int, current_user: User, session: AsyncSession) -> None` adicionado a `src/caramello/shared/auth.py`. Levanta 403 se `current_user` não for membro da família. Reutilizável para Account, Category, Subcategory (Phase 7) e Movement, FinancialEntry (Phases 8/9).
- **D-05:** Para Account: resolve `family_uuid` → `family_id`, depois chama `_require_family_access(family_id, current_user, session)`.
- **D-06:** Para Category/Subcategory: resolve `family_uuid` → `family_id` da categoria, depois chama `_require_family_access`.

### Schemas de API pública (family_uuid, não family_id)

- **D-07:** IDs internos **nunca** são expostos na API pública. Schemas locais definidos em `operations.py` (não no modelo gerado) usam `family_uuid: UUID` no payload de criação e na resposta.
- **D-08:** `AccountCreatePublic(family_uuid: UUID, name: str, type: Literal[...], currency: str)` — schema de criação público. Backend resolve `family_uuid` → `family_id` antes de persistir.
- **D-09:** `AccountReadPublic` — resposta expõe `uuid`, `family_uuid`, `name`, `type`, `currency`, `is_active`, `created_at`, `updated_at`. Nunca expõe `id` ou `family_id` internos.
- **D-10:** Mesmo padrão para Category e Subcategory: schemas locais com `family_uuid` (Category) e `category_uuid` (Subcategory).

### Validação do campo type de Account

- **D-11:** Campo `type` de `AccountCreatePublic` usa `Literal["corrente", "poupanca", "cartao", "investimento"]`. Validação automática pelo Pydantic — retorna 422 com mensagem clara para valores inválidos. O modelo gerado (`models.py`) mantém `str(max_length=20)` sem alteração.

### API de Subcategoria — rota plana

- **D-12:** Rotas planas para Subcategory:
  - `POST /finances/subcategory` — `SubcategoryCreatePublic(category_uuid: UUID, name: str, ...)` no payload
  - `GET /finances/subcategory?category_uuid=xxx` — query param opcional para filtrar por categoria pai
  - `GET /finances/subcategory/{uuid}` — detalhe por UUID
  - `PATCH /finances/subcategory/{uuid}` — atualização
- **D-13:** `category_uuid` é parâmetro público (UUID). Backend resolve para `category_id` interno. O helper `_require_family_access` é chamado via `category.family_id` após resolver a categoria.

### Claude's Discretion

- Organização dos routers em `operations.py` (um APIRouter por entidade ou router unificado `finances`) — planner decide pela abordagem mais limpa dado o padrão `families/operations.py`.
- Padrão de nomenclatura exato dos schemas locais (ex: `AccountPublicCreate` vs `AccountCreatePublic`) — manter consistência com Pydantic conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos funcionais
- `.planning/ROADMAP.md` §Phase 7 — goal, technical constraints (helper `_require_account_access`, pitfall P7 sobre registro de routers antes do MCP, `selectinload` explícito), success criteria detalhados. **LEITURA OBRIGATÓRIA.**
- `.planning/REQUIREMENTS.md` §Contas (ACC-01/02/03) — requisitos funcionais de Account incluindo `is_active=false` para arquivamento sem perder histórico.
- `.planning/REQUIREMENTS.md` §Categorias (CAT-01/02/03/04) — requisitos de Category/Subcategory. Nota: CAT-03 (máximo 2 níveis) é enforced estruturalmente pelo modelo, não por business logic.
- `.planning/REQUIREMENTS.md` §Autorização (AUTH-FIN-01/02) — 401 sem token, 403 para família alheia.

### Padrões de código existentes
- `src/caramello/families/operations.py` — **referência direta de padrão** para `finances/operations.py`: schemas locais (ex: `FamilyMemberRead`), router com prefix, helpers de acesso, padrão `# CARAMELLO-GENERATED: implemented`. **LER ANTES de implementar.**
- `src/caramello/shared/auth.py` — arquivo a ser estendido com `_require_family_access`. Ver `get_current_user` como referência de estilo.
- `src/caramello/main.py` — registrar routers de finances ANTES de `FastApiMCP(...)` (pitfall P7). Ver comentário sobre ordem de registro.

### Código gerado (referência, não editar)
- `src/caramello/finances/models.py` — modelos gerados; schemas locais em operations.py SOBREPÕEM as classes *Create/*Read para a API pública.
- `src/caramello/finances/router.py` — CRUD gerado; **não registrar em main.py** para Account/Category nesta fase. Mantido no disco como referência.
- `src/caramello/finances/operations.py` — stub atual a ser implementado.

### Migrações e banco
- `alembic/versions/0002_finances_schema.py` — migration Phase 6; define `account.family_id` (FK → `family.id`), `category.family_id` (FK → `family.id`), `subcategory.category_id` (FK → `category.id`). Confirmar FKs antes de implementar os helpers.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `families/operations.py` — padrão completo de como implementar `operations.py` com schemas locais, helper de acesso, e router com prefix. Copiar o estilo diretamente.
- `shared/auth.py:get_current_user` — Depends() que retorna `User`. `_require_family_access` deve seguir mesmo estilo: função async que recebe `session` e levanta `HTTPException(403)`.
- `families/models.py:FamilyMember` — tabela com `family_id + user_id`. Query de membership check: `select(FamilyMember).where(FamilyMember.family_id == X, FamilyMember.user_id == current_user.id)`.

### Established Patterns
- `selectinload` explícito em queries que serializam relacionamentos (pitfall P3 do ROADMAP) — obrigatório ao retornar objetos com relacionamentos.
- UUID público no path/payload, nunca `id` interno — convenção `AccountReadPublic.uuid` não `AccountReadPublic.id`.
- Schemas Read não incluem `id` nem FKs internas; apenas UUIDs públicos e campos de dados.
- `session.execute()` para queries com JOIN (verificação de membership) — não `session.exec()`.

### Integration Points
- `main.py`: adicionar `from caramello.finances import operations as finances_operations` e `app.include_router(finances_operations.router)` ANTES de `mcp.mount_http()`.
- `shared/auth.py`: adicionar `_require_family_access` como função pública (sem underscore se for conveniente) ou privada com export explícito.
- `finances/operations.py`: importar `FamilyMember` de `caramello.families.models` (não o inverso — anti-padrão import circular).

</code_context>

<specifics>
## Specific Ideas

- O helper de acesso foi definido como `_require_family_access(family_id: int, current_user: User, session: AsyncSession) -> None` no ROADMAP (Phase 7 technical constraints). A assinatura exata pode ser ajustada pelo planner, mas o conceito é: recebe `family_id` resolvido + usuário + session, levanta 403 se não for membro.
- `is_active=false` para arquivamento de conta (ACC-03) é um PATCH normal — não um endpoint dedicado de "archive". `AccountUpdatePublic.is_active: bool | None = None`.
- `currency` de Account default `"BRL"` no modelo gerado — manter esse default no schema público.

</specifics>

<deferred>
## Deferred Ideas

- Nenhuma ideia fora do escopo surgiu durante a discussão.

</deferred>

---

*Phase: 7-CRUD Account + Category*
*Context gathered: 2026-05-31*
