# Phase 7: CRUD Account + Category - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 7-CRUD Account + Category
**Areas discussed:** Onde fica o acesso por família, Como family_id chega à API, Subcategoria: rota plana vs aninhada

---

## Onde fica o acesso por família

| Option | Description | Selected |
|--------|-------------|----------|
| Implementar em operations.py (padrão families) | operations.py vira o arquivo de business logic com os endpoints reais. router.py é gerado mas não registrado em main.py para Account/Category. Mesmo padrão de families/operations.py. | ✓ |
| Editar router.py gerado (marca como implemented) | Edita o router.py diretamente adicionando o family membership check. Marca como # CARAMELLO-GENERATED: implemented. | |
| Você decide | Deixa o planner/executor escolher a abordagem mais consistente com o codebase atual. | |

**User's choice:** Implementar em operations.py (padrão families)
**Notes:** —

---

| Option | Description | Selected |
|--------|-------------|----------|
| Um router por entidade em operations.py (account_router + category_router) | Dois APIRouter separados no mesmo arquivo. Registrados individualmente em main.py. | |
| Um único router 'finances' para tudo | APIRouter(prefix='/finances') unificado. Mais simples de registrar em main.py. | |
| Você decide | Deixa o planner escolher. | ✓ |

**User's choice:** Você decide
**Notes:** Organização interna delegada ao planner.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Helper único _require_family_access(family_id, current_user, session) | Account e Category usam o mesmo helper. Mais reutilizável para Phases 8 e 9. | ✓ |
| Helper por entidade (_require_account_access + _require_category_access) | Mais explícito, menos acoplamento. Duplica a lógica de JOIN. | |
| Você decide | Deixa o planner escolher. | |

**User's choice:** Helper único _require_family_access
**Notes:** Assinatura `_require_family_access(family_id, current_user, session)`.

---

| Option | Description | Selected |
|--------|-------------|----------|
| finances/operations.py (no próprio arquivo) | Função privada dentro de operations.py. | |
| finances/auth.py (módulo dedicado de auth financeira) | Arquivo separado src/caramello/finances/auth.py. | |
| shared/auth.py (junto com get_current_user) | Extende o shared/auth.py existente. Mais visível para outros domínios. | ✓ |

**User's choice:** shared/auth.py
**Notes:** Junto com `get_current_user`. Mais visível e reutilizável por qualquer domínio futuro.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Manter gerado, mas não registrar em main.py | router.py existe como código gerado sem uso ativo. | ✓ |
| Deletar o router.py gerado | Remove o arquivo. operations.py é a única fonte de verdade. | |
| Registrar router.py para Movement/FinancialEntry apenas | Registrar em main.py apenas os routers que não têm coverage em operations.py nesta fase. | |

**User's choice:** Manter gerado, mas não registrar em main.py
**Notes:** router.py fica como referência e pode ser aproveitado em fases futuras.

---

## Como family_id chega à API

| Option | Description | Selected |
|--------|-------------|----------|
| family_uuid no payload (UUID público) | Cliente passa family_uuid no body. Backend resolve para family_id interno e verifica membership. Suporta usuário em múltiplas famílias. | ✓ |
| Backend resolve automático (first family do usuário) | Sem family_uuid no payload. Backend busca a única família do current_user. Erro se usuário tiver 0 ou 2+ famílias. | |
| family_uuid como query param | POST /finances/accounts?family_uuid=xxx. Não convencional para criação. | |

**User's choice:** family_uuid no payload (UUID público)
**Notes:** —

---

| Option | Description | Selected |
|--------|-------------|----------|
| family_uuid: UUID (apenas o UUID público) | Nunca expor IDs internos na API. Consistente com a convenção do projeto. | ✓ |
| Ambos: family_id e family_uuid | Expõe IDs internos — contra a convenção. | |
| Você decide | Deixa o planner definir. | |

**User's choice:** family_uuid: UUID (apenas o UUID público)
**Notes:** Consistente com a convenção do projeto — uuid nunca id nas respostas.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Schemas locais em operations.py (como FamilyMemberRead em families) | Define AccountCreatePublic + AccountReadPublic em operations.py com family_uuid. Modelo gerado não é tocado. Padrão já usado em families/operations.py. | ✓ |
| Atualizar o YAML e regenerar models.py | Muda account.yaml: family_id → family_uuid. Regenera models.py. | |

**User's choice:** Schemas locais em operations.py
**Notes:** Modelo gerado não é tocado. Schemas públicos definidos em `operations.py`.

---

## Subcategoria: rota plana vs aninhada

| Option | Description | Selected |
|--------|-------------|----------|
| Rota aninhada: POST /finances/category/{uuid}/subcategories | category_uuid no path — sem ambiguidade de qual pai pertence. Mais REST-ful para hierarquias. | |
| Rota plana: POST /finances/subcategory + category_uuid no payload | Mantém o padrão flat do gerador. category_uuid (UUID público) no body de SubcategoryCreate. | ✓ |
| Você decide | Deixa o planner definir. | |

**User's choice:** Rota plana: POST /finances/subcategory + category_uuid no payload
**Notes:** Consistente com o padrão flat do gerador.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Query param: GET /finances/subcategory?category_uuid=xxx | Sem filtro = retorna todas da família. Com category_uuid = filtra por pai. | ✓ |
| Rota aninhada apenas para GET: GET /finances/category/{uuid}/subcategories | Inconsistência entre criação (flat) e leitura (aninhada). | |

**User's choice:** Query param: GET /finances/subcategory?category_uuid=xxx
**Notes:** —

---

| Option | Description | Selected |
|--------|-------------|----------|
| Literal no schema local (Literal['corrente', 'poupanca', 'cartao', 'investimento']) | Validação automática pelo Pydantic. Retorna 422 para valores inválidos. Modelo gerado não muda. | ✓ |
| String livre (sem validação no backend) | Frontend valida. Backend aceita qualquer string <= 20 chars. | |
| Você decide | Deixa o planner definir. | |

**User's choice:** Literal no schema local
**Notes:** `Literal["corrente", "poupanca", "cartao", "investimento"]` em `AccountCreatePublic`.

---

## Claude's Discretion

- Organização interna dos routers em `operations.py` (um router por entidade vs. router unificado `finances`)
- Nomenclatura exata dos schemas locais (ex: `AccountPublicCreate` vs `AccountCreatePublic`)

## Deferred Ideas

Nenhuma ideia fora do escopo surgiu durante a discussão.
