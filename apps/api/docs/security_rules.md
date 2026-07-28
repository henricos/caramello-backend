# Regras de Segurança (Caramello API)

Estas regras visam proteger os dados da família e garantir a integridade da aplicação.

## 1. Validação de Dados (Pydantic & DSL)
*   **Trust No One**: Nunca confie em dados vindos da requisição.
*   **Schemas Rígidos**: Use Pydantic schemas com tipagem estrita (`StrictStr`, `StrictInt` quando aplicável).
*   **DSL Comunitário**: Defina restrições de validação (regex, min/max length) diretamente no DSL (`dsl/entities/*.yaml`) para que sejam propagadas para o código.

## 2. Proteção de Banco de Dados (SQLModel)
*   **SQL Injection**: **NUNCA** concatene strings em queries SQL.
    *   ✅ **Correto**: `session.exec(select(User).where(User.email == email))`
    *   ❌ **Proibido**: `session.exec(f"SELECT * FROM user WHERE email = '{email}'")`
*   **Exposição de Dados**: O ORM busca todos os campos por padrão. Tenha cuidado ao serializar objetos do banco diretamente.

## 3. Vazamento de Dados (Response Models)
*   **Response Model Obrigatório**: Todo endpoint FastAPI deve ter um `response_model` definido explicitamente.
*   **Separação de Camadas**: Nunca retorne a entidade do banco (SQLModel Table) diretamente como resposta da API.
    *   Use Schemas de Leitura (`UserRead`) que omitam campos sensíveis como senhas, tokens e metadados internos.

## 4. Gerenciamento de Dependências
*   **Auditoria**: Execute regularmente `uv pip list` e verifique por CVEs conhecidos.
*   **Pinning**: Mantenha o `pyproject.toml` e `uv.lock` atualizados para garantir builds reproduzíveis e seguros.

## 5. Logs e Erros
*   **Sanitização**: Nunca logue senhas, tokens JWT ou dados pessoais (PII) em logs de aplicação.
*   **Erros Genéricos**: Em produção, retorne mensagens de erro genéricas ("Internal Server Error") para não expor stack traces ou detalhes da infraestrutura.
