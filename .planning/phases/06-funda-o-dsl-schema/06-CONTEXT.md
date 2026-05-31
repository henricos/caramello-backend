# Phase 6: Fundação DSL + Schema - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Criar os YAMLs DSL do domínio financeiro, estender o gerador para suportar tipos e constraints novas, gerar o código base em `src/caramello/finances/` e aplicar a migration `0002` com o schema financeiro completo no banco.

**Entregáveis concretos:**
- 5 YAMLs em `dsl/entities/`: `account.yaml`, `movement.yaml`, `financial_entry.yaml`, `category.yaml`, `subcategory.yaml` (todos com `domain: finances`)
- Gerador estendido com: tipo `Decimal` → `Numeric(15,2)`, bloco `filters:` → `Index` no banco
- Código gerado em `src/caramello/finances/`: `models.py`, `router.py`, `operations.py` (stub)
- `naming_convention` adicionada em `alembic/env.py` antes da migration
- Migration `0002_finances_schema.py` com todas as constraints e índices

**Fora de escopo desta fase:**
- Lógica de negócio (operations/services das contas, categorias) — Phase 7
- Endpoints REST funcionais — Phase 7+
- Lógica de importação e deduplicação — Phase 8
- Conciliação e relatórios — Phase 9

**Nota sobre desvio do ROADMAP:** O ROADMAP original previa 4 entidades (`category.yaml` self-referencial). Esta fase usa **5 entidades**: `category.yaml` (pai) + `subcategory.yaml` (filha com FK para Category). Isso elimina o self-referencial e o pós-processamento manual. O planner deve atualizar `REQUIREMENTS.md` para refletir que CAT-01/02/03/04 mapeiam para duas entidades separadas.

</domain>

<decisions>
## Implementation Decisions

### Tipo Monetário no DSL

- **D-01:** Adicionar `Decimal` como tipo nativo no gerador (`scripts/generate_code.py`, função `map_type_to_python`). `Decimal` no YAML gera: anotação Python `Decimal`, coluna SA `sa_column(Column(Numeric(15, 2)))`. Precisão `NUMERIC(15,2)` fixo — sem parâmetros configuráveis no YAML.
- **D-02:** Nenhum campo monetário pode usar `float` no YAML. Todo campo de valor financeiro (`amount`, e similares futuros) usa `Decimal`.
- **D-03:** O import `from decimal import Decimal` deve ser adicionado ao cabeçalho dos `models.py` gerados quando ao menos um campo `Decimal` estiver presente.

### Competência em FinancialEntry

- **D-04:** Período contábil representado como **dois campos inteiros separados**: `competencia_year: int` e `competencia_month: int` (1-12). Razão: alinhado com o ROADMAP (índices em `competencia_year/month`), queries explícitas (`WHERE year=X AND month=Y`), e intuitivo para consumidores da API.
- **D-05:** `FinancialEntry` **não tem campo de valor próprio** — herda `amount` e `type` (crédito/débito) da `Movement` via relação. `FinancialEntry` armazena apenas metadados de classificação: `subcategory_id`, `competencia_year`, `competencia_month`, `notes`, `is_recorrente`.

### Hierarquia de Categorias — Duas Entidades Separadas

- **D-06:** Hierarquia de categorias implementada com **duas entidades distintas**:
  - `Category` — categoria pai (nível 1, ex: "Transporte"). Scoped por família via `family_id`.
  - `Subcategory` — subcategoria (nível 2, ex: "Gasolina"). FK obrigatória `category_id → Category.id`.
- **D-07:** Essa abordagem elimina a relação self-referencial em `category.yaml` e todo o pós-processamento manual de `models.py`. O gerador não precisa de suporte a `self_referential`.
- **D-08:** `FinancialEntry.subcategory_id` referencia `Subcategory` (não `Category`). Relatórios de Phase 9 agrupam por `Subcategory.category_id` para obter o nível pai.
- **D-09:** CAT-03 (rejeitar subcategoria filha de subcategoria — máximo 2 níveis) torna-se uma restrição estrutural do modelo: `Subcategory` simplesmente não tem campo para apontar para outra `Subcategory`. A validação é enforced pelo schema, não por business logic.

### Constraints e Filtros no DSL

- **D-10:** Constraints de coluna única (`import_hash`, `movement_id` em FinancialEntry) declaradas como `unique: true` no campo — comportamento já suportado pelo DSL.
- **D-11:** Novo bloco `filters:` nos YAMLs para declarar filtros naturais da entidade (gera `Index` no banco, documenta query params aceitos na API, sinaliza filtros exibíveis na UI). Sintaxe:
  ```yaml
  filters:
    - fields: [account_id]
    - fields: [competencia_year, competencia_month]
  ```
  O gerador emite `Index('ix_{table}_{fields}', '{field1}', '{field2}')` em `__table_args__`.
- **D-12:** `unique_together:` (para unique composto de múltiplas colunas) **deferido** — nenhum caso de uso no Phase 6. Implementar quando surgir o primeiro caso real.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap e Requisitos
- `.planning/ROADMAP.md` §Phase 6 — constraints técnicas detalhadas, pitfalls (P6), success criteria. **LEITURA OBRIGATÓRIA** — contém especificação precisa da migration 0002.
- `.planning/REQUIREMENTS.md` §Categorias (CAT-01/02/03/04) — requisitos funcionais de categorias. **Nota:** os nomes das entidades mudaram de `Category` (self-referencial) para `Category + Subcategory`; planner deve alinhar.

### DSL e Gerador
- `docs/dsl_rules.md` — regras estritas de nomenclatura e estrutura dos YAMLs. Seguir para os 5 novos YAMLs.
- `scripts/generate_code.py` — gerador atual a ser estendido. Funções-chave: `map_type_to_python`, `generate_models`, e a função nova a ser criada para `filters:` → `__table_args__`.
- `dsl/entities/family.yaml` — exemplo de referência para estrutura de YAML existente (campos padrão id, uuid, timestamps, domain, relationships).
- `dsl/manifest.yaml` — registrar os 5 novos YAMLs aqui após criar.

### Database e Migrations
- `alembic/env.py` — adicionar `naming_convention` ANTES de gerar a migration 0002. Ver ROADMAP §Phase 6 constraint sobre isso.
- `alembic/versions/0001_initial_schema.py` — verificar `revision` para definir `down_revision` correto da migration 0002.
- `.planning/REQUIREMENTS.md` §Requisitos Técnicos — `NUMERIC(15,2)`, deduplicação via `import_hash` SHA-256, `Decimal` no Python.

### Padrões de Código
- `src/caramello/families/models.py` — modelo de referência para a estrutura gerada atual (como relationships são declarados, padrão de campos padrão).
- `src/caramello/families/operations.py` — padrão de stub `# CARAMELLO-GENERATED: stub/implemented` que deve ser gerado para finances.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/generate_code.py` — gerador existente com `map_type_to_python`, `DOMAIN_TO_ENTITY_NAME`. Esta fase o estende; não reescreve do zero.
- `dsl/entities/*.yaml` — 4 YAMLs existentes como referência de estrutura, especialmente `family.yaml` (tem relationships) e `family_member.yaml` (link model).
- `alembic/versions/0001_initial_schema.py` — migration existente como referência de estilo e para obter o `revision` correto para `down_revision`.

### Established Patterns
- Geração por domínio: `domain: families` → código em `src/caramello/families/`. Os 5 YAMLs financeiros usam `domain: finances` → código em `src/caramello/finances/`.
- `DOMAIN_TO_ENTITY_NAME` dict em `generate_code.py` precisa de 5 novas entradas: `"finances"` e os 5 nomes canônicos.
- Estrutura de modelo gerado: 4 classes por entidade (`Entity`, `EntityRead`, `EntityCreate`, `EntityUpdate`).
- Stubs de operations: `# CARAMELLO-GENERATED: stub` → implementado em Phase 7+ com `# CARAMELLO-GENERATED: implemented`.

### Integration Points
- `alembic/env.py` — importar os 5 novos models de `caramello.finances.models` para o autogenerate do Alembic funcionar.
- `src/caramello/main.py` — registrar os routers gerados de finances após a fase (ou deixar para Phase 7 quando os routers tiverem lógica real).
- `naming_convention` no `MetaData` do Alembic deve estar configurado ANTES da migration 0002 para que constraints geradas sigam o padrão de nomenclatura.

</code_context>

<specifics>
## Specific Ideas

- O usuário sugeriu proativamente substituir a entidade self-referencial `Category` por duas entidades separadas (`Category` + `Subcategory`) — simplifica o gerador e elimina pós-processamento.
- O conceito de `filters:` no DSL foi definido como **abstrato** (não é "Index" que é conceito de banco): representa "este campo é um filtro natural da entidade" — válido para API query params e UI filtering além do índice de banco.
- `unique_together:` deferido explicitamente — não implementar nesta fase mesmo que pareça útil adicionar "de graça" junto com `filters:`.

</specifics>

<deferred>
## Deferred Ideas

- **`unique_together:` no DSL** — suporte a UniqueConstraint composta de múltiplas colunas. Deferido: nenhum caso de uso no Phase 6. Implementar no milestone/fase em que surgir o primeiro caso real.
- **`filters:` como base para query params automáticos na API** — o planner/executor de Phase 7+ pode usar o bloco `filters:` para gerar automaticamente os query params aceitos no router. Não implementar agora.
- **Registrar routers financeiros em `main.py`** — pode ser deixado para Phase 7 (quando os operations tiverem lógica real), ou feito no final desta fase. Decisão para o planner.

</deferred>

---

*Phase: 6-Fundação DSL + Schema*
*Context gathered: 2026-05-31*
