# Roadmap: Caramello API — Milestone 1

## Overview

O Milestone 1 não é construção de features novas: é a correção da fundação para que ela possa sustentar crescimento. A ordem das fases é determinada por dependências duras de stack — o driver async desbloqueie tudo; auth depende de User correto e estrutura por domínios; endpoints family dependem de auth; MCP, testes e Docker ficam para o final porque dependem de todos acima ou são independentes.

## Phases

- [ ] **Phase 1: Infra Base** - Corrige modelo User, recria migration, configura ruff/mypy e CORS
- [ ] **Phase 2: Stack Async** - Substitui psycopg2 por asyncpg, migra para AsyncSession e Alembic async, atualiza DSL generator
- [x] **Phase 3: Estrutura por Domínios e Autenticação** - Reorganiza código para domains/shared, implementa shared/auth.py com Keycloak JWT e endpoint /user/me (completed 2026-05-25; gap closure via 03-06/03-07)
- [ ] **Phase 4: Domínio Family** - Implementa todos os endpoints REST do domínio familia protegidos por auth
- [ ] **Phase 5: MCP, Testes e Docker** - Integra fastapi-mcp, cria infraestrutura de testes isolados e containeriza a aplicação

## Phase Details

### Phase 1: Infra Base
**Goal**: A fundação técnica está correta — modelo User sem campos de auth local, migration limpa aplicável em banco vazio, linting e type-check configurados, CORS habilitado para o frontend
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-02, INFRA-03, MODEL-01, MODEL-02, MODEL-03
**Success Criteria** (what must be TRUE):
  1. Tabela `users` não contém colunas `hashed_password`, `google_id`, `phone_number`, `is_active` — apenas `idp_sub`, `email`, `name`, `created_at`, `updated_at`
  2. `alembic upgrade head` em banco limpo com nome `familia_dev` conclui sem erro
  3. `ruff check src/` e `mypy src/` passam sem erros — configurados em `pyproject.toml`
  4. Frontend React/Capacitor em `localhost` recebe respostas sem erro de CORS — `CORSMiddleware` presente em `main.py`
  5. `.env.example` documenta `DATABASE_URL` com `familia_dev`/`familia_prod` e variáveis Keycloak
**Plans**: 4 planos
Plans:
- [x] 01-01-PLAN.md — Corrigir user.yaml e regenerar modelos (User Keycloak-aligned + datetime fix)
- [x] 01-02-PLAN.md — Remover artefatos obsoletos (schemas/, tests/generated/, api/v1/, arquivos vazios)
- [x] 01-03-PLAN.md — Configurar ruff/mypy, CORS e atualizar .env.example
- [x] 01-04-PLAN.md — Recriar migration Alembic (deletar antiga, gerar initial_schema)

### Phase 2: Stack Async
**Goal**: Todas as operações de banco são genuinamente assíncronas — event loop nunca bloqueado, Alembic opera em modo async, DSL generator emite código async
**Depends on**: Phase 1
**Requirements**: INFRA-01
**Success Criteria** (what must be TRUE):
  1. `asyncpg` é o driver de banco — `psycopg2-binary` removido das dependências; `grep -r "create_engine" src/` retorna vazio
  2. `shared/database.py` usa `create_async_engine` + `async_sessionmaker` + `AsyncSession` de `sqlalchemy.ext.asyncio`
  3. `alembic/env.py` usa `async_engine_from_config` com `NullPool` — `alembic upgrade head` conclui sem travar
  4. DSL generator produz routers com `async def` — endpoints gerados não bloqueiam o event loop
**Plans**: 4 planos
Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Trocar driver: remover psycopg2-binary, adicionar asyncpg, atualizar sqlmodel para 0.0.38

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md — Criar shared/database.py (engine + factory + get_session async) e ajustar prefixo postgresql+asyncpg em config.py
- [x] 02-03-PLAN.md — Migrar alembic/env.py para modo online async com async_engine_from_config + NullPool + dispose

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-04-PLAN.md — Atualizar generate_router() para template async, regenerar 4 routers, deletar database/session.py legado

### Phase 3: Estrutura por Domínios e Autenticação
**Goal**: Código organizado por domínio de negócio, camada de auth isolada em shared/auth.py, e usuário autenticado pode consultar seu próprio perfil
**Depends on**: Phase 2
**Requirements**: STRUCT-01, STRUCT-02, AUTH-01, AUTH-02, AUTH-03, USER-01
**Success Criteria** (what must be TRUE):
  1. Código está em `src/caramello/user/`, `src/caramello/family/`, `src/caramello/shared/` — diretórios `models/` e `api/generated/` removidos
  2. DSL generator com campo `domain` no YAML produz `models.py` (ORM + schemas Read/Create/Update), `router.py` e `operations.py` dentro de `src/caramello/{domain}/` sem editar arquivos gerados
  3. `GET /user/me` com Bearer token Keycloak válido retorna `id`, `email`, `name` do usuário autenticado
  4. `GET /user/me` sem token retorna 401 — validação via `Depends(get_current_user)` em `shared/auth.py`
  5. Primeira request com token válido de novo usuário cria registro na tabela `users` automaticamente (JIT provisioning com `ON CONFLICT DO NOTHING`)
**Plans**: 7 planos (5 iniciais + 2 gap closure)
Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Wave 0: stubs de testes (test_generator, test_auth, test_user_operations, conftest)
- [x] 03-02-PLAN.md — Wave 1: deps (PyJWT[crypto], httpx), Settings Keycloak, campo domain nos YAMLs, dsl/operations/user.yaml

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-03-PLAN.md — Wave 2: evoluir scripts/generate_code.py (domain + operations + tipos modernos + auth no router)
- [x] 03-04-PLAN.md — Wave 2: implementar src/caramello/shared/auth.py (JWKS cache + get_current_user + JIT provisioning)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-05-PLAN.md — Wave 3: regenerar código, implementar /user/me, atualizar main.py + alembic + pyproject, remover paths antigos, checkpoint humano

**Gap closure** *(após 03-VERIFICATION.md)*
- [x] 03-06-PLAN.md — Wave 1: corrigir generator para emitir `# noqa: UP037` (mapper bug), corrigir `_: User` em routers, destravar testes xfail/skip, ajustar ROADMAP SC2 (Gaps 1 e 3)
- [x] 03-07-PLAN.md — Wave 2 (autonomous: false): operador executa checklist E2E com Keycloak real + PostgreSQL, preenche 03-07-EVIDENCE.md (Gap 2)
**UI hint**: no

### Phase 4: Domínio Family
**Goal**: Usuário autenticado pode criar e gerenciar famílias, convidar membros e controlar adesões — todos os endpoints do domínio family funcionais e protegidos
**Depends on**: Phase 3
**Requirements**: FAMILY-01, FAMILY-02, FAMILY-03, FAMILY-04, FAMILY-05, FAMILY-06, FAMILY-07
**Success Criteria** (what must be TRUE):
  1. `POST /family/families` cria família e torna o usuário autenticado owner automaticamente
  2. `GET /family/families` lista apenas famílias das quais o usuário é membro
  3. `POST /family/families/{id}/invitations` gera código de convite reutilizável — apenas owner consegue; não-owner recebe 403
  4. `POST /family/invitations/{code}/join` registra solicitação pendente para o usuário autenticado
  5. `PATCH /family/invitations/{id}` permite owner aprovar ou rejeitar — solicitação aprovada adiciona membro; solicitação rejeitada não adiciona
  6. `DELETE /family/families/{id}/members/{user_id}` remove membro — apenas owner consegue; todos os endpoints retornam 401 sem token

**Plans**: 4 planos (1 wave por plano — sequenciais)
Plans:
**Wave 1**
- [x] 04-01-PLAN.md — Wave 0: stubs de testes (test_family_operations + test_auth.auto_join + test_generator)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 04-02-PLAN.md — Evoluir DSL: domains plurais (users/families), redesign FamilyInvitation, dsl/operations/family.yaml, generator com URL plural + hifens

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 04-03-PLAN.md — Regenerar código (users/ + families/), deletar diretórios antigos, atualizar main.py + alembic/env.py + migration Alembic

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 04-04-PLAN.md — Implementar families/operations.py (6 endpoints) + estender shared/auth.py com auto-join (D-02) + finalizar ROADMAP/REQUIREMENTS (FAMILY-04/05/06 deferidos M2)

> **Nota:** os Success Criteria acima refletem o fluxo original (código de convite reutilizável FAMILY-04/05/06). Após Plano 04-04, este bloco passa a refletir o fluxo de pré-cadastro por email (D-01/D-02 em 04-CONTEXT.md) — FAMILY-04/05/06 deferidos para M2 conforme D-04.

### Phase 5: MCP, Testes e Docker
**Goal**: Aplicação containerizada, testada com isolamento de banco, e expondo ferramentas MCP protegidas por auth — pronta para deploy
**Depends on**: Phase 4
**Requirements**: MCP-01, MCP-02, DEPLOY-01, DEPLOY-02, DEPLOY-03, TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. Cliente MCP em `/mcp` descobre ferramentas de consulta de `family` (famílias, membros, convites) e `user` (me) — ferramentas MCP exigem Bearer token válido com mesmo mecanismo dos endpoints REST
  2. `docker build` produz imagem reproducível com Dockerfile multi-stage, non-root user, sem secrets nos layers de build
  3. `docker compose up` inicia a aplicação com configuração exclusivamente via variáveis de ambiente — sem valores hardcoded; `APP_VERSION` como build arg aparece na OpenAPI spec
  4. `pytest` executa contra banco isolado `familia_test` com rollback por teste — banco `familia_dev` não é tocado
  5. Casos de sucesso do domínio family têm cobertura de testes: criar família, convidar, aprovar, listar membros — usando `dependency_overrides` para simular usuário autenticado sem Keycloak real
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infra Base | 0/4 | Planned | - |
| 2. Stack Async | 0/4 | Planned | - |
| 3. Estrutura por Domínios e Autenticação | 6/7 | In Progress|  |
| 4. Domínio Family | 0/? | Not started | - |
| 5. MCP, Testes e Docker | 0/? | Not started | - |
