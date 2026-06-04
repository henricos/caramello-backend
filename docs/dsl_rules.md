# Regras para Criação de DSL (Caramello API)

Este documento define as regras estritas para criação e manutenção dos arquivos de definição em `dsl/`. Aplica-se a entidades (`dsl/entities/*.yaml`) e a operações de negócio (`dsl/operations/{domain}.yaml`). Estas regras devem ser seguidas por Agentes de IA e Desenvolvedores para garantir a geração correta de código.

## 1. Nomenclatura

*   **Arquivos**: Snake case (ex: `user_profile.yaml`).
*   **Entidade (`name`)**: PascalCase, singular (ex: `UserProfile`).
*   **Tabela (`table_name`)**: Snake case, **SINGULAR** (ex: `user_profile`, `family`).
    *   *Motivo*: Padronização e simplicidade em queries SQL.

## 2. Estrutura Obrigatória da Entidade

Todas as entidades (exceto tabelas de associação puras) devem conter os seguintes campos padrão:

1.  **Chave Primária Interna**:
    ```yaml
    - name: id
      type: int
      primary_key: true
      description: "Internal primary key (numeric)."
    ```
2.  **Identificador Público**:
    ```yaml
    - name: uuid
      type: UUID
      unique: true
      default_factory: uuid4
      nullable: false
      description: "Unique public identifier (UUID)."
    ```

## 3. Tipagem de Campos

Use tipos Python modernos e "lowercased" sempre que possível, exceto para classes especiais.

*   ✅ `str`, `int`, `bool`, `float`
*   ✅ `list[T]` (Python 3.10+ style)
*   ✅ `UUID` (do módulo uuid), `datetime` (do módulo datetime), `EmailStr` (do Pydantic)
*   ❌ `String`, `Integer`, `List[T]` (Typing module style antigo)

## 4. Tabelas de Associação (Link Models)

Entidades que servem apenas para conectar duas outras (Many-to-Many) devem ter a flag `is_link_model: true`.
*   Elas **NÃO** precisam de `id` ou `uuid`.
*   Devem ter duas chaves primárias compostas (Foreign Keys).

## 5. Relacionamentos

*   Use `list[EntityName]` para relacionamentos "para muitos".
*   Sempre defina `back_populates` para garantir navegação bidirecional no ORM.
*   Para Many-to-Many, especifique `link_model`.

---

## Parte II — Operações de Negócio (`dsl/operations/{domain}.yaml`)

### 6. Regra fundamental: DSL sempre primeiro

**Nunca escreva um endpoint em `{domain}/operations.py` sem antes declarar a operação no DSL.**

O arquivo `operations.py` pode estar marcado como `# CARAMELLO-GENERATED: implemented` (o gerador o pula para proteger implementações). Isso **não** é licença para adicionar rotas diretamente — é apenas proteção para implementações já declaradas no DSL.

### 7. Estrutura do arquivo de operações

```yaml
domain: finances          # deve ser um dos domínios registrados em DOMAIN_TO_ENTITY_NAME
operations:
  - name: create_account  # snake_case — vira nome da função Python
    method: POST          # GET | POST | PATCH | DELETE | PUT
    path: /finances/accounts   # sempre começa com /{domain}/
    description: "..."    # aparece como docstring no stub gerado
```

### 8. Fluxo obrigatório para novos endpoints

1. **Declare** a operação em `dsl/operations/{domain}.yaml`
2. **Gere** o stub: `bin/generate_code` (só gera se o arquivo não existir ou for `stub`)
3. **Implemente** o stub substituindo `raise NotImplementedError`
4. Ao finalizar, troque a anotação de `# CARAMELLO-GENERATED: stub` para `# CARAMELLO-GENERATED: implemented`

### 9. Caminhos das rotas

- Sempre use o prefixo do domínio: `/finances/accounts`, `/families/families/{uuid}`
- O gerador remove o prefixo automaticamente para o decorator do router
- Use `{snake_case_uuid}` para path params (ex: `{account_uuid}`, `{family_uuid}`)

### 10. Anti-padrões proibidos

- ❌ Adicionar `@router.get(...)` em `operations.py` sem entrada no DSL
- ❌ Criar `operations.py` do zero sem passar pelo gerador
- ❌ Editar o path do decorator sem atualizar o DSL

---

## Parte I — Entidades (`dsl/entities/*.yaml`)

## Exemplo Completo (entidade)

```yaml
name: User
description: Represents a system user.
table_name: user  # Singular

fields:
  - name: id
    type: int
    primary_key: true
  - name: uuid
    type: UUID
    unique: true
    default_factory: uuid4
    nullable: false
  - name: tags
    type: list[str] # Lowercase generic
    nullable: true

relationships:
  - name: posts
    type: list[Post]
    back_populates: author
```
