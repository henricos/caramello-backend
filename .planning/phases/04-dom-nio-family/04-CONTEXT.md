# Phase 4: Domínio Family - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Implementar os endpoints REST do domínio `families` — CRUD gerado com novo padrão de URL, refatoração de URL de todos os domínios existentes, operações de negócio de família (criar família + owner, listar famílias do usuário, pré-registrar membros por email), auto-join de membros no primeiro login e gerenciamento de membros (listar e remover). Todos os endpoints protegidos por auth (`Depends(get_current_user)`).

**Entregável concreto:**
- `POST /families/registry` cria família e registra o usuário autenticado como owner (role="owner") em uma transação
- `GET /families/families` retorna apenas as famílias das quais o usuário autenticado é membro
- `POST /families/families/{family_uuid}/pre-register` registra um email para adesão automática — apenas owner consegue; não-owner recebe 403
- Ao fazer login, se o email do token JWT bater com um `FamilyInvitation` com `status="pending_login"`, o usuário é adicionado como membro automaticamente (`get_current_user()` cuida disso)
- `GET /families/families/{family_uuid}/members` lista membros; `DELETE /families/families/{family_uuid}/members/{user_uuid}` remove membro (owner only)
- URLs de todos os domínios refatoradas: `/user/` → `/users/user/`, `/user/me` → `/users/me`, `/family/` → `/families/family/`, `/family_invitation/` → `/families/family-invitation/`

**Fora de escopo desta fase:**
- Fluxo de convite com código reutilizável, join request e aprovação manual (FAMILY-04/05/06 originais) — deferido para M2 (expansão de produto público)
- Integração Keycloak Admin API para pré-cadastro automatizado no Keycloak (duplo cadastro manual nesta fase)
- Family-scoped CRUD automático no generator (conceito arquitetural deferido — ver D-08)
- Domínio `financeiro`, `lista_compras`, outros — milestones futuros

</domain>

<decisions>
## Implementation Decisions

### Modelo de Pré-cadastro (FamilyInvitation redesenhado)

- **D-01:** `FamilyInvitation` é redesenhado no DSL para o fluxo de pré-cadastro por email. Campos removidos: `invitee_email` (EmailStr), `expires_at`. Campos adicionados: `email` (str — endereço para matching no login), `status` (str, default `"pending_login"`; valores válidos: `"pending_login"`, `"joined"`). Campos mantidos: `id`, `uuid`, `family_id`, `inviter_id`, `created_at`. A entidade deixa de ser "convite por email com expiração" e passa a ser "pré-registro de membro".

- **D-02:** Auto-join integrado em `get_current_user()` em `shared/auth.py`. Fluxo: após JIT provisioning do `User`, busca `FamilyInvitation` com `email == token_email AND status == "pending_login"`. Se existir: cria `FamilyMember(user_id=current_user.id, family_id=inv.family_id, role="member", joined_at=now)` e atualiza `FamilyInvitation.status = "joined"`. Operação atômica na mesma sessão. O auto-join acontece de forma transparente no primeiro login da pessoa.

- **D-03:** Keycloak — duplo cadastro manual para Phase 4. Owner registra a pessoa no Keycloak manualmente (via admin console do Keycloak) E pré-cadastra o email na Caramello API via endpoint de negócio. A Caramello API não chama o Keycloak Admin API nesta fase. Integração Keycloak Admin API deferida para M2+.

- **D-04:** Fluxo FAMILY-04/05/06 original (código de convite reutilizável + POST /family/invitations/{code}/join + PATCH approve/reject) deferido para M2 como expansão de produto. Registrar no ROADMAP.md como requisito deferido.

### Endpoints de Negócio (family/operations.py)

- **D-05:** Operações de negócio do domínio family via DSL First: criar `dsl/operations/family.yaml` com todas as operações → generator produz stubs em `src/caramello/families/operations.py` com anotação `# CARAMELLO-GENERATED: stub` → implementar stubs → alterar anotação para `# CARAMELLO-GENERATED: implemented`. Mesmo padrão de `src/caramello/users/operations.py`.

- **D-06:** `operations.py` exporta `APIRouter` próprio (separado do CRUD em `router.py`). Registrado em `main.py` com include separado. Mesmo padrão de `users/operations.py` que já tem router separado do CRUD.

- **D-07:** Endpoints de negócio a implementar em `families/operations.py`:
  - `POST /families/registry` — cria `Family` + `FamilyMember(role="owner")` na mesma transação
  - `GET /families/families` — lista famílias do usuário autenticado (filtra por membership)
  - `GET /families/families/{family_uuid}` — detalhes da família (verifica se usuário é membro)
  - `POST /families/families/{family_uuid}/pre-register` — owner pré-registra email; não-owner → 403
  - `GET /families/families/{family_uuid}/members` — lista membros (qualquer membro pode ver)
  - `DELETE /families/families/{family_uuid}/members/{user_uuid}` — remove membro (owner only)

### CRUD Gerado e Escopo de Acesso

- **D-08:** CRUD gerado permanece com auth básico (token válido exigido em todos os endpoints — `Depends(get_current_user)` no template). Sem filtros automáticos por família ou role nesta fase. CRUD é considerado "nível de acesso interno/admin" — o frontend usa os endpoints de negócio.

- **D-08-DEFERRED (CONCEITO ARQUITETURAL — NÃO PERDER):**
  **Family-scoped CRUD automático** — visão para M2+:
  O generator deve suportar um campo `family_scope: true` (ou similar) nos YAMLs de entidade. Quando habilitado, o template de CRUD gerado inclui filtros automáticos baseados no contexto do usuário autenticado:
  - `GET /` → `WHERE family_id IN (SELECT family_id FROM family_member WHERE user_id = current_user.id)`
  - `GET /{uuid}` → verifica se o recurso pertence a uma família do usuário
  - `PATCH /{uuid}`, `DELETE /{uuid}` → verifica role (ex.: só owner pode editar/deletar)
  O contexto de família/role pode vir de: (a) consulta extra à tabela `family_member` na dependency, ou (b) claims enriquecidos no JWT via Keycloak Token Mapper. A escolha do mecanismo fica para quando o recurso for implementado. **Esse conceito foi alinhado com o operador e NÃO deve ser re-explicado — só implementado quando a fase for planejada.**

### Refatoração de URL e Convenção de Domínio

- **D-09:** O campo `domain` no YAML de entidade determina TANTO o diretório de output (`src/caramello/{domain}/`) QUANTO o prefixo de URL (`/{domain}/`). O valor é usado exatamente como escrito no YAML — sem auto-pluralização. O operador define o valor correto.

  Atualização dos YAMLs nesta fase:
  - `dsl/entities/user.yaml`: `domain: user` → `domain: users`
  - `dsl/entities/family.yaml`, `family_member.yaml`, `family_invitation.yaml`: `domain: family` → `domain: families`

  Consequência nos diretórios: `src/caramello/user/` → `src/caramello/users/`, `src/caramello/family/` → `src/caramello/families/`. Todos os imports em `main.py`, `shared/auth.py` e outros arquivos que importam desses módulos devem ser atualizados.

- **D-10:** URLs usam hifens, não underscores. O generator deve traduzir `table_name` (ex.: `family_member`) para URL com hifens (ex.: `family-member`). Regra: `table_name.replace("_", "-")`.

- **D-11:** Estrutura de URL estabelecida:
  ```
  CRUD (gerado, router.py):
    /{domain}/{table_name_with_hyphens}/          → lista e cria
    /{domain}/{table_name_with_hyphens}/{uuid}    → detalhe, update, delete

  Operações (manual, operations.py):
    /{domain}/{operacao}                           → operação simples
    /{domain}/{recurso}/{id}/{sub-recurso}         → operação sobre sub-recurso
  ```
  Exemplos concretos:
  - `/users/user/` — User CRUD (era `/user/`)
  - `/users/me` — Operação get_me (era `/user/me`)
  - `/families/family/` — Family CRUD
  - `/families/family-invitation/` — FamilyInvitation CRUD (era `/family_invitation/`)
  - `/families/registry` — Criar família + owner
  - `/families/families/{uuid}/members` — Membros de uma família

- **D-12:** FamilyMember permanece como `is_link_model: true` no DSL. Sem CRUD gerado para ele. Operações de membership (listar, remover) ficam em `families/operations.py`.

### Role de Owner

- **D-13:** Role de owner é `"owner"` (string) no campo `FamilyMember.role`. Quando o criador da família (via `POST /families/registry`) é adicionado como FamilyMember, recebe `role="owner"`. Membros adicionados via pré-cadastro recebem `role="member"`. Validações de owner verificam `FamilyMember.role == "owner"` na query.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requisitos e Roadmap
- `.planning/REQUIREMENTS.md` §FAMILY-01, §FAMILY-02, §FAMILY-03, §FAMILY-07 — requisitos que esta fase implementa (FAMILY-04/05/06 deferidos)
- `.planning/ROADMAP.md` §Phase 4 — success criteria desta fase (atenção: critérios 3-5 do ROADMAP são do fluxo original; downstream deve usar os critérios do CONTEXT.md como fonte de verdade para esta fase)

### Contexto de Fases Anteriores
- `.planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-CONTEXT.md` §D-06, §D-07, §D-08, §D-09, §D-10, §D-11, §D-12 — decisões do generator (domain field, operations.py pattern, anotações CARAMELLO-GENERATED)
- `.planning/phases/03-estrutura-por-dom-nios-e-autentica-o/03-CONTEXT.md` §D-01, §D-02, §D-04, §D-05, §D-11, §D-12 — configuração Keycloak, JIT provisioning, `get_current_user()`

### DSL e Generator
- `dsl/entities/family.yaml` — entidade Family (atualizar `domain: family` → `domain: families`)
- `dsl/entities/family_member.yaml` — FamilyMember (link model, atualizar domain)
- `dsl/entities/family_invitation.yaml` — FamilyInvitation (redesenhar campos — ver D-01)
- `dsl/entities/user.yaml` — User (atualizar `domain: user` → `domain: users`)
- `dsl/operations/user.yaml` — referência de formato para criar `dsl/operations/family.yaml`
- `scripts/generate_code.py` — generator a evoluir (URL prefix via domain field + hifens em URLs)
- `docs/dsl_rules.md` — regras da DSL que o generator deve seguir

### Código Existente (a ser migrado/evoluído)
- `src/caramello/family/router.py` — CRUD atual (migrar para `src/caramello/families/router.py`, atualizar prefixos)
- `src/caramello/family/models.py` — modelos atuais (migrar path, redesenhar FamilyInvitation)
- `src/caramello/user/operations.py` — referência de padrão para `families/operations.py`
- `src/caramello/shared/auth.py` — adicionar lógica de auto-join após JIT provisioning (ver D-02)
- `src/caramello/main.py` — atualizar imports de routers após renomear diretórios

### Qualidade
- `pyproject.toml` — configuração ruff/mypy strict; todo código desta fase deve passar

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/caramello/shared/auth.py` — `get_current_user()`: já faz JIT provisioning; estender para fazer auto-join (buscar FamilyInvitation por email após criar/encontrar User)
- `src/caramello/shared/database.py` — `get_session()`, `AsyncSession`: padrão de sessão async que operations.py deve usar
- `src/caramello/users/operations.py` (após migração): referência de padrão para `families/operations.py` — router separado, CARAMELLO-GENERATED: implemented, Depends(get_current_user)
- `src/caramello/family/models.py` — `Family`, `FamilyMember`, `FamilyInvitation`: código de referência para migrar; FamilyInvitation será redesenhado

### Established Patterns
- **DSL First:** nunca editar `src/caramello/{domain}/models.py` ou `router.py` diretamente — editar YAML e rodar `bin/generate_code`. Exceção: `operations.py` com anotação `CARAMELLO-GENERATED: implemented`
- **ruff + mypy strict:** todo código gerado e manual deve passar sem erros
- **CARAMELLO-GENERATED annotations:** `stub` = pode sobrescrever; `implemented` = generator pula; ausente = generator cria
- **AsyncSession via Depends:** todos os endpoints usam `AsyncSession = Depends(get_session)`
- **`pg_insert` com ON CONFLICT:** padrão de upsert usado no JIT provisioning de User — replicar para FamilyMember no auto-join
- **Verificação de owner:** query `SELECT * FROM family_member WHERE family_id=X AND user_id=Y AND role='owner'` antes de operações restritas → 403 se não encontrar

### Integration Points
- `src/caramello/main.py`: atualizar todos os includes de router após renomear diretórios (`families.router`, `families.operations`, `users.router`, `users.operations`)
- `alembic/versions/`: nova migration necessária para alterar tabela `family_invitation` (remover `invitee_email`/`expires_at`, adicionar `email`/`status`)
- `src/caramello/shared/auth.py`: auto-join precisa importar `FamilyInvitation` e `FamilyMember` de `caramello.families.models` — atenção para evitar import circular (usar `TYPE_CHECKING` se necessário)

</code_context>

<specifics>
## Specific Ideas

- **Auto-join é transparente para o usuário:** nenhum endpoint precisa ser chamado pelo frontend para "confirmar" a adesão. Acontece no primeiro login, dentro do `get_current_user()`.
- **Endpoint de pré-registro de membro:** `POST /families/families/{family_uuid}/pre-register` com body `{"email": "fulano@gmail.com"}`. Simples, sem fluxo de convite. Owner é verificado antes de criar o FamilyInvitation.
- **Validação de ownership:** padrão recomendado — consulta `FamilyMember` com `family_id + user_id + role="owner"`. Se não encontrar: raise `HTTPException(status_code=403)`.
- **Hifens nas URLs:** `family-invitation` nos endpoints (não `family_invitation`). O generator deve traduzir underscores de `table_name` para hifens na URL.
- **Import circular em shared/auth.py:** ao importar `FamilyInvitation` e `FamilyMember` para o auto-join, usar `from __future__ import annotations` e imports dentro do bloco `TYPE_CHECKING` se necessário para evitar circular imports entre `shared/` e `families/`.
- **Conceito arquitetural D-08-DEFERRED:** foi discutido em detalhe com o operador. Quando for planejado (M2+), o operador já sabe o que é — não re-explicar do zero. Implementar diretamente quando a fase chegar.

</specifics>

<deferred>
## Deferred Ideas

- **FAMILY-04/05/06 — Fluxo de convite com código reutilizável (M2 — expansão de produto):** Owner gera código de convite reutilizável (`POST /families/families/{id}/invitations`). Qualquer usuário usa o código para solicitar entrada (`POST /families/invitations/{code}/join`). Owner aprova ou rejeita (`PATCH /families/invitations/{id}`). Esse fluxo é para quando o Caramello virar produto público com múltiplas famílias de terceiros.

- **Integração Keycloak Admin API (M2+):** App chama Keycloak Admin REST API para criar usuário no Keycloak automaticamente ao pré-registrar. Elimina o duplo cadastro manual. Requer admin credentials na app (ex.: `client_credentials` com role de admin). Deferido por complexidade e por ser desnecessário para 1-5 usuários familiares.

- **Family-scoped CRUD automático no generator (M2+):** Campo `family_scope: true` no YAML de entidade → generator emite filtros automáticos de membership/ownership no CRUD. Ver D-08-DEFERRED para especificação completa.

- **`GET /health` com ping ao banco (OPS-01 — v2 requirements):** Deferido para milestone posterior.

- **Logging estruturado em JSON (`structlog`) (OPS-02 — v2 requirements):** Deferido para milestone posterior.

</deferred>

---

*Phase: 4-Domínio Family*
*Context gathered: 2026-05-26*
