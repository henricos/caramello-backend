# Caramello API

## What This Is

Backend Python/FastAPI do sistema Caramello — plataforma pessoal e familiar para centralizar agenda, finanças, listas de compras, saúde e entretenimento. Serve um grupo fechado de 1 a 5 usuários (membros da família), com autenticação via Keycloak e dados organizados por domínios de negócio. Destinado a ser consumido por um frontend React/Capacitor (mobile-first) e por agentes de IA via MCP.

## Core Value

Um backend sólido, seguro e extensível onde cada novo domínio de negócio (financeiro, agenda, compras…) pode ser adicionado sem tocar no que já existe.

## Current State — v1.0 (SHIPPED 2026-05-30)

A fundação está completa e pronta para receber novos domínios de negócio.

**O que existe:**
- Stack async: FastAPI + asyncpg + AsyncSession + Alembic async
- Auth: Keycloak JWT com validação local (JWKS cache), JIT provisioning, auto-join por email
- Domínio `users`: `GET /users/me` + CRUD gerado
- Domínio `families`: 6 endpoints de negócio + CRUD gerado + pré-registro por email
- MCP: `/mcp` expondo `list_my_families` com auth Bearer obrigatória
- Docker: Dockerfile multi-stage non-root + compose.yaml + APP_VERSION na spec
- Testes: 36 testes unitários + 4 testes de integração (stub, necessitam banco real)
- DSL generator: YAML → models.py + router.py + operations.py stub por domínio

**UAT pendente (requer ambiente real):**
- `docker build` + inspeção da imagem
- `docker compose up` com PostgreSQL + Keycloak
- `pytest -m integration` contra `caramello_dev`
- MCP Inspector com Bearer token Keycloak real

## Current Milestone — v2.0: Domínio Financeiro

**Goal:** Registrar movimentações brutas por conta, conciliar em lançamentos classificados e analisar por competência e categoria hierárquica.

**Modelo de domínio:**
- `Conta` — conta bancária/cartão/poupança; saldo derivado de movimentações
- `Movimentação` — crédito/débito bruto; entrada individual ou importação em lote com deduplicação
- `Lançamento` — movimentação conciliada 1:1 com categoria (2 níveis) + competência (ano/mês); base de todos os relatórios
- `Categoria` — hierarquia 2 níveis (ex: Transporte > Gasolina), scoped por família

**Target features:**
- CRUD de contas por família
- Registro individual e importação em lote de movimentações (com deduplicação)
- Categorias hierárquicas (2 níveis) por família
- Conciliação semi-automática: sistema propõe categoria por similaridade; usuário confirma
- Criação de lançamento a partir de movimentação conciliada
- Breakdown mensal por categoria pai e subcategoria
- Saldo por conta + consolidado familiar

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

## Out of Scope (permanente)

- Frontend React/Capacitor — repositório separado (`caramello-app`)
- Autenticação local com senha — Keycloak é o único IdP
- Multi-tenancy entre grupos — este repo serve exclusivamente o Grupo Família
- Token introspection remota — validação local com JWKS cacheado

---
*Last updated: 2026-05-31 — Phase 6 completa: schema financeiro fundado (gerador + YAMLs + migration 0002)*
