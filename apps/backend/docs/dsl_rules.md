# Regras para Criação de DSL (Caramello API)

Este documento define as regras estritas para criação e manutenção dos arquivos de definição em `dsl/`. Aplica-se a entidades (`dsl/entities/*.yaml`) e a operações de negócio (`dsl/operations/{domain}.yaml`). Estas regras devem ser seguidas por Agentes de IA e Desenvolvedores para garantir a geração correta de código.

---

## Parte I — Entidades (`dsl/entities/*.yaml`)

### 1. Nomenclatura

- **Arquivos**: snake_case (ex: `user_profile.yaml`).
- **Entidade (`name`)**: PascalCase, singular (ex: `UserProfile`).
- **Tabela (`table_name`)**: snake_case, **SINGULAR** (ex: `user_profile`, `family`).

### 2. Estrutura Obrigatória

Todas as entidades (exceto link models) devem conter os campos padrão:

```yaml
- name: id
  type: int
  primary_key: true
  description: "Internal primary key (numeric)."

- name: uuid
  type: UUID
  unique: true
  default_factory: uuid4
  nullable: false
  description: "Unique public identifier (UUID)."
```

### 3. Tipagem de Campos

Use tipos Python modernos (lowercase):

- ✅ `str`, `int`, `bool`, `float`, `Decimal`
- ✅ `list[T]` (Python 3.10+ style)
- ✅ `UUID`, `datetime`, `EmailStr`
- ❌ `String`, `Integer`, `List[T]` (typing module antigo)

### 4. Chaves Estrangeiras e Exposição Pública

FK int columns nunca devem vazar para schemas públicos de API. Use o flag `expose_as_uuid: true` para substituir o campo FK (`_id`) por um campo UUID (`_uuid`) nos schemas Read, Create e Update, mantendo o FK na tabela.

```yaml
- name: responsible_user_id
  type: int
  foreign_key: "user.id"
  nullable: true
  expose_as_uuid: true          # tabela: responsible_user_id (int)
  description: "..."            # schemas: responsible_user_uuid (UUID | None)
```

**O que o gerador produz:**

| Classe | Campo gerado |
|--------|-------------|
| `Entity` (table) | `responsible_user_id: int \| None = Field(foreign_key="user.id", ...)` |
| `EntityRead` | `responsible_user_uuid: UUID \| None = None` |
| `EntityCreate` | `responsible_user_uuid: UUID \| None = None` |
| `EntityUpdate` | `responsible_user_uuid: UUID \| None = None` |

> **Regra:** qualquer FK que seja opcional ou que aponte para `user` deve usar `expose_as_uuid: true`. FKs obrigatórios de estrutura interna (ex: `movement_id` em `FinancialEntry`) podem ficar sem o flag quando não forem expostos diretamente nos schemas públicos de negócio.

### 5. Tabelas de Associação (Link Models)

Entidades M:M com `is_link_model: true`:
- **Não** precisam de `id` ou `uuid`
- Têm duas chaves primárias compostas (FKs)

### 6. Relacionamentos

- Use `list[EntityName]` para "para muitos"
- Sempre defina `back_populates` para navegação bidirecional
- Para M:M, especifique `link_model`

### 7. Filtros e Índices

Declare índices via `filters:` — nunca adicione `Index(...)` manualmente em `models.py`:

```yaml
filters:
  - fields: [competencia_year, competencia_month]
  - fields: [subcategory_id]
```

### 8. Exemplo completo de entidade

```yaml
name: FinancialEntry
domain: finances
table_name: financial_entry

fields:
  - name: id
    type: int
    primary_key: true
  - name: uuid
    type: UUID
    unique: true
    default_factory: uuid4
    nullable: false
  - name: movement_id
    type: int
    foreign_key: "movement.id"
    unique: true
    nullable: false
  - name: responsible_user_id
    type: int
    foreign_key: "user.id"
    nullable: true
    expose_as_uuid: true
  - name: notes
    type: str
    max_length: 500
    nullable: true

filters:
  - fields: [competencia_year, competencia_month]
```

---

## Parte II — Operações de Negócio (`dsl/operations/{domain}.yaml`)

### 9. Regra fundamental: DSL sempre primeiro

**Nunca escreva um endpoint em `{domain}/operations.py` sem antes declarar a operação no DSL.**

O arquivo `operations.py` pode estar marcado como `# CARAMELLO-GENERATED: implemented` (o gerador o pula para proteger implementações). Isso **não** é licença para adicionar rotas diretamente — é apenas proteção para implementações já declaradas no DSL.

### 10. Estrutura do arquivo de operações

```yaml
domain: finances          # deve ser um dos domínios em DOMAIN_TO_ENTITY_NAME
operations:
  - name: create_account  # snake_case — vira nome da função Python
    method: POST          # GET | POST | PATCH | DELETE | PUT
    path: /finances/accounts   # sempre começa com /{domain}/
    description: "..."    # aparece como docstring no stub gerado
```

### 11. Fluxo obrigatório para novos endpoints

1. **Declare** a operação em `dsl/operations/{domain}.yaml`
2. **Gere** o stub: `bin/generate_code` (só gera se o arquivo não existir ou for `stub`)
3. **Implemente** o stub substituindo `raise NotImplementedError`
4. Ao finalizar, troque `# CARAMELLO-GENERATED: stub` por `# CARAMELLO-GENERATED: implemented`

### 12. Caminhos das rotas

- Sempre use o prefixo do domínio: `/finances/accounts`, `/families/families/{uuid}`
- O gerador remove o prefixo automaticamente para o decorator do router
- Use `{snake_case_uuid}` para path params (ex: `{account_uuid}`, `{family_uuid}`)

### 13. Anti-padrões proibidos

- ❌ Adicionar `@router.get(...)` em `operations.py` sem entrada no DSL
- ❌ Criar `operations.py` do zero sem passar pelo gerador
- ❌ Editar o path do decorator sem atualizar o DSL
- ❌ Adicionar campo FK int (ex: `user_id`) em schema público sem `expose_as_uuid: true`
- ❌ Editar `models.py` manualmente após geração — toda correção volta ao YAML
