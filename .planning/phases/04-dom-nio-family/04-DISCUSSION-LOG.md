# Phase 4: Domínio Family - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 04-Domínio Family
**Areas discussed:** Modelo de convite, CRUD gerado vs. operações, DSL para operações de negócio

---

## Modelo de convite

| Option | Description | Selected |
|--------|-------------|----------|
| invite_code na Family + FamilyInvitation como join request | Family ganha campo invite_code. FamilyInvitation redesenhado: remove invitee_email, adiciona invitee_id. Usu. usa código → cria FamilyInvitation. Owner faz PATCH. | |
| FamilyInvitation = código + FamilyJoinRequest = solicitação | FamilyInvitation fica como o código reutilizável. Nova entidade FamilyJoinRequest rastreia quem pediu entrada. Semântica mais clara, mais entidades. | |
| **Fluxo completamente diferente (resposta livre do operador)** | Sem convite por código. Operador pré-cadastra email da pessoa na app. Pessoa faz login com Google. App faz matching de email → auto-adiciona à família. | ✓ |

**User's choice:** Resposta livre — o operador rejeitou o modelo de convite por código. Quer pré-cadastro por email com auto-join no login via Google/Keycloak.

**Notes (sequência de esclarecimentos):**
1. **Confirmação do fluxo:** Owner pré-cadastra email → pessoa faz login com Google → Keycloak emite JWT com email → Caramello API faz matching no get_current_user() → auto-join sem aprovação manual. Confirmado: entra automático.
2. **Onde fica a lógica de matching:** O operador estava confuso sobre quem faz o matching (Keycloak vs. a aplicação). Alinhado: Keycloak só autentica. Caramello API (shared/auth.py) faz o matching do email Google contra o FamilyInvitation pré-cadastrado.
3. **Pré-cadastro no Keycloak:** O operador já tem o Keycloak configurado para exigir usuário pré-existente (não aceita qualquer conta Google). Por isso, o duplo cadastro manual (Keycloak + Caramello API) é necessário nesta fase. Integração com Keycloak Admin API deferida para M2+.
4. **FamilyInvitation redesenhado:** Remove invitee_email (EmailStr) e expires_at. Adiciona email (str puro) e status (pending_login/joined). Mantém family_id, inviter_id, created_at, uuid, id.
5. **FAMILY-04/05/06 deferidos:** Fluxo de código de convite reutilizável + join request + aprovação manual foi identificado como "feature de produto público (M2)", não do uso familiar pessoal atual.

---

## CRUD gerado vs. operações

| Option | Description | Selected |
|--------|-------------|----------|
| Substituir por endpoints de negócio | Remover CRUD plano gerado. Implementar apenas endpoints de negócio em operations.py. | |
| **Manter CRUD + validações de perfil** | CRUD gerado permanece. Regras de acesso por perfil/família (resposta livre). | ✓ |

**User's choice:** Resposta livre — o operador quer manter CRUD 100% gerado (nunca editado). CRUD deve ter validações de acesso, mas o mecanismo ideal (filtros automáticos baseados em contexto de família/JWT) é complexo demais para esta fase.

**Notes (sequência de esclarecimentos):**
1. **Entendimento inicial errado:** Claude propôs "substitituir CRUD por operações". O operador corrigiu: quer SEMPRE ter os CRUDs gerados como API — não são descartáveis.
2. **Dois conceitos distintos:** (a) CRUD gerado = operações simples que afetam UMA entidade; (b) Operações de negócio = operações compostas que afetam MÚLTIPLAS entidades. Ex.: criar família + virar owner = operação composta → operations.py.
3. **Conceito arquitetural D-08-DEFERRED:** O operador descreveu a visão de family-scoped CRUD automático: generator suporta `family_scope: true` no YAML → emite filtros automáticos (GET filtra por família do usuário, PATCH/DELETE verificam ownership). JWT poderia carregar claims de família/role. **Esse conceito foi alinhado com detalhe e registrado no CONTEXT.md para não ser re-explicado.**
4. **Decisão para Phase 4:** CRUD com auth básico (token válido). Filtros por família → operações de negócio em operations.py. Family-scoped CRUD → M2+.

---

## DSL para operações de negócio

| Option | Description | Selected |
|--------|-------------|----------|
| **DSL First: dsl/operations/family.yaml → stub gerado** | Cria family.yaml de operações. Generator produz stubs. Implementa stubs. CARAMELLO-GENERATED: implemented. | ✓ |
| Manual direto: escrever family/operations.py sem DSL | Pula o YAML e escreve operations.py diretamente. | |

**User's choice:** DSL First (recomendado).

**Notes (sequência de esclarecimentos):**
1. **Router separado em operations.py:** Confirmado — APIRouter próprio, prefixo separado, registrado em main.py independentemente do CRUD. Mesmo padrão de users/operations.py.
2. **URL prefix confuso:** O operador pediu exemplos concretos para entender a diferença entre CRUD e operações. Com a lista explícita, ficou claro.
3. **Arquitetura de URL por domínio (resposta livre):** O operador corrigiu o prefixo proposto. Quer: domínio = `families`, entidades embaixo do domínio. Ex.: `/families/family`, `/families/family-invitation`. Operações: `/families/{acao}`.
4. **Hifens nas URLs:** Operador confirmou: URLs devem usar hifens, não underscores. `family-invitation` não `family_invitation`.
5. **Refatoração de todos os domínios:** Operador decidiu refatorar AGORA, incluindo user: `/user/` → `/users/user/`, `/user/me` → `/users/me`.
6. **Pluralização — sem automatismo:** Operador esclareceu que o campo `domain` no YAML é usado exatamente como está — sem auto-pluralização. O operador define o valor correto. Domains são atualizados: `user` → `users`, `family` → `families`.
7. **Memória do Phase 3:** O operador lembrou que o campo `domain` foi decidido na Phase 3 para diretórios. Claude confirmou que o mesmo campo serve para URL prefix, sem campo novo necessário.

---

## Claude's Discretion

- Detalhes de implementação do auto-join (query específica, tratamento de erros, atomicidade da transação)
- Formato exato do endpoint de pré-registro (path params, body schema, response)
- Estratégia de migration Alembic para redesenho da FamilyInvitation

## Deferred Ideas

- **FAMILY-04/05/06 — Convite por código reutilizável:** `POST /families/families/{id}/invitations` gera código; `POST /families/invitations/{code}/join` cria join request; `PATCH /families/invitations/{id}` aprova/rejeita. Para M2 (produto público com múltiplas famílias de terceiros).
- **Keycloak Admin API integration:** App pré-registra usuário no Keycloak automaticamente. Elimina duplo cadastro manual. Para M2+.
- **Family-scoped CRUD automático no generator:** `family_scope: true` no YAML → filtros automáticos de membership/ownership no CRUD gerado. Para M2+.
