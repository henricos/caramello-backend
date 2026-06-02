# Phase 8: Movimentações + Importação - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementar o registro individual de movimentações financeiras e a importação em lote via CSV, OFX e XLSX — com deduplicação inteligente (nunca inserir duplicatas silenciosamente) e listagem básica para verificação.

**Entregáveis concretos:**
- `src/caramello/finances/operations.py` estendido com endpoints de Movement
- `src/caramello/finances/services.py` implementado com `import_movements()` e parsers
- Schema Movement revisado: `amount` com sinal (positivo=crédito, negativo=débito), campo `type` removido, campo `is_duplicate` removido
- Nova migration para alteração do schema `movement`
- `dsl/entities/movement.yaml` atualizado e código regenerado

**Endpoints desta fase:**
- `POST /finances/accounts/{uuid}/movements` — registro individual (MOV-01)
- `POST /finances/accounts/{uuid}/movements/import?format=csv|ofx|xlsx` — importação em lote (MOV-02/03/04)
- `POST /finances/accounts/{uuid}/movements/import/confirm` — confirmação de duplicatas suspeitas
- `GET /finances/accounts/{uuid}/movements` — listagem com paginação (adicionado para UX/verificação)

**Fora de escopo desta fase:**
- Conciliação de movimentações em lançamentos financeiros (Phase 9)
- Saldo de conta (Phase 9 — derivado de movimentações)
- Filtros avançados além de `date_from/date_to` (Phase 9)
- `FinancialEntry` e relatórios analíticos (Phase 9)

</domain>

<decisions>
## Implementation Decisions

### Schema Movement — mudanças em relação ao modelo gerado na Phase 6

- **D-01: `amount` com sinal** — Positivo = crédito, negativo = débito. Remover campo `type: str` do `dsl/entities/movement.yaml`. Migration: `ALTER TABLE movement DROP COLUMN type`. Benefício: `SUM(amount)` para saldo sem `CASE WHEN`; hash sem `type` é suficiente pois `-100 ≠ +100`.
- **D-02: Remover `is_duplicate`** — Campo `is_duplicate: bool` removido do DSL YAML e da migration. Razão: com a nova estratégia de deduplicação, duplicatas suspeitas nunca são inseridas — são retornadas para confirmação do usuário. Sem registros duplicados no banco, o campo não tem razão de existir.
- **D-03: Impacto em migration** — A migration de Phase 8 deve: (1) DROP COLUMN `type`, (2) DROP COLUMN `is_duplicate`, (3) confirmar que `NUMERIC(15,2)` aceita valores negativos (já aceita). Verificar `down_revision` com `alembic history --verbose` após gerar (pitfall P6 do STATE.md).

### Deduplicação — redesign em relação ao ROADMAP original

- **D-04: OFX com FITID = deduplicação definitiva** — `ofxparse` expõe `transaction.id` (FITID). Se presente, usar como `import_hash`. Hash match de FITID existente = duplicata certa. Não inserir, não perguntar.
- **D-05: CSV/XLSX sem ID bancário = duplicata suspeita** — Hash SHA-256 de `(account_id|date|amount|description_normalizada)`. Se hash já existe no banco → movimento é "suspected duplicate". **Não inserir.** Retornar em `potential_duplicates[]` para confirmação do usuário.
- **D-06: Normalização conservadora de description** — `description.strip().lower()` + colapsar espaços múltiplos (ex: `"  PIX RECEBIDO  "` → `"pix recebido"`). Sem remoção de números ou pontuação — manter simples.
- **D-07: Hash de `(account_id|date|amount|description_normalizada)`** — Sem campo `type` (removido). `amount` com sinal já diferencia crédito/débito.
- **D-08: Endpoint de confirmação** — `POST /finances/accounts/{uuid}/movements/import/confirm` recebe lista de `potential_duplicates` que o usuário confirmou como não-duplicatas. Insere-os normalmente. Permite que dois pagamentos idênticos no mesmo dia sejam registrados quando o usuário confirmar que são movimentações distintas.

### Importação — formato e parsing

- **D-09: Detecção de formato por query param** — `POST /import?format=csv|ofx|xlsx`. Explícito, sem ambiguidade de MIME type.
- **D-10: Auto-detect separador CSV** — Usar `csv.Sniffer` antes de parsear. Cobre `;` (padrão bancos BR) e `,` (padrão internacional) automaticamente.
- **D-11: Colunas obrigatórias no CSV** — Header na primeira linha com `date`, `amount`, `description` (case-insensitive). Ordem das colunas pelo header, não por posição.
- **D-12: Formatos de data aceitos** — `YYYY-MM-DD` (ISO 8601) e `DD/MM/YYYY` (extratos BR). Tentar ISO primeiro; fallback para formato BR. Retornar erro de linha se nenhum formato funcionar.
- **D-13: Linhas inválidas não abortam o lote** — Linhas com data inválida ou amount não-numérico são puladas. Reportadas em `error_lines: [{line_number, reason}]`. Limiar de segurança: se > 50% das linhas falharem, abortar e retornar 422.

### Resposta da importação

- **D-14: Shape da resposta de importação:**
  ```json
  {
    "inserted": 12,
    "duplicates_skipped": 3,
    "potential_duplicates": [
      {
        "new_row": {"date": "2026-01-15", "amount": "-100.00", "description": "pix fulano"},
        "existing_movement_uuid": "abc-123",
        "hash": "sha256..."
      }
    ],
    "error_lines": [
      {"line_number": 5, "reason": "amount inválido: 'R$ 100,00'"}
    ],
    "movements": [
      {"uuid": "...", "date": "...", "amount": "...", "description": "...", "created_at": "..."}
    ]
  }
  ```
  `movements[]` contém as movimentações inseridas com sucesso (para display imediato sem GET extra).

### Listagem de movimentações (adicionado)

- **D-15: GET incluído nesta fase** — `GET /finances/accounts/{uuid}/movements?limit=50&offset=0&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`. Necessário para verificar o que foi importado. Paginação por `limit/offset`.
- **D-16: MovementReadPublic** — Expõe: `uuid`, `date`, `amount` (Decimal como string), `description`, `import_hash` (opcional, para debug), `created_at`, `updated_at`. Sem `account_uuid` na resposta (já está na URL), sem `id` interno.

### Registro individual

- **D-17: POST individual — deduplicação aplicada** — `POST /finances/accounts/{uuid}/movements` com `{date, amount, description}`. Hash calculado. Se hash match com existing → retorna 409 com o UUID da movimentação existente. (Registro individual é intencional; o usuário pode usar endpoint de confirmação se quiser inserir mesmo assim.)

### Claude's Discretion

- Estrutura dos parsers: um arquivo `finances/parsers/` separado ou funções em `finances/services.py` — planner decide pela abordagem mais limpa.
- Tratamento de encoding OFX: `ofxparse` cuida, mas testar com extrato real de banco BR (gap identificado no STATE.md).
- Limiar de 50% de erros antes de abortar: planner pode ajustar com base no custo de rollback parcial.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos funcionais
- `.planning/ROADMAP.md` §Phase 8 — goal, technical constraints (import_movements signature, parsers, pitfall P4 on_conflict_do_nothing, pitfall P1 Decimal), success criteria. **LEITURA OBRIGATÓRIA.**
- `.planning/REQUIREMENTS.md` §Movimentações (MOV-01/02/03/04/05) — requisitos originais. Notar que MOV-04/05 foram redesenhados: `is_duplicate=true` substituído por `potential_duplicates[]` para confirmação.
- `.planning/REQUIREMENTS.md` §Autorização (AUTH-FIN-01/02) — 401 sem token, 403 para família alheia (já implementado, reutilizar `_require_family_access`).

### Schema e migration
- `dsl/entities/movement.yaml` — **EDITAR antes de regenerar**: remover campo `type`, remover campo `is_duplicate`, manter `amount` como Decimal (NUMERIC(15,2)). Ver D-01/D-02.
- `alembic/versions/0002_finances_schema.py` — Migration existente da Phase 6; a nova migration de Phase 8 deve ter `down_revision` apontando para ela. Usar `alembic history --verbose` para verificar (pitfall P6).
- `src/caramello/finances/models.py` — Código gerado; será sobrescrito após editar movement.yaml e regenerar.

### Padrões de código existentes
- `src/caramello/finances/operations.py` — **Referência direta de padrão** para os novos endpoints de Movement. Schemas locais (MovementCreatePublic, MovementReadPublic), router com prefix `/finances`, helpers de acesso. **LER ANTES de implementar.**
- `src/caramello/shared/auth.py:_require_family_access` — Já implementado. Reutilizar para todos os endpoints de Movement.
- `src/caramello/families/operations.py:FamilyMember` — Padrão de membership check com `session.execute()`.

### Bibliotecas e dependências
- `ofxparse` — Parser OFX. Acessar `transaction.id` (FITID) para dedup definitiva. Testar com extrato real de banco BR (gap no STATE.md).
- `openpyxl` — Parser XLSX com `read_only=True` (constraint do ROADMAP para eficiência de memória).
- `python-multipart` — Necessário para `UploadFile` via FastAPI. Verificar se já está em `pyproject.toml`.

### Integração com main.py
- `src/caramello/main.py` — Novos endpoints de Movement são adicionados ao mesmo `router` de `finances/operations.py` já registrado. Verificar que o router ainda está registrado ANTES de `FastApiMCP(...)` (pitfall P7).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `finances/operations.py:router` — Mesmo `APIRouter(prefix="/finances", tags=["Finances"])`. Todos os endpoints de Movement são adicionados a este router existente. Não criar router separado.
- `shared/auth.py:_require_family_access(family_id, current_user, session)` — Já implementado e testado. Para Movement: resolver `account_uuid` → `account` → `account.family_id`, depois chamar `_require_family_access`.
- `finances/models.py:Account` — `account.family_id` disponível após resolução de `account_uuid`. Padrão: `session.execute(select(Account).where(Account.uuid == account_uuid)).scalar_one_or_none()`.

### Established Patterns
- `session.execute()` para queries com filtros e agregações — não `session.exec()` (pitfall P3).
- UUID público no path (`/accounts/{uuid}/movements`), nunca `id` interno.
- `Decimal` em todos os campos de valor monetário — zero `float` (pitfall P1).
- `from __future__ import annotations` no topo de cada arquivo de operations.
- Schemas públicos definidos localmente em `operations.py` — não reutilizar os schemas gerados em `models.py` que expõem `id` internos.

### Integration Points
- `finances/operations.py` é o único arquivo a editar para adicionar os endpoints. `router.py` gerado **não** é registrado (D-02 da Phase 7 context).
- `finances/services.py` (stub atual) recebe a função `import_movements()` — lógica de parsing e deduplicação vive aqui, fora dos routers.
- `main.py`: sem alteração necessária se o router já está registrado. Confirmar antes de adicionar `include_router` duplicado.

</code_context>

<specifics>
## Specific Ideas

- **Amount com sinal como convenção**: quantidade negativa = saída de dinheiro (débito), positiva = entrada (crédito). Isso simplifica todos os cálculos de saldo em Phase 9 para um simples `SUM(amount)` sem `CASE WHEN type=...`.
- **Fluxo de confirmação de duplicatas**: o frontend recebe `potential_duplicates[]` após importação e exibe para o usuário revisar. O endpoint `POST /import/confirm` aceita a lista inteira de UUIDs de hash que o usuário confirmou como não-duplicatas, e os insere atomicamente.
- **Encoding OFX de bancos BR**: o `ofxparse` pode ter problemas com encoding ISO-8859-1 de alguns bancos. Tratar `UnicodeDecodeError` no parser OFX (gap identificado em STATE.md §Pending Todos).
- **Hash `import_hash` mantido no banco** — útil para debug e para o endpoint de confirmação identificar qual hash está sendo confirmado. Exposto em `MovementReadPublic.import_hash` (opcional, pode ser `None` para movimentações criadas individualmente sem hash).

</specifics>

<deferred>
## Deferred Ideas

- **Filtros avançados em GET /movements** (por tipo positivo/negativo, por valor mínimo/máximo) — Phase 9 junto com relatórios.
- **Soft delete de movimentação** — usuário pode querer remover uma importação errada. Deixar para depois que o padrão de `is_active` de Account for validado.
- **Importação com preview antes de confirmar** — retornar o que seria inserido sem persistir, para aprovação total antes de efetivar. Mais poderoso mas mais complexo; a abordagem de `potential_duplicates[]` cobre o caso mais comum.

</deferred>

---

*Phase: 8-Movimentações + Importação*
*Context gathered: 2026-06-02*
