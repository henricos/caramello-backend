# Contexto e Diretrizes — Backend

## DSL First

O DSL em `dsl/` é **sempre a origem do código**. Nunca escreva código gerado diretamente.

### Entidades (`dsl/entities/*.yaml`)

Os arquivos abaixo são **gerados automaticamente** — nunca edite:
- `src/caramello/{domain}/models.py`
- `src/caramello/{domain}/router.py`

Fluxo obrigatório: editar YAML → `bin/generate_code` → validar com `bin/validate_generation`.

### Operações de negócio (`dsl/operations/{domain}.yaml`)

Endpoints de negócio em `{domain}/operations.py` também seguem DSL First — **sem exceções**.

Fluxo obrigatório para qualquer novo endpoint:
1. Declarar a operação em `dsl/operations/{domain}.yaml`
2. Rodar `bin/generate_code` → cria stub com `raise NotImplementedError`
3. Implementar o stub

Nunca adicione endpoints diretamente em `operations.py` sem passar pelo DSL. Se `operations.py` estiver marcado `# CARAMELLO-GENERATED: implemented`, isso não é licença para adicionar rotas sem DSL — apenas autoriza editar implementações já declaradas.

Regras detalhadas: `docs/dsl_rules.md`.

---

## Identificadores públicos

- Toda entidade expõe `id` (int, PK interna) e `uuid` (UUID, identificador público).
- URLs e respostas de API usam **sempre `uuid`**, nunca `id`.
- A flag `expose_as_uuid` no DSL controla esse comportamento nas referências de entidade.

---

## Autenticação e autorização

- Auth via **Keycloak** com OIDC/JWT.
- Clients `dev` e `prod` já configurados na infra. Não criar novos clients sem alinhamento.
- Endpoints gerados são públicos por padrão — proteção deve ser adicionada explicitamente via dependência FastAPI.
- A api é **resource server OAuth2**: valida o `access_token` de qualquer consumidor por conta própria (JWKS/RS256, `iss`, `exp` e `aud` com a audience da própria api). Nunca aceite token sem validar `aud`.
- Autorização tem **duas camadas**, ambas atrás de `get_current_user` em `shared/auth.py`: allowlist de e-mail (`allowed_emails` — pode usar o sistema?) e pertencimento a família (quais dados alcança?).
- A **ordem** das verificações é invariante: `email_verified` é checado **antes de qualquer consulta ao banco** (sem custo e sem sinal de timing do allowlist) e nenhum corpo de erro pode conter o e-mail do chamador.
- `allowed_emails` é infraestrutura, não entidade de negócio: mora em `shared/models.py` (fora do alcance do gerador do DSL), não tem `uuid` e não tem rota — administração é via `scripts/seed_allowed_email.py` / `scripts/remove_allowed_email.py`.

---

## Estrutura de módulos

Cada domínio de negócio é um módulo isolado em `src/caramello/domains/`. Módulos não devem importar diretamente a camada interna de outros módulos — use contratos (schemas) ou serviços compartilhados.

Camadas dentro de cada módulo:
- `models.py` — ORM/tabelas (gerado)
- `router.py` — CRUD gerado (gerado)
- `operations.py` — endpoints de negócio (stub gerado, implementação manual)
- `services/` — lógica de negócio
- `repositories/` — acesso a dados

---

## Invariantes a preservar

- Driver de banco é `psycopg2-binary` (síncrono). Qualquer adoção de async exige migração para `asyncpg` e sessão async do SQLAlchemy — não misture os dois.
- `DATABASE_URL` é construída em `src/caramello/core/config.py` a partir de variáveis individuais — não leia diretamente da env.
- Migrações sempre via Alembic. Nunca altere schema diretamente no banco.
- Escopo do repo: apenas **Grupo Família** — sem tabelas compartilhadas com outros grupos.
