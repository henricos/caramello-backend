---
status: partial
phase: 05-mcp-testes-e-docker
source: [05-VERIFICATION.md]
started: 2026-05-27T00:00:00Z
updated: 2026-05-27T00:00:00Z
---

## Current Test

[aguardando testes manuais]

## Tests

### 1. Build Docker real
expected: `docker build --build-arg APP_VERSION=1.0.0-test -t caramello-api:test .` sai com exit 0; `docker inspect caramello-api:test` mostra User=app; `docker history caramello-api:test` sem DB_PASSWORD ou KEYCLOAK_* nos layers
result: [pending]

### 2. Stack completa docker compose
expected: Criar `.env` real com credenciais, `docker compose up` sobe a API; `curl http://localhost:8000/openapi.json` retorna `version` igual ao APP_VERSION injetado via `docker compose --build-arg`
result: [pending]

### 3. Suite de integração com caramello_dev real
expected: `uv run pytest -m integration -v` com `caramello_dev` disponível e `.env` configurado — 4 testes passam com rollback (nenhum dado fica no banco após os testes)
result: [pending]

### 4. Cliente MCP real
expected: `npx @modelcontextprotocol/inspector http://localhost:8000/mcp` com Bearer Keycloak válido — ferramenta `list_my_families` aparece na lista; sem Bearer retorna 401/403
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
