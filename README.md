# Caramello API

Serviços backend para o sistema pessoal de organização familiar Caramello.

## Sobre

O Caramello é um sistema pessoal e integrado para organização familiar. Este repositório contém os serviços backend (a API) escritos em Python, que servem como a base para todas as aplicações do ecossistema Caramello (web e mobile).

O objetivo do projeto é centralizar diversas ferramentas de uso individual e compartilhado, como agenda, finanças, listas de compras, saúde e entretenimento, para simplificar a gestão do dia a dia da família.

Para uma descrição detalhada da visão e de todas as funcionalidades planejadas, consulte o documento [Visão do Projeto](./docs/project_vision.md).

## Funcionalidades

Algumas das principais funcionalidades planejadas:

-   **Agenda Familiar**: Compromissos individuais e compartilhados.
-   **Gestão de Compras**: Lista de compras colaborativa em tempo real.
-   **Controle de Despensa**: Inventário de itens domésticos.
-   **Entretenimento**: Listas de filmes, séries e livros.
-   **Finanças Pessoais**: Controle de gastos e orçamento familiar.
-   **Saúde da Família**: Histórico médico e controle de medicação.
-   **Tarefas e Lembretes**: Organização de responsabilidades diárias.

## Tecnologias

-   **Python 3.10+**
-   **FastAPI** (async): framework web moderno e de alta performance.
-   **SQLModel / SQLAlchemy** (async): ORM que combina SQLAlchemy e Pydantic.
-   **Alembic**: ferramenta de migração de banco de dados.
-   **PostgreSQL**: banco de dados obrigatório em todos os ambientes - SQLite e bancos in-memory não são suportados.
-   **Pydantic**: validação de dados e gerenciamento de configurações.
-   **uv**: gerenciador de pacotes e projetos Python.

## Estrutura do Projeto

-   **`alembic/`**: Scripts de migração de banco de dados.
-   **`bin/`**: Scripts utilitários para gestão do projeto.
-   **`docs/`**: Documentação técnica do projeto.
-   **`dsl/`**: Definições de domínio em YAML. Fonte de verdade para geração de código.
-   **`src/caramello/`**: Pacote principal da aplicação.
    -   **`api/`**: Routers FastAPI (endpoints).
    -   **`core/`**: Configurações globais e utilitários.
    -   **`database/`**: Conexão e configuração de sessão.
    -   **`models/`**: Modelos SQLModel (gerados - não editar diretamente).
    -   **`repositories/`**: Camada de acesso a dados.
    -   **`schemas/`**: Schemas Pydantic para validação.
    -   **`services/`**: Camada de lógica de negócio.
-   **`tests/`**: Testes automatizados.

## Desenvolvimento

Para configurar o ambiente, instalar dependências e rodar a aplicação localmente, consulte [`docs/dev.md`](./docs/dev.md).

## Deploy

Para subir a aplicação em produção via Docker Compose, consulte [`docs/deploy.md`](./docs/deploy.md).

## Fechamento de versão

Para fechar uma release e publicar uma nova imagem Docker, consulte [`docs/release.md`](./docs/release.md).

## Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

