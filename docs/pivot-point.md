# Pivot Point — Ponto de Convergência entre Estado Atual e Visão Alvo

> **Propósito deste documento:** Registrar com precisão o estado em que o projeto foi pausado, as decisões arquiteturais tomadas após a pausa (documentadas em `apps-platform.md`) e todos os gaps que precisam ser resolvidos antes de avançar com novas funcionalidades. Serve como handoff estruturado para sessões de planejamento com IA.

---

## 1. Contexto da Pausa

O `caramello-api` foi iniciado como o backend Python do Grupo Família. Enquanto o projeto estava pausado, a visão da plataforma evoluiu significativamente: foram tomadas decisões sobre autenticação (Logto), modelo de usuários por grupo, estrutura de banco de dados e organização interna por domínios de negócio — todas documentadas em `docs/apps-platform.md`.

O projeto foi pausado **antes** de qualquer implementação de autenticação ou lógica de negócio. O que existe é uma fundação técnica parcial que precisa ser reconciliada com as decisões tomadas depois.

---

## 2. O Que Foi Construído (Estado Atual)

### 2.1 Infraestrutura presente

| Componente | Estado |
|---|---|
| Pipeline DSL → código gerado (YAML → SQLModel + routers) | Operacional |
| Alembic configurado | Sim (1 migração de consolidação) |
| Configuração via variáveis de ambiente | Sim |
| Scripts operacionais (`bin/`) | Sim (`generate_code`, `manage_db`, `setup_db`, `validate_generation`) |
| Banco de dados | PostgreSQL (obrigatório) |
| Docker / docker-compose | **Não existe** |
| Autenticação (qualquer forma) | **Não existe** |
| Testes | **Não existe** |

### 2.2 Entidades no DSL

Quatro entidades definidas em `dsl/entities/`, com modelos e routers gerados automaticamente:

- `User` — usuário do sistema
- `Family` — grupo familiar
- `FamilyMember` — associação M:M entre usuário e família (com papel)
- `FamilyInvitation` — convite para entrar em uma família

### 2.3 Estrutura de pastas atual

```
src/caramello/
├── api/
│   ├── generated/          # Routers gerados pelo DSL (não editar)
│   └── v1/                 # Esqueleto de rotas manuais (vazio)
├── core/
│   └── config.py           # Settings via pydantic-settings
├── database/
│   └── session.py          # Engine e sessão SQLAlchemy
├── models/                 # Models SQLModel gerados (não editar)
├── repositories/
│   └── user.py             # Esqueleto (vazio)
├── schemas/
│   └── generated/          # Schemas Pydantic gerados (não editar)
├── services/
│   └── user.py             # Esqueleto (vazio)
└── main.py                 # App FastAPI registrando os 4 routers gerados
```

### 2.4 Dependências atuais (pyproject.toml)

```
fastapi, sqlmodel, alembic, pydantic, uvicorn, pyyaml,
email-validator, pydantic-settings, psycopg2-binary
```

---

## 3. Visão Alvo (Decisões de apps-platform.md)

### 3.1 Identidade e autenticação

- **Provedor**: Logto, tenant `tenant-familia`
- **Mecanismo**: OAuth2 / Google + JWT padrão (OIDC)
- **Just-in-time provisioning**: usuário criado no banco no primeiro acesso via JWT
- **Campo de vínculo**: `idp_sub` (o `sub` do JWT emitido pelo Logto) — não `google_id`, não senha local

### 3.2 Modelo de usuários

O schema correto da tabela `users` conforme a decisão do `apps-platform.md`:

```sql
CREATE TABLE users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idp_sub    TEXT NOT NULL UNIQUE,  -- "sub" do JWT do Logto
    email      TEXT NOT NULL UNIQUE,
    name       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.3 Banco de dados

Naming convention definida:

| Database | Propósito |
|---|---|
| `familia_prod` | Produção do Grupo Família |
| `familia_dev` | Desenvolvimento do Grupo Família |

O projeto atualmente usa `caramello_db` como padrão no `.env.example`. Isso precisa ser atualizado.

### 3.4 Estrutura interna por domínios

O `apps-platform.md` define organização por domínio de negócio (não por camada técnica):

```
src/caramello/
├── main.py
├── shared/
│   └── auth.py             # Validação JWT + upsert just-in-time do usuário
├── domains/
│   ├── familia/            # Core: Family, FamilyMember, FamilyInvitation
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── services.py
│   │   └── routes.py
│   ├── agenda/             # Futuro
│   ├── financeiro/         # Futuro
│   └── lista_compras/      # Futuro
└── migrations/             # Alembic, todas as tabelas do grupo
```

### 3.5 Suporte a async real

A decisão de usar FastAPI async pressupõe driver assíncrono de banco. `psycopg2-binary` é síncrono. O driver correto para o stack async é `asyncpg`.

---

## 4. Gaps Identificados

### 4.1 Críticos — bloqueiam qualquer avanço correto

| # | Gap | Impacto |
|---|---|---|
| G1 | `user.yaml` tem `hashed_password` e `google_id` — modelo incompatível com Logto | Qualquer migração gerada com esse modelo estará errada |
| G2 | Nenhuma camada de autenticação JWT/Logto | Impossível proteger qualquer endpoint |
| G3 | Driver de banco `psycopg2-binary` é síncrono | Quebra o contrato async do FastAPI com SQLAlchemy async |

### 4.2 Importantes — necessários para o padrão correto

| # | Gap | Impacto |
|---|---|---|
| G4 | Banco de dados nomeado `caramello_db` no `.env.example` | Diverge da convenção `familia_dev` / `familia_prod` |
| G5 | Estrutura plana (`models/`, `services/`, `repositories/`) em vez de por domínio (`domains/`) | Dificulta adição de novos domínios conforme o projeto cresce |
| G6 | Nenhum Dockerfile nem docker-compose | O projeto não tem padrão de deployment definido |
| G7 | Nenhum teste (nem infraestrutura de testes) | Não há como validar o que for construído |

### 4.3 Estruturais — decisões de design a confirmar

| # | Gap | Decisão pendente |
|---|---|---|
| G8 | O pipeline DSL foi projetado para gerar código flat (um router por entidade). Com a estrutura por domínios, o gerador precisaria evoluir ou ser simplificado. | Manter DSL e evoluir o gerador? Ou simplificar para código manual por domínio? |
| G9 | A migração do Alembic existente foi criada com o modelo antigo (com `hashed_password`, `google_id`) | A migração existente precisa ser descartada e recriada após a correção do modelo de usuário |

---

## 5. Questões a Confirmar no Planejamento

Antes de criar um plano de execução, estas questões precisam de resposta explícita:

1. **DSL**: O pipeline YAML → código gerado deve ser mantido e evoluído, ou o projeto migra para código Python manual por domínio (mais simples, mais alinhado com a estrutura de `domains/`)?

2. **Versioning de API**: Manter o prefixo `/v1` nos endpoints ou adotar prefixo por domínio (`/familia/`, `/agenda/`, etc.)?

3. **Logto disponível**: O Logto já está rodando com o tenant `tenant-familia` configurado, ou a implementação da auth precisa esperar a infraestrutura?

4. **Primeiro domínio**: Após o terreno preparado, qual domínio implementar primeiro — o core de autenticação + família (já tem PRD em `prd_core.md`) ou outro?

---

## 6. Sequência de Atualização Recomendada

Ordem sugerida para preparar o terreno antes de implementar funcionalidades:

```
Fase 1 — Correção do Modelo
  └── Atualizar user.yaml: remover hashed_password, google_id; adicionar idp_sub
  └── Confirmar se a migração existente deve ser descartada e recriada

Fase 2 — Stack Atualizada
  └── Substituir psycopg2-binary por asyncpg
  └── Atualizar session.py para SQLAlchemy async
  └── Adicionar python-jose (ou PyJWT) para validação JWT
  └── Atualizar .env.example com nomes familia_dev / familia_prod

Fase 3 — Estrutura por Domínios
  └── Reorganizar src/caramello/ para estrutura domains/
  └── Resolver questão do DSL (manter ou simplificar)
  └── Criar shared/auth.py com middleware JWT + just-in-time provisioning

Fase 4 — Infraestrutura de Qualidade
  └── Configurar pytest + pytest-asyncio
  └── Criar Dockerfile e docker-compose.yml

Fase 5 — Primeiro Domínio (Piloto)
  └── Implementar domain familia/ com os endpoints do prd_core.md
  └── Validar o padrão completo antes de avançar para agenda, financeiro, etc.
```

---

## 7. Referências

| Documento | Relevância |
|---|---|
| `docs/apps-platform.md` | Fonte da verdade das decisões arquiteturais da plataforma |
| `docs/project_vision.md` | Visão de produto e domínios funcionais planejados |
| `docs/prd_core.md` | Requisitos funcionais de autenticação, famílias e convites |
| `docs/prd_agenda.md` | Requisitos funcionais do domínio de agenda |
| `docs/dsl_rules.md` | Regras do pipeline DSL atual |
| `dsl/entities/user.yaml` | Entidade User — precisa ser corrigida (Gap G1) |
| `alembic/versions/` | Migração existente — pode precisar ser descartada (Gap G9) |
