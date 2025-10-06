# Diretrizes de Fluxo de Trabalho de IA

> **Nota para a IA:** Para obter o contexto completo sobre a visão, os objetivos e a arquitetura do sistema Caramello, consulte sempre o `README.md` e o documento detalhado em `docs/project_vision.md`.

Este projeto segue uma estratégia **API First**, adotando a **Especificação OpenAPI** como a **única fonte da verdade**.  
Todas as decisões de modelagem, banco de dados e API devem sempre estar em conformidade com o OpenAPI.  

## Fluxo de Trabalho Principal

1. Crie ou atualize entidades em YAML dentro da pasta `dsl/`.  
2. Gere uma especificação **OpenAPI** atualizada a partir do DSL.  
3. A partir deste ponto, o **OpenAPI se torna a única fonte da verdade**.  
4. Gere/atualize o seguinte com base no OpenAPI:  
   - **Modelos SQLModel** → `src/caramello/models/`  
   - **Esquemas Pydantic** → `src/caramello/schemas/`  
   - **Roteadores FastAPI** → `src/caramello/api/`  
   - **Migrações Alembic** → `alembic/`  
5. Execute e mantenha os testes em `tests/`, garantindo a consistência com o contrato.  

## DSL (YAML)
- O DSL é um **atalho auxiliar** para descrever entidades de negócio (nome, campos, tipos, relações).  
- O DSL é simples, focado apenas em **entidades CRUD**.  
- O papel do DSL é **gerar um arquivo OpenAPI**.  
- O DSL **nunca é a fonte da verdade**. Após a geração, **apenas o OpenAPI deve ser usado**.  

### Convenções de Nomenclatura no DSL
- **Nome da Entidade (`name`):** Use `PascalCase` (ex: `UserProfile`), pois irá gerar uma classe Python com o mesmo nome.
- **Nome do Arquivo YAML:** Use `snake_case` (ex: `user_profile.yaml`).
- **Nome da Tabela (`table_name`):** Use `snake_case` no plural (ex: `user_profiles`).

## OpenAPI
- A **Especificação OpenAPI** é a **única fonte da verdade** para o projeto.  
- Deve incluir:  
  - **Endpoints CRUD** (derivados do DSL).  
  - **Endpoints adicionais** (negócio, autenticação, fluxos de trabalho, etc.) definidos diretamente no OpenAPI.  
- O OpenAPI deve ser **versionado** e mantido atualizado no repositório.  
- Todos os outros artefatos devem ser gerados ou validados em relação a ele.  

## Diretrizes de Idioma

O projeto adota uma estratégia de dois idiomas para equilibrar a clareza para o público-alvo e a conformidade com as práticas globais de desenvolvimento de software.

### Inglês (English)
Utilizado para toda a base de código e artefatos diretamente ligados a ela. O objetivo é manter a consistência com as ferramentas, bibliotecas e o ecossistema de programação.
- **Código-Fonte**: Nomes de arquivos, diretórios, variáveis, funções e classes.
- **Comentários e Docstrings**: Devem estar no mesmo idioma do código para evitar inconsistências.
- **Arquivos DSL (YAML)**: Todas as descrições (`description`), comentários e qualquer outro texto livre dentro dos arquivos `.yaml` na pasta `dsl/` devem estar em inglês. Esses arquivos são a base para a geração do OpenAPI e, consequentemente, do código-fonte.

### Português do Brasil (pt-BR)
Utilizado para toda a comunicação e documentação voltada para humanos. O objetivo é garantir que o projeto seja acessível e claro para a equipe e os usuários brasileiros.
- **Documentação Geral**: Conteúdo da pasta `docs/`, `README.md`, etc.
- **Mensagens de Commit**: Devem seguir o padrão em português.
- **Pull Requests**: Títulos e descrições.
- **Textos para o Usuário Final**: Mensagens de erro, interfaces e qualquer texto exibido na aplicação.

## Documentação de Referência
Regras e diretrizes adicionais estão disponíveis na pasta [`docs/`](./docs):
- [Guia de Estilo](./docs/style_guide.md)  
- [Estrutura do Projeto](./docs/project_structure.md)  
- [Regras de Commit](./docs/commit_rules.md)  
- [Regras de Pull Request](./docs/pr_rules.md)  
- [Regras de Segurança](./docs/security_rules.md)  
- [Regras de Qualidade](./docs/quality_rules.md)  

> **Importante:**  
> - O DSL é apenas auxiliar.  
> - O OpenAPI é a **única referência oficial**.  
> - Todo o código deve refletir o contrato definido no OpenAPI.
