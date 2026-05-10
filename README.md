# Caramello API

Serviços backend para o sistema pessoal de organização familiar Caramello.

## Índice

- [Sobre](#sobre)
- [Funcionalidades](#funcionalidades)
- [Instalação](#instalação)
- [Uso](#uso)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Tecnologias](#tecnologias)
- [Contribuição](#contribuição)
- [Licença](#licença)
- [Links Relacionados](#links-relacionados)
- [Contato](#contato)

## Sobre

O Caramello é um sistema pessoal e integrado para organização familiar. Este repositório contém os serviços backend (a API) escritos em Python, que servem como a base para todas as aplicações do ecossistema Caramello (web e mobile).

O objetivo do projeto é centralizar diversas ferramentas de uso individual e compartilhado, como agenda, finanças, listas de compras, saúde e entretenimento, para simplificar a gestão do dia a dia da família.

Para uma descrição detalhada da visão e de todas as funcionalidades planejadas, consulte o documento [Visão do Projeto](./docs/project_vision.md).

## Funcionalidades

O Caramello visa oferecer um conjunto diversificado de ferramentas para a gestão familiar. Algumas das principais funcionalidades planejadas incluem:

-   **Agenda Familiar**: Compromissos individuais e compartilhados.
-   **Gestão de Compras**: Lista de compras colaborativa em tempo real.
-   **Controle de Despensa**: Inventário de itens domésticos.
-   **Entretenimento**: Listas de filmes, séries e livros.
-   **Finanças Pessoais**: Controle de gastos e orçamento familiar.
-   **Saúde da Família**: Histórico médico e controle de medicação.
-   **Tarefas e Lembretes**: Organização de responsabilidades diárias.

Para uma descrição detalhada da visão e de todas as funcionalidades planejadas, consulte o documento [Visão do Projeto](./docs/project_vision.md).

## Instalação

Para configurar o ambiente de desenvolvimento e instalar as dependências do projeto, você precisará do `uv`.

1.  **Instale o `uv` (se ainda não tiver):**
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Crie o ambiente virtual:**
    ```bash
    uv venv
    ```

    **Ative o ambiente virtual:**
    ```bash
    source .venv/bin/activate
    ```

3.  **Instale as dependências do projeto:**
    ```bash
    uv pip install -e .
    ```

4.  **Instale as dependências de desenvolvimento (para geração de código):**
    ```bash
    uv pip install ".[dev]"
    ```

## Configuração

O projeto utiliza variáveis de ambiente para configuração e EXIGE um banco de dados PostgreSQL.

Antes de executar qualquer comando, certifique-se de configurar o ambiente:

1.  **Copie o exemplo de configuração:**
    ```bash
    cp .env.example .env
    ```
2.  **Edite o arquivo `.env`** com as credenciais do seu banco PostgreSQL local.

Você pode definir essas variáveis no seu sistema ou criar um arquivo `.env` na raiz do projeto (baseado em `.env.example`).

### Variáveis Disponíveis (Obrigatórias)

| Variável | Descrição | Padrão |
| :--- | :--- | :--- |
| `ENVIRONMENT` | Define o ambiente (`development`, `qa`, `production`). | `development` |
| `DB_HOST` | Host do banco de dados (PostgreSQL). | `localhost` |
| `DB_PORT` | Porta do banco de dados. | `5432` |
| `DB_USER` | Usuário do banco de dados. | `postgres` |
| `DB_PASSWORD` | Senha do banco de dados. | `postgres` |
| `DB_NAME` | Nome do banco de dados. | `caramello_db` |

### Ambientes

-   **Desenvolvimento:** Exige um banco PostgreSQL rodando localmente.
-   **Produção/QA:** Utilize as variáveis para apontar para o banco do ambiente.

3. Configure a Infraestrutura do Banco

O projeto inclui um assistente para criar o usuário e o banco de dados definidos no `.env`.

> **Nota:** Este passo requer credenciais de **superusuário** do Postgres (ex: `postgres`), mas não salva a senha.

```bash
./bin/setup_db
```

Este script irá:
1. Ler as variáveis `DB_USER` e `DB_NAME` do seu `.env`.
2. Verificar se o banco já existe.
3. Se existir, oferecerá o modo **RESET** (Drop & Create) para começar do zero.
4. Se não existir, criará o usuário (Role) e o Database, garantindo as permissões corretas.

## Uso

O projeto Caramello API utiliza um fluxo de trabalho onde DSLs em YAML definem as entidades. Um script de geração cria automaticamente os modelos SQLModel e os roteadores FastAPI, que por sua vez servem de base para a geração automática de migrações de banco de dados (Alembic).

### Geração de Código

O script de geração está localizado na pasta `scripts/`, mas recomendamos o uso do wrapper em `bin/`. Certifique-se de que seu ambiente virtual esteja configurado.

1.  **Gerar Modelos e API a partir do DSL:**
    Este script lê as definições de entidade em `dsl/entities/` e gera os modelos e roteadores.
    ```bash
    ./bin/generate_code
    ```

### Gestão de Banco de Dados

Utilize o script `bin/manage_db` para gerenciar o ciclo de vida do banco de dados. Ele encapsula o uso do Alembic e facilita operações comuns.

**Comandos disponíveis:**

-   **Inicializar/Atualizar Banco (`init` / `upgrade`):**
    Aplica todas as migrações pendentes.
    ```bash
    ./bin/manage_db init
    ```

-   **Criar Migração (`migrate`):**
    Gera um novo arquivo de migração detectando mudanças nos modelos.
    ```bash
    ./bin/manage_db migrate "descricao_da_mudanca"
    ```

-   **Resetar Banco (`reset`):**
    **CUIDADO:** Apaga todos os dados!
    -   Remove todas as tabelas (downgrade base) e recria.
    Útil para testes limpos em desenvolvimento.
    ```bash
    ./bin/manage_db reset
    ```

### Validação do Fluxo de Geração

Para garantir que o código gerado, as migrações e os testes estejam alinhados:

```bash
./bin/validate_generation
```

## Estrutura do Projeto

### Pastas principais:

-   **`alembic/`**: Scripts de migração de banco de dados (Alembic).
-   **`bin/`**: Scripts utilitários para gestão do projeto (banco, geração de código, etc).
-   **`docs/`**: Documentação detalhada do projeto.
-   **`dsl/`**: Definições de objetos de domínio em YAML (DSL). Gera código e OpenAPI.
-   **`src/caramello/`**: Pacote principal da aplicação.
    -   **`api/`**: Routers FastAPI (endpoints).
    -   **`core/`**: Configurações globais, variáveis de ambiente, utilitários.
    -   **`database/`**: Conexão com o banco de dados e configuração de sessão.
    -   **`models/`**: Modelos SQLModel (tabelas do banco de dados).
    -   **`repositories/`**: Camada de acesso a dados (queries).
    -   **`schemas/`**: Schemas Pydantic para validação.
    -   **`services/`**: Camada de lógica de negócio.
-   **`tests/`**: Testes automatizados.

## Tecnologias

O projeto é construído sobre uma stack moderna de Python:

-   **Python 3.10+**
-   **FastAPI** (async): framework web moderno e de alta performance.
-   **SQLModel / SQLAlchemy** (async): ORM que combina SQLAlchemy e Pydantic.
-   **Alembic**: ferramenta de migração de banco de dados.
-   **PostgreSQL**: banco de dados obrigatório em todos os ambientes — SQLite e bancos in-memory não são suportados.
-   **Pydantic**: validação de dados e gerenciamento de configurações.
-   **uv**: gerenciador de pacotes e projetos Python.

## Contribuição

Este projeto é pessoal, mas você pode usar esta seção para registrar como planejar melhorias, usar IA, etc.

## Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Links Relacionados

- [Caramello API](https://github.com/henricos/caramello-api)
- [Caramello App](https://github.com/henricos/caramello-app)

## Contato

[Henrico Scaranello](https://github.com/henricos)
