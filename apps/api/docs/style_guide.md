# Guia de Estilo Python

## Idioma

Para detalhes completos sobre a estratégia híbrida de idioma (Inglês para Código, Português para Docs), consulte:
📄 [Diretrizes de Idioma](./language_rules.md)

## Convenções de Nomenclatura
- **Pacotes/Módulos:** `snake_case` → `repositories`, `user.py`.
- **Classes:** `PascalCase` → `UserRepository`, `UserService`.
- **Funções/Variáveis:** `snake_case` → `create_user`, `max_retries`.
- **Constantes:** `UPPER_CASE` → `DEFAULT_PAGE_SIZE`.
- **Endpoints:** caminhos em `kebab-case`, funções em `snake_case`.

## Docstrings
- Siga a **PEP 257**:

```python
def create_user(data: UserCreate) -> User:
    """Creates a new user.

    Args:
        data: Validated user input data.

    Returns:
        The persisted User entity.
    """
```

## Estilo e Qualidade do Código
- **Comprimento da linha:** máx. 88 caracteres (Black).
- **Imports:** stdlib / terceiros / local (Ruff organiza).
- **Type hints:** sempre para funções públicas e objetos de domínio (verificado com mypy).
- **Ferramentas:**
  - `ruff` → lint/isort/docstyle
  - `black` → formatação
  - `mypy` → checagem de tipos
  - `pytest` → testes

## Banco de Dados
- Forneça uma `Session` por requisição via dependência (`yield`) em `database/session.py`.
- Configure o Alembic com `target_metadata = SQLModel.metadata` em `env.py`.


### Banco de Dados (SQLModel)
- **Nomes de Tabela:** Use **SINGULAR** e `snake_case` (ex: `user`, `family_member`).
- **Chave Primária (PK):** Todas as entidades devem ter um `id` (int, PK) e um `uuid` (UUID, unique).
    - *Exceção:* Tabelas de associação puras (Link Models) podem ter apenas as chaves estrangeiras compondo a PK.
- **Identificador Público:** Use sempre o `uuid` nas URLs e trocas de mensagens externas.
## API
- `api/v1/routes.py`: monta os routers.
- `api/v1/users.py`: rotas de usuário.
- Use `response_model`, `status_code`, `HTTPException`.

## Repositórios e Serviços
- **Repositório:** apenas acesso a dados.
- **Serviço:** orquestração e regras de negócio.
- Nomenclatura: `UserRepository`, `UserService`.

## Testes
- `tests/` espelha a estrutura do projeto.
- Use fixtures para `Session` de banco de dados isolada.
- Hooks de pré-commit: `ruff`, `black`, `mypy`, `pytest`.
