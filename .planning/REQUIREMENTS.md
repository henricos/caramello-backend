# Requirements: Caramello API — Milestone 1

**Definido:** 2026-05-23
**Core Value:** Um backend sólido, seguro e extensível onde cada novo domínio de negócio pode ser adicionado sem tocar no que já existe.

---

## v1 Requirements

Requisitos do Milestone 1 — Fundação e revisão geral do projeto.

### Infraestrutura Assíncrona

- [ ] **INFRA-01**: Todas as queries ao banco são executadas de forma assíncrona via `asyncpg` — o event loop não é bloqueado em nenhuma operação de I/O de banco
- [ ] **INFRA-02**: O código-fonte passa em `ruff` (linting) e `mypy` (type-check) sem erros — ferramentas configuradas em `pyproject.toml`
- [ ] **INFRA-03**: O frontend React/Capacitor pode consumir a API sem erros de CORS — `CORSMiddleware` configurado no `main.py`

### Modelo de Dados

- [ ] **MODEL-01**: A tabela `users` representa apenas dados de identidade Keycloak (`idp_sub`, `email`, `name`, `created_at`, `updated_at`) — sem campos de auth local (`hashed_password`, `google_id`, `phone_number`, `is_active`)
- [ ] **MODEL-02**: Migrações Alembic refletem o schema correto e podem ser aplicadas em banco limpo sem erro — migration antiga descartada e recriada
- [ ] **MODEL-03**: O banco de dados usa a convenção de nomenclatura `familia_dev` (dev) e `familia_prod` (prod) — `.env.example` atualizado

### Autenticação e Autorização

- [x] **AUTH-01**: Endpoints protegidos rejeitam requests sem Bearer token Keycloak válido com 401 — validação local via JWKS sem round-trip ao Keycloak por request
- [x] **AUTH-02**: Usuário é criado automaticamente no banco na primeira request com token válido (just-in-time provisioning) — operação atômica com `ON CONFLICT DO NOTHING`
- [x] **AUTH-03**: `shared/auth.py` isola completamente a lógica de validação JWT — qualquer endpoint usa `Depends(get_current_user)` para se proteger

### Estrutura por Domínios

- [x] **STRUCT-01**: Código organizado por domínio de negócio (`src/caramello/user/`, `src/caramello/family/`, `src/caramello/shared/`) em vez de camadas técnicas planas (`models/`, `api/generated/`) — routers gerados migrados para a nova estrutura
- [x] **STRUCT-02**: DSL generator produz `models.py` e `schemas.py` dentro do diretório do domínio correto quando o YAML contém o campo `domain` — sem editar arquivos gerados diretamente

### Domínio User

- [x] **USER-01**: Usuário autenticado pode consultar seu próprio perfil (`GET /user/me`) — retorna `id`, `email`, `name`

### Domínio Family

- [x] **FAMILY-01**: Usuário autenticado pode criar uma família e torna-se owner automaticamente (`POST /families/registry`)
- [x] **FAMILY-02**: Usuário autenticado pode listar suas famílias (`GET /families/families`)
- [x] **FAMILY-03**: Usuário autenticado pode consultar detalhes de uma família da qual é membro (`GET /families/families/{uuid}`)
- [ ] **FAMILY-04**: Owner pode gerar código de convite reutilizável para a família — DEFERIDO M2 (D-04)
- [ ] **FAMILY-05**: Usuário autenticado pode usar convite para solicitar entrada em família — DEFERIDO M2 (D-04)
- [ ] **FAMILY-06**: Owner pode aprovar ou rejeitar solicitações de entrada pendentes — DEFERIDO M2 (D-04)
- [x] **FAMILY-07**: Owner pode remover membros da família (`DELETE /families/families/{uuid}/members/{user_uuid}`) e listar (`GET /families/families/{uuid}/members`)

> **Nota Phase 4 (D-04):** Os requisitos FAMILY-04, FAMILY-05 e FAMILY-06 (fluxo de código de convite reutilizável + join request + aprovação manual) foram deferidos para o Milestone 2 — eles caracterizam um produto público com múltiplas famílias de terceiros, fora do escopo do M1 (grupo fechado 1-5 usuários). Em substituição, a Phase 4 implementa o fluxo de **pré-cadastro por email** (D-01, D-02) que é equivalente em valor para o grupo familiar e mais simples operacionalmente.

### MCP — Model Context Protocol

- [ ] **MCP-01**: Cliente MCP conectando em `/mcp` descobre ferramentas de consulta do domínio `family` (GET de famílias, membros e convites) e do domínio `user` (GET /user/me)
- [ ] **MCP-02**: Ferramentas MCP exigem Bearer token válido — mesmo mecanismo de auth dos endpoints REST

### Deploy e Containerização

- [ ] **DEPLOY-01**: Aplicação é construída como imagem Docker reproducível com `docker build` — Dockerfile multi-stage, non-root user, sem secrets no layer de build
- [ ] **DEPLOY-02**: Aplicação é iniciada com `docker compose up` injetando configuração exclusivamente via variáveis de ambiente — sem valores hardcoded
- [ ] **DEPLOY-03**: Build aceita `APP_VERSION` como build arg e expõe na OpenAPI spec (`title` ou `version`)

> **Nota de infraestrutura:** a exposição pública usa **Cloudflare Tunnel** (não nginx). Subdomínio definitivo para API e MCP ainda não decidido — ver questão em aberto abaixo.

### Testes

- [ ] **TEST-01**: Testes executam contra banco de dados isolado com rollback por teste — sem contaminar `familia_dev` ou produção
- [ ] **TEST-02**: Endpoints do domínio familia têm cobertura de testes para casos de sucesso — criar família, convidar, aprovar, listar membros
- [ ] **TEST-03**: Testes de endpoints protegidos usam `dependency_overrides` para simular usuário autenticado — sem precisar de Keycloak real nos testes

---

## v2 Requirements

Reconhecidos mas deferidos para milestones futuros.

### Qualidade Operacional

- **OPS-01**: Endpoint `GET /health` com ping ao banco — responde 200 se DB acessível, 503 se não
- **OPS-02**: Logging estruturado em JSON (`structlog`) — facilita consulta em produção
- **OPS-03**: SSL no `DATABASE_URL` em produção — `sslmode=require`
- **OPS-04**: CI pipeline automático (GitHub Actions) — rodar testes e linting no push

### MCP Avançado

- **MCP-03**: Ferramentas MCP de escrita para domínio familia — criar família, convidar, aprovar (operações além de GET)
- **MCP-04**: Documentação das ferramentas MCP com exemplos de uso para agentes

### Domínio Financeiro (Milestone 2)

- **FIN-01**: (a definir no M2)

### Domínio Lista de Compras (Milestone 3)

- **COMP-01**: (a definir no M3)

---

## Questões em Aberto

| Questão | Contexto |
|---------|---------|
| Subdomínio API vs MCP | `api.caramello.cloud` + `mcp.caramello.cloud` separados, ou tudo em `api.caramello.cloud/mcp`? Infraestrutura via Cloudflare Tunnel. Decide no M1 deploy. |
| Valores Keycloak | `realm_name`, `client_id`, `audience` — confirmar contra instância existente antes de implementar `shared/auth.py` |

## Out of Scope

| Feature | Razão |
|---------|-------|
| Autenticação local com senha | Keycloak é o único IdP — sem `hashed_password`, sem fluxo de cadastro local |
| Servidor MCP separado | `fastapi-mcp` integrado na mesma app via ASGI — sem serviço adicional |
| Token introspection remota | Validação local com JWKS cacheado — sem round-trip ao Keycloak por request |
| `response_model` com SQLModel table class | Sempre usar schemas `*Read` separados para não vazar campos internos |
| Middleware global de auth | `Depends(get_current_user)` por router — endpoints de health ficam desprotegidos intencionalmente |
| Lógica de negócio financeiro, agenda, saúde | Domains do M2+ — não entram no M1 |
| Frontend React/Capacitor | Repositório separado (`caramello-app`) |
| Multi-tenancy entre grupos | Este repo serve exclusivamente o Grupo Família |

---

## Traceability

| Requisito | Fase | Status |
|-----------|------|--------|
| INFRA-01 | Phase 2 | Pendente |
| INFRA-02 | Phase 1 | Pendente |
| INFRA-03 | Phase 1 | Pendente |
| MODEL-01 | Phase 1 | Pendente |
| MODEL-02 | Phase 1 | Pendente |
| MODEL-03 | Phase 1 | Pendente |
| AUTH-01 | Phase 3 | Pendente |
| AUTH-02 | Phase 3 | Pendente |
| AUTH-03 | Phase 3 | Pendente |
| STRUCT-01 | Phase 3 | Pendente |
| STRUCT-02 | Phase 3 | Pendente |
| USER-01 | Phase 3 | Pendente |
| FAMILY-01 | Phase 4 | Implementado (04-04) |
| FAMILY-02 | Phase 4 | Implementado (04-04) |
| FAMILY-03 | Phase 4 | Implementado (04-04) |
| FAMILY-04 | Phase 4 → M2 | Deferred (D-04) |
| FAMILY-05 | Phase 4 → M2 | Deferred (D-04) |
| FAMILY-06 | Phase 4 → M2 | Deferred (D-04) |
| FAMILY-07 | Phase 4 | Implementado (04-04) |
| MCP-01 | Phase 5 | Pendente |
| MCP-02 | Phase 5 | Pendente |
| DEPLOY-01 | Phase 5 | Pendente |
| DEPLOY-02 | Phase 5 | Pendente |
| DEPLOY-03 | Phase 5 | Pendente |
| TEST-01 | Phase 5 | Pendente |
| TEST-02 | Phase 5 | Pendente |
| TEST-03 | Phase 5 | Pendente |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27 ✓
- Unmapped: 0 ✓

---

*Requirements definidos: 2026-05-23*
*Last updated: 2026-05-23 — traceability preenchida pelo agente de roadmap (5 fases, cobertura 100%)*
