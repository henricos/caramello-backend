# Project Research Summary

**Project:** caramello-api — Milestone 1: Fundação
**Domain:** Backend FastAPI brownfield — async migration, auth Keycloak, MCP integrado
**Researched:** 2026-05-23
**Confidence:** HIGH

## Executive Summary

O caramello-api é um backend Python/FastAPI em estágio brownfield: a infraestrutura de base existe (DSL generator, Alembic, 4 entidades no schema), mas está tecnicamente incorreta em três dimensões críticas — modelo `User` com campos de auth descartados (`hashed_password`, `google_id`), driver de banco síncrono (`psycopg2-binary`) bloqueando o event loop, e endpoints sem nenhuma autenticação. O Milestone 1 não é construção de features novas: é a correção da fundação para que ela possa sustentar crescimento. A ordem de execução é estritamente determinada por dependências: driver async primeiro, pois tudo mais depende de `AsyncSession` funcionando corretamente.

A abordagem recomendada é: substituir o driver síncrono por `asyncpg` com `SQLAlchemy 2.0 async`, corrigir o modelo `User` para usar `idp_sub` (claim `sub` do JWT Keycloak), reorganizar a estrutura de código para o padrão por domínios (`domains/`, `shared/`), implementar validação JWT local com `PyJWT[crypto]` e `PyJWKClient` com cache, e adicionar o servidor MCP via `fastapi-mcp` como extensão da mesma app FastAPI. Os 11 table stakes identificados são todos obrigatórios — nenhum pode ser movido para depois sem comprometer a correção técnica da fundação.

Os riscos mais críticos são silenciosos: `create_engine` síncrono coexistindo com `AsyncSession` falha apenas sob carga; `aud` ausente no Keycloak causa `InvalidAudienceError` apenas em ambiente de dev sem roles configurados; o `env.py` do Alembic não adaptado para async trava sem mensagem clara. A mitigação é fazer substituições atômicas (substituir `session.py` inteiro de uma vez, não incrementalmente), validar com `grep` artefatos do driver antigo, e configurar o Audience Mapper no Keycloak antes de testar auth.

## Key Findings

### Stack Recomendado

| Tecnologia | Versão | Papel |
|------------|--------|-------|
| Python | 3.12 | Runtime — melhor suporte de ferramentas; 3.10+ obrigatório |
| FastAPI | ≥0.100.0 | Framework web async — decisão existente, compatível com fastapi-mcp |
| asyncpg | 0.31.0 | Driver PostgreSQL async nativo — substituto de psycopg2-binary |
| SQLAlchemy | ≥2.0 | ORM async — `create_async_engine` + `async_sessionmaker` + `AsyncSession` |
| SQLModel | 0.0.38 | Modelos Pydantic+SA — usar SA diretamente para AsyncSession |
| PyJWT[crypto] | 2.13.0 | Validação JWT RS256 — `PyJWKClient` com cache; python-jose descartado (abandonado) |
| fastapi-mcp | 0.4.0 | Servidor MCP integrado via ASGI — sem serviço separado |
| pytest-asyncio | 1.3.0 | Testes async — `asyncio_mode = "auto"` obrigatório |
| uv | atual | Gerenciador de pacotes — multi-stage Docker com `UV_LINK_MODE=copy` |

**Nota crítica:** SQLModel 0.0.38 não tem wrappers async próprios. `AsyncSession` e `create_async_engine` vêm de `sqlalchemy.ext.asyncio`. O generator DSL atual produz routers síncronos — precisam ser atualizados para `async def` junto com a migração do driver.

### Features Table Stakes do M1

Todos os 11 table stakes são obrigatórios. Ordem reflete dependências:

- **TS-1: asyncpg + AsyncSession** — desbloqueador de tudo; FastAPI sem async I/O real não é async
- **TS-2: Modelo User correto** (`idp_sub`, sem senha local) — cada schema gerado hoje está errado (G1)
- **TS-3: shared/auth.py** com validação JWT Keycloak + JIT provisioning — todos os endpoints são públicos hoje (G2)
- **TS-4: Estrutura por domínios** (`domains/`, `shared/`) — prerequisito para MCP e para escalar domínios futuros
- **TS-5: Endpoints do domínio familia** funcionais e protegidos — validação end-to-end da fundação
- **TS-6: fastapi-mcp integrado** — MCP é requisito do M1, não diferenciador futuro
- **TS-7: Dockerfile multi-stage** com non-root user — sem Docker não há deployment path
- **TS-8: Infraestrutura de testes** — pytest + pytest-asyncio + fixtures isoladas
- **TS-9: ruff + mypy configurados** — exigência de `docs/quality_rules.md`; ausentes no `pyproject.toml`
- **TS-10: CORS configurado** — sem CORS o frontend React/Capacitor é bloqueado
- **TS-11: Migration Alembic recriada** — a existente foi gerada com modelo errado

**Anti-features a nunca construir:**
- Autenticação local com senha — Keycloak é o único IdP
- Middleware global de auth — `Depends(get_current_user)` por router é o padrão correto
- Token introspection remota por request — validação local com JWKS cacheado
- Servidor MCP separado — `fastapi-mcp` via ASGI na mesma app
- `response_model=SQLModelTableClass` diretamente — sempre usar schema `*Read` separado

### Decisões Arquiteturais Críticas

| Componente | Responsabilidade |
|------------|-----------------|
| `main.py` | App factory: registra routers, monta MCP depois de todos os routers, configura CORS |
| `shared/auth.py` | Validação JWT RS256 via Keycloak JWKS (local, sem round-trip), JIT provisioning de User |
| `shared/database.py` | `AsyncEngine` + `get_session()` com `expire_on_commit=False` |
| `domains/familia/models.py` | SQLModel table definitions — gerado pelo DSL (com campo `domain: familia`) |
| `domains/familia/schemas.py` | Schemas Pydantic Read/Create/Update — gerado pelo DSL |
| `domains/familia/services.py` | Lógica de negócio pura — sem imports de FastAPI |
| `domains/familia/routes.py` | `APIRouter` com `Depends(get_current_user)` — wrappers finos sobre services |
| fastapi-mcp | Montado em `main.py` via `include_tags=["familia"]` — expõe endpoints como tools MCP |
| `alembic/env.py` | Reescrito para async com `NullPool`; importa modelos de todos os domínios explicitamente |

**Prefixo vs. versionamento:** prefixo por domínio sem `/v1/` — não existe compatibilidade retroativa com cliente único sob controle total. Resultado: `GET /familia/families/{id}`.

**DSL generator:** precisa de campo `domain` nos YAMLs. O generator produz apenas `models.py` e `schemas.py` — `services.py` e `routes.py` são sempre manuais.

### Armadilhas Críticas a Evitar

1. **`create_engine` síncrono coexistindo com `create_async_engine`** — falha silenciosa sob carga. Substituir `session.py` inteiro; validar com `grep -r "create_engine" src/` após migração.

2. **Lazy loading de relacionamentos com `AsyncSession`** — `Relationship()` sem `lazy` lança `MissingGreenletError` apenas ao serializar. Usar `selectinload` explícito; atualizar DSL generator para emitir `lazy="raise"`.

3. **`aud` ausente no token Keycloak** — sem Audience Mapper configurado no client, `InvalidAudienceError` em produção. Configurar o mapper antes de testar auth.

4. **Race condition no JIT provisioning** — dois requests simultâneos do mesmo user criam registro duplicado. Usar `INSERT ... ON CONFLICT DO NOTHING` com constraint `UNIQUE(idp_sub)`.

5. **`FastApiMCP` instanciado antes dos `include_router`** — endpoints adicionados depois não aparecem no MCP. Instanciar no final de `main.py`.

6. **Alembic `env.py` não adaptado para async** — trava sem mensagem clara. Reescrever com template async (`async_engine_from_config` + `NullPool`).

7. **`UV_LINK_MODE` não configurado no Dockerfile** — symlinks do `.venv` do builder quebram no runtime. `ENV UV_LINK_MODE=copy` é obrigatório no stage builder.

## Implications for Roadmap

### Fase 1: Correção do Modelo e Infra Base
**Entrega:** modelo `User` com `idp_sub`, migration descartada, ruff/mypy, CORS
**Aborda:** TS-2, TS-9, TS-10, TS-11

### Fase 2: Stack Async
**Entrega:** asyncpg + AsyncSession + Alembic async + DSL generator emitindo `async def`
**Aborda:** TS-1, parte do TS-8
**Evita:** PITFALL migração psycopg2→asyncpg (4 armadilhas)

### Fase 3: Estrutura por Domínios e Autenticação
**Entrega:** estrutura `domains/familia/` + `shared/`, `shared/auth.py` com JWKS cache, endpoints REST familia protegidos, DSL generator com campo `domain`
**Aborda:** TS-3, TS-4, TS-5
**⚠ Precisa antes:** confirmar realm name, audience claim e client ID do Keycloak existente

### Fase 4: MCP + Testes + Docker
**Entrega:** fastapi-mcp com `include_tags=["familia"]` + `AuthConfig`, fixtures isoladas, Dockerfile multi-stage
**Aborda:** TS-6, TS-7, TS-8

### Ordem de Implementação

```
TS-9 + TS-10 (zero deps, trivial)
  → TS-1 (desbloqueador universal)
    → TS-2 + TS-11 (modelo correto + migration recriada juntos)
      → TS-4 (estrutura; poucos arquivos para mover enquanto é cedo)
        → TS-3 (auth depende de User e estrutura no lugar)
          → TS-5 (endpoints dependem de tudo acima)
            → TS-8 (testes mais eficientes com estrutura estável)
            → TS-6 (MCP são 3 linhas se TS-5 estiver correto)
TS-7 (Docker) — independente, pode ser paralelo; bloqueante para deploy
```

## Questões em Aberto — Validação Operacional Necessária

Antes de implementar `shared/auth.py` (Fase 3), confirmar contra a instância Keycloak existente:

| Questão | Por que importa |
|---------|----------------|
| **Keycloak realm name** | Necessário para `KEYCLOAK_ISSUER` e `KEYCLOAK_JWKS_URL` |
| **Audience claim (`aud`)** | Valor real emitido nos tokens — `client_id` ou `"account"`? Determina `audience=` no `jwt.decode()` |
| **Keycloak client ID** | Parte das env vars de configuração |
| **`uv.lock` no repositório** | Necessário para `uv sync --locked` no Dockerfile |

## Confidence Assessment

| Área | Confiança | Notas |
|------|-----------|-------|
| Stack (versões e configuração) | HIGH | Versões verificadas no PyPI; padrões em docs oficiais e Context7 |
| Features (table stakes) | HIGH | Gaps mapeados no codebase; sem ambiguidade |
| Architecture | HIGH | Docs oficiais FastAPI + fastapi-mcp + codebase inspecionado |
| Pitfalls | HIGH | Bugs confirmados no `generate_code.py` existente; comportamentos documentados |
| Configuração Keycloak | MEDIUM | Depende de valores operacionais da instância existente |

---
*Pesquisa concluída: 2026-05-23 | Pronto para roadmap: sim*
