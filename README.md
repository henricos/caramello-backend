# Caramello Backend

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

_Em construção..._

## Instalação

Para configurar o ambiente de desenvolvimento e instalar as dependências do projeto, siga os passos abaixo:

1.  **Crie o ambiente virtual:**
    ```bash
    uv venv
    ```

2.  **Instale as dependências do projeto:**
    ```bash
    uv pip install -e .
    ```

3.  **Instale as dependências de desenvolvimento (para geração de código):**
    ```bash
    uv pip install ".[dev]"
    ```

## Uso

O projeto Caramello Backend utiliza um fluxo de trabalho "API First" com DSLs em YAML para definir entidades e gerar a especificação OpenAPI, que por sua vez é usada para gerar o código Python (modelos e esquemas).

### Fluxos de Geração

Os scripts de geração estão localizados na pasta `scripts/`. Certifique-se de que seu ambiente virtual esteja configurado e as dependências de desenvolvimento instaladas antes de executar.

1.  **Gerar Especificação OpenAPI a partir do DSL:**
    Este script lê as definições de entidade em `dsl/entities/` (conforme listado em `dsl/manifest.yaml`) e gera o arquivo `openapi/v1/spec.yaml`.
    ```bash
    uv run python scripts/generate_openapi_spec.py
    ```

2.  **Gerar Esquemas Pydantic a partir do OpenAPI:**
    Este script utiliza o `datamodel-code-generator` para gerar os modelos Pydantic (schemas da API) a partir do `openapi/v1/spec.yaml`. Os arquivos gerados serão salvos em `src/caramello/schemas/generated/`.
    ```bash
    uv run python scripts/generate_pydantic_schemas.py
    ```

## Estrutura do Projeto

_Em construção..._

## Tecnologias

_Em construção..._

## Contribuição

Este projeto é pessoal, mas você pode usar esta seção para registrar como planejar melhorias, usar IA, etc.

## Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Links Relacionados

- [Caramello Backend](https://github.com/henricos/caramello-backend)
- [Caramello Frontend Web](https://github.com/henricos/caramello-frontend-web)
- [Caramello Mobile](https://github.com/henricos/caramello-mobile)

## Contato

[Henrico Scaranello](https://github.com/henricos)
