# Guia de Estilo Python

## Idioma (Código-Fonte)

Para manter a consistência com o ecossistema de desenvolvimento (bibliotecas, frameworks, etc.), todo o código-fonte e seus artefatos diretos devem ser escritos em **Inglês (English)**.

- **Código-Fonte**: Identificadores, funções, classes, variáveis, módulos e pacotes.
- **Termos de Domínio**: Termos específicos do Brasil (como `CPF`, `CNPJ`) são permitidos, mas devem ser adaptados ao estilo `snake_case` em inglês (ex: `cpf_validator`, `handle_pix_webhook`).
- **Comentários e Docstrings**: Devem ser escritos em inglês para acompanhar o código ao qual se referem.

As diretrizes gerais sobre o uso de idiomas no projeto (commits, PRs, documentação) estão definidas no arquivo `AGENTS.md`.

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
