# Phase 1: Infra Base - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-24
**Phase:** 1-Infra Base
**Areas discussed:** Escopo da migration, Postura do ruff/mypy, CORS origins, Artefatos obsoletos

---

## Escopo da migration

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Todas as 4 tabelas | Migration inicial limpa cobrindo User, Family, FamilyMember, FamilyInvitation | ✓ |
| Só o User | Recriar migration apenas para o User; outras tabelas ficam para depois | |
| Todas via autogenerate | Corrigir user.yaml e deixar Alembic detectar tudo automaticamente | |

**Escolha do usuário:** Todas as 4 tabelas (opção recomendada)
**Notas:** Uma migration inicial completa é mais consistente para onboarding e garante que `alembic upgrade head` em banco limpo cria o schema inteiro.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| PK do User: int+uuid vs UUID puro | Manter int id + uuid (padrão atual) | UUID como única PK | int+uuid mantidos |

**Escolha do usuário:** Manter padrão int id + uuid — mas lembrar de adicionar `idp_sub` (UNIQUE) para vínculo com Keycloak
**Notas:** `idp_sub` é o JWT `sub` claim do Keycloak. O usuário confirmou que este campo deve ser `NOT NULL UNIQUE`.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| datetime.utcnow: corrigir agora ou Phase 2? | Corrigir o gerador agora | Deixar para Phase 2 | Corrigir agora |

**Escolha do usuário:** Corrigir agora (opção recomendada)
**Notas:** O gerador já está sendo tocado para o fix do User model. Pequena mudança (`datetime.now(UTC)`) que evita warnings em Python 3.12+ e deixa a Phase 2 herdar um gerador mais limpo.

---

## Postura do ruff/mypy

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Lenient + ignores explícitos | per-file-ignores para diretórios que serão removidos/reescritos | |
| Strict desde já | Regras rigorosas, corrigir o código atual para passar | ✓ |

**Escolha do usuário:** Strict desde já
**Notas:** O usuário quer código de qualidade desde o início, sem atalhos.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| Código gerado: como fazer passar no strict? | Corrigir o gerador DSL | per-file-ignores só para gerados | Corrigir o gerador |

**Escolha do usuário:** Corrigir o gerador (opção recomendada)
**Notas:** Correções no gerador persistem a cada regeneração. Editar arquivos gerados seria perdido no próximo `generate_code`.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| Arquivos vazios no mypy: como tratar? | Remover arquivos vazios | Adicionar type: ignore | Remover |

**Escolha do usuário:** Remover arquivos vazios (opção recomendada)
**Notas:** services/user.py, repositories/user.py, exceptions.py, http_errors.py, api/v1/routes.py, api/v1/users.py — nenhum contribui nada e serão recriados corretamente nas fases seguintes.

---

## CORS origins

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Lista explícita via env var | CORS_ORIGINS como env var, lista de URLs | ✓ |
| Wildcard `*` em dev | allow_origins=["*"] | |
| Hardcoded por ENVIRONMENT | Lista fixa baseada no ENVIRONMENT var | |

**Escolha do usuário:** Lista explícita via env var (opção recomendada)
**Notas:** Padrão seguro e flexível. Dev: `http://localhost:3000,http://localhost:5173`. Produção: domínio definitivo quando definido.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| allow_methods e allow_headers: permissivo ou explícito? | Permissivo (["*"]) | Explícito e mínimo | Permissivo |

**Escolha do usuário:** Permissivo (opção recomendada)
**Notas:** Para 1-5 usuários em ambiente familiar, simplicidade prevalece.

---

## Artefatos obsoletos

| Opção | Descrição | Selecionada |
|-------|-----------|-------------|
| Remover tudo que é morto | api_schemas.py, tests/generated/, test_generated_api.py | ✓ |
| Manter tudo | Deixar para Phase 3/5 | |
| Remover só o que impede ruff/mypy | Remoção cirúrgica | |

**Escolha do usuário:** Remover tudo que é morto (opção recomendada)
**Notas:** `schemas/generated/api_schemas.py` nunca foi usado por nenhum router. `tests/generated/` usa banco de produção sem fixtures. `test_generated_api.py` tem assertions erradas e nunca passou.

---

| Pergunta | Opção A | Opção B | Selecionada |
|----------|---------|---------|-------------|
| `api/v1/`: remover ou manter como placeholder? | Remover (sem versioning por ora) | Manter como estrutura base | Remover |

**Escolha do usuário:** Remover (opção recomendada)
**Contexto extra:** O usuário não sabia se URL versioning era boa prática. Foi explicado que para APIs internas com consumidores controlados (frontend próprio, agentes próprios), versioning no URL adiciona overhead sem benefício. A decisão foi: sem `/v1/` por enquanto; adicionar quando e se surgir necessidade real de v2.

---

## Claude's Discretion

Nenhuma área delegada à decisão do Claude — o usuário tomou todas as decisões explicitamente.

## Deferred Ideas

- `GET /health` endpoint com ping ao banco (OPS-01) — útil mas fora do escopo desta fase
- SSL no DATABASE_URL em produção (`sslmode=require`) — OPS-03, resolve no deploy (Phase 5)
- Logging estruturado em JSON (`structlog`) — OPS-02, milestone posterior
- CI pipeline (GitHub Actions) — OPS-04, pós-fundação
