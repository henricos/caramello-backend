# Caramello API

## What This Is

Backend Python/FastAPI do sistema Caramello — plataforma pessoal e familiar para centralizar agenda, finanças, listas de compras, saúde e entretenimento. Serve um grupo fechado de 1 a 5 usuários (membros da família), com autenticação via Keycloak e dados organizados por domínios de negócio. Destinado a ser consumido por um frontend React/Capacitor (mobile-first) e por agentes de IA via MCP.

## Core Value

Um backend sólido, seguro e extensível onde cada novo domínio de negócio (financeiro, agenda, compras…) pode ser adicionado sem tocar no que já existe.

## Requirements

### Validated

<!-- Infraestrutura técnica existente, inspecionada no codebase. -->

- ✓ Pipeline DSL (YAML → SQLModel + routers) operacional — `scripts/generate_code.py`, `dsl/entities/`
- ✓ Alembic configurado com banco PostgreSQL — `alembic/`
- ✓ Configuração via variáveis de ambiente (`pydantic-settings`) — `src/caramello/core/config.py`
- ✓ Scripts operacionais (`generate_code`, `manage_db`, `setup_db`, `validate_generation`) — `bin/`
- ✓ Entidades de núcleo definidas no DSL: `User`, `Family`, `FamilyMember`, `FamilyInvitation`
- ✓ FastAPI com 4 routers gerados registrados em `main.py`

### Active

<!-- Milestone 1 — Fundação e revisão geral. -->

- [ ] Servidor MCP integrado via `fastapi-mcp` expondo serviços do domínio `familia`
- [ ] Dockerfile e `compose.yaml` (padrão multi-stage, não-root user, inject via env — baseado em `hiring-pipeline`)
- [ ] Infraestrutura de testes: `pytest` + `pytest-asyncio`, fixtures de banco isoladas, testes do domínio `familia`

### Validated in Phase 4 (2026-05-26)

- ✓ DSL generator evoluído com suporte a campo `domain`, URL `/{domain}/{table-with-hyphens}`, `DOMAIN_TO_ENTITY_NAME` — `scripts/generate_code.py`
- ✓ Estrutura de código reorganizada para arquitetura por domínios (`src/caramello/users/`, `src/caramello/families/`, `src/caramello/shared/`)
- ✓ Domínio `families` implementado: `Family`, `FamilyMember`, `FamilyInvitation` (redesenhada com `email`+`status`) + User provisioning
- ✓ Endpoints REST do domínio `families` implementados e protegidos por auth (FAMILY-01/02/03/07 entregues; FAMILY-04/05/06 diferidos para M2)
- ✓ Camada de autenticação JWT via Keycloak: `shared/auth.py` com validação de token, just-in-time provisioning e auto-join (D-02)
- ✓ Migration Alembic para redesenho de `family_invitation` criada (`20260526_1500_redesign_family_invitation_pre_register.py`)

### Validated in Phase 1 (2026-05-24)

- ✓ Modelo `User` corrigido no DSL: `hashed_password`, `google_id` removidos; `idp_sub` (JWT `sub` do Keycloak) adicionado — `dsl/entities/user.yaml`, `src/caramello/models/user.py`
- ✓ `ruff` e `mypy` configurados com postura strict em `pyproject.toml` — ambos passam sem erros
- ✓ `.env.example` atualizado para `familia_dev` / `familia_prod` e variáveis do Keycloak
- ✓ CORS configurado no `main.py` com `CORS_ORIGINS` lido do `settings`
- ✓ Migração Alembic inicial recriada com schema correto (pending: validar no banco real via UAT)

### Out of Scope

- Domínio `financeiro` — Milestone 2; começa depois que a fundação do M1 estiver publicada
- Domínio `lista_compras` — Milestone 3
- Demais domínios (agenda, saúde, entretenimento) — milestones futuros a definir
- Frontend React/Capacitor — repositório separado (`caramello-app`)
- Autenticação local com senha — removida; Keycloak é o único provedor de identidade
- Multi-tenancy entre grupos — este repo serve exclusivamente o Grupo Família

## Context

**Brownfield com fundação parcial.** O projeto existe mas está pausado antes de qualquer autenticação ou lógica de negócio. O que há é esqueleto técnico com gaps críticos mapeados em `docs/pivot-point.md` e auditados em `.planning/codebase/CONCERNS.md`.

**Decisão de auth mudou.** A documentação (`docs/apps-platform.md`) define Logto como provedor de identidade. A decisão foi revisada: **Keycloak** é o provedor atual, com clients configurados para dev e prod. O Keycloak já está rodando em infra existente.

**MCP como cidadão de primeira classe.** A separação de lógica em `services.py` por domínio é o que permite que os endpoints MCP sejam wrappers finos sobre código já testado — sem duplicação. O `fastapi-mcp` integra o servidor MCP diretamente na app FastAPI.

**DSL permanece e evolui.** O gerador atual outputa código flat (`models/`, `api/generated/`). A decisão é evoluí-lo para suportar um campo `domain` nas definições YAML e outputar em `domains/{domain}/`. Isso mantém o automatismo sem abandonar a arquitetura por domínios.

**Padrão Docker.** O `hiring-pipeline` (Next.js) é a referência de padrão operacional: multi-stage build, non-root user, env injection via compose, `APP_VERSION` como build arg. A adaptação para Python/FastAPI seguirá os mesmos princípios.

**Escala:** 1 a 5 usuários simultâneos. Performance não é prioridade. Simplicidade operacional, manutenibilidade e evolução gradual são.

## Constraints

- **Stack**: Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL obrigatório — não há suporte a SQLite
- **Auth**: Keycloak com OIDC/JWT — clients de dev e prod já configurados na infra existente
- **DB naming**: `familia_dev` (dev) e `familia_prod` (prod) — convenção definida em `docs/apps-platform.md` §5
- **Código gerado**: arquivos em `src/caramello/domains/*/` gerados pelo DSL **não devem ser editados diretamente** — editar o YAML e regenerar
- **Escopo do repo**: apenas Grupo Família — sem tabelas compartilhadas com outros grupos

## Key Decisions

| Decisão | Rationale | Outcome |
|---------|-----------|---------|
| Keycloak como provedor de auth (reverte Logto) | Keycloak já está rodando com clients configurados para dev e prod; pragmatismo sobre a decisão arquitetural prévia | — Pendente |
| DSL evoluído para suportar `domain` field | Mantém automatismo de geração de código sem abrir mão da arquitetura por domínios | — Pendente |
| MCP integrado via `fastapi-mcp` (não servidor separado) | Reutiliza os mesmos `services.py`, mesma app, sem overhead operacional de serviço separado | — Pendente |
| Docker padrão do `hiring-pipeline` adaptado para Python | Multi-stage, non-root, env injection — padrão já validado no ecossistema pessoal | — Pendente |
| `familia` como nome do primeiro domínio piloto | Já definido em `docs/apps-platform.md` §3; cobre User, Family, FamilyMember, FamilyInvitation | — Pendente |
| Domínio `User` encapsulado em `shared/` | User é cross-domain (provisioning no primeiro acesso); não pertence a um domínio de negócio específico | — Pendente |
| Alembic migration inicial descartada e recriada | A migração existente foi gerada com o modelo errado (`hashed_password`, `google_id`) | — Pendente |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-26 after Phase 4 completion (Domínio Family) — domínio families com 6 endpoints operacionais, auto-join via Keycloak, migration Alembic, DSL generator evoluído para arquitetura por domínios. 31 testes passando. Próxima fase: MCP, testes e Docker.*
