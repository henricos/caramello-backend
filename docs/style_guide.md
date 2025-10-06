# Guia de Estilo Python

## Idioma (Código-Fonte)

Em conformidade com as diretrizes gerais de idioma do projeto (detalhadas em `AGENTS.md`), todo o código-fonte e artefatos diretamente relacionados devem ser escritos em **Inglês (English)**. Isso garante consistência com o ecossistema de desenvolvimento, ferramentas e bibliotecas.

-   **Código-Fonte**: Inclui identificadores, nomes de arquivos, diretórios, variáveis, funções, classes, módulos e pacotes.
-   **Comentários e Docstrings**: Devem ser escritos em inglês para manter a coesão com o código que descrevem.
-   **Termos de Domínio Específicos**: Termos inerentes ao contexto brasileiro (ex: `CPF`, `CNPJ`, `PIX`) são permitidos, mas devem ser adaptados ao estilo `snake_case` em inglês (ex: `cpf_validator`, `handle_pix_webhook`).

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


### Chaves Primárias e Identificadores Públicos
- **Chave Primária (PK):** Todas as tabelas devem ter uma chave primária interna do tipo `integer` autoincrementada, chamada `id`. Esta chave deve ser usada para relacionamentos (joins) entre tabelas.
- **Identificador Público:** Todas as tabelas devem ter uma coluna `uuid` do tipo `UUID`, com um valor padrão gerado e um índice `unique`. Este campo deve ser usado como o identificador público do recurso em todas as APIs externas, para evitar a exposição de IDs sequenciais.
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
