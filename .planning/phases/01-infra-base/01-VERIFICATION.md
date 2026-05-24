---
phase: 01-infra-base
verified: 2026-05-24T12:00:00Z
status: human_needed
score: 4/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Executar `uv run alembic upgrade head` com banco PostgreSQL familia_dev vazio"
    expected: "Comando conclui sem erro; `\\dt` lista user, family, family_member, family_invitation; `\\d user` mostra id, uuid, idp_sub, email, name, created_at, updated_at — SEM hashed_password, google_id, phone_number, is_active"
    why_human: "SC2 requer banco PostgreSQL acessível. Plan 04 contém task `checkpoint:human-verify gate=blocking`. Sem banco disponível no ambiente de CI/verificação automática."
---

# Phase 1: Infra Base — Verification Report

**Phase Goal:** A fundação técnica está correta — modelo User sem campos de auth local, migration limpa aplicável em banco vazio, linting e type-check configurados, CORS habilitado para o frontend
**Verified:** 2026-05-24T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Tabela `user` não contém colunas de auth local (`hashed_password`, `google_id`, `phone_number`, `is_active`) — apenas `idp_sub`, `email`, `name`, `uuid`, `id`, `created_at`, `updated_at` | ✓ VERIFIED | `alembic/versions/20260524_0138_initial_schema.py` e `src/caramello/models/user.py`: grep confirma ausência de todos os campos auth-local; `idp_sub` com `UniqueConstraint` presente. DSL `dsl/entities/user.yaml` sem campos removidos. |
| 2 | `alembic upgrade head` em banco limpo `familia_dev` conclui sem erro | ? UNCERTAIN | Migration estruturalmente correta (sintaxe válida, FKs na ordem certa, campo `idp_sub` presente), mas execução real requer banco PostgreSQL. Plan 04 tem `checkpoint:human-verify gate=blocking` ainda pendente per SUMMARY 04. |
| 3 | `ruff check src/` e `mypy src/` passam sem erros — configurados em `pyproject.toml` | ✓ VERIFIED | Executado: `uv run ruff check src/` → "All checks passed!" (exit 0). `uv run mypy src/` → "Success: no issues found in 9 source files" (exit 0). Configurações presentes em `pyproject.toml` com `[tool.ruff]` e `[tool.mypy]`. |
| 4 | Frontend React/Capacitor em `localhost` recebe respostas sem erro de CORS — `CORSMiddleware` presente em `main.py` | ✓ VERIFIED | `src/caramello/main.py` contém `CORSMiddleware` com `allow_origins=settings.CORS_ORIGINS`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. `CORS_ORIGINS` em `Settings` com default `["http://localhost:3000", "http://localhost:5173"]`. Link settings→main verificado. |
| 5 | `.env.example` documenta convenção `familia_dev`/`familia_prod` e variáveis Keycloak | ✓ VERIFIED | `.env.example` contém `DB_NAME=familia_dev`, comentário explícito "familia_dev (dev) e familia_prod (prod)", `CORS_ORIGINS`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`. Nota: SC5 do ROADMAP menciona `DATABASE_URL` explicitamente, mas `config.py` constrói a URL programaticamente a partir de componentes `DB_*` — o `.env.example` reflete corretamente a arquitetura atual. |

**Score:** 4/5 truths verified (SC2 aguarda confirmação humana)

**Nota sobre nomenclatura:** ROADMAP SC1 e REQUIREMENTS MODEL-01 referenciam tabela `users` (plural), mas `docs/dsl_rules.md` §table_name define explicitamente "Snake case, SINGULAR". Todo o código, DSL e migration usam `user` (singular). Tratado como inconsistência tipográfica na documentação de planejamento — não é falha de implementação.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `dsl/entities/user.yaml` | Definição canônica User Keycloak-aligned com `idp_sub` | ✓ VERIFIED | Contém `idp_sub`, `email`, `name`. Sem `hashed_password`, `phone_number`, `google_id`, `avatar_url`, `is_active`. |
| `scripts/generate_code.py` | Gerador DSL com `datetime.now(timezone.utc)` | ✓ VERIFIED | Linha 96: `field_args.append("default_factory=lambda: datetime.now(timezone.utc)")`. Sem nenhuma ocorrência de `utcnow` em código não-comentado. |
| `src/caramello/models/user.py` | Modelo ORM User regenerado com `idp_sub` | ✓ VERIFIED | Contém `idp_sub` (linha 14), `from datetime import datetime, timezone` (linha 3), `lambda: datetime.now(timezone.utc)` nas linhas 17-18. Sintaxe Python válida. |
| `pyproject.toml` | Configuração ruff e mypy com `[tool.ruff]` | ✓ VERIFIED | Contém `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.mypy]`. ruff e mypy presentes em `[dependency-groups] dev`. |
| `src/caramello/core/config.py` | Settings com `CORS_ORIGINS` como lista | ✓ VERIFIED | `CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]` na linha 26. |
| `src/caramello/main.py` | App FastAPI com CORSMiddleware conectado ao settings | ✓ VERIFIED | `CORSMiddleware` com `allow_origins=settings.CORS_ORIGINS`. Import de `settings` de `caramello.core.config`. |
| `.env.example` | Variáveis de ambiente documentadas com Keycloak | ✓ VERIFIED | Contém `DB_NAME=familia_dev`, `CORS_ORIGINS`, `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`. |
| `alembic/versions/20260524_0138_initial_schema.py` | Migration inicial limpa com `idp_sub` | ✓ VERIFIED | Único arquivo em `alembic/versions/` (exceto `__pycache__`). Contém `op.create_table('user', ...)` com `Column('idp_sub', ...)` e `UniqueConstraint('idp_sub')`. Sem campos auth-local. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `dsl/entities/user.yaml` | `src/caramello/models/user.py` | `bin/generate_code` | ✓ WIRED | `idp_sub` presente em ambos. Modelo regenerado reflete o YAML. |
| `scripts/generate_code.py` | `src/caramello/models/user.py` | geração automática | ✓ WIRED | `timezone.utc` no gerador (linha 96) → `datetime.now(timezone.utc)` nos campos `created_at`/`updated_at` do modelo gerado. |
| `src/caramello/core/config.py` | `src/caramello/main.py` | `settings.CORS_ORIGINS` | ✓ WIRED | `from caramello.core.config import settings` no main.py; `allow_origins=settings.CORS_ORIGINS` na linha 20. |
| `.env.example` | `src/caramello/core/config.py` | variável `CORS_ORIGINS` lida pelo pydantic-settings | ✓ WIRED | Campo `CORS_ORIGINS` em Settings com tipo `list[str]`; `.env.example` documenta a variável. |
| `src/caramello/models/user.py` | `alembic/versions/20260524_0138_initial_schema.py` | modelos SQLModel → DDL | ✓ WIRED | Campos `idp_sub`, `email`, `name` no modelo SQLModel mapeiam para colunas idênticas na migration. `UniqueConstraint` presente nos dois. |

### Data-Flow Trace (Level 4)

Não aplicável para esta phase — nenhum componente de renderização dinâmica. Os artefatos são modelos, configurações e migration DDL.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `ruff check src/` passa | `uv run ruff check src/` | "All checks passed!" (exit 0) | ✓ PASS |
| `mypy src/` passa | `uv run mypy src/` | "Success: no issues found in 9 source files" (exit 0) | ✓ PASS |
| `alembic upgrade head` conclui sem erro | Requer banco PostgreSQL `familia_dev` | Não testável sem banco | ? SKIP — roteado para Human Verification |

### Requirements Coverage

| Requirement | Source Plan | Descrição | Status | Evidence |
|-------------|------------|-----------|--------|----------|
| INFRA-02 | 01-02, 01-03, 01-04 | ruff e mypy configurados e passando | ✓ SATISFIED | `ruff check src/` exit 0; `mypy src/` exit 0; `[tool.ruff]` e `[tool.mypy]` em pyproject.toml |
| INFRA-03 | 01-03 | CORSMiddleware configurado em main.py | ✓ SATISFIED | `CORSMiddleware` com `allow_origins=settings.CORS_ORIGINS` em main.py |
| MODEL-01 | 01-01, 01-04 | Tabela `user` sem campos auth-local, com `idp_sub` | ✓ SATISFIED | Migration e modelo confirmados via grep |
| MODEL-02 | 01-04 | Migrations refletem schema correto, aplicáveis em banco limpo | ? NEEDS HUMAN | Migration estruturalmente correta; execução com banco real pendente (checkpoint bloqueante no plan 04) |
| MODEL-03 | 01-03 | Convenção `familia_dev`/`familia_prod` no `.env.example` | ✓ SATISFIED | `.env.example` contém `DB_NAME=familia_dev` e comentário sobre `familia_prod` |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/generate_code.py` | 5 | `from caramello.core.config import settings` — import não utilizado (F401) | ⚠️ Warning | Não bloqueia goal; `ruff check src/` exclui scripts/. Se `ruff check scripts/` for executado, retorna exit 1 com 45 erros (múltiplos UP, F401, E501, E701, F841). `scripts/` não está na lista de exclusão do ruff config, mas o `src` param de `[tool.ruff]` foca a análise em `src/`. |
| `scripts/generate_code.py` | 403-408 | `TESTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)` — gerador recria `tests/generated/` ao ser executado | ⚠️ Warning | Plan 02 removeu `tests/generated/` como artefato obsoleto. Executar `bin/generate_code` novamente recriaria o diretório com testes sem fixtures válidas. Não bloqueia o goal atual, mas inconsistência arquitetural a resolver na Phase 2+. |

### Human Verification Required

#### 1. Migration aplicável em banco vazio (SC2 / MODEL-02)

**Teste:** Garantir que PostgreSQL está rodando, banco `familia_dev` existe (criá-lo com `bin/setup_db` se necessário), copiar `.env.example` para `.env` preenchendo as credenciais reais, e executar:

```bash
uv run alembic upgrade head
```

**Verificações pós-execução:**

```bash
psql -U $DB_USER -d familia_dev -c "\dt"
# Deve listar: user, family, family_member, family_invitation, alembic_version

psql -U $DB_USER -d familia_dev -c "\d user"
# Deve conter: id, uuid, idp_sub, email, name, created_at, updated_at
# NÃO deve conter: hashed_password, google_id, phone_number, is_active
```

**Expected:** Comando conclui com exit 0 sem erros; tabela `user` tem exatamente os campos corretos.

**Why human:** Requer banco PostgreSQL acessível com credenciais reais. Plan 04 inclui task `checkpoint:human-verify gate=blocking` explicitamente pendente. Verificação automática não é possível sem banco.

---

### Gaps Summary

Nenhum gap técnico bloqueante foi encontrado. A única pendência é a verificação humana de SC2 (execução da migration), que foi explicitamente planejada como checkpoint humano no plan 04.

**Itens notáveis (não bloqueantes):**

1. **scripts/generate_code.py tem lint issues** — `ruff check scripts/` retorna 45 erros (UP, F401, E701, F841, E501). O sucesso do SC3 foi definido como `ruff check src/` (escopo `src/`), que passa. A exclusão de `scripts/` do escopo de linting é uma decisão técnica aceitável, mas deveria ser explicitada na configuração ruff.

2. **generate_code.py recria tests/generated/** — O gerador DSL recria o diretório `tests/generated/` ao ser executado, revertendo a remoção do plan 02. Isso não impacta o goal da Phase 1, mas criará ruído se o gerador for executado antes de Phase 5 criar os fixtures corretos.

3. **"users" vs "user" em ROADMAP/REQUIREMENTS** — ROADMAP SC1 e REQUIREMENTS MODEL-01 usam plural "users". Todo o código usa singular "user" per `docs/dsl_rules.md` (convenção normativa). A implementação está correta; a documentação de planejamento contém uma inconsistência tipográfica.

4. **SC5: DATABASE_URL não está no .env.example** — SC5 do ROADMAP menciona "DATABASE_URL". O design atual de `config.py` constrói `DATABASE_URL` programaticamente a partir de `DB_*` vars individuais. O `.env.example` reflete corretamente esse design. A discrepância está na redação do SC, não na implementação.

---

_Verified: 2026-05-24T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
