# Estrutura de Diretórios do Projeto

### Pastas principais:
- **`alembic/`**: Scripts de migração de banco de dados (Alembic).
- **`docs/`**: Documentação detalhada do projeto.
- **`dsl/`**: Definições de objetos de domínio em YAML (DSL). Gera código e OpenAPI.
- **`src/caramello/`**: Pacote principal da aplicação.
  - **`api/`**: Routers FastAPI (endpoints).
  - **`core/`**: Configurações globais, variáveis de ambiente, utilitários.
  - **`database/`**: Conexão com o banco de dados e configuração de sessão.
  - **`models/`**: Modelos SQLModel (tabelas do banco de dados).
  - **`repositories/`**: Camada de acesso a dados (queries).
  - **`schemas/`**: Schemas Pydantic para validação.
  - **`services/`**: Camada de lógica de negócio.
- **`tests/`**: Testes automatizados.
