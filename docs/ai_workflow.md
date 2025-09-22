# Orientações para IAs no Fluxo de Trabalho

Este projeto segue a estratégia **API First**, adotando o **OpenAPI Specification** como **fonte única de verdade**.  
Todas as decisões de modelagem, banco de dados e API devem sempre estar em conformidade com o OpenAPI.  

## 1. Papel do DSL (YAML)
- O **DSL em YAML** é um **atalho auxiliar** para descrever entidades de negócio (nome, campos, tipos, relações).  
- O DSL é simples, focado apenas em **CRUD de entidades**.  
- A função do DSL é **gerar automaticamente o arquivo OpenAPI** correspondente.  
- O **DSL nunca é considerado a fonte de verdade**. Após a geração, **somente o OpenAPI deve ser usado** como referência para todas as outras etapas.  

Exemplo de tarefas esperadas para IA:  
- Criar um arquivo YAML no diretório `dsl/` com entidades e relações.  
- Converter arquivos DSL em OpenAPI válido.  

---

## 2. Papel do OpenAPI
- O **OpenAPI Specification** é a **única fonte de verdade do projeto**.  
- Ele deve conter todos os endpoints:  
  - **CRUD de entidades** (derivados do DSL).  
  - **Endpoints adicionais** (negócio, autenticação, workflows, etc.) definidos diretamente no OpenAPI.  
- O OpenAPI deve sempre ser **versão controlada** e atualizado no repositório.  
- A partir do OpenAPI, o restante do código deve ser gerado ou validado.  

Exemplo de tarefas esperadas para IA:  
- Validar e expandir a especificação OpenAPI.  
- Gerar schemas Pydantic com base nos componentes do OpenAPI.  
- Gerar routers do FastAPI (`src/caramello/api/`) conforme definido no OpenAPI.  
- Garantir que os modelos, schemas e endpoints estão em conformidade com o contrato.  

---

## 3. Banco de Dados e Models
- O banco de dados será modelado com **SQLModel**.  
- **Alembic** será usado para gerar e versionar migrations no diretório `alembic/`.  
- Models em `src/caramello/models/` devem refletir fielmente os schemas definidos no OpenAPI.  
- Qualquer alteração de schema deve ser feita **via OpenAPI**, nunca direto nos models.  

Exemplo de tarefas esperadas para IA:  
- Gerar models SQLModel a partir dos schemas do OpenAPI.  
- Criar migrations Alembic automáticas com base nos models.  
- Atualizar migrations quando houver mudanças no OpenAPI.  

---

## 4. API (FastAPI + Pydantic)
- A API será implementada com **FastAPI**.  
- Todos os dados de entrada e saída devem ser validados com **Pydantic schemas**.  
- O diretório `src/caramello/api/` conterá os routers correspondentes aos endpoints do OpenAPI.  
- O diretório `src/caramello/schemas/` conterá os schemas Pydantic para validação.  

Exemplo de tarefas esperadas para IA:  
- Criar routers FastAPI a partir dos endpoints definidos no OpenAPI.  
- Criar schemas Pydantic compatíveis com os componentes do OpenAPI.  
- Gerar testes automatizados para validar a conformidade da API com o contrato.  

---

## 5. Fluxo Resumido
1. Criar ou ajustar entidades em YAML no diretório `dsl/`.  
2. Gerar um arquivo **OpenAPI** atualizado a partir do DSL.  
3. **O OpenAPI passa a ser a fonte de verdade**. Todas as etapas seguintes devem usá-lo como referência.  
4. Gerar/atualizar:  
   - **Models SQLModel** em `src/caramello/models/`  
   - **Schemas Pydantic** em `src/caramello/schemas/`  
   - **Routers FastAPI** em `src/caramello/api/`  
   - **Migrations Alembic** em `alembic/`  
5. Executar e manter testes em `tests/` garantindo que tudo está consistente com o contrato.  

---

> ⚠️ **Importante:**  
> - O DSL é apenas auxiliar.  
> - O OpenAPI é a **única referência oficial**.  
> - Todo código deve refletir o contrato definido no OpenAPI.  
