# Regras de Qualidade (Caramello API)

A qualidade do código é garantida por automação e disciplina no design.

## 1. Tooling Obrigatório
O projeto utiliza um conjunto estrito de ferramentas. **Não ignore os erros delas.**
*   **Linter/Formatter**: `ruff`. (Comando: `ruff check .` e `ruff format .`)
*   **Type Checker**: `mypy`. (Comando: `mypy .`)
    *   Objetivo: 100% de cobertura de tipagem estática.
*   **Test Runner**: `pytest`.

## 2. Tipagem (Type Hints)
*   **Assinaturas Completas**: Todas as funções (argumentos e retorno) devem ter type hints.
    *   ✅ `def get_user(user_id: uuid.UUID) -> UserRead | None:`
    *   ❌ `def get_user(user_id):`
*   **Generics**: Use `list[str]` em vez de `List[str]` (Python 3.10+).

## 3. Integridade do DSL
Como este projeto é *DSL-First*:
*   **Sincronia**: O código em `src/` deve estar sempre sincronizado com `dsl/`.
*   **Validação**: Use `./bin/validate_generation` antes de abrir um PR para garantir que o código gerado corresponde ao DSL e às migrações.

## 4. Testes
*   **Unidade**: Teste regras de negócio isoladas (Services).Mock dependências de banco.
*   **Integração**: Teste endpoints (Routers) usando um banco de teste real (via `conftest.py`).
*   **Cobertura**: Esforce-se para testar caminhos felizes e casos de erro comuns.

## 5. Simplicidade e Legibilidade
*   **Funções Pequenas**: Uma função deve fazer apenas uma coisa.
*   **Nomes Descritivos**: Use nomes de variáveis e funções que revelem a intenção (em Inglês para código, conforme `language_rules.md`).
