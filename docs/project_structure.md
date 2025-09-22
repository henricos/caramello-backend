# Estrutura do Projeto

### Descrição das Pastas Principais:

*   **`alembic/`**: Contém os scripts de migração de banco de dados gerados pelo Alembic.
*   **`docs/`**: Armazena a documentação detalhada do projeto.
*   **`dsl/`**: Contém as definições de objetos de domínio em formato YAML, servindo como uma Domain Specific Language para geração de código.
*   **`src/caramello/`**: Pacote principal da aplicação.
    *   **`api/`**: Contém os routers do FastAPI que definem os endpoints da API.
    *   **`core/`**: Módulo para configurações globais, variáveis de ambiente e utilitários.
    *   **`database/`**: Módulo responsável pela configuração da conexão com o banco de dados.
    *   **`models/`**: Define os modelos de dados usando `SQLModel`.
    *   **`repositories/`**: Camada de acesso a dados, isolando as queries.
    *   **`schemas/`**: Contém os schemas Pydantic para validação de dados.
    *   **`services/`**: Camada de regras de negócio.
*   **`tests/`**: Contém todos os testes automatizados.
