# Phase 3: Estrutura por Domínios e Autenticação - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 3-Estrutura por Domínios e Autenticação
**Areas discussed:** Keycloak — valores e claims JWT, Biblioteca JWT, Escopo do DSL generator por domínio, Auth nos routers CRUD existentes

---

## Keycloak — valores e claims JWT

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Via env vars em Settings | KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID em config.py. Placeholders já existem no .env.example (Phase 1). | ✓ |
| Hardcoded no shared/auth.py | Valores direto no código. Impede trocar dev/prod sem rebuild. | |
| Arquivo de configuração externo | .well-known OpenID discovery automático. Mais complexo. | |

**User's choice:** Via env vars em Settings

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| familia | realm 'familia' | |
| master | realm padrão do Keycloak | |
| Digitar o valor real | Valor confirmado pelo usuário | ✓ |

**User's choice:** `caramello` — realm confirmado da infra existente

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| client_id (valor de 'aud') | Validar aud == client_id | |
| Sem validação de audience | Só assinatura e expiração | |
| Verificar depois na implementação | Implementador confirma contra instância real antes de definir | ✓ |

**User's choice:** Verificar na implementação

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| name (claim padrão OIDC) | Claim 'name' com nome completo | |
| preferred_username | Username/email do usuário no Keycloak | |
| Tentar 'name', fallback 'preferred_username' | Robusto para diferentes configurações | ✓ |

**User's choice:** Fallback strategy — `name` → `preferred_username`

---

## Biblioteca JWT

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| PyJWT[crypto] | Mantido ativamente, sem CVEs recentes | ✓ |
| python-jose | Popular mas tem CVEs (GHSA-cjwg-qfpm-7377) | |
| authlib | Mais completo, mais pesado para o caso de uso | |

**User's choice:** PyJWT[crypto]

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Cache em memória com TTL | Busca JWKS no lifespan + retry em key rotation | ✓ |
| Cache com TTL explícito | cachetools com TTL configurado | |
| Buscar a cada request | Sem cache — viola AUTH-01 | |

**User's choice:** Cache em memória — busca na inicialização (lifespan) + retry em key rotation

---

## Escopo do DSL generator por domínio

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Só models.py + schemas implicitly | Generator produz models.py por domínio; routers manuais | |
| models.py + router.py gerado | Mantém geração de CRUD, novo output path | |
| models.py + schemas.py separados | Alinhado com apps-platform.md — ORM e DTOs separados | |

**User's choice:** Terceira opção formulada pelo usuário (ver notas)

**Notes:** Usuário propôs uma abordagem mais sofisticada: manter geração de CRUD automática (evita trabalho repetitivo volumoso) E adicionar suporte a "operações de negócio" no DSL. Operações de negócio geram apenas stubs. Como operações podem envolver múltiplas entidades (ex: fluxo de convite envolve User, FamilyInvitation e FamilyMember), a decisão foi: arquivo `dsl/operations/{domain}.yaml` por domínio (não por entidade). Generator produz `src/caramello/{domain}/operations.py` com stubs. Segurança de regeneração via anotação: `# CARAMELLO-GENERATED: stub` (pode sobrescrever) vs `# CARAMELLO-GENERATED: implemented` (protegido).

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Marcador no arquivo gerado | Comentário especial no topo indica estado | |
| Arquivo de lock .generated-stubs.json | Manifesto com hash do conteúdo | |
| Flag implemented: true no YAML | Developer atualiza YAML quando implementa | |

**User's choice (reformulado pelo usuário):** Anotação `# CARAMELLO-GENERATED: stub/implemented` no topo do arquivo. Lógica: se generator encontrar arquivo existente com conteúdo, verifica a anotação. `stub` = sobrescreve livremente. `implemented` = pula. Arquivo vazio = cria normalmente.

---

## Auth nos routers CRUD existentes

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Todos os CRUD recebem Depends(get_current_user) | Template gerado inclui auth em todos os endpoints | ✓ |
| Só /user/me recebe auth, CRUD fica público | Endpoints CRUD públicos até Phase 4 | |
| CRUD gerado é removido | Só operações de negócio ficam | |

**User's choice:** Sim — todos os CRUD recebem auth. Template do generator atualizado para incluir `Depends(get_current_user)`.

---

| Opção | Descrição | Selecionado |
|-------|-----------|-------------|
| Dentro de get_current_user() — centralizado | Todo endpoint protegido provisiona automaticamente | ✓ |
| Só em /user/me | get_current_user() só valida token | |

**User's choice:** JIT provisioning centralizado em `get_current_user()`. Rationale: usuário pediu análise das vantagens/desvantagens antes de decidir. Após análise, escolheu a opção centralizada — Phase 4 (family endpoints) receberá objeto `User` garantidamente presente no banco.

---

## Claude's Discretion

- Formato do `dsl/operations/{domain}.yaml` — a estrutura exata dos campos YAML (method, path, description, etc.) é definida pelo implementador seguindo as convenções da DSL existente
- Dict simples em módulo vs. objeto dedicado de cache JWKS — implementador decide a forma mais limpa dentro de `shared/auth.py`

## Deferred Ideas

- **Operações de negócio de escrita para domínio family** (criar família, convidar, aprovar) — Phase 4
- **Schema de request/response no YAML de operations** — evolução futura do DSL, não Phase 3
- **Stub generation interativa** (perguntar se quer descartar) — o usuário considerou mas preferiu a abordagem de anotação estática
- **GET /health** (OPS-01) — v2 requirements, milestone posterior
- **Logging estruturado structlog** (OPS-02) — milestone posterior
