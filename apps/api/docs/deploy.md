# Deploy

> **Pendente de revisão.** Este documento foi adaptado de outro projeto e ainda não reflete o fluxo definitivo deste projeto.

Este documento descreve como subir a aplicação `caramello-api` via Docker Compose, usando a imagem publicada.

Use este guia quando o objetivo for colocar a aplicação em produção. Para desenvolvimento local, use `docs/development.md`. Para criar uma nova release, use `docs/release.md`.

## Pré-requisitos

- Docker Engine com `docker compose`
- Credenciais reais para as variáveis de ambiente
- Banco PostgreSQL acessível pelo container

## 1. Configure as variáveis de ambiente

Crie um arquivo `.env` no diretório de deploy com os valores reais do seu ambiente, baseado em `.env.example`.

## 2. Suba a aplicação

```bash
docker compose up -d
```

Para atualizar para a imagem mais recente publicada:

```bash
docker compose pull
docker compose up -d
```

## 3. Compose de produção

```yaml
services:
  api:
    image: ghcr.io/henricos/caramello-api:latest
    container_name: caramello-api
    restart: unless-stopped
    environment:
      ENVIRONMENT: production
      DB_HOST: ${DB_HOST}
      DB_PORT: ${DB_PORT}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME}
    ports:
      - "${API_HOST_PORT:-8000}:8000"
```

## Relação com outros guias

- Para desenvolvimento local: `docs/development.md`.
- Para fechar uma nova versão: `docs/release.md`.
