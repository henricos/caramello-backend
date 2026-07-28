# Caramello API

## What This Is

Backend Python/FastAPI do sistema Caramello — plataforma pessoal e familiar para centralizar agenda, finanças, listas de compras, saúde e entretenimento. Serve um grupo fechado de 1 a 5 usuários (membros da família), com autenticação via Keycloak e dados organizados por domínios de negócio. Destinado a ser consumido por um frontend React/Capacitor (mobile-first) e por agentes de IA via MCP.

## Core Value

Um backend sólido, seguro e extensível onde cada novo domínio de negócio (financeiro, agenda, compras…) pode ser adicionado sem tocar no que já existe.

## Current State — v2.0 (SHIPPED 2026-06-04)

O domínio financeiro está completo. O projeto tem dois domínios de negócio funcionais (families + finances) e está pronto para receber o próximo domínio.

**O que existe:**
- Stack async: FastAPI + asyncpg + AsyncSession + Alembic async
- Auth: Keycloak JWT com validação local (JWKS cache), JIT provisioning, auto-join por email
- Domínio `users`: `GET /users/me` + CRUD gerado
- Domínio `families`: 6 endpoints de negócio + CRUD gerado + pré-registro por email
- Domínio `finances`: 25 endpoints — CRUD Account/Category/Subcategory, Movements (registro + importação CSV/OFX/XLSX), conciliação, saldos e relatórios analíticos
- MCP: `/mcp` expondo `list_my_families` com auth Bearer obrigatória
- Docker: Dockerfile multi-stage non-root + compose.yaml
- Testes: 85 testes unitários + 4 stubs de integração (necessitam banco real)
- DSL generator: YAML → models.py + router.py + operations.py; suporta Decimal→NUMERIC(15,2), filters→Index, expose_as_uuid
- Migrations: 0001 (schema inicial), 0002 (finances schema), 0003 (movement fields), 0004 (financial_entry responsible_user)

**UAT pendente (requer ambiente real):**
- `docker compose up` com PostgreSQL + Keycloak
- `pytest -m integration` contra `caramello_dev`
- MCP Inspector com Bearer token Keycloak real
- Teste de importação OFX com extrato real de banco BR

## Constraints

- **Stack**: Python 3.10+, FastAPI async, SQLModel/SQLAlchemy async, PostgreSQL obrigatório
- **Auth**: Keycloak com OIDC/JWT — clients dev/prod configurados em infra existente
- **DB naming**: `caramello_dev` (dev), `caramello` (prod)
- **Código gerado**: `models.py` e `router.py` em `src/caramello/{domain}/` — editar YAML e regenerar
- **Escopo do repo**: apenas Grupo Família

## Key Decisions

| Decisão | Rationale | Outcome |
|---------|-----------|---------|
| Keycloak como provedor de auth (reverteu Logto) | Keycloak já em infra com clients dev/prod configurados | ✅ Implementado — shared/auth.py |
| DSL com campo `domain` por entidade | Mantém automatismo de geração sem abrir mão da arquitetura por domínios | ✅ Implementado — scripts/generate_code.py |
| MCP via fastapi-mcp (não servidor separado) | Reutiliza services.py, mesma app, sem overhead operacional adicional | ✅ Implementado — /mcp com whitelist |
| Dockerfile padrão multi-stage non-root | Padrão já validado no ecossistema pessoal (hiring-pipeline) | ✅ Implementado — Dockerfile + compose.yaml |
| FamilyInvitation redesenhada: pré-registro por email | Adequado ao grupo familiar fechado — sem convite público por código (M1) | ✅ Implementado — D-01/D-02 |
| FAMILY-04/05/06 deferidos para M2 | Fluxo de convite reutilizável fora do escopo do grupo fechado de 1-5 usuários | ⏭ Deferido — D-04 |
| Testes contra caramello_dev com rollback por savepoint | Sem banco separado caramello_test; isolamento via transação revertida | ✅ Implementado — D-TEST-01 |
| Migration única 0001_initial_schema.py | 2 migrations anteriores nunca executadas em banco real; consolidadas em uma limpa | ✅ Implementado — M1 close |
| Precisão monetária: `Decimal` no DSL → `NUMERIC(15,2)` no banco | Zero `float` em campos de valor — pitfall P1 eliminado pelo gerador | ✅ Implementado — Phase 6 — scripts/generate_code.py |
| Hierarquia Category+Subcategory (2 entidades, D-06) | Substitui self-referencial com pós-processamento manual; 2 níveis enforced pelo schema | ✅ Implementado — Phase 6 — dsl/entities/category.yaml + subcategory.yaml |
| `filters:` no DSL → `__table_args__` com `Index` (D-11) | Índices declarados na fonte de verdade YAML, nunca editados manualmente nos models | ✅ Implementado — Phase 6 — scripts/generate_code.py `_build_table_args` |
| `naming_convention` em alembic/env.py antes dos imports de modelo | Constraints recebem nomes determinísticos no PostgreSQL — reverter/recriar sem nome aleatório | ✅ Implementado — Phase 6 — alembic/env.py |
| `expose_as_uuid: true` no DSL | FKs int nunca vazam para schemas públicos — ID interno fica na tabela, UUID exposto nos schemas | ✅ Implementado — Post-M2 — scripts/generate_code.py |
| DSL operations syncronizado retroativamente | finances/operations.py tinha 25 endpoints sem entrada no DSL — sincronizado e regra DSL-first reforçada | ✅ Implementado — Post-M2 — dsl/operations/finances.yaml |
| D-MCP-01: MCP financeiro deferido para M3 | APIs e services devem amadurecer antes de exposição via MCP | ⏭ Deferido — M3 |

## Out of Scope (permanente)

- Frontend React/Capacitor — módulo `apps/frontend` neste monorepo (ainda não iniciado)
- Autenticação local com senha — Keycloak é o único IdP
- Multi-tenancy entre grupos — este repo serve exclusivamente o Grupo Família
- Token introspection remota — validação local com JWKS cacheado

---
*Last updated: 2026-06-04 — Milestone v2.0 Domínio Financeiro fechado formalmente. 25 endpoints de finances, 85 testes, DSL sincronizado. Próximo milestone a definir com `/gsd-new-milestone`.*
