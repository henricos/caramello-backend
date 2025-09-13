# Estrutura do Projeto

Este documento descreve a estrutura de diretórios e arquivos do projeto `caramello-backend`. Ele serve como um guia para desenvolvedores e ferramentas de IA entenderem a organização do código e onde cada tipo de funcionalidade deve residir.

```
/caramello-backend
├── .clinerules/
│   └── context.md         # Arquivo de contexto para o Cline (e outras IAs)
├── .gitignore             # Arquivos e diretórios a serem ignorados pelo Git
├── README.md              # Descrição geral do projeto
├── pyproject.toml         # Configuração do projeto, dependências (gerenciado por 'uv')
├── alembic.ini            # Configuração do Alembic
│
├── alembic/               # Arquivos de migração do Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── dsl/                   # Definições de objetos de domínio em YAML (Domain Specific Language)
│   ├── schema.yaml        # Schema para validação das entidades DSL
│   └── entities/
│       └── user.yaml      # Exemplo de definição de um objeto de domínio 'User'
│
├── src/
│   └── caramello/         # Pacote principal da aplicação
│       ├── __init__.py
│       ├── main.py        # Ponto de entrada da API, instanciação do FastAPI
│       ├── exceptions.py  # Exceções de domínio customizadas
│       ├── http_errors.py # Handlers de exceção do FastAPI
│       │
│       ├── core/          # Configurações centrais da aplicação
│       ├── database/      # Módulo para conexão e sessão com o banco de dados
│       ├── models/        # Modelos de dados (SQLModel)
│       ├── schemas/       # Schemas Pydantic para validação de entrada/saída da API
│       ├── repositories/  # Camada de acesso a dados (queries)
│       ├── services/      # Camada de regras de negócio (lógica de domínio)
│       └── api/           # Endpoints da API (FastAPI Routers)
│           └── v1/
│               ├── routes.py
│               └── users.py
│
├── tests/                 # Testes unitários e de integração
│   ├── __init__.py
│   ├── conftest.py        # Fixtures de teste
│   ├── factories/         # Model factories
│   ├── test_repositories/
│   ├── test_services/
│   └── test_api/
│
├── docs/                  # Documentação para guiar o desenvolvimento (humano e IA)
│   ├── prd.md
│   ├── python_style_guide.md
│   ├── project_structure.md  # Este documento
│   ├── roadmap.md
│   ├── ai_workflow.md
│   └── api_conventions.md
│
└── prompts/               # Coleção de prompts reutilizáveis para a IA
    ├── finish_task.md
    └── review_project.md
```

### Descrição das Pastas Principais:

*   **`.clinerules/`**: Contém arquivos de configuração específicos para a ferramenta Cline, que direcionam a IA para a documentação relevante.
*   **`alembic/`**: Contém os scripts de migração de banco de dados gerados pelo Alembic.
*   **`dsl/`**: Contém as definições de objetos de domínio em formato YAML, servindo como uma Domain Specific Language para geração de código.
*   **`src/caramello/`**: Pacote principal da aplicação.
    *   **`core/`**: Módulo para configurações globais, variáveis de ambiente e utilitários.
    *   **`database/`**: Módulo responsável pela configuração da conexão com o banco de dados.
    *   **`models/`**: Define os modelos de dados usando `SQLModel`.
    *   **`schemas/`**: Contém os schemas Pydantic para validação de dados.
    *   **`repositories/`**: Camada de acesso a dados, isolando as queries.
    *   **`services/`**: Camada de regras de negócio.
    *   **`api/`**: Contém os routers do FastAPI que definem os endpoints da API.
*   **`tests/`**: Contém todos os testes automatizados.
*   **`docs/`**: Armazena a documentação detalhada do projeto.
*   **`prompts/`**: Uma coleção de prompts de IA reutilizáveis.
